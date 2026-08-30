#!/usr/bin/env python3
# persistrun.py -- host/device-side driver for agrun_persist (the persistent
# AGX hardware runner). Keeps one live agxrun_persist process (one MTLDevice)
# and issues many (spliced-archive, inputs) -> outputs requests over its stdin,
# with a per-request watchdog timeout that survives GPU wedges by killing and
# transparently restarting the child, so a big field sweep is robust.
#
# CLEAN-ROOM: pure process/protocol plumbing over our own OWN-SHADER runner.
#
# Usage as a library:
#   from persistrun import PersistRunner
#   r = PersistRunner(source="add.metal", function="k", fast_math=False,
#                     agxrun_persist="./agxrun_persist")
#   resp = r.request(archive="spliced.bin", grid=8, tg=8,
#                    ins={0: "in0.bin", 1: "in1.bin"}, outs={2: 32}, timeout=8)
#   # resp = {"status": "OK"|"CMDBUF_ERROR"|"HANG"|..., "outs": {2: b"..."},
#   #         "gputime_ns": int|None, "error": str|None, "restarted": bool}
#   r.close()

import os
import signal
import subprocess
import threading


class PersistRunner:
    def __init__(self, source, function, fast_math, agxrun_persist,
                 restart_hook=None):
        self.source = source
        self.function = function
        self.fast_math = fast_math
        self.exe = agxrun_persist
        self.restart_hook = restart_hook   # called after a wedge, before restart
        self.proc = None
        self._reqno = 0
        self._start()

    def _start(self):
        cmd = [self.exe, "--source", self.source, "--function", self.function]
        if not self.fast_math:
            cmd.append("--no-fast-math")
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
            start_new_session=True)
        ready = self._read_line(timeout=30)
        if not ready or not ready.startswith("READY"):
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"agxrun_persist did not become READY: {ready!r} {err}")
        self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    # ⚠ KNOWN DEFECT, NOT YET FIXED (DEF-0178-1, found by EXP-0178 2026-08-30):
    # _read_line starts a FRESH READER THREAD PER LINE and ABANDONS it on timeout,
    # and that thread re-resolves `self.proc` when it finally runs -- so after the
    # first watchdog timeout the abandoned thread wakes on the REPLACEMENT child's
    # stdout and races the foreground reader. Responses come back truncated
    # ("OUT 0 " with the hex missing), request() raises ValueError on the split,
    # and the run dies. In EXP-0178's pilot ONE benign case poisoned every later
    # request including the unspliced health check, and three consecutive cases
    # were recorded `hang` with restarts=99 -- all false.
    #
    # THE FIRST HANG CAN THEREFORE SILENTLY MANUFACTURE EVERY HANG AFTER IT, and a
    # false hang is indistinguishable from real inertness in a summary. Any sweep
    # that hits a genuine hang and then reports a cascade should be treated as
    # suspect past the first one.
    #
    # Until this is fixed: use one reader thread per child tagged by owner, and
    # record a malformed response as a MEASUREMENT FAILURE with the raw lines kept,
    # never as a hang -- a malformed response is not an observation. EXP-0178's
    # harness/saferunner.py is the reference subclass. This is the sibling of
    # DEF-0153-2 below, which was the EOF spin in this same method.
    def _read_line(self, timeout):
        """Read one line from child stdout with a timeout.

        Returns None on timeout OR on child EOF. Both are 'no usable response'
        and the caller treats either as a wedge.

        DEF-0153-2 (EXP-0153, 2026-08-29): this previously returned the raw
        readline() result. When the child process exits, readline() returns ""
        immediately and forever -- not None -- so the empty string fell through
        every startswith() branch in request()'s loop and it spun at 100% CPU
        with no timeout, hanging the run indefinitely. EXP-0153 lost a run to
        this and had to subclass around it. An exited child is now reported as a
        wedge, which is what it actually is.
        """
        result = [None]

        def rd():
            result[0] = self.proc.stdout.readline()

        t = threading.Thread(target=rd, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            return None            # timed out -> caller treats as wedge
        line = result[0]
        if line == "" or line is None:
            return None            # EOF: child died -> also a wedge
        return line

    def _kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            pass

    def request(self, archive, grid, tg, ins, outs, timeout=8.0):
        """Issue one request; returns a response dict. On watchdog timeout,
        marks HANG, restarts the child (calling restart_hook first), and the
        caller may re-issue."""
        self._reqno += 1
        rid = f"r{self._reqno}"
        parts = [rid, archive, str(grid), str(tg), str(len(ins))]
        for idx, path in ins.items():
            parts.append(f"{idx}:{path}")
        parts.append(str(len(outs)))
        for idx, nbytes in outs.items():
            parts.append(f"{idx}:{nbytes}")
        line = " ".join(parts) + "\n"

        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._restart_after_wedge()
            return {"status": "HANG", "outs": {}, "gputime_ns": None,
                    "error": "child pipe broken", "restarted": True}

        resp = {"status": "UNKNOWN", "outs": {}, "gputime_ns": None,
                "error": None, "restarted": False}
        # read until DONE <rid> (or matching REQ block), watchdog per line.
        saw_req = False
        while True:
            ln = self._read_line(timeout)
            if ln is None:                      # WEDGE
                self._restart_after_wedge()
                resp["status"] = "HANG"
                resp["error"] = f"no response within {timeout}s (GPU wedged)"
                resp["restarted"] = True
                return resp
            ln = ln.rstrip("\n")
            if ln.startswith("REQ "):
                saw_req = True
            elif ln.startswith("STATUS "):
                resp["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                resp["gputime_ns"] = int(ln.split(None, 1)[1])
            elif ln.startswith("OUT "):
                _, idx, hexb = ln.split(None, 2)
                resp["outs"][int(idx)] = bytes.fromhex(hexb)
            elif ln.startswith("ERROR "):
                resp["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                break
        return resp

    def _restart_after_wedge(self):
        self._kill()
        if self.restart_hook:
            self.restart_hook()      # e.g. macvdmtool reboot + wait + re-ssh
        self._start()

    def close(self):
        try:
            if self.proc and self.proc.stdin:
                self.proc.stdin.close()
            if self.proc:
                self.proc.wait(timeout=5)
        except Exception:
            self._kill()

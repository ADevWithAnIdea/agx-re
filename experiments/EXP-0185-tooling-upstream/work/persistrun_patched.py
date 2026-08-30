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
#   # resp = {"status": "OK"|"CMDBUF_ERROR"|"HANG"|"MALFORMED"|...,
#   #         "outs": {2: b"..."}, "gputime_ns": int|None, "error": str|None,
#   #         "restarted": bool, "raw": [str], "discarded_lines": int,
#   #         "restarts": int, "malformed_total": int}
#   r.close()
#
# "MALFORMED" is a MEASUREMENT FAILURE, not an observation about the encoding:
# score it as `measurement_failed`, keep resp["raw"], and remove it from any
# agreement/coverage computation -- never as `ok`, `fault`, or an inertness
# reading (FIELD-SWEEP-PROTOCOL section 5; EXP-0178 analysis/verdicts.py).

import os
import queue
import signal
import subprocess
import threading
import time


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
        self.restarts = 0          # child restarts after a wedge
        self.malformed = 0         # unparseable responses (measurement failures)
        self.discarded_lines = 0   # lines from a killed child, dropped by the pump
        self._start()

    def _start(self):
        cmd = [self.exe, "--source", self.source, "--function", self.function]
        if not self.fast_math:
            cmd.append("--no-fast-math")
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
            start_new_session=True)
        self._install_pump()
        ready = self._read_line(timeout=30)
        if not ready or not ready.startswith("READY"):
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"agxrun_persist did not become READY: {ready!r} {err}")
        self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    # DEF-0178-1 (found by EXP-0178 2026-08-30; FIXED here by EXP-0185 2026-08-30).
    #
    # HISTORY -- keep it, it is the paper trail for every capture taken before the fix.
    # `_read_line` used to start a FRESH READER THREAD PER LINE and ABANDON it on
    # timeout, and that thread re-resolved `self.proc` when it finally ran -- so after
    # the first watchdog timeout the abandoned thread could wake on the REPLACEMENT
    # child's stdout and race the foreground reader. Responses came back truncated
    # ("OUT 0 " with the hex missing), request() raised ValueError on the split, and the
    # run died. In EXP-0178's pilot ONE benign case poisoned every later request
    # including the unspliced health check, and three consecutive cases were recorded
    # `hang` with restarts=99 -- all false.
    #
    # A REAL HANG WAS NEVER REQUIRED: a mere WATCHDOG TIMEOUT was enough. EXP-0178
    # verified by hand, outside the harness, that its pre-registered hang candidate runs
    # CLEAN on G17P -- STATUS OK, GPUTIME_NS 5000, sentinel written -- so all four
    # "hangs" in its pilots were manufactured by this defect on a case the hardware
    # handles without complaint. The suspect set for PRE-FIX captures is therefore any
    # experiment whose runner ever timed out, not merely those that hit a real hang, and
    # a false `hang` is indistinguishable from real inertness in a summary.
    # FIELD-SWEEP-PROTOCOL section 3(d).
    #
    # THE FIX: exactly ONE reader thread per child, started in _start() and tagged with
    # the process object that owns it; lines from a killed child are discarded and
    # counted (`discarded_lines`) instead of being handed to the wrong request.
    # `tools/agxtest/saferunner.py` is the equivalent subclass, kept for experiments that
    # pin an older copy of this file; `tools/agxtest/selftest_tools.py` is the offline
    # gate (no device) for both. DEF-0153-2 below is the sibling defect in this same
    # method and stays fixed.
    def _install_pump(self):
        """Start the single reader thread for the CURRENT child (called by _start)."""
        self._q = queue.Queue()
        p = self.proc

        def pump():
            try:
                for ln in iter(p.stdout.readline, ""):
                    self._q.put((p, ln))
            except Exception:
                pass
            self._q.put((p, None))             # explicit EOF marker (DEF-0153-2)

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        self._pump = t

    def _read_line(self, timeout):
        """Read one line from the CURRENT child's stdout with a timeout.

        Returns None on timeout OR on child EOF. Both are 'no usable response'
        and the caller treats either as a wedge.

        DEF-0153-2 (EXP-0153, 2026-08-29): this previously returned the raw
        readline() result. When the child process exits, readline() returns ""
        immediately and forever -- not None -- so the empty string fell through
        every startswith() branch in request()'s loop and it spun at 100% CPU
        with no timeout, hanging the run indefinitely. EXP-0153 lost a run to
        this and had to subclass around it. An exited child is now reported as a
        wedge, which is what it actually is; the pump pushes an explicit None at
        EOF so that stays true with one thread per child.
        """
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                return None            # timed out -> caller treats as wedge
            try:
                owner, line = self._q.get(timeout=min(left, 0.5))
            except queue.Empty:
                continue
            if owner is not self.proc:
                self.discarded_lines += 1   # leftovers from a killed child
                continue
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
                    "error": "child pipe broken", "restarted": True, "raw": [],
                    "discarded_lines": self.discarded_lines,
                    "restarts": self.restarts,
                    "malformed_total": self.malformed}

        resp = {"status": "UNKNOWN", "outs": {}, "gputime_ns": None,
                "error": None, "restarted": False, "raw": []}
        # read until DONE <rid> (or matching REQ block), watchdog per line.
        saw_req = False
        while True:
            ln = self._read_line(timeout)
            if ln is None:                      # WEDGE
                self._restart_after_wedge()
                resp["status"] = "HANG"
                resp["error"] = f"no response within {timeout}s (GPU wedged)"
                resp["restarted"] = True
                break
            ln = ln.rstrip("\n")
            # Keep the raw response lines (truncated for size). A measurement failure
            # must be diagnosable from the committed raw instead of guessed at.
            resp["raw"].append(ln[:32] + (f"..+{len(ln) - 32}" if len(ln) > 32 else ""))
            if ln.startswith("REQ "):
                saw_req = True
            elif ln.startswith("STATUS "):
                resp["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                try:
                    resp["gputime_ns"] = int(ln.split(None, 1)[1])
                except ValueError:
                    pass
            elif ln.startswith("OUT "):
                # DEF-0178-1, second half. This was
                #     _, idx, hexb = ln.split(None, 2)
                # which RAISES on a short line and takes the whole run with it, so a
                # caller either crashed or -- if it wrapped the call -- recorded a
                # `hang`. A malformed response is a MEASUREMENT FAILURE and is not an
                # observation: it is recorded as one, with the raw lines kept.
                bits = ln.split(None, 2)
                if len(bits) < 3:
                    self.malformed += 1
                    resp["status"] = "MALFORMED"
                    resp["error"] = "truncated OUT line: %r" % ln[:80]
                    continue
                try:
                    resp["outs"][int(bits[1])] = bytes.fromhex(bits[2])
                except ValueError as e:
                    self.malformed += 1
                    resp["status"] = "MALFORMED"
                    resp["error"] = "unparseable OUT payload (%s): %r" % (e, ln[:80])
            elif ln.startswith("ERROR "):
                resp["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                break
        resp["discarded_lines"] = self.discarded_lines
        resp["restarts"] = self.restarts
        resp["malformed_total"] = self.malformed
        return resp

    def _restart_after_wedge(self):
        self.restarts += 1
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

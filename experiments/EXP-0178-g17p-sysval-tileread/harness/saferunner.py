#!/usr/bin/env python3
"""EXP-0178 leak-free persistent-runner wrappers.

DEFECT FOUND BY PILOT (2026-08-30, `work/pilot01` / `work/pilot02`, no gated
dispatch had occurred). Both shared drivers -- `tools/agxtest/persistrun.py` and
the render analogue this experiment copied from our own EXP-0147 -- read one
line by starting a **fresh daemon thread per read** and ABANDONING it on
timeout. The abandoned thread is still blocked in `readline()`, and it resolves
`self.proc` at *execution* time, so after the very first watchdog timeout it
wakes up on the **replacement** child's stdout and races the foreground reader
on the same stream. Responses then come back TRUNCATED: `OUT 0 ` with the hex
missing, which the shared parser turns into
`ValueError: not enough values to unpack (expected 3, got 2)`.

Observed consequence in `work/pilot02`: one genuine hang (the pre-registered
byte0-bit2 falsifier) corrupted **every subsequent request**, including the
unspliced health check, so the runner never recovered and three cases in a row
were recorded `hang` with `restarts=99`. Without this fix a single hang
poisons the rest of the run -- and this experiment deliberately has no hang
budget, so hangs are expected.

EXP-0153 hit the sibling of this bug (DEF-0153-2: an exited child makes
`readline()` return `""` forever, which fell through every branch and spun at
100% CPU) and also had to subclass around it.

The fix: **exactly one reader thread per child, bound to that child's
lifetime**, feeding a queue tagged with the process object it came from. Lines
from a dead child are discarded instead of being handed to the wrong request.

The shared tools are NOT modified -- other experiments are running against
them concurrently, and mutating them under those agents would be a courtesy
violation of FIELD-SWEEP-PROTOCOL section 7.
"""
import json
import os
import queue
import signal
import subprocess
import threading
import time

from persistrun import PersistRunner
from rsdrv import RenderRunner


class _Pumped:
    """One reader thread per child, tagged with its owner."""

    def _install_pump(self):
        self._q = queue.Queue()
        p = self.proc

        def pump():
            try:
                for ln in iter(p.stdout.readline, ""):
                    self._q.put((p, ln))
            except Exception:                                  # noqa: BLE001
                pass
            self._q.put((p, None))                             # EOF marker

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        self._pump = t

    def _pumped_readline(self, timeout):
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                return None
            try:
                owner, ln = self._q.get(timeout=min(left, 0.5))
            except queue.Empty:
                continue
            if owner is not self.proc:      # leftovers from a killed child
                continue
            return ln                       # None on EOF -> caller treats as wedge


class SafePersistRunner(_Pumped, PersistRunner):
    def _start(self):
        cmd = [self.exe, "--source", self.source, "--function", self.function]
        if not self.fast_math:
            cmd.append("--no-fast-math")
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        self._install_pump()
        ready = self._read_line(timeout=30)
        if not ready or not ready.startswith("READY"):
            raise RuntimeError("agxrun_persist did not become READY: %r" % (ready,))
        self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    def _read_line(self, timeout):
        return self._pumped_readline(timeout)



    # ------------------------------------------------------------------ #
    # A defensive re-implementation of PersistRunner.request().
    #
    # The shared parser does `_, idx, hexb = ln.split(None, 2)` on every line
    # beginning with "OUT ", which RAISES on a short line and takes the whole
    # run with it. A malformed response is a measurement failure, not a program
    # crash, so it is recorded as one -- with the offending raw lines kept, so
    # the cause is diagnosable from raw/ instead of guessed at.
    # ------------------------------------------------------------------ #
    def request(self, archive, grid, tg, ins, outs, timeout=8.0):
        self._reqno += 1
        rid = "r%d" % self._reqno
        parts = [rid, archive, str(grid), str(tg), str(len(ins))]
        parts += ["%d:%s" % (i, p) for i, p in ins.items()]
        parts.append(str(len(outs)))
        parts += ["%d:%d" % (i, n) for i, n in outs.items()]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._kill(); self._start()
            return {"status": "HANG", "outs": {}, "gputime_ns": None,
                    "error": "child pipe broken", "restarted": True, "raw": []}

        resp = {"status": "UNKNOWN", "outs": {}, "gputime_ns": None,
                "error": None, "restarted": False, "raw": []}
        while True:
            ln = self._read_line(timeout)
            if ln is None:
                self._kill(); self._start()
                resp.update(status="HANG", restarted=True,
                            error="no response within %ss (GPU wedged or child died)"
                                  % timeout)
                return resp
            ln = ln.rstrip("\n")
            resp["raw"].append(ln[:24] + ("..%d" % len(ln) if len(ln) > 24 else ""))
            if ln.startswith("STATUS "):
                resp["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                try:
                    resp["gputime_ns"] = int(ln.split(None, 1)[1])
                except ValueError:
                    pass
            elif ln.startswith("OUT "):
                bits = ln.split(None, 2)
                if len(bits) < 3:
                    resp["status"] = "MALFORMED"
                    resp["error"] = "truncated OUT line: %r" % ln[:80]
                    continue
                try:
                    resp["outs"][int(bits[1])] = bytes.fromhex(bits[2])
                except ValueError as e:
                    resp["status"] = "MALFORMED"
                    resp["error"] = "unparseable OUT payload (%s): %r" % (e, ln[:80])
            elif ln.startswith("ERROR "):
                resp["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                break
        return resp

class SafeRenderRunner(_Pumped, RenderRunner):
    def _start(self):
        cmd = [self.exe, "--source", self.source] + (["--fast-math"] if self.fast_math else [])
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        self._install_pump()
        ln = self._readline(60)
        if not ln or not ln.startswith("READY"):
            raise RuntimeError("rendersweep not READY: %r" % (ln,))
        self.device = ln.split(None, 1)[1].strip()

    def _readline(self, timeout):
        return self._pumped_readline(timeout)

#!/usr/bin/env python3
"""EXP-0180 leak-free persistent-runner wrapper (compute half only).

ADOPTED VERBATIM from our own `experiments/EXP-0178-g17p-sysval-tileread/harness/
saferunner.py` (same project, same rules), minus its render half, which this
experiment does not use. Its original header is preserved below.

WHY EXP-0180 NEEDS IT (DEF-0178-1). This experiment pre-registers NO abort path
and NO hang budget, and its `LEN` / `E8_*` / `F12_*` arms deliberately mutate
LENGTH- and IDENTITY-selecting bits of a 6/8/10/12-byte polymorphic family, so
instruction-stream desyncs -- and therefore watchdog timeouts -- are expected BY
DESIGN. With the shared driver's abandoned-reader-thread defect, the FIRST
genuine hang silently manufactures every hang after it. A false `hang` and a
real inertness are indistinguishable in a summary, and this experiment's whole
job is deciding whether 25 row-claims should be WITHDRAWN -- so a false-hang
cascade would make it withdraw rows for a harness artefact, the exact inverse of
the defect that put those rows in this state.

`tools/agxtest/persistrun.py` is NOT modified: EXP-0179 is running against it
concurrently (FIELD-SWEEP-PROTOCOL section 7 courtesy).

A `MALFORMED` response maps to outcome `measurement_failed` in this experiment:
a FAILURE TO MEASURE, never `hang`, never `fault`, never an observation. The raw
lines are kept in the case record, the case is retried up to 3 times, and a case
still failing is EXCLUDED from `values_dispatched` so it cannot inflate coverage.

--- original EXP-0178 header follows ---

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

================================ UPSTREAM NOTES ================================

This module is written to be LIFTED INTO `tools/agxtest/persistrun.py` (and the
render analogue) once the machine is clear. Two independent changes; either can
be taken alone. Both are DEFAULTS-PRESERVING: no signature, no return shape and
no status string that an existing caller already handles is changed, and a run
that never times out behaves exactly as before.

--- CHANGE 1: one reader thread per child, tagged by owner -------------------

BEFORE (`persistrun.py::_read_line`, and the identical body in `rsdrv.py`):

    def _read_line(self, timeout):
        result = [None]
        def rd():
            result[0] = self.proc.stdout.readline()   # <-- resolves self.proc
        t = threading.Thread(target=rd, daemon=True)  #     at EXECUTION time
        t.start(); t.join(timeout)
        if t.is_alive():
            return None            # thread is ABANDONED, still blocked in read

AFTER: `_install_pump()` starts ONE thread per child in `_start()`, pushing
`(proc, line)` onto a queue; `_read_line` pops from the queue and DISCARDS any
tuple whose `proc` is not the current child.

Why it matters: on timeout the old code abandons a live thread. `_restart_after_wedge`
then kills the child and starts a new one, and the abandoned thread -- which
re-reads `self.proc` when it finally runs -- attaches to the REPLACEMENT child
and races the foreground reader on the same stream. Lines get split between the
two readers, so responses come back truncated.

Defaults preserved: `_read_line` still returns a line, or `None` for
timeout/EOF. DEF-0153-2 (EOF must be reported as a wedge, not `""`) is kept: the
pump pushes an explicit `None` at EOF.

--- CHANGE 2: a malformed response is a MEASUREMENT FAILURE, not an exception --

BEFORE (`persistrun.py::request`):

    elif ln.startswith("OUT "):
        _, idx, hexb = ln.split(None, 2)      # raises on a short line
        resp["outs"][int(idx)] = bytes.fromhex(hexb)

AFTER:

    elif ln.startswith("OUT "):
        bits = ln.split(None, 2)
        if len(bits) < 3:
            resp["status"] = "MALFORMED"
            resp["error"] = "truncated OUT line: %r" % ln[:80]
            continue
        ...  # plus a try/except around bytes.fromhex for a corrupt payload

and `resp` gains a `"raw"` list of the (truncated-for-size) response lines, so
the cause is diagnosable from the committed raw instead of guessed at.

Why it matters, and this is the half that matters most: **a malformed response
is not an observation and must not be scored as one.** The old code raised, so a
caller either crashed or -- if it wrapped the call -- recorded a HANG. A false
`hang` and a real inertness are indistinguishable in a summary, so one genuine
hang could withdraw fields for an artefact.

Defaults preserved: `MALFORMED` is a NEW status value; every existing status
string is produced under exactly the same conditions as before. Callers that
test `status != "OK"` keep working unchanged and simply see the new value.

--- PROOF WITHOUT A DEVICE ---------------------------------------------------

`work/stub/fakerunner.py` speaks the same line protocol with no Metal and no
GPU, in a `--truncate` mode that emits `OUT 0` with the payload missing.
`harness/selftest.py` gate G9 drives both modes and asserts that the good mode
parses and the truncated mode yields `MALFORMED` with the raw lines kept --
never a crash and never a `hang`.
"""
import json
import os
import queue
import signal
import subprocess
import threading
import time

from persistrun import PersistRunner


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

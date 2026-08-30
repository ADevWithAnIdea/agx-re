#!/usr/bin/env python3
"""EXP-0179 leak-free persistent-runner wrapper — required for the hang-prone tail.

DEF-0178-1 / FIELD-SWEEP-PROTOCOL section 3(d). `tools/agxtest/persistrun.py`
reads one line by starting a FRESH daemon thread per read and ABANDONING it on
timeout. The abandoned thread resolves `self.proc` at EXECUTION time, so after
the first watchdog timeout it wakes on the REPLACEMENT child's stdout and races
the foreground reader. Responses come back truncated (`OUT 0 ` with the hex
missing), which the shared parser turns into
`ValueError: not enough values to unpack (expected 3, got 2)`.

**So the FIRST hang can silently manufacture every hang after it.** EXP-0178's
pilot recorded three consecutive false `hang`s with `restarts=99` from one
benign case.

WHY THIS EXPERIMENT NEEDS IT NOW AND DID NOT BEFORE. Arms G/T/M/B3/B5/B6/TL/R/L
and arm S produced **0 hangs in 10,484 dispatch results**, so the precondition
never occurred and none of those results can be a 3(d) artefact (RESULTS.md
section 7a). The remaining tail is the one part of this experiment **expected to
hang for real**: arm N destroys a return address on purpose. A false cascade
after arm N's first genuine hang would corrupt arms F and O, and a false `hang`
is indistinguishable from real inertness in a summary. That is exactly the
failure this file exists to prevent.

LINEAGE: `experiments/EXP-0178-g17p-sysval-tileread/harness/saferunner.py`
(our own code, this repository, same project). This is the COMPUTE half only —
EXP-0178's render half is not needed here — re-derived rather than imported so
this experiment's harness stays self-contained and hash-pinned on its own.

THE SHARED TOOL IS NOT MODIFIED. Other experiments are running against it
concurrently and the orchestrator deliberately left it unpatched while runs are
in flight; mutating it under those agents would be a FIELD-SWEEP-PROTOCOL
section 7 courtesy violation.

TWO CHANGES, both defaults-preserving:

1. **One reader thread per child, tagged by owner.** `_install_pump()` starts a
   single thread per child pushing `(proc, line)` onto a queue; `_read_line`
   discards any tuple whose `proc` is not the current child. A timeout no longer
   abandons a live reader. DEF-0153-2 is preserved: EOF pushes an explicit
   `None`, so an exited child is reported as a wedge rather than as `""` forever.

2. **A malformed response is a MEASUREMENT FAILURE, not an exception.** A short
   or unparseable `OUT` line yields the NEW status `MALFORMED` with the raw
   response lines kept, instead of raising. This is the half that matters most:
   a malformed response is not an observation and must not be scored as one —
   under the old code a caller either crashed or recorded a `hang`, and a false
   `hang` could withdraw a field for an artefact.

Every pre-existing status string is produced under exactly the same conditions
as before, so a run that never times out behaves identically.
"""
import queue
import subprocess
import threading
import time


class PumpedReader(object):
    """One reader thread per child, tagged with its owner."""

    def _install_pump(self):
        self._q = queue.Queue()
        p = self.proc
        self._pump_owner = p

        def pump():
            try:
                for ln in iter(p.stdout.readline, ""):
                    self._q.put((p, ln))
            except Exception:
                pass
            self._q.put((p, None))          # explicit EOF marker (DEF-0153-2)

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        self._pump = t
        self.discarded_lines = getattr(self, "discarded_lines", 0)

    def _pumped_readline(self, timeout):
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                return None                 # timeout -> caller treats as wedge
            try:
                owner, ln = self._q.get(timeout=min(left, 0.5))
            except queue.Empty:
                continue
            if owner is not self.proc:      # leftovers from a killed child
                self.discarded_lines += 1
                continue
            return ln                       # None on EOF -> caller treats as wedge


def make_safe_runner(PersistRunner):
    """Build the SafePersistRunner subclass over whichever PersistRunner class the
    caller loaded (sweeprun loads the PINNED copy under this experiment's own
    tools/, never the shared one on the neo)."""

    class SafePersistRunner(PumpedReader, PersistRunner):

        def _start(self):
            cmd = [self.exe, "--source", self.source, "--function", self.function]
            if not self.fast_math:
                cmd.append("--no-fast-math")
            self.proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True)
            self._install_pump()
            self.restarts = getattr(self, "restarts", 0)
            self.malformed = getattr(self, "malformed", 0)
            ready = self._read_line(timeout=30)
            if not ready or not ready.startswith("READY"):
                raise RuntimeError("agxrun_persist did not become READY: %r" % (ready,))
            self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

        def _read_line(self, timeout):
            return self._pumped_readline(timeout)

        def _restart_after_wedge(self):
            self.restarts = getattr(self, "restarts", 0) + 1
            self._kill()
            if getattr(self, "restart_hook", None):
                self.restart_hook()
            self._start()

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
                self._restart_after_wedge()
                return {"status": "HANG", "outs": {}, "gputime_ns": None,
                        "error": "child pipe broken", "restarted": True, "raw": [],
                        "discarded_lines": self.discarded_lines,
                        "restarts": self.restarts}

            resp = {"status": "UNKNOWN", "outs": {}, "gputime_ns": None,
                    "error": None, "restarted": False, "raw": []}
            while True:
                ln = self._read_line(timeout)
                if ln is None:
                    self._restart_after_wedge()
                    resp.update(status="HANG", restarted=True,
                                error="no response within %ss (GPU wedged or "
                                      "child died)" % timeout)
                    break
                ln = ln.rstrip("\n")
                resp["raw"].append(ln[:32] + ("..+%d" % (len(ln) - 32)
                                              if len(ln) > 32 else ""))
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
                        self.malformed = getattr(self, "malformed", 0) + 1
                        resp["status"] = "MALFORMED"
                        resp["error"] = "truncated OUT line: %r" % ln[:80]
                        continue
                    try:
                        resp["outs"][int(bits[1])] = bytes.fromhex(bits[2])
                    except ValueError as e:
                        self.malformed = getattr(self, "malformed", 0) + 1
                        resp["status"] = "MALFORMED"
                        resp["error"] = ("unparseable OUT payload (%s): %r"
                                         % (e, ln[:80]))
                elif ln.startswith("ERROR "):
                    resp["error"] = ln.split(None, 1)[1]
                elif ln.startswith("DONE "):
                    break
            resp["discarded_lines"] = self.discarded_lines
            resp["restarts"] = getattr(self, "restarts", 0)
            resp["malformed_total"] = getattr(self, "malformed", 0)
            return resp

    return SafePersistRunner

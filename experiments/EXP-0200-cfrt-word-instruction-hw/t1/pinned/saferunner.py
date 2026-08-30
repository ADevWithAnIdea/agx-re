#!/usr/bin/env python3
"""Leak-free wrappers for the persistent AGX runners (DEF-0178-1).

UPSTREAMED 2026-08-30 by EXP-0185 from `EXP-0178-g17p-sysval-tileread/harness/saferunner.py`
and `EXP-0179-g17p-call/harness/saferunner.py` (our own code, this repository). The two
experiment copies stay where they are as evidence; this is the shared one.

WHY THIS FILE EXISTS
====================

`tools/agxtest/persistrun.py` (and the `rsdrv.py` render driver that experiments keep
copying) reads one line by starting a **fresh daemon thread per read** and **abandoning it
on timeout**. The abandoned thread is still blocked in `readline()`, and it resolves
`self.proc` at *execution* time -- so after the very first watchdog timeout it can wake on
the **replacement** child's stdout and race the foreground reader on the same stream.
Responses then come back TRUNCATED (`OUT 0 ` with the hex missing), which the shared
parser turns into `ValueError: not enough values to unpack (expected 3, got 2)`, and the
run dies.

Observed cost (EXP-0178 `work/pilot02`): one case poisoned **every subsequent request**,
including the unspliced health check, and three consecutive cases were recorded `hang` with
`restarts=99` -- all false.

**A REAL HANG IS NOT REQUIRED. A mere WATCHDOG TIMEOUT is enough to start the cascade.**
EXP-0178 verified by hand, outside the harness, that its pre-registered hang candidate runs
CLEAN on G17P (`STATUS OK`, `GPUTIME_NS 5000`, integrity sentinel written), so all four
"hangs" in its pilots were manufactured by this defect on a case the hardware handles
without complaint. The suspect set is therefore **any experiment whose runner ever timed
out**, not merely those that hit a real hang. See FIELD-SWEEP-PROTOCOL section 3(d).

EXP-0153 hit the sibling of this bug (DEF-0153-2: an exited child makes `readline()` return
`""` forever, which fell through every branch and spun at 100% CPU with no timeout).

THE TWO CHANGES (both DEFAULTS-PRESERVING)
==========================================

1. **One reader thread per child, tagged by owner.** `_install_pump()` starts a single
   thread per child pushing `(proc, line)` onto a queue; `_read_line` pops and DISCARDS any
   tuple whose `proc` is not the current child. A timeout no longer abandons a live reader.
   `_read_line` still returns a line, or `None` for timeout/EOF -- DEF-0153-2 is preserved
   because the pump pushes an explicit `None` at EOF.

2. **A malformed response is a MEASUREMENT FAILURE, not an exception.** A short or
   unparseable `OUT` line yields the NEW status `MALFORMED` with the raw response lines
   kept in `resp["raw"]`, instead of raising. This is the half that matters most: **a
   malformed response is not an observation and must not be scored as one.** Under the old
   code a caller either crashed or -- if it wrapped the call -- recorded a `hang`, and a
   false `hang` is indistinguishable from real inertness in a summary, so one genuine
   timeout could withdraw fields for an artefact.

   `MALFORMED` is a NEW status value; every pre-existing status string is produced under
   exactly the same conditions as before, so a run that never times out behaves identically.

Downstream rule (FIELD-SWEEP-PROTOCOL section 5 / EXP-0178 `analysis/verdicts.py`): score a
`MALFORMED` response as `measurement_failed` and REMOVE it from the agreement computation
and from `values_dispatched` -- never as `ok`, never as `fault`, never as an inertness
reading -- and refuse a field whose measurement failures exceed 1% of its dispatched values.

USE
===

    import sys, os
    sys.path.insert(0, ".../tools/agxtest")
    from saferunner import SafePersistRunner
    r = SafePersistRunner(source="add.metal", function="k", fast_math=False,
                          agxrun_persist="./agxrun_persist")
    resp = r.request(archive="spliced.bin", grid=8, tg=8, ins={}, outs={0: 32}, timeout=8)
    if resp["status"] == "MALFORMED":
        ...                       # measurement failure: keep resp["raw"], do NOT score it

If your experiment pins its own copy of `persistrun.py` (recommended -- hash-pinned
harnesses should not float with the shared tool), build the subclass over that class:

    SafeRunner = make_safe_runner(my_pinned_persistrun.PersistRunner)

The render analogue (`rsdrv.py`-style JSON line protocol, one response line per request)
gets the same treatment through `make_safe_render_runner(RenderRunner)`.

OFFLINE GATE (no device, no GPU, no SSH)
========================================

    python3 tools/agxtest/selftest_tools.py

drives `tools/agxtest/fakepersist.py` -- a stand-in that speaks the same line protocol --
and asserts that a truncated `OUT` line RAISES under the shared runner and comes back as
`MALFORMED` with the raw lines kept under this one, and that the owner tag discards a dead
child's leftovers deterministically.

Clean-room: pure process/protocol plumbing over our own OWN-SHADER runner. No Apple binary
is inspected.
"""
import importlib.util
import os
import queue
import subprocess
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))

__all__ = ["PumpedReader", "make_safe_runner", "make_safe_render_runner",
           "load_persist_runner", "SafePersistRunner"]


def load_persist_runner():
    """Return the `PersistRunner` class, preferring whatever is already importable
    (an experiment's pinned copy) and falling back to the sibling shared file."""
    try:
        from persistrun import PersistRunner        # noqa: WPS433
        return PersistRunner
    except ImportError:
        pass
    path = os.path.join(_HERE, "persistrun.py")
    spec = importlib.util.spec_from_file_location("agxtest_persistrun", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PersistRunner


class PumpedReader(object):
    """One reader thread per child, tagged with its owner.

    Mix in BEFORE the runner base class so its `_read_line` wins:
    `class Safe(PumpedReader, PersistRunner)`.
    """

    def _install_pump(self):
        """Start the single reader thread for the CURRENT child. Call at the end of
        `_start()`, after `self.proc` exists."""
        self._q = queue.Queue()
        self.discarded_lines = getattr(self, "discarded_lines", 0)
        p = self.proc
        self._pump_owner = p

        def pump():
            try:
                for ln in iter(p.stdout.readline, ""):
                    self._q.put((p, ln))
            except Exception:                       # noqa: BLE001 - child died mid-read
                pass
            self._q.put((p, None))                  # explicit EOF marker (DEF-0153-2)

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        self._pump = t

    def _pumped_readline(self, timeout):
        """Return one line from the CURRENT child, or None on timeout/EOF.

        Lines produced by a previous (killed) child are discarded and counted, not
        handed to the caller: that hand-off is the whole defect."""
        self.discarded_lines = getattr(self, "discarded_lines", 0)
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                return None                          # timeout -> caller treats as wedge
            try:
                owner, ln = self._q.get(timeout=min(left, 0.5))
            except queue.Empty:
                continue
            if owner is not self.proc:               # leftovers from a killed child
                self.discarded_lines += 1
                continue
            return ln                                # None at EOF -> also a wedge


_SAFE_CACHE = {}


def make_safe_runner(base=None):
    """Build a `SafePersistRunner` subclass over `base` (default: the importable
    `PersistRunner`). Cached, so repeated calls return the same class."""
    if base is None:
        base = load_persist_runner()
    if base in _SAFE_CACHE:
        return _SAFE_CACHE[base]

    class SafePersistRunner(PumpedReader, base):
        """`PersistRunner` with a per-child reader and MALFORMED instead of a crash."""

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
            """Issue one request. Same protocol and same return keys as the shared
            runner, plus `raw` / `discarded_lines` / `restarts` / `malformed_total`,
            and the new `MALFORMED` status for an unparseable response."""
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
                        "restarts": self.restarts,
                        "malformed_total": getattr(self, "malformed", 0)}

            resp = {"status": "UNKNOWN", "outs": {}, "gputime_ns": None,
                    "error": None, "restarted": False, "raw": []}
            while True:
                ln = self._read_line(timeout)
                if ln is None:
                    self._restart_after_wedge()
                    resp.update(status="HANG", restarted=True,
                                error="no response within %ss (GPU wedged or child died)"
                                      % timeout)
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

    _SAFE_CACHE[base] = SafePersistRunner
    return SafePersistRunner


def make_safe_render_runner(base):
    """Same treatment for the `rsdrv.py`-style persistent RENDER runner.

    That driver has the identical abandoned-reader body and a one-JSON-line-per-request
    protocol; `base` is passed in because `rsdrv.py` is copied per experiment rather
    than shared. A response that is not parseable JSON already comes back as
    `BAD_RESPONSE` there (its analogue of `MALFORMED`), so only change 1 applies."""

    class SafeRenderRunner(PumpedReader, base):
        def _start(self):
            cmd = [self.exe, "--source", self.source] + (
                ["--fast-math"] if self.fast_math else [])
            self.proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True)
            self._install_pump()
            self.restarts = getattr(self, "restarts", 0)
            ln = self._readline(60)
            if not ln or not ln.startswith("READY"):
                raise RuntimeError("rendersweep not READY: %r" % (ln,))
            self.device = ln.split(None, 1)[1].strip()

        def _readline(self, timeout):
            return self._pumped_readline(timeout)

        # some copies of the render driver spell it the other way
        def _read_line(self, timeout):
            return self._pumped_readline(timeout)

    return SafeRenderRunner


try:                                     # convenience binding over the shared class
    SafePersistRunner = make_safe_runner()
except Exception as _e:                  # noqa: BLE001 - persistrun.py missing/renamed
    SafePersistRunner = None
    _SAFE_IMPORT_ERROR = _e


if __name__ == "__main__":
    print("saferunner: import this module; run the offline gate with")
    print("  python3 %s" % os.path.join(_HERE, "selftest_tools.py"))
    sys.exit(0)

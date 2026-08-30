#!/usr/bin/env python3
"""EXP-0201 leak-free persistent-runner wrappers (compute + acceleration-structure).

WHY THIS FILE EXISTS -- FIELD-SWEEP-PROTOCOL section 3(d), widened 2026-08-30:

    A mere WATCHDOG TIMEOUT -- not a real hang -- starts a false-hang cascade on
    the shared `tools/agxtest/persistrun.py`.

The shared driver starts a FRESH reader thread per line and ABANDONS it on
timeout, and that thread re-resolves `self.proc` at execution time, so after the
first timeout the abandoned thread wakes on the REPLACEMENT child's stdout and
races the foreground reader. Responses come back truncated (`OUT 0 ` with the
hex missing), the shared parser raises `ValueError: not enough values to unpack`,
and the run dies. In EXP-0178's pilot ONE benign case poisoned every later
request including the unspliced health check and three consecutive cases were
recorded `hang` with `restarts=99` -- all false. EXP-0178 then verified by hand,
outside the harness, that its "hang" candidate runs clean on G17P.

A false `hang` and a real inertness are INDISTINGUISHABLE in a summary, so a
sweep that hits one genuine hang can withdraw fields for an artefact. This
experiment deliberately has NO abort path (protocol 3c), so hangs are expected
and the defect would be maximally damaging here.

THE FIX, lifted from EXP-0178 `harness/saferunner.py` (reference implementation,
cited; not re-derived): exactly ONE reader thread per child, bound to that
child's lifetime, feeding a queue tagged with the process object it came from.
Lines from a dead child are discarded instead of being handed to the wrong
request. And a malformed response becomes a MEASUREMENT FAILURE with the raw
lines kept -- status `MALFORMED`, never `hang`, because a malformed response is
not an observation and must not be scored as one.

The shared tools in `tools/agxtest/` are NOT modified: sibling experiments run
against them concurrently and mutating them would be a courtesy violation of
FIELD-SWEEP-PROTOCOL section 7.

CLEAN-ROOM: pure process/protocol plumbing over our own OWN-SHADER runners.
"""
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path


def _import_persistrun(pinned_dir):
    """Import the PINNED persistrun.py by ABSOLUTE path, with a hard exit if it
    is absent. EXP-0182 owns `tools/agx-isa/isadb.py` and EXP-0183 owns
    `tools/agx-isa/db.json` RIGHT NOW; nothing here may resolve through a shared
    tool directory that another agent is editing."""
    p = Path(pinned_dir) / "persistrun.py"
    if not p.exists():
        sys.stderr.write("FATAL: pinned persistrun.py absent at %s\n" % p)
        raise SystemExit(2)
    sys.path.insert(0, str(Path(pinned_dir)))
    import persistrun  # noqa: E402
    if Path(persistrun.__file__).resolve() != p.resolve():
        sys.stderr.write("FATAL: persistrun resolved to %s, not the pinned %s\n"
                         % (persistrun.__file__, p))
        raise SystemExit(2)
    return persistrun.PersistRunner


class _Pumped:
    """One reader thread per child, tagged with its owner."""

    def _install_pump(self):
        self._q = queue.Queue()
        p = self.proc

        def pump():
            try:
                for ln in iter(p.stdout.readline, ""):
                    self._q.put((p, ln))
            except Exception:                                   # noqa: BLE001
                pass
            self._q.put((p, None))                              # EOF marker

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
            if owner is not self.proc:        # leftovers from a killed child
                continue
            return ln                         # None on EOF -> caller sees a wedge
        # unreachable

    def _read_line(self, timeout):
        return self._pumped_readline(timeout)

    # ------------------------------------------------------------------ #
    # Defensive re-implementation of PersistRunner.request(): the shared
    # parser does `_, idx, hexb = ln.split(None, 2)` on every "OUT " line and
    # RAISES on a short one, taking the whole run with it.
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


def make_classes(pinned_dir):
    Base = _import_persistrun(pinned_dir)

    class SafePersistRunner(_Pumped, Base):
        def _start(self):
            cmd = [self.exe, "--source", self.source, "--function", self.function]
            if not self.fast_math:
                cmd.append("--no-fast-math")
            self.proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True)
            self._install_pump()
            ready = self._read_line(timeout=60)
            if not ready or not ready.startswith("READY"):
                raise RuntimeError("agxrun_persist did not become READY: %r" % (ready,))
            self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    return SafePersistRunner, None

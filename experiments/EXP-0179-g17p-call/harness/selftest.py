#!/usr/bin/env python3
"""EXP-0179 device-free self-test for the DEF-0178-1 fix. No GPU, no Metal.

  python3 harness/selftest.py

G1  a normal response parses, under BOTH runners.
G2  a TRUNCATED `OUT` line CRASHES the shared runner (ValueError) and is recorded
    by the safe runner as `MALFORMED` with the raw lines kept -- never a `hang`.
G3  THE CASCADE. One genuine watchdog timeout, then two benign requests.
    Shared runner: the abandoned reader attaches to the replacement child, so the
    requests AFTER the hang do not come back clean.
    Safe runner: the hang is reported once and the following requests are clean.
G4  the geometry cross-check and the case matrix still build.

Exit code 0 iff every gate passes.
"""
from __future__ import print_function

import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))

FAKE = str(HERE / "fakechild.py")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tools_dir():
    for cand in (EXP / "tools" / "agxtest" / "persistrun.py",
                 EXP.parent.parent / "tools" / "agxtest" / "persistrun.py"):
        if cand.exists():
            return cand
    raise RuntimeError("persistrun.py not found")


persistrun = load("persistrun", tools_dir())
import saferunner  # noqa: E402

SafeRunner = saferunner.make_safe_runner(persistrun.PersistRunner)
fails = []


def mk(cls, mode):
    os.environ["EXP0179_FAKE_MODE"] = mode
    return cls(source="x.metal", function="k", fast_math=False,
               agxrun_persist=sys.executable + " " + FAKE)


class _Exec(object):
    """PersistRunner builds argv itself, so route through a tiny shim exe."""


SHIM = HERE / "_fakeshim.sh"
SHIM.write_text("#!/bin/bash\nexec %s %s \"$@\"\n" % (sys.executable, FAKE))
SHIM.chmod(0o755)


def mkr(cls, mode, state=None):
    os.environ["EXP0179_FAKE_MODE"] = mode
    os.environ["EXP0179_FAKE_STATE"] = state or ""
    return cls(source="x.metal", function="k", fast_math=False,
               agxrun_persist=str(SHIM))


def req(r, timeout=1.0):
    return r.request(archive="a.bin", grid=1, tg=1, ins={}, outs={0: 8},
                     timeout=timeout)


# ---- G1 ------------------------------------------------------------------
for name, cls in (("shared", persistrun.PersistRunner), ("safe", SafeRunner)):
    r = mkr(cls, "good")
    resp = req(r)
    ok = resp["status"] == "OK" and resp["outs"].get(0) == bytes.fromhex("deadbeef" * 2)
    print("G1 %-7s good response parses: %s" % (name, ok))
    if not ok:
        fails.append("G1/%s" % name)
    r.close()

# ---- G2 ------------------------------------------------------------------
r = mkr(persistrun.PersistRunner, "truncate")
try:
    req(r)
    shared_raised = False
except ValueError as e:
    shared_raised = True
    print("G2 shared  truncated OUT RAISES (as documented): %s" % e)
r.close()
if not shared_raised:
    print("G2 shared  did NOT raise -- the shared bug may have been patched")

r = mkr(SafeRunner, "truncate")
resp = req(r)
ok = bool(resp["status"] == "MALFORMED" and resp["error"] and resp["raw"])
print("G2 safe    truncated OUT -> MALFORMED, raw kept, NOT a hang: %s (status=%s)"
      % (ok, resp["status"]))
if not ok:
    fails.append("G2/safe")
r.close()

# ---- G3 THE CASCADE ------------------------------------------------------
state = HERE / "_fakestate.tmp"
if state.exists():
    state.unlink()
r = mkr(SafeRunner, "hang_first", state=str(state))
first = req(r, timeout=1.0)
after = [req(r, timeout=2.0) for _ in range(2)]
ok = (first["status"] == "HANG"
      and all(x["status"] == "OK" for x in after)
      and all(x["outs"].get(0) == bytes.fromhex("deadbeef" * 2) for x in after))
# The same sequence on the SHARED runner, for contrast. Recorded as an
# OBSERVATION, not a gate: the race is real but not deterministic, so a clean
# pass here would not mean the defect is absent.
state2 = HERE / "_fakestate2.tmp"
if state2.exists():
    state2.unlink()
rs = mkr(persistrun.PersistRunner, "hang_first", state=str(state2))
sfirst = req(rs, timeout=1.0)
safter = []
for _ in range(2):
    try:
        safter.append(req(rs, timeout=2.0)["status"])
    except Exception as e:
        safter.append("EXC:%s" % type(e).__name__)
print("G3 shared  (observation) hang then 2: %s then %s" % (sfirst["status"], safter))
print("           NOTE: the shared runner did NOT necessarily cascade here. The "
      "abandoned thread\n           resolves self.proc when rd() EXECUTES, which is "
      "usually immediately at thread\n           start, so it is normally already "
      "bound to the OLD child. The real failure needs\n           scheduling luck "
      "and/or several accumulated abandoned readers (EXP-0178's pilot saw\n"
      "           restarts=99). A clean result HERE is therefore NOT evidence the "
      "defect is absent --\n           G2 is the deterministic half, and the safe "
      "runner is immune BY CONSTRUCTION.")
try:
    rs.close()
except Exception:
    pass

print("G3 safe    hang then 2 clean requests: %s (%s then %s), discarded_lines=%s"
      % (ok, first["status"], [x["status"] for x in after],
         after[-1].get("discarded_lines")))
if not ok:
    fails.append("G3/safe")
r.close()

# ---- G4 ------------------------------------------------------------------
try:
    import isa_helpers as H
    import json
    import cases as CM
    n = H.assert_geometry()
    cs = CM.build_cases(json.loads((EXP / "work" / "addendum.json").read_text()))
    bad = 0
    for c in cs:
        try:
            H.synth_call_program(H.PLANS[c["plan"]], 6142, **c["build"])
        except Exception:
            bad += 1
    ok = (n > 0 and bad == 0)
    print("G4 geometry checks=%d, %d cases build, %d failures: %s" % (n, len(cs), bad, ok))
    if not ok:
        fails.append("G4")
except Exception as e:
    print("G4 FAILED: %r" % e)
    fails.append("G4")

SHIM.unlink(missing_ok=True)
(HERE / "_fakestate.tmp").unlink(missing_ok=True)
(HERE / "_fakestate2.tmp").unlink(missing_ok=True)
print()
print("SELFTEST %s%s" % ("PASS" if not fails else "FAIL ", ",".join(fails)))
sys.exit(1 if fails else 0)

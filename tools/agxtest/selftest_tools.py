#!/usr/bin/env python3
"""OFFLINE gates for the shared agxtest checks. NO GPU, NO Metal, NO device, NO SSH.

    python3 tools/agxtest/selftest_tools.py            # exit 0 iff every gate passes

A check that has been copied without its gate is a check nobody will trust, so every
module upstreamed by EXP-0185 keeps the gate that caught its defect:

  T0  the modules import and `SafePersistRunner` binds over the shared `PersistRunner`.
  T1  a normal response parses under BOTH the shared runner and the safe runner
      (the fix does not change good-path behaviour).
  T2  DEF-0178-1, the deterministic half: a TRUNCATED `OUT` line RAISES `ValueError` in
      the shared runner and comes back from the safe runner as `MALFORMED` with the raw
      lines kept -- never a crash and never a `hang`.
  T3  DEF-0178-1, the cascade: one genuine watchdog timeout, then two benign requests.
      The safe runner reports the hang ONCE and the requests after it are clean.
      The shared runner's behaviour here is recorded as an OBSERVATION, never a gate: the
      race needs scheduling luck, and a clean stub run is not evidence the defect is
      absent (SUBAGENT_BRIEF). The structural fix is what is relied on.
  T4  the owner tag itself, deterministically: a line from a KILLED child is discarded and
      counted, and the current child's line is the one returned.
  T5  DEF-0153-2 stays fixed: an exited child is reported as a wedge, not as an empty line
      that falls through every branch and spins.
  T6  closure_scan finds the planted `nb`-rebind on the bad fixture, is clean on the fixed
      one, and its allow-list is load-bearing (removing it re-flags the if/else name).
  T7  verify_remote reports OK / MISSING / STALE correctly against a local fake "remote"
      tree, exits 3 for the last two, and REFUSES (exit 2) a check that matched no blobs.

Scratch lives in `tools/agxtest/work/` -- inside the repository, per SUBAGENT_BRIEF -- and
is removed on exit.

Clean-room: our own harness code and fixtures only. No Apple binary is involved.
"""
import atexit
import contextlib
import hashlib
import io
import json
import os
import queue
import shutil
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import closure_scan                                            # noqa: E402
import saferunner                                              # noqa: E402
import verify_remote                                           # noqa: E402

WORK = os.path.join(HERE, "work")
FAKE = os.path.join(HERE, "fakepersist.py")
TESTDATA = os.path.join(HERE, "testdata")

fails = []
notes = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def mkrunner(cls, mode, state=None, trunc_from=None):
    os.environ["AGXTEST_FAKE_MODE"] = mode
    os.environ["AGXTEST_FAKE_STATE"] = state or ""
    os.environ["AGXTEST_FAKE_TRUNCATE_FROM"] = str(trunc_from or 1)
    return cls(source="x.metal", function="k", fast_math=False, agxrun_persist=FAKE)


def req(r, timeout=1.5, nb=8):
    return r.request(archive="a.bin", grid=1, tg=1, ins={}, outs={0: nb},
                     timeout=timeout)


def shutdown(r):
    try:
        r._kill()
    except Exception:                                          # noqa: BLE001
        pass


PAYLOAD = bytes.fromhex("a5" * 8)

os.makedirs(WORK, exist_ok=True)
atexit.register(lambda: shutil.rmtree(WORK, ignore_errors=True))   # even on a crash
os.chmod(FAKE, os.stat(FAKE).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

# ---------------------------------------------------------------------- T0 --
Shared = saferunner.load_persist_runner()
Safe = saferunner.make_safe_runner(Shared)
check("T0 modules import, SafePersistRunner binds", Safe is not None
      and saferunner.SafePersistRunner is not None,
      "%s over %s" % (Safe.__name__, Shared.__module__))

# ---------------------------------------------------------------------- T1 --
t1 = []
for name, cls in (("shared", Shared), ("safe", Safe)):
    r = mkrunner(cls, "good")
    try:
        resp = req(r)
        if resp["status"] != "OK" or resp["outs"].get(0) != PAYLOAD:
            t1.append("%s: %r" % (name, {k: resp[k] for k in ("status", "outs")}))
    except Exception as e:                                     # noqa: BLE001
        t1.append("%s raised %s" % (name, e))
    shutdown(r)
check("T1 good response parses under both runners", not t1, "; ".join(t1))

# ---------------------------------------------------------------------- T2 --
t2 = []
r = mkrunner(Shared, "truncate")
shared_raised = None
try:
    req(r)
except ValueError as e:
    shared_raised = str(e)
except Exception as e:                                         # noqa: BLE001
    shared_raised = "%s: %s" % (type(e).__name__, e)
shutdown(r)
if shared_raised is None:
    notes.append("T2: the SHARED runner did NOT raise on a truncated OUT -- "
                 "the DEF-0178-1 patch may already be applied to persistrun.py")

r = mkrunner(Safe, "truncate")
resp = req(r)
if resp["status"] != "MALFORMED":
    t2.append("safe: status %r, want MALFORMED" % resp["status"])
if resp["status"] == "HANG":
    t2.append("safe: a malformed response was scored as a HANG")
if not resp.get("raw"):
    t2.append("safe: MALFORMED without the raw lines kept")
if not resp.get("error"):
    t2.append("safe: MALFORMED without an error string")
shutdown(r)
check("T2 truncated OUT -> MALFORMED (safe) / raises (shared)", not t2,
      "shared raised: %s" % (shared_raised or "NO -- see note"))

# ---------------------------------------------------------------------- T3 --
t3 = []
state = os.path.join(WORK, "hang_state.tmp")
if os.path.exists(state):
    os.unlink(state)
r = mkrunner(Safe, "hang_first", state=state)
first = req(r, timeout=1.0)
after = [req(r, timeout=3.0) for _ in range(2)]
if first["status"] != "HANG":
    t3.append("first request: %r, want HANG" % first["status"])
if [x["status"] for x in after] != ["OK", "OK"]:
    t3.append("after the hang: %r, want ['OK','OK'] (this is the cascade)"
              % [x["status"] for x in after])
if any(x["outs"].get(0) != PAYLOAD for x in after):
    t3.append("after the hang: payload corrupted")
shutdown(r)

state2 = os.path.join(WORK, "hang_state2.tmp")
if os.path.exists(state2):
    os.unlink(state2)
rs = mkrunner(Shared, "hang_first", state=state2)
try:
    sfirst = req(rs, timeout=1.0)["status"]
    safter = []
    for _ in range(2):
        try:
            safter.append(req(rs, timeout=3.0)["status"])
        except Exception as e:                                 # noqa: BLE001
            safter.append("EXC:%s" % type(e).__name__)
except Exception as e:                                         # noqa: BLE001
    sfirst, safter = "EXC:%s" % type(e).__name__, []
shutdown(rs)
notes.append("T3 shared runner (OBSERVATION, not a gate): hang then %s %s. The abandoned "
             "thread usually binds to the OLD child at rd() entry, so the race needs "
             "scheduling luck; a clean stub run is NOT evidence the defect is absent."
             % (sfirst, safter))
check("T3 one timeout does not manufacture the requests after it", not t3,
      "; ".join(t3))

# ---------------------------------------------------------------------- T4 --
t4 = []


class _Pumped(saferunner.PumpedReader):
    pass


p = _Pumped()
cur, old = object(), object()
p.proc = cur
p._q = queue.Queue()
p.discarded_lines = 0
p._q.put((old, "STALE FROM THE DEAD CHILD\n"))          # must never reach the caller
p._q.put((cur, "STATUS OK\n"))
got = p._pumped_readline(2.0)
if got != "STATUS OK\n":
    t4.append("returned %r, want the CURRENT child's line" % got)
if p.discarded_lines != 1:
    t4.append("discarded_lines=%d, want 1" % p.discarded_lines)
if p._pumped_readline(0.2) is not None:
    t4.append("an empty queue did not time out to None")
check("T4 a killed child's leftovers are discarded, not handed over", not t4,
      "; ".join(t4))

# ---------------------------------------------------------------------- T5 --
t5 = []
r = mkrunner(Safe, "eof_first")
resp = req(r, timeout=2.0)
if resp["status"] != "HANG":
    t5.append("exited child gave %r, want HANG (DEF-0153-2: EOF is a wedge)" % resp["status"])
shutdown(r)
check("T5 an exited child is a wedge, not an empty-line spin", not t5, "; ".join(t5))

# ---------------------------------------------------------------------- T6 --
t6 = []
ALLOW = {"mnem": "assigned in two mutually exclusive if/else branches"}
bad = closure_scan.scan(os.path.join(TESTDATA, "closure_shadow_bad.py"), "main",
                        allow=ALLOW)
if "nb" not in bad:
    t6.append("the planted read-back-size rebind was NOT flagged: %r" % bad)
good = closure_scan.scan(os.path.join(TESTDATA, "closure_shadow_good.py"), "main",
                         allow=ALLOW)
if good:
    t6.append("the corrected fixture was flagged: %r" % good)
unallowed = closure_scan.scan(os.path.join(TESTDATA, "closure_shadow_good.py"), "main")
if "mnem" not in unallowed:
    t6.append("the allow-list is not load-bearing: %r without it" % unallowed)
check("T6 closure_scan flags the rebind, clears the fix, allow-list works", not t6,
      "; ".join(t6))

# ---------------------------------------------------------------------- T7 --
t7 = []
FR = os.path.join(WORK, "fakeremote")
shutil.rmtree(FR, ignore_errors=True)
os.makedirs(os.path.join(FR, "harness"))
os.makedirs(os.path.join(FR, "kernels"))
blobs = {"harness/run.py": b"# authored run.py\n",
         "harness/sync.sh": b"#!/bin/bash\necho push\n",
         "kernels/k.metal": b"kernel void k() {}\n"}
for k, v in blobs.items():
    with open(os.path.join(FR, k), "wb") as fh:
        fh.write(v)
contract = {"authored_sha256": {k: hashlib.sha256(v).hexdigest()
                                for k, v in blobs.items()},
            "pinned_inputs_sha256": {}}
contract["authored_sha256"]["README.md"] = "0" * 64      # repo-side only: never pushed
CPATH = os.path.join(WORK, "CAPTURE_CONTRACT.json")
with open(CPATH, "w") as fh:
    json.dump(contract, fh, indent=1)


def run_verify(extra=()):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = verify_remote.main(["--contract", CPATH, "--remote", ".",
                                 "--local-root", FR] + list(extra))
    return rc, buf.getvalue()


rc, out = run_verify()
if rc != 0:
    t7.append("clean tree returned %d (%s)" % (rc, out.strip().splitlines()[-1]))
if "3/3 blobs match" not in out:
    t7.append("clean tree did not report 3/3: %r" % out.strip()[-120:])

os.unlink(os.path.join(FR, "kernels/k.metal"))
rc, out = run_verify()
if rc != 3 or "MISSING" not in out:
    t7.append("a missing blob returned %d without MISSING" % rc)
with open(os.path.join(FR, "kernels/k.metal"), "wb") as fh:
    fh.write(blobs["kernels/k.metal"])

with open(os.path.join(FR, "harness/run.py"), "wb") as fh:
    fh.write(b"# AMENDED after the push\n")
rc, out = run_verify()
if rc != 3 or "STALE" not in out:
    t7.append("a stale blob returned %d without STALE" % rc)

rc, out = run_verify(["--prefix", "nothing_matches/"])
if rc != 2 or "matched NO pushed blobs" not in out:
    t7.append("an empty check returned %d -- it must REFUSE, not pass" % rc)
check("T7 verify_remote catches MISSING and STALE and refuses an empty check", not t7,
      "; ".join(t7))

# ---------------------------------------------------------------------------
shutil.rmtree(WORK, ignore_errors=True)
print()
for n in notes:
    print("NOTE %s" % n)
print()
print("SELFTEST %s (%d failure(s))" % ("PASS" if not fails else "FAIL", len(fails)))
sys.exit(0 if not fails else 1)

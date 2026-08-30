#!/usr/bin/env python3
"""Gate the PROPOSED patch to `tools/agxtest/persistrun.py` -- offline, no device.

    python3 analysis/gate_patched_persistrun.py        # exit 0 iff every gate passes

Loads BOTH the committed shared runner and the patched copy produced by
`analysis/make_persistrun_patch.py`, drives them against `tools/agxtest/fakepersist.py`
(no Metal, no GPU), and proves:

  P1  the good path is UNCHANGED: every pre-existing response key has the same value
      under both runners.
  P2  DEF-0178-1: a truncated `OUT` line RAISES `ValueError` in the shared runner and
      comes back as `MALFORMED` (raw kept, not a `hang`) in the patched one.
  P3  the cascade: after one genuine watchdog timeout the patched runner reports the hang
      once and the following requests are clean, and the HANG `error` string is
      BYTE-IDENTICAL to the shared runner's, so a caller matching on it is unaffected.
  P4  DEF-0153-2 stays fixed: an exited child is a wedge, not an empty-line spin.
  P5  API compatibility: the patched response is a strict SUPERSET of the old keys, the
      added keys are exactly the four documented ones, and `MALFORMED` is the only new
      status value.
  P6  `saferunner.make_safe_runner()` still builds and works over the PATCHED class, so
      experiments that pin the wrapper keep working after the patch lands.
  P7  the broken-pipe path is unchanged (same status and same error string).

Clean-room: our own harness plumbing only; no Apple binary is inspected.
"""
import importlib.util
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
AGXTEST = os.path.join(REPO, "tools", "agxtest")
FAKE = os.path.join(AGXTEST, "fakepersist.py")
PATCHED = os.path.join(EXP, "work", "persistrun_patched.py")
WORK = os.path.join(EXP, "work")

sys.path.insert(0, AGXTEST)
import saferunner                                              # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


os.chmod(FAKE, os.stat(FAKE).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
Shared = load("persistrun_shared", os.path.join(AGXTEST, "persistrun.py")).PersistRunner
Patched = load("persistrun_patched", PATCHED).PersistRunner

OLD_KEYS = {"status", "outs", "gputime_ns", "error", "restarted"}
NEW_KEYS = {"raw", "discarded_lines", "restarts", "malformed_total"}
PAYLOAD = bytes.fromhex("a5" * 8)


def mk(cls, mode, state=None, trunc=1):
    os.environ["AGXTEST_FAKE_MODE"] = mode
    os.environ["AGXTEST_FAKE_STATE"] = state or ""
    os.environ["AGXTEST_FAKE_TRUNCATE_FROM"] = str(trunc)
    return cls(source="x.metal", function="k", fast_math=False, agxrun_persist=FAKE)


def req(r, timeout=1.5):
    return r.request(archive="a.bin", grid=1, tg=1, ins={}, outs={0: 8}, timeout=timeout)


def bye(r):
    try:
        r._kill()
    except Exception:                                          # noqa: BLE001
        pass


# ------------------------------------------------------------------- P1 -----
a, b = mk(Shared, "good"), mk(Patched, "good")
ra, rb = req(a), req(b)
p1 = [k for k in OLD_KEYS if ra[k] != rb[k]]
check("P1 good path unchanged on every pre-existing key", not p1,
      "differs: %r" % p1 if p1 else "status=%s outs[0]=%s" % (rb["status"],
                                                              rb["outs"][0].hex()))

# ------------------------------------------------------------------- P5 -----
p5 = []
if not OLD_KEYS <= set(rb):
    p5.append("patched response DROPPED keys: %r" % (OLD_KEYS - set(rb)))
if set(rb) - set(ra) != NEW_KEYS:
    p5.append("added keys are %r, want %r" % (set(rb) - set(ra), NEW_KEYS))
if ra["status"] != "OK" or rb["status"] != "OK":
    p5.append("good-mode status changed: %s -> %s" % (ra["status"], rb["status"]))
check("P5 response is a strict superset; the four new keys only", not p5, "; ".join(p5))
bye(a)
bye(b)

# ------------------------------------------------------------------- P2 -----
p2 = []
r = mk(Shared, "truncate")
raised = None
try:
    req(r)
except ValueError as e:
    raised = str(e)
except Exception as e:                                         # noqa: BLE001
    raised = "%s: %s" % (type(e).__name__, e)
bye(r)
if raised is None:
    p2.append("the SHARED runner did not raise -- is persistrun.py already patched?")

r = mk(Patched, "truncate")
resp = req(r)
if resp["status"] != "MALFORMED":
    p2.append("patched status %r, want MALFORMED" % resp["status"])
if resp["status"] == "HANG":
    p2.append("patched scored a malformed response as a HANG")
if not resp["raw"] or not resp["error"]:
    p2.append("patched MALFORMED without raw lines / error string")
if resp["malformed_total"] != 1:
    p2.append("malformed_total=%r" % resp["malformed_total"])
bye(r)
check("P2 truncated OUT: shared RAISES, patched -> MALFORMED", not p2,
      "shared raised: %s" % raised)

# ------------------------------------------------------------------- P3 -----
p3 = []
state = os.path.join(WORK, "gate_hang_state.tmp")
if os.path.exists(state):
    os.unlink(state)
r = mk(Patched, "hang_first", state=state)
first = req(r, timeout=1.0)
after = [req(r, timeout=3.0) for _ in range(2)]
if first["status"] != "HANG":
    p3.append("first: %r, want HANG" % first["status"])
if first["error"] != "no response within 1.0s (GPU wedged)":
    p3.append("HANG error string changed: %r" % first["error"])
if [x["status"] for x in after] != ["OK", "OK"]:
    p3.append("after the hang: %r -- the cascade is NOT fixed"
              % [x["status"] for x in after])
if any(x["outs"].get(0) != PAYLOAD for x in after):
    p3.append("payload corrupted after the hang")
if first["restarts"] != 1:
    p3.append("restarts=%r after one wedge" % first["restarts"])
bye(r)
check("P3 one timeout does not manufacture later results; HANG text unchanged", not p3,
      "; ".join(p3))

# ------------------------------------------------------------------- P4 -----
r = mk(Patched, "eof_first")
resp = req(r, timeout=2.0)
check("P4 an exited child is a wedge (DEF-0153-2)", resp["status"] == "HANG",
      "status=%s" % resp["status"])
bye(r)

# ------------------------------------------------------------------- P6 -----
p6 = []
try:
    Safe = saferunner.make_safe_runner(Patched)
    r = mk(Safe, "truncate")
    resp = req(r)
    if resp["status"] != "MALFORMED":
        p6.append("wrapper over the patched class gave %r" % resp["status"])
    bye(r)
    r = mk(Safe, "good")
    if req(r)["outs"].get(0) != PAYLOAD:
        p6.append("wrapper good path broken over the patched class")
    bye(r)
except Exception as e:                                         # noqa: BLE001
    p6.append("wrapper failed over the patched class: %s: %s" % (type(e).__name__, e))
check("P6 saferunner still works over the patched class", not p6, "; ".join(p6))

# ------------------------------------------------------------------- P7 -----
p7 = []
got = {}
for name, cls in (("shared", Shared), ("patched", Patched)):
    r = mk(cls, "good")
    r.proc.stdin.close()
    resp = r.request(archive="a.bin", grid=1, tg=1, ins={}, outs={0: 8}, timeout=1.0)
    got[name] = (resp["status"], resp["error"], resp["restarted"])
    bye(r)
if got["shared"] != got["patched"]:
    p7.append("%r vs %r" % (got["shared"], got["patched"]))
check("P7 broken-pipe path unchanged", not p7, "%s" % (got["patched"],))

for f in (state,):
    if os.path.exists(f):
        os.unlink(f)

print()
print("PATCH GATE %s (%d failure(s))" % ("PASS" if not fails else "FAIL", len(fails)))
sys.exit(0 if not fails else 1)

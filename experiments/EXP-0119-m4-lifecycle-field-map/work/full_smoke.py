#!/usr/bin/env python3
"""INFORMAL, NON-GATED pilot-phase smoke of the whole matrix. Not part of the
gated raw/ capture -- run.py has its own single-case NON-RECORDED smoke gate
before raw/ is created (per SUBAGENT_BRIEF.md/CODEX standing gates). This
script exists purely to catch oracle bugs BEFORE freezing PRE_REGISTRATION.md,
exactly like every predecessor experiment's own informal pilot phase."""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import casematrix as CM

cs = CM.build_cases()
print("total cases:", len(cs))
bad = []
for c in cs:
    if c["name"].endswith("_HANGPROBE"):
        print("SKIP (hang-probe, tested separately with extra care):", c["name"])
        continue
    r = subprocess.run([sys.executable, "-B", str(HERE / "harness" / "case_exec.py"),
                         "--case-index", str(c["i"]), "--run-dir", str(HERE / "work" / "full_smoke_run"),
                         "--bin-dir", str(HERE / "work" / "pilot_bin"), "--repo", str(HERE.parents[1])],
                        capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        print("PARSE FAIL", c["name"], r.stdout[-500:], r.stderr[-1000:])
        bad.append(c["name"])
        continue
    flag = "OK" if d["status"] == "OK" else "STATUS=" + str(d["status"])
    matchflag = "match" if d["match"] else "MISMATCH"
    print("%-55s %-10s %-10s observed=%s" % (c["name"], flag, matchflag, d["observed"]))
    if d["status"] != "OK":
        bad.append(c["name"])
print()
print("problem cases:", bad)

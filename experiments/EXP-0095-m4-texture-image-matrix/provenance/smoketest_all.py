#!/usr/bin/env python3
import json, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
cases = json.loads((HERE / "cases_generated.json").read_text())
probe = ROOT / "analysis/pre_freeze/explore/probe_test"
fails = []
for c in cases:
    kf = ROOT / c["kernel_file"]
    argv = [str(probe), "--family", c["family"], "--case", c["case"], "--source", str(kf), "--args", json.dumps(c["args"])]
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=c.get("timeout_seconds", 60))
    except subprocess.TimeoutExpired:
        fails.append((c["case"], "TIMEOUT", ""))
        continue
    if c["expect_status"] == "abort":
        if r.returncode >= 0:
            fails.append((c["case"], "expected abort (negative signal exit), got " + str(r.returncode), r.stdout[-300:]))
        continue
    if r.returncode != 0:
        fails.append((c["case"], "exit=" + str(r.returncode), (r.stdout + r.stderr)[-500:]))
        continue
    try:
        p = json.loads(r.stdout)
    except json.JSONDecodeError:
        fails.append((c["case"], "bad json", r.stdout[-300:]))
        continue
    if p.get("status") != "ok":
        fails.append((c["case"], "status=" + str(p.get("status")), json.dumps(p)[-500:]))
print(f"{len(cases)-len(fails)}/{len(cases)} ok")
for f in fails:
    print("FAIL", f[0], "|", f[1])
    if f[2]:
        print("   ", f[2][:300].replace("\n"," "))

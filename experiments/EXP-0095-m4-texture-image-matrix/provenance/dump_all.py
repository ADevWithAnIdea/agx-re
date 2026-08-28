#!/usr/bin/env python3
import json, subprocess, pathlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
cases = json.loads((HERE / "cases_generated.json").read_text())
probe = ROOT / "analysis/pre_freeze/explore/probe_test"
results = {}
for c in cases:
    kf = ROOT / c["kernel_file"]
    argv = [str(probe), "--family", c["family"], "--case", c["case"], "--source", str(kf), "--args", json.dumps(c["args"])]
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=c.get("timeout_seconds", 60))
    except subprocess.TimeoutExpired:
        results[c["case"]] = {"exit": "TIMEOUT"}
        continue
    if c["expect_status"] == "abort":
        results[c["case"]] = {"exit": r.returncode, "abort_stderr": r.stderr[-200:]}
        continue
    try:
        p = json.loads(r.stdout)
    except Exception:
        results[c["case"]] = {"exit": r.returncode, "raw": (r.stdout+r.stderr)[-300:]}
        continue
    results[c["case"]] = {"status": p.get("status"), "out_words": p.get("out_words"), "n_outputs": c["n_outputs"], "expected": c["expected_out_words"]}
(HERE / "dump_results.json").write_text(json.dumps(results, indent=2))
mismatches = 0
for c in cases:
    r = results[c["case"]]
    if c["expect_status"] == "abort":
        continue
    if r.get("status") != "ok":
        print("NONOK", c["case"], r.get("status")); continue
    ow = r["out_words"]
    exp = c["expected_out_words"]
    n = c["n_outputs"]
    for i in range(n):
        if exp[i] is not None and ow[i] != exp[i]:
            mismatches += 1
            print(f"MISMATCH {c['case']} word{i}: expected {exp[i]:#x} got {ow[i]:#x} (rule {c['rule']})")
    for i in range(n, 16):
        if ow[i] != 0xEEEEEEEE:
            print(f"UNEXPECTED-WRITE {c['case']} word{i}: expected sentinel, got {ow[i]:#x}")
print("mismatches:", mismatches)

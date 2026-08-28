import json, subprocess, sys
idxs = list(range(144,161))
results = []
for i in idxs:
    r = subprocess.run([sys.executable, "-B", "harness/case_exec.py",
                         "--case-index", str(i), "--run-dir", "work/dryrun4",
                         "--bin-dir", "work/baseline_bin", "--repo", "/Users/user/asahi_re/public/agx-re"],
                        capture_output=True, text=True, timeout=45)
    try:
        d = json.loads(r.stdout)
        results.append((i, d["name"], d["group"], d["status"], d["match"], d["expect_match"], d.get("observed"), d.get("oracle")))
    except Exception as e:
        results.append((i, "PARSE_FAIL", "?", "?", None, None, None, None))
        print("PARSE FAIL", i, r.stdout[:500], r.stderr[:1000])
for row in results:
    print(row)
bad = [row for row in results if row[4] != row[5]]
print("MISMATCHED EXPECTATION count:", len(bad))

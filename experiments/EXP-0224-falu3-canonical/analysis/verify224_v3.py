#!/usr/bin/env python3
"""Verify EXP-0224's two formal V3 low-bank FMA captures."""

import collections
import json
from pathlib import Path

import verify224 as V


EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parent.parent


def main():
    contract = json.loads((EXP / "CAPTURE_CONTRACT_V3.json").read_text())
    paths = [EXP / "raw" / run["id"] for run in contract["runs"]]
    if any(not path.is_dir() for path in paths):
        raise SystemExit("missing V3 formal run directory")
    decoder = V.load_decoder(REPO / "tools" / "agx-isa" / "isadb.py")
    runs = [(path.name, V.load_run(path)) for path in paths]
    failures = []
    summary = {"runs": {}}
    expected_dst = {"v3_dst_r%02d" % r for r in range(16)}
    expected_src = {"v3_src%s_r%02d" % (role, r) for role in "abc" for r in range(16)}
    expected_dag = {"v3_dag_%03d" % i for i in range(100)}
    expected_load = {"v3_load_%s_gap%d" % (role, gap)
                     for role in "abc" for gap in (0, 1, 4)}

    for run_name, by_name in runs:
        rows = [row for row in by_name.values() if row["arm"] == "V3"]
        positives = [row for row in rows if row["expect_match"]]
        refuters = [row for row in rows if not row["expect_match"]]
        walk_bad = 0
        for row in rows:
            if V.reconstruct_body(row, decoder):
                walk_bad += 1
            if (not row["dispatched_bytes_verified"] or row["gate_a"]["n_bad"]
                    or row["gate_a"]["n_alias"]):
                failures.append("%s/%s Gate A" % (run_name, row["name"]))
            if row["ledger"].get("COPIED") or row["ledger"].get("CARRIER"):
                failures.append("%s/%s donor field" % (run_name, row["name"]))
            if row["status"] != "OK" or not row["sentinel_ok"] or row["restarts"]:
                failures.append("%s/%s invalid hardware state" % (run_name, row["name"]))
            if not row["bucket_ok"]:
                failures.append("%s/%s frozen bucket" % (run_name, row["name"]))
        names = set(by_name)
        for label, expected in (("dst", expected_dst), ("src", expected_src),
                                ("dag", expected_dag), ("load", expected_load)):
            if names & expected != expected:
                failures.append("%s wrong %s coverage" % (run_name, label))
        if len(rows) != 200 or len(positives) != 198 or len(refuters) != 2:
            failures.append("%s wrong cardinality" % run_name)
        if any(row["observed_bucket"] != "exact" for row in positives):
            failures.append("%s non-exact positive" % run_name)
        if any(row["observed_bucket"] == "exact" for row in refuters):
            failures.append("%s refuter did not fire" % run_name)
        if walk_bad:
            failures.append("%s %d whole-walk errors" % (run_name, walk_bad))
        summary["runs"][run_name] = {
            "v3": len(rows),
            "positive_exact": sum(r["observed_bucket"] == "exact" for r in positives),
            "refuters_fired": sum(r["observed_bucket"] != "exact" for r in refuters),
            "outcomes": dict(collections.Counter(r["outcome"] for r in rows)),
            "whole_walk_errors": walk_bad,
        }

    first, second = runs[0][1], runs[1][1]
    if set(first) != set(second):
        failures.append("case-name sets differ")
    cross = []
    for name in sorted(set(first) & set(second)):
        a, b = first[name], second[name]
        if any(a.get(k) != b.get(k) for k in
               ("prog_sha256", "out_sha256", "outcome", "observed_bucket", "under_test")):
            cross.append(name)
    if cross:
        failures.append("cross-run mismatch in %d cases" % len(cross))
    summary["cross_run_mismatches"] = cross[:20]
    summary["failures"] = failures[:60]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

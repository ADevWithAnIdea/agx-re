#!/usr/bin/env python3
"""Verify EXP-0225's two formal generated IMAD captures."""

import collections
import importlib.util
import json
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parent.parent


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_run(path):
    rows = [json.loads(line) for line in (path / "sweep.jsonl").read_text().splitlines()]
    return {row["name"]: row for row in rows}


def main():
    contract = json.loads((EXP / "CAPTURE_CONTRACT.json").read_text())
    paths = [EXP / "raw" / run["id"] for run in contract["runs"]]
    if any(not path.is_dir() for path in paths):
        raise SystemExit("missing formal run directory")

    helper = load_module(
        REPO / "experiments" / "EXP-0224-falu3-canonical" / "analysis" / "verify224.py",
        "exp0224_verify")
    decoder = helper.load_decoder(REPO / "tools" / "agx-isa" / "isadb.py")
    runs = [(path.name, load_run(path)) for path in paths]
    failures = []
    summary = {"runs": {}}
    expected_counts = {
        "p2_srcx_": 24, "p2_srcy_": 24, "p2_dst_": 24,
        "p2_load_": 6, "p2_imm_": 256, "p2_alias_": 3,
        "p2_numeric_": 3, "p2_dag_": 100, "p2_ctl_": 2,
    }

    for run_name, by_name in runs:
        run_path = EXP / "raw" / run_name
        rows = [row for row in by_name.values() if row["arm"] == "P2"]
        positives = [row for row in rows if row["expect_match"]]
        refuters = [row for row in rows if not row["expect_match"]]
        walk_bad = 0
        for row in rows:
            if helper.reconstruct_body(row, decoder):
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
        if len(rows) != 442 or len(positives) != 440 or len(refuters) != 2:
            failures.append("%s wrong cardinality" % run_name)
        if any(row["observed_bucket"] != "exact" for row in positives):
            failures.append("%s non-exact positive" % run_name)
        if any(row["observed_bucket"] == "exact" for row in refuters):
            failures.append("%s refuter did not fire" % run_name)
        for prefix, expected in expected_counts.items():
            got = sum(name.startswith(prefix) for name in by_name)
            if got != expected:
                failures.append("%s %s coverage %d != %d" %
                                (run_name, prefix, got, expected))
        if walk_bad:
            failures.append("%s %d whole-walk errors" % (run_name, walk_bad))
        quiet = [json.loads(line) for line in
                 (run_path / "procs.jsonl").read_text().splitlines()]
        if not quiet or any(sample["n_foreign"] or sample["n_foreign_runner"]
                            or sample["n_compiler_svc"] for sample in quiet):
            failures.append("%s contaminated quiet sample" % run_name)
        pre = json.loads((run_path / "gpu_pre.json").read_text())
        post = json.loads((run_path / "gpu_post.json").read_text())
        recoveries = {sample["gpu"]["recovery_count"] for sample in quiet}
        recoveries.update((pre["recovery_count"], post["recovery_count"]))
        if len(recoveries) != 1:
            failures.append("%s recovery count changed" % run_name)
        summary["runs"][run_name] = {
            "p2": len(rows),
            "positive_exact": sum(r["observed_bucket"] == "exact" for r in positives),
            "refuters_fired": sum(r["observed_bucket"] != "exact" for r in refuters),
            "outcomes": dict(collections.Counter(r["outcome"] for r in rows)),
            "whole_walk_errors": walk_bad,
            "quiet_samples": len(quiet),
            "recovery_count": sorted(recoveries),
        }

    first, second = runs[0][1], runs[1][1]
    if set(first) != set(second):
        failures.append("case-name sets differ")
    cross = []
    for name in sorted(set(first) & set(second)):
        a, b = first[name], second[name]
        if any(a.get(key) != b.get(key) for key in
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

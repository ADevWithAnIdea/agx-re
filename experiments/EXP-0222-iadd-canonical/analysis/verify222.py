#!/usr/bin/env python3
"""Verify EXP-0222's frozen G17P iadd2 capture without trusting RESULTS.md."""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((EXP / "CAPTURE_CONTRACT.json").read_text())
EXPECTED_ARMS = {"S0": 8, "C0": 2, "V1": 16, "P1": 11, "CROSS": 28, "DAG": 100}
EXACT_ARMS = {"V1", "P1", "CROSS", "DAG"}


def fail(message):
    print("FAIL:", message)
    raise SystemExit(1)


def load_json(path):
    return json.loads(path.read_text())


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    harness = EXP / "harness" / "run222_pilot.py"
    got_hash = hashlib.sha256(harness.read_bytes()).hexdigest()
    if got_hash != CONTRACT["harness_sha256"]:
        fail(f"harness hash {got_hash} != frozen {CONTRACT['harness_sha256']}")

    by_run = {}
    for run_spec in CONTRACT["runs"]:
        run = run_spec["id"]
        rd = EXP / "raw" / run
        rows = load_jsonl(rd / "sweep.jsonl")
        counts = Counter(row["arm"] for row in rows)
        if dict(counts) != EXPECTED_ARMS:
            fail(f"{run}: arm counts {dict(counts)} != {EXPECTED_ARMS}")
        if len({row["name"] for row in rows}) != len(rows):
            fail(f"{run}: duplicate case name")

        semantic = [row for row in rows if row["arm"] != "S0"]
        exact = [row for row in semantic
                 if row["arm"] in EXACT_ARMS or row["name"] == "c0_generated_baseline"]
        refute = [row for row in semantic if row["name"] == "c0_wrong_first_selector"]
        if len(exact) != 156 or len(refute) != 1:
            fail(f"{run}: exact/refute counts are {len(exact)}/{len(refute)}")
        if any(row["status"] != "OK" or not row["match"] or row["outcome"] != "ok"
               for row in exact):
            fail(f"{run}: an exact case failed")
        if refute[0]["match"] or refute[0]["outcome"] != "wrong_value" \
                or not refute[0]["bucket_ok"]:
            fail(f"{run}: wrong-selector refuter did not fire")

        for row in rows:
            if not row["dispatched_bytes_verified"]:
                fail(f"{run}/{row['name']}: dispatched bytes not verified")
            if row["gate_a"]["n_bad"] or row["gate_a"]["n_alias"]:
                fail(f"{run}/{row['name']}: Gate A failed")
            if row["ledger"].get("COPIED", 0) or row["ledger"].get("CARRIER", 0):
                fail(f"{run}/{row['name']}: donor field present")
            if row["donor_fields"]:
                fail(f"{run}/{row['name']}: nonempty donor list")
            if row.get("foreign_retries", 0):
                fail(f"{run}/{row['name']}: foreign retry")
            if row["outcome"] in {"hang", "fault", "measurement_failure", "victim"}:
                fail(f"{run}/{row['name']}: {row['outcome']}")
            if not row.get("sentinel_ok", True):
                fail(f"{run}/{row['name']}: sentinel failure")

        procs = load_jsonl(rd / "procs.jsonl")
        if not procs:
            fail(f"{run}: no quiet samples")
        if any(p.get("n_foreign", 0) or p.get("n_foreign_runner", 0) for p in procs):
            fail(f"{run}: foreign process in quiet samples")
        pre, post = load_json(rd / "gpu_pre.json"), load_json(rd / "gpu_post.json")
        if pre.get("recovery_count") != post.get("recovery_count"):
            fail(f"{run}: recovery count changed")
        manifest = load_json(rd / "05_run_manifest.json")
        if manifest["dispatched"] != 165 or manifest["hangs"] != 0:
            fail(f"{run}: bad run manifest")
        by_run[run] = {row["name"]: row for row in rows}

    first, second = (by_run[r["id"]] for r in CONTRACT["runs"])
    if set(first) != set(second):
        fail("cross-run case-name sets differ")
    keys = ("prog_sha256", "out_sha256", "outcome", "match", "sem_checked",
            "n_pred_wrong", "n_pred_nowrite", "n_stray_bytes", "gate_a", "ledger")
    for name in first:
        for key in keys:
            if first[name].get(key) != second[name].get(key):
                fail(f"cross-run mismatch {name}.{key}")

    print("PASS: 2 runs, 330 dispatches, 312/312 exact semantics, refuter 2/2, "
          "0 faults/hangs/donors/foreign runners/cross-run mismatches")
    return 0


if __name__ == "__main__":
    sys.exit(main())

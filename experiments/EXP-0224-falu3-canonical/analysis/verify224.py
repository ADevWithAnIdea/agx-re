#!/usr/bin/env python3
"""Verify EXP-0224's two formal generated-FMA captures."""

import argparse
import collections
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent.parent


def load_decoder(path):
    spec = importlib.util.spec_from_file_location("exp0224_isadb", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_run(path):
    rows = [json.loads(line) for line in (path / "sweep.jsonl").read_text().splitlines()]
    return {row["name"]: row for row in rows}


def reconstruct_body(row, isadb):
    parts = row["under_test"]
    lo = min(part["offset"] for part in parts)
    hi = max(part["offset"] + len(bytes.fromhex(part["bytes"])) for part in parts)
    body = bytearray(hi - lo)
    covered = bytearray(hi - lo)
    requested = {}
    errors = []
    for part in parts:
        off = part["offset"] - lo
        raw = bytes.fromhex(part["bytes"])
        body[off:off + len(raw)] = raw
        covered[off:off + len(raw)] = b"\x01" * len(raw)
        requested[off] = part["mnemonic"]
        if part["bytes"] != part.get("actual_bytes", part["bytes"]):
            errors.append("requested/actual byte mismatch")
    if not all(covered):
        return ["under_test ledger is not contiguous"]
    decoded, leftover = isadb.disassemble(bytes(body))
    walked = {}
    pos = 0
    for record in decoded:
        walked[pos] = record.get("mnemonic")
        pos += record.get("length", 0)
    for off, mnemonic in requested.items():
        if walked.get(off) != mnemonic:
            errors.append("offset %d requested %s walked %s" %
                          (lo + off, mnemonic, walked.get(off)))
    if leftover or pos != len(body):
        errors.append("whole walk consumed %d/%d, leftover %d" %
                      (pos, len(body), len(leftover)))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=EXP / "raw")
    parser.add_argument("--decoder", type=Path,
                        default=REPO / "tools" / "agx-isa" / "isadb.py")
    args = parser.parse_args()
    contract = json.loads((EXP / "CAPTURE_CONTRACT.json").read_text())
    run_paths = [args.raw / run["id"] for run in contract["runs"]]
    if any(not path.is_dir() for path in run_paths):
        raise SystemExit("missing formal run directory")
    isadb = load_decoder(args.decoder)
    runs = [(path.name, load_run(path)) for path in run_paths]
    failures = []
    summary = {"runs": {}}

    expected_dst = {"v2_dst_r%02d" % r for r in range(16)}
    expected_src = {"v2_src%s_r%02d" % (role, r)
                    for role in "abc" for r in range(24)}
    expected_dag = {"v2_dag_%03d" % i for i in range(100)}
    expected_load = {"v2_load_%s_gap%d" % (role, gap)
                     for role in "abc" for gap in (0, 1, 4)}

    for run_name, by_name in runs:
        rows = [row for row in by_name.values() if row["arm"] == "V2"]
        positives = [row for row in rows if row["expect_match"]]
        refuters = [row for row in rows if not row["expect_match"]]
        token_errors = {}
        for row in rows:
            errs = reconstruct_body(row, isadb)
            if errs:
                token_errors[row["name"]] = errs[:8]
            if not row["dispatched_bytes_verified"] or row["gate_a"]["n_bad"] \
                    or row["gate_a"]["n_alias"]:
                failures.append("%s/%s failed Gate A" % (run_name, row["name"]))
            if row["ledger"].get("COPIED") or row["ledger"].get("CARRIER"):
                failures.append("%s/%s contains donor fields" % (run_name, row["name"]))
            if row["status"] != "OK" or not row["sentinel_ok"] or row["restarts"]:
                failures.append("%s/%s invalid hardware run" % (run_name, row["name"]))
            if not row["bucket_ok"]:
                failures.append("%s/%s failed frozen bucket" % (run_name, row["name"]))
        names = set(by_name)
        for label, expected in (("destination", expected_dst), ("source", expected_src),
                                ("DAG", expected_dag), ("load", expected_load)):
            actual = names & expected
            if actual != expected:
                failures.append("%s wrong %s coverage" % (run_name, label))
        if len(rows) != 224 or len(positives) != 222 or len(refuters) != 2:
            failures.append("%s wrong V2 cardinality" % run_name)
        if any(row["observed_bucket"] != "exact" for row in positives):
            failures.append("%s has non-exact positive" % run_name)
        if any(row["observed_bucket"] == "exact" for row in refuters):
            failures.append("%s has a refuter that did not fire" % run_name)
        if token_errors:
            failures.append("%s has %d whole-walk errors" % (run_name, len(token_errors)))
        if "v2_num_fused_cancel" not in names:
            failures.append("%s omitted fused-rounding discriminator" % run_name)
        summary["runs"][run_name] = {
            "v2": len(rows),
            "positive_exact": sum(r["observed_bucket"] == "exact" for r in positives),
            "refuters_fired": sum(r["observed_bucket"] != "exact" for r in refuters),
            "outcomes": dict(collections.Counter(r["outcome"] for r in rows)),
            "whole_walk_errors": len(token_errors),
        }

    first_name, first = runs[0]
    second_name, second = runs[1]
    if set(first) != set(second):
        failures.append("formal case-name sets differ")
    cross = []
    for name in sorted(set(first) & set(second)):
        a, b = first[name], second[name]
        keys = ("prog_sha256", "out_sha256", "outcome", "observed_bucket", "under_test")
        if any(a.get(key) != b.get(key) for key in keys):
            cross.append(name)
    if cross:
        failures.append("cross-run mismatch in %d cases" % len(cross))
    summary["cross_run_mismatches"] = cross[:20]
    summary["failures"] = failures[:60]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify EXP-0223's formal V2 hardware and corrected-tokenizer contracts."""

import argparse
import collections
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent.parent


def load_decoder(path):
    spec = importlib.util.spec_from_file_location("exp0223_isadb", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_run(path):
    rows = [json.loads(line) for line in (path / "sweep.jsonl").read_text().splitlines()]
    return {row["name"]: row for row in rows}


def reconstruct_body(row, isadb):
    parts = row["under_test"]
    if not parts:
        return ["empty under_test ledger"]

    lo = min(part["offset"] for part in parts)
    hi = max(part["offset"] + len(bytes.fromhex(part["bytes"])) for part in parts)
    body = bytearray(hi - lo)
    covered = bytearray(hi - lo)
    requested = {}
    errors = []
    for part in parts:
        offset = part["offset"] - lo
        raw = bytes.fromhex(part["bytes"])
        # `under_test.bytes` is populated from Gate A's `actual_bytes`; newer
        # captures may retain both names explicitly.
        if part["bytes"] != part.get("actual_bytes", part["bytes"]):
            errors.append("requested/actual bytes differ at %d" % part["offset"])
        body[offset:offset + len(raw)] = raw
        covered[offset:offset + len(raw)] = b"\x01" * len(raw)
        requested[offset] = part["mnemonic"]
    if not all(covered):
        errors.append("under_test ledger is not contiguous")
        return errors

    decoded, leftover = isadb.disassemble(bytes(body))
    walked = {}
    walked_bytes = 0
    for rec in decoded:
        walked[walked_bytes] = rec.get("mnemonic")
        walked_bytes += rec.get("length", 0)
    for requested_offset, mnemonic in requested.items():
        if walked.get(requested_offset) != mnemonic:
            errors.append("offset %d: requested %s, walked %s" %
                          (requested_offset + lo, mnemonic, walked.get(requested_offset)))
    if leftover:
        errors.append("walk left %d bytes" % len(leftover))
    if walked_bytes != len(body):
        errors.append("walk consumed %d of %d bytes" % (walked_bytes, len(body)))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=EXP / "raw")
    parser.add_argument("--decoder", type=Path,
                        default=REPO / "tools" / "agx-isa" / "isadb.py")
    parser.add_argument("--runs", nargs=2,
                        help="two raw directory names; defaults to CAPTURE_CONTRACT_V4")
    args = parser.parse_args()
    isadb = load_decoder(args.decoder)

    if args.runs:
        run_paths = [args.raw / name for name in args.runs]
    else:
        contract = json.loads((EXP / "CAPTURE_CONTRACT_V4.json").read_text())
        run_paths = [args.raw / run["id"] for run in contract["runs"]]
    if any(not path.is_dir() for path in run_paths):
        raise SystemExit("missing formal run directory")
    runs = [(path.name, load_run(path)) for path in run_paths]
    failures = []
    summary = {"decoder": str(args.decoder), "runs": {}}

    for run_name, by_name in runs:
        rows = [row for row in by_name.values() if row["arm"] == "V2"]
        positives = [row for row in rows if row["expect_match"]]
        refuters = [row for row in rows if not row["expect_match"]]
        token_errors = {}
        for row in rows:
            errs = reconstruct_body(row, isadb)
            if errs:
                token_errors[row["name"]] = errs[:8]
            if not row["dispatched_bytes_verified"]:
                failures.append("%s/%s archive bytes not verified" % (run_name, row["name"]))
            if row["gate_a"]["n_bad"]:
                failures.append("%s/%s independent byte decode failed" % (run_name, row["name"]))
            if row["ledger"].get("COPIED") or row["ledger"].get("CARRIER"):
                failures.append("%s/%s contains donor fields" % (run_name, row["name"]))
            if row["status"] != "OK" or not row["sentinel_ok"]:
                failures.append("%s/%s invalid hardware run" % (run_name, row["name"]))
            if not row["bucket_ok"]:
                failures.append("%s/%s failed its frozen behavior bucket" %
                                (run_name, row["name"]))
        if token_errors:
            failures.append("%s has %d corrected-tokenizer failures" %
                            (run_name, len(token_errors)))
        expected_dst = {"v2_dst_r%02d" % dst for dst in range(16)}
        actual_dst = {row["name"] for row in rows if row["name"].startswith("v2_dst_r")}
        if actual_dst != expected_dst:
            failures.append("%s has wrong destination-reach set" % run_name)
        if len(rows) != 212 or len(positives) != 210 or len(refuters) != 2:
            failures.append("%s has wrong V2 cardinality" % run_name)
        if any(row["observed_bucket"] != "exact" for row in positives):
            failures.append("%s has a non-exact positive" % run_name)
        if any(row["observed_bucket"] == "exact" for row in refuters):
            failures.append("%s has a refuter that did not fire" % run_name)

        summary["runs"][run_name] = {
            "v2": len(rows),
            "positive_exact": sum(row["observed_bucket"] == "exact" for row in positives),
            "refuters_fired": sum(row["observed_bucket"] != "exact" for row in refuters),
            "original_alias_cases": sum(row["gate_a"]["n_alias"] > 0 for row in rows),
            "original_alias_records": sum(row["gate_a"]["n_alias"] for row in rows),
            "corrected_body_walk_failures": len(token_errors),
            "outcomes": dict(collections.Counter(row["outcome"] for row in rows)),
        }

    first_name, first = runs[0]
    second_name, second = runs[1]
    if set(first) != set(second):
        failures.append("run case-name sets differ")
    cross_mismatch = []
    for name in sorted(set(first) & set(second)):
        a, b = first[name], second[name]
        keys = ("prog_sha256", "out_sha256", "outcome", "observed_bucket", "under_test")
        if any(a.get(key) != b.get(key) for key in keys):
            cross_mismatch.append(name)
    if cross_mismatch:
        failures.append("cross-run mismatch in %d cases" % len(cross_mismatch))
    summary["cross_run_mismatches"] = cross_mismatch[:20]
    summary["failures"] = failures[:40]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

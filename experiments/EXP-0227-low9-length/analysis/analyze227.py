#!/usr/bin/env python3
"""Check a completed EXP-0227 sweep against its frozen pilot criteria."""

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep", type=Path)
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.sweep.read_text().splitlines() if line]
    probes = [row for row in rows if row.get("kind") == "low9_length"]
    errors = []
    if len(probes) != 5:
        errors.append("expected 5 length probes, found %d" % len(probes))
    for row in probes:
        p = row.get("length_probe", {})
        if row.get("status") != "OK":
            errors.append("%s status=%s" % (row["name"], row.get("status")))
        if not row.get("sentinel_ok"):
            errors.append("%s sentinel failed" % row["name"])
        if not row.get("dispatched_bytes_verified"):
            errors.append("%s archive bytes not verified" % row["name"])
        if row.get("gate_a", {}).get("n_bad"):
            errors.append("%s Gate A disagreement" % row["name"])
        if row.get("donor_fields"):
            errors.append("%s has donor fields" % row["name"])
        requested = row.get("under_test", [{}])[0].get("requested", {})
        byte2 = requested.get("opsel", 0) | (requested.get("opmode", 0) << 3)
        expected_bytes = "0901%02x05" % byte2
        if p.get("candidate_bytes") != expected_bytes:
            errors.append("%s candidate bytes=%r, expected %s" %
                          (row["name"], p.get("candidate_bytes"), expected_bytes))
        if p.get("inferred_length_candidates") != [4]:
            errors.append("%s inferred %r" %
                          (row["name"], p.get("inferred_length_candidates")))
        if not p.get("length_gate_ok"):
            errors.append("%s length gate failed" % row["name"])

    summary = {
        "rows": len(rows),
        "probes": len(probes),
        "all_status_ok": all(r.get("status") == "OK" for r in probes),
        "all_infer_four": all(r.get("length_probe", {}).get(
            "inferred_length_candidates") == [4] for r in probes),
        "errors": errors,
        "pass": not errors,
    }
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

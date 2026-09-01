#!/usr/bin/env python3
"""Frozen pilot analysis for EXP-0228."""

import argparse
import collections
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    args = ap.parse_args()
    rows = [json.loads(x) for x in (args.run / "sweep.jsonl").read_text().splitlines()]
    probes = [r for r in rows if r.get("kind") == "low9_length"]
    errors = []
    buckets = collections.Counter()
    for r in probes:
        p = r.get("length_probe", {})
        buckets[(r["arm"], r["status"], tuple(p.get("inferred_length_candidates", [])))] += 1
        if r["status"] != "OK":
            errors.append("%s status=%s" % (r["name"], r["status"]))
            continue
        if r.get("gate_a", {}).get("n_bad") or r.get("gate_a", {}).get("n_alias"):
            errors.append("%s Gate A" % r["name"])
        if r.get("donor_fields") or not r.get("sentinel_ok") or r.get("n_stray_bytes"):
            errors.append("%s provenance/integrity" % r["name"])
        if p.get("inferred_length_candidates") != [4]:
            errors.append("%s inferred=%r" %
                          (r["name"], p.get("inferred_length_candidates")))
        if r["arm"] == "CTL":
            if not p.get("control_detected"):
                errors.append("control did not detect wrong model")
        elif not r.get("match"):
            errors.append("%s host mismatch" % r["name"])
    pre, post = (json.loads((args.run / n).read_text())
                 for n in ("gpu_pre.json", "gpu_post.json"))
    quiet = [json.loads(x) for x in (args.run / "procs.jsonl").read_text().splitlines()]
    if pre.get("recovery_count") != post.get("recovery_count"):
        errors.append("recovery count changed")
    if any(q.get("n_foreign_runner") for q in quiet):
        errors.append("foreign runner")
    result = {
        "pass": not errors, "errors": errors, "probes": len(probes),
        "quiet_samples": len(quiet),
        "recovery_delta": post.get("recovery_count", 0) - pre.get("recovery_count", 0),
        "buckets": {"%s/%s/%s" % (a, s, list(ls)): n
                    for (a, s, ls), n in sorted(buckets.items())},
    }
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

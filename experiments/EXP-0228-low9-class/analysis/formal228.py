#!/usr/bin/env python3
"""Frozen formal acceptance gate for EXP-0228 Amendment 01."""

import argparse
import json
from pathlib import Path


ALL = tuple(v for v in range(256) if (v & 7) in (0, 1))
EXPECTED = ["full_b%02x" % v for v in ALL] + ["ctl_b20_wrong_r6"]


def load(path):
    return json.loads(path.read_text())


def check(path):
    errors = []
    rows = [json.loads(x) for x in (path / "sweep.jsonl").read_text().splitlines()]
    probes = [r for r in rows if r.get("kind") == "low9_length"]
    full = [r for r in probes if r.get("arm") == "FULL"]
    values = [int(r["length_probe"]["candidate_bytes"][4:6], 16) for r in full]
    if len(probes) != 65 or len(full) != 64:
        errors.append("case counts probes=%d full=%d" % (len(probes), len(full)))
    if len(values) != len(set(values)) or set(values) != set(ALL):
        errors.append("byte+2 coverage is not exact 64-value class")
    for r in probes:
        name, p = r["name"], r.get("length_probe", {})
        if r.get("status") != "OK":
            errors.append("%s status=%s" % (name, r.get("status")))
            continue
        if r.get("restarted") or r.get("foreign_retries"):
            errors.append("%s restart/foreign" % name)
        if not r.get("sentinel_ok") or r.get("n_stray_bytes"):
            errors.append("%s integrity" % name)
        if r.get("gate_a", {}).get("n_bad") or r.get("gate_a", {}).get("n_alias"):
            errors.append("%s Gate A" % name)
        if r.get("donor_fields"):
            errors.append("%s donor fields" % name)
        if p.get("marker_hits") != [True, True, True, True] or \
                not p.get("post_marker_hit") or \
                p.get("inferred_length_candidates") != [4] or \
                not p.get("length_gate_ok"):
            errors.append("%s length signature" % name)
        if r.get("arm") == "CTL":
            if r.get("match") or not r.get("bucket_ok") or not p.get("control_detected"):
                errors.append("control did not refute wrong model")
        elif not r.get("match"):
            errors.append("%s host mismatch" % name)
    slots = load(path / "01_slot_probe.json").get("learned")
    if slots != {"imem": 2, "mem": 1, "out": 0}:
        errors.append("slot map %r" % slots)
    manifest = load(path / "05_run_manifest.json")
    if manifest.get("dispatched") != 73 or manifest.get("hangs") != 0:
        errors.append("manifest %r" % manifest)
    pre, post = load(path / "gpu_pre.json"), load(path / "gpu_post.json")
    quiet = [json.loads(x) for x in (path / "procs.jsonl").read_text().splitlines()]
    if len(quiet) < 2 or any(q.get("n_foreign_runner") for q in quiet):
        errors.append("quiet window")
    if pre.get("busy_count") != 0 or post.get("busy_count") != 0:
        errors.append("busy snapshot")
    if pre.get("recovery_count") != post.get("recovery_count"):
        errors.append("recovery delta")
    inputs = load(path / "00_inputs.json")
    if inputs.get("target") != "G17P" or "A18 Pro" not in inputs.get("device", ""):
        errors.append("target metadata")
    return {"errors": errors, "probes": probes,
            "order": [r["name"] for r in probes], "quiet_samples": len(quiet),
            "recovery_delta": post.get("recovery_count", 0)-pre.get("recovery_count", 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run01", type=Path); ap.add_argument("run02", type=Path)
    args = ap.parse_args()
    a, b = check(args.run01), check(args.run02)
    cross = []
    if a["order"] != EXPECTED: cross.append("run01 order")
    if b["order"] != list(reversed(EXPECTED)): cross.append("run02 order")
    ma, mb = ({r["name"]: r for r in x["probes"]} for x in (a, b))
    if set(ma) != set(mb): cross.append("case sets")
    for name in sorted(set(ma) & set(mb)):
        for key in ("prog_sha256", "out_sha256", "outcome", "status"):
            if ma[name].get(key) != mb[name].get(key): cross.append("%s %s" % (name,key))
        if ma[name].get("length_probe", {}).get("observed_u32") != \
                mb[name].get("length_probe", {}).get("observed_u32"):
            cross.append("%s markers" % name)
    result = {
        "experiment": "EXP-0228-low9-class",
        "run01": {k:v for k,v in a.items() if k != "probes"},
        "run02": {k:v for k,v in b.items() if k != "probes"},
        "cross_run_errors": cross,
    }
    result["pass"] = not a["errors"] and not b["errors"] and not cross
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

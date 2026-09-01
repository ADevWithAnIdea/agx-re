#!/usr/bin/env python3
"""Frozen acceptance gate for EXP-0229's opposite-order G17P runs."""

import argparse
import hashlib
import json
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((EXP / "CAPTURE_CONTRACT_FORMAL.json").read_text())
EXPECTED = CONTRACT["expected_cases_run01"]


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(path, expected_order):
    errors = []
    rows = [json.loads(x) for x in (path / "sweep.jsonl").read_text().splitlines()]
    probes = [r for r in rows if r.get("kind") == "simd_length"]
    if [r["name"] for r in probes] != expected_order:
        errors.append("case order")
    if len(probes) != 23:
        errors.append("case count %d" % len(probes))
    for r in probes:
        name, p = r["name"], r.get("length_probe", {})
        # The generated prefix's byte+1 is the mode.
        mode = int(p.get("candidate_bytes", "0000")[2:4], 16)
        expected = 12 if mode == 6 else 10
        hits = [False, True, True] if expected == 12 else [True, True, True]
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
        if p.get("marker_hits") != hits or not p.get("post_marker_hit") or \
                p.get("inferred_length_candidates") != [expected] or \
                not p.get("length_gate_ok"):
            errors.append("%s length signature" % name)
        if name == "ctl_wrong_marker":
            if r.get("match") or not r.get("bucket_ok") or \
                    not p.get("control_detected"):
                errors.append("control did not reject wrong model")
        elif expected == 10 and not r.get("match"):
            errors.append("%s ten-byte host mismatch" % name)
        elif expected == 12 and r.get("n_pred_wrong") != 1:
            errors.append("%s twelve-byte marker mismatch count" % name)

    slots = load(path / "01_slot_probe.json").get("learned")
    if slots != CONTRACT["expected_slot_map"]:
        errors.append("slot map %r" % slots)
    manifest = load(path / "05_run_manifest.json")
    if manifest.get("dispatched") != 31 or manifest.get("hangs") != 0:
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
    return {
        "errors": errors, "probes": probes, "quiet_samples": len(quiet),
        "recovery_delta": post.get("recovery_count", 0) - pre.get("recovery_count", 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run01", type=Path)
    ap.add_argument("run02", type=Path)
    args = ap.parse_args()
    a = check(args.run01, EXPECTED)
    b = check(args.run02, list(reversed(EXPECTED)))
    cross = []
    ma = {r["name"]: r for r in a["probes"]}
    mb = {r["name"]: r for r in b["probes"]}
    if set(ma) != set(mb):
        cross.append("case sets")
    for name in sorted(set(ma) & set(mb)):
        for key in ("prog_sha256", "out_sha256", "outcome", "status"):
            if ma[name].get(key) != mb[name].get(key):
                cross.append("%s %s" % (name, key))
        if ma[name].get("length_probe", {}).get("observed_u32") != \
                mb[name].get("length_probe", {}).get("observed_u32"):
            cross.append("%s markers" % name)

    hash_errors = []
    for rel, want in CONTRACT["hashes"].items():
        path = EXP / rel
        if not path.exists() or sha(path) != want:
            hash_errors.append(rel)
    result = {
        "experiment": "EXP-0229-simd-length",
        "rule": "simd_shuffle mode == 0x06 ? 12 : 10",
        "run01": {k: v for k, v in a.items() if k != "probes"},
        "run02": {k: v for k, v in b.items() if k != "probes"},
        "cross_run_errors": cross,
        "hash_errors": hash_errors,
    }
    result["pass"] = not a["errors"] and not b["errors"] and not cross and not hash_errors
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

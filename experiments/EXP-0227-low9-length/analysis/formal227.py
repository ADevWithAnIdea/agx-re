#!/usr/bin/env python3
"""Frozen two-run acceptance gate for EXP-0227 Amendment 01."""

import argparse
import json
from pathlib import Path


EXPECTED = [
    "h1_b20_r0_imm55",
    "h1_b20_r0_imm33",
    "h1_b20_r6_imm57",
    "p1_known_b21_r0_imm55",
    "ctl_wrong_r0_model33",
]


def read_json(path):
    return json.loads(path.read_text())


def check_run(path):
    errors = []
    rows = [json.loads(line) for line in (path / "sweep.jsonl").read_text().splitlines()
            if line]
    probes = [row for row in rows if row.get("kind") == "low9_length"]
    slots = read_json(path / "01_slot_probe.json").get("learned")
    manifest = read_json(path / "05_run_manifest.json")
    pre, post = read_json(path / "gpu_pre.json"), read_json(path / "gpu_post.json")
    quiet = [json.loads(line) for line in (path / "procs.jsonl").read_text().splitlines()
             if line]

    if slots != {"imem": 2, "mem": 1, "out": 0}:
        errors.append("slot map %r" % slots)
    if manifest.get("hangs") != 0 or manifest.get("dispatched") != 13:
        errors.append("manifest %r" % manifest)
    if len(probes) != 5:
        errors.append("expected 5 probes, found %d" % len(probes))

    for row in probes:
        name = row.get("name", "?")
        p = row.get("length_probe", {})
        req = row.get("under_test", [{}])[0].get("requested", {})
        byte2 = req.get("opsel", 0) | (req.get("opmode", 0) << 3)
        expected_bytes = "0901%02x05" % byte2
        if row.get("status") != "OK":
            errors.append("%s status=%s" % (name, row.get("status")))
        if row.get("restarted") or row.get("foreign_retries"):
            errors.append("%s restart/foreign retry" % name)
        if not row.get("sentinel_ok") or row.get("n_stray_bytes") != 0:
            errors.append("%s sentinel/stray failure" % name)
        if row.get("gate_a", {}).get("n_bad") or row.get("gate_a", {}).get("n_alias"):
            errors.append("%s Gate A failure" % name)
        if row.get("donor_fields"):
            errors.append("%s donor fields" % name)
        if p.get("candidate_bytes") != expected_bytes:
            errors.append("%s candidate bytes %r != %s" %
                          (name, p.get("candidate_bytes"), expected_bytes))
        if p.get("marker_hits") != [True, True, True, True] or \
                not p.get("post_marker_hit") or \
                p.get("inferred_length_candidates") != [4]:
            errors.append("%s marker signature %r" % (name, p))
        if not p.get("length_gate_ok"):
            errors.append("%s length gate" % name)
        if row.get("arm") == "CTL":
            if row.get("match") or not row.get("bucket_ok") or \
                    not p.get("control_detected"):
                errors.append("%s detection control did not fire" % name)
        elif not row.get("match"):
            errors.append("%s host comparison mismatch" % name)

    if len(quiet) < 2:
        errors.append("only %d quiet samples" % len(quiet))
    if any(q.get("n_foreign_runner") != 0 for q in quiet):
        errors.append("foreign runner observed")
    if pre.get("busy_count") != 0 or post.get("busy_count") != 0:
        errors.append("nonzero pre/post busy_count")
    if pre.get("recovery_count") != post.get("recovery_count"):
        errors.append("recovery_count changed %r -> %r" %
                      (pre.get("recovery_count"), post.get("recovery_count")))
    inputs = read_json(path / "00_inputs.json")
    if inputs.get("target") != "G17P" or "A18 Pro" not in inputs.get("device", ""):
        errors.append("wrong target metadata")
    return {
        "path": str(path), "errors": errors, "rows": rows, "probes": probes,
        "probe_order": [r["name"] for r in probes], "quiet_samples": len(quiet),
        "recovery_delta": post.get("recovery_count", 0) - pre.get("recovery_count", 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run01", type=Path)
    ap.add_argument("run02", type=Path)
    args = ap.parse_args()
    a, b = check_run(args.run01), check_run(args.run02)
    cross_errors = []
    if a["probe_order"] != EXPECTED:
        cross_errors.append("run01 order %r" % a["probe_order"])
    if b["probe_order"] != list(reversed(EXPECTED)):
        cross_errors.append("run02 order %r" % b["probe_order"])
    ma = {r["name"]: r for r in a["probes"]}
    mb = {r["name"]: r for r in b["probes"]}
    if set(ma) != set(mb):
        cross_errors.append("case sets differ")
    for name in sorted(set(ma) & set(mb)):
        ra, rb = ma[name], mb[name]
        for key in ("prog_sha256", "out_sha256", "outcome", "status"):
            if ra.get(key) != rb.get(key):
                cross_errors.append("%s %s differs" % (name, key))
        if ra.get("length_probe", {}).get("observed_u32") != \
                rb.get("length_probe", {}).get("observed_u32"):
            cross_errors.append("%s observed markers differ" % name)

    result = {
        "experiment": "EXP-0227-low9-length",
        "run01": {k: v for k, v in a.items() if k not in ("rows", "probes")},
        "run02": {k: v for k, v in b.items() if k not in ("rows", "probes")},
        "cross_run_errors": cross_errors,
    }
    result["pass"] = not a["errors"] and not b["errors"] and not cross_errors
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

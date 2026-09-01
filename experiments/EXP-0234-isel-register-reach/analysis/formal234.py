#!/usr/bin/env python3
"""Formal cross-run gate for EXP-0234 canonical isel10 reach."""

import json
import sys
from collections import Counter
from pathlib import Path


def load(path):
    rows = [json.loads(line) for line in open(Path(path) / "sweep.jsonl")]
    return {row["name"]: row for row in rows if row.get("kind") == "isel_reach"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: formal234.py RUN01 RUN02")
    a, b = load(argv[1]), load(argv[2])
    names = sorted(set(a) | set(b))
    main_names = [n for n in names if not n.startswith("ctl_")]
    controls = [n for n in names if n.startswith("ctl_")]
    missing = [n for n in names if n not in a or n not in b]
    counts = Counter()
    byte_disagree = []
    observation_disagree = []
    undecidable = []
    semantic_fail = []
    gate_a_fail = []
    donor_fail = []
    source_model_failures = []
    high_exact_aliases = []
    high_mod16_aliases = []

    for name in main_names + controls:
        if name not in a or name not in b:
            continue
        ra, rb = a[name], b[name]
        role = ra.get("isel_reach_probe", {}).get("role")
        if name in main_names:
            counts[role] += 1
        for rec in (ra, rb):
            ga = rec.get("gate_a", {})
            body = rec.get("under_test", [])
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 \
                    or ga.get("n_alias") != 0 or len(body) != 1 \
                    or body[0].get("mnemonic") != "isel10":
                gate_a_fail.append("%s:%s" % (name, rec.get("run")))
            ledger = rec.get("ledger", {})
            if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
                donor_fail.append("%s:%s" % (name, rec.get("run")))
        if ra.get("prog_sha256") != rb.get("prog_sha256") \
                or ra.get("under_test") != rb.get("under_test"):
            byte_disagree.append(name)
        pa = ra.get("isel_reach_probe", {})
        pb = rb.get("isel_reach_probe", {})
        if pa.get("observed") != pb.get("observed"):
            observation_disagree.append(name)
        if name in main_names:
            if not pa.get("semantic_decidable") or not pb.get("semantic_decidable"):
                undecidable.append(name)
            if not ra.get("match") or not rb.get("match"):
                semantic_fail.append(name)
            if role in ("cmp_a", "cmp_b", "sel_true", "sel_false"):
                reg = pa.get("register")
                expected_model = "exact" if reg < 64 else "mod64"
                for probe in (pa, pb):
                    models = probe.get("matching_models", [])
                    if probe.get("oracle_model") != expected_model \
                            or expected_model not in models:
                        source_model_failures.append(name)
                    if reg >= 64 and "exact" in models:
                        high_exact_aliases.append(name)
                    if reg >= 80 and "mod16" in models:
                        high_mod16_aliases.append(name)

    control_fired = [n for n in controls if n in a and n in b
                     and not a[n].get("match") and not b[n].get("match")
                     and a[n].get("bucket_ok") and b[n].get("bucket_ok")]
    result = {
        "runs": [argv[1], argv[2]],
        "expected_counts": {
            "cmp_a": 128, "cmp_b": 128, "sel_true": 128, "sel_false": 128,
            "destination": 16,
        },
        "seen_counts": dict(counts),
        "controls_seen": len(controls),
        "missing_cross_run": missing,
        "byte_ledger_disagreements": byte_disagree,
        "observation_disagreements": observation_disagree,
        "semantically_undecidable": undecidable,
        "semantic_failures": semantic_fail,
        "gate_a_failures": gate_a_fail,
        "donor_failures": donor_fail,
        "source_model_failures": sorted(set(source_model_failures)),
        "high_exact_aliases": sorted(set(high_exact_aliases)),
        "high_mod16_aliases": sorted(set(high_mod16_aliases)),
        "control_fired": control_fired,
    }
    expected = result["expected_counts"]
    result["pass"] = bool(
        dict(counts) == expected and len(controls) == 2 and not missing
        and not byte_disagree and not observation_disagree and not undecidable
        and not semantic_fail and not gate_a_fail and not donor_fail
        and not source_model_failures and not high_exact_aliases and not high_mod16_aliases
        and len(control_fired) == 2)
    out = Path(__file__).with_name("formal_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({
        "pass": result["pass"], "seen_counts": result["seen_counts"],
        "controls_seen": len(controls), "control_fired": len(control_fired),
        "missing": len(missing), "byte_disagree": len(byte_disagree),
        "observation_disagree": len(observation_disagree),
        "undecidable": len(undecidable), "semantic_fail": len(semantic_fail),
        "gate_a_fail": len(gate_a_fail), "donor_fail": len(donor_fail),
        "source_model_failures": len(set(source_model_failures)),
        "high_exact_aliases": len(set(high_exact_aliases)),
        "high_mod16_aliases": len(set(high_mod16_aliases)),
    }, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

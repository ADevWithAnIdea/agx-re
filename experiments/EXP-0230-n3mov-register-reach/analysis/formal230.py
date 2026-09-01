#!/usr/bin/env python3
"""Formal cross-run/model gate for EXP-0230."""

import json
import sys
from collections import Counter
from pathlib import Path


MODELS = ("full96_zero_oob", "mod64", "low64_zero_high", "mod96")


def load(path):
    rows = [json.loads(line) for line in open(Path(path) / "sweep.jsonl")]
    return {row["name"]: row for row in rows if row.get("kind") == "n3_reach"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: formal230.py RUN01 RUN02")
    a, b = load(argv[1]), load(argv[2])
    names = sorted(set(a) | set(b))
    missing = [n for n in names if n not in a or n not in b]
    main_names = [n for n in names if n.startswith("r1_")]
    controls = [n for n in names if n.startswith("ctl_")]
    byte_disagree = []
    observation_disagree = []
    undecidable = []
    gate_a_fail = []
    donor_fail = []
    model_pass = {m: [] for m in MODELS}
    outcomes = Counter()
    descriptor_values = {14: set(), 15: set()}
    for name in main_names:
        if name not in a or name not in b:
            continue
        ra, rb = a[name], b[name]
        outcomes[(ra.get("outcome"), rb.get("outcome"))] += 1
        for rec in (ra, rb):
            rp0 = rec.get("reach_probe", {})
            descriptor_values.get(rp0.get("index_reg"), set()).add(
                (rp0.get("source", -1) << 1) | rp0.get("source_half", 0))
            ga = rec.get("gate_a", {})
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 or \
                    ga.get("n_alias") != 0 or len(rec.get("under_test", [])) != 1:
                gate_a_fail.append("%s:%s" % (name, rec.get("run")))
            ledger = rec.get("ledger", {})
            if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
                donor_fail.append("%s:%s" % (name, rec.get("run")))
        if ra.get("prog_sha256") != rb.get("prog_sha256") or \
                ra.get("under_test") != rb.get("under_test"):
            byte_disagree.append(name)
        pa, pb = ra.get("reach_probe", {}), rb.get("reach_probe", {})
        if pa.get("observed") != pb.get("observed"):
            observation_disagree.append(name)
        if not pa.get("semantic_decidable") or not pb.get("semantic_decidable"):
            undecidable.append(name)
            continue
        for model in MODELS:
            want_a = pa.get("expected_post_dst", {}).get(model)
            want_b = pb.get("expected_post_dst", {}).get(model)
            if pa.get("observed", {}).get("post_dst") != want_a or \
                    pb.get("observed", {}).get("post_dst") != want_b:
                model_pass[model].append(name)
    control_fired = []
    for name in controls:
        if name in a and name in b and not a[name].get("match") and not b[name].get("match"):
            control_fired.append(name)

    zero_mismatch_models = sorted(m for m in MODELS if not model_pass[m])
    selected_model = zero_mismatch_models[0] if len(zero_mismatch_models) == 1 else None
    descriptor_coverage = {str(k): len(v) for k, v in descriptor_values.items()}
    result = {
        "runs": [argv[1], argv[2]],
        "main_cases_expected_per_run": 512,
        "main_cases_seen": len(main_names),
        "controls_seen": len(controls),
        "missing_cross_run": missing,
        "byte_ledger_disagreements": byte_disagree,
        "observation_disagreements": observation_disagree,
        "semantically_undecidable": undecidable,
        "gate_a_failures": gate_a_fail,
        "donor_failures": donor_fail,
        "descriptor_coverage": descriptor_coverage,
        "model_mismatches": {k: v for k, v in model_pass.items()},
        "zero_mismatch_models": zero_mismatch_models,
        "selected_model": selected_model,
        "control_fired": control_fired,
        "outcome_pairs": {str(k): v for k, v in outcomes.items()},
    }
    result["pass"] = bool(
        len(main_names) == 512 and len(controls) == 2 and not missing and
        not byte_disagree and not observation_disagree and not undecidable and
        not gate_a_fail and not donor_fail and
        descriptor_coverage == {"14": 256, "15": 256} and
        selected_model is not None and len(control_fired) == 2)
    out = Path(__file__).with_name("formal_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v if not isinstance(v, list) else len(v)
                      for k, v in result.items() if k != "model_mismatches"}, indent=1))
    print("model mismatch counts:", {k: len(v) for k, v in model_pass.items()})
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

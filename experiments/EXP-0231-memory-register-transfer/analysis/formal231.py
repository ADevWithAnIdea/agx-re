#!/usr/bin/env python3
"""Formal cross-run/model gate for EXP-0231."""

import json
import sys
from collections import Counter
from pathlib import Path


MODELS = ("exact", "stale_destination", "zero", "source_mod64", "store_absent")


def load(path):
    rows = [json.loads(line) for line in open(Path(path) / "sweep.jsonl")]
    return {row["name"]: row for row in rows
            if row.get("kind") == "memory_transfer"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: formal231.py RUN01 RUN02")
    a, b = load(argv[1]), load(argv[2])
    names = sorted(set(a) | set(b))
    main_names = [n for n in names if n.startswith("m_")]
    controls = [n for n in names if n.startswith("ctl_")]
    missing = [n for n in names if n not in a or n not in b]
    byte_disagree = []
    observation_disagree = []
    undecidable = []
    gate_a_fail = []
    donor_fail = []
    model_mismatches = {m: [] for m in MODELS}
    direction_gap = Counter()
    outcomes = Counter()

    for name in main_names:
        if name not in a or name not in b:
            continue
        ra, rb = a[name], b[name]
        outcomes[(ra.get("outcome"), rb.get("outcome"))] += 1
        pa, pb = ra.get("transfer_probe", {}), rb.get("transfer_probe", {})
        direction_gap[(pa.get("source_tier"), pa.get("destination_tier"),
                       pa.get("gap"))] += 1
        for rec in (ra, rb):
            probe = rec.get("transfer_probe", {})
            ga = rec.get("gate_a", {})
            expected_instr = probe.get("gap", -99) + 2
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 \
                    or ga.get("n_alias") != 0 \
                    or len(rec.get("under_test", [])) != expected_instr:
                gate_a_fail.append("%s:%s" % (name, rec.get("run")))
            ledger = rec.get("ledger", {})
            if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
                donor_fail.append("%s:%s" % (name, rec.get("run")))
        if ra.get("prog_sha256") != rb.get("prog_sha256") \
                or ra.get("under_test") != rb.get("under_test"):
            byte_disagree.append(name)
        if pa.get("observed") != pb.get("observed"):
            observation_disagree.append(name)
        if not pa.get("semantic_decidable") or not pb.get("semantic_decidable"):
            undecidable.append(name)
            continue
        for model in MODELS:
            want_a = pa.get("models", {}).get(model, {})
            want_b = pb.get("models", {}).get(model, {})
            got_a, got_b = pa.get("observed", {}), pb.get("observed", {})
            if (got_a.get("scratch") != want_a.get("scratch")
                    or got_a.get("post_forward") != want_a.get("destination")
                    or got_a.get("post_destination") != want_a.get("destination")
                    or got_b.get("scratch") != want_b.get("scratch")
                    or got_b.get("post_forward") != want_b.get("destination")
                    or got_b.get("post_destination") != want_b.get("destination")):
                model_mismatches[model].append(name)

    control_fired = [name for name in controls if name in a and name in b
                     and not a[name].get("match") and not b[name].get("match")
                     and a[name].get("bucket_ok") and b[name].get("bucket_ok")]
    zero_mismatch = sorted(m for m in MODELS if not model_mismatches[m])
    expected_direction_gap = 3 * 3 * 4
    result = {
        "runs": [argv[1], argv[2]],
        "main_cases_expected": 144,
        "main_cases_seen": len(main_names),
        "controls_seen": len(controls),
        "direction_gap_cells_seen": len(direction_gap),
        "direction_gap_cells_expected": expected_direction_gap,
        "missing_cross_run": missing,
        "byte_ledger_disagreements": byte_disagree,
        "observation_disagreements": observation_disagree,
        "semantically_undecidable": undecidable,
        "gate_a_failures": gate_a_fail,
        "donor_failures": donor_fail,
        "model_mismatches": model_mismatches,
        "zero_mismatch_models": zero_mismatch,
        "selected_model": zero_mismatch[0] if len(zero_mismatch) == 1 else None,
        "control_fired": control_fired,
        "outcome_pairs": {str(k): v for k, v in outcomes.items()},
    }
    result["pass"] = bool(
        len(main_names) == 144 and len(controls) == 2 and not missing
        and len(direction_gap) == expected_direction_gap
        and not byte_disagree and not observation_disagree and not undecidable
        and not gate_a_fail and not donor_fail and zero_mismatch == ["exact"]
        and len(control_fired) == 2)
    out = Path(__file__).with_name("formal_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: len(v) if isinstance(v, list) else v
                      for k, v in result.items() if k != "model_mismatches"},
                     indent=1, sort_keys=True))
    print("model mismatch counts:", {k: len(v) for k, v in model_mismatches.items()})
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

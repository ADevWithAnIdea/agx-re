#!/usr/bin/env python3
"""Combine the broad EXP-0230 pair with Amendment-02's exact missing rows."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
base = json.load(open(HERE / "formal_result.json"))
r2 = json.load(open(HERE / "formal_r2_result.json"))

expected_missing = {
    "r1_i%02d_s%03d_h%d" % (plan, source, half)
    for plan in (14, 15) for source in range(92, 96) for half in (0, 1)
}
base_missing = set(base.get("semantically_undecidable", []))
r2_expected = {
    "r2_i%02d_s%03d_h%d" % (plan, source, half)
    for plan in (14, 15) for source in range(92, 96) for half in (0, 1)
}
r2_records = set()
for run in ("g17p_e0230_run03", "g17p_e0230_run04"):
    p = HERE.parent / "raw" / run / "sweep.jsonl"
    for row in map(json.loads, open(p)):
        if row.get("arm") == "R2":
            r2_records.add(row["name"])

result = {
    "base_main_cases": base.get("main_cases_seen"),
    "base_decidable_cases": base.get("main_cases_seen", 0) - len(base_missing),
    "base_missing_exact": sorted(base_missing),
    "base_missing_matches_amendment_scope": base_missing == expected_missing,
    "base_selected_model": base.get("selected_model"),
    "base_gate_a_failures": base.get("gate_a_failures"),
    "base_donor_failures": base.get("donor_failures"),
    "amendment_records_exact": r2_records == r2_expected,
    "amendment_pass": r2.get("pass"),
    "amendment_selected_model": r2.get("selected_model"),
    "closed_source_descriptor_values": 256,
    "closed_effective_source_gprs": 64,
}
result["pass"] = bool(
    result["base_main_cases"] == 512 and result["base_decidable_cases"] == 496 and
    result["base_missing_matches_amendment_scope"] and
    result["base_selected_model"] == "mod64" and
    not result["base_gate_a_failures"] and not result["base_donor_failures"] and
    result["amendment_records_exact"] and result["amendment_pass"] and
    result["amendment_selected_model"] == "mod64")

(HERE / "combined_result.json").write_text(
    json.dumps(result, indent=1, sort_keys=True) + "\n")
print(json.dumps(result, indent=1, sort_keys=True))
raise SystemExit(0 if result["pass"] else 1)

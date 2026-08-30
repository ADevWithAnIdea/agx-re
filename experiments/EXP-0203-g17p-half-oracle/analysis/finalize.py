#!/usr/bin/env python3
"""EXP-0203 -- assemble the final analysis/field_verdicts.json.

PRIMARY EVIDENCE: `raw/g17p_run31` (forward) and `raw/g17p_run32` (reverse).  These are the
two runs that carry the Gate A actual-byte ledger and the Gate C per-case semantic class, and
they are the Gate E confirmation pair (reversed case order).

SECONDARY, RETAINED: `raw/g17p_run21`, `raw/g17p_run22` (forward) and `raw/g17p_run23`
(reverse).  Same fields, same oracle, four fewer arms and NO actual-byte ledger.  They are
kept, unedited, and reported alongside -- RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 9:
"do not retroactively call an observation false merely because a later acceptance gate is
stricter than the experiment's frozen gate."

Verdicts carry the six INDEPENDENT axes of section 2 as well as the legacy label.

Usage:  python3 analysis/finalize.py
"""
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
P1, P2 = "raw/g17p_run31", "raw/g17p_run32"
L1, L2, L3 = "raw/g17p_run21", "raw/g17p_run22", "raw/g17p_run23"


def gate(a, b, mode, out):
    subprocess.run([sys.executable, str(EXP / "analysis" / "verdicts.py"), a, b,
                    "--g7", mode, "--out", str(EXP / out)], cwd=str(EXP), check=True,
                   stdout=subprocess.DEVNULL)
    return json.loads((EXP / out).read_text())


AXES = {
 "half_alu_fma12.dst": {
  "encoding_geometry": "geometry-mapped",
  "encoding_geometry_basis":
    "Gate A ledger on 64 of 64 dispatched cases in both runs: requested bytes == actual bytes "
    "read back from the dispatched artifact, and the value decoded from those ACTUAL bytes "
    "equals the requested value in 64/64. 16 distinct requested values -> 16 distinct actual "
    "encodings per arm, differing ONLY inside bits 4..7. Framing invariant: all four 2-byte "
    "length markers survived on 16/16 values in every arm and every run.",
  "liveness": "live",
  "liveness_basis":
    "10 of 11 decidable values per arm move the observable against the arm's single anchor "
    "observation (the 11th IS the anchor value). Detection-power control `__ctl_live_srcA`: "
    "8/8 oracle matches with 8 distinct payloads in every arm and both runs.",
  "semantics": "semantically-mapped",
  "semantics_basis":
    "An independent host predictor, fitted offline on EXP-0180's committed raw BEFORE this "
    "experiment's contract was frozen, predicts the COMPLETE 16-word post-state from each "
    "case's own pre-dump. It matched 11/11 decidable values per arm in BOTH runs (44/44 arm-"
    "values), and 8 competing frozen models were rejected. Four adversarial cases per arm "
    "(null block, opsel change, destination override) all produced the required NON-match.",
  "compiler_recipe": "generated-point",
  "compiler_recipe_basis":
    "The instruction is built byte by byte from documented rules -- necessarily, because "
    "db.json pins byte0 and an assembler cannot express any other destination. DONOR REGIONS "
    "DECLARED: bytes +6..+11 keep the values our OWN `k_hfma_abs` compiled to, and byte+2's "
    "opsel 6 is the compiler-observed hfma selector. Not `canonical-recipe-proven`: those six "
    "tail bytes were not generated from rules.",
  "target": "G17P-direct",
  "reproducibility": "independently-confirmed",
  "reproducibility_basis":
    "Two carriers (different Metal buffer signatures) x two disjoint register/readback plans "
    "x two seed sets x two run orders (forward g17p_run31, reverse g17p_run32); 0 cross-run "
    "disagreements; immutable raw; hashed authored sources; repeatable analysis scripts."},
 "half_pack.dstlo": {
  "encoding_geometry": "geometry-mapped",
  "encoding_geometry_basis":
    "Gate A ledger on 256 of 256 dispatched cases per arm x 4 arms x 2 runs: requested == "
    "actual == decoded, 256 distinct actual encodings for 256 distinct requested values, "
    "differing only inside bits 8..15. Framing invariant: `hw_markers == 4` on 256/256, so the "
    "HARDWARE consumed exactly four bytes for every value.",
  "liveness": "live",
  "liveness_basis":
    "254 of 256 values move the observable per arm (the 2 that do not are the anchor value "
    "and its bit-7 alias). Control `__ctl_hp_live`: 8/8 with 8 distinct payloads, every arm, "
    "both runs.",
  "semantics": "semantically-mapped",
  "semantics_basis":
    "256/256 full-post-state oracle match per arm in BOTH runs, over 29 distinct predicted "
    "payloads. Seven competing frozen models were rejected (all scored 2/80 on the pilot until "
    "the measured source-release was added, which the arithmetic member survived). Three "
    "adversarial cases per arm all NON-matched.",
  "compiler_recipe": "generated-point",
  "compiler_recipe_basis":
    "All four bytes are constructed from rules. DONOR VALUE DECLARED: byte+2 = 0x18 is the "
    "op/opflags byte our own compiled `half2` add uses; its bits were not independently "
    "derived here.",
  "target": "G17P-direct",
  "reproducibility": "independently-confirmed",
  "reproducibility_basis":
    "Two carriers x two disjoint readback plans (layout HI dst r1, layout LO dst r7) x two "
    "seed sets x forward and reverse run order; 0 cross-run disagreements."},
 "half_alu_fma12.ext": {
  "encoding_geometry": "ledger-verified",
  "encoding_geometry_basis":
    "Gate A ledger on 2048 of 2048 dispatched cases per arm x 3 arms x 2 runs, 2048 distinct "
    "actual encodings. Framing is NOT invariant here and that is the point: byte+4's low two "
    "bits are the length selector, so 128 of its 256 values change the consumed length "
    "(measured by the marker chain) and are excluded from every semantic claim.",
  "liveness": "live (per-byte; see db_defects and analysis/ext_bytes.json)",
  "liveness_basis":
    "byte+5 gives 29 distinct payloads over 256 values on all three arms. byte+4/+6/+7 give "
    "5..11. byte+8/+9/+10 give 2. byte+11 gives 1 on all three arms and is NOT declared "
    "inert. byte+10 is the cautionary case: 1 payload on carrier A, 2 on carriers B and C in "
    "the same runs.",
  "semantics": "bounded-map",
  "semantics_basis":
    "bits 40..47 (byte+5) are SEMANTICALLY MAPPED: 256/256 full-post-state oracle match on "
    "three arms in both runs, with bit 7 a measured don't-care (128/128 value pairs identical). "
    "The rest of `ext` is a liveness map with per-bit resolution, not a semantic map.",
  "compiler_recipe": "not-generated",
  "compiler_recipe_basis":
    "bits 48..95 are unmodelled; `half_alu_fma12` must keep `emit_unsafe`.",
  "target": "G17P-direct",
  "reproducibility": "auditable",
  "reproducibility_basis":
    "Three arms, two run orders, 1 cross-run disagreement in 5760 covered arm-values; one "
    "isolated GPU-hang fault at byte+7 = 0xEE on arm F12_EXT_C in run31 only, and one "
    "InnocentVictim that cost arm F12_EXT_C its anchor observation in run32 (see RESULTS.md "
    "-> Contamination)."},
}
AXES["half_pack.b3"] = dict(AXES["half_pack.dstlo"])
AXES["half_pack.b3"]["encoding_geometry_basis"] = AXES["half_pack.b3"][
    "encoding_geometry_basis"].replace("bits 8..15", "bits 24..31")

NOTES = json.loads((EXP / "analysis" / "notes.json").read_text())
DB_DEFECTS = json.loads((EXP / "analysis" / "db_defects.json").read_text())


def main():
    hw = gate(P1, P2, "hardware", "analysis/field_verdicts.json")
    fz = gate(P1, P2, "frozen", "work/fv_g7frozen.json")
    lg = gate(L1, L3, "hardware", "work/fv_legacy_21v23.json")
    ext = json.loads((EXP / "analysis" / "ext_bytes.json").read_text())
    for k, v in hw.items():
        v["note"] = NOTES.get(k, "")
        v["target"] = "G17P"
        v["evidence"] = ["EXP-0203"]
        v["axes"] = AXES.get(k, {})
        v["cross_check_frozen_G7"] = {
            "label": fz[k]["label"], "covered_values": fz[k]["covered_values"],
            "moved": fz[k]["moved"],
            "why_it_differs": ("the literal frozen G7 also required OUR OWN tokenizer's "
                               "mnemonic to match the anchor's. Every value it excluded had "
                               "hw_markers identical to the anchor AND oracle_match true, so "
                               "the correction re-admits passing values and cannot manufacture "
                               "a promotion. PRE_REGISTRATION Amendment 03b.")}
        v["cross_check_pre_ledger_runs"] = {
            "pair": "%s (forward) vs %s (reverse)" % (L1, L3),
            "note": "the earlier runs, retained: same oracle and gates MINUS Gate A, and with "
                    "four fewer arms",
            "label": lg[k]["label"], "covered_values": lg[k]["covered_values"],
            "moved": lg[k]["moved"], "disagree": lg[k]["disagree"]}
    hw["db_defects"] = DB_DEFECTS
    hw["_ext_byte_analysis"] = ext
    hw["_provenance"] = {
        "experiment": "EXP-0203-g17p-half-oracle", "target": "G17P (A18 Pro, applegpu_g17p)",
        "primary_gated_runs": [P1, P2],
        "primary_pair_role": "Gate E confirmation pair: forward and reverse case order, both "
                             "carrying the Gate A actual-byte ledger",
        "retained_earlier_gated_runs": [L1, L2, L3],
        "pilot": "raw/pilot01 (instruments only; never evidence for a field verdict)",
        "burned_run_ids": ["g17p_run01", "g17p_run11"],
        "clean_room": "OWN-SHADER + HW-PROBE; no Apple binary introspected"}
    (EXP / "analysis" / "field_verdicts.json").write_text(json.dumps(hw, indent=1, sort_keys=True))
    for k in sorted(hw):
        if k.startswith("_") or k == "db_defects":
            continue
        a = hw[k]["axes"]
        print("%-26s %-14s geom=%-16s live=%-6s sem=%-20s recipe=%-16s covered=%s/%s"
              % (k, hw[k]["label"], a.get("encoding_geometry"), a.get("liveness", "")[:6],
                 a.get("semantics"), a.get("compiler_recipe"),
                 hw[k]["covered_values"], hw[k]["encodable_range"]))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""EXP-0201 finalizer: attach the human-readable notes, the second confirmation
pair, and the `db_defects` block to `analysis/field_verdicts.json`.

    python3 analysis/finalize.py

Everything numeric here is copied from what `analysis/verdicts.py` already
re-derived from `raw/`; nothing is recomputed by hand and nothing is asserted
that a reader cannot check against `analysis/verdicts_pair1_*.json`,
`analysis/verdicts_pair2_*.json`, `analysis/maps.json` and
`analysis/op_semantics.json`.

The notes use the safe negative wording required by
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 1: an inert reading is
`inert in <exact tested envelope>; global role unknown`, never `unused`,
`reserved`, `don't-care` or `may be chosen arbitrarily`.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

NOTES = {
    "falu3.op": (
        "LIVE and SEMANTICALLY MAPPED on G17P, NOT PROMOTED: the only failing gate is E "
        "(no quiet confirmation window -- five sibling experiments dispatched GPU work "
        "throughout). 3 independent arms. On the compiled 3-source fma carrier with bits "
        "6/7 clear: low3=4 -> -b (bit-exact, incl. -(-0.0)=+0.0 and -inf), low3=5 -> "
        "0.0*b (NOT a constant zero: sign follows srcB, inf srcB gives NaN -- DEF-0201-2), "
        "low3=6 -> a*b+c (bit-exact FMA), low3=7 -> no output (32 of 256 values). Bits "
        "3/4/5 inert in that envelope; bits 6/7 corrupt. db.json's published low3 entries "
        "0 (a+b), 1 (a*b) and 2 (a*b+a) are REFUTED on this carrier -- 0/2 return a "
        "lane-uniform 7.5 (an unrelated live register) and 1 returns +0.0. Every cross-run "
        "disagreement in 8 runs is a fault/wrote-nothing flip inside the (v&7)==7 class; "
        "adjudicated agreement 100.00%."),
    "falu3_ext.op": (
        "LIVE and SEMANTICALLY MAPPED on G17P, NOT PROMOTED: only gate E fails. 4 "
        "independent arms. Accept rule is EXACTLY (v & 0xC7) == 0x06 -- 8 of 256 values -- "
        "so on the 10-byte saturating form ONLY low3=6 computes the fma; -b and the "
        "multiply-by-zero do NOT reproduce, and low3=5 leaves the output entirely "
        "unwritten. Bits 3/4/5 inert in this envelope, bits 6/7 corrupt. THE TWO `op` "
        "FIELDS DO NOT SHARE AN OPERATION MAP, although db.json currently carries one "
        "identical note on both descriptors."),
    "fspecial_est.srcA": (
        "CARRIER-UNDECIDABLE, NOT inert. 5 arms (precise rsqrt / divide / sqrt, plus a "
        "two-estimate kernel giving two occurrences), 256 values each, 0 faults: all 1280 "
        "read-backs are the carrier's exactly correct result. The POSITIVE CONTROL FAILED "
        "ON EVERY ARM -- sweeping subop over 20 values moves nothing, and the "
        "pre-registered falsifier (subop=0, which our own tokenizer then reads as a "
        "different instruction entirely) does not fire either. So the estimate's own "
        "result is not observable at the refined output of a precise:: lowering on these "
        "carriers, and zero movement here is not evidence of inertness. Safe wording: "
        "inert in this exact tested envelope; global role unknown. ONE reproducible "
        "effect was seen and is kept: srcA = 0x81, and only 0x81, in all 6 runs that "
        "carried the arm, makes the register holding a second live float read as 0.0 "
        "while leaving the estimate untouched -- consistent with the release-on-read "
        "lifecycle db.json documents for falu2, reached through a (reg 64 << 1)|1 source "
        "descriptor. One moving value with a dead control promotes nothing. NEXT: read "
        "the seed register directly (redirect the store, as EXP-0026 did)."),
    "falu3_srcmod12.opsel": (
        "LIVE within the mnemonic, NOT PROMOTED: only gate E fails. THE FIELD'S SPAN "
        "OVERLAPS ITS OWN DESCRIPTOR'S MATCH BIT (DEF-0201-1): opsel is bits 16..18 and "
        "the descriptor pins [17,1,1], so only 2 of 3 bits are free and the encodable "
        "range inside this mnemonic is 4 values {2,3,6,7}, not 8. Values {0,1,4,5} clear "
        "bit 17 and the pinned tokenizer re-labels the bytes falu_srcmod12b -- their "
        "movement is EXCLUDED from this field's count and reported separately. No "
        "assembler is used, so the prior aliasing (nominal 4 and 6 assembling to identical "
        "bytes) does not recur: 8 distinct requested values produced 8 distinct ACTUAL "
        "dispatched encodings, 0 ledger mismatches. Accept rule (v & 7) == 6; moved 3 of "
        "the 4 in-mnemonic values, 0 cross-run disagreements in 8 runs."),
    "falu3_srcmod12.ctrl": (
        "LIVE on G17P, NOT PROMOTED: only gate E fails. 128 values dense x 2 carriers, "
        "0 cross-run disagreements in 8 runs. Accept set is exactly {0x03}: rule "
        "(v & 0x7F) == 0x03, so all 7 modelled bits are load-bearing on this carrier. The "
        "pre-registered length model length = 6 + 2*(v & 3) is NOT contradicted -- only "
        "(v & 3) == 3 preserves the 12-byte framing, and values that re-length the "
        "instruction re-tokenize everything after it; that movement is recorded as a "
        "FRAMING effect with the mutated token, never as operand semantics. 64 of 128 "
        "values return an all-zero vector, 28 return a*b (third source dropped), 1 returns "
        "a*b-c, 24 fault in a contiguous region dispatched without a hang budget."),
    "copysign.operands": (
        "LIVE on G17P with a NAMED function, NOT PROMOTED: only gate E fails. This field "
        "was previously left untested after a dense M4 sweep of 256 legal values and 256 "
        "distinct encodings, because that sweep produced ONE distinct valid payload "
        "against ONE constant oracle. The binding constraint was the oracle, not the "
        "range, so this experiment changed the oracle and not the coverage: 13 "
        "pairwise-distinct named host candidates (asserted bit-exactly before freezing), a "
        "-0.0 sign source, two lanes where sign(a)==sign(b) on purpose, a ROLE-EXCHANGED "
        "carrier, and an adversarial set with +-0, +-inf, NaN, the smallest denormal and "
        "2^24. Result: 252 of 256 values move, V = 4 distinct valid payloads on the chosen "
        "arm (19 across the directory), 0 cross-run disagreements in 8 runs, and the "
        "accept set is EXACTLY {0x00,0x01,0x80,0x81} -- rule (v & 0x7E) == 0x00, i.e. bits "
        "0 and 7 inert and bits 1..6 required zero, the (reg<<1)|size operand shape with "
        "the inert top bit now measured on a sixth family. At the accept set the hardware "
        "computes copysign(a,b) on the load carrier and copysign(b,a) on the "
        "role-exchanged one, from BYTE-IDENTICAL instructions -- so the operand ROLE is "
        "not carried in this byte (DEF-0201-3). Every other value degrades quietly; the "
        "field never faults."),
}

DB_DEFECTS = {
    "DEF-0201-1": {
        "descriptor": "falu3_srcmod12",
        "field": "opsel",
        "claim": "The modelled field span (start 16, width 3) OVERLAPS the descriptor's "
                 "own match constraint [17,1,1]. Only 2 of the 3 bits are free within "
                 "this mnemonic; the encodable range is 4 values {2,3,6,7}, not 8. "
                 "Values with bit 17 clear are a DIFFERENT instruction "
                 "(falu_srcmod12b), which the pinned tokenizer confirms per case.",
        "evidence": ["raw/g17p_20260830_a_run01/sweep.jsonl",
                     "raw/g17p_20260830_a_run02/sweep.jsonl",
                     "analysis/maps.json"],
        "target": "G17P",
        "note": "This is the cause behind the earlier aliasing symptom (an assembler "
                "that could not clear the pinned bit). db.json is NOT edited here.",
    },
    "DEF-0201-2": {
        "descriptor": "falu3",
        "field": "op",
        "claim": "db.json's falu3.op note maps low-3 class 5 to `0` (a constant zero). "
                 "It is a MULTIPLY BY ZERO: the result's sign follows srcB (-0.0 for "
                 "negative srcB) and an INFINITE srcB yields NaN (0x7fc00000). "
                 "Additionally, low-3 classes 0, 1 and 2 (`a+b`, `a*b`, `a*b+a`) are "
                 "REFUTED on a compiled three-source fma carrier: 0 and 2 return a "
                 "lane-uniform constant drawn from an unrelated live register and 1 "
                 "returns +0.0. Classes 4, 6 and 7 are confirmed bit-exactly.",
        "evidence": ["analysis/op_semantics.json",
                     "raw/g17p_20260830_a_run01/sweep.jsonl",
                     "raw/g17p_20260830_a_run02/sweep.jsonl"],
        "target": "G17P",
        "note": "The published map came from a synthesized-and-lifted carrier with "
                "seeded registers; this is a compiled 3-source fma carrier. Neither "
                "record is retracted here. A hypothesis that would reconcile them -- "
                "classes 0/2/3 re-decoding the operand descriptors to a source class a "
                "3-source carrier does not name -- is NOT established.",
    },
    "DEF-0201-3": {
        "descriptor": "copysign",
        "field": "operands / _instruction",
        "claim": "byte+3 is a live operand descriptor with accept rule "
                 "(v & 0x7E) == 0x00, but it does NOT encode the operand ROLE. Two "
                 "carriers differing only in which argument is the magnitude source "
                 "compile to BYTE-IDENTICAL instructions (07 c2 88 00 at the same "
                 "offset) and compute copysign(a,b) and copysign(b,a) respectively. The "
                 "role is established by the surrounding register allocation, behind "
                 "bytes the descriptor models as match constants.",
        "evidence": ["analysis/maps.json",
                     "raw/g17p_20260830_a_run01/sweep.jsonl"],
        "target": "G17P",
        "note": "Consequence: copysign._instruction stays corpus-correlation. The "
                "4-byte word can be generated from the descriptor and executes "
                "correctly (generated-point), but a canonical recipe must state how "
                "the roles are established, which this experiment cannot.",
    },
    "OBS-0201-1": {
        "descriptor": "falu3",
        "field": "(numeric behaviour, not an encoding field)",
        "claim": "A denormal operand and/or a denormal RESULT does not survive the "
                 "falu3 fused multiply-add on G17P: 1.4e-45 * 2.0 + 0.0, whose IEEE "
                 "result is 0x00000002, returned 0x00000000. The two flush points are "
                 "NOT separated by this arm.",
        "evidence": ["analysis/op_semantics.json"],
        "target": "G17P",
        "note": "Found only by the bit-exact offline classifier; the sweep's own "
                "tolerance-based comparison accepted it as correct.",
    },
    "OBS-0201-2": {
        "descriptor": "fspecial_est",
        "field": "subop",
        "claim": "COMPILER OBSERVATION about our own source, not a hardware claim: on "
                 "G17P precise::rsqrt and precise::sqrt both lower to subop 0x0f, and "
                 "precise::divide(1,x) to subop 0x0d, where db.json's enum reads "
                 "9 = rcp, 11 = rsqrt, 13 = sqrt, 15 = rsqrt.",
        "evidence": ["work/census.json"],
        "target": "G17P",
        "note": "Recorded so the enum's provenance can be revisited; nothing is "
                "concluded about what the hardware computes for each subop.",
    },
}


def main():
    path = os.path.join(HERE, "field_verdicts.json")
    d = json.load(open(path))
    pair2 = json.load(open(os.path.join(HERE, "field_verdicts_pair2.json")))
    for k, v in d.items():
        v["note"] = NOTES.get(k, "")
        v["target"] = "G17P"
        v["evidence"] = ["EXP-0201"]
        v["confirmation_pairs"] = {
            "pair1_a_run01_forward_a_run02_reverse": {
                "cross_run_agree_pct": v.get("cross_run_agree_pct"),
                "disagree": v.get("disagree"),
                "common": v.get("common"),
                "cross_run_agree_pct_adjudicated":
                    v.get("cross_run_agree_pct_adjudicated"),
            },
            "pair2_a_run03_forward_a_run04_reverse": {
                "cross_run_agree_pct": pair2.get(k, {}).get("cross_run_agree_pct"),
                "disagree": pair2.get(k, {}).get("disagree"),
                "common": pair2.get(k, {}).get("common"),
            },
        }
        v["encodable_range"] = (4 if k == "falu3_srcmod12.opsel"
                                else v.get("values_dispatched"))
        v["quiet_confirmation"] = False
        v["blocked_by"] = [r for r in v.get("reasons", [])]
    d["_meta"] = {
        "experiment": "EXP-0201-g17p-float-alu-sixfield",
        "target": "G17P (Apple A18 Pro, applegpu_g17p)",
        "gate": "PRE_REGISTRATION.md section 7 as amended by PRE_REGISTRATION-A.md; "
                "RE_EXPERIMENT_PROCESS_CORRECTIONS.md gates A/B/C/E",
        "canonical_pair": ["g17p_20260830_a_run01 (forward)",
                           "g17p_20260830_a_run02 (reverse)"],
        "second_pair": ["g17p_20260830_a_run03 (forward)",
                        "g17p_20260830_a_run04 (reverse)"],
        "pre_amendment_runs_retained": ["g17p_20260830_run01",
                                        "g17p_20260830_run02",
                                        "g17p_20260830_run03",
                                        "g17p_20260830_run04"],
        "headline": "No field promoted. The single blocking gate for five of six is E "
                    "(no quiet confirmation window); fspecial_est.srcA is additionally "
                    "carrier-undecidable under gate B.",
    }
    d["db_defects"] = DB_DEFECTS
    json.dump(d, open(path, "w"), indent=1, default=str)
    print("field_verdicts.json finalized: %d fields, %d db_defects"
          % (len([k for k in d if not k.startswith("_") and k != "db_defects"]),
             len(DB_DEFECTS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""EXP-0203 -- byte-resolved analysis of `half_alu_fma12.ext` (bits 32..95).

`ext` is 64 bits wide, so no sampled set can establish it and its label is forced to
`untested` (PRE_REGISTRATION section 6).  What CAN be established is the internal structure:
which of its eight bytes are live, which one is a third source operand, and which bits of
byte+4 select length versus arithmetic.  That is a MODEL CORRECTION and is reported under
`db_defects`, per FIELD-SWEEP-PROTOCOL section 6.

Usage: python3 analysis/ext_bytes.py raw/g17p_run21 raw/g17p_run22 [raw/g17p_run23]
"""
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def load(d):
    return [json.loads(l) for l in open(Path(d) / "sweep.jsonl")]


def anchors(d):
    return {json.loads(l)["arm"]: json.loads(l) for l in open(Path(d) / "anchor.jsonl")}


def dig(r):
    o = r.get("observed")
    return "".join("%08x" % w for w in o["post"]) if o else None


def main():
    runs = sys.argv[1:] or ["raw/g17p_run31", "raw/g17p_run32"]
    R = [load(d) for d in runs]
    A = [anchors(d) for d in runs]
    out = {}
    for arm in ("F12_EXT_A", "F12_EXT_B", "F12_EXT_C"):
        if arm not in A[0] or A[0][arm].get("observed") is None:
            continue
        amk = A[0][arm]["hw_markers"]
        per = {}
        for bi in range(4, 12):
            rs = [[r for r in R[i] if r["arm"] == arm and r["field"] == "ext"
                   and r["byte_index"] == bi] for i in range(len(R))]
            r0 = sorted(rs[0], key=lambda x: x["value"])
            same_id = [r for r in r0 if r["hw_markers"] == amk]
            live = len({dig(r) for r in same_id} - {None})
            resmatch = [r["value"] for r in same_id if r.get("oracle_result_match")]
            fullmatch = [r["value"] for r in same_id if r.get("oracle_match")]
            hard = collections.Counter(r["outcome"] for r in r0
                                       if r["outcome"] in ("fault", "hang",
                                                           "measurement_failed"))
            # cross-run agreement on this byte
            dd = []
            if len(rs) > 1:
                m0 = {r["value"]: dig(r) for r in rs[0]}
                m1 = {r["value"]: dig(r) for r in rs[1]}
                dd = [v for v in set(m0) & set(m1) if m0[v] != m1[v]]
            per["byte+%d" % bi] = {
                "dispatched": len(r0),
                "hardware_identity_preserved": len(same_id),
                "distinct_observed_payloads_at_same_identity": live,
                "arith_model_result_match": len(resmatch),
                "full_vector_oracle_match": len(fullmatch),
                "hard_outcomes": dict(hard),
                "cross_run_disagreements": len(dd),
                "inert_at_same_identity": live <= 1,
            }
        out[arm] = per
    print(json.dumps(out, indent=1, sort_keys=True))
    (EXP / "analysis" / "ext_bytes.json").write_text(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

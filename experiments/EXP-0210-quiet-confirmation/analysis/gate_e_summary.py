#!/usr/bin/env python3
"""EXP-0210 -- the Gate E table, computed from this experiment's own outputs.

    python3 analysis/gate_e_summary.py

Reads every `raw/<tag>/quietcheck.json` (the quiet measurement) and every
`analysis/out/*.json` produced by `analysis/pairwise.py` (the ledger + agreement), and prints
one row per confirmed pair.  It decides nothing that is not already in those files; it only
puts the three Gate E conjuncts side by side:

    quiet(A) AND quiet(B) AND identical ledgers AND no victim/cascade AND opposite order

`PAIRS` names, per source experiment, the two captures and the two quiet tags.  Superseded
captures are listed in `SUPERSEDED` and are printed but never scored.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)

PAIRS = [
    # (source experiment, pairwise json, quiet tag A, quiet tag B, order A, order B, fields)
    ("EXP-0203", "e0203_q43_q44.json", "e0203_q43", "e0203_q44", "forward", "reverse",
     ["half_alu_fma12.dst", "half_pack.dstlo", "half_pack.b3"]),
    ("EXP-0205", "e0205_q03_q04.json", "e0205_q03", "e0205_q04", "forward", "reverse",
     ["simd_reduce.op", "simd_reduce.dtype", "simd_shuffle.dir", "simd_shuffle.cache"]),
    ("EXP-0202", "e0202_q03_q04.json", "e0202_q03", "e0202_q04", "forward", "reverse",
     ["irotate.operands", "ibitcount.cache", "ibitcount.dst", "cvt_f2i._instruction"]),
    ("EXP-0201", "e0201_q01_q02.json", "e0201_q01", "e0201_q02", "forward", "reverse",
     ["falu3.op", "falu3_ext.op", "falu3_srcmod12.opsel", "falu3_srcmod12.ctrl",
      "copysign.operands"]),
    ("EXP-0199", "e0199_q01_q02.json", "e0199_q01", "e0199_q02", "shuffle", "reverse",
     ["frag_depth_store._instruction", "sfu_marker._instruction"]),
    # EXP-0206: its OWN committed run05/run07 are the quiet pair (re-derived from their own
    # procs.jsonl: zero foreign dispatch runners in either).  The remaining carriers were NOT
    # REACHED -- see RESULTS section 8.2.  No EXP-0210 quiet tags exist for this row, so the
    # tool prints NOT REACHED and the committed-pair numbers are in
    # analysis/out/e0206_committed_run05_run07.json.
    ("EXP-0206", "e0206_committed_run05_run07.json", "__committed__", "__committed__",
     "shuffled:206", "shuffled:407",
     ["pop_reconverge.reserved", "ret.scoreboard", "stop.reserved (cf_nl3/cf_ifnl arms)"]),
    ("EXP-0204", "e0204_c1_c2.json", "e0204_c1", "e0204_c2", "shuffle", "reverse",
     ["tex_sample.mode", "tex_write.amode", "tex_write.rsv11"]),
    ("EXP-0204", "e0204_d1_d2.json", "e0204_d1", "e0204_d2", "forward", "reverse",
     ["tex_deriv.dstsrc"]),
]


def jload(p):
    try:
        return json.load(open(p))
    except Exception:                                              # noqa: BLE001
        return None


def main():
    rows = []
    for src, pw, qa, qb, oa, ob, fields in PAIRS:
        P = jload(os.path.join(HERE, "out", pw))
        QA = jload(os.path.join(EXP, "raw", qa, "quietcheck.json"))
        QB = jload(os.path.join(EXP, "raw", qb, "quietcheck.json"))
        if P is None or QA is None or QB is None:
            rows.append({"source": src, "fields": fields, "status": "NOT REACHED",
                         "have_pairwise": P is not None,
                         "have_quiet": [QA is not None, QB is not None]})
            continue
        led_ok = (P["ledger"].get("actual_bytes_DIFFER", 0) == 0
                  and P["ledger"].get("bytes_match_FALSE_A", 0) == 0
                  and P["ledger"].get("bytes_match_FALSE_B", 0) == 0
                  and P["ledger"].get("req_NE_dec_A", 0) == 0
                  and P["ledger"].get("req_NE_dec_B", 0) == 0)
        vict = sum(P["victim_records"].values())
        ag = P["agreement"]
        # A capture that stopped early is not a "clean run": if one side is missing keys the
        # other dispatched, the pair does not cover the same cases and cannot confirm them.
        complete = (P["A_only"] == 0 and P["B_only"] == 0)
        met = bool(QA.get("QUIET") and QB.get("QUIET") and led_ok and complete
                   and vict == 0 and ag["disagree"] == 0 and oa != ob)
        rows.append({
            "source": src, "fields": fields,
            "orders": [oa, ob],
            "quiet": [QA.get("QUIET"), QB.get("QUIET")],
            "max_foreign_runner": [QA.get("max_foreign_runner"),
                                   QB.get("max_foreign_runner")],
            "recovery_delta": [QA.get("Q2b_recovery_delta"), QB.get("Q2b_recovery_delta")],
            "samples": [QA.get("samples"), QB.get("samples")],
            "ledger_identical": led_ok,
            "both_runs_cover_same_keys": complete,
            "A_only": P["A_only"], "B_only": P["B_only"],
            "ledger": P["ledger"],
            "shared_keys": P["shared_keys"], "key_unique": P["key_unique"],
            "agreement_pct": ag["pct"], "agree": ag["agree"], "disagree": ag["disagree"],
            "hard_flip": ag["hard_flip"], "soft_disagree": ag["soft_disagree"],
            "both_hard_excluded": ag["both_hard_excluded"],
            "hard_outcomes": P["hard_outcomes"], "victim_records": vict,
            "status": "GATE E MET" if met else "GATE E NOT MET",
        })
    json.dump(rows, sys.stdout, indent=1)
    print()
    print("\n=== one line per pair ===")
    for r in rows:
        print("%-9s %-14s quiet=%s ledger=%s same-keys=%s agree=%s  %s"
              % (r["source"], r["status"], r.get("quiet"), r.get("ledger_identical"),
                 r.get("both_runs_cover_same_keys"),
                 r.get("agreement_pct"), ",".join(r["fields"])[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

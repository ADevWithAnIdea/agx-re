#!/usr/bin/env python3
"""EXP-0113 post-capture analysis. Reads raw/<run>/01_results.jsonl (both
runs, must already be byte-identical -- verify.py --captured checks that),
computes the POST-HOC comparisons the per-case oracles cannot express
alone (H2 producer-independence and pair-quantization; H3 buffer-count
correlation), and writes analysis.json. No GPU access. Re-runnable.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as RUN  # noqa: E402


def load_results(run_id):
    p = HERE / "raw" / run_id / "01_results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def by_name(rows):
    return {r["name"]: r for r in rows}


def word(row, k):
    return row["observed"].get(str(k))


def analyze():
    rows = load_results(RUN.RUNS[0])
    rows2 = load_results(RUN.RUNS[1])
    assert [r["name"] for r in rows] == [r["name"] for r in rows2], "case order/name drift between runs"
    n1 = by_name(rows)
    n2 = by_name(rows2)
    cross_run_diffs = [a["name"] for a, b in zip(rows, rows2) if a != b]
    # DECISIVE OWN FINDING (not a harness defect): 01_results.jsonl is NOT
    # byte-identical between run01/run02 -- verify.py --captured reports
    # this as a FAIL, exactly as it should (this experiment's own frozen
    # byte-identity bar). Confirmed confined to H1_LOADFWD (4/46 cases:
    # loadfwd_singlehop_r7/r16/r63, loadfwd_mismatch_load67_read3) -- EVERY
    # other group (SEED_CHECK, H1_ALIAS_RECONFIRM, H1_CTRL_BITS_4_6,
    # H2_REGMOVE_C9, H3_BUFFER_SIGNATURE, 33/46 cases outside H1_LOADFWD's
    # own persist/mismatch subgroup) round-trips byte-identically across
    # both independent hardware runs. See RESULTS.md Section on H1_LOADFWD
    # for the full account: this cross-run instability is itself the
    # headline H1c finding (the apparent load-forwarding "success" is not
    # even reproducible with IDENTICAL bytes on IDENTICAL hardware across
    # two independent process launches, let alone a validated addressing
    # mechanism).
    non_loadfwd_diffs = [name for name in cross_run_diffs if n1[name]["group"] != "H1_LOADFWD"]
    assert not non_loadfwd_diffs, "unexpected cross-run divergence OUTSIDE H1_LOADFWD: %r" % non_loadfwd_diffs
    n = n1  # run01 is the reference row set for every group EXCEPT H1_LOADFWD's own cross-run table below
    out = {"schema": 1, "n_cases": len(rows),
           "cross_run_byte_identity": {
               "identical": cross_run_diffs == [],
               "diverging_case_names": cross_run_diffs,
               "diverging_groups": sorted(set(n1[nm]["group"] for nm in cross_run_diffs)),
           }}

    # ---- H1_ALIAS_RECONFIRM / H1_CTRL_BITS_4_6 summary --------------
    h1_alias = {}
    for name in ("falu2i_srca_high67_reconfirm", "falu2_srcb_high67_reconfirm"):
        r = n[name]
        h1_alias[name] = {"observed": word(r, 0), "match_aliasing_prediction": r["match"]}
    out["h1_alias_reconfirm"] = h1_alias

    ctrl = {}
    for bit in (4, 5, 6):
        lo = n["ctrl_low_bit%d" % bit]
        hi = n["ctrl_high_bit%d" % bit]
        lo_v, hi_v = word(lo, 0), word(hi, 0)
        verdict = "inert_or_aliased"
        if lo_v is not None and lo_v != 30.0:
            verdict = "general_corruptor"  # changed the LOW baseline too
        elif hi_v is not None and hi_v != 30.0:
            verdict = "bank_select_candidate"  # low unchanged, high changed away from aliasing
        ctrl["bit%d" % bit] = {"low_observed": lo_v, "high_observed": hi_v, "verdict": verdict}
    out["h1_ctrl_bits_4_6"] = ctrl

    # ---- H1_LOADFWD summary (BOTH runs shown explicitly -- this group
    # has genuine cross-run divergence, see cross_run_byte_identity above)
    LOADFWD_A = [1234, 5678, 9, 10]

    def words4(r, base=0):
        return [word(r, k) for k in range(base, base + 4)]

    singlehop = {}
    for r in rows:
        if r["group"] == "H1_LOADFWD" and r["name"].startswith("loadfwd_singlehop_r"):
            R = int(r["name"][len("loadfwd_singlehop_r"):])
            r2 = n2[r["name"]]
            obs1, obs2 = words4(r), words4(r2)
            singlehop[R] = {"run01_observed": obs1, "run01_matches_a": obs1 == LOADFWD_A,
                             "run02_observed": obs2, "run02_matches_a": obs2 == LOADFWD_A,
                             "reproduced_across_runs": obs1 == obs2,
                             "pilot_predicted_success": r["expect_match"]}
    out["h1_loadfwd_singlehop"] = singlehop

    persist = {}
    for name in ("loadfwd_persist_r67", "loadfwd_persist_r7"):
        r, r2 = n[name], n2[name]
        persist[name] = {
            "run01_first_read": words4(r, 0), "run01_second_read": words4(r, 4),
            "run02_first_read": words4(r2, 0), "run02_second_read": words4(r2, 4),
            "reproduced_across_runs": r == r2,
            "persistence_holds_run01": words4(r, 0) == LOADFWD_A and words4(r, 4) == LOADFWD_A,
            "persistence_holds_run02": words4(r2, 0) == LOADFWD_A and words4(r2, 4) == LOADFWD_A,
        }
    out["h1_loadfwd_persistence"] = persist

    mm, mm2 = n["loadfwd_mismatch_load67_read3"], n2["loadfwd_mismatch_load67_read3"]
    out["h1_loadfwd_mismatch"] = {
        "run01_observed": words4(mm), "run02_observed": words4(mm2),
        "reproduced_across_runs": mm == mm2,
    }

    # ---- H2_REGMOVE_C9: producer-independence + pair-quantization ---
    v1 = n["move_c9_producer_v1"]["observed"]["0"]
    v2 = n["move_c9_producer_v2"]["observed"]["0"]
    out["h2_producer_independence"] = {
        "producer_v1_seed_30.0_observed": v1, "producer_v2_seed_2.0_observed": v2,
        "identical_regardless_of_producer_value": v1 == v2,
        "verdict": ("does NOT read the ALU-written GPR (producer-independent)"
                    if v1 == v2 else "DOES depend on producer value (candidate real move)"),
    }
    pairs = {}
    for lo in (0, 2, 4, 8):
        a = n["move_c9_pair_%d_lo" % lo]["observed"]["0"]
        b = n["move_c9_pair_%d_hi" % lo]["observed"]["0"]
        pairs["pair_%d_%d" % (lo, lo + 1)] = {"src_reg_%d" % lo: a, "src_reg_%d" % (lo + 1): b,
                                                "identical": a == b}
    out["h2_pair_quantization"] = pairs

    # ---- H3_BUFFER_SIGNATURE: content vs buffer count ---------------
    h3 = {}
    for src_reg in (0, 2, 4, 8):
        row = {}
        for bufN in (1, 2, 3):
            r = n["h3_buf%d_src%d" % (bufN, src_reg)]
            row["buf%d" % bufN] = r["observed"]["0"]
        vals = list(row.values())
        row["identical_across_buffer_counts"] = len(set(vals)) == 1
        h3["src_reg_%d" % src_reg] = row
    out["h3_buffer_signature"] = h3

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    out = analyze()
    txt = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(txt)
        print("wrote analysis.json")
    else:
        print(txt)


if __name__ == "__main__":
    main()

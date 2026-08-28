#!/usr/bin/env python3
"""report.py -- EXP-0104 derived report generator.

Reads raw/m4_20260827_run01.jsonl (gated) and re-derives the headline
per-item facts referenced in RESULTS.md, so a reviewer can regenerate the
same numbers from the immutable raw capture without re-reading RESULTS.md's
prose. Read-only over raw/; writes analysis/summary.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
RAW = os.path.join(EXP_ROOT, "raw", "m4_20260827_run01.jsonl")


def load():
    recs = {}
    for line in open(RAW):
        d = json.loads(line)
        if "case_id" in d:
            recs[d["case_id"]] = d
    return recs


def main():
    recs = load()
    out = {}

    # CF-03 finite resource: deepest tested depth per family, all verdicts.
    for fam, prefix in [("ifnest", "cf_ifnest_"), ("loopnest1", "cf_loopnest1_"),
                         ("loopnestD", "cf_loopnestD_")]:
        rows = []
        for cid, d in recs.items():
            if cid.startswith(prefix):
                depth = int(cid.split("_")[-1])
                rows.append((depth, d["status"], d["verdict"]))
        rows.sort()
        out[f"CF-03_{fam}"] = rows

    # CF-05/06: dst_pred census + splice results
    out["CF-05_splice"] = {
        cid: recs[cid]["out"].get("_locate", {}) | {"results": recs[cid]["out"].get("results")}
        for cid in recs if cid.startswith("cf_predalias_splice_")
    }

    # CF-01/02-reach
    out["reach_splices"] = {
        cid: {"status": recs[cid]["status"], "locate": recs[cid]["out"].get("_locate", {}),
              "results": recs[cid]["out"].get("results")}
        for cid in recs if cid.startswith("cf_reach_splice_")
    }

    # CF-04 structural
    d = recs["cf_structural_ret_vs_join"]["out"]
    out["CF-04_structural"] = {"ret_early_len": d["a_len"], "plain_join_len": d["b_len"],
                                "identical": d["identical"]}

    # SIMD-01 partial simdgroup
    r = recs["simd_width_partial48"]["out"]["results"]
    out["SIMD-01_partial48"] = {"lane_id_32_48": r["0"][32:48], "tps_32_48": r["1"][32:48],
                                 "sgid_32_48": r["2"][32:48]}

    # SIMD-03 shuffle sweep
    out["SIMD-03_shuffle"] = {
        cid.replace("simd_shuffle_idx_", ""): recs[cid]["out"]["results"]["0"][0]
        for cid in recs if cid.startswith("simd_shuffle_idx_") and "perlane" not in cid
    }
    out["SIMD-03_shufflexor"] = {
        cid.replace("simd_shufflexor_mask_", ""): recs[cid]["out"]["results"]["0"][:4]
        for cid in recs if cid.startswith("simd_shufflexor_mask_")
    }
    out["SIMD-03_quadshuffle"] = {
        cid.replace("simd_quadshuffle_idx_", ""): recs[cid]["out"]["results"]["0"][:4]
        for cid in recs if cid.startswith("simd_quadshuffle_idx_")
    }

    # SIMD-05 fragment geometry (representative pixels)
    out["SIMD-05_frag"] = {}
    for fn in ("f_quad_selfcode", "f_quad_xor1", "f_quad_xor2", "f_quad_xor3",
               "f_quad_up1", "f_quad_down1"):
        px = recs[f"frag_{fn}"]["out"]["pixels"]
        out["SIMD-05_frag"][fn] = {k: v["r"] for k, v in px.items()}

    # SIMD-06 structural
    out["SIMD-06_structural"] = recs["simd_sgbar_structural"]["out"]["lens"]
    out["SIMD-06_conv"] = {
        "with_barrier": recs["simd_sgbar_conv"]["out"]["results"]["0"],
        "without_barrier": recs["simd_sgbar_conv_none"]["out"]["results"]["0"],
    }

    # SIMD-07 fragment ballot
    out["SIMD-07_frag"] = {}
    for fn in ("f_ballot_baseline", "f_ballot_onediscard",
               "f_ballot_baseline_raw", "f_ballot_onediscard_raw"):
        px = recs[f"frag_{fn}"]["out"]["pixels"]
        out["SIMD-07_frag"][fn] = px

    summary_path = os.path.join(HERE, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()

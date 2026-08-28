#!/usr/bin/env python3
"""EXP-0109 post-capture analysis (pure arithmetic on already-captured
run01 JSONL; issues no GPU calls). Decodes half-float bits from the mrt/
dualsource HW-PROBE records, cross-checks the geometric expectation for the
sampled pixel, and reports vertex-fetch-format byte-length deltas from the
structural vfetch_extract records. Writes analysis/summary.json.
"""
import json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def half_to_float(bits):
    return struct.unpack("<e", struct.pack("<H", bits & 0xFFFF))[0]


def load(run):
    return {r["id"]: r for r in (json.loads(l) for l in (HERE / "raw" / run / "04_results.jsonl").read_text().splitlines())}


def main():
    recs = load("m4-20260828-run01")

    out = {}

    # ---- MRT: decode half4 bits, check att2/att3 == att0/att1 * 0.5 -------
    mrt = {}
    for natt in (1, 2, 4):
        g = recs[f"mrt_hw_{natt}"]["gated"]["result"]
        targets = {t["att"]: [half_to_float(b) for b in t["half_bits"]] for t in g["targets"]}
        mrt[natt] = targets
    # f_mrt4: c2 = c0*0.5, c3 = c1*0.5 (kernels/mrt_interp.metal f_mrt4)
    c0, c1, c2, c3 = mrt[4][0], mrt[4][1], mrt[4][2], mrt[4][3]
    half_check = {
        "c0": c0, "c1": c1, "c2": c2, "c3": c3,
        "c2_matches_half_c0": all(abs(c2[i] - c0[i] * 0.5) < 0.01 for i in range(4)),
        "c3_matches_half_c1": all(abs(c3[i] - c1[i] * 0.5) < 0.01 for i in range(4)),
        "mrt1_matches_mrt4_att0": all(abs(mrt[1][0][i] - mrt[4][0][i]) < 0.001 for i in range(4)),
        "mrt2_matches_mrt4_att0_att1": (
            all(abs(mrt[2][0][i] - mrt[4][0][i]) < 0.001 for i in range(4)) and
            all(abs(mrt[2][1][i] - mrt[4][1][i]) < 0.001 for i in range(4))
        ),
    }
    out["mrt"] = half_check

    # ---- dual-source: does the blended pixel match c1 (index(1)), not c0? -
    ds = recs["dualsource_hw"]["gated"]["result"]
    ds_val = [half_to_float(b) for b in ds["half_bits"]]
    out["dualsource"] = {
        "observed_rgba": ds_val,
        "expected_c1_rgba": c1,  # v_common's c1 == f_dualsource's index(1) output, same geometry/sample point
        "expected_c0_rgba": c0,
        "matches_c1_not_c0": (
            all(abs(ds_val[i] - c1[i]) < 0.02 for i in range(4)) and
            not all(abs(ds_val[i] - c0[i]) < 0.02 for i in range(4))
        ),
    }

    # ---- vsfetch format family: byte-length + presence of format-specific code
    vf = {}
    for cid in ["vsfetch_format_float4", "vsfetch_format_half4", "vsfetch_format_uchar4norm",
                "vsfetch_format_short4norm", "vsfetch_format_int4", "vsfetch_format_uint4",
                "vsfetch_format_int1010102norm"]:
        g = recs[cid]["gated"]
        vf[cid] = {"len": g["vertex_hex_len"], "hex": g["vertex_hex"]}
    baseline_hex = vf["vsfetch_format_float4"]["hex"]
    for cid, v in vf.items():
        v["byte_identical_to_float4_baseline"] = (v["hex"] == baseline_hex)
        del v["hex"]
    out["vsfetch_format_lengths"] = vf

    # ---- vsfetch layout family: byte length deltas ------------------------
    layout = {}
    for cid in ["vsfetch_stride_32", "vsfetch_stride_64", "vsfetch_offset_0", "vsfetch_offset_16",
                "vsfetch_step_vertex", "vsfetch_step_instance",
                "vsfetch_instance_rate1", "vsfetch_instance_rate2"]:
        g = recs[cid]["gated"]
        layout[cid] = {"len": g["vertex_hex_len"]}
    out["vsfetch_layout_lengths"] = layout
    pairs = [("vsfetch_stride_32", "vsfetch_stride_64"),
             ("vsfetch_offset_0", "vsfetch_offset_16"),
             ("vsfetch_step_vertex", "vsfetch_step_instance"),
             ("vsfetch_instance_rate1", "vsfetch_instance_rate2")]
    pair_diffs = {}
    for a, b in pairs:
        ha = recs[a]["gated"]["vertex_hex"]
        hb = recs[b]["gated"]["vertex_hex"]
        pair_diffs[f"{a}_vs_{b}"] = {"identical_bytes": ha == hb, "len_a": len(ha)//2, "len_b": len(hb)//2}
    out["vsfetch_layout_pair_diffs"] = pair_diffs

    # ---- fsin_interp family: are all 7 qualifiers byte-distinct? ----------
    interp_ids = ["fsin_interp_persp", "fsin_interp_nopersp", "fsin_interp_centroid_p",
                  "fsin_interp_centroid_np", "fsin_interp_sample_p", "fsin_interp_sample_np",
                  "fsin_interp_flat"]
    interp_hex = {cid: recs[cid]["gated"]["fragment_hex"] for cid in interp_ids}
    distinct = len(set(interp_hex.values()))
    out["fsin_interp"] = {
        "n_variants": len(interp_ids), "n_byte_distinct_variants": distinct,
        "lengths": {cid: len(h)//2 for cid, h in interp_hex.items()},
        "flat_shorter_than_persp": len(interp_hex["fsin_interp_flat"]) < len(interp_hex["fsin_interp_persp"]),
    }

    # ---- pull-model vs qualifier-form comparison ---------------------------
    pull_ids = ["fsin_pull_center", "fsin_pull_centroid", "fsin_pull_sample", "fsin_pull_offset"]
    out["fsin_pullmodel_lengths"] = {cid: recs[cid]["gated"]["fragment_hex_len"] for cid in pull_ids}

    # ---- structural region names: constant_program / no third segment -----
    struct_check = {}
    for cid in ["vsfetch_format_float4", "cs_preamble_with_constant", "cs_preamble_no_constant"]:
        struct_check[cid] = recs[cid]["gated"]["structure"]["region_names"]
    out["structural_regions"] = struct_check

    # ---- stencil / depth / vsfetch HW-PROBE summary (already JSON, just excerpt)
    for cid in ["stencil_hw_sval5", "stencil_hw_sval9", "stencil_hw_control_mrt1",
                "depth_hw_any_250", "depth_hw_any_750", "depth_hw_less_250", "depth_hw_greater_250",
                "vsfetch_hw_inrange", "vsfetch_hw_oob", "vsfetch_hw_instancing_base",
                "vsfetch_hw_oob_large_base", "frontfacing_hw", "cstgmem_hw_sweep"]:
        out.setdefault("hw_probe_excerpts", {})[cid] = recs[cid]["gated"].get("result", recs[cid]["gated"])

    # ---- negative control ---------------------------------------------------
    out["negative_control"] = recs["fsout_bogus_negative_control"]["gated"]
    out["stencil_positive"] = recs["fsout_stencil_struct"]["gated"]["status"]

    (HERE / "analysis" / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps({k: (v if not isinstance(v, dict) else "...") for k, v in out.items()}, indent=2))


if __name__ == "__main__":
    main()

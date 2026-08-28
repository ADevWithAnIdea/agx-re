#!/usr/bin/env python3
"""EXP-0117 post-capture analysis. Reads raw/<run>/04_results.jsonl (no new
GPU calls), computes host oracles for every family, and reports PASS/FAIL
per case plus a summary. Blend-factor/operation formulas are STANDARD,
publicly documented GPU blend-equation math (identical across OpenGL/
Vulkan/D3D/Metal specs) -- PUBLIC knowledge, not learned from any Apple
binary.

Usage: python3 analysis/decode.py [raw/m4-20260828-run01]
"""
import json, struct, sys, math
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def load(run_dir):
    recs = {}
    for line in (run_dir / "04_results.jsonl").read_text().splitlines():
        r = json.loads(line)
        recs[r["id"]] = r
    return recs


def hex_to_floats(h):
    b = bytes.fromhex(h)
    n = len(b) // 4
    return list(struct.unpack("<%df" % n, b[:4 * n]))


# ---------------------------------------------------------------- blend math
SRC = (0.7, 0.4, 0.2, 0.9)
DST = (0.3, 0.6, 0.8, 0.1)
CONST = (0.25, 0.75, 0.5, 0.6)
SRC1 = (0.5, 0.6, 0.7, 0.8)


def factor_rgb(fid, src, dst, const, src1):
    """Returns (fr,fg,fb) for a given MTLBlendFactor id in the RGB role."""
    if fid == 0: return (0.0, 0.0, 0.0)
    if fid == 1: return (1.0, 1.0, 1.0)
    if fid == 2: return src[:3]
    if fid == 3: return tuple(1 - c for c in src[:3])
    if fid == 4: return (src[3],) * 3
    if fid == 5: return (1 - src[3],) * 3
    if fid == 6: return dst[:3]
    if fid == 7: return tuple(1 - c for c in dst[:3])
    if fid == 8: return (dst[3],) * 3
    if fid == 9: return (1 - dst[3],) * 3
    if fid == 10:
        f = min(src[3], 1 - dst[3]); return (f, f, f)
    if fid == 11: return const[:3]
    if fid == 12: return tuple(1 - c for c in const[:3])
    if fid == 13: return (const[3],) * 3
    if fid == 14: return (1 - const[3],) * 3
    if fid == 15: return src1[:3]
    if fid == 16: return tuple(1 - c for c in src1[:3])
    if fid == 17: return (src1[3],) * 3
    if fid == 18: return (1 - src1[3],) * 3
    raise ValueError(f"unhandled rgb factor id {fid}")


def factor_alpha(fid, src, dst, const, src1):
    if fid == 0: return 0.0
    if fid == 1: return 1.0
    if fid == 2: return src[3]
    if fid == 3: return 1 - src[3]
    if fid == 4: return src[3]
    if fid == 5: return 1 - src[3]
    if fid == 6: return dst[3]
    if fid == 7: return 1 - dst[3]
    if fid == 8: return dst[3]
    if fid == 9: return 1 - dst[3]
    if fid == 10: return 1.0  # SourceAlphaSaturated is ALWAYS 1 for the alpha role
    if fid == 11: return const[3]
    if fid == 12: return 1 - const[3]
    if fid == 13: return const[3]
    if fid == 14: return 1 - const[3]
    if fid == 15: return src1[3]
    if fid == 16: return 1 - src1[3]
    if fid == 17: return src1[3]
    if fid == 18: return 1 - src1[3]
    raise ValueError(f"unhandled alpha factor id {fid}")


def blend_op(op, s, d):
    if op == 0: return s + d
    if op == 1: return s - d
    if op == 2: return d - s
    if op == 3: return min(s, d)
    if op == 4: return max(s, d)
    raise ValueError(f"unhandled op {op}")


def approx(a, b, tol=1e-3):
    return abs(a - b) <= tol


def check_blend_factor(recs, out):
    FACTOR_NAMES = {
        0: "Zero", 1: "One", 2: "SourceColor", 3: "OneMinusSourceColor", 4: "SourceAlpha",
        5: "OneMinusSourceAlpha", 6: "DestinationColor", 7: "OneMinusDestinationColor",
        8: "DestinationAlpha", 9: "OneMinusDestinationAlpha", 10: "SourceAlphaSaturated",
        11: "BlendColor", 12: "OneMinusBlendColor", 13: "BlendAlpha", 14: "OneMinusBlendAlpha",
        15: "Source1Color", 16: "OneMinusSource1Color", 17: "Source1Alpha", 18: "OneMinusSource1Alpha",
    }
    rows = []
    for fid, name in FACTOR_NAMES.items():
        cid = f"blendfac_src_{name}"
        rec = recs.get(cid)
        if not rec or rec["gated"]["status"] != "OK":
            rows.append({"id": cid, "status": "MISSING_OR_NOT_OK"}); continue
        hexs = rec["gated"]["result"]["center_hex"]
        vals = hex_to_floats(hexs)
        s1 = SRC1 if fid in (15, 16, 17, 18) else SRC
        fr, fg, fb = factor_rgb(fid, SRC, DST, CONST, SRC1)
        fa = factor_alpha(fid, SRC, DST, CONST, SRC1)
        # blendfac_src_* cases: dst factor = Zero, op = Add -> result = src*factor
        pred = (SRC[0] * fr, SRC[1] * fg, SRC[2] * fb, SRC[3] * fa)
        ok = all(approx(a, b) for a, b in zip(vals, pred))
        rows.append({"id": cid, "factor": fid, "predicted": pred, "observed": vals, "match": ok})
    name_to_id = {v: k for k, v in FACTOR_NAMES.items()}
    for name in ("Zero", "One", "SourceColor", "DestinationColor"):
        fid = name_to_id[name]
        cid = f"blendfac_dst_{name}"
        rec = recs.get(cid)
        if not rec or rec["gated"]["status"] != "OK":
            rows.append({"id": cid, "status": "MISSING_OR_NOT_OK"}); continue
        vals = hex_to_floats(rec["gated"]["result"]["center_hex"])
        fr, fg, fb = factor_rgb(fid, SRC, DST, CONST, SRC1)
        fa = factor_alpha(fid, SRC, DST, CONST, SRC1)
        pred = (DST[0] * fr, DST[1] * fg, DST[2] * fb, DST[3] * fa)
        ok = all(approx(a, b) for a, b in zip(vals, pred))
        rows.append({"id": cid, "factor": fid, "role": "dst", "predicted": pred, "observed": vals, "match": ok})
    out["blend_factor"] = rows
    return rows


def check_blend_op(recs, out):
    OPS = {"Add": 0, "Subtract": 1, "ReverseSubtract": 2, "Min": 3, "Max": 4}
    rows = []
    for name, op in OPS.items():
        cid = f"blendop_{name}"
        rec = recs.get(cid)
        vals = hex_to_floats(rec["gated"]["result"]["center_hex"])
        pred = tuple(blend_op(op, SRC[i], DST[i]) for i in range(4))
        ok = all(approx(a, b) for a, b in zip(vals, pred))
        rows.append({"id": cid, "op": op, "predicted": pred, "observed": vals, "match": ok})
    out["blend_op"] = rows
    return rows


def check_unspecialized(recs, out):
    rows = []
    # factor=19 as src role -> should behave as One -> result == SRC
    rec = recs["blendfac_src_Unspecialized19"]
    vals = hex_to_floats(rec["gated"]["result"]["center_hex"])
    rows.append({"id": "blendfac_src_Unspecialized19", "predicted_as_One": SRC,
                 "observed": vals, "match_One": all(approx(a, b) for a, b in zip(vals, SRC))})
    # factor=19 as dst role (src factor=One) -> should behave as Zero -> result == SRC (dst contributes 0)
    rec = recs["blendfac_dst_Unspecialized19"]
    vals = hex_to_floats(rec["gated"]["result"]["center_hex"])
    rows.append({"id": "blendfac_dst_Unspecialized19", "predicted_as_Zero_dst": SRC,
                 "observed": vals, "match_Zero": all(approx(a, b) for a, b in zip(vals, SRC))})
    # op=5 -> should behave as Add
    rec = recs["blendop_Unspecialized5"]
    vals = hex_to_floats(rec["gated"]["result"]["center_hex"])
    pred = tuple(blend_op(0, SRC[i], DST[i]) for i in range(4))
    rows.append({"id": "blendop_Unspecialized5", "predicted_as_Add": pred, "observed": vals,
                 "match_Add": all(approx(a, b) for a, b in zip(vals, pred))})
    out["unspecialized"] = rows
    return rows


def check_stencil_overflow(recs, out):
    rows = []
    for v in (0, 1, 127, 254, 255, 256, 257, 511, 65535, 4294967295):
        cid = f"stencilover_u32_{v}"
        rec = recs[cid]["gated"]["result"]
        pred_trunc = v & 0xFF
        pred_clamp = min(v, 255)
        obs = rec["observed"]
        rows.append({"id": cid, "requested": v, "observed": obs, "pred_truncate": pred_trunc,
                     "pred_clamp": pred_clamp, "matches_truncate": obs == pred_trunc,
                     "matches_clamp": obs == pred_clamp})
    for v in (255, 300):
        cid = f"stencilover_u16_{v}"
        rec = recs[cid]["gated"]["result"]
        pred_trunc = v & 0xFF
        obs = rec["observed"]
        rows.append({"id": cid, "requested": v, "observed": obs, "pred_truncate": pred_trunc,
                     "matches_truncate": obs == pred_trunc})
    out["stencil_overflow"] = rows
    return rows


def check_samplemask(recs, out):
    rows = []
    for prefix, N, masks in (
        ("samplemask_n4_", 4, (0x0, 0x1, 0x3, 0x7, 0xF, 0x10, 0xFFFFFFFF)),
        ("samplemask_n2_", 2, (0x0, 0x1, 0x3, 0x4, 0xFFFFFFFF)),
        ("samplemask_n1_", 1, (0x0, 0x1)),
    ):
        for m in masks:
            cid = f"{prefix}{m:#x}"
            rec = recs[cid]["gated"]["result"]
            pop = bin(m & ((1 << N) - 1)).count("1")
            pred = pop / N
            obs = rec["resolved"][0]
            rows.append({"id": cid, "N": N, "mask": m, "predicted_fraction": pred,
                         "observed": obs, "match": approx(obs, pred, 0.01)})
    out["sample_mask"] = rows
    return rows


def check_logic(recs, out):
    ops = {
        "and_a": lambda s, d: s & d, "and_identity": lambda s, d: s & d,
        "or_a": lambda s, d: s | d, "xor_a": lambda s, d: s ^ d,
        "xor_selfcancel": lambda s, d: s ^ d, "inv_zero": lambda s, d: (~d) & 0xFFFFFFFF,
        "inv_allones": lambda s, d: (~d) & 0xFFFFFFFF, "copy_ignores_dst": lambda s, d: s,
    }
    rows = []
    for name, fn in ops.items():
        cid = f"logic_{name}"
        rec = recs[cid]["gated"]["result"]
        s, d = rec["src"], rec["dst"]
        pred = fn(s, d) & 0xFFFFFFFF
        rows.append({"id": cid, "src": s, "dst": d, "predicted": pred, "observed": rec["result"],
                     "match": pred == rec["result"]})
    out["logic_epilog"] = rows
    return rows


def check_calldepth(recs, out):
    rows = []
    for d in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128):
        cid = f"calldepth_{d}"
        rec = recs[cid]["gated"]["result"]
        vals = rec["values"]
        pred = [float(i + d) for i in range(4)]
        ok = vals == pred
        rows.append({"id": cid, "depth": d, "predicted": pred, "observed": vals, "match": ok})
    out["call_depth"] = rows
    return rows


def check_call_abi(recs, out):
    rows = []
    for cid in ("callabi_k_single", "callabi_k_twosame", "callabi_k_twodiff",
                "callabi_k_threecalls", "callabi_k_far", "callabi_k_nested_midfn"):
        rec = recs[cid]["gated"]
        calls = rec.get("calls", [])
        rows.append({"id": cid, "n_calls": len(calls),
                     "byte6_values": sorted(set(c["byte6"] for c in calls)),
                     "byte5_values": [c["byte5"] for c in calls],
                     "off40_values": [c["off40"] for c in calls]})
    all_byte6 = set()
    for r in rows:
        all_byte6 |= set(r["byte6_values"])
    out["call_abi"] = {"rows": rows, "all_byte6_values_seen": sorted(all_byte6),
                        "uniform_0x54": all_byte6 == {0x54}}
    return rows


def check_msaadiff(recs, out):
    rec = recs["msaadiff_n4"]["gated"]["result"]
    recs_ = rec["records"]
    centroids = set(round(r["vcentroid"], 6) for r in recs_)
    samples = [r["vsample"] for r in recs_]
    out["msaa_diff"] = {
        "records": recs_,
        "centroid_uniform_across_invocations": len(centroids) == 1,
        "sample_values_distinct": len(set(round(s, 6) for s in samples)) == len(samples),
    }


def check_bary(recs, out):
    rec = recs["bary_values"]["gated"]["result"]
    b = rec["raw"]
    manual = rec["manual"]
    tags = (10.0, 20.0, 30.0)
    bsum = sum(b)
    manual_pred = sum(bi * t for bi, t in zip(b, tags))

    # Host oracle: independent geometric computation from the SAME known
    # triangle (screen position independent of w; only interpolation math
    # differs between linear and perspective-correct).
    W = H = 64
    p = [(-0.6, -0.6), (0.6, -0.6), (0.0, 0.6)]
    w = [1.0, 2.0, 4.0]
    # Sample point: center texel (32,32) -> continuous window coords (32.5, 32.5).
    px, py = 32.5, 32.5
    ndc_x = (px / W) * 2 - 1
    ndc_y = 1 - (py / H) * 2  # y-down window -> NDC y (FS-03 convention)

    def screen_bary(qx, qy, tri):
        (x0, y0), (x1, y1), (x2, y2) = tri
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        l0 = ((y1 - y2) * (qx - x2) + (x2 - x1) * (qy - y2)) / d
        l1 = ((y2 - y0) * (qx - x2) + (x0 - x2) * (qy - y2)) / d
        l2 = 1 - l0 - l1
        return (l0, l1, l2)

    lin = screen_bary(ndc_x, ndc_y, p)
    persp_num = [lin[i] / w[i] for i in range(3)]
    s = sum(persp_num)
    persp = tuple(x / s for x in persp_num)

    manual_linear = sum(li * t for li, t in zip(lin, tags))
    manual_persp = sum(pi * t for pi, t in zip(persp, tags))

    out["bary"] = {
        "observed_raw": b, "observed_manual": manual, "sum_b": bsum,
        "sum_is_one": approx(bsum, 1.0, 1e-3),
        "host_linear_bary": lin, "host_perspective_bary": persp,
        "manual_pred_from_observed_b": manual_pred,
        "manual_matches_own_b": approx(manual, manual_pred, 1e-2),
        "host_linear_manual": manual_linear, "host_perspective_manual": manual_persp,
        "matches_linear_model": approx(manual, manual_linear, 0.05),
        "matches_perspective_model": approx(manual, manual_persp, 0.05),
        "b_matches_linear_model": all(approx(a, b_, 0.01) for a, b_ in zip(b, lin)),
        "b_matches_perspective_model": all(approx(a, b_, 0.01) for a, b_ in zip(b, persp)),
    }


def check_pid(recs, out):
    rows = {}
    for cid in ("pid_nonindexed", "pid_indexed_shuffled", "pid_instanced"):
        rows[cid] = recs[cid]["gated"]["result"]["records"]
    out["bary_pid"] = rows


def check_blend_struct(recs, out):
    rows = {}
    for cid in ("blendstruct_off", "blendstruct_on_srconly", "blendstruct_on_dstonly", "blendstruct_on_both"):
        g = recs[cid]["gated"]
        h = g.get("fragment_hex") or ""
        rows[cid] = {"len": len(h) // 2, "has_tile_read": g.get("has_tile_read")}
    rows["off_equals_srconly"] = (
        recs["blendstruct_off"]["gated"]["fragment_hex"] == recs["blendstruct_on_srconly"]["gated"]["fragment_hex"]
    )
    out["blend_struct"] = rows


def check_fsorder(recs, out):
    ab = recs["fsorder_struct_ab"]["gated"]["fragment_hex"]
    ba = recs["fsorder_struct_ba"]["gated"]["fragment_hex"]
    cmp_ = recs["fsorder_render_cmp"]["gated"]["result"]["results"]
    kr = recs["fsorder_suppress_keep_replace"]["gated"]["result"]
    rk = recs["fsorder_suppress_replace_keep"]["gated"]["result"]
    out["fsorder"] = {
        "struct_byte_identical": ab == ba,
        "render_cmp_identical": cmp_[0] == cmp_[1],
        "suppress_keep_replace": kr,
        "suppress_replace_keep": rk,
        "op_selection_tracks_assignment": (
            kr["left_stencil"] == 222 and kr["right_stencil"] == 77 and
            rk["left_stencil"] == 77 and rk["right_stencil"] == 222
        ),
    }


def main():
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "raw" / "m4-20260828-run01"
    recs = load(run_dir)
    out = {"run_dir": str(run_dir)}
    check_blend_factor(recs, out)
    check_blend_op(recs, out)
    check_unspecialized(recs, out)
    check_stencil_overflow(recs, out)
    check_samplemask(recs, out)
    check_logic(recs, out)
    check_calldepth(recs, out)
    check_call_abi(recs, out)
    check_msaadiff(recs, out)
    check_bary(recs, out)
    check_pid(recs, out)
    check_blend_struct(recs, out)
    check_fsorder(recs, out)

    outpath = HERE / "analysis" / "summary.json"
    outpath.write_text(json.dumps(out, indent=2, default=str))
    # Print concise pass/fail digest.
    def digest(rows, key="match"):
        if isinstance(rows, list):
            n = len(rows); ok = sum(1 for r in rows if r.get(key))
            return f"{ok}/{n}"
        return "n/a"
    print("blend_factor:", digest(out["blend_factor"]))
    print("blend_op:", digest(out["blend_op"]))
    print("stencil_overflow (truncate model):", digest(out["stencil_overflow"], "matches_truncate"))
    print("sample_mask:", digest(out["sample_mask"]))
    print("logic_epilog:", digest(out["logic_epilog"]))
    print("call_depth:", digest(out["call_depth"]))
    print("call_abi uniform byte6==0x54:", out["call_abi"]["uniform_0x54"], out["call_abi"]["all_byte6_values_seen"])
    print("msaa centroid uniform / sample distinct:",
          out["msaa_diff"]["centroid_uniform_across_invocations"], out["msaa_diff"]["sample_values_distinct"])
    print("bary sum==1:", out["bary"]["sum_is_one"],
          " matches_linear:", out["bary"]["matches_linear_model"],
          " matches_perspective:", out["bary"]["matches_perspective_model"],
          " b_matches_linear:", out["bary"]["b_matches_linear_model"],
          " b_matches_perspective:", out["bary"]["b_matches_perspective_model"])
    print("blend_struct off==srconly (no tile_read either):", out["blend_struct"]["off_equals_srconly"])
    print("fsorder struct byte-identical:", out["fsorder"]["struct_byte_identical"],
          " render identical:", out["fsorder"]["render_cmp_identical"],
          " op-selection tracks assignment:", out["fsorder"]["op_selection_tracks_assignment"])
    print("wrote", outpath)


if __name__ == "__main__":
    main()

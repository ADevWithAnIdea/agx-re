#!/usr/bin/env python3
"""EXP-0129 analysis: turns the OFFICIAL raw captures into the discriminating
report cited in RESULTS.md. No new GPU calls -- pure post-hoc arithmetic on
the committed raw/ JSONL. Run: python3 analysis/decode.py [run_dir]
(default: raw/m4-20260828-run01)."""
import json, sys, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def load(run_dir):
    recs = [json.loads(l) for l in (EXP / run_dir / "04_results.jsonl").read_text().splitlines() if l.strip()]
    return {r["id"]: r for r in recs}


def approx(a, b, tol):
    return abs(a - b) <= tol * max(1.0, abs(b))


# ---- H1: host oracle models -------------------------------------------
def screen_bary(qx, qy, tri):
    (x0, y0), (x1, y1), (x2, y2) = tri
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    l0 = ((y1 - y2) * (qx - x2) + (x2 - x1) * (qy - y2)) / d
    l1 = ((y2 - y0) * (qx - x2) + (x0 - x2) * (qy - y2)) / d
    l2 = 1 - l0 - l1
    return (l0, l1, l2)


SAMPLE_PX = (32.5, 32.5)  # 64x64 target, center texel -- both configs
W = H = 64
NDC_X = (SAMPLE_PX[0] / W) * 2 - 1
NDC_Y = 1 - (SAMPLE_PX[1] / H) * 2

CONFIG1 = {"p": [(-0.6, -0.6), (0.6, -0.6), (0.0, 0.6)], "w": [1.0, 2.0, 4.0], "tags": (10.0, 20.0, 30.0)}
CONFIG2 = {"p": [(-0.5, -0.3), (0.55, -0.2), (0.0925, 0.6975)], "w": [1.0, 3.0, 2.5], "tags": (100.0, -50.0, 7.0)}


def models(cfg):
    lin = screen_bary(NDC_X, NDC_Y, cfg["p"])
    w = cfg["w"]
    numer = [lin[i] / w[i] for i in range(3)]
    s = sum(numer)
    persp = tuple(x / s for x in numer)
    # Model B: "raw perspective numerator for slots 0,1; slot 2 derived as
    # the sum-to-one complement" -- the mechanism this experiment attributes
    # to the baseline (no-position) compiled form (2 `iter` ops only, no
    # `fspecial`/W-denominator).
    modelB = (numer[0], numer[1], 1.0 - numer[0] - numer[1])
    # Model C: fully-normalized perspective-correct (the standard graphics
    # convention) -- attributed to the position-consuming compiled form.
    modelC = persp
    return {"lin": lin, "numer": numer, "s": s, "modelB": modelB, "modelC": modelC}


def check_h1(recs, out):
    variants = ["base", "pos3", "count3_const", "count3_vary", "pos2", "posread_noout", "attach3ctrl", "base2", "pos3_2"]
    render = {}
    for v in variants:
        g = recs[f"baryrender_{v}"]["gated"]
        r = g["result"]
        render[v] = {"c0": r["c0"], "c1": r["c1"], "c2": r["c2"], "natt": r["natt"]}

    struct = {}
    for v in variants:
        g = recs[f"barystruct_{v}"]["gated"]
        d = g["disasm"]
        struct[v] = {"n_iter": len(d["iters"]), "iters": d["iters"], "n_fspecial": d["n_fspecial"],
                     "fragment_hex_len": g["fragment_hex_len"]}

    m1 = models(CONFIG1)
    m2 = models(CONFIG2)

    def b_of(v):
        return tuple(render[v]["c0"][:3])

    base_b = b_of("base")
    pos3_b = b_of("pos3")

    discrimination = {
        "count_alone_triggers": not approx(sum(abs(a - b) for a, b in zip(b_of("count3_const"), base_b)), 0, 1e-6),
        "any_extra_interpolant_triggers": not approx(sum(abs(a - b) for a, b in zip(b_of("count3_vary"), base_b)), 0, 1e-6),
        "position_output_at_count2_triggers": not approx(sum(abs(a - b) for a, b in zip(b_of("pos2"), base_b)), 0, 1e-6),
        "position_readonly_noout_triggers": not approx(sum(abs(a - b) for a, b in zip(b_of("posread_noout"), base_b)), 0, 1e-6),
        "harness_attach3_alone_triggers": not approx(sum(abs(a - b) for a, b in zip(b_of("attach3ctrl"), base_b)), 0, 1e-6),
        "pos3_matches_pos2": all(approx(a, b, 1e-4) for a, b in zip(b_of("pos3"), b_of("pos2"))),
        "pos3_matches_posread_noout": all(approx(a, b, 1e-4) for a, b in zip(b_of("pos3"), b_of("posread_noout"))),
    }

    cfg1_fit = {
        "base_matches_modelB": all(approx(a, b, 5e-4) for a, b in zip(base_b, m1["modelB"])),
        "base_matches_modelC": all(approx(a, b, 5e-4) for a, b in zip(base_b, m1["modelC"])),
        "pos3_matches_modelB": all(approx(a, b, 5e-4) for a, b in zip(pos3_b, m1["modelB"])),
        "pos3_matches_modelC": all(approx(a, b, 5e-4) for a, b in zip(pos3_b, m1["modelC"])),
    }
    base2_b = b_of("base2")
    pos3_2_b = b_of("pos3_2")
    cfg2_fit = {
        "base2_matches_modelB": all(approx(a, b, 1e-2) for a, b in zip(base2_b, m2["modelB"])),
        "base2_matches_modelC": all(approx(a, b, 1e-2) for a, b in zip(base2_b, m2["modelC"])),
        "pos3_2_matches_modelB": all(approx(a, b, 1e-2) for a, b in zip(pos3_2_b, m2["modelB"])),
        "pos3_2_matches_modelC": all(approx(a, b, 1e-2) for a, b in zip(pos3_2_b, m2["modelC"])),
    }

    out["h1"] = {
        "render": render, "struct": struct,
        "config1_models": m1, "config2_models": m2,
        "discrimination": discrimination,
        "config1_fit": cfg1_fit, "config2_fit": cfg2_fit,
    }


# ---- H2 --------------------------------------------------------------
def check_h2(recs, out):
    negctrl_s = recs["negctrl_struct"]["gated"]
    negctrl_r = recs["negctrl_render"]["gated"]["result"]
    epilog_s = recs["epilog_struct"]["gated"]
    epilog_r0 = recs["epilog_render_mode0"]["gated"]["result"]
    epilog_r1 = recs["epilog_render_mode1"]["gated"]["result"]
    prolog_s = recs["prolog_struct"]["gated"]
    prolog_r = recs["prolog_render"]["gated"]["result"]
    callret_s = recs["callret_struct"]["gated"]
    callret_r = recs["callret_render"]["gated"]["result"]

    def blend_add(src, sf, dst, df):
        return [s * f1 + d * f2 for s, f1, d, f2 in zip(src, sf, dst, df)]

    def blend_mul(src, sf, dst, df):
        return [(s * f1) * (d * f2) for s, f1, d, f2 in zip(src, sf, dst, df)]

    exp0 = blend_add(epilog_r0["src"], epilog_r0["srcFactor"], epilog_r0["dst"], epilog_r0["dstFactor"])
    exp1 = blend_mul(epilog_r1["src"], epilog_r1["srcFactor"], epilog_r1["dst"], epilog_r1["dstFactor"])
    epilog_check = {
        "mode0_add_matches": all(approx(a, b, 1e-3) for a, b in zip(epilog_r0["result"], exp0)),
        "mode1_mul_matches": all(approx(a, b, 1e-3) for a, b in zip(epilog_r1["result"], exp1)),
        "expected_mode0": exp0, "expected_mode1": exp1,
    }

    prolog_recs = prolog_r["records"]
    prolog_check = []
    for rec in prolog_recs:
        vid = rec["vid"]
        attr = rec["attr"]
        if vid < 6:
            expected = [((vid * 40 + k) & 0xFF) / 255.0 for k in range(4)]
        else:
            expected = [0.0, 0.0, 0.0, 0.0]
        ok = all(approx(a, b, 1e-4) for a, b in zip(attr, expected))
        prolog_check.append({"vid": vid, "attr": attr, "expected": expected, "match": ok})

    callret_ins = callret_r["in"]
    callret_outs = callret_r["out"]
    callret_check = []
    for base, out4 in zip(callret_ins, callret_outs):
        r1 = [base + (base + 1), (base + 1) + (base + 2), (base + 2) + (base + 3), (base + 3) + (base + 4)]
        b2 = base * 2.0
        r2 = [b2 + (b2 + 1), (b2 + 1) + (b2 + 2), (b2 + 2) + (b2 + 3), (b2 + 3) + (b2 + 4)]
        expected = [a + b for a, b in zip(r1, r2)]
        ok = all(approx(a, b, 1e-3) for a, b in zip(out4, expected))
        callret_check.append({"base": base, "out": out4, "expected": expected, "match": ok})

    out["h2"] = {
        "negctrl": {"struct_status": negctrl_s["status"], "render": negctrl_r,
                    "value_forwards_correctly": all(approx(a, b, 1e-4) for a, b in zip(negctrl_r["clear"], negctrl_r["result"]))},
        "epilog": {"region_names": epilog_s["structure"]["region_names"],
                   "n_call": epilog_s["disasm"]["n_call"], "check": epilog_check},
        "prolog": {"region_names": prolog_s["structure"]["region_names"],
                   "n_call": prolog_s["disasm"]["n_call"], "records": prolog_check},
        "callret": {"region_names": callret_s["structure"]["region_names"],
                    "callee_symbol": callret_s["callee_symbol"],
                    "caller_n_call": callret_s["caller_disasm"]["n_call"],
                    "callee_n_instr": callret_s["callee_disasm"]["n_instr"],
                    "records": callret_check},
    }


def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "raw/m4-20260828-run01"
    recs = load(run_dir)
    out = {"run_dir": run_dir}
    check_h1(recs, out)
    check_h2(recs, out)
    (HERE / "summary.json").write_text(json.dumps(out, indent=2))
    d = out["h1"]["discrimination"]
    print("H1 discrimination:", json.dumps(d, indent=2))
    print("H1 config1 fit:", json.dumps(out["h1"]["config1_fit"], indent=2))
    print("H1 config2 fit:", json.dumps(out["h1"]["config2_fit"], indent=2))
    print("H2 epilog check:", json.dumps(out["h2"]["epilog"]["check"], indent=2))
    print("H2 prolog all match:", all(r["match"] for r in out["h2"]["prolog"]["records"]))
    print("H2 callret all match:", all(r["match"] for r in out["h2"]["callret"]["records"]))
    print("H2 negctrl forwards:", out["h2"]["negctrl"]["value_forwards_correctly"])


if __name__ == "__main__":
    main()

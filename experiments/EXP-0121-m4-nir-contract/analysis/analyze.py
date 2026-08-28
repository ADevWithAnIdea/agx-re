#!/usr/bin/env python3
"""EXP-0121 analysis: reads raw/<run>/01_results.jsonl + 01_detail.jsonl and produces
a structured per-item report (analysis/report.json) plus prints a human-readable
summary. Compares observed values against harness/oracle.py, structurally
tokenizes captured main_hex/frag_hex via tools/agx-isa (READ-ONLY), and classifies
concurrency verdicts across PAIRS/repeats.
"""
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(EXP.parent.parent / "tools" / "agx-isa"))
import oracle as O  # noqa: E402
import casematrix as CM  # noqa: E402
import isadb  # noqa: E402


def load_jsonl(p):
    out = {}
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


def tok(hexstr):
    if not hexstr:
        return None, None
    b = bytes.fromhex(hexstr)
    insns, leftover = isadb.disassemble(b)
    return insns, leftover


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else "m4-20260828T000000Z-run01"
    run_dir = EXP / "raw" / run
    results = load_jsonl(run_dir / "01_results.jsonl")
    detail = load_jsonl(run_dir / "01_detail.jsonl")
    cases = {c["id"]: c for c in CM.build_cases()}

    report = {}

    # ---------------- OPT-01 ----------------
    div_ids = ["opt01_plain_relaxed", "opt01_plain_precise", "opt01_fastns_precise", "opt01_precisens_precise"]
    div_report = {}
    for cid in div_ids:
        r, d = results[cid], detail[cid]
        insns, leftover = tok(d["main_hex"])
        mnem_counts = dict(Counter(i["mnemonic"] for i in insns)) if insns else None
        div_report[cid] = {
            "main_len": r["main_len"], "mnemonics": mnem_counts, "leftover_len": len(leftover) if leftover else 0,
            "observed_sample": d["observed"][:6],
        }
    # numeric compare relaxed vs precise
    corpus = CM.DIV_CORPUS
    obs_relaxed = detail["opt01_plain_relaxed"]["observed"]
    obs_precise = detail["opt01_plain_precise"]["observed"]
    obs_fastns = detail["opt01_fastns_precise"]["observed"]
    obs_precisens = detail["opt01_precisens_precise"]["observed"]
    n = len(corpus)
    ref_daz_ftz = [O.div_daz_ftz(a, b) for a, b in corpus]

    def bits_eq(observed_f, ref_bits):
        try:
            ob = O.f32_bits(observed_f)
        except OverflowError:
            return False
        if O.is_nan_bits(ob) and O.is_nan_bits(ref_bits):
            return True
        return ob == ref_bits

    precise_vs_ref = sum(bits_eq(obs_precise[i], ref_daz_ftz[i]) for i in range(n))
    precisens_vs_ref = sum(bits_eq(obs_precisens[i], ref_daz_ftz[i]) for i in range(n))
    relaxed_vs_precise_diff = sum(1 for i in range(n) if not bits_eq(obs_relaxed[i], O.f32_bits(obs_precise[i]) if obs_precise[i] == obs_precise[i] or True else 0))
    # simpler: count bit-exact agreement relaxed vs precise (NaN-aware)
    def bits_eq2(a_f, b_f):
        try:
            ab, bb = O.f32_bits(a_f), O.f32_bits(b_f)
        except OverflowError:
            return a_f != a_f and b_f != b_f
        if O.is_nan_bits(ab) and O.is_nan_bits(bb):
            return True
        return ab == bb
    relaxed_eq_precise = sum(bits_eq2(obs_relaxed[i], obs_precise[i]) for i in range(n))
    fastns_eq_relaxed = sum(bits_eq2(obs_fastns[i], obs_relaxed[i]) for i in range(n))
    precisens_eq_precise = sum(bits_eq2(obs_precisens[i], obs_precise[i]) for i in range(n))

    report["OPT-01"] = {
        "structural": div_report,
        "n_corpus": n,
        "precise_vs_daz_ftz_oracle": f"{precise_vs_ref}/{n}",
        "precisens_vs_daz_ftz_oracle": f"{precisens_vs_ref}/{n}",
        "relaxed_bit_identical_to_precise": f"{relaxed_eq_precise}/{n}",
        "fastns_bit_identical_to_relaxed": f"{fastns_eq_relaxed}/{n}",
        "precisens_bit_identical_to_precise": f"{precisens_eq_precise}/{n}",
    }

    # ---------------- OPT-03 ----------------
    pb = detail["opt03_pow_builtin"]["observed"]
    pm = detail["opt03_pow_manual"]["observed"]
    corpus3 = CM.POW_CORPUS
    n3 = len(corpus3)
    diffs = []
    for i in range(n3):
        a, b = pb[i], pm[i]
        same = (a != a and b != b) or a == b
        if not same:
            diffs.append({"i": i, "x": corpus3[i][0], "y": corpus3[i][1], "builtin": a, "manual": b})
    r_b = results["opt03_pow_builtin"]
    r_m = results["opt03_pow_manual"]
    report["OPT-03"] = {
        "builtin_main_len": r_b["main_len"], "manual_main_len": r_m["main_len"],
        "n_corpus": n3, "n_diffs_builtin_vs_manual": len(diffs),
        "diffs_sample": diffs[:20],
    }

    # ---------------- OPT-04 ----------------
    ldx = detail["opt04_ldexp_dynamic"]["observed"]
    corpus4 = CM.LDEXP_CORPUS
    n4 = len(corpus4)
    ref4 = [O.ldexp_oracle_bits(xb, nn) for xb, nn in corpus4]
    def eq4(i):
        try:
            ob = O.f32_bits(ldx[i])
        except OverflowError:
            return O.is_nan_bits(ref4[i])
        if O.is_nan_bits(ob) and O.is_nan_bits(ref4[i]):
            return True
        return ob == ref4[i]
    matches4 = sum(1 for i in range(n4) if eq4(i))
    mism4 = []
    for i in range(n4):
        if not eq4(i):
            try:
                ob = O.f32_bits(ldx[i])
            except OverflowError:
                ob = None
            mism4.append({"i": i, "x_bits": hex(corpus4[i][0]), "n": corpus4[i][1],
                          "observed": ldx[i], "observed_bits": hex(ob) if ob is not None else None,
                          "ref_bits": hex(ref4[i])})
    insns4, leftover4 = tok(detail["opt04_ldexp_dynamic"]["main_hex"])
    insns4c, leftover4c = tok(detail["opt04_ldexp_const3"]["main_hex"])
    report["OPT-04"] = {
        "n_corpus": n4, "matches": f"{matches4}/{n4}",
        "mismatches_sample": mism4[:20],
        "dynamic_mnemonics": dict(Counter(i["mnemonic"] for i in insns4)) if insns4 else None,
        "dynamic_has_fldexp": any(i["mnemonic"] == "fldexp" for i in insns4) if insns4 else None,
        "const3_mnemonics": dict(Counter(i["mnemonic"] for i in insns4c)) if insns4c else None,
        "const3_has_fldexp": any(i["mnemonic"] == "fldexp" for i in insns4c) if insns4c else None,
    }

    # ---------------- OPT-05/06 ----------------
    sel_report = {}
    for typ in ["f32", "i32", "u32"]:
        for cond in CM.SELECT_CONDS:
            cid = f"opt0506_sel_{typ}_{cond}"
            c = cases[cid]
            obs = detail[cid]["observed"]
            pairs = c["sel_pairs"]
            A, B = c["sel_A"], c["sel_B"]
            oracle_fn = {"f32": O.select_f32, "i32": O.select_i32, "u32": O.select_u32}[typ]
            matches = 0
            mism = []
            for i, (ca, cb) in enumerate(pairs):
                exp = oracle_fn(A, B, ca, cb, cond)
                got = obs[i]
                ok = (exp != exp and got != got) if typ == "f32" else (exp == got)
                if typ == "f32" and not (exp != exp):
                    ok = (exp == got) or (exp != exp and got != got)
                if ok:
                    matches += 1
                elif len(mism) < 10:
                    mism.append({"i": i, "ca": ca, "cb": cb, "expected": exp, "observed": got})
            insns, leftover = tok(detail[cid]["main_hex"])
            mn = [i["mnemonic"] for i in insns] if insns else None
            isel_insns = [i for i in insns if "isel" in i["mnemonic"] or i["mnemonic"] in ("icmp_pred", "sel")] if insns else []
            sel_report[cid] = {
                "matches": f"{matches}/{len(pairs)}", "mismatches": mism,
                "main_len": results[cid]["main_len"], "mnemonics": mn,
                "fused_single_isel": len(isel_insns) == 1 and insns and "isel" in isel_insns[0]["mnemonic"] if isel_insns else False,
                "isel_fields": isel_insns[0]["fields"] if isel_insns else None,
            }
    report["OPT-05/06"] = sel_report

    # ---------------- OPT-07 ----------------
    r7 = results["opt07_dynin_8way"]
    d7 = detail["opt07_dynin_8way"]
    r7s = results["opt07_staticidx_8"]
    d7s = detail["opt07_staticidx_8"]
    buf7 = d7["buffers"].get("0")
    import struct
    vals7 = [struct.unpack('<f', bytes.fromhex(buf7[i*8:i*8+8]))[0] for i in range(8)] if buf7 else None
    insns7, _ = tok(d7["frag_hex"])
    iter_slots = [i["fields"].get("src_slot") for i in insns7 if i["mnemonic"] in ("iter", "iter_flat")] if insns7 else None
    report["OPT-07"] = {
        "dynamic_readback": vals7, "expected": [200 + i for i in range(8)],
        "frag_len": r7["frag_len"], "static_frag_len": r7s["frag_len"],
        "iter_src_slot_values": iter_slots,
        "iter_mnemonic_counts": dict(Counter(i["mnemonic"] for i in insns7)) if insns7 else None,
    }

    # ---------------- OPT-08 ----------------
    def rt_pixels(cid, rtcount):
        d = detail[cid]
        px = {}
        for p in d["pixels"]:
            px.setdefault(int(p["rt"]), {})[int(p["x"])] = p["bgra"]
        return px
    px2 = rt_pixels("opt08_dynout_2way", 2)
    px3 = rt_pixels("opt08_dynout_3way", 3)
    insns2, _ = tok(detail["opt08_dynout_2way"]["frag_hex"])
    insns3, _ = tok(detail["opt08_dynout_3way"]["frag_hex"])
    def store_info(insns):
        stores = [i for i in insns if i["mnemonic"] == "frag_color_store"]
        setups = [i["fields"] for i in insns if i["mnemonic"] == "frag_tile_setup"]
        return {"n_stores": len(stores), "store_fields": [s["fields"] for s in stores], "tile_setups": setups}
    report["OPT-08"] = {
        "pixels_2way": px2, "pixels_3way": px3,
        "frag_len_2way": results["opt08_dynout_2way"]["frag_len"],
        "frag_len_3way": results["opt08_dynout_3way"]["frag_len"],
        "pipeline_source_2way": results["opt08_dynout_2way"]["pipeline_source"],
        "pipeline_source_3way": results["opt08_dynout_3way"]["pipeline_source"],
        "structural_2way": store_info(insns2) if insns2 else None,
        "structural_3way": store_info(insns3) if insns3 else None,
    }

    # ---------------- OPT-10/11 ----------------
    conc = defaultdict(lambda: defaultdict(dict))
    for cid, r in results.items():
        if r.get("kind") != "concurrency":
            continue
        fn = r["function"]
        pairs = r["pairs"]
        rep = r["repeat"]
        conc[fn][pairs][rep] = {"verdict": r["verdict"], "detail": detail[cid]}
    conc_summary = {}
    for fn, bypairs in conc.items():
        conc_summary[fn] = {}
        for pairs, byrep in bypairs.items():
            verdicts = [v["verdict"] for v in byrep.values()]
            details = [v["detail"] for v in byrep.values()]
            conc_summary[fn][pairs] = {"verdicts": verdicts, "raw": details}
    report["OPT-10/11"] = conc_summary

    out_path = HERE / f"report_{run}.json"
    out_path.write_text(json.dumps(report, indent=1, default=str))
    print(f"wrote {out_path}")

    # human summary
    print("\n=== OPT-01 ===")
    print(json.dumps(report["OPT-01"], indent=1, default=str)[:2000])
    print("\n=== OPT-03 ===")
    print("n_diffs builtin vs manual:", report["OPT-03"]["n_diffs_builtin_vs_manual"], "/", report["OPT-03"]["n_corpus"])
    print("main_len builtin/manual:", report["OPT-03"]["builtin_main_len"], report["OPT-03"]["manual_main_len"])
    print("\n=== OPT-04 ===")
    print("matches:", report["OPT-04"]["matches"], "has_fldexp(dynamic):", report["OPT-04"]["dynamic_has_fldexp"])
    print("\n=== OPT-05/06 summary ===")
    for cid, v in sel_report.items():
        print(cid, v["matches"], "fused:", v["fused_single_isel"])
    print("\n=== OPT-07 ===")
    print(report["OPT-07"]["dynamic_readback"], "expected", report["OPT-07"]["expected"])
    print("iter src_slot values:", report["OPT-07"]["iter_src_slot_values"])
    print("\n=== OPT-08 ===")
    print("2way stores:", report["OPT-08"]["structural_2way"]["n_stores"] if report["OPT-08"]["structural_2way"] else None)
    print("3way stores:", report["OPT-08"]["structural_3way"]["n_stores"] if report["OPT-08"]["structural_3way"] else None)
    print("\n=== OPT-10/11 summary ===")
    for fn, bypairs in conc_summary.items():
        line = fn + ": "
        for pairs, v in sorted(bypairs.items()):
            line += f"p{pairs}={v['verdicts']} "
        print(line)


if __name__ == "__main__":
    main()

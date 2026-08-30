#!/usr/bin/env python3
"""EXP-0161: quantify the SFU precision drop that fspecial byte+8 bit0 causes.

run01/run02's `roundmode` sweep splits exactly in half: even values reproduce
the refined result, odd values reproduce something ~1% off. This measures how
far off, in mantissa bits, and compares it with EXP-0026's measured
`fspecial_est` seed (~7.5-8 good mantissa bits) -- i.e. it asks whether byte+8
bit0 selects the SAME estimate datapath the precise lowering seeds from.

No GPU time; analysis of raw/g17p_20260829_run0*/sweep.jsonl only.
"""
from __future__ import print_function
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import cases as CM  # noqa

F = CM.F_IN
REF = {"D_FSPEC_INPLACE": [1.0 / math.sqrt(x) for x in F],
       "D2_FSPEC_LOG2": [math.log2(x) for x in F]}

out = {}
for nm in ("g17p_20260829_run01", "g17p_20260829_run02"):
    p = EXP / "raw" / nm / "sweep.jsonl"
    if not p.exists():
        continue
    for l in open(str(p)):
        r = json.loads(l)
        if r["arm"] not in REF or r["field"] != "roundmode":
            continue
        o = r.get("observed") or {}
        if not o.get("out"):
            continue
        got = [float(x) for x in o["out"]]
        ref = REF[r["arm"]]
        key = (r["arm"], "odd" if r["value"] & 1 else "even")
        d = out.setdefault(key, {"n": 0, "max_rel": 0.0, "min_rel": 1.0,
                                 "n_all_nan": 0, "n_any_nan": 0})
        d["n"] += 1
        if all(g != g for g in got):
            d["n_all_nan"] += 1
            continue
        if any(g != g for g in got):
            d["n_any_nan"] += 1
        rel = [abs(g - w) / abs(w) for g, w in zip(got, ref)
               if w != 0 and g == g]
        if not rel:
            continue
        mx = max(rel)
        d["max_rel"] = max(d["max_rel"], mx)
        d["min_rel"] = min(d["min_rel"], mx)

doc = {}
for (arm, par), d in sorted(out.items()):
    bits = (-math.log2(d["max_rel"])) if d["max_rel"] > 0 else float("inf")
    doc["%s.byte8_bit0_%s" % (arm, par)] = {
        "cases": d["n"], "all_nan_cases": d["n_all_nan"],
        "partial_nan_cases": d["n_any_nan"],
        "max_rel_err": d["max_rel"], "min_rel_err": d["min_rel"],
        "good_mantissa_bits_worst_case": (None if bits == float("inf")
                                          else round(bits, 2))}
    print("%-30s n=%-4d all_nan=%-4d max_rel=%.3e  good bits >= %s"
          % ("%s %s" % (arm, par), d["n"], d["n_all_nan"], d["max_rel"],
             "n/a" if d["n_all_nan"] == d["n"] else
             ("inf" if bits == float("inf") else round(bits, 2))))
(EXP / "analysis" / "sfu_precision.json").write_text(json.dumps(
    {"_meta": {"inputs": F,
               "reference": "host math.sqrt / math.log2 in double, rounded to the "
                            "comparison; 'good bits' = -log2(max relative error)",
               "compare_with": "EXP-0026 measured the fspecial_est seed at ~7.5-8 "
                               "good mantissa bits (rcp 8.0, rsqrt 7.9, sqrt 7.5)"},
     "measurements": doc}, indent=1, sort_keys=True))

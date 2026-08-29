#!/usr/bin/env python3
"""EXP-0138: re-check the DERIVED models in `annotate.py` against every raw case.

  analysis/model_check.py raw/<run> [raw/<run> ...]

A model that was fitted to the data is worth nothing until it is scored against
ALL of it. This prints, per run, how many cases each model reproduces exactly.

CLEAN-ROOM: analysis of this experiment's own raw JSON only.
"""
import json, sys, collections
from pathlib import Path

SEED = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
        8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0}
# uniform-register contents observed in kernels/carrier_uni.metal. 6..9 are the
# bound `constant float4&`; index 10 is the carrier's OWN literal, so it is a
# property of this carrier, not of the hardware, and is marked as such.
UNI = {6: 101.0, 7: 202.0, 8: 303.0, 9: 404.0, 10: 1.0}
CARRIER_SPECIFIC = {10}


def minifloat(k):
    """AGX 6-bit inline float immediate, established here by hardware sweep."""
    e, m = k >> 3, k & 7
    return m * 2 ** -5 if e == 0 else (8 + m) * 2.0 ** (e - 6)


def srcB(idx, cls):
    if cls == 0:
        return SEED.get(idx % 64, 0.0)
    if cls == 1:
        return minifloat(idx - 64) if idx >= 64 else UNI.get(idx, 0.0)
    return 0.0                                    # classes 2 and 3 read as zero


def falu2_modlo(sa, sb, op, v):
    a = 0.0 if (v & 1) else SEED.get(sa, 0.0)
    b = srcB(sb, (v >> 1) & 3)
    return a + b if op == 4 else a * b


def check(run):
    rs = [json.loads(l) for l in open(Path(run) / "sweep.jsonl")]
    sel = [r for r in rs if r["instr"] == "falu2" and r["field"] == "mod_lo"]
    hit = miss = 0
    for r in sel:
        n, w = r["note"], r["observed"]["w0"]
        if n.startswith("H-MODLO"):
            sa = int(n.split("srcA_reg=")[1].split()[0])
            sb = int(n.split("srcB_reg=")[1].split()[0])
            op = int(n.split("opsel=")[1])
            p = falu2_modlo(sa, sb, op, r["value"])
        elif n.startswith("uniform-file"):
            p = falu2_modlo(0, int(n.split("=")[-1]), 4, 2)
        else:
            p = falu2_modlo(0, 2, 4, 2)
        ok = w is not None and abs(w - p) <= 1e-5 * max(1.0, abs(p))
        hit += ok
        miss += not ok
        if not ok:
            print("   MISS", n, "v=", r["value"], "obs", w, "model", p)
    print("%-28s falu2.mod_lo model: %d/%d exact" % (Path(run).name, hit, hit + miss))
    return miss


if __name__ == "__main__":
    bad = sum(check(a) for a in sys.argv[1:])
    print("minifloat table:", {k: minifloat(k) for k in (0, 2, 3, 31, 32, 48, 56, 61, 62, 63)})
    print("carrier-specific uniform indices (NOT hardware facts):", sorted(CARRIER_SPECIFIC))
    sys.exit(1 if bad else 0)

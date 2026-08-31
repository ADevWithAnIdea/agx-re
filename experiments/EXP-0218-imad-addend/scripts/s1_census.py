#!/usr/bin/env python3
"""EXP-0218 step 1 — CO-VARIATION CENSUS: for every byte position, does the
recovered ADDEND move at all?

Two independent recovery routes, so no population depends on a single model:

  C-G17P route 1 (model-free, byte+7 only): when byte+7's mode bits are 1 or 2
      the product is dropped, so the destination IS the addend.  No product
      model is used.
  C-G17P route 2: A = destination - SEED[b5>>2]*SEED[b6>>3] (step 0 re-derived
      this map: 126/126 and 290/290 on the two multiplicand sweeps).
  C-M4   route 3 (model-free): lanes 5 (a=0, b=32) and 7 (a=0x7FFFFFFF, b=0)
      have a ZERO product under low-32, unsigned-high and signed-high multiply
      alike, so their output word IS the addend whatever multiply variant the
      swept byte selects.  This is the route that cannot be fooled by a byte
      that changes the PRODUCT rather than the addend.
  C-M4   route 4: the full 8-lane residual against a library of candidate
      multiply variants, used to say WHICH thing a byte changed.
"""
from __future__ import annotations
import sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G  # 0xDEADBEEF
from lib0218 import (cases_g17p, cases_m4, SEEDS, ANCHOR_G17P, ANCHOR_M4,
                     swept_byte, dump, M32, A_IN, B_IN)

ANG = bytes.fromhex(ANCHOR_G17P)
ANM = bytes.fromhex(ANCHOR_M4)
ZERO_PRODUCT_LANES = [5, 7]     # a*b == 0 under low32, mulhi_u and mulhi_s


def s32(u):
    return u - (1 << 32) if u & 0x80000000 else u


OPS = {
    "low32":   lambda a, b: (a * b) & M32,
    "mulhi_u": lambda a, b: (a * b) >> 32,
    "mulhi_s": lambda a, b: ((s32(a) * s32(b)) >> 32) & M32,
    "zero":    lambda a, b: 0,
    "a":       lambda a, b: a,
    "b":       lambda a, b: b,
    "a_plus_b": lambda a, b: (a + b) & M32,
}


# --------------------------------------------------------------- C-G17P ------
def g17p_census():
    pops = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    stats = defaultdict(Counter)
    for c in cases_g17p():
        raw = c["raw"]
        sb = swept_byte(raw, ANCHOR_G17P)
        key = "byte" + ",".join(map(str, sb)) if sb else "anchor"
        if c["excl"]:
            stats[key][c["excl"]] += 1
            continue
        dst = raw[3] >> 1
        if dst > 15:
            stats[key]["dst_outside_dump"] += 1
            continue
        got = c["regs"][dst]
        if got == POISON_G:
            stats[key]["destination_still_poison"] += 1
            continue
        seeds = SEEDS[c["sset"]]
        i5, i6 = raw[5] >> 2, raw[6] >> 3
        m = raw[7] & 3
        if m == 0:
            if i5 > 15 or i6 > 15:
                stats[key]["multiplicand_out_of_seed_table"] += 1
                continue
            P = (seeds[i5] * (0 if raw[6] & 1 else seeds[i6])) & M32
            A = (got - P) & M32
            route = "route2_minus_product"
        elif m in (1, 2):
            A = got
            route = "route1_product_dropped"
        else:
            stats[key]["mode3_reserved"] += 1
            continue
        stats[key]["scored"] += 1
        bval = raw[sb[0]] if len(sb) == 1 else tuple(raw[i] for i in sb)
        pops[key][c["sset"]][bval][A] += 1
        pops[key][c["sset"]]["__route__"][route] += 1
    return pops, stats


# ----------------------------------------------------------------- C-M4 ------
def m4_census():
    pops = defaultdict(lambda: defaultdict(Counter))
    ops = defaultdict(Counter)
    stats = defaultdict(Counter)
    for c in cases_m4():
        raw = c["raw"]
        sb = swept_byte(raw, ANCHOR_M4)
        key = "byte" + ",".join(map(str, sb)) if sb else "anchor"
        if c["excl"]:
            stats[key][c["excl"]] += 1
            continue
        w = c["words"]
        stats[key]["scored"] += 1
        bval = raw[sb[0]] if len(sb) == 1 else tuple(raw[i] for i in sb)
        # route 3: model-free addend from the zero-product lanes
        z = set(w[i] for i in ZERO_PRODUCT_LANES)
        pops[key][bval][("zeroLaneA", tuple(sorted(z)))] += 1
        # route 4: which multiply variant (if any) explains all 8 lanes
        best = None
        for name, f in OPS.items():
            res = set((w[i] - f(A_IN[i], B_IN[i])) & M32 for i in range(8))
            if len(res) == 1:
                best = (name, res.pop())
                break
        ops[key][best if best else ("unmodelled", None)] += 1
    return pops, ops, stats


def main():
    out = {}
    gp, gstat = g17p_census()
    grows = []
    for key in sorted(gp):
        for ss in sorted(k for k in gp[key] if isinstance(k, int)):
            tab = {b: dict(v) for b, v in gp[key][ss].items() if b != "__route__"}
            allA = set()
            multi = 0
            for b, v in tab.items():
                allA |= set(v)
                if len(v) > 1:
                    multi += 1
            grows.append({
                "population": key, "sset": ss,
                "n_byte_values": len(tab),
                "n_scored": sum(sum(v.values()) for v in tab.values()),
                "distinct_addends": len(allA),
                "byte_values_with_more_than_one_addend": multi,
                "addend_set": sorted(allA)[:40],
                "routes": dict(gp[key][ss]["__route__"]),
                "excluded": dict(gstat[key]),
            })
    out["C_G17P"] = grows
    mp, mops, mstat = m4_census()
    mrows = []
    for key in sorted(mp):
        allA = set()
        multi = 0
        for b, v in mp[key].items():
            for (tag, z) in v:
                allA.add(z)
            if len(set(z for (tag, z) in v)) > 1:
                multi += 1
        mrows.append({
            "population": key,
            "n_byte_values": len(mp[key]),
            "n_scored": sum(sum(v.values()) for v in mp[key].values()),
            "distinct_zero_lane_addends": len(allA),
            "zero_lane_addend_set": sorted(allA, key=str)[:40],
            "byte_values_with_more_than_one": multi,
            "eight_lane_op_fit": {str(k): v for k, v in mops[key].most_common(8)},
            "excluded": dict(mstat[key]),
        })
    out["C_M4"] = mrows
    dump(out, "s1_census.json")

    print("=== C-G17P (A18 Pro / G17P) ===")
    print(f"{'population':12s} {'ss':>2s} {'bytevals':>8s} {'scored':>7s} "
          f"{'distinctA':>9s} {'bvals>1A':>8s}  addends")
    for r in grows:
        print(f"{r['population']:12s} {r['sset']:2d} {r['n_byte_values']:8d} "
              f"{r['n_scored']:7d} {r['distinct_addends']:9d} "
              f"{r['byte_values_with_more_than_one_addend']:8d}  "
              f"{r['addend_set'][:12]}")
    print()
    print("=== C-M4 (M4 / G16G), zero-product lanes 5 & 7 ===")
    for r in mrows:
        print(f"{r['population']:12s} bytevals={r['n_byte_values']:4d} "
              f"scored={r['n_scored']:5d} distinctA={r['distinct_zero_lane_addends']:4d} "
              f"bvals>1={r['byte_values_with_more_than_one']:4d}")
        print(f"             A set: {r['zero_lane_addend_set'][:14]}")
        print(f"             8-lane op fit: {r['eight_lane_op_fit']}")


if __name__ == "__main__":
    main()

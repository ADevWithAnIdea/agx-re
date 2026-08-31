#!/usr/bin/env python3
"""EXP-0218 step 3 (the five discriminators) + the focused decisive tables.

(a) C-M4 byte+7 sweep, literal mode: is A == K over all 32 K?
(b) C-M4 byte+8 sweep, restricted to the documented low-32 mulsel high nibble:
    is A == K | (b8&7)<<5?
(c)/(d) byte+9 bit roles on BOTH carriers -- the literal/fetch selector.
(e) discriminator b: GPR seed set 1 vs 2 (C-G17P, same target, same carrier).
(f) discriminator c: per-lane spread (C-M4) -- scalar vs per-lane addend.
(g) discriminator d: process launch run01 vs run02 (C-M4, same target/carrier).
(h) discriminator a: the SAME byte value in the two carriers.
(i) Group III: every M-REG-bN(>>k) scored, so a register model cannot be
    dismissed by assertion.
"""
from __future__ import annotations
import sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G
from lib0218 import (cases_g17p, cases_m4, SEEDS, ANCHOR_G17P, ANCHOR_M4,
                     swept_byte, dump, M32, A_IN, B_IN)
from s3_models import K, mode, imm8, litsel, SLOT_G17P, PROD_M4

ANG = bytes.fromhex(ANCHOR_G17P)
ANM = bytes.fromhex(ANCHOR_M4)
OUT = {}


def m4_addend(c):
    """(A, scalar?) from the 8 lanes; None if no constant addend explains them."""
    w = c["words"]
    base = PROD_M4 if mode(c["raw"]) == 0 else [0] * 8
    res = set((w[i] - base[i]) & M32 for i in range(8))
    return (res.pop(), True) if len(res) == 1 else (None, False)


# ---- (a) C-M4 byte+7: A vs K -------------------------------------------------
def a_m4_byte7():
    t = defaultdict(Counter)
    n = hit = 0
    misses = []
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_M4) != (7,) or mode(raw) == 3:
            continue
        A, ok = m4_addend(c)
        n += 1
        t[K(raw)][A] += 1
        if ok and A == K(raw):
            hit += 1
        elif len(misses) < 5:
            misses.append({"hex": c["hex"], "K": K(raw), "A": A,
                           "words": c["words"], "src": c["src"]})
    return {"n_scored": n, "A_equals_K": hit,
            "distinct_K_covered": len(t),
            "per_K": {str(k): {str(a): m for a, m in v.items()}
                      for k, v in sorted(t.items())},
            "misses": misses}


# ---- (b) C-M4 byte+8 within the low-32 mulsel high nibble --------------------
def b_m4_byte8():
    rows = {}
    for hi in (0xc0, 0xd0, 0xe0, 0xf0, 0x00):
        t = defaultdict(Counter)
        n = hit = 0
        for c in cases_m4():
            raw = c["raw"]
            if c["excl"] or swept_byte(raw, ANCHOR_M4) not in ((8,), ()):
                continue
            if (raw[8] & 0xF0) != hi or mode(raw) == 3:
                continue
            A, ok = m4_addend(c)
            n += 1
            t[raw[8] & 0x0F][A] += 1
            if ok and A == imm8(raw):
                hit += 1
        rows[hex(hi)] = {"n_scored": n, "A_equals_imm8": hit,
                         "per_low_nibble": {str(k): {str(a): m for a, m in v.items()}
                                            for k, v in sorted(t.items())}}
    return rows


# ---- (c)/(d) byte+9 bit roles ------------------------------------------------
def c_byte9_m4():
    per = defaultdict(Counter)
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_M4) not in ((9,), ()) or mode(raw) == 3:
            continue
        A, ok = m4_addend(c)
        per[raw[9]][A if ok else ("nonconstant", tuple(c["words"]))] += 1
    # collapse to bit roles over the region where the instruction computes at all
    bits = defaultdict(lambda: defaultdict(Counter))
    for v, cnt in per.items():
        for i in range(8):
            for A, m in cnt.items():
                bits[i][(v >> i) & 1][A] += m
    return {"per_value": {str(v): {str(a): m for a, m in cnt.items()}
                          for v, cnt in sorted(per.items())},
            "per_bit": {str(i): {str(b): {str(a): m for a, m in cc.items()}
                                 for b, cc in d.items()} for i, d in bits.items()}}


def d_byte9_g17p():
    per = defaultdict(lambda: defaultdict(Counter))
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_G17P) not in ((9,), ()) or mode(raw) == 3:
            continue
        dst = raw[3] >> 1
        got = c["regs"][dst]
        if got == POISON_G:
            continue
        s = SEEDS[c["sset"]]
        P = (s[raw[5] >> 2] * (0 if raw[6] & 1 else s[raw[6] >> 3])) & M32
        A = (got - (P if mode(raw) == 0 else 0)) & M32
        per[raw[9]][c["sset"]][A] += 1
    return {str(v): {str(ss): {str(a): m for a, m in cc.items()}
                     for ss, cc in d.items()} for v, d in sorted(per.items())}


# ---- (e) seed-set independence ----------------------------------------------
def e_seedsets():
    by = defaultdict(lambda: defaultdict(Counter))
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3:
            continue
        dst = raw[3] >> 1
        if dst > 15:
            continue
        got = c["regs"][dst]
        if got == POISON_G:
            continue
        i5, i6 = raw[5] >> 2, raw[6] >> 3
        if i5 > 15 or i6 > 15:
            continue
        s = SEEDS[c["sset"]]
        P = (s[i5] * (0 if raw[6] & 1 else s[i6])) & M32
        A = (got - (P if mode(raw) == 0 else 0)) & M32
        by[c["hex"]][c["sset"]][A] += 1
    same = diff = onlyone = 0
    diffs = []
    for h, d in by.items():
        if len(d) < 2:
            onlyone += 1
            continue
        a1, a2 = set(d[1]), set(d[2])
        if a1 == a2:
            same += 1
        else:
            diff += 1
            if len(diffs) < 8:
                diffs.append({"hex": h, "sset1": sorted(a1), "sset2": sorted(a2)})
    return {"encodings_run_under_both_seed_sets": same + diff,
            "same_addend_under_both": same,
            "different_addend_under_both": diff,
            "encodings_with_only_one_seed_set": onlyone,
            "examples_of_difference": diffs}


# ---- (f) per-lane spread on C-M4 --------------------------------------------
def f_lanes():
    scalar = nonconst = 0
    ex = []
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3:
            continue
        if swept_byte(raw, ANCHOR_M4) not in ((7,), (8,), (9,), (11,), (1,), ()):
            continue
        A, ok = m4_addend(c)
        if ok:
            scalar += 1
        else:
            nonconst += 1
            if len(ex) < 6:
                ex.append({"hex": c["hex"], "words": c["words"], "src": c["src"]})
    return {"cases": scalar + nonconst, "one_addend_explains_all_8_lanes": scalar,
            "no_single_addend": nonconst, "examples": ex}


# ---- (g) launch stability on C-M4 -------------------------------------------
def g_launch():
    by = defaultdict(lambda: defaultdict(Counter))
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3:
            continue
        A, ok = m4_addend(c)
        by[c["hex"]][c["run"]][A if ok else "nonconstant"] += 1
    same = diff = 0
    diffs = []
    for h, d in by.items():
        runs = [r for r in d if r.startswith("m4_20260828_run")]
        if len(runs) < 2:
            continue
        if set(d[runs[0]]) == set(d[runs[1]]):
            same += 1
        else:
            diff += 1
            if len(diffs) < 8:
                diffs.append({"hex": h, runs[0]: list(d[runs[0]]),
                              runs[1]: list(d[runs[1]])})
    return {"encodings_in_both_launches": same + diff, "same_addend": same,
            "different_addend": diff, "examples": diffs}


# ---- (h) same byte value, two carriers --------------------------------------
def h_cross():
    g = defaultdict(Counter)
    m = defaultdict(Counter)
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_G17P) != (7,) or mode(raw) == 3:
            continue
        dst = raw[3] >> 1
        got = c["regs"][dst]
        if got == POISON_G:
            continue
        s = SEEDS[c["sset"]]
        P = (s[raw[5] >> 2] * (0 if raw[6] & 1 else s[raw[6] >> 3])) & M32
        g[K(raw)][(got - (P if mode(raw) == 0 else 0)) & M32] += 1
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_M4) != (7,) or mode(raw) == 3:
            continue
        A, ok = m4_addend(c)
        m[K(raw)][A if ok else "nonconstant"] += 1
    rows = []
    agree = 0
    for k in sorted(set(g) | set(m)):
        gv = sorted(g[k]) if k in g else None
        mv = sorted(m[k], key=str) if k in m else None
        if gv and mv and set(gv) == set(mv):
            agree += 1
        rows.append({"K": k, "C_G17P_addend": gv, "C_M4_addend": mv})
    return {"K_values_in_both": sum(1 for r in rows
                                    if r["C_G17P_addend"] and r["C_M4_addend"]),
            "K_values_where_the_two_carriers_agree": agree, "table": rows}


# ---- (i) Group III, every register model ------------------------------------
def i_regmodels():
    tot = defaultdict(lambda: [0, 0])
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3:
            continue
        dst = raw[3] >> 1
        if dst > 15:
            continue
        got = c["regs"][dst]
        if got == POISON_G:
            continue
        i5, i6 = raw[5] >> 2, raw[6] >> 3
        if i5 > 15 or i6 > 15:
            continue
        s = SEEDS[c["sset"]]
        P = (s[i5] * (0 if raw[6] & 1 else s[i6])) & M32
        base = P if mode(raw) == 0 else 0
        for n in range(3, 12):
            for k in range(5):
                nm = f"M-REG-b{n}(>>{k})"
                tot[nm][1] += 1
                if ((base + s[(raw[n] >> k) & 0xF]) & M32) == got:
                    tot[nm][0] += 1
    return {k: {"hit": v[0], "scored": v[1]} for k, v in sorted(tot.items())}


if __name__ == "__main__":
    OUT["a_C_M4_byte7_A_equals_K"] = a_m4_byte7()
    OUT["b_C_M4_byte8_immediate_high_bits"] = b_m4_byte8()
    OUT["c_C_M4_byte9_bit_roles"] = c_byte9_m4()
    OUT["d_C_G17P_byte9"] = d_byte9_g17p()
    OUT["e_seed_set_independence_C_G17P"] = e_seedsets()
    OUT["f_per_lane_spread_C_M4"] = f_lanes()
    OUT["g_process_launch_stability_C_M4"] = g_launch()
    OUT["h_same_K_two_carriers"] = h_cross()
    OUT["i_group_III_register_models_C_G17P"] = i_regmodels()
    dump(OUT, "s4_discriminators.json")

    a = OUT["a_C_M4_byte7_A_equals_K"]
    print(f"(a) C-M4 byte+7: A == K in {a['A_equals_K']}/{a['n_scored']} cases, "
          f"{a['distinct_K_covered']}/32 K values covered")
    for m in a["misses"]:
        print("     miss:", m)
    print("(b) C-M4 byte+8 by mulsel high nibble:")
    for hi, r in OUT["b_C_M4_byte8_immediate_high_bits"].items():
        print(f"     {hi}: A == imm8 in {r['A_equals_imm8']}/{r['n_scored']}")
    print("(e) seed-set independence (C-G17P):", OUT["e_seed_set_independence_C_G17P"]
          | {"examples_of_difference": "..."} if False else
          {k: v for k, v in OUT["e_seed_set_independence_C_G17P"].items()
           if k != "examples_of_difference"})
    print("(f) per-lane (C-M4):", {k: v for k, v in OUT["f_per_lane_spread_C_M4"].items()
                                   if k != "examples"})
    print("(g) launch stability (C-M4):",
          {k: v for k, v in OUT["g_process_launch_stability_C_M4"].items()
           if k != "examples"})
    print("(h) same K, two carriers:",
          {k: v for k, v in OUT["h_same_K_two_carriers"].items() if k != "table"})
    print("(i) best Group III register models (C-G17P):")
    for k, v in sorted(OUT["i_group_III_register_models_C_G17P"].items(),
                       key=lambda kv: -kv[1]["hit"])[:6]:
        print(f"     {k:22s} {v['hit']}/{v['scored']}")

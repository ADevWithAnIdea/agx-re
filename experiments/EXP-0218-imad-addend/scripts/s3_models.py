#!/usr/bin/env python3
"""EXP-0218 steps 3-4 — score EVERY pre-registered addend model over the whole
committed `imad` population, with exact numerators and denominators.

Prediction target is the DESTINATION, not a recovered addend, so a model cannot
be scored against a quantity that was derived using it:

    dest_pred = (b7&3 == 0 ? PRODUCT : 0) + A_model

PRODUCT on C-G17P is SEED[b5>>2] * SEED[b6>>3] (byte+6 bit0 forces 0), the map
step 0 re-derived at 126/126 and 290/290.  PRODUCT on C-M4 is the per-lane
A_IN[i]*B_IN[i]; a C-M4 case is a hit only if ALL EIGHT lanes match.

FIT vs HELD OUT.  Exactly one model has a fitted parameter: the external-slot
table SLOT[K].  It is fitted ONLY on EXP-0160 run01, seed set 1, byte+7 sweep,
and every other population is a held-out prediction.  The literal model
A = ((b8 & 7) << 5) | ((b7 >> 3) & 0x1F) has NO fitted parameter at all.
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
PROD_M4 = [(a * b) & M32 for a, b in zip(A_IN, B_IN)]


def K(raw):
    return (raw[7] >> 3) & 0x1F


def mode(raw):
    return raw[7] & 3


def imm8(raw):
    return (((raw[8] & 7) << 5) | K(raw)) & M32


def imm9_dbjson(raw):
    """db.json's own historical claim: K in b7[3:8] + mulsel[0:3]."""
    return ((((raw[8] & 0xF) << 5) | K(raw))) & M32


def litsel(raw):
    """byte+9 bit 3 == 0 -> the addend is the literal; 1 -> external fetch."""
    return ((raw[9] >> 3) & 1) == 0


# ---------------------------------------------------------------- fit SLOT ---
def fit_slot_table():
    """SLOT[K] from EXP-0160 run01 / seed set 1 / byte+7 sweep ONLY."""
    obs = defaultdict(Counter)
    for c in cases_g17p():
        if c["exp"] != "EXP-0160-g17p-last-field" or c["run"] != "g17p_20260830_run01":
            continue
        if c["excl"] or c["sset"] != 1:
            continue
        raw = c["raw"]
        if swept_byte(raw, ANCHOR_G17P) != (7,):
            continue
        if mode(raw) == 3:
            continue
        dst = raw[3] >> 1
        got = c["regs"][dst]
        if got == POISON_G:          # destination never written -> not an addend
            continue
        seeds = SEEDS[1]
        P = (seeds[raw[5] >> 2] * (0 if raw[6] & 1 else seeds[raw[6] >> 3])) & M32
        A = (got - (P if mode(raw) == 0 else 0)) & M32
        obs[K(raw)][A] += 1
    tab, amb = {}, {}
    for k, cnt in obs.items():
        if len(cnt) == 1:
            tab[k] = next(iter(cnt))
        else:
            top = cnt.most_common()
            tab[k] = top[0][0]
            amb[k] = dict(cnt)
    return tab, amb, {k: sum(v.values()) for k, v in obs.items()}


SLOT_G17P, SLOT_AMBIG, SLOT_N = fit_slot_table()
# C-M4's slot table is measurable only at K=7 (its anchor byte+7 is fixed in the
# only population that reaches slot mode), and only for the 16-bit form.
SLOT_M4 = {7: 0}


# ----------------------------------------------------------------- models ----
def models_for(raw, seeds, slot):
    """name -> addend, or None when the model is out of domain for this case."""
    m = {}
    m["U  literal|slot, sel = b9 bit3"] = (
        imm8(raw) if litsel(raw) else slot.get(K(raw)))
    m["M-IMM-IMM8  A = (b8&7)<<5 | b7>>3"] = imm8(raw)
    m["M-IMM-K  A = b7>>3"] = K(raw)
    m["M-IMM-K9  db.json (b8&0xF)<<5|K"] = imm9_dbjson(raw)
    m["M-IMM-K8  A = b7"] = raw[7]
    m["M-NONE-EXT(K)  A = SLOT[K]"] = slot.get(K(raw))
    m["M-NONE-FIXED  A = anchor addend"] = (
        slot.get(K(bytes.fromhex(ANCHOR_G17P))) if slot is SLOT_G17P else 7)
    for n in (9, 10, 11, 4, 3):
        m[f"M-IMM-B{n}  A = b{n}"] = raw[n]
    if seeds is not None:
        for n in (3, 4, 5, 6, 7, 8, 9, 10, 11):
            for k in (0, 1, 2, 3, 4):
                idx = (raw[n] >> k) & 0xF
                m[f"M-REG-b{n}(>>{k})  A = SEED[(b{n}>>{k})&15]"] = seeds[idx]
    return m


# ------------------------------------------------------------------ score ----
def score_g17p():
    res = defaultdict(lambda: defaultdict(lambda: {"n": 0, "hit": 0,
                                                   "oob": 0, "miss": []}))
    excl = defaultdict(Counter)
    for c in cases_g17p():
        raw = c["raw"]
        sb = swept_byte(raw, ANCHOR_G17P)
        pop = "byte" + ",".join(map(str, sb)) if sb else "anchor"
        held = not (c["exp"] == "EXP-0160-g17p-last-field"
                    and c["run"] == "g17p_20260830_run01"
                    and c["sset"] == 1 and sb == (7,))
        pop += "  [FIT]" if not held else ""
        if c["excl"]:
            excl[pop][c["excl"]] += 1
            continue
        if mode(raw) == 3:
            excl[pop]["b7_mode3_reserved"] += 1
            continue
        dst = raw[3] >> 1
        if dst > 15:
            excl[pop]["dst_outside_16reg_dump"] += 1
            continue
        i5, i6 = raw[5] >> 2, raw[6] >> 3
        if i5 > 15 or i6 > 15:
            excl[pop]["multiplicand_out_of_seed_table"] += 1
            continue
        seeds = SEEDS[c["sset"]]
        P = (seeds[i5] * (0 if raw[6] & 1 else seeds[i6])) & M32
        got = c["regs"][dst]
        if got == POISON_G:          # destination never written -> not an addend
            excl[pop]["destination_still_poison"] += 1
            continue
        base = P if mode(raw) == 0 else 0
        for name, A in models_for(raw, seeds, SLOT_G17P).items():
            S = res[pop][name]
            if A is None:
                S["oob"] += 1
                continue
            S["n"] += 1
            if ((base + A) & M32) == got:
                S["hit"] += 1
            elif len(S["miss"]) < 3:
                S["miss"].append({"hex": c["hex"], "sset": c["sset"],
                                  "pred": (base + A) & M32, "got": got,
                                  "src": c["src"]})
    return res, excl


def score_m4():
    res = defaultdict(lambda: defaultdict(lambda: {"n": 0, "hit": 0,
                                                   "oob": 0, "miss": []}))
    excl = defaultdict(Counter)
    for c in cases_m4():
        raw = c["raw"]
        sb = swept_byte(raw, ANCHOR_M4)
        pop = "byte" + ",".join(map(str, sb)) if sb else "anchor"
        if c["excl"]:
            excl[pop][c["excl"]] += 1
            continue
        if mode(raw) == 3:
            excl[pop]["b7_mode3_reserved"] += 1
            continue
        w = c["words"]
        base = PROD_M4 if mode(raw) == 0 else [0] * 8
        for name, A in models_for(raw, None, SLOT_M4).items():
            S = res[pop][name]
            if A is None:
                S["oob"] += 1
                continue
            S["n"] += 1
            if all(((base[i] + A) & M32) == w[i] for i in range(8)):
                S["hit"] += 1
            elif len(S["miss"]) < 3:
                S["miss"].append({"hex": c["hex"], "pred8": [(base[i] + A) & M32
                                                             for i in range(8)],
                                  "got8": w, "src": c["src"]})
    return res, excl


def report(res, excl, title, models_shown):
    print(f"\n########## {title} ##########")
    pops = sorted(res, key=lambda s: (len(s), s))
    hdr = f"{'population':16s}" + "".join(f"{m[:26]:>28s}" for m in models_shown)
    print(hdr)
    for p in pops:
        row = f"{p:16s}"
        for m in models_shown:
            S = res[p].get(m)
            row += (f"{S['hit']:>12d}/{S['n']:<15d}" if S else f"{'-':>28s}")
        print(row)
    print("\nexclusions per population:")
    for p in pops:
        if excl[p]:
            print(f"  {p:16s} {dict(excl[p])}")


if __name__ == "__main__":
    SHOW = ["U  literal|slot, sel = b9 bit3",
            "M-IMM-IMM8  A = (b8&7)<<5 | b7>>3",
            "M-IMM-K  A = b7>>3",
            "M-IMM-K9  db.json (b8&0xF)<<5|K",
            "M-NONE-EXT(K)  A = SLOT[K]",
            "M-NONE-FIXED  A = anchor addend"]
    rg, eg = score_g17p()
    rm, em = score_m4()
    report(rm, em, "C-M4  (M4 / G16G)  — hit = all EIGHT lanes exact", SHOW)
    report(rg, eg, "C-G17P  (A18 Pro / G17P)", SHOW)

    out = {"SLOT_G17P_fitted_on_EXP0160_run01_sset1_byte7": SLOT_G17P,
           "SLOT_G17P_cases_per_K": SLOT_N,
           "SLOT_G17P_ambiguous_K": SLOT_AMBIG,
           "SLOT_M4_measurable": SLOT_M4,
           "C_M4": {p: {m: {k: v for k, v in S.items()} for m, S in d.items()}
                    for p, d in rm.items()},
           "C_M4_excluded": {p: dict(c) for p, c in em.items()},
           "C_G17P": {p: {m: {k: v for k, v in S.items()} for m, S in d.items()}
                      for p, d in rg.items()},
           "C_G17P_excluded": {p: dict(c) for p, c in eg.items()}}
    dump(out, "s3_models.json")
    print("\nSLOT_G17P (fitted, EXP-0160 run01 sset1 byte+7 only):")
    for k in sorted(SLOT_G17P):
        print(f"   K={k:2d}  A={SLOT_G17P[k]:<12d} n={SLOT_N[k]:3d}"
              + ("  AMBIGUOUS " + str(SLOT_AMBIG[k]) if k in SLOT_AMBIG else ""))

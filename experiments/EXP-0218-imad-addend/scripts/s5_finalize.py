#!/usr/bin/env python3
"""EXP-0218 step 5 — the numbers the verdict rests on, each with its exact
numerator and denominator, split by experiment / run / seed set so no single
process, run or fit can carry a claim on its own."""
from __future__ import annotations
import sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G
from lib0218 import (cases_g17p, cases_m4, SEEDS, ANCHOR_G17P, ANCHOR_M4,
                     swept_byte, dump, M32)
from s3_models import K, mode, imm8, litsel, SLOT_G17P, PROD_M4

OUT = {}


def g_addend(c):
    raw = c["raw"]
    dst = raw[3] >> 1
    if dst > 15:
        return None
    got = c["regs"][dst]
    if got == POISON_G:
        return None
    i5, i6 = raw[5] >> 2, raw[6] >> 3
    if i5 > 15 or i6 > 15:
        return None
    s = SEEDS[c["sset"]]
    P = (s[i5] * (0 if raw[6] & 1 else s[i6])) & M32
    return (got - (P if mode(raw) == 0 else 0)) & M32


def m_addend(c):
    w = c["words"]
    base = PROD_M4 if mode(c["raw"]) == 0 else [0] * 8
    r = set((w[i] - base[i]) & M32 for i in range(8))
    return r.pop() if len(r) == 1 else None


# 1. byte+7 sweep on C-G17P, split by experiment/run/seed set: does SLOT[K]
#    (fitted on EXP-0160 run01 sset1 alone) predict every other slice?
def slot_holdout():
    rows = defaultdict(lambda: [0, 0])
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_G17P) != (7,):
            continue
        A = g_addend(c)
        if A is None:
            continue
        key = f"{c['exp'][:8]}/{c['run']}/sset{c['sset']}"
        rows[key][1] += 1
        if SLOT_G17P.get(K(raw)) == A:
            rows[key][0] += 1
    return {k: {"predicted_by_fitted_SLOT": v[0], "scored": v[1]}
            for k, v in sorted(rows.items())}


# 2. the byte+9 literal switch, both carriers, exact counts
def byte9_switch():
    res = {}
    g = defaultdict(lambda: defaultdict(Counter))
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_G17P) not in ((9,), ()):
            continue
        A = g_addend(c)
        if A is None:
            continue
        if not (raw[9] >> 5) & 1:      # byte+9 bit5 == 0: the block does
            continue                   # not compute at all (see RESULTS 4.3)
        g[("literal" if litsel(raw) else "fetch")][raw[9]][A] += 1
    res["C_G17P"] = {
        "K_at_anchor": K(bytes.fromhex(ANCHOR_G17P)),
        "literal_branch(b9 bit5==1, bit3==0)": {
            "byte9_values": sorted(g["literal"]),
            "cases": sum(sum(c.values()) for c in g["literal"].values()),
            "cases_with_A_equal_to_K": sum(
                n for v, c in g["literal"].items() for a, n in c.items()
                if a == K(bytes.fromhex(ANCHOR_G17P))),
            "addends_seen": sorted({a for c in g["literal"].values() for a in c})},
        "fetch_branch(b9 bit5==1, bit3==1)": {
            "byte9_values": sorted(g["fetch"]),
            "cases": sum(sum(c.values()) for c in g["fetch"].values()),
            "cases_with_A_equal_to_K": sum(
                n for v, c in g["fetch"].items() for a, n in c.items()
                if a == K(bytes.fromhex(ANCHOR_G17P))),
            "per_value": {hex(v): {str(a): n for a, n in c.items()}
                          for v, c in sorted(g["fetch"].items())}}}
    m = defaultdict(lambda: defaultdict(Counter))
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_M4) not in ((9,), ()):
            continue
        A = m_addend(c)
        if not (raw[9] >> 5) & 1:
            continue
        m[("literal" if litsel(raw) else "fetch")][raw[9]][A] += 1
    KM = K(bytes.fromhex(ANCHOR_M4))
    res["C_M4"] = {
        "K_at_anchor": KM,
        "literal_branch(b9 bit5==1, bit3==0)": {
            "n_byte9_values": len(m["literal"]),
            "cases": sum(sum(c.values()) for c in m["literal"].values()),
            "cases_with_A_equal_to_imm8": sum(
                n for v, c in m["literal"].items() for a, n in c.items() if a == KM),
            "addends_seen": sorted({str(a) for c in m["literal"].values() for a in c})},
        "fetch_branch(b9 bit5==1, bit3==1)": {
            "n_byte9_values": len(m["fetch"]),
            "cases": sum(sum(c.values()) for c in m["fetch"].values()),
            "cases_with_A_equal_to_imm8": sum(
                n for v, c in m["fetch"].items() for a, n in c.items() if a == KM),
            "addends_seen": sorted({str(a) for c in m["fetch"].values() for a in c}),
            "split_by_b9_bit0": {
                str(b): sorted({str(a) for v, c in m["fetch"].items()
                                if (v & 1) == b for a in c}) for b in (0, 1)}}}
    return res


# 3. byte+9 bit-by-bit: which bits change the addend, in the region where the
#    instruction still computes (byte+9 bit5 == 1 on both carriers)
def byte9_bits():
    out = {}
    for name, cases, anchor, add in (("C_M4", cases_m4, ANCHOR_M4, m_addend),
                                     ("C_G17P", cases_g17p, ANCHOR_G17P, g_addend)):
        seen = {}
        for c in cases():
            raw = c["raw"]
            if c["excl"] or mode(raw) == 3 or swept_byte(raw, anchor) not in ((9,), ()):
                continue
            if not (raw[9] >> 5) & 1:
                continue
            A = add(c)
            if A is None:
                continue
            seen.setdefault(raw[9], set()).add(A)
        roles = {}
        for i in range(8):
            pairs = flips = 0
            for v, s in seen.items():
                w = v ^ (1 << i)
                if w in seen:
                    pairs += 1
                    if s != seen[w]:
                        flips += 1
            roles[f"bit{i}"] = {"pairs_compared": pairs // 2,
                                "pairs_whose_addend_differs": flips // 2}
        out[name] = {"values_observed": len(seen), "bit_roles": roles}
    return out


# 4. does byte+8's low nibble contribute to the addend in FETCH mode?
def b8_in_fetch():
    hit = n = 0
    tab = defaultdict(Counter)
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_G17P) not in ((8,), ()):
            continue
        if litsel(raw) or (raw[8] & 0xF0) != 0xD0:
            continue
        A = g_addend(c)
        if A is None:
            continue
        n += 1
        tab[raw[8] & 0xF][A] += 1
        if A == imm8(raw):
            hit += 1
    return {"population": "C-G17P byte+8 sweep, mulsel high nibble 0xd, FETCH mode",
            "A_equals_imm8": hit, "scored": n,
            "per_low_nibble": {str(k): {str(a): m for a, m in v.items()}
                               for k, v in sorted(tab.items())}}


# 5. the one C-M4 byte+7 anomaly, in full
def anomaly():
    out = []
    for c in cases_m4():
        if c["hex"] == "9f00560002080024d0260a00":
            out.append({"src": c["src"], "run": c["run"], "outcome": c["outcome"],
                        "status": c["status"], "words": c["words"],
                        "excl": c["excl"]})
    return out


if __name__ == "__main__":
    OUT["slot_table_holdout_C_G17P"] = slot_holdout()
    OUT["byte9_literal_switch"] = byte9_switch()
    OUT["byte9_bit_roles"] = byte9_bits()
    OUT["byte8_low_nibble_in_fetch_mode"] = b8_in_fetch()
    OUT["C_M4_byte7_anomaly_0x24"] = anomaly()
    dump(OUT, "s5_finalize.json")
    import json
    print(json.dumps(OUT, indent=1, default=str))

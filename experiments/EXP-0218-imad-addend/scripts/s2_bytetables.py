#!/usr/bin/env python3
"""EXP-0218 step 2 — per-byte-value addend tables for every candidate byte, on
BOTH carriers, with the recovery route recorded per case.

No model is assumed: on C-M4 the addend comes from the zero-product lanes
(a*b == 0 for lanes 5 and 7 under every multiply variant), and the 8-lane fit
says which multiply variant, if any, the swept byte selected.  On C-G17P it
comes either from a product-dropped case (byte+7 mode 1/2) or from
destination - SEED[b5>>2]*SEED[b6>>3].
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


def s32(u):
    return u - (1 << 32) if u & 0x80000000 else u


OPS = [("low32", lambda a, b: (a * b) & M32),
       ("mulhi_u", lambda a, b: (a * b) >> 32),
       ("mulhi_s", lambda a, b: ((s32(a) * s32(b)) >> 32) & M32),
       ("zero", lambda a, b: 0),
       ("a", lambda a, b: a),
       ("b", lambda a, b: b),
       ("a_plus_b", lambda a, b: (a + b) & M32),
       ("a_minus_b", lambda a, b: (a - b) & M32)]


def m4_table(pos):
    """value -> Counter of (op_that_fits_all_8_lanes, addend)."""
    t = defaultdict(Counter)
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_M4) not in ((pos,), ()):
            continue
        w = c["words"]
        got = None
        for name, f in OPS:
            res = set((w[i] - f(A_IN[i], B_IN[i])) & M32 for i in range(8))
            if len(res) == 1:
                got = (name, res.pop())
                break
        if got is None:
            got = ("unmodelled", tuple(w[i] for i in (5, 7)))
        t[raw[pos]][got] += 1
    return t


def g17p_table(pos):
    """value -> {sset -> Counter of (route, addend)}."""
    t = defaultdict(lambda: defaultdict(Counter))
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or swept_byte(raw, ANCHOR_G17P) not in ((pos,), ()):
            continue
        dst = raw[3] >> 1
        if dst > 15:
            continue
        got = c["regs"][dst]
        if got == POISON_G:
            continue
        m = raw[7] & 3
        seeds = SEEDS[c["sset"]]
        i5, i6 = raw[5] >> 2, raw[6] >> 3
        if m == 0 and i5 <= 15 and i6 <= 15:
            P = (seeds[i5] * (0 if raw[6] & 1 else seeds[i6])) & M32
            t[raw[pos]][c["sset"]][("minus_product", (got - P) & M32)] += 1
        elif m in (1, 2):
            t[raw[pos]][c["sset"]][("product_dropped", got)] += 1
    return t


def show_m4(pos, limit=None):
    t = m4_table(pos)
    print(f"--- C-M4 (G16G)  byte+{pos}  ({len(t)} values) anchor={ANM[pos]:#04x}")
    for v in sorted(t):
        if limit and v >= limit:
            continue
        e = "  ".join(f"{k}x{n}" for k, n in t[v].most_common(3))
        print(f"   {v:3d} 0x{v:02x}  {e}")
    return t


def show_g(pos, limit=None):
    t = g17p_table(pos)
    print(f"--- C-G17P byte+{pos}  ({len(t)} values) anchor={ANG[pos]:#04x}")
    for v in sorted(t):
        if limit and v >= limit:
            continue
        parts = []
        for ss in sorted(t[v]):
            parts.append(f"s{ss}:" + ",".join(f"{k[1]}({k[0][:4]})x{n}"
                                              for k, n in t[v][ss].most_common(3)))
        print(f"   {v:3d} 0x{v:02x}  " + "   ".join(parts))
    return t


if __name__ == "__main__":
    out = {}
    for pos in (7, 8, 9, 10, 4, 2, 1, 11, 3):
        tm = show_m4(pos)
        tg = show_g(pos)
        out[f"byte{pos}"] = {
            "C_M4": {str(v): {str(k): n for k, n in c.items()} for v, c in tm.items()},
            "C_G17P": {str(v): {str(ss): {str(k): n for k, n in cc.items()}
                                for ss, cc in d.items()} for v, d in tg.items()},
        }
        print()
    dump(out, "s2_bytetables.json")

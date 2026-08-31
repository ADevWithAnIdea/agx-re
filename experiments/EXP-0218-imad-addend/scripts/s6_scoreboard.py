#!/usr/bin/env python3
"""EXP-0218 — the complete model scoreboard (every pre-registered model, every
population, exact numerator/denominator) plus three remaining counts:
  * byte+8 bit 3: is it part of the immediate?
  * the 8-bit-selector vs 5-bit-selector ambiguity in fetch mode;
  * every Group II single-byte immediate model.
"""
from __future__ import annotations
import json, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G
from lib0218 import cases_m4, cases_g17p, ANCHOR_M4, ANCHOR_G17P, swept_byte, dump, M32, SEEDS
from s3_models import K, mode, imm8, litsel, PROD_M4, SLOT_G17P

EXP = Path(__file__).resolve().parents[1]
S3 = json.loads((EXP / "analysis" / "s3_models.json").read_text())

KEY_M4 = ["anchor", "byte7", "byte8", "byte9", "byte11", "byte1", "byte2"]
KEY_G = ["anchor", "byte7  [FIT]", "byte7", "byte8", "byte9", "byte11",
         "byte6,7", "byte7,8", "byte5", "byte6"]


def board(car, keys, title):
    print(f"\n===== {title} =====")
    models = sorted({m for p in keys for m in S3[car].get(p, {})})
    w = max(len(m) for m in models) + 2
    print(" " * w + "".join(f"{k[:12]:>16s}" for k in keys))
    for m in models:
        row = f"{m:{w}s}"
        for k in keys:
            S = S3[car].get(k, {}).get(m)
            row += f"{(str(S['hit'])+'/'+str(S['n'])) if S else '-':>16s}"
        print(row)


def b8_bit3():
    """C-M4, literal mode, mulsel high nibble 0xd: does byte+8 bit 3 move A?"""
    seen = defaultdict(set)
    for c in cases_m4():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_M4) not in ((8,), ()):
            continue
        if (raw[8] & 0xF0) != 0xD0 or not litsel(raw):
            continue
        w = c["words"]
        base = PROD_M4 if mode(raw) == 0 else [0] * 8
        r = set((w[i] - base[i]) & M32 for i in range(8))
        if len(r) == 1:
            seen[raw[8]].add(r.pop())
    pairs = same = 0
    for v in list(seen):
        u = v ^ 0x08
        if u in seen and v < u:
            pairs += 1
            same += (seen[v] == seen[u])
    return {"byte8_values_with_a_constant_addend": len(seen),
            "bit3_pairs_compared": pairs, "pairs_with_identical_addend": same,
            "table": {hex(v): sorted(a) for v, a in sorted(seen.items())}}


def fetch_index_width():
    """C-G17P fetch mode: is the source index 8 bits (b7[3:8] | b8[0:3]<<5) or
    5 bits with a nonzero b8 low nibble suppressing the addend?  Both predict
    the same thing wherever FILE[index>=32] == 0, so count the cases that could
    have separated them."""
    sep = agree = 0
    rows = Counter()
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or litsel(raw):
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
        n = raw[8] & 7
        idx8 = K(raw) | (n << 5)
        m8 = SLOT_G17P.get(idx8, 0)          # 8-bit index; unseen index -> 0
        m5 = SLOT_G17P.get(K(raw)) if n == 0 else 0
        rows[(n != 0, A == m8, A == m5)] += 1
        if m8 != m5:
            sep += 1
            agree += (A == m8)
    return {"cases_scored": sum(rows.values()),
            "cases_where_the_two_readings_differ": sep,
            "of_those_the_8bit_reading_wins": agree,
            "breakdown_(nibble_nonzero, fits8, fits5)": {str(k): v
                                                         for k, v in rows.items()}}


if __name__ == "__main__":
    board("C_M4", KEY_M4, "C-M4 (M4 / G16G) — hit = all 8 lanes exact")
    board("C_G17P", KEY_G, "C-G17P (A18 Pro / G17P)")
    out = {"byte8_bit3_in_literal_mode": b8_bit3(),
           "fetch_index_width_ambiguity": fetch_index_width()}
    print("\nbyte+8 bit 3 (C-M4, literal, mulsel 0xd):",
          {k: v for k, v in out["byte8_bit3_in_literal_mode"].items() if k != "table"})
    print("byte+8 table:", out["byte8_bit3_in_literal_mode"]["table"])
    print("\n8-bit vs 5-bit fetch index (C-G17P):", out["fetch_index_width_ambiguity"])
    dump(out, "s6_scoreboard.json")

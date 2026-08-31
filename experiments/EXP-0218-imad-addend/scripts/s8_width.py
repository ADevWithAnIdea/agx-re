#!/usr/bin/env python3
"""EXP-0218 — the 32-bit fetch: an out-of-sample prediction from the 16-bit
slot table alone.

If a 16-bit fetch returns half K of a 32-bit external word file, a 32-bit fetch
at the same K must return  SLOT[K] | SLOT[K+1] << 16  (for even K).  SLOT was
fitted on the byte+7 sweep in 16-bit fetch mode ONLY, so every 32-bit case is
held out.
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G
from lib0218 import cases_g17p, cases_m4, SEEDS, ANCHOR_G17P, ANCHOR_M4, swept_byte, dump, M32
from s3_models import K, mode, litsel, SLOT_G17P, PROD_M4

hit = n = 0
rows = Counter()
for c in cases_g17p():
    raw = c["raw"]
    if c["excl"] or mode(raw) == 3 or litsel(raw):
        continue
    if not ((raw[9] >> 5) & 1) or not (raw[9] & 1):     # 32-bit fetch only
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
    k = K(raw)
    pred = (SLOT_G17P.get(k, 0) | (SLOT_G17P.get(k + 1, 0) << 16)) & M32
    n += 1
    hit += (A == pred)
    rows[(k, A, pred, hex(raw[9]))] += 1

# byte+8 = 0xf0 reaches the same 32-bit form without touching byte+9
hit8 = n8 = 0
rows8 = Counter()
for c in cases_g17p():
    raw = c["raw"]
    if c["excl"] or mode(raw) == 3 or litsel(raw):
        continue
    if swept_byte(raw, ANCHOR_G17P) not in ((8,), ()) or raw[8] != 0xF0:
        continue
    dst = raw[3] >> 1
    got = c["regs"][dst]
    if got == POISON_G:
        continue
    s = SEEDS[c["sset"]]
    P = (s[raw[5] >> 2] * (0 if raw[6] & 1 else s[raw[6] >> 3])) & M32
    A = (got - (P if mode(raw) == 0 else 0)) & M32
    k = K(raw)
    pred = (SLOT_G17P.get(k, 0) | (SLOT_G17P.get(k + 1, 0) << 16)) & M32
    n8 += 1
    hit8 += (A == pred)
    rows8[(k, A, pred)] += 1

# C-M4: the same width bit, at the one K its carrier reaches
m16 = Counter()
m32 = Counter()
for c in cases_m4():
    raw = c["raw"]
    if c["excl"] or mode(raw) == 3 or litsel(raw):
        continue
    if not ((raw[9] >> 5) & 1) or swept_byte(raw, ANCHOR_M4) not in ((9,), ()):
        continue
    w = c["words"]
    base = PROD_M4 if mode(raw) == 0 else [0] * 8
    r = set((w[i] - base[i]) & M32 for i in range(8))
    if len(r) != 1:
        continue
    (m32 if raw[9] & 1 else m16)[(K(raw), r.pop())] += 1

out = {"C_G17P_32bit_via_byte9_bit0": {
           "predicted_by_SLOT[K] | SLOT[K+1]<<16": hit, "scored": n,
           "cases": {str(k): v for k, v in rows.items()}},
       "C_G17P_32bit_via_byte8_0xf0": {
           "predicted": hit8, "scored": n8,
           "cases": {str(k): v for k, v in rows8.items()}},
       "C_M4_fetch_by_width": {
           "16bit(b9 bit0 == 0)": {str(k): v for k, v in m16.items()},
           "32bit(b9 bit0 == 1)": {str(k): v for k, v in m32.items()},
           "note": "SLOT_M4[8] was never dispatched, so the pairing rule cannot "
                   "be scored here; the two observations are consistent with a "
                   "32-bit word file whose half 7 is 0 and whose word 3 is 0x100."}}
dump(out, "s8_width.json")
import json
print(json.dumps(out, indent=1, default=str))

#!/usr/bin/env python3
"""EXP-0218 — adversarial checks against the experiment's own conclusion.

1. Do the two anchors differ ONLY at byte+7 and byte+9?  (If they differ
   somewhere else, byte+9 is not the only candidate explanation.)
2. Which byte+9 bits could carry the literal/fetch selector on EACH carrier?
   A bit is a candidate only if it is 0 in every literal-mode value dispatched
   and 1 in every fetch-mode value dispatched.  If more than one bit qualifies,
   that carrier cannot name the bit.
3. Provenance of the C-G17P literal-mode cases (which experiment, run, seed set).
4. Constant-byte artefact: how many models "fit" only because the byte they read
   is 0x00 at the anchor and the addend is 0 for most K.
"""
from __future__ import annotations
import sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G
from lib0218 import (cases_m4, cases_g17p, ANCHOR_M4, ANCHOR_G17P, swept_byte,
                     dump, M32, SEEDS)
from s3_models import K, mode, litsel, PROD_M4, SLOT_G17P

OUT = {}
AM, AG = bytes.fromhex(ANCHOR_M4), bytes.fromhex(ANCHOR_G17P)
OUT["anchor_diff"] = {"C_M4": ANCHOR_M4, "C_G17P": ANCHOR_G17P,
                      "byte_positions_that_differ":
                          [i for i in range(12) if AM[i] != AG[i]],
                      "values": {str(i): [hex(AM[i]), hex(AG[i])]
                                 for i in range(12) if AM[i] != AG[i]}}

# 2. candidate selector bits per carrier
def cand(cases, anchor, add):
    lit, fet = set(), set()
    for c in cases():
        raw = c["raw"]
        if c["excl"] or mode(raw) == 3 or swept_byte(raw, anchor) not in ((9,), ()):
            continue
        if not (raw[9] >> 5) & 1:
            continue
        A = add(c)
        if A is None:
            continue
        (lit if A == K(raw) or (anchor is AM and A == K(raw)) else fet).add(raw[9])
    return lit, fet


def m_add(c):
    w = c["words"]
    base = PROD_M4 if mode(c["raw"]) == 0 else [0] * 8
    r = set((w[i] - base[i]) & M32 for i in range(8))
    return r.pop() if len(r) == 1 else None


def g_add(c):
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


for name, cs, anc, add in (("C_M4", cases_m4, ANCHOR_M4, m_add),
                           ("C_G17P", cases_g17p, ANCHOR_G17P, g_add)):
    lit, fet = cand(cs, anc, add)
    ok = [i for i in range(8)
          if all(not (v >> i) & 1 for v in lit) and all((v >> i) & 1 for v in fet)]
    OUT.setdefault("candidate_selector_bits", {})[name] = {
        "literal_mode_byte9_values": sorted(hex(v) for v in lit),
        "fetch_mode_byte9_values": sorted(hex(v) for v in fet),
        "bits_that_separate_them_perfectly": ok}

# 3. provenance of the G17P literal-mode cases
prov = Counter()
for c in cases_g17p():
    raw = c["raw"]
    if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_G17P) not in ((9,), ()):
        continue
    if not ((raw[9] >> 5) & 1) or not litsel(raw):
        continue
    A = g_add(c)
    if A is None:
        continue
    prov[(c["exp"], c["run"], c["sset"], hex(raw[9]), A)] += 1
OUT["C_G17P_literal_mode_case_provenance"] = {str(k): v for k, v in sorted(prov.items())}

# 4. constant-byte artefact
z = Counter()
for c in cases_g17p():
    raw = c["raw"]
    if c["excl"] or mode(raw) == 3 or swept_byte(raw, ANCHOR_G17P) != (7,):
        continue
    A = g_add(c)
    if A is None:
        continue
    z[(A == 0, raw[11] == 0, raw[3] == 0)] += 1
OUT["constant_byte_artefact_C_G17P_byte7"] = {
    "note": "b3 and b11 are 0x00 at the anchor and never move in this population, "
            "so 'A = b3' and 'A = b11' score a hit on every case whose addend is 0.",
    "(addend_is_zero, b11_is_zero, b3_is_zero)": {str(k): v for k, v in z.items()}}

dump(OUT, "s7_adversarial.json")
import json
print(json.dumps(OUT, indent=1, default=str))

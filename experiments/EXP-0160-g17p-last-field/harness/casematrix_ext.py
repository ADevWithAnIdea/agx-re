#!/usr/bin/env python3
"""EXP-0160 EXTENSION matrix (pre-registered addendum; see PRE_REGISTRATION.md
"Addendum A"). Frozen separately so the ORIGINAL harness/casematrix.py stays
byte-identical to the copy hashed in CAPTURE_CONTRACT.json and run01/run02
remain exactly reproducible.

Why it exists: the dispatch's premise was that each of the eight instructions
was ONE field from emittable. For `falu3` and `falu3_ext` that is wrong --
`tools/agx-isa/validation.json` leaves BOTH `op` and `srcB` below emitter
grade. EXP-0154 sampled only 29 of `srcB`'s 256 values. This extension sweeps
it densely with the same instrument.

CLEAN-ROOM: same authored inputs, same carriers, same tools.
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402  (reuse its builders verbatim)

INS = CM.INS
SEED_SETS = CM.SEED_SETS
set_field = CM.set_field
set_byte = CM.set_byte
field_geom = CM.field_geom

ARMS = [
    ("F3_SRCB",  "k_fma",     56, 64, 0, "falu3",     "float", "srcB"),
    ("F3E_SRCB", "k_sat_fma", 56, 66, 0, "falu3_ext", "float", "srcB"),
]


def resolve_arms(anchor_report):
    return list(ARMS)


def build_cases(anchor_report):
    cases = []
    for (arm, fn, lo, hi, tgt, mn, kind, field) in ARMS:
        main = bytes.fromhex(anchor_report[fn]["main_hex"])
        blk = main[lo:hi]
        ilen = INS[mn]["length"]
        anchor_instr = blk[tgt:tgt + ilen]
        start, w = field_geom(mn, field)
        anchor_val = 0
        for i in range(w):
            bit = start + i
            if anchor_instr[bit >> 3] >> (bit & 7) & 1:
                anchor_val |= 1 << i
        base = dict(arm=arm, probe=fn, block_lo=lo, block_hi=hi, tgt=tgt,
                    instr=mn, kind=kind, anchor=anchor_instr.hex(),
                    fstart=start, fwidth=w, anchor_value=anchor_val)

        def emit(**kw):
            for ss in SEED_SETS:
                c = dict(base)
                c.update(kw)
                c["sset"] = ss
                cases.append(c)

        emit(field="__falsifier_byte0", value=0,
             bytes=set_byte(blk, tgt, 0, 0x00).hex(), predict="not_ok")
        for v in range(1 << w):
            emit(field=field, value=v,
                 bytes=set_field(blk, tgt, start, w, v).hex(), predict="")
    for i, c in enumerate(cases):
        c["idx"] = i
    return cases


matrix_sha256 = CM.matrix_sha256


def main():
    rep = json.loads((HERE.parent / "work" / "anchors" /
                      "anchor_report.json").read_text())
    cs = build_cases(rep)
    print("cases:", len(cs))
    print("matrix_sha256:", matrix_sha256(cs))


if __name__ == "__main__":
    main()

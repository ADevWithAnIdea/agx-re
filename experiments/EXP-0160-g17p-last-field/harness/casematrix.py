#!/usr/bin/env python3
"""EXP-0160 case matrix (frozen at pre-registration; sha256 in CAPTURE_CONTRACT).

EIGHT arms, one per instruction whose LAST blocking field this experiment tries
to close. Each arm names the authored probe kernel whose compiled `_agc.main`
supplies the anchor, the contiguous ALU BLOCK lifted verbatim from it, and the
offset of the instruction under test inside that block.

Every field is swept DENSELY over its whole encodable range (FIELD-SWEEP-PROTOCOL
section 3.3, `w <= 8`), and every case is run under BOTH seed sets so a model
fitted on set 1 must predict set 2's 16-register post-state out of sample.

Extra, pre-registered probes:
  * `__falsifier_byte0` per arm  -- byte0 of the instruction under test forced to
    0x00. It MUST NOT score `ok`; if it does, that arm cannot detect a difference
    and nothing in it is promoted (EXP-0154 lost two arms exactly this way).
  * HALFPACK `__split*`          -- replaces byte+0..+1 and/or byte+2..+3 of the
    4-byte `half_pack` descriptor with a 2-byte `mov_imm` we assembled. This
    decides DEF-0154-1: is `half_pack` one 4-byte instruction, or two 2-byte
    half-lane instructions (in which case db.json's `src`/`b3` are the SECOND
    instruction's bytes and are not fields of `half_pack` at all)?
  * IMAD `__2d_*`                -- srcC_desc crossed against srcC_lo and against
    mulsel, to test db.json's claim that the immediate addend is assembled from
    those three bytes.

CLEAN-ROOM: block bytes come from the compiled form of OUR OWN MSL; field
geometry comes from our own tools/agx-isa/db.json; the spliced `mov_imm`s are
assembled by our own tools/agx-isa.
"""
from __future__ import print_function

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

DB = json.loads((H.ISA_DIR / "db.json").read_text())
INS = dict((i["mnemonic"], i) for i in DB["instructions"])

# arm -> (probe fn, block lo, block hi, tgt-in-block, mnemonic, seed kind, field)
# lo == None  ->  resolve from the anchor token stream: the FIRST occurrence of
# `mnemonic`, block = exactly that instruction.
ARMS = [
    ("F2E_CTRL",      "k_sat_add", 32,   40,   0, "falu2_ext", "float", "ctrl"),
    ("F3_OP",         "k_fma",     56,   64,   0, "falu3",     "float", "op"),
    ("F3E_OP",        "k_sat_fma", 56,   66,   0, "falu3_ext", "float", "op"),
    ("IMINMAX_SRCB",  "k_imin",    32,   38,   0, "iminmax",   "int",   "srcB"),
    ("ISEL8_CMPMODE", "k_rsqrt",   18,   32,   6, "isel8",     "float", "cmp_mode"),
    ("IMAD_SRCC",     "k_imad",    32,   44,   0, "imad",      "int",   "srcC_desc"),
    ("HALFPACK_SRC",  "k_half2",   32,   42,   6, "half_pack", "int",   "src"),
    ("F2I_CTRLLO",    "k_addimm",  None, None, 0, "falu2i",    "float", "ctrl_lo"),
]

SEED_SETS = (1, 2)


def resolve_arms(anchor_report):
    """Turn `None` block bounds into concrete offsets using the anchor tokens."""
    out = []
    for (arm, fn, lo, hi, tgt, mn, kind, field) in ARMS:
        if lo is None:
            toks = anchor_report[fn]["tokens"]
            hit = [t for t in toks if t["mn"] == mn]
            if not hit:
                raise RuntimeError("no %s anchor in %s" % (mn, fn))
            lo = hit[0]["off"]
            hi = lo + hit[0]["len"]
            tgt = 0
        out.append((arm, fn, lo, hi, tgt, mn, kind, field))
    return out


def set_field(blk, tgt, start, width, value):
    """`blk` with the db field [start, start+width) of the instruction at byte
    offset `tgt` set to `value`. Bit numbering is LSB-first across the
    instruction's bytes, exactly as tools/agx-isa/db.json defines it."""
    b = bytearray(blk)
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
        mask = 1 << (bit & 7)
        if (value >> i) & 1:
            b[byi] |= mask
        else:
            b[byi] &= 0xFF ^ mask
    return bytes(b)


def set_byte(blk, tgt, byte_index, value):
    b = bytearray(blk)
    b[tgt + byte_index] = value & 0xFF
    return bytes(b)


def splice(blk, at, payload):
    b = bytearray(blk)
    b[at:at + len(payload)] = payload
    return bytes(b)


def field_geom(mn, field):
    for f in INS[mn]["fields"]:
        if f["name"] == field:
            return f["start"], f["width"]
    raise KeyError("%s.%s not in db.json" % (mn, field))


# Extra probe grids (frozen).
IMAD_DESC_PTS = [0x00, 0x08, 0x0c, 0x10, 0x18, 0x20, 0x40, 0x60, 0x64, 0x68,
                 0x80, 0xc0]
IMAD_LO_PTS = [0x00, 0x01, 0x02, 0x03, 0x04, 0x08, 0x10, 0x20, 0x40, 0x7f, 0xff]
IMAD_MUL_PTS = [0x00, 0x10, 0x40, 0x50, 0x80, 0x90, 0xc0, 0xd0]


def build_cases(anchor_report):
    cases = []
    for (arm, fn, lo, hi, tgt, mn, kind, field) in resolve_arms(anchor_report):
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

        # pre-registered falsifier first so a broken arm is visible early
        emit(field="__falsifier_byte0", value=0,
             bytes=set_byte(blk, tgt, 0, 0x00).hex(), predict="not_ok")

        # the dense field sweep
        for v in range(1 << w):
            emit(field=field, value=v,
                 bytes=set_field(blk, tgt, start, w, v).hex(), predict="")

        if mn == "half_pack":
            mv6 = H.mov_imm(6, 77)
            mv7 = H.mov_imm(7, 99)
            emit(field="__split_at2_r6", value=77,
                 bytes=splice(blk, tgt + 2, mv6).hex(), predict="")
            emit(field="__split_at2_r7", value=99,
                 bytes=splice(blk, tgt + 2, mv7).hex(), predict="")
            emit(field="__split_at0_r6", value=77,
                 bytes=splice(blk, tgt + 0, mv6).hex(), predict="")
            emit(field="__split_at0and2", value=6799,
                 bytes=splice(blk, tgt + 0, mv6 + mv7).hex(), predict="")

        if mn == "imad":
            lo_s, lo_w = field_geom(mn, "srcC_lo")
            mu_s, mu_w = field_geom(mn, "mulsel")
            for d in IMAD_DESC_PTS:
                nb0 = set_field(blk, tgt, start, w, d)
                for x in IMAD_LO_PTS:
                    emit(field="__2d_desc_lo", value=(d << 8) | x,
                         bytes=set_field(nb0, tgt, lo_s, lo_w, x).hex(),
                         predict="")
                for x in IMAD_MUL_PTS:
                    emit(field="__2d_desc_mul", value=(d << 8) | x,
                         bytes=set_field(nb0, tgt, mu_s, mu_w, x).hex(),
                         predict="")

    for i, c in enumerate(cases):
        c["idx"] = i
    return cases


def matrix_sha256(cases):
    blob = json.dumps([[c["arm"], c["field"], c["value"], c["sset"], c["bytes"]]
                       for c in cases], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def main():
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cs = build_cases(rep)
    print("cases:", len(cs))
    print("matrix_sha256:", matrix_sha256(cs))
    from collections import Counter
    for a, n in sorted(Counter(c["arm"] for c in cs).items()):
        print("   %-16s %5d" % (a, n))
    for (arm, fn, lo, hi, tgt, mn, kind, field) in resolve_arms(rep):
        main_b = bytes.fromhex(rep[fn]["main_hex"])
        blk = main_b[lo:hi]
        print("   %-16s %-12s block[%d:%d] tgt=%d anchor=%s"
              % (arm, mn, lo, hi, tgt, blk[tgt:tgt + INS[mn]["length"]].hex()))


if __name__ == "__main__":
    main()

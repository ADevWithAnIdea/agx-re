#!/usr/bin/env python3
"""EXP-0154 case matrix (frozen at pre-registration; hash in CAPTURE_CONTRACT).

One ARM per instruction under test. Each arm names:
  * the authored probe kernel whose compiled `_agc.main` supplies the anchor,
  * the byte range of the contiguous ALU BLOCK lifted verbatim from it,
  * the offset of the instruction under test inside that block,
  * the seed kind (`int` / `float`) the synthesized program uses.

Cases are generated PER db.json FIELD, densely over the field's whole encodable
range when width <= 8, and BYTE-WISE (each constituent byte 0..255) for wider
raw fields -- FIELD-SWEEP-PROTOCOL section 3.3.

Every arm additionally carries a pre-registered FALSIFIER: byte0 of the
instruction under test forced to 0x00, which MUST NOT be scored `ok`. If a
falsifier ever scores `ok`, that arm's sweep proves nothing and is reported as
such rather than promoted.

CLEAN-ROOM: the block bytes come from the compiled form of our own MSL; field
geometry comes from our own tools/agx-isa/db.json.
"""
from __future__ import print_function

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

DB = json.loads((H.ISA_DIR / "db.json").read_text())
INS = dict((i["mnemonic"], i) for i in DB["instructions"])

# arm -> (probe function, block lo, block hi, target offset in block, mnemonic, seed kind)
ARMS = [
    # ---- integer -----------------------------------------------------------
    ("IADD2",          "k_u32add", 32,  42,  0,  "iadd2",          "int"),
    ("CARRY_GEN",      "k_u64add", 32,  72,  10, "carry_gen",      "int"),
    ("ILOGIC",         "k_and",    32,  42,  0,  "ilogic",         "int"),
    ("IROTATE",        "k_rot_imm", 18, 30,  0,  "irotate",        "int"),
    ("SHIFT_AMT_MOVE", "k_rot_var", 76, 80,  0,  "shift_amt_move", "int"),
    ("MOV_ZEXT16",     "k_zext16", 18,  22,  0,  "mov_zext16",     "int"),
    ("IBFE",           "k_bfe",    18,  30,  0,  "ibfe",           "int"),
    ("ISHIFT",         "k_ashr",   18,  28,  0,  "ishift",         "int"),
    ("IMINMAX",        "k_imin",   32,  38,  0,  "iminmax",        "int"),
    ("ISEL10",         "k_isel",   32,  62,  20, "isel10",         "int"),
    ("IMAD",           "k_imad",   32,  44,  0,  "imad",           "int"),
    ("IBFINS",         "k_rot_var", 42, 54,  0,  "ibfins",         "int"),
    ("HALF_PACK",      "k_half2",  32,  42,  6,  "half_pack",      "int"),
    # ---- float -------------------------------------------------------------
    ("FALU2_EXT",      "k_sat_add", 32, 40,  0,  "falu2_ext",      "float"),
    ("FALU2_SRCMOD10", "k_abs_add", 32, 42,  0,  "falu2_srcmod10", "float"),
    ("FALU3",          "k_fma",     56, 64,  0,  "falu3",          "float"),
    ("FALU3_EXT",      "k_sat_fma", 56, 66,  0,  "falu3_ext",      "float"),
    ("FALU3_SRCMOD12", "k_fma_abs", 56, 68,  0,  "falu3_srcmod12", "float"),
    ("FALU_ACC",       "k_sum",    252, 256, 0,  "falu_acc",       "float"),
    ("FSPECIAL_EST",   "k_rsqrt",  18,  24,  0,  "fspecial_est",   "float"),
    ("ISEL8",          "k_rsqrt",  18,  32,  6,  "isel8",          "float"),
    ("ISEL_REG",       "k_rsqrt",  80, 100, 10,  "isel_reg",       "float"),
]

# `fspecial` is DELIBERATELY ABSENT: EXP-0138 recorded three reproducible GPU
# hangs on its byte+3 bit7 (values 192..255) and stopped that arm under
# FIELD-SWEEP-PROTOCOL section 8. This experiment does not re-open it.
# `int_alu_ehi` and `ibfe_mesh_attr` are absent because no kernel in
# kernels/probes.metal produces an own-MSL anchor for them (compute-only
# harness; int_alu_ehi is only known from committed third-party std140 shaders).
# `falu_srcmod12b` and `half_alu_fma12` are absent because db.json flags them
# `emit_unsafe` regardless of field labels.
SKIPPED = {
    "fspecial": "hang hazard (EXP-0138: 3 reproducible hangs on byte+3 bit7); arm not opened",
    "int_alu_ehi": "no own-MSL anchor in kernels/probes.metal",
    "ibfe_mesh_attr": "fragment/mesh-stage only; this harness is compute-only",
    "falu_srcmod12b": "emit_unsafe in db.json (opsel==4 corrupts an unrelated register, EXP-0119)",
    "half_alu_fma12": "emit_unsafe in db.json (12-byte length over-consumes the next leader)",
    "icmpsel": "no own-MSL anchor: 27 authored probes produced isel10/isel8/isel_reg, never icmpsel",
    "isel10_c": "no own-MSL anchor in kernels/probes.metal",
    "isel_reg8": "no own-MSL anchor (EXP-0139 reached it only by rewriting isel8's byte+2)",
    "falu2_uni": "needs a uniform-bound carrier; not built in this experiment",
}


def set_field(blk, tgt, start, width, value):
    """Return `blk` with the db field [start, start+width) of the instruction at
    byte offset `tgt` set to `value`. Bit numbering is LSB-first across the
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


VAL = json.loads((H.ISA_DIR / "validation.json").read_text())["instructions"]
GOOD_LABELS = ("hardware-run", "isolated-byte-diff")


DENSE_ALL = os.environ.get("EXP0154_DENSE_ALL") == "1"


def is_blocked(mnemonic, field):
    """True iff this field is what stops the instruction being emittable, i.e.
    it is not already at emitter grade in tools/agx-isa/validation.json.

    With EXP0154_DENSE_ALL=1 every field is swept densely regardless (matrix
    v3). The sampled mode (matrix v2) existed only because throughput was
    mis-estimated; see CAPTURE_CONTRACT.json amendment_03."""
    if DENSE_ALL:
        return True
    return VAL.get(mnemonic, {}).get(field, {}).get("label", "untested") \
        not in GOOD_LABELS


def sample_values(w):
    """FIELD-SWEEP-PROTOCOL section 3.3 sample for a field that is ALREADY at
    emitter grade: boundaries, every power of two, and interior points. Used
    only to CONFIRM such a field on G17P, never to promote it."""
    n = 1 << w
    vs = {0, 1, 2, n - 1, n - 2}
    b = 1
    while b < n:
        vs.add(b); vs.add(b - 1); vs.add(b + 1 if b + 1 < n else b)
        b <<= 1
    for k in range(1, 8):
        vs.add((n * k) // 8)
    vs.add(n // 3); vs.add((2 * n) // 3)
    return sorted(v for v in vs if 0 <= v < n)


def field_cases(mnemonic):
    """Yield (field_name, kind, param) sweep descriptors for one instruction."""
    out = []
    for f in INS[mnemonic]["fields"]:
        w = f["width"]
        if w <= 8:
            vals = (list(range(1 << w)) if is_blocked(mnemonic, f["name"])
                    else sample_values(w))
            out.append((f["name"], "field", (f["start"], w, vals)))
        else:
            lo = f["start"] // 8
            hi = (f["start"] + w - 1) // 8
            if f["start"] % 8 or (f["start"] + w) % 8:
                # not byte-aligned and wider than a byte: sample the aligned
                # bytes it fully covers and record the geometry in the note
                pass
            blocked = is_blocked(mnemonic, f["name"])
            for bi in range(lo, hi + 1):
                out.append((f["name"], "byte",
                            (bi, list(range(256)) if blocked else sample_values(8))))
    return out


def build_cases(anchor_report):
    """Return the full ordered case list. Deterministic: this list IS the
    frozen matrix (its sha256 goes into CAPTURE_CONTRACT.json)."""
    cases = []
    for (arm, fn, lo, hi, tgt, mn, kind) in ARMS:
        main = bytes.fromhex(anchor_report[fn]["main_hex"])
        blk = main[lo:hi]
        ilen = INS[mn]["length"]
        anchor_instr = blk[tgt:tgt + ilen]
        base = dict(arm=arm, probe=fn, block_lo=lo, block_hi=hi, tgt=tgt,
                    instr=mn, kind=kind, anchor=anchor_instr.hex())
        # pre-registered falsifier first, so a broken arm is visible early
        c = dict(base); c.update(field="__falsifier_byte0", value=0,
                                 bytes=set_byte(blk, tgt, 0, 0x00).hex(),
                                 predict="not_ok")
        cases.append(c)
        for (name, how, param) in field_cases(mn):
            if how == "field":
                start, w, vals = param
                for v in vals:
                    nb = set_field(blk, tgt, start, w, v)
                    c = dict(base)
                    c.update(field=name, value=v, bytes=nb.hex(),
                             fstart=start, fwidth=w, predict="")
                    cases.append(c)
            else:
                bi, vals = param
                for v in vals:
                    nb = set_byte(blk, tgt, bi, v)
                    c = dict(base)
                    c.update(field=name, value=v, bytes=nb.hex(),
                             byte_index=bi, predict="")
                    cases.append(c)
        # ILOGIC only: the 2-D LUT probe that recovers the boolean-function map
        if mn == "ilogic":
            fa = dict((f["name"], f) for f in INS["ilogic"]["fields"])
            for ob in (0, 1):
                for la in range(16):
                    for lb in range(16):
                        nb = set_field(blk, tgt, fa["op_base"]["start"], 1, ob)
                        nb = set_field(nb, tgt, fa["lut_a"]["start"], 8, la)
                        nb = set_field(nb, tgt, fa["lut_b"]["start"], 8, lb)
                        c = dict(base)
                        c.update(field="__lut2d", value=(ob << 8) | (la << 4) | lb,
                                 bytes=nb.hex(), predict="")
                        cases.append(c)
    for i, c in enumerate(cases):
        c["idx"] = i
    return cases


def main():
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cs = build_cases(rep)
    import hashlib
    blob = json.dumps([[c["arm"], c["field"], c["value"], c["bytes"]] for c in cs],
                      sort_keys=True).encode()
    print("cases:", len(cs))
    print("matrix_sha256:", hashlib.sha256(blob).hexdigest())
    from collections import Counter
    for a, n in sorted(Counter(c["arm"] for c in cs).items()):
        print("   %-16s %5d" % (a, n))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""EXP-0138 instruction-construction helpers (float-ALU emission sweep).

Every function builds ONE instruction's raw bytes via `tools/agx-isa`'s own,
READ-ONLY `isadb.assemble(mnemonic, fields)` -- never a hand-spliced byte
string. Field VALUES are either (a) HW-VALIDATED by a prior experiment and
cited, (b) taken VERBATIM from an anchor encoding produced by compiling OUR
OWN MSL in this experiment's pilot phase (`work/pilot/anchors*.metal`,
recorded in PROGRESS.md Milestone 1), or (c) the swept independent variable.

Reused (structure, not values) from EXP-0119/EXP-0128 `isa_helpers.py`, same
project, same rules, cited: `mov_imm`, `falu2i_raw`, `falu2_raw`,
`device_store`, `stop`, `build_program`, `assert_round_trip`.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte here is either produced by
`isadb.assemble` from our own field values or copied from the compiled form
of our own MSL. No Apple binary is disassembled or introspected.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use)

R_IDX = 15            # store index register, always 0
R_UNWRITTEN = 14      # never written -> reads exactly 0.0 (EXP-0087)
PAD_DST = 13          # padding target, never a live operand

# 13 distinct EXACT minifloat fixed points seeded into r0..r12 (verified
# exact round-trip through isadb.imm_encode/imm_decode; see PROGRESS.md).
SEED = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0,
        7: 13.0, 8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0}


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def mov_imm(dst, imm8):
    """2B: d[dst] = imm8 (integer). HW-VALIDATED EXP-0031 for 0..127;
    128..255 silently read back 0 (EXP-0128) -- hard-rejected here."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm imm8 must be 0..127 (EXP-0128 boundary)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F, "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0xC0,
               srcA_size=1, imm_flag=None, opsel=4):
    """6B falu2i, every bit caller-controlled. Anchor (OUR OWN compiled MSL,
    `k_addi` = a[t]+3.0f): `09 c9 14 01 80 c0` -> imm_flag=1, opflags=1,
    ctrl_lo=0, mods=0xC0. `mods=0xC0` is EXP-0101's HW-VALIDATED requirement
    when the operand is load-sourced; it is also the compiler's own value
    here, so it is this experiment's default."""
    b1, sign = isadb.imm_encode(k)
    if imm_flag is None:
        imm_flag = b1 & 1
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo & 0x7F,
        "mods": mods & 0xFF,
    })


def seed(dst, value):
    """r[dst] = value, via falu2i(srcA = the never-written r14 = 0.0) + K."""
    return falu2i_raw(dst, R_UNWRITTEN, value, opflags4=0, mods=0xC0)


def falu2_raw(dst, srcA_reg7, srcB_reg7, opsel=4, opflags5=3, ctrl=0,
              srcB_imm=0, mod_lo=0, srcB_neg=0, mod_hi=0xC,
              srcA_size=1, srcB_size=1):
    """6B falu2. Anchor (OUR OWN compiled MSL, `k_add` = a[t+0]+a[t+1]):
    `09 01 1c 05 00 c0` -> opflags=3, ctrl=0, mod_lo=0, srcB_neg=0,
    mod_hi=0xC. Those are this builder's defaults."""
    # db.json models falu2's register fields as 6 bits PLUS a separate
    # HW-TESTED-INERT top bit (srcA_reg_top / srcB_reg_top, EXP-0099/0119),
    # so a 7-bit caller value is split across the two.
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x3F,
        "srcA_reg_top": (srcA_reg7 >> 6) & 1, "srcB_reg_top": (srcB_reg7 >> 6) & 1,
        "opsel": opsel & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x3F,
        "ctrl": ctrl & 0x7F, "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7,
        "srcB_neg": srcB_neg & 1, "mod_hi": mod_hi & 0xF,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                 space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                 st_format_ext=0, st_desc_hi=0x24, elem_size=0x11,
                 reserved7=0, reserved13=0):
    """14B device_store, ALU-forwarded form. `extmode = 2*data_reg` is
    EXP-0090 finding_5 (HW-VALIDATED, narrow: data_reg < 64). idx_off unit
    is 4 WORDS (16 bytes) -- EXP-0090/EXP-0119."""
    if extmode is None:
        extmode = (data_reg << 1) & 0xFF
    return isadb.assemble("device_store", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "st_format": st_format, "st_format_ext": st_format_ext,
        "idx_off": idx_off & 0x7FF, "st_desc_hi": st_desc_hi,
        "elem_size": elem_size & 0xFF, "reserved13": reserved13,
    })


def store_word(word_idx, data_reg):
    assert word_idx % 4 == 0, "store_word takes an absolute WORD index (0,4,8,...)"
    return device_store(R_IDX, word_idx // 4, 0, data_reg=data_reg)


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def build_program(instrs, carrier_len, pad_dst=PAD_DST):
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d exceeds carrier %d" % (len(body), carrier_len))
    rem = carrier_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + mov_imm(pad_dst, 0) * (rem // 2)
    assert len(out) == carrier_len
    return out


def assert_round_trip(buf):
    recs, leftover = isadb.disassemble(buf)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes: %s" % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = buf[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s"
                                 % (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs


# ---------------------------------------------------------------------------
# Extended / 3-source float-ALU builders.
#
# Every default below is copied VERBATIM from an anchor encoding produced by
# compiling OUR OWN MSL in this experiment's pilot phase
# (work/pilot/anchors*.metal; the exact anchor is named in each docstring).
# `reg_desc` is the family's own operand-descriptor convention:
#     byte = (reg << 1) | is32,  bit7 = the HW-TESTED-INERT top bit
# (EXP-0099/0105/0113/0119 -- NOT a register-index bit, NOT a retention flag).
# ---------------------------------------------------------------------------
def reg_desc(reg, is32=1, top=0):
    return ((reg & 0x3F) << 1) | (is32 & 1) | ((top & 1) << 7)


def falu2_ext_raw(dst, srcA_reg7, srcB_reg7, opsel=4, opflags5=3, ctrl=1,
                  srcB_imm=0, mod_lo=0, srcB_neg=0, mod_hi=0,
                  ext_tail=0x8200, srcA_size=1, srcB_size=1):
    """8B falu2_ext. Anchor (OWN MSL `k_sat2` = saturate(a0-a1)):
    `09 01 1c 05 01 08 00 82` -> ctrl=1 (the byte+4 low-2 LENGTH selector
    == 1 for the 8-byte form, EXP-0119), srcB_neg=1, ext_tail=0x8200
    (byte+6=0x00, byte+7=0x82 = the saturate/op-valid tail)."""
    return isadb.assemble("falu2_ext", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F,
        "ctrl": ctrl & 0x7F, "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7,
        "srcB_neg": srcB_neg & 1, "mod_hi": mod_hi & 0xF,
        "ext_tail": ext_tail & 0xFFFF,
    })


def falu2_srcmod10_raw(dst, srcA_reg7, srcB_reg7, opsel=4, opflags5=3, ctrl=2,
                       srcB_imm=0, mod_lo=0, srcB_neg=0, mod_hi=0,
                       ext_srcmod=0x00008000, srcA_size=1, srcB_size=1):
    """10B falu2_srcmod10. Anchor (OWN MSL `k_abs2` = |a0|+|a1|):
    `09 01 1c 05 02 00 00 80 03 00` -> ctrl=2 (length selector = 2 -> 10B),
    ext_srcmod = 0x00038000 (byte+6=0x00, byte+7=0x80 op-valid base,
    byte+8 = abs mask, byte+9=0x00). The DEFAULT here uses abs mask 0
    (`0x00008000`) so the base form is a plain a+b."""
    return isadb.assemble("falu2_srcmod10", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F,
        "ctrl": ctrl & 0x7F, "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7,
        "srcB_neg": srcB_neg & 1, "mod_hi": mod_hi & 0xF,
        "ext_srcmod": ext_srcmod & 0xFFFFFFFF,
    })


def falu_srcmod12b_raw(dst, srcA_reg7, srcB_reg7, opsel=4, opflags5=3, ctrl=3,
                       srcB_imm=0, mod_lo=0, srcB_neg=0, mod_hi=0,
                       ext_srcmod=0x000000008000, srcA_size=1, srcB_size=1):
    """12B falu_srcmod12b (2-source, byte+4 low2 == 3). No compiler-emitted
    anchor was found by this experiment's own MSL probe set (round 4,
    work/pilot/anchors4.metal); the encoding is therefore CONSTRUCTED by
    family analogy from falu2_srcmod10 with the length selector raised to 3.
    SAFETY (EXP-0119, respected here): `opsel == 4` in this family CORRUPTS
    an unrelated, independently seeded register -- it is never swept and is
    only ever used in a deliberately isolated case."""
    return isadb.assemble("falu_srcmod12b", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F,
        "ctrl": ctrl & 0x7F, "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7,
        "srcB_neg": srcB_neg & 1, "mod_hi": mod_hi & 0xF,
        "ext_srcmod": ext_srcmod & ((1 << 48) - 1),
    })


def falu3_raw(dst_lo, dst, op, srcA, srcB, srcC, ctrl=2, srcmods=0xC0):
    """8B falu3. Anchor (OWN MSL `k_fma` = fma(a0,a1,a2)):
    `09 01 1e 05 81 08 02 c0` -> dst_lo=0 (byte0 high nibble), dst=0x01,
    op=0x1e, srcA=0x05, srcB=0x81, srcC=0x08, ctrl=0x02, srcmods=0xc0.
    Field NAMES are db.json's; this experiment tests what each byte really
    addresses (see RESULTS.md / db_defects)."""
    return isadb.assemble("falu3", {
        "dst_lo": dst_lo & 0xF, "dst": dst & 0xFF, "op": op & 0xFF,
        "srcA": srcA & 0xFF, "srcB": srcB & 0xFF, "srcC": srcC & 0xFF,
        "ctrl": ctrl & 0xFF, "srcmods": srcmods & 0xFF,
    })


def falu3_ext_raw(dst_lo, dst, op, srcA, srcB, srcC, ext=0x82000002):
    """10B falu3_ext. Anchor (OWN MSL `k_satfma` = saturate(fma(a0,a1,a2))):
    `09 01 1e 05 82 08 02 00 00 82` -> srcB=0x82 (byte+4 low2 == 2 -> 10B),
    ext = bytes +6..+9 = 02 00 00 82 (little-endian 0x82000002)."""
    return isadb.assemble("falu3_ext", {
        "dst_lo": dst_lo & 0xF, "dst": dst & 0xFF, "op": op & 0xFF,
        "srcA": srcA & 0xFF, "srcB": srcB & 0xFF, "srcC": srcC & 0xFF,
        "ext": ext & 0xFFFFFFFF,
    })


def falu3_srcmod12_raw(dst, srcA_reg7, srcB_reg7, opsel=6, opflags5=3, ctrl=3,
                       srcB_imm=1, mod_lo=0, srcB_neg=1, mod_hi=0,
                       ext_srcmod=0x080000002, srcA_size=1, srcB_size=1):
    """12B falu3_srcmod12. Anchor (OWN MSL `k_fmaabs` = fma(|a0|,a1,a2)):
    `09 01 1e 05 83 08 02 00 00 80 01 00`. In db.json's field decomposition
    that reads ctrl=3, srcB_imm=1, mod_lo=0, srcB_neg=1, mod_hi=0,
    ext_srcmod = bytes +6..+11 = 02 00 00 80 01 00 (little-endian
    0x180000002); byte+10 = 0x01 is the abs-on-first-source mask, so the
    DEFAULT here uses 0x00 (`0x080000002`) = plain fma."""
    return isadb.assemble("falu3_srcmod12", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F,
        "ctrl": ctrl & 0x7F, "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7,
        "srcB_neg": srcB_neg & 1, "mod_hi": mod_hi & 0xF,
        "ext_srcmod": ext_srcmod & ((1 << 48) - 1),
    })


def falu_acc_raw(dst, srcA, srcB, op=0, cache=1):
    """4B falu_acc. Anchor (OWN MSL `k_sum`, a 10-value reduction):
    `09 01 38 17` -> dst = byte0 high nibble, srcA = byte+1 descriptor,
    srcB = byte+3 descriptor, op=0 (fadd), cache=1."""
    return isadb.assemble("falu_acc", {
        "dst": dst & 0xF, "srcA": srcA & 0xFF, "op": op & 1,
        "cache": cache & 1, "srcB": srcB & 0xFF,
    })

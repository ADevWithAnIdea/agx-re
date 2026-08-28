#!/usr/bin/env python3
"""EXP-0099 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes via `tools/agx-isa`'s
own, READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing
a captured byte string, and never by copying the external compiler
engineer's own GLSL/bytes verbatim (see apple9_isa_explainer.md -- his
document is a HYPOTHESIS SOURCE we test, not a source we port). All field
VALUES are either (a) HW-VALIDATED by a prior experiment and cited, (b) the
literal value under test in this experiment's matrix, or (c) a structural
default copied from a prior experiment's own-compiled anchor.

Register plan used throughout (flat register-index convention, matches
EXP-0090's convention):
  R_IDX      = 15  index register for device_load/store addressing, always
                   holds 0 (mov_imm(15,0)) -- HW-VALIDATED EXP-0031/EXP-0082.
  R_UNWRITTEN= 14  NEVER written by any program in this experiment; reads
                   0.0 exactly (EXP-0087 MOVE-04, HW-VALIDATED) -- used as
                   the "don't care" operand wherever only ONE operand is
                   real.
  low registers 0-13 are used as ALU write targets (falu2/falu2i dst is a
    4-bit nibble field, r0-r15 only) and as the "known low value" operand
    in the H1/H2 register-identity tests.
  r67 (encoded via device_load's HW-VALIDATED 9-bit extended dst,
    EXP-M4-13 R8: dst = dst_lo | (dst_ext9<<2)) is the "known high value"
    register -- written ONLY by device_load, independent of any ALU
    consumption (so seeding r67 does not itself depend on the H4 blocker
    under test).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use: assemble/disassemble/imm_encode/imm_decode)

R_IDX = 15
R_UNWRITTEN = 14

# ---------------------------------------------------------------------------
# float helpers
# ---------------------------------------------------------------------------
def imm_value(k):
    """The EXACT value the hardware will use for falu2i immediate k (round
    trip through isadb's own HW-VALIDATED minifloat codec, EXP-0006)."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# single-instruction builders
# ---------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031."""
    return isadb.assemble("mov_imm", {"dst": dst, "imm8": imm8 & 0xFF})


def falu2i_raw(dst, srcA_reg7, k, opflags4, ctrl_lo=0, mods=0, srcA_size=1, op="fadd"):
    """6B falu2i, EVERY bit of the field layout passed explicitly by the
    caller -- no hidden last-use/retention logic (unlike EXP-0090's
    isa_helpers.falu2i, which baked in an opflags CONVENTION; this
    experiment's whole point is to test that convention, so every bit is
    caller-controlled). `srcA_reg7` is the raw 7-bit field value (bits
    25-31 of the instruction): callers pass e.g. 3 (bit31=0) or 67 (bit31=1,
    low6=3) directly, per db.json's falu2i field table.
    """
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    imm_flag = b1 & 1
    imm_mant = (b1 >> 1) & 0x7
    imm_exp = (b1 >> 4) & 0xF
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag, "imm_mant": imm_mant, "imm_exp": imm_exp,
        "opsel": opsel, "imm_sign": sign, "opflags": opflags4 & 0xF,
        "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F, "ctrl_lo": ctrl_lo, "mods": mods,
    })


def falu2_raw(dst, srcA_reg7, srcB_reg7, opflags5, mod_hi4=0xC, ctrl=0, mod_lo=0,
              srcB_neg=0, srcA_size=1, srcB_size=1, op="fadd"):
    """6B falu2 (register-register), EVERY bit explicit. `srcA_reg7`/
    `srcB_reg7` are the raw 7-bit field values (bits 9-15 / 25-31); their
    OWN top bit (bit15 / bit31) is whatever the caller passes as part of
    the 0-127 value -- e.g. srcA_reg7=67 sets bit15=1 with low6=3.
    `opflags5` is the raw 5-bit field (bits19-23): bit0=bit19 (EXP-0086
    HW-VALIDATED last-use-of-srcA), bit1=bit20, bit2=bit21
    (explainer's claimed srcB-retention-companion / dest-publication bits
    -- UNDER TEST here, not assumed). `mod_hi4` bits1-3 = bits45-47
    (explainer's claimed "consumer route" -- UNDER TEST, default 0xC =
    route 0b110=6, the value implicit in every EXP-0090 falu2/falu2i
    anchor that is known to work for ALU-to-ALU chaining).
    """
    opsel = {"fadd": 4, "fmul": 5}[op]
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi4 & 0xF,
    })


def route_mod_hi(route3, bit0=0):
    """mod_hi (4-bit field, bits44-47) built from a 3-bit route value at
    bits45-47 (explainer's claimed "consumer route" position, the tested
    compact float form) plus bit44 (bit0 here) held at a fixed value.
    route=6 (0b110) reproduces EXP-0090's own default 0xC=0b1100 anchor
    (bit44=0,bit45=0,bit46=1,bit47=1 -> route bits[45:48]=0b110=6)."""
    return (bit0 & 1) | ((route3 & 0x7) << 1)


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED


def device_load(dst, index_reg, idx_off, elem_code=3, base_slot=1,
                 extmode=0, space=0x10, addr_mode=0x44, access_desc=0x20,
                 ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0):
    """14B device_load. EXP-0082/0083 (base_slot/index_reg/idx_off/elem_size)
    + EXP-M4-13 R8 (dst=dst_lo|(dst_ext9<<2), reaches r0..r511) --
    HW-VALIDATED. `elem_code` is the canonical 0..4 code -> raw byte+12
    value via `0x40|(code<<1)` (EXP-0082 formula)."""
    dst_lo = dst & 3
    dst_ext9 = (dst >> 2) & 0x7F
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format, "dst_lo": dst_lo, "dst_ext9": dst_ext9,
        "idx_off": idx_off & 0x7FF, "ldform_hi11": ldform_hi11,
        "elem_size": 0x40 | ((elem_code & 0x7) << 1), "reserved13": reserved13,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                  space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                  st_format_ext=0, st_desc_hi=0x24, elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store. `extmode = 2*data_reg` is EXP-0090's own
    HW-VALIDATED formula (finding_5, cross-checked on 7 store instances /
    2 kernels), REUSED here (not re-derived) -- extended, as an explicit
    exploratory step, to data_reg values >=64 (untested range for that
    formula; this experiment's own SEED_R67_READBACK case is the
    independent check for that extension)."""
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


def reg_move(dst, src_reg, src_flag=0):
    """4B compact register move. docs/isa/register-move-and-liveness.md
    HW-VALIDATED encoding: byte+2=0x01 (src_class nibble 0), op_desc=0x08.
    EXP-0087 (uniform-sourced scope); EXP-0090 (falsified for an
    ALU-written GPR source, the H5 blocker under retry here)."""
    return isadb.assemble("reg_move_c1", {
        "dst": dst, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": 0x0, "op_desc": 0x08,
    })


def falu3_raw(dst_byte, op, srcA, srcB, srcC, ctrl=0x02, srcmods=0xC0, dst_lo=None):
    """8B falu3 (plain 3-source FMA, db.json: dst_lo(nibble)+dst(byte+1,
    full 8 bits)+op+srcA(byte3)+srcB(byte4)+srcC(byte5)+ctrl+srcmods).
    UNLIKE falu2/falu2i, this family's srcA/srcB/srcC fields are modeled as
    PLAIN 8-bit register indices with no documented retention split --
    db.json's own provenance note flags this family as STRUCTURAL/
    byte-diff-only (weaker than falu2's HW-VALIDATED status), so results
    from this builder are reported at correspondingly lower confidence
    (see RESULTS.md H3 section). `dst_lo` defaults to `dst_byte & 0xF`
    (the two dst fields kept consistent, per the only own-compiled anchor
    available -- db.json's own semantics note: 'dst=byte+1, 7-bit').
    """
    if dst_lo is None:
        dst_lo = dst_byte & 0xF
    return isadb.assemble("falu3", {
        "dst_lo": dst_lo & 0xF, "dst": dst_byte & 0xFF, "op": op & 0xFF,
        "srcA": srcA & 0xFF, "srcB": srcB & 0xFF, "srcC": srcC & 0xFF,
        "ctrl": ctrl & 0xFF, "srcmods": srcmods & 0xFF,
    })


def unpack_convert_raw(reg_sel, cache_byte, src_class=0, convert_desc=0, size=0):
    """8B unpack_convert. db.json fields: src_class(byte+1),
    cache(byte+2, FULL BYTE -- EXP-0089 HW-VALIDATED bit17=byte+2 bit1
    corrupts a later read), convert_desc(byte+3..6, 32-bit),
    size(byte+7 low nibble), reg_sel(byte+7 high nibble, the source/dest
    register selector this family actually exposes -- EXP-0089's own
    positive-control gap: this field's exact addressing was NOT
    independently confirmed there, see its RESULTS.md 'positive-control
    limitation'). `cache_byte` is caller-controlled in full (this
    experiment's H6 sweep varies it bit-by-bit)."""
    return isadb.assemble("unpack_convert", {
        "src_class": src_class & 0xFF, "cache": cache_byte & 0xFF,
        "convert_desc": convert_desc & 0xFFFFFFFF, "size": size & 0xF,
        "reg_sel": reg_sel & 0xF,
    })


def stop():
    return isadb.assemble("stop", {"reserved": 0})


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=13):
    """Concatenate instruction byte-strings (must already end with stop()),
    pad with mov_imm(pad_dst,0) 2-byte instructions to EXACTLY carrier_len.
    pad_dst=13 is a register never used as a live seed/result target in
    this experiment's case matrix (kept distinct from R_UNWRITTEN=14 and
    R_IDX=15 so padding writes can never be mistaken for either sentinel)."""
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier length %d" % (len(body), carrier_len))
    remainder = carrier_len - len(body)
    if remainder % 2:
        raise ValueError("odd padding remainder %d" % remainder)
    pad = mov_imm(pad_dst, 0) * (remainder // 2)
    out = body + pad
    assert len(out) == carrier_len
    return out


def assert_round_trip(hexbytes):
    """asm/disasm round trip (CODEX step 10)."""
    recs, leftover = isadb.disassemble(hexbytes)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes: %s" % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = hexbytes[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s" %
                                  (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs

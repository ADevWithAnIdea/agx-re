#!/usr/bin/env python3
"""EXP-0090 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes by calling
`tools/agx-isa`'s own, read-only `isadb.assemble(mnemonic, fields)` --
never by hand-splicing a captured byte string. Field VALUES for the
"structural/plumbing" positions the current DB leaves undocumented
(falu2/falu2i `ctrl`/`ctrl_lo`, device_load/store `extmode`/`access_desc`/
`reserved*`) are copied verbatim from our OWN compiled reference kernels
(see ANCHORS below, each with its own compile/tokenize provenance recorded
in PRE_REGISTRATION.md) per docs/isa/register-move-and-liveness.md section
2.4's standing guidance ("emit them exactly as they appear in a pattern you
copied from compiler output for the same operand shape"); the fields under
active TEST in this experiment's field matrix (register indices, immediate
values, idx_off, elem_size, base_slot, the liveness opflags bit) are always
set explicitly by the caller, never left at an anchor's original value
unless that IS the value under test.

Register numbering convention used throughout this file: a single flat
"logical register" index N (0..15 for every field exercised here), passed
uniformly to get_sr/mov_imm/falu2 dst nibbles, falu2/falu2i srcA_reg/
srcB_reg 7-bit fields, device_load/store index_reg (raw byte, confirmed
against get_sr's own dst -> device_load's index_reg=that same N in our own
pilot compiles), and device_load's dst = dst_lo|(dst_ext9<<2) (EXP-M4-13 R8
ld_regsweep, HW-validated for N in the small range we use, dst_ext9 = N>>2,
dst_lo = N&3).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use: assemble/disassemble/imm_encode/imm_decode)


# ---------------------------------------------------------------------------
# float immediate helpers (isadb's own HW-VALIDATED minifloat codec, EXP-0006)
# ---------------------------------------------------------------------------
def imm_field(k):
    """(imm8_byte, sign) for the nearest representable falu2i immediate."""
    return isadb.imm_encode(k)


def imm_value(k):
    """The EXACT value the hardware will use for immediate k (round-trip
    through isadb's own encode+decode, so the oracle always matches what we
    actually assembled, never the caller's nominal k)."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# single-instruction builders (each a thin isadb.assemble() call)
# ---------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031."""
    return isadb.assemble("mov_imm", {"dst": dst, "imm8": imm8 & 0xFF})


def falu2(dst, op, srcA_reg, srcB_reg, last_use_srcA, ctrl=0, srcB_neg=0,
          srcA_size=1, srcB_size=1, opflags_extra=None, mod_lo=0, mod_hi=0xC,
          both_real=True):
    """6B float 2-source ALU, both operands GPRs. `op` in {'fadd','fmul'}.

    opflags (byte+2 bits3-7 = instr bits19-23): bit0 (instr bit19) is the
    EXP-0086-analogous last-use-of-srcA liveness flag. THIS EXPERIMENT'S OWN
    DECISIVE FINDING (a dedicated differential probe, see RESULTS.md
    "srcB readability" section): srcB_reg reading a value a PRIOR
    instruction actually computed (as opposed to an unwritten register,
    which correctly reads 0 regardless) additionally requires opflags bit1
    (instr bit20) SET -- i.e. opflags=0b11=3, not just bit0. opflags=1
    (bit0 only) leaves srcB reads of a real prior value SILENTLY ZEROED
    (4 independent falsifying probes: EXP-0090 pilot25/26/28/31 raw notes),
    while opflags=3 correctly delivers the real value (pilot30, reproduced).
    This matches the natural byte pattern observed in real compiler output
    (pilot_extmode.metal's falu2 instances reading two genuinely live
    device_load results both show opflags=0x3). `both_real=True` (default)
    sets opflags=3 whenever srcB is a value a prior instruction computed;
    pass `both_real=False` (srcB is an immediate-like/unwritten/don't-care
    register) to fall back to bit0-only. `opflags_extra` (raw override, 0-7,
    packed at bits1-3) takes precedence if given. `mod_hi` defaults to 0xC,
    `mod_lo`/`ctrl` to 0 -- the natural values observed in every one of our
    own compiled falu2 reg-reg instances.
    """
    opsel = {"fadd": 4, "fmul": 5}[op]
    if opflags_extra is None:
        opflags_extra = 1 if both_real else 0
    opflags = (1 if last_use_srcA else 0) | (opflags_extra << 1)
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg,
        "opsel": opsel, "opflags": opflags,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg, "ctrl": ctrl,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi,
    })


def falu2i(dst, op, srcA_reg, k, last_use_srcA, ctrl_lo=0, mods=0,
           srcA_size=1, opflags_hi=0):
    """6B float 2-source ALU, srcB = packed minifloat immediate k.
    imm_flag/imm_mant/imm_exp/imm_sign are derived from isadb.imm_encode(k)
    (the SAME codec the oracle uses via imm_value()), never hand-computed.
    opflags (byte+2 bits4-7 = instr bits20-23): bit0 (instr bit20) is the
    EXP-0086 HW-VALIDATED last-use-of-srcA liveness flag.
    """
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    imm_flag = b1 & 1
    imm_mant = (b1 >> 1) & 0x7
    imm_exp = (b1 >> 4) & 0xF
    opflags = (1 if last_use_srcA else 0) | (opflags_hi << 1)
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag, "imm_mant": imm_mant, "imm_exp": imm_exp,
        "opsel": opsel, "imm_sign": sign, "opflags": opflags,
        "srcA_size": srcA_size, "srcA_reg": srcA_reg, "ctrl_lo": ctrl_lo, "mods": mods,
    })



# EXP-0082 HW-VALIDATED load element-size code table (raw byte+12 value =
# 0x40 | (code<<1); code 3 = 4-byte/32-bit, the compiler's own default).
# ELEM_SCALE is the resulting per-index byte stride (codes 1/2 COLLAPSE:
# EXP-0082 MEM-01 -- the raw element address is computed at the nominal
# 1B/2B scale, then the ACCESS itself is rounded down to the nearest 4-byte
# boundary; not true sub-word addressing).
ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}


def elem_byte(code):
    """Canonical load elem_size code (0..4) -> raw device_load byte+12
    value, EXP-0082 HW-VALIDATED formula `0x40 | (code<<1)`."""
    return 0x40 | ((code & 0x7) << 1)


def load_byte_offset(idx, idx_off, code):
    """EXP-0082 HW-VALIDATED device_load address formula (scalar 32-bit
    ld_format=17 form): byte_offset = (idx*ELEM_SCALE[code] + idx_off*4)
    mod 2**32, with codes 1/2's index term additionally floor-aligned to 4
    (the sub-word collapse). `idx_off` is masked to its real 11-bit
    instruction field (0x7FF) FIRST, matching device_load()'s own masking --
    an out-of-range Python idx_off arg (e.g. testing the field's own
    encoding boundary) must predict from the SAME truncated value that gets
    assembled, never the caller's raw nominal value."""
    idx_off = idx_off & 0x7FF
    scale = ELEM_SCALE[code]
    index_term = idx * scale
    if code in (1, 2):
        index_term = (index_term // 4) * 4
    return (index_term + idx_off * 4) & 0xFFFFFFFF


def store_byte_offset(idx, idx_off):
    """EXP-0082 HW-VALIDATED device_store address formula for the baseline
    byte+12=0x11 (4-byte scalar) encoding: byte_offset = (idx*4 + idx_off*16)
    mod 2**32. The store-side elem_size code space beyond this one baseline
    value is NOT resolved by EXP-0082 (flagged STRUCTURAL/UNKNOWN there);
    this experiment does not vary it beyond the one validated value."""
    return (idx * 4 + idx_off * 16) & 0xFFFFFFFF


def device_load(dst, index_reg, idx_off, elem_code, base_slot,
                 extmode=0, space=0, addr_mode=0x44, access_desc=0x20,
                 ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0):
    """14B device_load. Field-by-field HW-VALIDATED model: EXP-0082/0083
    (base_slot/index_reg/idx_off/elem_size) + EXP-M4-13 R8 (dst=
    dst_lo|(dst_ext9<<2)). `elem_code` is the CANONICAL 0..4 code (converted
    here to the raw byte+12 value via elem_byte(), EXP-0082's own formula --
    never passed as a raw byte by the caller, so the oracle and the
    assembled instruction can never disagree about which code means what).
    `extmode`/`access_desc`/`space`/`addr_mode`/`ld_format`/`ldform_hi11`/
    reserved* are copied from the EXP-0082 own-compiled load anchor
    (structural plumbing, not independently re-derived here -- see
    PRE_REGISTRATION.md)."""
    dst_lo = dst & 3
    dst_ext9 = (dst >> 2) & 0x7F
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format, "dst_lo": dst_lo, "dst_ext9": dst_ext9,
        "idx_off": idx_off & 0x7FF, "ldform_hi11": ldform_hi11,
        "elem_size": elem_byte(elem_code), "reserved13": reserved13,
    })


def device_store(index_reg, idx_off, base_slot, data_reg,
                  extmode=None, space=0, addr_mode=0x54, access_desc=0x21,
                  st_format=0x11, st_format_ext=0, st_desc_hi=0x24,
                  elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store. `addr_mode=0x54` = "ALU/register-forwarded data"
    (the form our preceding falu2/falu2i result feeds); other structural
    fields (incl. the fixed `elem_size=0x11` baseline -- EXP-0082's ONLY
    HW-validated store-side value) copied from the EXP-0082 own-compiled
    store anchor.

    `data_reg`: the GPR holding the value to store. THIS EXPERIMENT'S OWN
    finding (differential decoding of two independent own-compiled
    multi-output kernels, kernels/pilot_extmode.metal and
    kernels/carrier_p2.metal -- see PRE_REGISTRATION.md/RESULTS.md): the
    `extmode` byte (db.json: untyped 'mod', role previously UNKNOWN) equals
    `2 * data_reg` in every one of 7 independently cross-checked store
    instances across two unrelated compiled kernels (0 exceptions) --
    REFINING the current db.json/EXP-0082 description ("the value register
    is supplied implicitly by the preceding op/amode") to a concrete,
    reproducible field formula: `extmode = data_reg << 1`. Passing
    `extmode=` explicitly overrides this (used only for the one deliberate
    negative-space field-matrix probe that tests a store whose extmode does
    NOT match the value the preceding ALU op produced)."""
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
    """4B compact register move. ONLY the docs/isa/register-move-and-
    liveness.md HW-VALIDATED encoding: byte+2=0x01 (src_class nibble 0),
    op_desc(byte+3)=0x08. EXP-0087, HW-VALIDATED across 5 source values."""
    return isadb.assemble("reg_move_c1", {
        "dst": dst, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": 0x0, "op_desc": 0x08,
    })


def reg_move_silent_zero(dst, src_reg, src_flag=0, byte2_hi=0x0):
    """4B compact register move variant KNOWN to silently zero the
    destination (EXP-0087 MOVE-01, e.g. byte+2=0x00/0x20/0x60 family) --
    used only for an explicit negative-space field-matrix case, never for a
    real dataflow step."""
    return isadb.assemble("reg_move_c0", {
        "dst": dst, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": byte2_hi & 0xF, "op_desc": 0x08,
    })


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def mem_fence():
    """6B standalone device-memory ordering fence (seq_cst), verbatim
    HW-documented byte pattern `07 04 54 84 0a 00` (db.json mem_fence
    descriptor, match-bit-determined -- every field here is either a match
    bit or the descriptor's own documented dominant value)."""
    return isadb.assemble("mem_fence", {"sub": 4, "memclass": 0x0A, "b5": 0})


# ---------------------------------------------------------------------------
# whole-program assembly: concatenate + pad to an exact carrier length
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=15):
    """Concatenate instruction byte-strings (already includes a trailing
    stop()), then pad with mov_imm(pad_dst, 0) 2-byte instructions until the
    total equals carrier_len EXACTLY (never a length mismatch -- see
    PRE_REGISTRATION.md `padding` note on why exact-length matching is used
    instead of relying on `stop` as a scanned terminator)."""
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier length %d" % (len(body), carrier_len))
    remainder = carrier_len - len(body)
    if remainder % 2:
        raise ValueError("odd padding remainder %d -- every AGX instruction length is even" % remainder)
    pad = mov_imm(pad_dst, 0) * (remainder // 2)
    out = body + pad
    assert len(out) == carrier_len
    return out


def assert_round_trip(hexbytes):
    """Prove the assembled program tokenizes cleanly under our own
    disassembler and reassembles byte-identically (asm/disasm round trip,
    CODEX.md step 10). Raises on any leftover bytes or mismatch."""
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

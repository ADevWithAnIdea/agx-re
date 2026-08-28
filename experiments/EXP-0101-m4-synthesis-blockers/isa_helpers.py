#!/usr/bin/env python3
"""EXP-0101 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes via `tools/agx-isa`'s
own, READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing
a captured byte string. All field VALUES are either (a) HW-VALIDATED by a
prior experiment and cited, (b) the literal value under test in this
experiment's matrix, or (c) derived from this experiment's own pilot-phase
OWN-SHADER differential analysis (`analysis/census.py`, see PROGRESS.md
Milestone 2) -- never copied from any Apple binary or from a third party's
document.

Architecture verbatim-adapted from
`EXP-0099-m4-lifetime-field-model/isa_helpers.py` (same builder shapes for
`mov_imm`/`falu2i_raw`/`falu2_raw`/`device_store`/`reg_move`/`stop`/
`build_program`/`assert_round_trip`), extended with two NEW builders this
experiment's own pilot phase required:

- `device_load_fixed()` -- unlike EXP-0099's `device_load()` (which always
  DERIVED `dst_lo`/`dst_ext9` from the same register value passed for
  `extmode`, i.e. assumed a single unified "destination register" model),
  this experiment's own pilot phase (PROGRESS.md Milestone 2) found by
  OWN-SHADER differential analysis of a compiler-emitted `device_load`-then-
  `falu2i` sequence (`analysis/census.py`) that `extmode` and
  `dst_lo`/`dst_ext9` are TWO INDEPENDENT fields: `extmode = 2 *
  (the register a later falu2/falu2i must reference)`, matching (and
  unifying with) EXP-0090's own `device_store extmode = 2*data_reg`
  formula -- while `dst_lo`/`dst_ext9` must be COPIED VERBATIM from a
  compiler-observed value for the same `ld_format`/`addr_mode` shape, not
  derived from the target register at all (HW-VALIDATED by splice, see
  RESULTS.md H1). `device_load_fixed()` exposes both fields independently
  so casematrix.py can hold one fixed while varying the other.
- `reg_move_var()` -- unlike EXP-0099's `reg_move()` (which hardcoded
  `src_class=0x0, op_desc=0x08`, i.e. `byte+2=0x01`, the one EXP-0087
  found to "work" for a uniform source), this experiment's own pilot phase
  swept `src_class` (byte+2 high nibble) and `op_desc` more broadly on an
  ALU-SOURCED carrier (rather than EXP-0087's uniform-sourced
  `synth_move.metal`) specifically to retest EXP-0087's own open question
  about `byte+2=0x21` (`src_class=2`) against a genuine ALU-computed value
  -- see RESULTS.md H2.

Register plan (matches EXP-0090/EXP-0099's convention):
  R_IDX      = 15  index register for device_load/store addressing, always
                   holds 0 (mov_imm(15,0)) -- HW-VALIDATED EXP-0031/EXP-0082.
  R_UNWRITTEN= 14  NEVER written by any program in this experiment; reads
                   0.0 exactly (EXP-0087 MOVE-04, HW-VALIDATED) -- used as
                   the "don't care" operand wherever only ONE operand is
                   real.
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
    """6B falu2i. Verbatim from EXP-0099's own builder (unchanged; this
    family's field roles are not under test here beyond srcA_reg's VALUE)."""
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
    """6B falu2 (register-register). Verbatim from EXP-0099's own builder."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi4 & 0xF,
    })


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED


def device_load_fixed(index_reg, idx_off, elem_code, base_slot, extmode,
                       dst_lo, dst_ext9, space=0x10, addr_mode=0x44,
                       access_desc=0x20, ld_format=0x11, ldform_hi11=0x10,
                       reserved7=0, reserved13=0):
    """14B device_load with `extmode` and `dst_lo`/`dst_ext9` EACH an
    independent, explicit caller-supplied value -- this experiment's own H1
    finding (RESULTS.md) is that these are NOT the same quantity encoded
    two ways (EXP-M4-13's own `dst = dst_lo | (dst_ext9<<2)` formula, used
    unmodified by EXP-0099's `device_load()`, predicts the WRONG register
    for the loaded value's ALU-visible destination). `extmode = 2 *
    target_register` is this experiment's own HW-VALIDATED formula (see
    RESULTS.md H1 casematrix groups LOAD_FIX/LOAD_ADVERSARIAL);
    `dst_lo`/`dst_ext9` must be copied from a real compile of the same
    `ld_format=0x11`/`addr_mode=0x44` (terminal, indexed) shape -- this
    experiment's own compiled anchor (`analysis/census.py`'s `v0` case)
    established `dst_lo=1, dst_ext9=1` as one such valid, HW-confirmed
    pair; no other pair was found to work for this addr_mode/ld_format
    combination (see RESULTS.md H1 "dst_lo/dst_ext9 characterization").
    """
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format, "dst_lo": dst_lo & 0x3, "dst_ext9": dst_ext9 & 0x7F,
        "idx_off": idx_off & 0x7FF, "ldform_hi11": ldform_hi11,
        "elem_size": 0x40 | ((elem_code & 0x7) << 1), "reserved13": reserved13,
    })


# The one HW-CONFIRMED-valid (dst_lo, dst_ext9) pair for addr_mode=0x44 /
# ld_format=0x11 (terminal scalar 32-bit load), established by this
# experiment's own compiled census anchor (analysis/census.py "v0" case,
# byte-for-byte: dst_lo=1, dst_ext9=1) and re-confirmed by splice
# (RESULTS.md H1). Naming it here (rather than repeating the literal 1,1
# at every call site) makes casematrix.py's intent legible: "copy the
# known-good token" vs "vary it" are then textually distinct.
DST_TOKEN_KNOWNGOOD = (1, 1)
DST_TOKEN_ZERO = (0, 0)


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                  space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                  st_format_ext=0, st_desc_hi=0x24, elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store. `extmode = 2*data_reg` is EXP-0090's own
    HW-VALIDATED formula (finding_5), reused verbatim (EXP-0099's own
    builder, unchanged)."""
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
    """4B compact register move, the EXP-0087 HW-VALIDATED encoding
    (byte+2=0x01, op_desc=0x08). Verbatim from EXP-0099's own builder."""
    return isadb.assemble("reg_move_c1", {
        "dst": dst, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": 0x0, "op_desc": 0x08,
    })


def reg_move_var(dst, src_reg, src_class, op_desc, src_flag=0):
    """4B compact register move with `src_class` (byte+2 HIGH nibble --
    db.json `reg_move_c1`'s own field, distinct from the family-selecting
    LOW nibble) and `op_desc` (byte+3) BOTH caller-controlled, to retest
    EXP-0087's own open question (docs/isa/register-move-and-liveness.md
    section 1.3: "byte+2=0x21 ... UNKNOWN -- do not rely on it") against a
    genuine ALU-computed source instead of EXP-0087's uniform-sourced
    carrier. `src_class=0` reproduces `reg_move()` above (byte+2=0x01);
    `src_class=2` is byte+2=0x21."""
    return isadb.assemble("reg_move_c1", {
        "dst": dst, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": src_class & 0xF, "op_desc": op_desc & 0xFF,
    })


def stop():
    return isadb.assemble("stop", {"reserved": 0})


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=13):
    """Concatenate instruction byte-strings (must already end with stop()),
    pad with mov_imm(pad_dst,0) 2-byte instructions to EXACTLY carrier_len.
    pad_dst=13 kept distinct from R_UNWRITTEN=14 and R_IDX=15 (EXP-0099
    convention, reused verbatim)."""
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

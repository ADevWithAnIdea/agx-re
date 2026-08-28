#!/usr/bin/env python3
"""EXP-0112 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes via `tools/agx-isa`'s
own, READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing
a captured byte string. Field VALUES are either (a) HW-VALIDATED by a prior
experiment and cited, (b) a value under test by THIS experiment's own
generator (random or systematic), or (c) a documented constant copied
VERBATIM from a prior compiler-observed/HW-confirmed anchor -- labelled as
such in the docstring at the point of use. No value here is copied from an
Apple binary or a third party's document.

Merged and adapted from two direct ancestors:
  - EXP-0101-m4-synthesis-blockers/isa_helpers.py: device_load_fixed()
    (the extmode=2*R / dst_lo,dst_ext9-verbatim / falu2i mods=0xC0 load-to-
    ALU bridge rule -- RESULTS.md H1, HW-VALIDATED), falu2_raw/falu2i_raw.
  - EXP-0090-m4-handbuilt-program-suite/isa_helpers.py: device_store's
    extmode=2*data_reg formula (HW-VALIDATED finding_5), the ELEM_SCALE /
    load_byte_offset / store_byte_offset address formulas (EXP-0082
    HW-VALIDATED), build_program/assert_round_trip.

Register plan (this experiment; documented in PRE_REGISTRATION.md):
  POOL          = r0..r13 (14 registers), the DAG value-node register file.
                  falu2/falu2i's own `dst` field is a HARD 4-bit nibble
                  (tools/agx-isa/db.json: width=4) -- POOL never exceeds 14
                  distinct simultaneously-live values for this reason.
  R_UNWRITTEN   = 14  NEVER written by any program in this experiment;
                  reads 0.0 exactly (EXP-0087 MOVE-04, HW-VALIDATED) --
                  used as falu2i's "seed" srcA for `const` DAG nodes
                  (EXP-0090 P1's own pattern: unwritten-register-plus-
                  immediate = a directly-loaded float constant).
  R_IDX         = 15  index register for device_load/store addressing,
                  always holds 0 (mov_imm(15,0)) -- HW-VALIDATED
                  EXP-0031/EXP-0082. Kept at 0 throughout so every load's
                  address is controlled entirely by its own idx_off field
                  (EXP-0082's formula collapses to idx_off*unit when the
                  index register holds 0).
  device_load's own consumer-register target (the `R` in EXP-0101's
  extmode=2*R rule) is a SEPARATE 7-bit field independent of the 4-bit
  `dst` nibble above -- this experiment's REGBOUNDARY family sweeps it
  0..127, well beyond POOL's own 0..13 range, specifically to test the
  coordinator-requested boundary the rest of this experiment's own DAG
  family never reaches.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use: assemble/disassemble/imm_encode/imm_decode)

POOL = list(range(14))          # r0..r13
R_UNWRITTEN = 14
R_IDX = 15


# ---------------------------------------------------------------------------
# float / bit helpers
# ---------------------------------------------------------------------------
def imm_value(k):
    """The EXACT value the hardware will use for a falu2i immediate k
    (round-trip through isadb's own HW-VALIDATED minifloat codec,
    EXP-0006) -- the oracle must always use this, never the nominal k."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32(x):
    """Round a Python float through an exact IEEE-754 binary32 cast (the
    hardware's own arithmetic precision for falu2/falu2i, confirmed by
    every prior float-ALU experiment's exact-match oracle convention)."""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


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


def falu2i(dst, op, srcA_reg, k, last_use_srcA, mods=0, ctrl_lo=0, srcA_size=1):
    """6B falu2i (register + packed-minifloat immediate).
    `mods` MUST be 0xC0 (not the naive default 0) when srcA_reg is a
    device_load's bridged target register -- EXP-0101 RESULTS.md H1,
    HW-VALIDATED. Callers pass mods explicitly; the generator decides based
    on whether srcA's producer is a `load` DAG node (see generator.py)."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    imm_flag = b1 & 1
    imm_mant = (b1 >> 1) & 0x7
    imm_exp = (b1 >> 4) & 0xF
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag, "imm_mant": imm_mant, "imm_exp": imm_exp,
        "opsel": opsel, "imm_sign": sign, "opflags": (1 if last_use_srcA else 0) & 0xF,
        "srcA_size": srcA_size, "srcA_reg": srcA_reg & 0x7F, "ctrl_lo": ctrl_lo, "mods": mods & 0xFF,
    })


def falu2(dst, op, srcA_reg, srcB_reg, last_use_srcA, mod_hi=0xC, mod_lo=0, ctrl=0,
           srcB_neg=0, srcA_size=1, srcB_size=1):
    """6B falu2 (register-register, BOTH operands real/computed values).
    opflags = last_use_bit | (1<<1): bit1 ("both_real") is UNCONDITIONALLY
    set -- EXP-0090 RESULTS.md decisive finding, opflags=1 (bit0 alone)
    silently zeroes srcB's read; opflags=3 is correct. mod_hi=0xC is the
    natural value observed in every own-compiled falu2 reg-reg instance
    (EXP-0090), reused as the default for both operand-real combinations
    including a load-sourced operand (EXP-0101's own LOAD_FIX cases use
    this same default; no falu2-specific "mods" analogue to falu2i's
    load-sourced 0xC0 requirement is documented anywhere)."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    opflags = (1 if last_use_srcA else 0) | (1 << 1)
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg & 0x7F,
        "opsel": opsel, "opflags": opflags & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg & 0x7F, "ctrl": ctrl,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi & 0xF,
    })


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED


def elem_byte(code):
    """Canonical load elem_size code (0..4) -> raw device_load byte+12
    value, EXP-0082 HW-VALIDATED formula `0x40 | (code<<1)`."""
    return 0x40 | ((code & 0x7) << 1)


def load_byte_offset(idx, idx_off, code):
    """EXP-0082 HW-VALIDATED device_load address formula (scalar 32-bit
    ld_format=17 form, index register always 0 in this experiment so
    idx=0 always -- kept general for documentation fidelity)."""
    idx_off = idx_off & 0x7FF
    scale = ELEM_SCALE[code]
    index_term = idx * scale
    if code in (1, 2):
        index_term = (index_term // 4) * 4
    return (index_term + idx_off * 4) & 0xFFFFFFFF


def store_byte_offset(idx, idx_off):
    """EXP-0082 HW-VALIDATED device_store address formula (baseline
    byte+12=0x11, 4-byte scalar): idx*4 + idx_off*16 (a DIFFERENT, larger
    fixed unit than the load's own idx_off*4)."""
    return (idx * 4 + idx_off * 16) & 0xFFFFFFFF


DST_TOKEN_KNOWNGOOD = (1, 1)   # verbatim anchor, EXP-0101 H1, addr_mode=0x44/ld_format=0x11


def device_load(index_reg, idx_off, elem_code, base_slot, extmode,
                 dst_lo=1, dst_ext9=1, space=0x10, addr_mode=0x44,
                 access_desc=0x20, ld_format=0x11, ldform_hi11=0x10,
                 reserved7=0, reserved13=0):
    """14B device_load. `extmode = 2 * R` where R is the register a later
    falu2/falu2i consumer will reference (EXP-0101 RESULTS.md H1,
    HW-VALIDATED, "R may be any value the ALU's own 7-bit register field
    can represent (0-127)"). `dst_lo`/`dst_ext9` default to the ONE
    HW-CONFIRMED-valid verbatim token for this addr_mode/ld_format shape
    (DST_TOKEN_KNOWNGOOD=(1,1)) -- copied verbatim, per EXP-0101's own
    explicit finding that this pair must NEVER be derived from the target
    register."""
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format, "dst_lo": dst_lo & 0x3, "dst_ext9": dst_ext9 & 0x7F,
        "idx_off": idx_off & 0x7FF, "ldform_hi11": ldform_hi11,
        "elem_size": elem_byte(elem_code), "reserved13": reserved13,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                  space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                  st_format_ext=0, st_desc_hi=0x24, elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store. `extmode = 2*data_reg` is EXP-0090's own
    HW-VALIDATED formula (finding_5)."""
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


def iadd2_anchor(srcB_imm_raw, dst=0):
    """10B iadd2, the EXP-0090 P1/P2 VERBATIM-ANCHOR shape
    (kernels/pilot_immadd.metal, HW-VALIDATED across pilot22/32 and this
    project's own P1/P2 gated cases): every field EXCEPT `srcB_imm` (the
    raw byte+5 value; caller passes the ALREADY-ENCODED byte, i.e.
    (K<<1)&0xFF for logical addend K -- iadd2's OWN register-mode operand
    encoding is explicitly NOT independently re-derived anywhere in this
    project (EXP-0090 RESULTS.md S9: "UNKNOWN / not independently
    re-derived"), so this generator treats the whole anchor pattern as a
    single documented-constant copy, labelled here, never as a
    freely-parameterized register-mode instruction. `dst` is part of the
    copied anchor and is NOT independently varied by this generator (fixed
    at the anchor's own natural value, 0) -- passing a non-default dst is
    accepted for API completeness (this experiment's own CF family reuses
    a SECOND, differently-shaped iadd2 anchor at dst=6 for its loop
    counter, copied verbatim from EXP-0090's P3 program) but is never
    derived from a rule."""
    return isadb.assemble("iadd2", {
        "addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
        "store_en": 1, "b2_fmt": 0x15, "dst": dst, "opmode": 2,
        "srcB_imm": srcB_imm_raw & 0xFF, "srcB_imm_hi": 0, "srcB_ext": 0,
        "srcA": 0x88, "opc_tail": 0x15, "opc_tail2": 4,
    })


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def get_sr_tid(dst=0):
    """4B get_sr: dst = thread_position_in_grid (EXP-0090 P3 anchor byte
    pattern, verbatim; grid=1/tg=1 dispatch in this experiment so tid=0
    always -- retained only for byte-shape fidelity with the reused P3 CF
    skeleton, not independently re-derived)."""
    return isadb.assemble("get_sr", {"form": 1, "dst": dst, "sr_sel": 0xA0,
                                       "dp_width": 0x10, "dp_marker": 6, "dst_hi": 0})


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=13):
    """Concatenate instruction byte-strings (must already end with stop()),
    pad with mov_imm(pad_dst,0) 2-byte instructions to EXACTLY carrier_len.
    pad_dst=13 is inside POOL -- fine, since padding runs strictly AFTER
    stop() and is never reached."""
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

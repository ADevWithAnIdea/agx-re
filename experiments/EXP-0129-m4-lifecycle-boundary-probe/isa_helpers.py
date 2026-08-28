#!/usr/bin/env python3
"""EXP-0119 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes via `tools/agx-isa`'s
own, READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing a
captured byte string. All field VALUES are either (a) HW-VALIDATED by a prior
experiment and cited, (b) the literal value under test in this experiment's
matrix, or (c) a structural default copied from a prior experiment's own
proven anchor. Architecture verbatim-adapted from
EXP-0099-m4-lifetime-field-model/isa_helpers.py; extended with builders for
the falu2-sibling extended/12-byte forms and for `ibitcount` (a THIRD,
independently HW-VALIDATED family carrying the literal bit-17 "cache" field,
per db.json's own EXP-M4-14 provenance note -- see PRE_REGISTRATION.md).

Register plan (flat register-index convention, matches EXP-0090/EXP-0099):
  R_IDX      = 15  index register for device_load/store addressing, always
                   holds 0 (mov_imm(15,0)) -- HW-VALIDATED EXP-0031/EXP-0082.
  R_UNWRITTEN= 14  NEVER written by any program in this experiment; reads
                   0.0 exactly (EXP-0087 MOVE-04, HW-VALIDATED) -- the
                   "don't care" / zero-seed operand.
  Low registers 0-13 are ALU write targets and "known value" registers.
  r67 (device_load's HW-VALIDATED 9-bit extended dst, EXP-M4-13 R8:
    dst = dst_lo | (dst_ext9<<2)) is the "known high value" register for
    H1's bit15/31 field-value=67 tests.

REGISTER-ADDRESSING SCOPE NOTE (read before adding a new family): this
experiment owns register LIFETIME, not register ADDRESSING (EXP-0113 owns
addressing; see dispatch). Every builder below uses ONLY register fields
this project has already independently HW-VALIDATED for arbitrary hand
construction: falu2/falu2i's srcA_reg/srcB_reg (EXP-0099 H1), the
falu2-sibling extended/12-byte forms' srcA_reg/srcB_reg (same bit positions
by direct db.json match-table inspection -- an explicitly disclosed
extrapolation, not independently re-validated per family), device_load's
dst_lo/dst_ext9 and device_store's extmode=2*data_reg formula for SMALL
registers only (EXP-0082/83/M4-13/90; EXP-0099 showed extmode fails at
r67, so this experiment only ever device_stores registers <64), and
ibitcount's dst/src (EXP-M4-14, HW-VALIDATED by direct hardware splice, a
field-scaling convention of reg<<1 for dst and reg<<2 for src -- NOT the
same convention as falu2's fields, called out explicitly at each use site).
iadd2/falu_compact4/falu_acc/ilogic/ibfins and other integer-ALU families
were deliberately EXCLUDED from this experiment: EXP-0090/EXP-0112's own
comments record that iadd2's srcA/srcB register-mode addressing is "NOT
independently re-derived anywhere in this project" (their anchors use a
fixed, uninterpreted srcA=0x88 byte), and falu_compact4/falu_acc's operand
fields are flagged STRUCTURAL/byte-diff-only in db.json's own provenance
notes. Building new lifetime tests on an unvalidated address mapping would
silently conflate "field is inert" with "field addresses a register I
guessed wrong" -- indistinguishable without addressing validation this
experiment does not have. This is a disclosed, time-boxed scoping decision
(CODEX process step 5's "known confounders"), not an oversight.
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
# float / bit helpers
# ---------------------------------------------------------------------------
def imm_value(k):
    """The EXACT value the hardware will use for a falu2i-family immediate k
    (round trip through isadb's own HW-VALIDATED minifloat codec, EXP-0006)."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# single-instruction builders -- falu2 family (base 48-bit layout)
# ---------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031."""
    return isadb.assemble("mov_imm", {"dst": dst, "imm8": imm8 & 0xFF})


def falu2i_raw(dst, srcA_reg7, k, opflags4, ctrl_lo=0, mods=0, srcA_size=1, op="fadd"):
    """6B falu2i. EVERY bit caller-controlled (no baked-in retention
    convention). `srcA_reg7` is the raw 7-bit field value (bits 25-31):
    callers pass e.g. 3 (bit31=0) or 67 (bit31=1, low6=3) directly."""
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
    """6B falu2 (register-register). EVERY bit caller-controlled.
    `opflags5` bits: bit0=bit19 (EXP-0086/89/99 HW-VALIDATED release-srcA),
    bit1=bit20 (release-srcB), bit2=bit21 (destination publication)."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi4 & 0xF,
    })


def _length_ctrl(length_low2, ctrl_hi5):
    """`ctrl`/`ctrl_lo`'s bits [32:39) ARE byte+4 of the instruction, and
    isadb.instr_length's own length rule for the WHOLE low-nibble-9 float-ALU
    group (2-source AND 3-source alike) is `6 + 2*(byte4 & 0x3)` -- i.e. the
    field's OWN LOW 2 BITS are the instruction-LENGTH selector, not a free
    semantic bit (discovered while building this experiment's falu2_ext/
    falu3_srcmod12/falu_srcmod12b cases: constructing them with ctrl=0
    silently decoded back as a 6-byte falu2/falu2i on round-trip -- see
    PRE_REGISTRATION.md "pilot finding"/RESULTS.md). This reframes EXP-0089's
    own finding that ctrl/ctrl_lo bits 0/1 are "always dangerous" and the
    SOLE source of every cross-run-nondeterministic case in that experiment:
    flipping them does not corrupt a semantic field, it RECLASSIFIES THE
    INSTRUCTION'S OWN LENGTH, desyncing the decode of every subsequent byte
    in the program -- explaining both the fault-heavy and the
    boundary-dependent-nondeterministic character of that result without
    needing a new semantic mechanism. `length_low2` MUST be 0 (6B), 1 (8B),
    2 (10B) or 3 (12B) to keep the instruction's OWN declared length; passing
    any other value is a deliberate desync probe, not a field test, and the
    caller must say so explicitly (see H2_SRCMOD12B_NOLOOP's one
    exploratory case). `ctrl_hi5` sets the field's semantically-meaningful
    upper 5 bits (bits 2-6, i.e. mask/value >> 2)."""
    return (length_low2 & 0x3) | ((ctrl_hi5 & 0x1F) << 2)


def falu2_ext_raw(dst, srcA_reg7, srcB_reg7, opflags5, ctrl_hi5=0, mod_hi4=0xC,
                   mod_lo=0, srcB_neg=0, srcB_imm=0, ext_tail=0,
                   srcA_size=1, srcB_size=1, op="fadd", _ctrl_len=1):
    """8B falu2_ext (db.json match byte0 nibble9, bit17=0,bit18=1; ACTUAL
    length selector per isadb.instr_length is byte+4&3==1, held fixed here
    -- see `_length_ctrl`). Shares falu2's base-48-bit field layout
    (srcA_reg bits9-15, opflags bits19-23, srcB_reg bits25-31, ctrl
    bits32-38, mod_hi bits44-47) -- same bit POSITIONS as falu2, confirmed
    by direct db.json match-table inspection (see module docstring's
    addressing-scope note); NOT itself independently re-validated by
    splice in this experiment beyond what H1's own bit15/31 group
    establishes. `ext_tail` is the extra 16-bit tail this 8-byte form adds
    beyond falu2's 6 bytes; UNCHARACTERIZED, default 0."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    ctrl = _length_ctrl(_ctrl_len, ctrl_hi5)
    return isadb.assemble("falu2_ext", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl,
        "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7, "srcB_neg": srcB_neg & 1,
        "mod_hi": mod_hi4 & 0xF, "ext_tail": ext_tail & 0xFFFF,
    })


def falu3_srcmod12_raw(dst, srcA_reg7, srcB_reg7, opflags5, ctrl_hi5=0, mod_hi4=0xC,
                        mod_lo=0, srcB_neg=0, srcB_imm=0, ext_srcmod=0,
                        srcA_size=1, srcB_size=1, _ctrl_len=3):
    """12B falu3_srcmod12 (3-source FMA-shaped, db.json match byte0
    nibble9,bit17=1; ACTUAL length selector byte+4&3==3, held fixed here --
    see `_length_ctrl`). Shares falu2's base-48-bit srcA/srcB/opflags
    layout. NOTE (found while building this experiment): `assemble()`
    composes match-constant bits and field bits with OR, never AND/clear,
    so a field whose bit RANGE overlaps a match-forced bit cannot reach any
    value inconsistent with that match condition -- opsel (bits16-18) here
    overlaps the match's forced bit17=1, so only opsel in {2,3,6,7} is
    reachable regardless of what is requested (an earlier version of this
    builder requested opsel=4 "fadd" and silently got opsel=6 "fma" back;
    caught by this experiment's own round-trip self-check before any
    hardware run). This builder does not expose `op` at all: this
    experiment never reads falu3_srcmod12's OWN computed result (dst is a
    throwaway register) -- only whether a LATER, INDEPENDENT instruction's
    read of srcA/srcB survived -- so the specific reachable opsel value is
    immaterial to what is being tested. The 48-bit `ext_srcmod` tail (bits
    48-95, presumably the 3rd source + its own retention bits) is
    UNCHARACTERIZED and NOT independently addressed by this experiment
    (out of scope -- see PRE_REGISTRATION.md); default 0 throughout."""
    ctrl = _length_ctrl(_ctrl_len, ctrl_hi5)
    return isadb.assemble("falu3_srcmod12", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": 6, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl,
        "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7, "srcB_neg": srcB_neg & 1,
        "mod_hi": mod_hi4 & 0xF, "ext_srcmod": ext_srcmod & ((1 << 48) - 1),
    })


def falu_srcmod12b_raw(dst, srcA_reg7, srcB_reg7, opflags5, ctrl_hi5=0, mod_hi4=0xC,
                        mod_lo=0, srcB_neg=0, srcB_imm=0, ext_srcmod=0,
                        srcA_size=1, srcB_size=1, opsel_mod=4, _ctrl_len=3):
    """12B falu_srcmod12b (2-source, db.json match byte0 nibble9,bit17=0
    -- the EXP-0089 `loop_boundary` c1 family: opsel here is `mod`, not a
    typed opcode enum, unlike falu2's; ACTUAL length selector byte+4&3==3,
    held fixed here -- see `_length_ctrl`). Base-48-bit layout identical
    position-for-position to falu2. This is the family whose `ctrl` field
    EXP-0089 found to be 0/8-safe (incl. one GENUINE GPU HANG at bit2) --
    ONLY when executed inside a real loop; this experiment retests a subset
    of that field OUTSIDE a loop to separate the two confounded variables
    (see H2_SRCMOD12B_NOLOOP, PRE_REGISTRATION.md; SAFETY: single
    hang-candidate case, isolated, placed LAST in the whole capture
    sequence). `ctrl_hi5` bit0 (field bit2, absolute instruction bit 34)
    is EXP-0089's hang-implicated bit -- pass with care."""
    ctrl = _length_ctrl(_ctrl_len, ctrl_hi5)
    return isadb.assemble("falu_srcmod12b", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel_mod & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl,
        "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7, "srcB_neg": srcB_neg & 1,
        "mod_hi": mod_hi4 & 0xF, "ext_srcmod": ext_srcmod & ((1 << 48) - 1),
    })


# ---------------------------------------------------------------------------
# memory family
# ---------------------------------------------------------------------------
ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED


def device_load(dst, index_reg, idx_off, elem_code=3, base_slot=1,
                 extmode=0, space=0x10, addr_mode=0x44, access_desc=0x20,
                 ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0):
    """14B device_load. EXP-0082/0083 + EXP-M4-13 R8 -- HW-VALIDATED."""
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
    """14B device_store. `extmode = 2*data_reg` is EXP-0090's HW-VALIDATED
    formula (finding_5), NARROW -- EXP-0099 showed it fails at r67, so this
    experiment restricts `data_reg` to the small/validated range (<64,
    normally <16) everywhere it is used. `addr_mode`: 0x54="store
    (ALU-computed data / base-relative)", 0x56="store (direct live
    load-result data; bit1 set)" -- literal bit-17 position, db.json's own
    enum; H2_DEVSTORE_ADDRMODE tests this bit as a THIRD independent
    instance of the same literal bit position (see H3)."""
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


# ---------------------------------------------------------------------------
# ibitcount -- HW-VALIDATED (EXP-0033, EXP-M4-13 R10, EXP-M4-14 direct
# splice) integer family. dst is reg<<1, src is reg<<2 (NOT falu2's
# convention -- db.json's own EXP-M4-14 provenance note, verbatim).
# srcdesc=0x5c ("bit6 set -> GPR source read normally") is the anchor's own
# validated value; op_enable bit1 set (0x02) is required for the op to
# compute at all (0x00/0x01/0x04/0x05 -> result forced 0, a SEPARATE gate
# from `cache`, per the same provenance note -- held fixed at the anchor's
# own value throughout this experiment, never swept).
# ---------------------------------------------------------------------------
def ibitcount_raw(dst_reg, src_reg, cache_bit17, fn_hi=0, form=5,
                   op_enable=2, srcdesc=0x5c, tail=4):
    """8B ibitcount (popcount when fn_hi=0/form=5, EXP-0033/EXP-M4-14
    default). `cache_bit17`: 1 -> byte+2=0x56 (own-result WRITTEN BACK,
    the anchor's natural value); 0 -> byte+2=0x54 (own-result BROKEN,
    EXP-M4-14 HW-VALIDATED same-instruction finding). `dst_reg`/`src_reg`
    are LOGICAL register numbers 0-63; this builder applies the
    HW-VALIDATED reg<<1 / reg<<2 scaling internally."""
    return isadb.assemble("ibitcount", {
        "fn_hi": fn_hi & 1, "form": form & 0xFF, "cache": cache_bit17 & 1,
        "dst": (dst_reg << 1) & 0xFF, "op_enable": op_enable & 0xFF,
        "src": (src_reg << 2) & 0xFF, "srcdesc": srcdesc & 0xFF, "tail": tail & 0xFF,
    })


def reg_move(dst, src_reg, src_flag=0):
    """4B compact register move. HW-VALIDATED scope: uniform-register
    sources only (EXP-0087); NOT used to read an ALU-written GPR anywhere
    in this experiment (EXP-0090/99/101 already closed that as a
    non-generalizing negative result)."""
    return isadb.assemble("reg_move_c1", {
        "dst": dst, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": 0x0, "op_desc": 0x08,
    })


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def get_sr_tid(dst=0):
    """4B get_sr: dst = thread_position_in_grid. Ported VERBATIM from
    EXP-0112-m4-program-generator/isa_helpers.py (our own prior tooling,
    reuse across experiments explicitly encouraged by SUBAGENT_BRIEF.md).
    Needed here ONLY by build_cf_topbit_program's reused P3/CF skeleton
    (EXP-0090 byte pattern) and by H3's per-lane-divergent MODE A variant."""
    return isadb.assemble("get_sr", {"form": 1, "dst": dst, "sr_sel": 0xA0,
                                       "dp_width": 0x10, "dp_marker": 6, "dst_hi": 0})


# EXP-0101's corrected device_load: extmode and dst_lo/dst_ext9 are
# INDEPENDENT caller-supplied values (EXP-M4-13's dst=dst_lo|(dst_ext9<<2)
# formula, used by this file's own device_load() above for the WRITE-side
# shape, does NOT predict the register a later falu2/falu2i consumer must
# reference -- that is extmode=2*target_register, EXP-0101 HW-VALIDATED,
# 29 cases two runs). Ported verbatim from
# EXP-0101-m4-synthesis-blockers/isa_helpers.py.
DST_TOKEN_KNOWNGOOD = (1, 1)   # the one HW-confirmed (dst_lo,dst_ext9) pair
                                # for addr_mode=0x44/ld_format=0x11 (terminal
                                # scalar 32-bit load), EXP-0101 census anchor.


def device_load_fixed(index_reg, idx_off, elem_code, base_slot, extmode,
                       dst_lo, dst_ext9, space=0x10, addr_mode=0x44,
                       access_desc=0x20, ld_format=0x11, ldform_hi11=0x10,
                       reserved7=0, reserved13=0):
    """14B device_load, EXP-0101's corrected formula (verbatim port):
    `extmode = 2 * target_register` addresses the register a LATER
    falu2/falu2i consumer will reference via its own srcA_reg/srcB_reg
    field; `dst_lo`/`dst_ext9` is a SEPARATE, independently-required field,
    copied verbatim from a real compile (DST_TOKEN_KNOWNGOOD=(1,1) for this
    addr_mode/ld_format shape) -- never derived from the target register."""
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format, "dst_lo": dst_lo & 0x3, "dst_ext9": dst_ext9 & 0x7F,
        "idx_off": idx_off & 0x7FF, "ldform_hi11": ldform_hi11,
        "elem_size": 0x40 | ((elem_code & 0x7) << 1), "reserved13": reserved13,
    })


# ---------------------------------------------------------------------------
# H1 CF-boundary skeleton -- REUSES EXP-0112/EXP-0090's own HW-VALIDATED
# loop+if/else->select control-flow skeleton (carrier_cf.metal, "0 byte
# diffs against a genuine own-compile", captured/gated in EXP-0112's own
# two-run raw/). Every instruction is byte-for-byte identical to that
# skeleton EXCEPT the "arm_true" falu2i's srcA_reg field (this experiment's
# OWN H1 top-bit probe) -- everything else, including base_slot/buffer
# wiring, is copied unmodified so the skeleton's own HW-validation carries
# over unchanged. See EXP-0112/cf.py for the original, and this file's
# module-level docstring / PRE_REGISTRATION.md for why an extra
# instruction could NOT simply be appended (CARRIER_LEN=152 has zero
# slack -- confirmed by this experiment's own pilot compile of
# kernels/carrier_cf.metal, PROGRESS.md).
# ---------------------------------------------------------------------------
CF_CARRIER_LEN = 152
CF_SLOT_OUT, CF_SLOT_A, CF_SLOT_N = 0, 2, 1   # verbatim from EXP-0112/cf.py


def build_cf_topbit_program(a_val, n_val, srcA_reg_byte, cond_override=None):
    """Byte-for-byte EXP-0112/cf.py::build_cf_program EXCEPT the "arm_true"
    falu2i (`r2 = acc*2.0`, reads the loop-carried accumulator r1) has its
    FULL 7-bit srcA_reg field passed explicitly as `srcA_reg_byte` instead
    of the skeleton's own natural compiled value (0x41 = top-bit SET, low6=1
    -- i.e. this instruction, as REALLY compiled by EXP-0090's own P3
    program, already addresses its source with the top bit set). Passing
    0x41 reproduces the untouched skeleton exactly (round-trip-identical to
    EXP-0112's own bytes); 0x01 clears ONLY the top bit, same low6=1 (same
    nominal register), everything else unchanged -- this experiment's own
    H1 addressing/retention probe across a REAL loop+if/else reconvergence
    boundary. `falu_srcmod12b`'s sibling "arm_false" (`r3 = acc-3.0`,
    instruction bit-for-bit UNTOUCHED, srcA_reg=0x41 always) is a SECOND,
    independent reader of the SAME register r1, executed immediately after
    the top-bit-varied instruction and BEFORE isel10 overwrites r1 -- so
    choosing `cond_override`/`a_val`/`n_val` such that isel10 selects the
    FALSE arm (r3) instead of TRUE (r2) turns this SAME construction into a
    retention probe (does varying the EARLIER instruction's top bit corrupt
    a LATER, independent reader of the same register?) with ZERO extra
    instruction bytes -- see PRE_REGISTRATION.md H1_CF."""
    instrs = []
    instrs.append(get_sr_tid(dst=0))
    instrs.append(isadb.assemble("device_load", {
        "space": 0x10, "addr_mode": 0x54, "extmode": 4, "base_slot": CF_SLOT_A,
        "index_reg": 0, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
        "dst_lo": 1, "dst_ext9": 1, "idx_off": 0, "ldform_hi11": 0x10,
        "elem_size": 0x46, "reserved13": 0}))                              # r5 = a[tid] (acc)
    instrs.append(isadb.assemble("device_load", {
        "space": 0, "addr_mode": 0x44, "extmode": 2, "base_slot": CF_SLOT_N,
        "index_reg": 0, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
        "dst_lo": 0, "dst_ext9": 0, "idx_off": 0, "ldform_hi11": 0x10,
        "elem_size": 0x46, "reserved13": 0}))                              # r0 = n[tid] (count)
    cond = 6 if cond_override is None else cond_override
    instrs.append(isadb.assemble("icmp_pred", {"dst_pred": 0, "srcA": 0x5, "neg": 1, "cmpmode": 2,
                                                  "opdesc_hi": 2, "srcB": 0x80, "cond": cond, "opclass": 0xC2}))
    instrs.append(isadb.assemble("if_push_pred", {"pred": 1, "scope": 0x54, "level": 1}))
    instrs.append(isadb.assemble("jump_cond", {"cf_scope": 0x54, "offset": 0x40, "reserved": 0}))
    instrs.append(isadb.assemble("reg_move_c0", {"dst": 3, "src_reg": 0, "src_flag": 0, "src_class": 2, "op_desc": 0}))
    instrs.append(isadb.assemble("if_push", {"scope": 0x54, "scope_kind": 0x1A}))
    instrs.append(isadb.assemble("iadd2", {"addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
                                             "store_en": 0, "b2_fmt": 1, "dst": 6, "opmode": 3, "srcB_imm": 2,
                                             "srcB_imm_hi": 0, "srcB_ext": 0xC, "srcA": 0x88, "opc_tail": 0x15,
                                             "opc_tail2": 4}))                                      # i++
    instrs.append(isadb.assemble("icmp_pred", {"dst_pred": 0, "srcA": 0x7, "neg": 1, "cmpmode": 3,
                                                  "opdesc_hi": 2, "srcB": 5, "cond": 6, "opclass": 0}))
    instrs.append(isadb.assemble("scoreboard_fence", {"kind": 0, "scope": 0, "mask": 0}))
    instrs.append(isadb.assemble("falu2i", {"dst": 1, "imm_flag": 1, "imm_mant": 4, "imm_exp": 0xB, "opsel": 4,
                                              "imm_sign": 0, "opflags": 3, "srcA_size": 1, "srcA_reg": 1,
                                              "ctrl_lo": 0, "mods": 0}))                             # acc += 1.5
    instrs.append(isadb.assemble("ret", {"linkmode": 4, "scoreboard": 0x22}))
    instrs.append(isadb.assemble("jump", {"branch_ctrl": 0x54, "offset": (-30) & ((1 << 48) - 1), "link": 0}))
    instrs.append(isadb.assemble("pop_reconverge", {"scope": 4, "scope_kind": 2, "reserved": 0}))
    instrs.append(isadb.assemble("pop_reconverge", {"scope": 4, "scope_kind": 1, "reserved": 0}))
    # ---- the ONE varied instruction (H1's own probe) ----
    instrs.append(isadb.assemble("falu2i", {"dst": 2, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xC, "opsel": 5,
                                              "imm_sign": 0, "opflags": 2, "srcA_size": 1,
                                              "srcA_reg": srcA_reg_byte & 0x7F, "ctrl_lo": 0, "mods": 0}))  # r2 = acc*2.0
    # ---- UNTOUCHED sibling: a second, independent, LATER reader of r1 ----
    instrs.append(isadb.assemble("falu2i", {"dst": 3, "imm_flag": 1, "imm_mant": 4, "imm_exp": 0xC, "opsel": 4,
                                              "imm_sign": 1, "opflags": 2, "srcA_size": 1, "srcA_reg": 0x41,
                                              "ctrl_lo": 0, "mods": 0}))                              # r3 = acc-3.0
    instrs.append(isadb.assemble("isel10", {"dst": 1, "cmpA": 3, "opsel": 1, "cmpB": 0xC, "cmp_mode": 0x82,
                                              "selTrue": 4, "cc": 2, "flags": 2, "selFalse_file": 0x80,
                                              "selFalse": 6}))
    instrs.append(device_store(0, 0, CF_SLOT_OUT, data_reg=1))  # index_reg=0, VERBATIM from cf.py
    instrs.append(stop())
    prog = build_program(instrs, CF_CARRIER_LEN)
    assert_round_trip(prog)

    acc = a_val
    guard_taken = (cond == 6)
    if guard_taken:
        for _ in range(max(0, int(n_val))):
            acc = f32(acc + 1.5)
    arm_true = f32(acc * 2.0)
    arm_false = f32(acc - 3.0)
    natural_select_true = acc > 100.0
    out0 = arm_true if natural_select_true else arm_false
    return prog.hex(), out0, {"acc": acc, "natural_select_true": natural_select_true,
                                "arm_true": arm_true, "arm_false": arm_false}


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=13):
    """Concatenate instruction byte-strings (must already end with stop()),
    pad with mov_imm(pad_dst,0) 2-byte instructions to EXACTLY carrier_len.
    pad_dst=13 is a register never used as a live seed/result target."""
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

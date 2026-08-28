#!/usr/bin/env python3
"""EXP-0113 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes via `tools/agx-isa`'s
own, READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing
a captured byte string except where explicitly noted (the LOADFWD group,
which grafts onto a real compiled instance's OTHER, untouched instructions
by design -- see casematrix.py's own docstring for why).

Register plan (flat register-index convention, matches EXP-0090/EXP-0099/
EXP-0101/EXP-0105's own SEED_CHECK / CAND_BANK convention so results are
directly comparable):
  R_IDX       = 15  index register for device_load/store addressing, always
                    holds 0 (mov_imm(15,0)) -- HW-VALIDATED EXP-0031/EXP-0082.
  R_UNWRITTEN = 14  NEVER written by any falu2/falu2i-family case.
  R_LOW       = 3   the "known low" seed register (falu2i), matches
                    EXP-0099/EXP-0105's own convention exactly.
  R_HIGH_FIELD= 67  the srcA/srcB FIELD VALUE under test for register-64-95
                    addressing (67's low 6 bits == 3, matches EXP-0099's own
                    aliasing-detection design).
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
R_LOW = 3
R_HIGH_FIELD = 67


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
# single-instruction builders (packed-field float ALU family)
# ---------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031."""
    return isadb.assemble("mov_imm", {"dst": dst, "imm8": imm8 & 0xFF})


def falu2i_raw(dst, srcA_reg7, k, opflags4=1, ctrl_lo=0, mods=0, srcA_size=1, op="fadd"):
    """6B falu2i. HW-VALIDATED field layout (EXP-0006, EXP-0090's default
    opflags=1 'one real + don't-care' pattern). Verbatim convention from
    EXP-0099/EXP-0105's own isa_helpers.py."""
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


def falu2_raw(dst, srcA_reg7, srcB_reg7, opflags5=0, mod_hi4=0, ctrl=0, mod_lo=0,
              srcB_neg=0, srcA_size=1, srcB_size=1, op="fadd"):
    """6B falu2 (register-register). `opflags5` bits: bit0=instr-bit19
    (EXP-0086 srcA last-use), bit1=bit20 (srcB last-use), bit2=bit21
    (EXP-0099 'destination publication', REFUTED), bit3=bit22, bit4=bit23
    (EXP-0105: general silent corruptors). `ctrl` is the 7-bit byte+4
    field: bits0/1 corrupting (EXP-0105), bits2/3 inert (EXP-0105),
    bits4-6 UNTESTED before this experiment (THIS experiment's own
    H1_CTRL_BITS_4_6 group closes that gap). `mod_hi4` bit0=instr-bit44
    (EXP-0105: corrupting); bits1-3/route inert for ALU-sourced operands
    (EXP-0099 H4)."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl & 0x7F,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi4 & 0xF,
    })


def get_sr_raw(dst, sr_sel, form=1, dp_width=16, dp_marker=6):
    """4B get_sr. dst = dst_lo | (dst_hi<<4), reaching r0..r127 (db.json
    field table; HW-VALIDATED 0-95 round-trip via the get_sr+device_store
    coupled-index-register technique, EXP-0092 GLIO-A02). `form=1` matches
    the compiler's OWN emitted value for the position-in-grid SR family
    (THIS experiment's own pilot-phase finding, PROGRESS.md Milestone 1:
    a freshly compiled kernel's `gid = thread_position_in_grid.x` get_sr
    used form=1, byte0=0x1c for dst=1, not form=0/0x14 as EXP-0092/
    EXP-0105's own helper defaulted -- functionally inert per db.json's
    own semantics note, but matched here to minimize confounders).
    `dp_width=16` matches EXP-0092's OWN dstsweep evidence: registers
    64-95 round-tripped correctly using dp_width=16 (the SAME value used
    for dst<64), contradicting db.json's own untested 'dp_width=0x50 for
    dst>=64' enum annotation -- see RESULTS.md for the proposed
    correction."""
    dst_lo = dst & 0xF
    dst_hi = (dst >> 4) & 0x7
    return isadb.assemble("get_sr", {
        "form": form & 1, "dst": dst_lo, "sr_sel": sr_sel & 0xFF,
        "dp_width": dp_width & 0xFF, "dp_marker": dp_marker & 0x1F, "dst_hi": dst_hi,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                  space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                  st_format_ext=0, st_desc_hi=0x24, elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store. `extmode = 2*data_reg` is EXP-0090's own
    HW-VALIDATED formula for LOW data registers (r0-r20ish, EXP-0101).
    `index_reg` is the SEPARATE, EXP-0092-VALIDATED register-VALUE-as-
    address-index mechanism (GLIO-A02 dstsweep, 0-95 round-trip). NOTE
    (THIS experiment's own pilot finding, PROGRESS.md Milestone 1):
    index_reg-based addressing has a HARD 16-BIT CEILING -- storing to
    element index >= 65536 silently fails (reads back as the buffer's
    zero-initialized default) regardless of the VALUE being stored;
    exact boundary 65535 (last correct) / 65536 (first silently-lost),
    reproducible. Never used above that ceiling in this experiment's
    gated matrix."""
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


def reg_move_c9_raw(dst, src_reg, src_flag=0, src_class=0, op_desc=0xC0):
    """4B reg_move_c9. THIS is byte0=0x2b's decode family: assemble('reg_move_c9',
    {dst=2,src_reg=0,src_flag=0,src_class=0,op_desc=0xC0}) reproduces
    EXP-0087's own undecoded '2b0009c0' byte-for-byte (verified statically,
    see RESULTS.md H2). db.json's field table already covers this shape;
    the reason tools/agx-isa's disassembler still reports it 'undecoded'
    is a NARROWER defect in isadb.py's instr_length() byte0=0xNb length
    rule, which does not recognize byte+2 low-nibble==9 -- a length-rule
    coverage gap, not a wrong field mapping (see RESULTS.md proposed
    correction). Independent of that gap, THIS function bypasses
    decode_one()/instr_length() entirely (assemble() only), so it is
    unaffected."""
    return isadb.assemble("reg_move_c9", {
        "dst": dst & 0xF, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": src_class & 0xF, "op_desc": op_desc & 0xFF,
    })


def reg_move_c1_raw(dst, src_reg, src_flag=0, src_class=2, op_desc=0):
    """4B reg_move_c1 -- EXP-0101's own characterized family (byte+2 low-
    nibble 1). Reused here (H3) to probe the src_reg addressing rule
    against the kernel's own buffer/uniform layout."""
    return isadb.assemble("reg_move_c1", {
        "dst": dst & 0xF, "src_reg": src_reg & 0x7F, "src_flag": src_flag & 1,
        "src_class": src_class & 0xF, "op_desc": op_desc & 0xFF,
    })


def iminmax_raw(dst, srcA_byte, srcB_byte, sel=6, fmt=3, selhi=0):
    """6B iminmax (int/float min/max). `srcA`/`srcB` (byte+3/byte+5) are
    PLAIN 8-bit register-index bytes (structurally UNLIKE falu2's packed
    7-bit+size field) -- per db.json / EXP-0105's own pilot compile.
    `sel=6` is imax (HW-VALIDATED op-select). This helper is used for
    STANDALONE constructions where srcA/srcB are meant literally; the
    LOADFWD group (device_load-fed) builds iminmax bytes directly via
    isadb.assemble (see casematrix.py) since it also needs a non-default
    `srcB` tail value copied from a compiled instance."""
    dst4 = dst & 0xF
    return isadb.assemble("iminmax", {
        "dst": dst4, "dst_full": ((dst4 << 1) | 1) & 0xFF, "fmt": fmt & 0x1F,
        "srcA": srcA_byte & 0xFF, "sel": sel & 0x7, "selhi": selhi & 0x1F,
        "srcB": srcB_byte & 0xFF,
    })


def device_load_a(R, base_slot=0):
    """14B device_load, THE EXACT field shape THIS experiment's own pilot
    phase (PROGRESS.md Milestone 2) extracted from a real compiled
    `int a=...; int b=...; out=max(a,b);` kernel's FIRST (non-terminal,
    addr_mode=0x54) load: space=16, extmode=0, access_desc=32,
    ld_format=17, idx_off=0, ldform_hi11=16, elem_size=70. `dst_lo`/
    `dst_ext9` are set from R via dst = dst_lo | (dst_ext9<<2) (the
    formula THIS experiment's own pilot phase used to relocate the
    load's target across an R sweep -- NOT claimed to be the general
    dst-addressing formula; see RESULTS.md H1/LOADFWD for the full,
    nuanced finding: this construction's apparent success is EPHEMERAL
    pipeline forwarding to an immediately-following, field-matching
    consumer, NOT proof of persistent register-file semantics)."""
    return isadb.assemble("device_load", {
        "space": 16, "addr_mode": 0x54, "extmode": 0, "base_slot": base_slot & 0xFF,
        "index_reg": 1, "access_desc": 32, "reserved7": 0, "ld_format": 17,
        "dst_lo": R & 0x3, "dst_ext9": (R >> 2) & 0x7F,
        "idx_off": 0, "ldform_hi11": 16, "elem_size": 70, "reserved13": 0,
    })


def device_load_b(base_slot=1):
    """14B device_load, the SAME pilot-extracted kernel's SECOND
    (terminal, addr_mode=0x44) load -- unchanged in every LOADFWD case
    (dst_lo=1, dst_ext9=1, extmode=4)."""
    return isadb.assemble("device_load", {
        "space": 0, "addr_mode": 0x44, "extmode": 4, "base_slot": base_slot & 0xFF,
        "index_reg": 1, "access_desc": 32, "reserved7": 0, "ld_format": 17,
        "dst_lo": 1, "dst_ext9": 1,
        "idx_off": 0, "ldform_hi11": 16, "elem_size": 70, "reserved13": 0,
    })


def loadfwd_iminmax(srcA, srcB=192, dst=0):
    """6B iminmax matching the pilot-extracted compiled instance's OWN
    tail byte value (srcB=0xC0=192 -- NOT a plausible plain register
    index; db.json's own srcB field position for this instruction is
    itself part of the flagged anomaly, see RESULTS.md). `srcA` is the
    field under test."""
    return isadb.assemble("iminmax", {
        "dst": dst & 0xF, "dst_full": ((dst & 0xF) << 1) | 1, "fmt": 3,
        "srcA": srcA & 0xFF, "sel": 6, "selhi": 0, "srcB": srcB & 0xFF,
    })


def loadfwd_store(base_slot, idx_off=0):
    """14B device_store matching the pilot-extracted compiled instance's
    OWN store shape exactly (space=0, addr_mode=0x54, access_desc=33,
    st_format=17, st_desc_hi=36, elem_size=17, extmode=0 -- 'implicit
    preceding-op' data forwarding, per device_store's own db.json
    semantics note)."""
    return isadb.assemble("device_store", {
        "space": 0, "addr_mode": 0x54, "extmode": 0, "base_slot": base_slot & 0xFF,
        "index_reg": 1, "access_desc": 33, "reserved7": 0, "st_format": 17,
        "st_format_ext": 0, "idx_off": idx_off & 0x7FF, "st_desc_hi": 36,
        "elem_size": 17, "reserved13": 0,
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
    this experiment's SEED_CHECK/H1_ALIAS/CTRL case matrices."""
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


def assert_reg_move_c9_program(hexbytes, c9_offset, c9_fields):
    """Targeted verification for programs containing a `reg_move_c9`
    instruction. `isadb.disassemble()` cannot round-trip these programs
    whole: isadb.py's `instr_length()` byte0=0xNb length rule has no
    branch for byte+2 low-nibble==9 (H2's own finding, RESULTS.md) --
    NOT a wrong field mapping (db.json's `reg_move_c9` match/field table
    is independently confirmed correct, see below), a narrower defect in
    the hand-written length-rule dispatcher only, which this helper
    documents and works around rather than silently skipping validation.

    Checks, in place of the whole-stream round trip:
    1. hexbytes[c9_offset:c9_offset+4] == isadb.assemble('reg_move_c9',
       c9_fields) exactly (the instruction bytes are exactly what the
       named fields assemble to -- this IS a round trip, just scoped to
       the one instruction isadb.py's own length dispatcher cannot
       currently reach).
    2. Every OTHER instruction in the program (everything strictly
       before c9_offset, and everything from c9_offset+4 onward) DOES
       round-trip cleanly via the normal disassemble()+assemble() path,
       proving this program's only unparseable region is the single,
       precisely-diagnosed reg_move_c9 instruction, not some other,
       undisclosed defect.
    """
    want = isadb.assemble("reg_move_c9", c9_fields)
    got = hexbytes[c9_offset:c9_offset + 4]
    if got != want:
        raise AssertionError("reg_move_c9 bytes mismatch at +0x%x: %s != %s" %
                              (c9_offset, got.hex(), want.hex()))
    before = hexbytes[:c9_offset]
    after = hexbytes[c9_offset + 4:]
    for chunk, label in ((before, "before"), (after, "after")):
        if not chunk:
            continue
        recs, leftover = isadb.disassemble(chunk)
        if leftover:
            raise AssertionError("reg_move_c9 program: %s-segment round-trip "
                                  "leftover %d bytes: %s" % (label, len(leftover), leftover.hex()))
        off = 0
        for r in recs:
            g = isadb.assemble(r["mnemonic"], r["fields"])
            w = chunk[off:off + r["length"]]
            if g != w:
                raise AssertionError("reg_move_c9 program: %s-segment mismatch "
                                      "at +0x%x (%s)" % (label, off, r["mnemonic"]))
            off += r["length"]
    return True

#!/usr/bin/env python3
"""EXP-0105 shared instruction-construction helpers.

Every function here builds ONE instruction's raw bytes via `tools/agx-isa`'s
own, READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing
a captured byte string. Field values are either (a) HW-VALIDATED by a prior
experiment and cited, (b) empirically extracted from OUR OWN freshly
compiled MSL (see `work/iminmax_probe.metal` / PROGRESS.md -- the `fmt`/
`selhi`/`dst_full` defaults for `iminmax` and the `form`/`dp_width`/
`dp_marker` defaults for `get_sr`), or (c) the literal value under test.

Register plan (flat register-index convention, matches EXP-0090/EXP-0099):
  R_IDX       = 15  index register for device_load/store addressing, always
                    holds 0 (mov_imm(15,0)) -- HW-VALIDATED EXP-0031/EXP-0082.
  R_UNWRITTEN = 14  NEVER written by any program in this experiment.
  R_LOW       = 3   the "known low" seed register (mov_imm or falu2i, per
                    test family) -- matches EXP-0099's exact convention so
                    the register-64-95 aliasing test is directly comparable.
  R_HIGH_FIELD= 67  the srcA/srcB FIELD VALUE under test for register-64-95
                    addressing (67's low 6 bits == 3, the SAME low register
                    R_LOW lives in -- EXP-0099's exact aliasing-detection
                    design, reused here on a DIFFERENT, independently
                    validated instruction family, iminmax, as the "second
                    method" CODEX step 8 calls for). No case ever WRITES a
                    genuine register 67 via any path OTHER than get_sr (used
                    only in the SEEDED group, where it is the deliberate
                    subject of the test).
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
# single-instruction builders
# ---------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031."""
    return isadb.assemble("mov_imm", {"dst": dst, "imm8": imm8 & 0xFF})


def falu2i_raw(dst, srcA_reg7, k, opflags4=1, ctrl_lo=0, mods=0, srcA_size=1, op="fadd"):
    """6B falu2i. HW-VALIDATED field layout (EXP-0006, EXP-0090's default
    opflags=1 'one real + don't-care' pattern). Reused verbatim from
    EXP-0099's isa_helpers.py -- only to SEED a known low float value into
    R_LOW; the field under test in THIS experiment is falu2's srcA_reg/
    srcB_reg CANDIDATE-BIT sweep (CAND_BANK group), not this seeding path."""
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
    """6B falu2 (register-register). EVERY bit explicit -- this is the
    CAND_BANK candidate-field-under-test builder. `opflags5` bits:
    bit0=instr-bit19 (EXP-0086 srcA last-use, HW-VALIDATED), bit1=bit20
    (srcB last-use), bit2=bit21 (EXP-0099 'destination publication',
    HW-REFUTED as a register-addressing mechanism), bit3=bit22, bit4=bit23
    (UNTESTED before this experiment -- the CAND_BANK candidates). `ctrl`
    is the untested 7-bit byte+4 field (another CAND_BANK candidate).
    `mod_hi4` bit0=instr-bit44 (UNTESTED before this experiment -- the
    remaining bit of the 4-bit mod_hi field whose bits1-3/45-47 EXP-0099
    already tested and found inert for load-to-ALU 'route').
    """
    opsel = {"fadd": 4, "fmul": 5}[op]
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x7F,
        "opsel": opsel, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x7F, "ctrl": ctrl & 0x7F,
        "srcB_imm": 0, "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi4 & 0xF,
    })


def iminmax_raw(dst, srcA_byte, srcB_byte, sel=6, fmt=3, selhi=0):
    """6B iminmax (int/float min/max). `srcA`/`srcB` (byte+3/byte+5) are
    PLAIN 8-bit register-index bytes -- confirmed empirically in THIS
    experiment's own pilot compile (`work/iminmax_probe.metal`, own-MSL,
    OWN-SHADER): a real compiled `int a=mem[tid]; int b=mem[tid+1];
    out[tid]=max(a,b);` kernel emitted `02 01 1e 05 06 c0` with srcA=5
    matching EXACTLY the register the preceding device_load wrote 'a'
    into (dst=1|(1<<2)=5) -- i.e. the field holds the LITERAL register
    number, not a (reg<<1)|size packed value (unlike falu2/iadd2's own
    source fields). `fmt=3`/`selhi=0` are the SAME two field values that
    compiled instance used (structurally 'INFERRED' per db.json's own
    provenance note, but now empirically anchored to a real, dispatched-
    context compiled value rather than guessed). `sel=6` is imax
    (HW-VALIDATED op-select, EXP-M4-13 R2 byte-diff on an 8-register
    sweep). dst nibble reaches r0-r15 only (compact form, matches falu2's
    own dst-nibble cap); dst_full is the redundant (dst<<1)|size byte the
    real compile also carried (dst=0 -> dst_full=1, confirmed identity).
    """
    dst4 = dst & 0xF
    return isadb.assemble("iminmax", {
        "dst": dst4, "dst_full": ((dst4 << 1) | 1) & 0xFF, "fmt": fmt & 0x1F,
        "srcA": srcA_byte & 0xFF, "sel": sel & 0x7, "selhi": selhi & 0x1F,
        "srcB": srcB_byte & 0xFF,
    })


def get_sr_raw(dst, sr_sel, form=0, dp_width=16, dp_marker=6):
    """4B get_sr. dst = dst_lo | (dst_hi<<4), reaching r0..r127 (db.json
    field table; HW-VALIDATED 0-95 round-trip via the get_sr+device_store
    coupled-index-register technique, EXP-0092 GLIO-A02, dstsweep group,
    tested at reg in {0,1,15,16,31,32,47,48,63,64,79,80,87,88,94,95} plus
    the 96-127 fault boundary). `form=0, dp_width=16, dp_marker=6` are
    EXP-0092's own SRPROBE_V_ANCHOR field values (sr_sel=0x82 compiled
    anchor), which that experiment's srsweep group proved work UNCHANGED
    across the ENTIRE sr_sel=0x00-0xFF space (256/256 cases, no fault) --
    i.e. these three fields do not need to vary per sr_sel or per dst.
    NOTE (proposed db.json correction, see RESULTS.md): db.json's own
    `dp_width` enum claims `0x50`='top dst bank (dst>=r64)' is needed for
    a high dst -- EXP-0092's OWN dstsweep data contradicts this: registers
    64-95 (including 64,79,80,87,88,94,95) round-tripped correctly using
    dp_width=16 (the SAME value used for dst<64), never 0x50. This
    experiment reuses dp_width=16 for dst=67, consistent with that
    stronger, already-HW-VALIDATED evidence, not with the untested enum
    annotation.
    """
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
    HW-VALIDATED formula (finding_5), reused here ONLY for LOW data
    registers (r0-r13, well within EXP-0090's own validated range -- this
    experiment never uses it for a data register >=64, sidestepping
    EXP-0099's own finding that the formula does NOT extend past small
    registers). `index_reg` is the SEPARATE, EXP-0092-VALIDATED
    register-VALUE-as-address-index mechanism (GLIO-A02 dstsweep,
    0-95 round-trip) -- used in the SEEDED group to independently confirm
    a get_sr write landed in r67, decoupled from anything this experiment
    is testing about ALU source-operand addressing."""
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


def stop():
    return isadb.assemble("stop", {"reserved": 0})


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=13):
    """Concatenate instruction byte-strings (must already end with stop()),
    pad with mov_imm(pad_dst,0) 2-byte instructions to EXACTLY carrier_len.
    pad_dst=13 is a register never used as a live seed/result target in
    this experiment's case matrix."""
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

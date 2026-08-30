#!/usr/bin/env python3
"""EXP-0150 instruction-construction helpers.

Every builder emits ONE instruction's raw bytes through `tools/agx-isa`'s
READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing a captured
byte string, and never from an Apple binary. Field values are either
(a) HW-VALIDATED by a cited prior experiment, (b) the literal value under test in
this experiment's matrix, or (c) derived from this experiment's own analysis.

Shapes are kept byte-compatible with EXP-0101 / EXP-0141 `isa_helpers.py` so the
three experiments' evidence composes; the differences are deliberate and marked:

  * `falu2i_raw` takes `mods` with NO default -- `mods` is the field under test
    here, so a silent default would be the whole experiment's confound.
  * `falu2_raw` likewise takes the whole of byte+5 (`mod_lo`/`srcB_neg`/`mod_hi`)
    with no default.
  * every synthesised program re-zeroes the index register immediately before its
    final store (see `sweepdefs.build_program`), because a swept `device_load`
    destination can otherwise land in that register.

Clean-room: OWN-SHADER + HW-PROBE. No Apple binary introspected.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only: assemble/disassemble/imm_encode/imm_decode)

# ---------------------------------------------------------------------------
# register plan (all < 64, so EXP-0112's [64,112] alias region is never entered)
# ---------------------------------------------------------------------------
R_A = 7        # primary source register (load destination or ALU seed)
R_B = 9        # secondary source register (falu2's srcB)
R_D = 8        # ALU destination (falu2/falu2i `dst` is a 4-bit nibble: r0..r15)
R_CAN = 10     # integrity-sentinel register
R_IDX = 14     # index register (mov_imm `dst` is 4 bits: r0..r15)
R_PAD = 13     # padding sink; padding sits AFTER stop() and never executes


def eff_reg(r):
    """The register a falu2/falu2i source field VALUE actually reads.

    `srcA_reg`/`srcB_reg` are 6 bits with an HW-TESTED-INERT top bit
    (EXP-0099/0105/0113/0119), so field value 71 reads r7 and 103 reads r39.
    Recorded per case so a reader never has to re-derive it."""
    return r & 0x3F


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def imm_value(k):
    """The EXACT value the hardware uses for a falu2i immediate k (round trip
    through isadb's HW-VALIDATED minifloat codec, EXP-0006)."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


# ---------------------------------------------------------------------------
# single-instruction builders
# ---------------------------------------------------------------------------
def mov_imm(dst, imm7, imm_top=0):
    """2B: d[dst] = imm7. HW-VALIDATED EXP-0031. EXP-0128: immediates must stay
    0..127 -- `imm_top` (values 128..255) SILENTLY ZEROES."""
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm7 & 0x7F,
                                      "imm_top": imm_top & 1})


def falu2i_raw(dst, srcA_reg7, k, mods, opflags4=1, ctrl_lo=0, srcA_size=1,
               op="fadd"):
    """6B falu2i (register + immediate).

    `mods` (bits 40-47, i.e. byte+5) is THE FIELD UNDER TEST and has no default.
    EXP-0101 established mods=0xC0 for a device_load-sourced operand; EXP-0141's
    pilot note says a mov_imm-sourced operand needs 0x00 and BREAKS at 0xC0.
    This experiment sweeps all 256 values under both provenances."""
    opsel = {"fadd": 4, "fmul": 5, "fma": 6}[op]
    b1, sign = isadb.imm_encode(k)
    return isadb.assemble("falu2i", {
        "dst": dst & 0xF, "imm_flag": b1 & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo, "mods": mods & 0xFF,
    })


def falu2_raw(dst, srcA_reg7, srcB_reg7, byte5, opflags5=1, ctrl=0,
              srcA_size=1, srcB_size=1, op="fadd"):
    """6B falu2 (register-register).

    `byte5` is the WHOLE of byte+5 = mod_lo(bits40-42) | srcB_neg(bit43) |
    mod_hi(bits44-47). Bits 7:6 of this byte are instruction bits 47:46 -- the
    SAME literal bits as falu2i's `mods` bits 7:6, which is what makes the H3
    "are they the same bits" comparison meaningful rather than nominal."""
    opsel = {"fadd": 4, "fmul": 5, "fma": 6}[op]
    return isadb.assemble("falu2", {
        "dst": dst & 0xF, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x3F,
        "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "opsel": opsel, "opflags": opflags5 & 0x1F, "srcB_size": srcB_size,
        "srcB_reg": srcB_reg7 & 0x3F, "srcB_reg_top": (srcB_reg7 >> 6) & 1,
        "ctrl": ctrl & 0x7F, "srcB_imm": 0,
        "mod_lo": byte5 & 0x7, "srcB_neg": (byte5 >> 3) & 1,
        "mod_hi": (byte5 >> 4) & 0xF,
    })


def falu2_byte5(mod_lo=0, srcB_neg=0, mod_hi=0xC):
    return (mod_lo & 0x7) | ((srcB_neg & 1) << 3) | ((mod_hi & 0xF) << 4)


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED (load)


def device_load(index_reg, base_slot, extmode, dst_lo=1, dst_ext9=1, idx_off=0,
                elem_code=3, space=0x10, addr_mode=0x44, access_desc=0x20,
                ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0,
                elem_size=None):
    """14B device_load. Defaults are the compiler-observed terminal scalar-32-bit
    shape (addr_mode=0x44, ld_format=0x11, ldform_hi11=0x10, access_desc=0x20,
    space=0x10) that EXP-0101 validated end to end and EXP-0141 swept.

    `extmode` is THE PRODUCER FIELD UNDER TEST. EXP-0141: destination register =
    extmode>>1, bit 0 don't-care, R reachable 0..63 only. Whether bits 7:6 are
    additionally (or instead) a FORM selector is H1."""
    if elem_size is None:
        elem_size = 0x40 | ((elem_code & 0x7) << 1)
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format & 0x3F, "dst_lo": dst_lo & 0x3,
        "dst_ext9": dst_ext9 & 0x7F, "idx_off": idx_off & 0x7FF,
        "ldform_hi11": ldform_hi11 & 0x3F, "elem_size": elem_size & 0xFF,
        "reserved13": reserved13 & 0xFF,
    })


def device_store(index_reg, base_slot, data_reg=None, extmode=None, idx_off=0,
                 space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                 st_format_ext=0, st_desc_hi=0x24, elem_size=0x11,
                 reserved7=0, reserved13=0):
    """14B device_store. `extmode = 2*data_reg` is EXP-0090/0101's HW-VALIDATED
    source-register formula; EXP-0141 additionally found `2*R | 0xC0` accepted
    for an ALU-sourced store, which is one of the two-bit pairs under test here.
    `addr_mode` bit 1 is the data-source selector (EXP-0141 H2): 0x54 =
    ALU-computed, 0x56 = direct live load-result."""
    if extmode is None:
        if data_reg is None:
            raise ValueError("device_store needs data_reg or extmode")
        extmode = (data_reg << 1) & 0xFF
    return isadb.assemble("device_store", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7 & 0xFF,
        "st_format": st_format & 0xFF, "st_format_ext": st_format_ext & 0x7F,
        "idx_off": idx_off & 0x7FF, "st_desc_hi": st_desc_hi & 0x3F,
        "elem_size": elem_size & 0xFF, "reserved13": reserved13 & 0xFF,
    })


def stop():
    """4B program terminator (db.json `stop`, length 4)."""
    return isadb.assemble("stop", {"reserved": 0})


def assert_round_trip(b):
    """asm/disasm round trip (CODEX step 10). Raises on any mismatch."""
    recs, leftover = isadb.disassemble(b)
    if leftover:
        raise AssertionError("round-trip leftover %d bytes: %s"
                             % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = b[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s"
                                 % (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs

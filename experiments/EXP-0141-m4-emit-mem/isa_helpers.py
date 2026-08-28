#!/usr/bin/env python3
"""EXP-0141 instruction-construction helpers (memory/atomic/fence family).

Every builder emits ONE instruction's raw bytes through `tools/agx-isa`'s
READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing a
captured byte string. Field VALUES are either (a) HW-VALIDATED by a cited
prior experiment, (b) the literal value under test in this experiment's
sweep matrix, or (c) derived from this experiment's own OWN-SHADER
differential analysis. No Apple binary is inspected anywhere.

Architecture adapted from EXP-0101-m4-synthesis-blockers/isa_helpers.py
(itself from EXP-0099); the device_load/device_store/falu2/falu2i/mov_imm/
stop builders keep the same shapes so the two experiments' evidence
composes. NEW here: the sweep builders expose EVERY device_load and
device_store field independently (EXP-0101 fixed ld_format/ldform_hi11/
reserved7/reserved13/access_desc/space/addr_mode at their compiler-observed
constants; this experiment sweeps them).

Register plan (EXP-0090/0099/0101 convention):
  R_IDX_PREF   candidate index registers, holding 0 via mov_imm
  R_PAD = 13   padding sink (padding sits AFTER stop(), so never executes)
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only: assemble/disassemble/imm_encode/imm_decode)

R_PAD = 13
# mov_imm's `dst` field is 4 bits wide (db.json), so an index register we can
# zero with a 2-byte mov_imm must live in r0..r15.
R_IDX_PREF = (15, 14, 12, 11, 10, 9, 7, 6, 5, 4, 3, 2, 1, 0)


def alias_class(r):
    """EXP-0112 (M4): a register field value R in [64,112] silently aliases
    r(R mod 64); 126/127 fault. Used only to keep a sweep's own fixed
    registers out of the swept target's alias class -- never as a claim."""
    return r % 64 if r < 113 else r


def pick_idx_reg(*avoid):
    bad = {alias_class(r) for r in avoid}
    for cand in R_IDX_PREF:
        if alias_class(cand) not in bad:
            return cand
    raise ValueError("no free index register for avoid=%r" % (avoid,))


# ---------------------------------------------------------------------------
# float helpers
# ---------------------------------------------------------------------------
def imm_value(k):
    """The EXACT value the hardware uses for a falu2i immediate k (round trip
    through isadb's HW-VALIDATED minifloat codec, EXP-0006)."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# single-instruction builders
# ---------------------------------------------------------------------------
def mov_imm(dst, imm7, imm_top=0):
    """2B: d[dst] = imm7. HW-VALIDATED EXP-0031. EXP-0128: immediates must
    stay 0..127 -- `imm_top` (values 128..255) SILENTLY ZEROES."""
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm7 & 0x7F,
                                      "imm_top": imm_top & 1})


def falu2i_raw(dst, srcA_reg7, k, opflags4=1, ctrl_lo=0, mods=0xC0, srcA_size=1, op="fadd"):
    """6B falu2i (register + immediate). mods=0xC0 is EXP-0101's HW-VALIDATED
    requirement when the register operand is device_load-sourced."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    return isadb.assemble("falu2i", {
        "dst": dst & 0xF, "imm_flag": b1 & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo, "mods": mods,
    })


def falu2_raw(dst, srcA_reg7, srcB_reg7, opflags5=1, mod_hi4=0xC, ctrl=0, mod_lo=0,
              srcB_neg=0, srcA_size=1, srcB_size=1, op="fadd"):
    """6B falu2 (register-register). Verbatim shape from EXP-0099/0101."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    return isadb.assemble("falu2", {
        "dst": dst & 0xF, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x3F,
        "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "opsel": opsel, "opflags": opflags5 & 0x1F, "srcB_size": srcB_size,
        "srcB_reg": srcB_reg7 & 0x3F, "srcB_reg_top": (srcB_reg7 >> 6) & 1,
        "ctrl": ctrl, "srcB_imm": 0,
        "mod_lo": mod_lo, "srcB_neg": srcB_neg, "mod_hi": mod_hi4 & 0xF,
    })


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED (load)


def device_load(index_reg, base_slot, extmode, dst_lo=1, dst_ext9=1, idx_off=0,
                elem_code=3, space=0x10, addr_mode=0x44, access_desc=0x20,
                ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0,
                elem_size=None):
    """14B device_load, EVERY field caller-controllable.

    Defaults are the compiler-observed terminal scalar-32-bit shape
    (addr_mode=0x44, ld_format=0x11, ldform_hi11=0x10, access_desc=0x20,
    space=0x10) that EXP-0101 validated end to end. `extmode = 2*R` where R
    is the register a later falu2/falu2i reads (EXP-0101 HW-VALIDATED);
    (dst_lo, dst_ext9) = (1, 1) is EXP-0101's verbatim token, and is the
    quantity THIS experiment sweeps.
    """
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
    """14B device_store, EVERY field caller-controllable. `extmode =
    2*data_reg` is EXP-0090/0101's HW-VALIDATED source-register formula."""
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


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=R_PAD):
    """Concatenate instruction byte-strings, append stop(), pad with 2-byte
    mov_imm(pad_dst,0) to EXACTLY carrier_len. Padding sits AFTER stop() and
    therefore never executes."""
    body = b"".join(instrs) + stop()
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier %d" % (len(body), carrier_len))
    rem = carrier_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + mov_imm(pad_dst, 0) * (rem // 2)
    assert len(out) == carrier_len
    return out


def assert_round_trip(b):
    """asm/disasm round trip (CODEX step 10). Raises on any mismatch."""
    recs, leftover = isadb.disassemble(b)
    if leftover:
        raise AssertionError("round-trip leftover %d bytes: %s" % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = b[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s"
                                 % (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs

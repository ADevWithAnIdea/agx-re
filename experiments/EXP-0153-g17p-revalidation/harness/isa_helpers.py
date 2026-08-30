#!/usr/bin/env python3
"""EXP-0153 instruction-construction helpers (G17P revalidation).

Every builder emits ONE instruction's raw bytes through `tools/agx-isa`'s
READ-ONLY `isadb.assemble(mnemonic, fields)` -- never by hand-splicing a
captured byte string. This file is a MERGE of the equivalent helpers from
`EXP-0141-m4-emit-mem/isa_helpers.py` (device_load / device_store /
build_program / round trip) and `EXP-0138-m4-emit-falu/harness/isa_helpers.py`
(SEED / falu2_raw / falu2i_raw / seed / store_word), kept byte-for-byte
compatible so that a G17P case is the SAME construction the M4 experiment ran.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte here is produced by
`isadb.assemble` from our own field values, or is the compiled form of our own
MSL. No Apple binary is disassembled or introspected.

Python 3.9 compatible (the neo ships python3 3.9.6).
"""
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _tools_dir():
    """tools/ lives at <repo>/tools locally and at ~/agxre/tools on the neo.
    AGX_TOOLS overrides; otherwise fall back to the in-repo layout."""
    env = os.environ.get("AGX_TOOLS")
    if env:
        return Path(env)
    return EXP.parents[1] / "tools"


TOOLS = _tools_dir()
sys.path.insert(0, str(TOOLS / "agx-isa"))
import isadb  # noqa: E402  (read-only: assemble/disassemble/imm_encode/imm_decode)

# ---------------------------------------------------------------------------
# register plan (EXP-0090/0099/0101/0138 convention, unchanged)
# ---------------------------------------------------------------------------
R_PAD = 13            # padding sink; padding sits AFTER stop() so never executes
R_IDX = 15            # store index register, always 0
R_UNWRITTEN = 14      # never written -> reads exactly 0.0 (EXP-0087)

# mov_imm's `dst` field is 4 bits wide (db.json), so an index register we can
# zero with a 2-byte mov_imm must live in r0..r15.
R_IDX_PREF = (15, 14, 12, 11, 10, 9, 7, 6, 5, 4, 3, 2, 1, 0)

# 13 distinct EXACT minifloat fixed points seeded into r0..r12 (EXP-0138).
SEED = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0,
        7: 13.0, 8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0}


def alias_class(r):
    """EXP-0112 (M4): a register field value R in [64,112] silently aliases
    r(R mod 64); 126/127 fault. Used only to keep a sweep's own fixed
    registers out of the swept target's alias class -- never as a claim, and
    on G17P it is exactly what arm D re-measures."""
    return r % 64 if r < 113 else r


def pick_idx_reg(*avoid):
    bad = set(alias_class(r) for r in avoid)
    for cand in R_IDX_PREF:
        if alias_class(cand) not in bad:
            return cand
    raise ValueError("no free index register for avoid=%r" % (avoid,))


# ---------------------------------------------------------------------------
# scalar helpers
# ---------------------------------------------------------------------------
def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def i32(u):
    return struct.unpack("<i", struct.pack("<I", u & 0xFFFFFFFF))[0]


def imm_value(k):
    """The EXACT value the hardware uses for a falu2i immediate k (round trip
    through isadb's HW-VALIDATED minifloat codec, EXP-0006)."""
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


# ---------------------------------------------------------------------------
# single-instruction builders
# ---------------------------------------------------------------------------
def mov_imm(dst, imm7, imm_top=0):
    """2B: d[dst] = imm7. HW-VALIDATED EXP-0031 (M4). EXP-0140 (M4): the
    immediate is SEVEN bits -- `imm_top = 1` does not write at all."""
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm7 & 0x7F,
                                      "imm_top": imm_top & 1})


def mov_imm_raw(dst, imm8):
    """The 8-bit view of the same two bytes: imm7 = imm8 & 0x7F,
    imm_top = imm8 >> 7. Used by arm F to drive the 0..255 boundary."""
    return mov_imm(dst, imm8 & 0x7F, (imm8 >> 7) & 1)


def falu2i_raw(dst, srcA_reg7, k, opflags4=1, ctrl_lo=0, mods=0xC0,
               srcA_size=1, op="fadd"):
    """6B falu2i (register + immediate). mods=0xC0 is EXP-0101's HW-VALIDATED
    requirement when the register operand is device_load-sourced."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    return isadb.assemble("falu2i", {
        "dst": dst & 0xF, "imm_flag": b1 & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo & 0x7F, "mods": mods & 0xFF,
    })


def seed(dst, value):
    """r[dst] = value, via falu2i(srcA = the never-written r14 = 0.0) + K.
    EXP-0138's MODE-A prologue primitive."""
    return falu2i_raw(dst, R_UNWRITTEN, value, opflags4=0, mods=0xC0)


def falu2_raw(dst, srcA_reg7, srcB_reg7, opsel=4, opflags5=3, ctrl=0,
              srcB_imm=0, mod_lo=0, srcB_neg=0, mod_hi=0xC,
              srcA_size=1, srcB_size=1):
    """6B falu2, EXP-0138's builder verbatim. db.json models falu2's register
    fields as 6 bits PLUS a separate top bit (srcA_reg_top / srcB_reg_top), so
    a 7-bit caller value is split across the two."""
    return isadb.assemble("falu2", {
        "dst": dst & 0xF, "srcA_size": srcA_size, "srcA_reg": srcA_reg7 & 0x3F,
        "srcA_reg_top": (srcA_reg7 >> 6) & 1, "srcB_reg_top": (srcB_reg7 >> 6) & 1,
        "opsel": opsel & 0x7, "opflags": opflags5 & 0x1F,
        "srcB_size": srcB_size, "srcB_reg": srcB_reg7 & 0x3F,
        "ctrl": ctrl & 0x7F, "srcB_imm": srcB_imm & 1, "mod_lo": mod_lo & 0x7,
        "srcB_neg": srcB_neg & 1, "mod_hi": mod_hi & 0xF,
    })


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED (load)


def device_load(index_reg, base_slot, extmode, dst_lo=1, dst_ext9=1, idx_off=0,
                elem_code=3, space=0x10, addr_mode=0x44, access_desc=0x20,
                ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0,
                elem_size=None):
    """14B device_load, EVERY field caller-controllable (EXP-0141 verbatim).

    Defaults are the compiler-observed terminal scalar-32-bit shape that
    EXP-0101 validated end to end. `extmode = 2*R` where R is the register a
    later falu2/falu2i reads; (dst_lo, dst_ext9) = (1, 1) is the pair EXP-0141
    established as the only accepted enable pattern on M4 -- and is exactly
    what arm A re-measures on G17P.
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
    """14B device_store. `extmode = 2*data_reg` is EXP-0090/0101's
    HW-VALIDATED source-register formula. idx_off unit is 4 WORDS (16 B)."""
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


def store_word(word_idx, data_reg, base_slot=0, index_reg=R_IDX):
    """Store r[data_reg] into out[word_idx]. `word_idx` is an ABSOLUTE word
    index and must be a multiple of 4 because idx_off's unit is 4 words."""
    if word_idx % 4:
        raise ValueError("store_word takes an absolute WORD index (0,4,8,...)")
    return device_store(index_reg, base_slot, data_reg=data_reg,
                        idx_off=word_idx // 4)


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
        raise ValueError("program body %d bytes exceeds carrier %d"
                         % (len(body), carrier_len))
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

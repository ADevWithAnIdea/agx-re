#!/usr/bin/env python3
"""EXP-0219 instruction/program construction helpers.

**BYTE-IDENTICAL COPY of EXP-0160's `harness/isa_helpers.py`** (same project,
same rules, cited) except for (a) this header and (b) `_find_isadb`, which is
pointed at THIS experiment's own pinned `work/frozen/` copy of tools/agx-isa so
a sibling edit to the shared DB cannot change what we ran against.  Copied
rather than imported so EXP-0160's committed harness is not executed, edited or
depended on at run time.

The original docstring follows.

EXP-0160 instruction/program construction helpers (G17P last-field sweep).

Structure reused verbatim from EXP-0154 `harness/isa_helpers.py` (same project,
same rules, cited): the SYNTH-WITH-LIFTED-BLOCK carrier, the release-on-read
16-register dump, and the two integrity sentinels that live where the
instruction under test cannot name them (PRE stored to memory before the block;
POST written to a register after it). EXP-0138 lost six sweeps by putting its
sentinel in a register the instruction then read and zeroed.

WHAT IS NEW HERE: **two independent seed sets per arm.** Every case is run
twice, once under each set. Because the seed VALUES differ but the program
SHAPE is byte-identical, a model fitted on set 1 makes a real out-of-sample
prediction about set 2's 16-register post-state. That is the difference between
"this value reproduced the anchor" and "we can predict what this value does".

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    for cand in (EXP / "work" / "frozen",
                 Path.home() / "agxre" / "EXP-0219" / "work" / "frozen",
                 EXP.parents[1] / "tools" / "agx-isa"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    raise RuntimeError("cannot locate tools/agx-isa")


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

R_IDX = 15          # device_store index register, re-seeded 0 before every store
R_SENT = 12         # POST-sentinel register, written AFTER the tested block
R_PRE = 13          # scratch used to materialize the PRE sentinel
N_REGS = 16

# --------------------------------------------------------------------------
# Seed sets. Set 1 is EXP-0154's, kept so the two experiments' baselines are
# directly comparable. Set 2 is new and is chosen so that EVERY arm's anchor
# result differs from set 1's -- otherwise the out-of-sample prediction test
# would be vacuous.
# --------------------------------------------------------------------------
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}
SEED_I2 = {0: 7, 1: 13, 2: 19, 3: 29, 4: 37, 5: 43, 6: 53, 7: 61,
           8: 73, 9: 79, 10: 89, 11: 97, 12: 103, 13: 109, 14: 5, 15: 0}

SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}
SEED_F2 = {0: 0.25, 1: 0.875, 2: 0.375, 3: 1.75, 4: 0.5, 5: 12.0, 6: 14.0,
           7: 16.0, 8: 0.125, 9: 20.0, 10: 24.0, 11: 28.0, 12: 6.0, 13: 2.5,
           14: 0.0, 15: 0.0}

SEEDS = {("int", 1): SEED_I, ("int", 2): SEED_I2,
         ("float", 1): SEED_F, ("float", 2): SEED_F2}

SENT_PRE = 0x5A5A5A5A
SENT_POST = 111

STORE_STRIDE_WORDS = 4                # device_store idx_off unit (EXP-0090/0119)
W_REG0 = 0
W_PRE = 16 * STORE_STRIDE_WORDS       # 64
W_POST = W_PRE + STORE_STRIDE_WORDS   # 68
OUT_WORDS = W_POST + STORE_STRIDE_WORDS   # 72
POISON = 0xDEADBEEF


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031 for 0..127; >=128 silently
    reads back 0 (EXP-0128) -- hard-rejected here."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm imm8 must be 0..127 (EXP-0128 boundary)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F,
                                      "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0xC0,
               srcA_size=1, imm_flag=None, opsel=4):
    b1, sign = isadb.imm_encode(k)
    if imm_flag is None:
        imm_flag = b1 & 1
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo & 0x7F, "mods": mods & 0xFF,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                 space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                 st_format_ext=0, st_desc_hi=0x24, elem_size=0x11,
                 reserved7=0, reserved13=0):
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


def store_word(word_idx, data_reg, base_slot=0):
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(R_IDX, 0)
            + device_store(R_IDX, word_idx // STORE_STRIDE_WORDS, base_slot,
                           data_reg=data_reg))


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def build_program(instrs, carrier_len, pad_dst=13):
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d exceeds carrier %d"
                         % (len(body), carrier_len))
    rem = carrier_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + mov_imm(pad_dst, 0) * (rem // 2)
    assert len(out) == carrier_len
    return out


def assert_round_trip(buf):
    recs, leftover = isadb.disassemble(buf)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes" % len(leftover))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = buf[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s)"
                                 % (off, r["mnemonic"]))
        off += r["length"]
    return recs


def round_trips(buf):
    """A MUTATED instruction is often deliberately undecodable by OUR
    disassembler -- a recorded property of the case (`rt_ok`), never a build
    error: the hardware, not tools/agx-isa, is the authority on the bytes."""
    try:
        assert_round_trip(buf)
        return True
    except Exception:
        return False


def seeds_for(kind, sset):
    return SEEDS[(kind, sset)]


def seed_instrs(kind, sset=1):
    s = seeds_for(kind, sset)
    if kind == "int":
        return [mov_imm(r, s[r]) for r in range(N_REGS)]
    if kind == "float":
        out = [mov_imm(14, 0)]                  # r14 = 0.0f, the +0 source
        for r in range(N_REGS):
            if r == 14:
                continue
            out.append(falu2i_raw(r, 14, s[r]))
        return out
    raise ValueError(kind)


def dump_instrs(store_regs=None):
    regs = list(range(N_REGS)) if store_regs is None else list(store_regs)
    out = []
    for r in regs:
        out.append(store_word(W_REG0 + r * STORE_STRIDE_WORDS, r))
    out.append(mov_imm(R_SENT, SENT_POST))
    out.append(store_word(W_POST, R_SENT))
    return out


def pre_sentinel_instrs(kind, sset=1):
    """Write SENT_PRE to memory BEFORE the block, then RESTORE the scratch
    register's seed so the seed table the block sees is intact."""
    s = seeds_for(kind, sset)
    out = [mov_imm(R_PRE, SENT_PRE & 0x7F), store_word(W_PRE, R_PRE)]
    if kind == "int":
        out.append(mov_imm(R_PRE, s[R_PRE]))
    else:
        out.append(falu2i_raw(R_PRE, 14, s[R_PRE]))
    return out


def synth_program(kind, block_bytes, carrier_len, sset=1):
    instrs = seed_instrs(kind, sset)
    instrs += pre_sentinel_instrs(kind, sset)
    instrs.append(block_bytes)
    instrs += dump_instrs()
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def expected_pre():
    return SENT_PRE & 0x7F


# Sanity: every float seed in EVERY set must be an exact minifloat fixed point,
# and every integer seed must be inside mov_imm's HW-VALIDATED range.
for _name, _tab in (("SEED_F", SEED_F), ("SEED_F2", SEED_F2)):
    for _r, _v in _tab.items():
        if f32(imm_value(_v)) != f32(_v):
            raise AssertionError("%s[%d]=%r is not an exact minifloat fixed point"
                                 % (_name, _r, _v))
for _name, _tab in (("SEED_I", SEED_I), ("SEED_I2", SEED_I2)):
    for _r, _v in _tab.items():
        if not (0 <= _v <= 127) or _v == 12:
            raise AssertionError("%s[%d]=%r outside the usable mov_imm range"
                                 % (_name, _r, _v))

#!/usr/bin/env python3
"""EXP-0154 instruction/program construction helpers (G17P ALU emission sweep).

Every scaffolding instruction is built through `tools/agx-isa`'s own READ-ONLY
`isadb.assemble(mnemonic, fields)`; the instruction UNDER TEST is lifted
byte-for-byte out of the compiled form of OUR OWN MSL (`kernels/probes.metal`)
and then mutated one byte at a time.

Scaffolding field values are (a) HW-VALIDATED by a prior committed experiment
and cited, or (b) copied from an anchor produced by compiling our own MSL.

Reused (structure, not results) from EXP-0138/EXP-0139 `isa_helpers.py`, same
project, same rules, cited: `mov_imm`, `falu2i_raw`, `device_store`,
`build_program`, `assert_round_trip`.

THE SENTINEL FIX (this experiment's reason for existing, EXP-0138 §9):
EXP-0138 held six sweeps at `untested` because reading a GPR as a 32-bit source
ZEROES it afterwards (release-on-read), so its own sentinel register was
destroyed BY THE FIELD WORKING. Here the integrity sentinels never live in a
register the instruction under test can name at the time it runs:

  * PRE  sentinel  -- stored to memory BEFORE the instruction under test runs;
  * POST sentinel  -- its register is `mov_imm`-written AFTER the instruction
                      under test has already executed.

Both are therefore immune to release-on-read, and a full 16-register dump is
taken as well, which turns release-on-read from a trap into an oracle: the
register that went to zero is the register the swept operand descriptor named.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    """Return the agx-isa directory this experiment is pinned to.

    `work/frozen/` holds the EXACT `db.json` / `isadb.py` / `validation.json`
    the hardware ran against, pulled off the neo and sha256-checked against
    CAPTURE_CONTRACT.json. It is preferred because the repo host's
    `tools/agx-isa/db.json` DRIFTS while sibling experiments extend the ISA --
    during this experiment `ilogic.lut_a` was split into
    `lut_a_sel`/`lut_a_free`/`lut_a_z` in the repo copy, which would silently
    re-key our verdicts against a descriptor the hardware never saw.

    On the neo `work/frozen/` is absent and `~/agxre/tools/agx-isa` is used;
    the two are byte-identical (sha256 in CAPTURE_CONTRACT.json).
    """
    for cand in (EXP / "work" / "frozen",
                 Path.home() / "agxre" / "tools" / "agx-isa",
                 EXP.parents[1] / "tools" / "agx-isa"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    raise RuntimeError("cannot locate tools/agx-isa")


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

# --------------------------------------------------------------------------
# Register plan.
# --------------------------------------------------------------------------
R_IDX = 15          # device_store index register; re-seeded to 0 before EVERY
                    # store so a release-on-read of r15 cannot move later stores
R_SENT = 12         # POST-sentinel register, written after the tested block
N_REGS = 16

# Distinct integer seeds, all inside mov_imm's HW-VALIDATED 0..127 range
# (EXP-0128: imm >= 128 silently zeroes; imm7 == 12 does not tokenize, so it is
# avoided).  Chosen so that a+b, a-b, a*b, min/max and "which one is it" are all
# uniquely decodable over the set.
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}

# Distinct float seeds. Every value is an EXACT fixed point of the falu2i
# minifloat immediate encoder (asserted at import time below).
SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}

SENT_PRE = 0x5A5A5A5A     # written to memory before the tested block
SENT_POST = 111           # mov_imm-able POST sentinel (< 128)

# Output word layout (in 32-bit words). Filled in by `set_store_stride()` once
# the pilot has measured the real device_store granularity.
STORE_STRIDE_WORDS = 4    # device_store idx_off unit is 4 WORDS (EXP-0090/0119)
W_REG0 = 0                            # r0..r15 -> words 0,4,...,60
W_PRE = 16 * STORE_STRIDE_WORDS       # 64
W_POST = W_PRE + STORE_STRIDE_WORDS   # 68
OUT_WORDS = W_POST + STORE_STRIDE_WORDS   # 72 words read back
POISON = 0xDEADBEEF


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


# --------------------------------------------------------------------------
# Scaffolding instructions.
# --------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031 for 0..127; >= 128 silently
    reads back 0 (EXP-0128) -- hard-rejected here."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm imm8 must be 0..127 (EXP-0128 boundary)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F,
                                      "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0xC0,
               srcA_size=1, imm_flag=None, opsel=4):
    """6B falu2i (float add with a packed minifloat immediate). Defaults are
    the anchor values of our own compiled `a[t]+3.0f` (EXP-0138 §isa_helpers);
    `mods=0xC0` is EXP-0101's HW-VALIDATED requirement."""
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
    """14B device_store, ALU-forwarded form. `extmode = 2*data_reg` is
    EXP-0090 finding_5 (HW-VALIDATED for data_reg < 64); `idx_off` unit is
    4 WORDS (EXP-0090/EXP-0119)."""
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
    """Store r[data_reg] at absolute output WORD index `word_idx`, re-seeding
    the index register first so a release-on-read of r15 cannot relocate it."""
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
    """True iff the whole program re-tokenizes exactly. A MUTATED instruction
    is often deliberately undecodable by OUR disassembler -- that is a recorded
    property of the case (`rt_ok`), never a build error: the hardware, not
    `tools/agx-isa`, is the authority on what the bytes mean."""
    try:
        assert_round_trip(buf)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# The synthesized program.
# --------------------------------------------------------------------------
def seed_instrs(kind):
    """Seed r0..r15 with distinct, decodable values."""
    if kind == "int":
        return [mov_imm(r, SEED_I[r]) for r in range(N_REGS)]
    if kind == "float":
        out = [mov_imm(14, 0)]                  # r14 = 0.0f, the +0 source
        for r in range(N_REGS):
            if r == 14:
                continue
            out.append(falu2i_raw(r, 14, SEED_F[r]))
        return out
    raise ValueError(kind)


def dump_instrs(store_regs=None):
    """Store every register plus the POST sentinel."""
    regs = list(range(N_REGS)) if store_regs is None else list(store_regs)
    out = []
    for r in regs:
        out.append(store_word(W_REG0 + r * STORE_STRIDE_WORDS, r))
    out.append(mov_imm(R_SENT, SENT_POST))
    out.append(store_word(W_POST, R_SENT))
    return out


R_PRE = 13          # scratch used to materialize the PRE sentinel


def pre_sentinel_instrs(kind):
    """Write SENT_PRE into memory BEFORE the tested block runs, then RESTORE
    the scratch register's seed so the seed table the block sees is intact.
    (Smoke S1/S5 caught the missing restore: r13 came back 90, not its seed.)"""
    out = [mov_imm(R_PRE, SENT_PRE & 0x7F), store_word(W_PRE, R_PRE)]
    if kind == "int":
        out.append(mov_imm(R_PRE, SEED_I[R_PRE]))
    else:
        out.append(falu2i_raw(R_PRE, 14, SEED_F[R_PRE]))
    return out


def synth_program(kind, block_bytes, carrier_len):
    """seeds -> PRE sentinel -> [block under test] -> full register dump ->
    POST sentinel -> stop, padded to the carrier length."""
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    instrs.append(block_bytes)
    instrs += dump_instrs()
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def expected_pre():
    return SENT_PRE & 0x7F


# Sanity: every float seed must be an EXACT minifloat fixed point.
for _r, _v in SEED_F.items():
    if f32(imm_value(_v)) != f32(_v):
        raise AssertionError("SEED_F[%d]=%r is not an exact minifloat fixed point"
                             % (_r, _v))

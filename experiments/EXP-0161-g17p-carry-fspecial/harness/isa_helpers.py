#!/usr/bin/env python3
"""EXP-0161 instruction/program construction helpers (G17P).

WHY THIS FILE EXISTS AT ALL
---------------------------
EXP-0154 swept `carry_gen` and `mov_zext16` on G17P and promoted NOTHING from
either arm, because both failed their pre-registered falsifier: forcing byte0
of the instruction under test to 0x00 still reproduced the entire 16-register
baseline.  EXP-0154 diagnosed its own cause and stated it plainly --

    "for CARRY_GEN the cause is my own design error -- the integer seeds are
     all <= 127 so the low-word add never carries, making the instruction a
     no-op in that carrier whatever its encoding."

The same defect silently disables `mov_zext16` (with a seed <= 127,
`x & 0xFFFF == x`, so the zero-extend is the identity) and leaves `ibfe`'s
`offset`/`width` only weakly live (bits 4..11 of a <=127 seed are zero).

The fix is a carrier defect fix, not a new hypothesis: SEED THE REGISTERS WITH
VALUES THAT ACTUALLY CARRY.  `mov_imm`'s immediate is only seven bits
(EXP-0128/EXP-0140), so a big seed cannot come from `mov_imm` at all.  This
file seeds r0..r14 with a `device_load` per register out of an authored SEED
buffer bound at buffer(1), which gives arbitrary 32-bit values.  That is safe
without any wait instruction: db.json's scoreboard_model records (EXP-0025,
HW-validated) that G17P has a HARDWARE register interlock and that >= 20
independent device loads may be outstanding with no wait op.

Structure (not results) reused from `EXP-0154/harness/isa_helpers.py` and
`EXP-0153/harness/isa_helpers.py`, same project, same rules, cited:
`mov_imm`, `falu2i_raw`, `device_load`, `device_store`, `build_program`,
`assert_round_trip`, and the PRE/POST sentinel discipline.

THE SENTINEL RULE (EXP-0138 section 9, kept):
reading a GPR as a 32-bit source ZEROES it (release-on-read), so an integrity
sentinel must never live in a register the instruction under test can name at
the time it runs:
  * PRE  sentinel -- stored to memory BEFORE the seeds are even loaded;
  * POST sentinel -- its register is written AFTER the tested block has run.
The full 16-register dump then turns release-on-read from a trap into an
ORACLE: the register that goes to zero is the register the swept operand
descriptor named.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte is produced by
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


def _find_isadb():
    """The agx-isa this experiment is PINNED to.

    `work/frozen/` holds the exact `db.json` / `isadb.py` / `validation.json`
    the hardware ran against (sha256 in CAPTURE_CONTRACT.json). It is preferred
    over `tools/agx-isa` because the repo host's copy DRIFTS while sibling
    experiments extend the ISA -- EXP-0154 lost verdict keys to exactly that.
    """
    env = os.environ.get("AGX_ISA_DIR")
    cands = [Path(env)] if env else []
    cands += [EXP / "work" / "frozen",
              Path.home() / "agxre" / "tools" / "agx-isa",
              EXP.parents[1] / "tools" / "agx-isa"]
    for c in cands:
        if (c / "isadb.py").exists() and (c / "db.json").exists():
            return c
    raise RuntimeError("cannot locate agx-isa")


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

M32 = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# register plan
# ---------------------------------------------------------------------------
R_IDX = 15          # store/load index register, held at 0; re-seeded to 0
                    # before EVERY store so a release-on-read cannot move one
R_SENT = 12         # POST-sentinel register, written after the tested block
R_PRE = 14          # PRE-sentinel scratch, used BEFORE any seed is loaded
N_REGS = 16
N_SEEDED = 15       # r0..r14 carry seeds; r15 is the index register

SLOT_OUT = 0        # buffer(0) in kernels/carrier_seed.metal
SLOT_SEED = 1       # buffer(1)


# ---------------------------------------------------------------------------
# seeds
# ---------------------------------------------------------------------------
def _mk_u32_seeds():
    """15 distinct 32-bit seeds chosen so that EVERY defect EXP-0154 hit is
    gone, and so the sweep can still discriminate:

      * the pair the lifted 64-bit low-word add actually names (r1 and r3 in
        the k_u64add anchor: `srcB_ext>>2 = 3`, `srcB_imm>>2 = 1`) BOTH have
        bit31 set, so that add ALWAYS carries and `carry_gen`'s predicate is
        load-bearing -- this is the single defect that made EXP-0154's
        CARRY_GEN arm a no-op, and CARRY_PAIR below asserts it;
      * high halfword non-zero and DISTINCT -> `mov_zext16` is not the
        identity, and its result identifies the source register;
      * low halfword DISTINCT, and low byte distinct -> `ibfe` extracts a
        different, register-identifying value for every offset/width;
      * the values are spread across [2^31, 2^32) rather than clustered, so
        `carry_gen`'s unsigned compare `r[srcA] <u r[srcB]` is TRUE for some
        register pairs and FALSE for others -- without that spread the
        predicate would be constant and the sweep could not tell operands
        apart.
    """
    base = [0x80112233, 0x8F4E7A15, 0x0A2C51E7, 0xA7D30B49,
            0x161F94AB, 0xC48A2D5D, 0x23654EBF, 0xE2B0C721,
            0x310D3883, 0x47F6A9E5, 0x5613BA47, 0xF5E0CBA9,
            0x64CD1C0B, 0x73BA8D6D, 0xEE9F7ECF]
    assert len(base) == N_SEEDED
    return base


CARRY_PAIR = (1, 3)   # the registers the k_u64add anchor's low-word add reads
SEED_U32 = _mk_u32_seeds() + [0]                  # r15 = 0 (index register)

# 15 distinct POSITIVE finite floats: legal inputs to rsqrt/log2/sqrt/exp2, with
# distinct results under every one of them, and distinct raw bit patterns.
SEED_F32 = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0,
            1.5, 36.0, 0.125, 81.0, 6.25, 121.0, 3.0] + [0.0]

SENT_PRE = 90             # mov_imm-able (< 128); stored before ANY seed exists
SENT_POST = 111           # mov_imm-able; written after the tested block
POISON = 0xDEADBEEF


def _check_seeds():
    u = SEED_U32[:N_SEEDED]
    assert len(set(u)) == N_SEEDED, "u32 seeds not distinct"
    assert len(set(v & 0xFFFF for v in u)) == N_SEEDED, "low halfwords collide"
    assert len(set(v >> 16 for v in u)) == N_SEEDED, "high halfwords collide"
    assert len(set((v >> 4) & 0xFF for v in u)) == N_SEEDED, "ibfe(4,8) collide"
    a, b = u[CARRY_PAIR[0]], u[CARRY_PAIR[1]]
    assert (a + b) >> 32 == 1, "the anchor's addend pair does not carry"
    slo = (a + b) & M32
    assert 3 <= sum(1 for v in u if v < slo) <= 12, \
        "sum_lo does not split the seed set -- carry_gen's compare would be constant"
    assert 3 <= sum(1 for v in u if v < b) <= 12, \
        "seed[srcB] does not split the seed set"
    assert all(v & 0xFFFF0000 for v in u), "a seed zero-extends to itself"
    f = SEED_F32[:N_SEEDED]
    assert len(set(f)) == N_SEEDED, "f32 seeds not distinct"
    assert all(v > 0 for v in f), "f32 seed not positive"
    assert len(set(struct.pack("<f", v) for v in f)) == N_SEEDED


_check_seeds()


def seed_buffer_bytes():
    """The authored buffer(1) contents: words 0..15 = the u32 seeds, words
    16..31 = the f32 seeds, words 32..47 = a poison guard so an out-of-range
    idx_off is visible rather than silently reading a seed."""
    w = [v & M32 for v in SEED_U32]
    w += [struct.unpack("<I", struct.pack("<f", v))[0] for v in SEED_F32]
    w += [(0xC0DE0000 + i) & M32 for i in range(16)]
    return b"".join(struct.pack("<I", v) for v in w)


SEED_BASE = {"int": 0, "float": 16}


def seeds_for(kind):
    if kind == "int":
        return list(SEED_U32)
    if kind == "float":
        return [struct.unpack("<I", struct.pack("<f", v))[0] for v in SEED_F32]
    raise ValueError(kind)


# ---------------------------------------------------------------------------
# output layout (32-bit words)
# ---------------------------------------------------------------------------
STORE_STRIDE_WORDS = 4                   # device_store idx_off unit (EXP-0090/0119)
W_REG0 = 0                               # r0..r15 -> words 0,4,...,60
W_PRE = 16 * STORE_STRIDE_WORDS          # 64
W_POST = W_PRE + STORE_STRIDE_WORDS      # 68
W_SCRATCH = W_POST + STORE_STRIDE_WORDS  # 72: the drain stores' sink
OUT_WORDS = W_SCRATCH + STORE_STRIDE_WORDS   # 76 words read back


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


# ---------------------------------------------------------------------------
# single-instruction builders (all through isadb.assemble)
# ---------------------------------------------------------------------------
def mov_imm(dst, imm7, imm_top=0):
    """2B: d[dst] = imm7. HW-VALIDATED EXP-0031 for 0..127; EXP-0140: with
    imm_top=1 the instruction does not write the destination at all."""
    if not (0 <= imm7 <= 127):
        raise ValueError("mov_imm imm7 must be 0..127 (EXP-0128 boundary)")
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm7 & 0x7F,
                                      "imm_top": imm_top & 1})


def device_load(index_reg, base_slot, extmode, dst_lo=1, dst_ext9=1, idx_off=0,
                elem_code=3, space=0x10, addr_mode=0x44, access_desc=0x20,
                ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0,
                elem_size=None):
    """14B device_load, EXP-0141's HW-VALIDATED terminal scalar-32-bit shape
    (verbatim from EXP-0153/harness/isa_helpers.py). `extmode = 2*R` selects
    the destination register R; (dst_lo, dst_ext9) = (1, 1) is the only enable
    pattern EXP-0141/EXP-0153 found accepted."""
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
    HW-VALIDATED source-register formula; idx_off's unit is 4 WORDS."""
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


def store_word(word_idx, data_reg, base_slot=SLOT_OUT):
    """Store r[data_reg] at ABSOLUTE output word `word_idx`, re-seeding the
    index register to 0 first so a release-on-read of r15 inside the tested
    block cannot relocate every later store (EXP-0154's discipline)."""
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(R_IDX, 0)
            + device_store(R_IDX, base_slot, data_reg=data_reg,
                           idx_off=word_idx // STORE_STRIDE_WORDS))


def stop():
    return isadb.assemble("stop", {"reserved": 0})


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
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


N_DRAIN = 6          # dummy stores issued before the real dump (see below)


def seed_instrs(kind, elem_code=3, waves=2):
    """r15 = 0, then r0..r14 <- SEED buffer(1)[SEED_BASE[kind] + r], TWICE.

    WHY TWICE (HW-PROBE, work/pilot_seed.json, G17P, this experiment):
    db.json's scoreboard_model records (EXP-0025) that G17P has a hardware
    register interlock and needs no wait op, with >= 20 device loads
    outstanding "all consumed correctly". That holds for ALU consumers. It does
    NOT hold for a `device_store` consumer: with a single wave of 15 loads, the
    registers read by the FIRST ~5 STORES issued afterwards come back with
    their PRE-LOAD value, and the effect follows the STORE order, not the load
    order --

        P1 loads r0..r14, dump r0..r15   -> r0..r4  stale
        P3 loads r14..r0, dump r0..r15   -> r0..r4  stale  (same registers)
        P5 loads r0..r14, dump r15..r0   -> r11..r14 stale (the first stored)
        P4 loads r0..r4 only             -> r0..r4  stale
        P2 loads + 64 pad ops            -> only r13 stale (a race, not a fix)
        P8 loads TWICE                   -> 15/15 correct

    Two waves fix it deterministically: the first wave has retired by the time
    the second is issued, so a store whose interlock does not cover it still
    reads the value wave 1 wrote. `N_DRAIN` dummy stores of the always-zero
    index register are additionally issued before the real dump, so the stores
    that are demonstrably too early are spent on a scratch word.
    """
    base = SEED_BASE[kind]
    out = [mov_imm(R_IDX, 0)]
    for _ in range(waves):
        for r in range(N_SEEDED):
            out.append(device_load(index_reg=R_IDX, base_slot=SLOT_SEED,
                                   extmode=2 * r, dst_lo=1, dst_ext9=1,
                                   idx_off=base + r, elem_code=elem_code))
    return out


def pre_sentinel_instrs():
    """Written BEFORE any seed is loaded, so no register it touches is still
    holding a seed when the tested block runs."""
    return [mov_imm(R_PRE, SENT_PRE), store_word(W_PRE, R_PRE)]


def dump_instrs():
    out = [store_word(W_SCRATCH, R_IDX) for _ in range(N_DRAIN)]
    for r in range(N_REGS):
        out.append(store_word(W_REG0 + r * STORE_STRIDE_WORDS, r))
    out.append(mov_imm(R_SENT, SENT_POST))
    out.append(store_word(W_POST, R_SENT))
    return out


def synth_program(kind, block_bytes, carrier_len, elem_code=3):
    """PRE sentinel -> seed r0..r14 from buffer(1) -> [block under test] ->
    full 16-register dump -> POST sentinel -> stop, padded to carrier_len."""
    instrs = pre_sentinel_instrs()
    instrs += seed_instrs(kind, elem_code=elem_code)
    instrs.append(block_bytes)
    instrs += dump_instrs()
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def expected_pre():
    return SENT_PRE


# ---------------------------------------------------------------------------
# round trip (CODEX step 10) -- RECORDED per case, never asserted for a mutated
# instruction: the hardware, not tools/agx-isa, is the authority on bytes.
# ---------------------------------------------------------------------------
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
    try:
        assert_round_trip(buf)
        return True
    except Exception:
        return False

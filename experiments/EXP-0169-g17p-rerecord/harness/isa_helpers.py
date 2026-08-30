#!/usr/bin/env python3
"""EXP-0169 instruction/program construction helpers (G17P re-record sweep).

Every scaffolding instruction is built through `tools/agx-isa`'s own READ-ONLY
`isadb.assemble(mnemonic, fields)`; an instruction UNDER TEST is either

  * LIFTED byte-for-byte out of the compiled form of OUR OWN MSL
    (`kernels/probes.metal`) and then mutated one field at a time, or
  * SYNTHESIZED from db.json's own field rules (the stronger evidence level:
    an independently generated encoding executed on hardware).

Reused (structure, not results) from EXP-0154 `harness/isa_helpers.py` and
EXP-0141 `isa_helpers.py`, same project, same rules, cited per function.

WHY THIS EXPERIMENT EXISTS: EXP-0164 found 144 emitter-grade fields with no
per-value raw record attributable to them. Re-recording them means a FRESH
capture in the EXP-0138+ per-case schema -- never a re-labelling of an old
narrative summary.

THE TWO INSTRUMENTS THAT DECIDE WHETHER A SWEEP CAN SEE ANYTHING
1. The oracle is the FULL 16-GPR dump, not one output word. A field whose
   effect is *where* a result lands (any `dst`-like selector) is invisible to a
   single-word read-back; the audit's `uniform_mov.dst` "16 values, 0 moved" is
   the signature of exactly that blindness.
2. Two carriers that are identical in the dimension the field controls are ONE
   carrier. So the seeds come in two provenances and two value shapes:
     C1_alu  -- operands produced by mov_imm / falu2i (ALU-sourced), narrow;
     C2_load -- operands produced by device_load (LOAD-sourced), and chosen
                with NON-ZERO LOW HALVES so that a b16 read is a DIFFERENT
                NON-ZERO value rather than 0;
     C3_uni  -- a carrier that also preloads the UNIFORM register file, the
                only place `falu2_uni.uni_mode` and `falu2.srcB_class==1` can
                be seen.
   `falu2.mod_hi` is operand-provenance-dependent (EXP-0158: inert for an
   ALU-sourced operand, only 0xC of 16 works for a load-sourced one), so
   C1 vs C2 is a designed difference in exactly the dimension it controls.

SENTINELS (EXP-0154 section 'THE SENTINEL FIX', kept verbatim in spirit):
reading a GPR as a 32-bit source ZEROES it (release-on-read), so neither
integrity sentinel may live in a register the instruction under test can name
while it runs. PRE is in memory before the block; POST's register is written
after it. Release-on-read then becomes an ORACLE: the register that went to
zero is the register the swept operand descriptor named.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    """The agx-isa directory this experiment is pinned to.

    `work/frozen/` holds the EXACT db.json / isadb.py the hardware ran against,
    sha256-checked against CAPTURE_CONTRACT.json, because the repo host's
    tools/agx-isa/db.json DRIFTS while sibling experiments extend the ISA
    (EXP-0165 owns db.json and is editing it concurrently with this run).
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
# Register plan (EXP-0154 verbatim, with the load-seeded variant added).
# --------------------------------------------------------------------------
R_IDX = 15          # device_store index register; re-seeded to 0 before EVERY
                    # store so a release-on-read of r15 cannot move later stores
R_SENT = 12         # POST-sentinel register, written AFTER the tested block
R_PRE = 13          # scratch used to materialize the PRE sentinel
N_REGS = 16
N_LOAD_SEEDED = 14  # C2_load seeds r0..r13 from memory; r14/r15 stay mov_imm

SLOT_OUT, SLOT_MEM, SLOT_IMEM = 0, 1, 2

# EXP-0154 verbatim. All inside mov_imm's HW-VALIDATED 0..127 range (EXP-0128:
# imm >= 128 does not write; imm7 == 12 does not tokenize, so it is avoided).
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}

# EXP-0154 verbatim. Every value is an EXACT fixed point of the falu2i minifloat
# immediate encoder (asserted at import time below). NOTE their fp32 bit
# patterns all have a ZERO low half, so on C1 a b16 source read yields 0.0 --
# a movement, but a weakly identifying one. C2's seeds fix that.
SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}

# C2_load seeds: normal fp32 values with a NON-ZERO LOW HALF, so `srcA_size` /
# `srcB_size` (b16 vs b32) select two DIFFERENT NON-ZERO operands instead of
# "the value" vs "0.0". Distinct, monotone, and none is a power of two.
WSEED_BITS = [0x40000000 + (k + 1) * 0x00081111 for k in range(N_LOAD_SEEDED)]
# The memory image loaded by C2_load: a ramp so that whatever the device_load
# `idx_off` unit turns out to be, every reachable word is distinct and
# self-identifying (the pilot calibrates the unit and the calibration is frozen
# before the gated runs).
MEM_WORDS = 8192


def mem_image():
    return struct.pack("<%dI" % MEM_WORDS,
                       *[(0x40000000 + (i + 1) * 0x00081111) & 0xFFFFFFFF
                         for i in range(MEM_WORDS)])


SENT_PRE = 0x5A5A5A5A     # written to memory before the tested block
SENT_POST = 111           # mov_imm-able POST sentinel (< 128)

STORE_STRIDE_WORDS = 4    # device_store idx_off unit is 4 WORDS (EXP-0090/0119)
W_REG0 = 0                                 # r0..r15 -> words 0,4,...,60
W_PRE = 16 * STORE_STRIDE_WORDS            # 64
W_POST = W_PRE + STORE_STRIDE_WORDS        # 68
W_PROBE = W_POST + STORE_STRIDE_WORDS      # 72: first word a probe store may use
OUT_WORDS = 104                            # default read-back
# The device_store arm sweeps `idx_off` (11 bits, unit 4 words) and `base_slot`,
# so its read-back must span the whole reachable range or an in-range store
# would look like a fault.
OUT_WORDS_BIG = 8256
POISON = 0xDEADBEEF


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def bits_to_f32(b):
    return struct.unpack("<f", struct.pack("<I", b & 0xFFFFFFFF))[0]


def f32_to_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def inline_minifloat(v):
    """db.json falu2 semantics, EXP-0138: in srcB source-class 1, srcB_reg
    values 64..127 are an INLINE 8-bit minifloat immediate. k = v-64,
    e = k>>3, m = k&7; value = m*2^-5 when e==0 else (8+m)*2^(e-6).
    Reproduced here as a HOST-SIDE ORACLE so the claim is checkable per value.
    Returns None for v < 64 (a uniform-file index, not an immediate)."""
    if v < 64 or v > 127:
        return None
    k = v - 64
    e, m = k >> 3, k & 7
    return f32(m * 2.0 ** -5 if e == 0 else (8 + m) * 2.0 ** (e - 6))


# --------------------------------------------------------------------------
# Scaffolding instructions.
# --------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031 for 0..127; >= 128 does not
    write the destination at all and consumes the next 2-byte instruction
    (EXP-0140) -- hard-rejected here."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm imm8 must be 0..127 (EXP-0128/EXP-0140)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F,
                                      "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0xC0,
               srcA_size=1, imm_flag=None, opsel=4):
    """6B falu2i. Defaults are the anchor values of our own compiled
    `a[t]+3.0f` (EXP-0138); `mods=0xC0` is EXP-0101's HW-VALIDATED requirement
    for a LOAD-sourced operand and BREAKS a mov_imm-sourced one (EXP-0141
    amendment 1), so the caller passes mods=0 for ALU-sourced seeds."""
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
    """14B device_store, ALU-forwarded form (EXP-0154 verbatim).
    `extmode = 2*data_reg` is EXP-0090 finding_5 (HW-VALIDATED for
    data_reg < 64); `idx_off` unit is 4 WORDS (EXP-0090/EXP-0119)."""
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


def device_load(index_reg, base_slot, extmode, dst_lo=1, dst_ext9=1, idx_off=0,
                elem_code=3, space=0x10, addr_mode=0x44, access_desc=0x20,
                ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0,
                elem_size=None):
    """14B device_load (EXP-0141 `isa_helpers.device_load`, verbatim).
    Defaults are the compiler-observed terminal scalar-32-bit shape that
    EXP-0101 validated end to end; `extmode = 2*R` selects the destination
    register R."""
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


def regmove(dst, src_byte, form_byte, opdesc_byte):
    """4B byte0-low-nibble-0xB instruction -- the family db.json splits into
    reg_move_c0 / c1 / c2var / c9 / cb / uniform_mov. Built as ONE instruction
    with four independent bytes (EXP-0140 verbatim; EXP-0087 already showed the
    five descriptors are one instruction):
        byte0 = (dst<<4)|0x0B   byte+1 = src   byte+2 = form   byte+3 = opdesc
    """
    return bytes([((dst & 0xF) << 4) | 0x0B, src_byte & 0xFF,
                  form_byte & 0xFF, opdesc_byte & 0xFF])


def get_sr(dst, sr_sel, form=0, dp_width=0, dp_marker=0, dst_hi=0):
    """4B get_sr: d[dst | dst_hi<<4] = special_register[sr_sel]."""
    return isadb.assemble("get_sr", {
        "form": form & 1, "dst": dst & 0xF, "sr_sel": sr_sel & 0xFF,
        "dp_width": dp_width & 0xFF, "dp_marker": dp_marker & 0x1F,
        "dst_hi": dst_hi & 0x7})


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def store_word(word_idx, data_reg, base_slot=SLOT_OUT):
    """Store r[data_reg] at absolute output WORD index `word_idx`, re-seeding
    the index register first so a release-on-read of r15 cannot relocate it."""
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(R_IDX, 0)
            + device_store(R_IDX, word_idx // STORE_STRIDE_WORDS, base_slot,
                           data_reg=data_reg))


def load_reg(dst_reg, word_off, base_slot=SLOT_MEM):
    """Seed r[dst_reg] from buffer `base_slot` at device_load offset
    `word_off`. The idx_off UNIT is calibrated by harness/smoke.py and frozen
    before the gated runs; the memory image is a ramp so every reachable word
    is self-identifying whatever the unit turns out to be."""
    return (mov_imm(R_IDX, 0)
            + device_load(index_reg=R_IDX, base_slot=base_slot,
                          extmode=2 * dst_reg, idx_off=word_off))


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
    """True iff the block re-tokenizes exactly. A MUTATED instruction is often
    deliberately undecodable by OUR disassembler -- a recorded property of the
    case (`rt_ok`), never a build error: the hardware, not tools/agx-isa, is
    the authority on what the bytes mean."""
    try:
        assert_round_trip(buf)
        return True
    except Exception:
        return False


def tokenize_first(buf):
    """The db mnemonic tools/agx-isa assigns to the first instruction of
    `buf`, or None. Recorded per case as `tok_instr` so a sweep that walks a
    descriptor discriminator (e.g. reg_move_c2var.subform) leaves an audit
    trail of WHICH descriptor each value actually is, while `instr` stays the
    descriptor the arm is testing."""
    try:
        recs, _ = isadb.disassemble(buf)
        return recs[0]["mnemonic"] if recs else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# The synthesized program.
# --------------------------------------------------------------------------
def seed_instrs(kind):
    """Seed r0..r15 with distinct, decodable values.

    kind == 'int'   : mov_imm seeds (ALU-sourced, narrow)          [C1_alu]
    kind == 'float' : falu2i seeds  (ALU-sourced, zero low halves) [C1_alu]
    kind == 'load'  : device_load seeds (LOAD-sourced, non-zero
                      low halves) for r0..r13; r14/r15 mov_imm     [C2_load]
    """
    if kind == "int":
        return [mov_imm(r, SEED_I[r]) for r in range(N_REGS)]
    if kind == "float":
        out = [mov_imm(14, 0)]                  # r14 = 0.0f, the +0 source
        for r in range(N_REGS):
            if r == 14:
                continue
            out.append(falu2i_raw(r, 14, SEED_F[r], mods=0))
        return out
    if kind == "load":
        out = [mov_imm(14, 0), mov_imm(R_IDX, 0)]
        for r in range(N_LOAD_SEEDED):
            out.append(load_reg(r, r))
        return out
    raise ValueError(kind)


def seed_values(kind, idx_unit=1):
    """Host-side model of the seeds, for the semantic oracle. `idx_unit` is the
    pilot-calibrated device_load idx_off unit in WORDS."""
    if kind == "int":
        return {r: SEED_I[r] for r in range(N_REGS)}
    if kind == "float":
        return {r: f32_to_bits(SEED_F[r]) for r in range(N_REGS)}
    if kind == "load":
        d = {r: (0x40000000 + (r * idx_unit + 1) * 0x00081111) & 0xFFFFFFFF
             for r in range(N_LOAD_SEEDED)}
        d[14] = 0
        d[15] = 0
        return d
    raise ValueError(kind)


def pre_sentinel_instrs(kind):
    """Write SENT_PRE into memory BEFORE the tested block runs, then RESTORE
    the scratch register's seed so the seed table the block sees is intact.
    (EXP-0154 smoke S1/S5 caught the missing restore.)"""
    out = [mov_imm(R_PRE, SENT_PRE & 0x7F), store_word(W_PRE, R_PRE)]
    if kind == "int":
        out.append(mov_imm(R_PRE, SEED_I[R_PRE]))
    elif kind == "float":
        out.append(falu2i_raw(R_PRE, 14, SEED_F[R_PRE], mods=0))
    else:
        out.append(load_reg(R_PRE, R_PRE))
    return out


def dump_instrs(store_regs=None):
    """Store every register plus the POST sentinel."""
    regs = list(range(N_REGS)) if store_regs is None else list(store_regs)
    out = []
    for r in regs:
        out.append(store_word(W_REG0 + r * STORE_STRIDE_WORDS, r))
    out.append(mov_imm(R_SENT, SENT_POST))
    out.append(store_word(W_POST, R_SENT))
    return out


def synth_program(kind, block_bytes, carrier_len, tail=()):
    """seeds -> PRE sentinel -> [block under test] -> full 16-register dump ->
    POST sentinel -> [optional tail] -> stop, padded to the carrier length."""
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    instrs.append(block_bytes)
    instrs += dump_instrs()
    instrs += list(tail)
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def store_probe_program(kind, store_bytes, carrier_len):
    """The device_store arm's shape: the store UNDER TEST runs AFTER the
    register dump and the POST sentinel, carrying a distinctive data register,
    so wherever it lands is visible against the 0xDEADBEEF poison without
    disturbing the dump. The dump therefore also proves the program ran even
    when the store under test writes nothing."""
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    instrs += dump_instrs()
    instrs.append(mov_imm(R_IDX, 0))
    instrs.append(store_bytes)
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def expected_pre():
    return SENT_PRE & 0x7F


# Sanity: every C1 float seed must be an EXACT minifloat fixed point.
for _r, _v in SEED_F.items():
    if f32(imm_value(_v)) != f32(_v):
        raise AssertionError("SEED_F[%d]=%r is not an exact minifloat fixed point"
                             % (_r, _v))
# Sanity: every C2 seed must have a non-zero low half (that is its whole point).
for _b in WSEED_BITS:
    if (_b & 0xFFFF) == 0:
        raise AssertionError("C2 seed 0x%08x has a zero low half" % _b)

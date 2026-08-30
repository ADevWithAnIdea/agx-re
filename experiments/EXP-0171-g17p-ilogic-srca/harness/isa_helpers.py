#!/usr/bin/env python3
"""EXP-0171 instruction/program construction helpers (G17P).

ADAPTED, with citation, from `experiments/EXP-0154-g17p-emit-alu/harness/
isa_helpers.py` -- same project, same rules. Reused verbatim in structure:
`mov_imm`, `falu2i_raw`, `device_store`, `store_word`, `build_program`,
`synth_program`, `assert_round_trip`, the register plan, and the sentinel
design. NEW here:

  * `synth_program(..., suffix=...)` -- an optional instruction sequence placed
    IMMEDIATELY AFTER the block under test. This is the carrier axis for the
    trailing-byte fields (`ilogic.z6/z8/z9`, `*.tail`): if a swept trailing byte
    were really a LENGTH or framing bit, the instruction that follows would be
    mis-framed, and the suffix's two markers (r6, r7) would stop arriving. A
    trailing-byte verdict of "inert" is only admissible from a carrier that
    could have seen that.

Every scaffolding instruction is built through `tools/agx-isa`'s READ-ONLY
`isadb.assemble()`. The instruction UNDER TEST is lifted byte-for-byte out of
the compiled form of OUR OWN MSL (`kernels/probes.metal`) and mutated as RAW
BYTES -- never through `assemble()`, because `assemble()` ORs the match constant
and cannot clear a bit (EXP-0166 DEF-0166-1: 53 fields silently under-swept).

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    """Prefer this experiment's pinned snapshot: `work/frozen/` holds the EXACT
    db.json / isadb.py the hardware ran against, sha256-checked against
    CAPTURE_CONTRACT.json. The repo copy DRIFTS while sibling experiments extend
    the ISA (EXP-0154 lost its `ilogic.lut_a` verdict to exactly that)."""
    for cand in (EXP / "work" / "frozen",
                 Path.home() / "agxre" / "EXP-0171" / "frozen",
                 Path.home() / "agxre" / "tools" / "agx-isa",
                 EXP.parents[1] / "tools" / "agx-isa"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    raise RuntimeError("cannot locate tools/agx-isa")


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

# --------------------------------------------------------------------------
# Register plan (EXP-0154, unchanged).
# --------------------------------------------------------------------------
R_IDX = 15          # device_store index register, re-seeded before EVERY store
R_SENT = 12         # POST-sentinel register, written AFTER the tested block
R_PRE = 13          # scratch used to materialize the PRE sentinel
N_REGS = 16

# HIGH-POPCOUNT, PAIRWISE-OVERLAPPING seeds. EXP-0154's seeds (r0=10, r1=21)
# are bit-disjoint, so a lifted logic op whose operands the compiler chose as
# (r1, r0) computes 21 & 10 == 0 and the baseline itself is a silent zero --
# indistinguishable from a broken encoding. Every value here is <= 127
# (mov_imm.imm7's HW boundary, EXP-0128) and no pair ANDs to 0:
#   min over all 91 pairs of popcount(a & b) == 2  (checked at import, below).
SEED_I = {0: 107, 1: 93, 2: 55, 3: 122, 4: 47, 5: 115, 6: 77, 7: 118,
          8: 31, 9: 101, 10: 59, 11: 89, 12: 125, 13: 127, 14: 3, 15: 0}

SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}

SENT_PRE = 0x5A5A5A5A
SENT_POST = 111

STORE_STRIDE_WORDS = 4                    # device_store idx_off unit (EXP-0090/0119)
W_REG0 = 0                                # r0..r15 -> words 0,4,...,60
W_PRE = 16 * STORE_STRIDE_WORDS           # 64
W_POST = W_PRE + STORE_STRIDE_WORDS       # 68
OUT_WORDS = W_POST + STORE_STRIDE_WORDS   # 72 words read back
POISON = 0xDEADBEEF

# Suffix markers: registers the tested instruction's descriptor may name as an
# operand but which are re-written AFTER it runs, so release-on-read cannot
# forge a pass. Both are checked in `classify()`.
R_MARK_A = 6
R_MARK_B = 7
MARK_A = 77
MARK_B_F = 13.0


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


# --------------------------------------------------------------------------
# Scaffolding instructions (EXP-0154, unchanged).
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
    """6B falu2i (float add with a packed minifloat immediate). Defaults are the
    anchor values of our own compiled `a[t]+3.0f`; `mods=0xC0` is EXP-0101's
    HW-VALIDATED requirement for this operand provenance."""
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
    """14B device_store, ALU-forwarded form. `extmode = 2*data_reg` is EXP-0090
    finding_5 (HW-VALIDATED for data_reg < 64)."""
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
    """True iff the whole program re-tokenizes exactly. A MUTATED instruction is
    often deliberately undecodable by OUR disassembler -- a recorded property of
    the case (`rt_ok`), never a build error: the hardware, not tools/agx-isa, is
    the authority on what the bytes mean."""
    try:
        assert_round_trip(buf)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# The synthesized program.
# --------------------------------------------------------------------------
def seed_instrs(kind):
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
    regs = list(range(N_REGS)) if store_regs is None else list(store_regs)
    out = []
    for r in regs:
        out.append(store_word(W_REG0 + r * STORE_STRIDE_WORDS, r))
    out.append(mov_imm(R_SENT, SENT_POST))
    out.append(store_word(W_POST, R_SENT))
    return out


def pre_sentinel_instrs(kind):
    """Write SENT_PRE into memory BEFORE the tested block runs, then RESTORE the
    scratch register's seed so the seed table the block sees is intact."""
    out = [mov_imm(R_PRE, SENT_PRE & 0x7F), store_word(W_PRE, R_PRE)]
    if kind == "int":
        out.append(mov_imm(R_PRE, SEED_I[R_PRE]))
    else:
        out.append(falu2i_raw(R_PRE, 14, SEED_F[R_PRE]))
    return out


def suffix_instrs(kind):
    """The FRAMING PROBE (new in EXP-0171). Two markers written immediately
    after the block under test, using two DIFFERENT instruction lengths (6B
    falu2i then 2B mov_imm). If a swept trailing byte changed the tested
    instruction's length, the decoder would resume mid-instruction here and both
    markers would be lost -- so a `tail`/`z*` inertness verdict from this carrier
    is a statement about framing as well as about arithmetic."""
    if kind == "int":
        return [falu2i_raw(R_MARK_B, 14, MARK_B_F), mov_imm(R_MARK_A, MARK_A)]
    return [falu2i_raw(R_MARK_B, 14, MARK_B_F), mov_imm(R_MARK_A, MARK_A)]


def synth_program(kind, block_bytes, carrier_len, suffix=False):
    """seeds -> PRE sentinel -> [block under test] -> (optional framing probe)
    -> full register dump -> POST sentinel -> stop, padded to carrier_len."""
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    instrs.append(block_bytes)
    if suffix:
        instrs += suffix_instrs(kind)
    instrs += dump_instrs()
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def expected_pre():
    return SENT_PRE & 0x7F


# No pair of INT seeds may AND to zero (r14/r15 are the scratch/index regs and
# are excluded: r15 must be 0, it is the device_store index register).
_sk = [r for r in range(N_REGS) if r not in (14, 15)]
for _i in range(len(_sk)):
    for _j in range(_i + 1, len(_sk)):
        if SEED_I[_sk[_i]] & SEED_I[_sk[_j]] == 0:
            raise AssertionError("SEED_I[%d] & SEED_I[%d] == 0 -- a lifted "
                                 "logic op on that pair has a degenerate "
                                 "baseline" % (_sk[_i], _sk[_j]))

for _r, _v in SEED_F.items():
    if f32(imm_value(_v)) != f32(_v):
        raise AssertionError("SEED_F[%d]=%r is not an exact minifloat fixed point"
                             % (_r, _v))

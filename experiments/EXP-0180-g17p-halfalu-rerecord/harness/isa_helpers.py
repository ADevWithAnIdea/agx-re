#!/usr/bin/env python3
"""EXP-0180 instruction/program construction helpers (G17P half-ALU re-record).

WHAT THIS FIXES, RELATIVE TO EXP-0169 (all four are pre-registered, PROGRESS.md M3/M4):

  DEF-0169-1  `device_load` on G17P is ASYNCHRONOUS and EXP-0169's harness issued no wait
              anywhere, so a periodically-refreshed diff baseline could FABRICATE movement.
              -> NO seed path here uses `device_load`, AND every case dumps all 16 GPRs
                 BEFORE the block as well as after, so "the seeds landed" is proved PER
                 CASE. There is no refreshed baseline anywhere in this experiment.
  DEF-0180-A  EXP-0169's lifted half anchors were COMPUTATIONALLY DEAD in its carrier:
              their descriptors name registers 64/65 (never seeded) and its float seeds
              have ZERO low 16 bits, so every even half-register descriptor read 0.0.
              -> seeds here carry distinct non-zero fp16 values in BOTH halves.
  DEF-0180-B  `byte0 -> 0x00` is not a falsifier for the byte0==0x10 family: byte0's HIGH
              NIBBLE is the destination GPR, so it only RELOCATES the write.
              -> `byte0_dst()` makes that explicit and the DSTNIB arm tests it (H0).
  DEF-0180-2  `byte+4 & 3` is a LENGTH selector inside `half_alu_ext8.srcB_desc` and
              `half_alu_fma12.ext`. -> every case records `tok_instr` and the hardware
              measured length; `gate_identity` excludes identity-changing values.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Scaffolding is built through `tools/agx-isa`'s own
READ-ONLY `isadb.assemble`; instructions under test are either lifted byte-for-byte from
the compiled form of our own MSL or synthesized from db.json's own field rules. No Apple
binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

# --------------------------------------------------------------------------
# PINNED ISA. EXPLICIT resolution -- there is deliberately NO path fall-through
# and NO home-directory candidate. A sibling experiment silently resolved a
# STALE shared db.json on the neo through exactly such a fall-through; this
# raises instead.
# --------------------------------------------------------------------------
ISA_DIR = EXP / "work" / "frozen"
if not ((ISA_DIR / "isadb.py").exists() and (ISA_DIR / "db.json").exists()):
    raise RuntimeError(
        "EXP-0180 pins tools/agx-isa to %s and will not fall back. "
        "Run harness/sync.sh push, which copies work/frozen/ to the neo." % ISA_DIR)
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

DB_SHA256 = "a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22"
ISADB_SHA256 = "9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8"


def assert_pins():
    """Assert the pinned hashes at run start; written into raw/<run>/00_env.json."""
    import hashlib
    got = {p: hashlib.sha256((ISA_DIR / p).read_bytes()).hexdigest()
           for p in ("db.json", "isadb.py")}
    if got["db.json"] != DB_SHA256 or got["isadb.py"] != ISADB_SHA256:
        raise RuntimeError("pinned ISA hash mismatch: %r" % got)
    return {"isa_dir": str(ISA_DIR), "db_sha256": got["db.json"],
            "isadb_sha256": got["isadb.py"]}


# --------------------------------------------------------------------------
# Register plan and output-word layout.
# --------------------------------------------------------------------------
R_IDX = 15          # device_store index register; re-seeded to 0 before EVERY store
R_SENT = 12         # POST-sentinel register, written AFTER the block and after the dump
R_PRE = 13          # scratch used to materialize the PRE sentinel (seed restored after)
R_ZERO = 14         # the +0.0 source falu2i seeding needs; always 0
R_C2 = 13           # C_LO's second-consumer destination
N_REGS = 16
N_SEED = 14         # r0..r13 carry two-half seeds; r14 = 0, r15 = index

SLOT_OUT, SLOT_MEM, SLOT_IMEM = 0, 1, 2
STORE_STRIDE_WORDS = 4                    # device_store idx_off unit = 4 WORDS (EXP-0090/0119)

W_PRE_REGS = 0                            # pre-dump  r_i -> word 4*i          (0..60)
W_PRE_SENT = 64
W_POST_REGS = 80                          # post-dump r_i -> word 80 + 4*i     (80..140)
W_POST_SENT = 144
W_SPARE = 148                             # first word a probe store may use
OUT_WORDS = 176
POISON = 0xDEADBEEF

SENT_PRE = 0x5A                           # mov_imm-able (< 128)
SENT_POST = 111

KNOWN_WORDS = set([W_PRE_REGS + i * STORE_STRIDE_WORDS for i in range(N_REGS)]
                  + [W_POST_REGS + i * STORE_STRIDE_WORDS for i in range(N_REGS)]
                  + [W_PRE_SENT, W_POST_SENT])


# --------------------------------------------------------------------------
# float / half bit helpers (host side; the oracle is computed here, not on the GPU)
# --------------------------------------------------------------------------
def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(b):
    return struct.unpack("<f", struct.pack("<I", b & 0xFFFFFFFF))[0]


def f16_bits(x):
    return struct.unpack("<H", struct.pack("<e", float(x)))[0]


def bits_f16(b):
    return struct.unpack("<e", struct.pack("<H", b & 0xFFFF))[0]


def lane(word, half):
    """half 0 = LOW 16 bits, half 1 = HIGH 16 bits."""
    return (word >> (16 * half)) & 0xFFFF


def halfreg_value(regs, h):
    """The fp16 bit pattern the half-register descriptor `h` selects, under the model
    h -> (GPR h>>1, half h&1) with bit 7 a documented DON'T-CARE (EXP-0169 raw: 129..155
    mirrors 1..27). Returns None when the descriptor names a GPR outside the seeded file."""
    r = (h & 0x7F) >> 1
    if r >= N_REGS:
        return None
    return lane(regs[r], h & 1)


def f16_normal_nonzero(b):
    e = (b >> 10) & 0x1F
    return 0 < e < 0x1F                      # not zero/subnormal, not inf/nan


# --------------------------------------------------------------------------
# Scaffolding instructions (built through isadb.assemble; values are ours).
# --------------------------------------------------------------------------
def mov_imm(dst, imm7):
    """2B: d[dst] = imm7. HW-VALIDATED 0..127; imm_top=1 does NOT write and consumes the
    following 2-byte instruction (EXP-0140), so it is hard-rejected here."""
    if not (0 <= imm7 <= 127):
        raise ValueError("mov_imm imm7 must be 0..127 (EXP-0128/EXP-0140)")
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm7, "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0, srcA_size=1,
               imm_flag=None, opsel=4):
    """6B falu2i. `mods=0xC0` is EXP-0101's requirement for a LOAD-sourced operand and
    BREAKS a mov_imm-sourced one (EXP-0141 amendment 1); every seed here is ALU-sourced,
    so mods defaults to 0."""
    b1, sign = isadb.imm_encode(k)
    if imm_flag is None:
        imm_flag = b1 & 1
    return isadb.assemble("falu2i", {
        "dst": dst & 0xF, "imm_flag": imm_flag & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo & 0x7F, "mods": mods & 0xFF})


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None, space=0,
                 addr_mode=0x54, access_desc=0x21, st_format=0x11, st_format_ext=0,
                 st_desc_hi=0x24, elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store, ALU-forwarded form. `extmode = 2*data_reg` is EXP-0090 finding_5
    (HW-VALIDATED for data_reg < 64); `idx_off` unit is 4 WORDS (EXP-0090/EXP-0119)."""
    if extmode is None:
        extmode = (data_reg << 1) & 0xFF
    return isadb.assemble("device_store", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7, "st_format": st_format,
        "st_format_ext": st_format_ext, "idx_off": idx_off & 0x7FF,
        "st_desc_hi": st_desc_hi, "elem_size": elem_size & 0xFF,
        "reserved13": reserved13})


def stop():
    return isadb.assemble("stop", {"reserved": 0})


def store_word(word_idx, data_reg, base_slot=SLOT_OUT):
    """Store r[data_reg] at absolute output WORD index `word_idx`, re-seeding the index
    register first so a release-on-read of r15 cannot relocate the store."""
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(R_IDX, 0)
            + device_store(R_IDX, word_idx // STORE_STRIDE_WORDS, base_slot, data_reg))


# --------------------------------------------------------------------------
# The byte0 == 0x10 half-ALU family, built BYTE BY BYTE.
#
# Built raw rather than through isadb.assemble because db.json pins ALL EIGHT bits of
# byte0 in `match` (DEF-0180-1), which would make every generated instruction write r1
# and would make the H0 destination probe unexpressible. The db FIELD geometry is still
# the authority for every mutation (casematrix.set_field uses db.json's own start/width);
# only byte0's high nibble is reached this way, and that is the hypothesis under test.
# --------------------------------------------------------------------------
FAMILY_LOW_NIBBLE = 0x0


def byte0_dst(dst_reg):
    """byte0 for the half-ALU family with destination GPR `dst_reg` (H0)."""
    return ((dst_reg & 0xF) << 4) | FAMILY_LOW_NIBBLE


def halfop(dst_reg, b1, b2, b3, b4=None, b5=None, b6=None, b7=None):
    """One instruction of the byte0==0x10 family. Length follows from how many trailing
    bytes are supplied; the HARDWARE's length rule is what the LEN arm measures, and this
    builder never assumes it."""
    out = [byte0_dst(dst_reg), b1 & 0xFF, b2 & 0xFF, b3 & 0xFF]
    for b in (b4, b5, b6, b7):
        if b is None:
            break
        out.append(b & 0xFF)
    return bytes(out)


OPSEL_HADD, OPSEL_HMUL, OPSEL_HFMA = 4, 5, 6


def half_add(dst_reg, hA, hB, opflags=0):
    """The 6-byte hadd shape our own k_hadd compiles to: `10 <hB> 1c <hA> 00 c0`.
    byte+2 = (opflags << 3) | opsel."""
    return halfop(dst_reg, hB, ((opflags & 0x1F) << 3) | OPSEL_HADD, hA, 0x00, 0xC0)


# --------------------------------------------------------------------------
# Seeds. TWO tables, and both fill BOTH halves of every seeded GPR.
#
# Stage 1 (high halves): falu2i writes an exact minifloat fixed point into r0..r13. The
#   TOP 16 bits of that fp32 pattern are a valid non-zero NORMAL fp16 value -- that is
#   what EXP-0169's carrier had, and all it had.
# Stage 2 (low halves): one half-ALU add per register writes hi[A_j] + hi[B_j] into
#   r_j's LOW 16 bits (DEF-0180-1: destination = byte0's high nibble; the write is to the
#   low half and preserves the high half -- both directly observed in EXP-0169's raw).
#
# The predicted low halves are checked against the ADEQUACY PREDICATE at import time, and
# the OBSERVED pre-dump is checked against it again on hardware. Validity does not depend
# on the prediction being right: the per-case oracle is computed from the observed
# pre-dump, and a mismatch between predicted and observed seeds is recorded as a finding.
# --------------------------------------------------------------------------
# Magnitudes spread across the minifloat octaves so the fp16 high-half patterns are well
# separated; signs alternate so sums do not collide. Every value must be an EXACT fixed
# point of the falu2i minifloat encoder (asserted below).
SEED_A_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: -0.5, 4: 7.0, 5: -9.0, 6: 11.0,
            7: 13.0, 8: 0.25, 9: -18.0, 10: 22.0, 11: 26.0, 12: -30.0, 13: 0.75}
SEED_B_F = {0: 26.0, 1: -0.75, 2: 13.0, 3: 22.0, 4: 0.5, 5: 3.0, 6: -30.0,
            7: 1.5, 8: 11.0, 9: 0.25, 10: -7.0, 11: 18.0, 12: 5.0, 13: -9.0}


def _low_pairs(table):
    """DETERMINISTIC greedy choice of the (A_j, B_j) half-register descriptors whose sum
    becomes r_j's LOW half: scan a fixed order and take the first pair whose predicted fp16
    sum is normal, non-zero and not already used by any lane. Frozen by being the code.
    Signs are mixed in the seed tables precisely so the sums do not collide -- an all-positive
    table has only ~27 distinct lanes and FAILS the adequacy predicate, which is how this
    construction was arrived at."""
    hi = {j: (f32_bits(table[j]) >> 16) & 0xFFFF for j in range(N_SEED)}
    if len(set(hi.values())) != N_SEED:
        raise AssertionError("seed high halves collide")
    used, pairs, lo = set(hi.values()), {}, {}
    for j in range(N_SEED):
        hit = None
        for a in range(N_SEED):
            for b in range(N_SEED):
                v = f16_bits(bits_f16(hi[a]) + bits_f16(hi[b]))
                if f16_normal_nonzero(v) and v not in used:
                    hit = (a, b, v)
                    break
            if hit:
                break
        if hit is None:
            raise AssertionError("no usable low-half pair for r%d" % j)
        a, b, v = hit
        used.add(v)
        pairs[j] = (2 * a + 1, 2 * b + 1)      # ODD descriptors = the non-zero high halves
        lo[j] = v
    return pairs, hi, lo


def _predict_seed_words(table):
    pairs, hi, lo = _low_pairs(table)
    out = {j: (hi[j] << 16) | lo[j] for j in range(N_SEED)}
    out[R_ZERO] = 0
    out[R_IDX] = 0
    return out, pairs


def adequacy(words):
    """FROZEN seed-adequacy predicate: all 28 half-lanes of r0..r13 are non-zero,
    pairwise distinct, finite and NOT fp16-subnormal. Returns (ok, report).
    Evaluated on the PREDICTED words at import time, and again on the OBSERVED pre-dump
    on hardware -- a carrier that fails it on hardware is rejected before the gated pair."""
    lanes = [((j, h), lane(words[j], h)) for j in range(N_SEED) for h in (0, 1)]
    vals = [v for _, v in lanes]
    bad = [k for k, v in lanes if not f16_normal_nonzero(v)]
    return (not bad and len(vals) == len(set(vals))), {
        "n_lanes": len(lanes), "distinct": len(set(vals)),
        "not_normal_nonzero": bad, "duplicates": len(vals) != len(set(vals))}


SEED_A, LOW_PAIRS_A = _predict_seed_words(SEED_A_F)
SEED_B, LOW_PAIRS_B = _predict_seed_words(SEED_B_F)
LOW_PAIRS = {"A": LOW_PAIRS_A, "B": LOW_PAIRS_B}
SEEDS = {"A": (SEED_A_F, SEED_A, LOW_PAIRS_A), "B": (SEED_B_F, SEED_B, LOW_PAIRS_B)}


# Two FROZEN stage-2 variants. The pilot selects between them with the seed-adequacy
# predicate; the choice is recorded in raw/<run>/00_arm_resolution.json.
#
#   V1  opflags = 0 -- no source release. Every low-half add reads r0's HIGH half, so a
#       release would zero r0 and destroy the rest of the chain. This is the intended
#       variant, and EXP-0169's own opflags sweep shows opflags=0 executes and differs
#       from the compiler's 3 (28 of 32 values moved against a baseline of 3).
#   V2  opflags = 3 -- the compiler-observed value, WITH the released source registers
#       re-materialized by falu2i immediately after each add. Costs 2 extra instructions
#       per register and is used only if V1's observed pre-dump fails adequacy, i.e. if
#       opflags bit(s) turn out to gate the write itself.
SEED_STAGE2_VARIANTS = ("V1_opflags0", "V2_opflags3_rematerialize")


def _stage2(sid, variant):
    table, _, pairs = SEEDS[sid]
    out = []
    for j in range(N_SEED):
        a, b = pairs[j]
        if variant == "V1_opflags0":
            out.append(half_add(j, a, b, opflags=0))
        elif variant == "V2_opflags3_rematerialize":
            out.append(half_add(j, a, b, opflags=3))
            for r in sorted({(a & 0x7F) >> 1, (b & 0x7F) >> 1}):
                if r < N_SEED and r != j:
                    out.append(falu2i_raw(r, R_ZERO, table[r], mods=0))
        else:
            raise ValueError(variant)
    return out


def seed_instrs(sid, variant=SEED_STAGE2_VARIANTS[0]):
    """Stage 1 (falu2i -> high halves) + stage 2 (half-ALU add -> low halves)."""
    table, _, _ = SEEDS[sid]
    out = [mov_imm(R_ZERO, 0), mov_imm(R_IDX, 0)]
    for j in range(N_SEED):
        out.append(falu2i_raw(j, R_ZERO, table[j], mods=0))
    return out + _stage2(sid, variant)


def reseed_one(sid, j, variant=SEED_STAGE2_VARIANTS[0]):
    """Re-materialize r_j fully (used to restore the PRE-sentinel scratch register)."""
    table, _, pairs = SEEDS[sid]
    a, b = pairs[j]
    out = [falu2i_raw(j, R_ZERO, table[j], mods=0)]
    if variant == "V1_opflags0":
        out.append(half_add(j, a, b, opflags=0))
    else:
        out.append(half_add(j, a, b, opflags=3))
        for r in sorted({(a & 0x7F) >> 1, (b & 0x7F) >> 1}):
            if r < N_SEED and r != j:
                out.append(falu2i_raw(r, R_ZERO, table[r], mods=0))
    return out


# --------------------------------------------------------------------------
# Program shapes.
# --------------------------------------------------------------------------
LEN_MARKERS = ((8, 101), (9, 102), (10, 103), (11, 104))


def marker_chain():
    """Four 2-byte mov_imm markers. Placed at the instruction's byte +6, the count that
    SURVIVES reads the HARDWARE's instruction length: 4 -> 6B, 3 -> 8B, 2 -> 10B,
    1 -> 12B, 0 -> 14B. Host-computable, five distinguishable outcomes (H2/H3)."""
    return b"".join(mov_imm(r, v) for r, v in LEN_MARKERS)


def tail_slack():
    """C_LO's 8 bytes of register-NEUTRAL slack between the block and the post-dump:
    an over-consuming length eats pads instead of dump code, so the program SURVIVES
    where C_HI desyncs. That difference is the framing dimension `srcB_desc` controls."""
    return mov_imm(R_ZERO, 0) * 4


def second_consumer(hA, hB):
    """C_LO only: one further half-ALU op after the block, reading the SAME source
    half-registers into R_C2, so an `opflags` release / last-use / publication bit with no
    effect on the block's own result can still change a downstream read. This is the
    ordering dimension EXP-0179's `ret.scoreboard` had no carrier for."""
    return half_add(R_C2, hA, hB, opflags=0)


def dump(base_word):
    out = []
    for r in range(N_REGS):
        out.append(store_word(base_word + r * STORE_STRIDE_WORDS, r))
    return out


def build_program(instrs, region_len, pad_reg=R_ZERO):
    body = b"".join(instrs)
    if len(body) > region_len:
        raise ValueError("program body %d exceeds carrier region %d" % (len(body), region_len))
    rem = region_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + mov_imm(pad_reg, 0) * (rem // 2)
    assert len(out) == region_len
    return out


def synth_program(sid, block, region_len, slack=False, consumer=None,
                  variant=SEED_STAGE2_VARIANTS[0]):
    """seeds -> PRE sentinel (scratch restored) -> PRE-DUMP of all 16 GPRs
    -> [block under test] -> [optional slack] -> [optional second consumer]
    -> POST-DUMP of all 16 GPRs -> POST sentinel -> stop, padded to the region."""
    ins = seed_instrs(sid, variant)
    ins += [mov_imm(R_PRE, SENT_PRE), store_word(W_PRE_SENT, R_PRE)]
    ins += reseed_one(sid, R_PRE, variant)
    ins += dump(W_PRE_REGS)
    ins.append(block)
    if slack:
        ins.append(tail_slack())
    if consumer is not None:
        ins.append(consumer)
    ins += dump(W_POST_REGS)
    ins += [mov_imm(R_SENT, SENT_POST), store_word(W_POST_SENT, R_SENT)]
    ins.append(stop())
    return build_program(ins, region_len)


# --------------------------------------------------------------------------
# Tokenization -- RECORDED, NEVER CITED as an emitter gate (EXP-0170).
# --------------------------------------------------------------------------
def tokenize_first(buf):
    try:
        recs, _ = isadb.disassemble(buf)
        return (recs[0]["mnemonic"], recs[0]["length"]) if recs else (None, None)
    except Exception:
        return (None, None)


def round_trips(buf):
    """`rt_ok`. Recorded as a property of the case. It is NOT evidence that an encoding
    can be emitted (EXP-0170: roundtrip_test.py passes with a broken assembler)."""
    try:
        recs, leftover = isadb.disassemble(buf)
        if leftover:
            return False
        off = 0
        for r in recs:
            if isadb.assemble(r["mnemonic"], r["fields"]) != buf[off:off + r["length"]]:
                return False
            off += r["length"]
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Import-time sanity. These are CODE assertions, not evidence.
# --------------------------------------------------------------------------
for _t, _n in ((SEED_A_F, "SEED_A"), (SEED_B_F, "SEED_B")):
    for _r, _v in _t.items():
        _b1, _s = isadb.imm_encode(_v)
        if isadb.imm_decode(_b1, _s) != _v:
            raise AssertionError("%s[%d]=%r is not an exact minifloat fixed point" % (_n, _r, _v))
for _w, _n in ((SEED_A, "SEED_A"), (SEED_B, "SEED_B")):
    _ok, _rep = adequacy(_w)
    if not _ok:
        raise AssertionError("%s fails the frozen seed-adequacy predicate: %r" % (_n, _rep))

#!/usr/bin/env python3
"""EXP-0203 instruction/program construction + HOST ORACLE (G17P half-precision).

WHAT THIS ADDS RELATIVE TO EXP-0180 (whose program shape this reuses; see PRE_REGISTRATION
section 1.1 and section 4):

  * A HOST-COMPUTED, PER-VALUE-DISCRIMINATING ORACLE.  EXP-0180 recorded no `oracle` key at
    all, so nothing in its raw could discriminate one field value from another; its cases
    were only ever compared against an anchor observation.  Here every case carries a full
    predicted 16-word post-dump, computed on the host from the case's OWN observed pre-dump
    plus a frozen arithmetic model.
  * TWO INFRASTRUCTURE LAYOUTS, so that all 16 values of a 4-bit destination nibble are
    observable somewhere.  EXP-0180's harness could not observe dst = 15 because r15 is its
    store index register; the same limit applies to the four length-marker registers.
  * A BASE INSTANCE WITH NO SOURCE-RELEASE SIDE EFFECT (byte+4 = 0x13 rather than 0x93),
    established offline from EXP-0180's committed raw, so the destination sweep cannot
    collide with a released source lane.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Scaffolding is built through `tools/agx-isa`'s own
READ-ONLY `isadb.assemble`; the two families under test are built BYTE BY BYTE because
`db.json` pins byte0 in `match` and an assembler cannot clear a pinned bit.  No Apple binary
is disassembled.
"""
import hashlib
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

# --------------------------------------------------------------------------
# PINNED ISA.  EXPLICIT resolution -- deliberately NO fall-through to a shared
# copy on the neo (a sibling experiment silently resolved a STALE shared
# db.json through exactly such a fall-through).
# --------------------------------------------------------------------------
ISA_DIR = EXP / "work" / "frozen"
if not ((ISA_DIR / "isadb.py").exists() and (ISA_DIR / "db.json").exists()):
    raise RuntimeError(
        "EXP-0203 pins tools/agx-isa to %s and will not fall back. "
        "Run harness/sync.sh push, which copies work/frozen/ to the neo." % ISA_DIR)
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

DB_SHA256 = "2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4"
ISADB_SHA256 = "500db91a6077cd1968570dd1f7c08ae22a63bbfb39e688168ce711397375aa9f"


def assert_pins():
    got = {p: hashlib.sha256((ISA_DIR / p).read_bytes()).hexdigest()
           for p in ("db.json", "isadb.py")}
    if got["db.json"] != DB_SHA256 or got["isadb.py"] != ISADB_SHA256:
        raise RuntimeError("pinned ISA hash mismatch: %r" % got)
    return {"isa_dir": str(ISA_DIR), "db_sha256": got["db.json"],
            "isadb_sha256": got["isadb.py"]}


# --------------------------------------------------------------------------
# Output-word layout (identical to EXP-0180's, so the two raws are comparable).
# --------------------------------------------------------------------------
N_REGS = 16
SLOT_OUT = 0
STORE_STRIDE_WORDS = 4                    # device_store idx_off unit = 4 WORDS

W_PRE_REGS = 0
W_PRE_SENT = 64
W_POST_REGS = 80
W_POST_SENT = 144
OUT_WORDS = 176
POISON = 0xDEADBEEF

SENT_PRE = 0x5A                           # mov_imm-able (< 128)
SENT_POST = 111

KNOWN_WORDS = set([W_PRE_REGS + i * STORE_STRIDE_WORDS for i in range(N_REGS)]
                  + [W_POST_REGS + i * STORE_STRIDE_WORDS for i in range(N_REGS)]
                  + [W_PRE_SENT, W_POST_SENT])


# --------------------------------------------------------------------------
# float / half bit helpers.  THE ORACLE IS COMPUTED HERE, ON THE HOST.
# --------------------------------------------------------------------------
def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def f16_bits(x):
    """Round a binary64 value to binary16, round-to-nearest-even.  Returns the bit
    pattern, or None when the value is outside binary16's finite range (recorded as
    `oracle_overflow`, never silently clamped)."""
    try:
        return struct.unpack("<H", struct.pack("<e", float(x)))[0]
    except (OverflowError, ValueError):
        return None


def bits_f16(b):
    return struct.unpack("<e", struct.pack("<H", b & 0xFFFF))[0]


def lane(word, half):
    """half 0 = LOW 16 bits, half 1 = HIGH 16 bits."""
    return (word >> (16 * half)) & 0xFFFF


def f16_subnormal(b):
    return ((b >> 10) & 0x1F) == 0 and (b & 0x3FF) != 0


def f16_normal_nonzero(b):
    e = (b >> 10) & 0x1F
    return 0 < e < 0x1F


def hreg(d):
    """Half-register descriptor -> (GPR, half).  Bit 7 is a documented DON'T-CARE
    (EXP-0169 raw: descriptors 129..155 mirror 1..27)."""
    return ((d & 0x7F) >> 1, d & 1)


def hval(regs, d):
    """The fp16 bit pattern descriptor `d` selects.  A descriptor naming a GPR outside the
    16-entry architectural window this harness can see is predicted to read 0 -- a CARRIER
    property, checked per run by the `__ctl_unseeded` control (PRE_REGISTRATION 4.4)."""
    r, h = hreg(d)
    if r >= N_REGS:
        return 0, True                    # (value, unseeded)
    return lane(regs[r], h), False


# --------------------------------------------------------------------------
# Infrastructure layouts.
# --------------------------------------------------------------------------
class Layout:
    def __init__(self, name, r_idx, r_zero, markers):
        self.name = name
        self.R_IDX = r_idx
        self.R_ZERO = r_zero
        self.markers = tuple(markers)                     # ((reg, value), ...)
        self.marker_regs = tuple(m for m, _ in markers)
        self.seeded = tuple(j for j in range(N_REGS) if j not in (r_idx, r_zero))
        # A destination that infrastructure overwrites AFTER the block is not observable.
        self.undecidable_dst = frozenset((r_idx,) + self.marker_regs)

    def as_json(self):
        return {"name": self.name, "R_IDX": self.R_IDX, "R_ZERO": self.R_ZERO,
                "markers": [list(m) for m in self.markers],
                "seeded": list(self.seeded),
                "undecidable_dst": sorted(self.undecidable_dst)}


LAYOUTS = {
    "HI": Layout("HI", r_idx=15, r_zero=14, markers=((10, 101), (11, 102), (12, 103), (13, 104))),
    "LO": Layout("LO", r_idx=0, r_zero=1, markers=((2, 101), (3, 102), (4, 103), (5, 104))),
}


# --------------------------------------------------------------------------
# Scaffolding instructions (built through isadb.assemble; the VALUES are ours).
# --------------------------------------------------------------------------
def mov_imm(dst, imm7):
    """2B: r[dst] = imm7.  HW-VALIDATED 0..127; imm_top=1 does NOT write and consumes the
    following 2-byte instruction (EXP-0140), so it is hard-rejected here."""
    if not (0 <= imm7 <= 127):
        raise ValueError("mov_imm imm7 must be 0..127 (EXP-0128/EXP-0140)")
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm7, "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0, srcA_size=1,
               imm_flag=None, opsel=4):
    """6B falu2i.  Every seed here is ALU-sourced, so `mods` is 0 (EXP-0141 amendment 1:
    `mods=0xC0` is required for a LOAD-sourced operand and BREAKS a mov_imm-sourced one)."""
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
    """14B device_store, ALU-forwarded form.  `extmode = 2*data_reg` is EXP-0090 finding_5;
    `idx_off` unit is 4 WORDS (EXP-0090/EXP-0119)."""
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


def store_word(lay, word_idx, data_reg):
    """Store r[data_reg] at absolute output WORD index, re-seeding the index register first
    so a release-on-read of the index register cannot relocate the store."""
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(lay.R_IDX, 0)
            + device_store(lay.R_IDX, word_idx // STORE_STRIDE_WORDS, SLOT_OUT, data_reg))


# --------------------------------------------------------------------------
# The two families under test, built BYTE BY BYTE.
#
# db.json pins byte0 in `match` for BOTH of them (`half_alu_fma12`: low nibble 0;
# `half_pack`: the whole byte = 0x18), so `isadb.assemble` can never produce an instance
# with a different destination nibble.  That is exactly the field under test, so the bytes
# are laid out here.  Every MUTATION still uses db.json's own start/width geometry.
# --------------------------------------------------------------------------
FMA12_LOW_NIBBLE = 0x0
HALFPACK_BYTE0_TAG = 0x8            # low nibble of half_pack's pinned byte0 (0x18)

OPSEL_HADD, OPSEL_HMUL, OPSEL_HFMA = 4, 5, 6


def fma12(dst_reg, hA=0x0D, hB=0x11, hC=0x12, b2=0x06, b4=0x13,
          tail=(0x00, 0x00, 0x00, 0x80, 0x01, 0x00)):
    """The 12-byte fp16 fma form.
    byte0 = (dst<<4)|0x0, +1 = hA, +2 = (opflags<<3)|opsel, +3 = hB, +4 = modifier/length,
    +5 = hC, +6..+11 = tail (the values our own k_hfma_abs compiles to)."""
    return bytes([((dst_reg & 0xF) << 4) | FMA12_LOW_NIBBLE, hA & 0xFF, b2 & 0xFF,
                  hB & 0xFF, b4 & 0xFF, hC & 0xFF] + [t & 0xFF for t in tail])


def halfpack(dst_reg, hB=0x0D, hA=0x11, b2=0x18):
    """The 4-byte `half_pack` form: byte0 = (dst<<4)|0x8, +1 = hB, +2 = op byte, +3 = hA."""
    return bytes([((dst_reg & 0xF) << 4) | HALFPACK_BYTE0_TAG, hB & 0xFF, b2 & 0xFF,
                  hA & 0xFF])


def half_add(dst_reg, hB, hA, opflags=0):
    """The 6-byte hadd shape our own k_hadd compiles to: `10 <hB> 1c <hA> 00 c0`,
    byte+2 = (opflags<<3)|opsel.  Used only as SEEDING scaffolding."""
    return bytes([((dst_reg & 0xF) << 4) | FMA12_LOW_NIBBLE, hB & 0xFF,
                  ((opflags & 0x1F) << 3) | OPSEL_HADD, hA & 0xFF, 0x00, 0xC0])


# --------------------------------------------------------------------------
# Seeds.  Two tables; both fill BOTH halves of every seeded GPR with a distinct,
# non-zero, NORMAL fp16 value, because a carrier whose lanes are zero cannot show a
# source descriptor moving anything (DEF-0180-A).
#
# Stage 1: falu2i writes an exact minifloat fixed point -> the TOP 16 bits are a valid
#          non-zero normal fp16 pattern.
# Stage 2: one half-ALU add per register writes hi[A] + hi[B] into that register's LOW half
#          (destination = byte0's high nibble; the write preserves the high half).
# --------------------------------------------------------------------------
SEED_VALUES_A = [5.0, 1.5, 3.0, -0.5, 7.0, -9.0, 11.0, 13.0, 0.25, -18.0, 22.0, 26.0,
                 -30.0, 0.75, 1.25, -2.5]
SEED_VALUES_B = [26.0, -0.75, 13.0, 22.0, 0.5, 3.0, -30.0, 1.5, 11.0, 0.25, -7.0, 18.0,
                 5.0, -9.0, -1.75, 6.0]


def _assign(values, lay):
    """Assign seed float values to the layout's seeded registers, in register order."""
    return {j: values[i] for i, j in enumerate(lay.seeded)}


def _low_pairs(table, lay):
    """DETERMINISTIC greedy choice of the (A, B) half-register descriptors whose fp16 sum
    becomes r_j's LOW half: scan a fixed order, take the first pair whose predicted sum is
    normal, non-zero and not already used by any lane.  Frozen by being the code."""
    hi = {j: (f32_bits(table[j]) >> 16) & 0xFFFF for j in lay.seeded}
    if len(set(hi.values())) != len(lay.seeded):
        raise AssertionError("seed high halves collide")
    used, pairs, lo = set(hi.values()), {}, {}
    for j in lay.seeded:
        hit = None
        for a in lay.seeded:
            for b in lay.seeded:
                v = f16_bits(bits_f16(hi[a]) + bits_f16(hi[b]))
                if v is not None and f16_normal_nonzero(v) and v not in used:
                    hit = (a, b, v)
                    break
            if hit:
                break
        if hit is None:
            raise AssertionError("no usable low-half pair for r%d" % j)
        a, b, v = hit
        used.add(v)
        pairs[j] = (2 * a + 1, 2 * b + 1)          # ODD descriptors = the high halves
        lo[j] = v
    return pairs, hi, lo


def seed_plan(sid, layname):
    lay = LAYOUTS[layname]
    table = _assign(SEED_VALUES_A if sid == "A" else SEED_VALUES_B, lay)
    pairs, hi, lo = _low_pairs(table, lay)
    words = {j: (hi[j] << 16) | lo[j] for j in lay.seeded}
    words[lay.R_ZERO] = 0
    words[lay.R_IDX] = 0
    return {"lay": lay, "table": table, "pairs": pairs, "words": words}


def adequacy(words, lay):
    """FROZEN seed-adequacy predicate: every half-lane of every SEEDED register is
    non-zero, pairwise distinct, finite and NOT fp16-subnormal.  Evaluated on the PREDICTED
    words offline and again on the ON-HARDWARE pre-dump; a carrier that fails it on
    hardware is REJECTED before the gated pair, not repaired."""
    lanes = [((j, h), lane(words[j], h)) for j in lay.seeded for h in (0, 1)]
    vals = [v for _, v in lanes]
    bad = [list(k) for k, v in lanes if not f16_normal_nonzero(v)]
    return (not bad and len(vals) == len(set(vals))), {
        "n_lanes": len(lanes), "distinct": len(set(vals)),
        "not_normal_nonzero": bad, "duplicates": len(vals) != len(set(vals))}


def seed_instrs(plan):
    lay = plan["lay"]
    out = [mov_imm(lay.R_ZERO, 0), mov_imm(lay.R_IDX, 0)]
    for j in lay.seeded:
        out.append(falu2i_raw(j, lay.R_ZERO, plan["table"][j], mods=0))
    for j in lay.seeded:
        a, b = plan["pairs"][j]
        out.append(half_add(j, a, b, opflags=0))
    return out


def reseed_one(plan, j):
    lay = plan["lay"]
    a, b = plan["pairs"][j]
    return [falu2i_raw(j, lay.R_ZERO, plan["table"][j], mods=0), half_add(j, a, b, opflags=0)]


# --------------------------------------------------------------------------
# Program assembly.
# --------------------------------------------------------------------------
def marker_chain(lay):
    return b"".join(mov_imm(r, v) for r, v in lay.markers)


def dump(lay, base_word):
    return [store_word(lay, base_word + r * STORE_STRIDE_WORDS, r) for r in range(N_REGS)]


def build_program(instrs, region_len, pad_reg):
    body = b"".join(instrs)
    if len(body) > region_len:
        raise ValueError("program body %d exceeds carrier region %d" % (len(body), region_len))
    rem = region_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + mov_imm(pad_reg, 0) * (rem // 2)
    assert len(out) == region_len
    return out


# The PRE-sentinel scratch register: a SEEDED register that is not infrastructure and is
# not one of the operand registers (r6..r9), chosen per layout and restored immediately.
PRE_SCRATCH = {"HI": 12, "LO": 4}


def synth_program(plan, block, region_len):
    """seeds -> PRE sentinel (scratch restored) -> PRE-DUMP of all 16 GPRs
    -> [block: instruction under test + 4 length markers] -> POST-DUMP of all 16 GPRs
    -> POST sentinel (register re-materialized at that moment) -> stop, padded."""
    lay = plan["lay"]
    scratch = PRE_SCRATCH[lay.name]
    ins = seed_instrs(plan)
    ins += [mov_imm(scratch, SENT_PRE), store_word(lay, W_PRE_SENT, scratch)]
    ins += reseed_one(plan, scratch)
    ins += dump(lay, W_PRE_REGS)
    ins.append(block)
    ins += dump(lay, W_POST_REGS)
    sent_reg = scratch
    ins += [mov_imm(sent_reg, SENT_POST), store_word(lay, W_POST_SENT, sent_reg)]
    ins.append(stop())
    return build_program(ins, region_len, pad_reg=lay.R_ZERO)


# --------------------------------------------------------------------------
# Tokenization -- RECORDED, NEVER CITED as an emitter gate (EXP-0170: the repo's own
# round-trip suite passes unmodified against a deliberately broken assembler).
# --------------------------------------------------------------------------
def tokenize_first(buf):
    try:
        recs, _ = isadb.disassemble(buf)
        return (recs[0]["mnemonic"], recs[0]["length"]) if recs else (None, None)
    except Exception:                                              # noqa: BLE001
        return (None, None)


def round_trips(buf):
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
    except Exception:                                              # noqa: BLE001
        return False

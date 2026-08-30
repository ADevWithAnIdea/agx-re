#!/usr/bin/env python3
"""EXP-0205 carrier definitions, authored inputs, and HOST-COMPUTED oracles.

FROZEN at pre-registration (after the pre-freeze calibration recorded in
`raw/prefreeze/calibration.json`, which refuted two of the design's starting
premises -- see PROGRESS.md and PRE_REGISTRATION.md section 3).  Imported by
`run.py` (capture), `analysis/gen_arms.py` (arm construction) and
`analysis/verdicts.py` (scoring), so the three cannot disagree about what was
built or what was predicted.

THE ORACLE IS DISCRIMINATING, NOT CONSTANT
==========================================
The dispatch's hardest requirement, and the reason for 32 separate output words.
For every field under test except the two `cache` bits, the prediction is a
DIFFERENT 32-word vector for different values of the field:

  simd_reduce.op      ior / isum / smax / umax (int carriers, opcls=1) and
                      fmin / f32sum / fmax (float carrier, opcls=0) are four and
                      three distinct predicted vectors.  The int inputs contain
                      ONE NEGATIVE WORD precisely so that smax != umax; with
                      all-positive inputs those two values of the field would be
                      indistinguishable BY CONSTRUCTION.
  simd_reduce.dtype   reduce / inclusive scan / exclusive scan of the SAME op
                      differ in 31 of 32 lanes.  A single-word read-back could
                      not tell them apart at all.
  simd_shuffle.dir    0 -> every lane reads lane 5; 1 -> lane t reads lane t^5.
                      Both were CONFIRMED against hardware at their own compiled
                      baselines in calibration, before any splice was scored.
  simd_ballot.pred    calibration REFUTED db.json's mapping (both the ballot and
                      the active-mask form compile with pred=0 on G17P), so the
                      per-value oracle for pred!=0 is None -- we predict nothing
                      we cannot derive -- and the field is instead tested
                      against the pre-registered hypothesis H1, evaluated over
                      the whole swept range in analysis/verdicts.py.

`None` means WE DO NOT PREDICT this value.  A case with no prediction is
recorded with its full observation and is NEVER scored as a match: silence is
not a pass.  It still counts for MOVEMENT, which is what the promotion gate
reads, and `analysis/semantics.py` identifies it against a named host-computed
catalogue afterwards.

THE THREE INSTRUMENTS (FIELD-SWEEP-PROTOCOL section 7)
======================================================
1. POISONED READ-BACK.  Every carrier binds its output slot as an INPUT file
   pre-filled with POISON(i) = 0xDEADBEEF+i, so "wrote the right value" /
   "wrote a wrong value" / "never ran at all" are three distinguishable
   outcomes.  Against a zero buffer, `not_written` and `silent_zero` read the
   same, and this ISA produces silent zeros constantly.
2. INTEGRITY SENTINEL.  out[72] = 12345, stored FIRST in every kernel through a
   constant path, in no register any descriptor under test names.  A dispatch
   whose sentinel is absent is `invalid_run`, is retried, and is never scored.
3. The OS fault-classification string is recorded on every non-OK case
   (run.py); `InnocentVictim` is retried before anything is concluded.

CLEAN-ROOM: OWN-SHADER.  Only our own MSL in kernels/ and its compiled bytes.
Shape (not values) follows EXP-0184 harness/carriers184.py, our own code.
"""
import struct

M32 = 0xFFFFFFFF
NWORDS = 80
VAL_WORDS = list(range(0, 32))
SEC_WORDS = list(range(32, 64))
SENT_WORD = 72
SENT_VAL = 12345
DEAD_WORDS = list(range(64, 72)) + list(range(73, 80))

# Two asymmetric ballot predicates.  Each is distinct from 0xFFFFFFFF
# (all-active), 0xAAAAAAAA (odd lanes), 0x00000000 (silent zero), from its own
# bit-reversal, and from the other -- so every trivial confound has a different
# value, and a moved observation can be tested for predicate-dependence.
BALLOT_MASK = 0x6C8AF35D
BALLOT_MASK2 = 0x35D6C8AF
INACTIVE_FILL = 0x00C0FFEE
SHUF_LANE = 5


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n=NWORDS):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def pack_u32(v):
    return b"".join(struct.pack("<I", x & M32) for x in v)


def pack_f32(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def bits_f32(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def from_bits(u):
    return struct.unpack("<f", struct.pack("<I", u & M32))[0]


def s32(x):
    x &= M32
    return x - (1 << 32) if x >= (1 << 31) else x


# ------------------------------------------------------------------- inputs
PRESSURE = [(0x9E3779B9 ^ (k * 0x01000193)) & M32 for k in range(32)]

BALLOT_IN = [(BALLOT_MASK >> t) & 1 for t in range(32)] + PRESSURE
BALLOT_IN2 = [(BALLOT_MASK2 >> t) & 1 for t in range(32)] + PRESSURE

# ONE NEGATIVE WORD (lane 31) so that smax != umax and isum != ior.  Without it
# op values 2 and 3 predict the same vector and the sweep could not tell them
# apart however clean the data was.
REDUCE_IN = [(7 * t + 3) for t in range(31)] + [0xFFFFFF00] + PRESSURE

# Exact binary fractions: every partial sum is exact in f32, so the scan oracles
# are exact predictions and not floating-point approximations.
FREDUCE_IN = [1.5 + 0.25 * t for t in range(32)] + [0.0] * 32

SHUFFLE_IN = [1000 + 13 * t for t in range(32)] + PRESSURE


# ------------------------------------------------------------- reduce model
# Named semantics, host-computed.  `shape` in {reduce, incl, excl}.
INT_OPS = ("ior", "iand", "isum", "ixor", "smax", "smin", "umax", "umin")
FLT_OPS = ("f32sum", "f32prod", "fmin", "fmax")

_IDENTITY = {"ior": 0, "iand": M32, "isum": 0, "ixor": 0,
             "smax": 0x80000000, "smin": 0x7FFFFFFF, "umax": 0, "umin": M32}


def _step(op, acc, v):
    if op == "ior":
        return (acc | v) & M32
    if op == "iand":
        return (acc & v) & M32
    if op == "isum":
        return (acc + v) & M32
    if op == "ixor":
        return (acc ^ v) & M32
    if op == "smax":
        return (max(s32(acc), s32(v))) & M32
    if op == "smin":
        return (min(s32(acc), s32(v))) & M32
    if op == "umax":
        return max(acc & M32, v & M32)
    if op == "umin":
        return min(acc & M32, v & M32)
    raise ValueError(op)


def int_model(op, shape, vals):
    vals = [v & M32 for v in vals]
    if shape == "reduce":
        acc = _IDENTITY[op]
        for v in vals:
            acc = _step(op, acc, v)
        return [acc] * 32
    out, acc = [], _IDENTITY[op]
    for t in range(32):
        if shape == "incl":
            acc = _step(op, acc, vals[t])
            out.append(acc)
        else:
            out.append(acc)
            acc = _step(op, acc, vals[t])
    return out


def _fstep(op, acc, v):
    if op == "f32sum":
        return f32(acc + v)
    if op == "f32prod":
        return f32(acc * v)
    if op == "fmin":
        return min(acc, v)
    if op == "fmax":
        return max(acc, v)
    raise ValueError(op)


_FIDENT = {"f32sum": 0.0, "f32prod": 1.0,
           "fmin": float("inf"), "fmax": float("-inf")}


def flt_model(op, shape, vals):
    vals = [f32(x) for x in vals]
    if shape == "reduce":
        acc = _FIDENT[op]
        for v in vals:
            acc = _fstep(op, acc, v)
        return [bits_f32(acc)] * 32
    out, acc = [], _FIDENT[op]
    for t in range(32):
        if shape == "incl":
            acc = _fstep(op, acc, vals[t])
            out.append(bits_f32(acc))
        else:
            out.append(bits_f32(acc))
            acc = _fstep(op, acc, vals[t])
    return out


# The EMPIRICAL op mapping, anchored on the calibrated baselines rather than on
# db.json's enum text (whose pair ordering is NOT opcls order: at opcls=1 the
# hardware gave `isum` and `smax`, the FIRST names of "isum/ixor" and
# "smax/smin"; at opcls=0 it gave `f32sum`, the SECOND name of "f32prod/f32sum").
# Only the entries with a measured anchor or its direct family are predicted.
OPCLS1_OPS = {0: "ior", 1: "isum", 2: "smax", 3: "umax"}     # 1,2 measured
OPCLS0_FLT = {5: "fmin", 6: "f32sum", 7: "fmax"}             # 6 measured


def _shuf(direction, src=None):
    src = [v & M32 for v in (src or SHUFFLE_IN)[:32]]
    if direction == 0:
        return [src[SHUF_LANE]] * 32
    return [src[t ^ SHUF_LANE] for t in range(32)]


def _reuse_sec(src_words, r_hi):
    """out[32+t] = (v*3 + XOR(16-wide pressure window) + (r>>31))."""
    out = []
    for t in range(32):
        s = 0
        for k in range(16):
            s ^= src_words[32 + ((t + k) & 31)]
        out.append(((src_words[t] * 3) + s + r_hi) & M32)
    return out


# ----------------------------------------------------------------- carriers
def _base(metal, func, ins_words, dtype, doc, why, sec=False, ftype=False):
    tail = list(DEAD_WORDS) if sec else sorted(set(SEC_WORDS + DEAD_WORDS))
    return {
        "metal": metal, "func": func, "grid": 32, "tg": 32, "nwords": NWORDS,
        "dtype": dtype, "sent_word": SENT_WORD, "sent_val": SENT_VAL,
        "val_words": VAL_WORDS, "sec_words": SEC_WORDS if sec else [],
        "tail_words": tail, "has_sec": sec,
        "inputs": {1: ("in_%s.bin" % func,
                       pack_f32(ins_words) if ftype else pack_u32(ins_words))},
        "in_words": list(ins_words), "float_in": ftype,
        "doc": doc, "why": why,
    }


CARRIERS = {
    # ------------------------------------------------------------ simd_ballot
    "sb_ballot": _base(
        "kernels/k_ballot.metal", "k_sb_ballot", BALLOT_IN, "u32",
        "simd_ballot(predicate), 32 active lanes, divergent predicate",
        "simd_ballot.pred + .cache. Every lane ACTIVE but the predicate "
        "divergent, so ballot(predicate)=0x6C8AF35D and the all-active mask "
        "0xFFFFFFFF are DIFFERENT observations -- the minimum condition under "
        "which `pred` can be observed at all."),
    "sb_ballot2": _base(
        "kernels/k_ballot.metal", "k_sb_ballot2", BALLOT_IN2, "u32",
        "same code, SECOND predicate mask 0x35D6C8AF",
        "ATTRIBUTION arm for simd_ballot.pred: tells a moved observation that "
        "still tracks the predicate (ballot-like) apart from one that is the "
        "same on both masks (predicate-independent / active-mask-like)."),
    "sb_active": _base(
        "kernels/k_ballot.metal", "k_sb_active", BALLOT_IN, "u32",
        "simd_active_threads_mask() inside a divergent if",
        "simd_ballot.pred + .cache, a structurally DIFFERENT compiled form of "
        "the same descriptor: byte+5 = 0x02 and the byte+7..9 tail is 08 02 18 "
        "rather than 58 22 12. Calibration refuted the premise that it would "
        "carry the other value of `pred` -- it does not, and that refutation is "
        "part of this experiment's result."),
    "sb_reuse": _base(
        "kernels/k_ballot.metal", "k_sb_reuse", BALLOT_IN, "u32",
        "ballot with the predicate source re-read after it, under register pressure",
        "simd_ballot.cache -- THE DIMENSION ARM. Public docs for the older AGX "
        "describe operand cache/discard as 'retain in register cache' / 'future "
        "reads undefined, frees register for reuse'. That dimension is the "
        "content of the SOURCE REGISTER AFTER the instruction, and expressing it "
        "needs BOTH a later read (EXP-0172's `deadsrc` carrier deliberately "
        "removed it) AND register pressure (no prior carrier varied it). Here 16 "
        "loads stay live across the ballot and the predicate source is read "
        "again after it, into out[32..63].",
        sec=True),

    # ------------------------------------------------------------ simd_reduce
    "sr_sum": _base(
        "kernels/k_reduce.metal", "k_sr_sum", REDUCE_IN, "u32",
        "simd_sum(int) -- baseline op=1 dtype=3 opcls=1",
        "simd_reduce.op + .dtype. Per-lane read-back makes reduce / inclusive "
        "scan / exclusive scan three different 32-word vectors."),
    "sr_scan": _base(
        "kernels/k_reduce.metal", "k_sr_scan", REDUCE_IN, "u32",
        "simd_prefix_inclusive_sum(int) -- baseline op=1 dtype=9",
        "second dtype baseline: the sweep runs scan->reduce as well as "
        "reduce->scan, and byte+4/byte+6 differ from the reduce form too."),
    "sr_max": _base(
        "kernels/k_reduce.metal", "k_sr_max", REDUCE_IN, "u32",
        "simd_max(int) -- baseline op=2 dtype=7",
        "second op baseline and a third dtype baseline."),
    "sr_fsum": _base(
        "kernels/k_reduce.metal", "k_sr_fsum", FREDUCE_IN, "f32",
        "simd_sum(float) -- baseline op=6 dtype=18 opcls=0",
        "the float half of the op enum, and the only carrier with opcls=0. On "
        "the int carriers a float-op reinterpretation of small ints is a "
        "denormal and is not honestly predictable, so the float enum values get "
        "their oracle here instead of being scored against a guess.",
        ftype=True),

    # ----------------------------------------------------------- simd_shuffle
    "sh_bc": _base(
        "kernels/k_shuffle.metal", "k_sh_bc", SHUFFLE_IN, "u32",
        "simd_broadcast(v,5) -- baseline dir=0, cache=1",
        "simd_shuffle.dir + .cache. 32 DISTINCT per-lane source values, so "
        "dir=0 (all lanes read lane 5) and dir=1 (lane t reads lane t^5) are two "
        "completely different predicted vectors, both confirmed at their own "
        "baselines in calibration."),
    "sh_xor": _base(
        "kernels/k_shuffle.metal", "k_sh_xor", SHUFFLE_IN, "u32",
        "simd_shuffle_xor(v,5) -- baseline dir=1, cache=1",
        "opposite `dir` baseline: each carrier's splice target is the other "
        "carrier's measured baseline vector."),
    "sh_reuse": _base(
        "kernels/k_shuffle.metal", "k_sh_reuse", SHUFFLE_IN, "u32",
        "shuffle with the source re-read after it, under register pressure "
        "-- baseline dir=0, cache=0",
        "simd_shuffle.cache -- THE DIMENSION ARM, same construction as sb_reuse. "
        "It also carries the OTHER baseline value of `cache`: the compiler chose "
        "byte+2 = 0x54 here and 0x56 on sh_bc/sh_xor, and both are correct, "
        "which is itself an observation about the field.",
        sec=True),

    # ------------------------------------------------------------ width probe
    "sb_width": _base(
        "kernels/k_ballot.metal", "k_sb_width", BALLOT_IN, "u32",
        "SIMD width probe -- never spliced",
        "Records the measured SIMD width, lane index and simdgroup index per "
        "thread so the width is an OBSERVATION, not an assumption."),
}

# Which instruction and which fields each carrier is an arm for.
CARRIER_TARGET = {
    "sb_ballot": "simd_ballot", "sb_ballot2": "simd_ballot",
    "sb_active": "simd_ballot", "sb_reuse": "simd_ballot",
    "sr_sum": "simd_reduce", "sr_scan": "simd_reduce",
    "sr_max": "simd_reduce", "sr_fsum": "simd_reduce",
    "sh_bc": "simd_shuffle", "sh_xor": "simd_shuffle",
    "sh_reuse": "simd_shuffle", "sb_width": None,
}

# Baseline op/shape per reduce carrier, from the CALIBRATED bytes.
REDUCE_BASE = {
    "sr_sum":  {"opcls": 1, "op": 1, "dtype": 3,  "op_name": "isum",   "shape": "reduce"},
    "sr_scan": {"opcls": 1, "op": 1, "dtype": 9,  "op_name": "isum",   "shape": "incl"},
    "sr_max":  {"opcls": 1, "op": 2, "dtype": 7,  "op_name": "smax",   "shape": "reduce"},
    "sr_fsum": {"opcls": 0, "op": 6, "dtype": 18, "op_name": "f32sum", "shape": "reduce"},
}

# dtype value -> shape, from db.json's own enum (i32/f16/f32 reduce vs incl/excl
# scan).  Only the entries whose shape the enum states are used.
DTYPE_SHAPE = {3: "reduce", 7: "reduce", 8: "reduce", 18: "reduce", 19: "reduce",
               9: "incl", 16: "incl", 34: "incl",
               11: "excl", 24: "excl", 50: "excl"}
DTYPE_INT = {3, 7, 9, 11}
DTYPE_F32 = {18, 34, 50}


def out_inputs(name):
    """Input file specs, INCLUDING the poison pre-fill of the output slot."""
    c = CARRIERS[name]
    ins = {0: ("poison_%s.bin" % name, poison_bytes(c["nwords"]))}
    ins.update(c["inputs"])
    return ins


# -------------------------------------------------------- baseline oracles
def baseline_oracle(name):
    if name in ("sb_ballot", "sb_reuse"):
        return [BALLOT_MASK] * 32
    if name == "sb_ballot2":
        return [BALLOT_MASK2] * 32
    if name == "sb_active":
        # CALIBRATED, and the pre-calibration prediction (0x6C8AF35D) is
        # recorded as REFUTED in raw/prefreeze/calibration.json: the observed
        # active mask is all-ones, so either the region is predicated rather
        # than divergent or the mask reports resident rather than executing
        # lanes.  We do not claim which.
        return [M32 if ((BALLOT_MASK >> t) & 1) else INACTIVE_FILL
                for t in range(32)]
    if name in REDUCE_BASE:
        b = REDUCE_BASE[name]
        if name == "sr_fsum":
            return flt_model(b["op_name"], b["shape"], FREDUCE_IN[:32])
        return int_model(b["op_name"], b["shape"], REDUCE_IN[:32])
    if name == "sh_bc":
        return _shuf(0)
    if name == "sh_xor":
        return _shuf(1)
    if name == "sh_reuse":
        return _shuf(0)
    return None


def baseline_sec_oracle(name):
    """Predicted out[32..63] for the reuse carriers (None elsewhere)."""
    if name == "sb_reuse":
        return _reuse_sec([v & M32 for v in BALLOT_IN], (BALLOT_MASK >> 31) & 1)
    if name == "sh_reuse":
        return _reuse_sec([v & M32 for v in SHUFFLE_IN], (_shuf(0)[0] >> 31) & 1)
    return None


def oracle_for(name, instr, field, value):
    """The DISCRIMINATING per-value oracle, or None where we predict nothing."""
    if field is None:
        return baseline_oracle(name)

    # ------------------------------------------------------- simd_ballot.pred
    if instr == "simd_ballot" and field == "pred":
        # Calibration showed BOTH compiled forms carry pred=0, refuting
        # db.json's 0x07/0x17 mapping, so only the baseline value is predicted.
        # `pred` is judged instead by movement plus hypothesis H1, which is
        # evaluated over the whole range in analysis/verdicts.py.
        return baseline_oracle(name) if value == 0 else None

    # --------------------------------------------------------- simd_reduce.op
    if instr == "simd_reduce" and field == "op":
        b = REDUCE_BASE.get(name)
        if not b:
            return None
        shape = b["shape"]
        if b["opcls"] == 1:
            nm = OPCLS1_OPS.get(value)
            return int_model(nm, shape, REDUCE_IN[:32]) if nm else None
        nm = OPCLS0_FLT.get(value)
        return flt_model(nm, shape, FREDUCE_IN[:32]) if nm else None

    # ------------------------------------------------------ simd_reduce.dtype
    if instr == "simd_reduce" and field == "dtype":
        b = REDUCE_BASE.get(name)
        if not b:
            return None
        shape = DTYPE_SHAPE.get(value)
        if shape is None:
            return None
        if name == "sr_fsum":
            return (flt_model(b["op_name"], shape, FREDUCE_IN[:32])
                    if value in DTYPE_F32 else None)
        return (int_model(b["op_name"], shape, REDUCE_IN[:32])
                if value in DTYPE_INT else None)

    # ------------------------------------------------------ simd_shuffle.dir
    if instr == "simd_shuffle" and field == "dir":
        return _shuf(value) if name in ("sh_bc", "sh_xor", "sh_reuse") else None

    # `cache` on either instruction, and every control field: the prediction is
    # the carrier's baseline vector.  A CONSTANT ORACLE IS THE CORRECT ORACLE
    # for a bit that is supposed to be inert -- and, exactly because it cannot
    # fail, it is NOT what promotes anything here.  Promotion reads MOVEMENT
    # plus the detection-power controls (analysis/verdicts.py).
    return baseline_oracle(name)


# ---------------------------------------------------------------- decoding
def summarize(name, blob):
    c = CARRIERS[name]
    words = u32s(blob)
    obs = {
        "vals_u32": [words[i] for i in c["val_words"]],
        "sec_u32": [words[i] for i in c["sec_words"]],
        "sent_u32": words[c["sent_word"]] if c["sent_word"] < len(words) else None,
        "tail_poison_ok": all(words[i] == POISON(i)
                              for i in c["tail_words"] if i < len(words)),
    }
    return obs, words


def sentinel_ok(name, words):
    c = CARRIERS[name]
    i = c["sent_word"]
    return i < len(words) and words[i] == c["sent_val"]


def unwritten(name, words):
    c = CARRIERS[name]
    return [i for i in c["val_words"] if i < len(words) and words[i] == POISON(i)]


def match_oracle(name, words, expect):
    """True iff every value word equals its prediction.  `expect is None` (we
    made no prediction) is NEVER a match -- it returns None, not True."""
    if expect is None:
        return None
    c = CARRIERS[name]
    for k, w in enumerate(c["val_words"]):
        if w >= len(words) or (words[w] & M32) != (expect[k] & M32):
            return False
    return True

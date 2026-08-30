#!/usr/bin/env python3
"""EXP-0201 carrier definitions, authored inputs, and the HOST FUNCTION LIBRARY.

Every oracle here is computed on the HOST from the MSL WE WROTE
(`kernels/k_falu201.metal`) -- never from an observed GPU output.

WHY A LIBRARY AND NOT A SINGLE EXPECTED VECTOR
----------------------------------------------
`copysign.operands` has already been swept dense on the M4 -- 256 legal values,
256 distinct encodings, no faults, 100 % cross-run agreement -- and it stayed
`untested`, because the sweep produced **one** distinct valid payload against
**one** constant oracle. Values that run legally and are indistinguishable are a
hazard map, not a semantic. So the oracle here is a *per-value prediction* drawn
from a library of named host-computed candidate functions, and every case
records which library member the hardware actually produced (`observed_fn`).

POISONED READ-BACK (protocol section 7, instrument 1): buffer 0 is bound to a
file pre-filled with POISON(i) = 0xDEADBEEF + i, so "wrote zero" and "never ran"
are distinguishable. INTEGRITY SENTINEL (instrument 2): out[8] = 7.5f, written
first, through a path independent of the instruction under test.

CLEAN-ROOM: OWN-SHADER. Only our own MSL and its compiled bytes.
"""
import struct

M32 = 0xFFFFFFFF
NWORDS = 32


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def pack_f32(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def v32(v):
    return [f32(x) for x in v]


# --------------------------------------------------------------------- inputs
# falu3 / falu3_srcmod12 -- chosen so a+b, a*b, a*b+a, a*b+c, a-b, -b, a, b, c
# and 0 are pairwise-distinct 8-lane vectors (asserted by oracle_check.py).
F3_A = v32([3.0,  5.0,  7.0, 11.0,  2.5, -4.0,  6.0,  1.5])
F3_B = v32([2.0, -3.0,  4.0,  0.5,  8.0,  1.25, -2.0, 9.0])
F3_C = v32([10.0, 20.0, -5.0,  3.0,  7.0, -1.5, 12.0, 0.25])

# falu3_ext -- the same library must stay distinct AFTER clamp(x, 0, 1).
FE_A = v32([0.25,  0.5,   0.75,  0.125, 0.375, 0.625, 0.875, 0.0625])
FE_B = v32([-0.5,  0.25, -0.125, 0.75, -0.625, 0.375, -0.9,   0.5])
FE_C = v32([0.6,   0.1,   0.4,   0.05,  0.8,   0.2,   0.3,    0.7])

# fspecial_est -- exactly representable rsqrt/rcp/sqrt, never zero, and a SECOND
# live float `b` whose magnitude is orders away from `a` in every lane, so an
# estimate seeded from the wrong register cannot be rescued by the refinement.
FS_A = v32([4.0, 0.25, 16.0, 100.0, 0.0625, 2.0, 9.0, 1.5625])
FS_B = v32([1024.0, 4096.0, 0.001953125, 65536.0, 262144.0, 0.000244140625,
            16384.0, 0.00048828125])

# copysign -- ASYMMETRIC, one lane of the sign source is -0.0, and lanes 4/5 have
# sign(a) == sign(b) on purpose: with all signs opposite, copysign(a,b) collides
# with -a and the library stops discriminating.
CS_A = v32([5.0, -5.0,  3.25, -3.25,  9.5, -9.5,  1.75, -1.75])
CS_B = v32([-2.0,  2.0, -8.0,   8.0,   0.5, -0.5, -0.0,   6.0])


# ---- Phase 3 adversarial input sets (AMENDMENT A, gate C) -------------------
# Signed zero, infinities, NaN, a denormal, and the 2^24 rounding boundary, so
# that an operation map cannot be read off two well-behaved magnitude vectors.
DEN = 1.401298464324817e-45          # smallest positive denormal
BIG = 16777216.0                     # 2^24: BIG + 1 rounds back to BIG
NAN = float("nan")
IN_ = float("inf")

F3X_A = [-0.0,  2.0,  1.0,  DEN,  BIG, -1.5,  IN_,  0.25]
F3X_B = [3.0,  -0.0,  IN_,  2.0,  1.0,  2.0,  0.0,  -4.0]
F3X_C = [1.0,   1.0, -1.0,  0.0,  1.0, -0.5,  2.0,   0.125]

# The saturating form clamps to [0,1], and `saturate(NaN)` is not something we
# can predict on the host with confidence, so the extended set for the ext form
# deliberately carries signed zero, a denormal and the rounding boundary but NO
# NaN and NO infinity. That limitation is stated rather than papered over.
FEX_A = [-0.0,  0.5,  0.25, DEN,  0.75, 0.125, 0.875, 0.0625]
FEX_B = [0.75, -0.0,  0.5,  1.0,  0.25, 0.5,  -0.5,   0.5]
FEX_C = [0.125, 0.25, 0.0,  0.5,  0.375, 0.0625, 0.75, 0.03125]

CSX_A = [-0.0,  0.0,  IN_, -IN_,  DEN, -DEN,  BIG,  NAN]
# NOT the exact sign-inverse of CSX_A: with all signs opposite, copysign(a,b)
# collides with -a and copysign(b,a) with -b, and the library stops
# discriminating a sign COPY from a NEGATION. oracle_check.py caught exactly
# that on the first draft of this set, before any device time.
CSX_B = [1.0,  -1.0, -1.0, -1.0, -1.0,  1.0, -1.0,   1.0]


def _copysign(x, y):
    return f32(struct.unpack("<f", struct.pack(
        "<I", (struct.unpack("<I", struct.pack("<f", x))[0] & 0x7FFFFFFF)
        | (struct.unpack("<I", struct.pack("<f", y))[0] & 0x80000000)))[0])


def _clamp01(v):
    return [f32(0.0 if x < 0.0 else (1.0 if x > 1.0 else x)) for x in v]


# ------------------------------------------------------- host function library
def falu3_library(a, b, c, sat=False):
    """Named candidate 8-lane vectors for a three-source float ALU op.

    The six named entries `a+b`, `a*b`, `a*b+a`, `-b`, `zero`, `a*b+c` are the
    operation map `db.json`'s `falu3.op` note publishes for the low 3 bits of
    byte+2 (EXP-0160, G17P). They are pre-registered PREDICTIONS here, not
    assumptions: a class whose observed vector matches none of them refutes the
    published map, which is refuter R1a.
    """
    lib = {
        "a+b":    [f32(x + y) for x, y in zip(a, b)],
        "a*b":    [f32(x * y) for x, y in zip(a, b)],
        "a*b+a":  [f32(x * y + x) for x, y in zip(a, b)],
        "a*b+c":  [f32(x * y + z) for x, y, z in zip(a, b, c)],
        "-b":     [f32(-y) for y in b],
        "zero":   [f32(0.0)] * len(a),
        "a":      list(a),
        "b":      list(b),
        "c":      list(c),
        "a-b":    [f32(x - y) for x, y in zip(a, b)],
        "a*b-c":  [f32(x * y - z) for x, y, z in zip(a, b, c)],
        "a+c":    [f32(x + z) for x, z in zip(a, c)],
        "b*c":    [f32(y * z) for y, z in zip(b, c)],
        "-a*b+c": [f32(-(x * y) + z) for x, y, z in zip(a, b, c)],
    }
    if sat:
        lib = {k: _clamp01(v) for k, v in lib.items()}
    return lib


def copysign_library(a, b):
    """Thirteen named candidates for a sign-combine ALU op. `operands` is
    modelled as the src/dst descriptor, so the members that matter are the ones
    that differ by WHICH operand plays WHICH role."""
    return {
        "copysign(a,b)": [_copysign(x, y) for x, y in zip(a, b)],
        "copysign(b,a)": [_copysign(y, x) for x, y in zip(a, b)],
        "a":     list(a),
        "b":     list(b),
        "|a|":   [f32(abs(x)) for x in a],
        "|b|":   [f32(abs(y)) for y in b],
        "-a":    [f32(-x) for x in a],
        "-b":    [f32(-y) for y in b],
        "-|a|":  [f32(-abs(x)) for x in a],
        "-|b|":  [f32(-abs(y)) for y in b],
        "zero":  [f32(0.0)] * len(a),
        "a*b":   [f32(x * y) for x, y in zip(a, b)],
        "a+b":   [f32(x + y) for x, y in zip(a, b)],
    }


def fspecial_library(a, b):
    """Named candidates for a special-function estimate + refinement. The two
    input vectors are orders of magnitude apart in every lane, so `rsqrt(a)` and
    `rsqrt(b)` are unmistakable, which is the detection power the previous
    `srcA` arms lacked."""
    def rs(v):
        return [f32(1.0 / (x ** 0.5)) for x in v]

    def rc(v):
        return [f32(1.0 / x) for x in v]

    def sq(v):
        return [f32(x ** 0.5) for x in v]
    return {
        "rsqrt(a)": rs(a), "rsqrt(b)": rs(b),
        "rcp(a)": rc(a),   "rcp(b)": rc(b),
        "sqrt(a)": sq(a),  "sqrt(b)": sq(b),
        "a": list(a), "b": list(b),
        "zero": [f32(0.0)] * len(a),
    }


# ------------------------------------------------------------------- carriers
def _c(func, kind, ins, oracle_vals, lib, aux, doc):
    tail = [i for i in range(9, NWORDS) if i not in (aux or [])]
    return {"metal": "kernels/k_falu201.metal", "func": func, "kind": kind,
            "grid": 8, "tg": 8, "nwords": NWORDS, "dtype": "f32",
            "sent_word": 8, "sent_val": f32(7.5),
            "val_words": list(range(8)),
            "aux_words": list(aux or []),
            "tail_words": tail,
            "inputs": ins, "oracle": oracle_vals, "library": lib,
            "identity_post": True, "doc": doc}


_F3_INS = {1: ("f3_a.bin", pack_f32(F3_A)), 2: ("f3_b.bin", pack_f32(F3_B)),
           3: ("f3_c.bin", pack_f32(F3_C))}
_FE_INS = {1: ("fe_a.bin", pack_f32(FE_A)), 2: ("fe_b.bin", pack_f32(FE_B)),
           3: ("fe_c.bin", pack_f32(FE_C))}
_FS_INS = {1: ("fs_a.bin", pack_f32(FS_A)), 2: ("fs_b.bin", pack_f32(FS_B))}
_CS_INS = {1: ("cs_a.bin", pack_f32(CS_A)), 2: ("cs_b.bin", pack_f32(CS_B))}
_F3X_INS = {1: ("f3x_a.bin", pack_f32(F3X_A)), 2: ("f3x_b.bin", pack_f32(F3X_B)),
            3: ("f3x_c.bin", pack_f32(F3X_C))}
_FEX_INS = {1: ("fex_a.bin", pack_f32(FEX_A)), 2: ("fex_b.bin", pack_f32(FEX_B)),
            3: ("fex_c.bin", pack_f32(FEX_C))}
_CSX_INS = {1: ("csx_a.bin", pack_f32(CSX_A)), 2: ("csx_b.bin", pack_f32(CSX_B))}

_F3LIB = falu3_library(F3_A, F3_B, F3_C)
_FELIB = falu3_library(FE_A, FE_B, FE_C, sat=True)
_FSLIB = fspecial_library(FS_A, FS_B)
_CSLIB = copysign_library(CS_A, CS_B)

CARRIERS = {
    # ---- falu3 -----------------------------------------------------------
    "f3_fma":   _c("k_f3_fma", "falu3", _F3_INS, _F3LIB["a*b+c"], _F3LIB, None,
                   "fma(a,b,c) -> 8-byte falu3, identity result routing"),
    "f3_chain": _c("k_f3_chain", "falu3", _F3_INS,
                   [f32(r * 0.5 + y) for r, y in zip(_F3LIB["a*b+c"], F3_B)],
                   _F3LIB, None,
                   "fma feeding a following fma that re-reads b (release-flag visible)"),
    "f3_two":   _c("k_f3_two", "falu3", _F3_INS,
                   [f32(p * 0.5 + q * 0.25) for p, q in
                    zip(_F3LIB["a*b+c"],
                        [f32(z * x + y) for x, y, z in zip(F3_A, F3_B, F3_C)])],
                   _F3LIB, None, "two independent fmas, two allocations"),
    # ---- falu3_ext -------------------------------------------------------
    "f3e_sat":   _c("k_f3e_sat", "falu3_ext", _FE_INS, _FELIB["a*b+c"], _FELIB,
                    None, "saturate(fma(a,b,c)) -> 10-byte falu3_ext"),
    "f3e_chain": _c("k_f3e_chain", "falu3_ext", _FE_INS,
                    [f32(r * 0.5 + 0.25) for r in _FELIB["a*b+c"]], _FELIB, None,
                    "saturating fma feeding a following fma"),
    "f3e_two":   _c("k_f3e_two", "falu3_ext", _FE_INS,
                    [f32(p + q * 0.125) for p, q in
                     zip(_FELIB["a*b+c"],
                         _clamp01([f32(z * x + y) for x, y, z
                                   in zip(FE_A, FE_B, FE_C)]))],
                    _FELIB, None, "two saturating fmas, two allocations"),
    # ---- falu3_srcmod12 --------------------------------------------------
    "f12_abs":  _c("k_f12_abs", "falu3_srcmod12", _F3_INS,
                   [f32(abs(x) * y + z) for x, y, z in zip(F3_A, F3_B, F3_C)],
                   falu3_library([f32(abs(x)) for x in F3_A], F3_B, F3_C), None,
                   "fma(|a|,b,c) -> 12-byte source-modifier form"),
    "f12_abs2": _c("k_f12_abs2", "falu3_srcmod12", _F3_INS,
                   [f32(abs(x) * abs(y) + z) for x, y, z in zip(F3_A, F3_B, F3_C)],
                   falu3_library([f32(abs(x)) for x in F3_A],
                                 [f32(abs(y)) for y in F3_B], F3_C), None,
                   "fma(|a|,|b|,c), two source modifiers"),
    # ---- fspecial_est ----------------------------------------------------
    "fsp_rsqrt": _c("k_fsp_rsqrt", "fspecial_est", _FS_INS, _FSLIB["rsqrt(a)"],
                    _FSLIB, list(range(16, 24)),
                    "precise rsqrt, second live float of a distant magnitude"),
    "fsp_rcp":   _c("k_fsp_rcp", "fspecial_est", _FS_INS, _FSLIB["rcp(a)"],
                    _FSLIB, list(range(16, 24)), "precise 1/x"),
    "fsp_sqrt":  _c("k_fsp_sqrt", "fspecial_est", _FS_INS, _FSLIB["sqrt(a)"],
                    _FSLIB, list(range(16, 24)), "precise sqrt"),
    "fsp_two":   _c("k_fsp_two", "fspecial_est", _FS_INS, _FSLIB["rsqrt(a)"],
                    _FSLIB, list(range(16, 24)),
                    "two estimates of two different live values"),
    # ---- copysign --------------------------------------------------------
    "cs_load":  _c("k_cs_load", "copysign", _CS_INS, _CSLIB["copysign(a,b)"],
                   _CSLIB, None, "copysign(a,b), load-sourced operands"),
    "cs_swap":  _c("k_cs_swap", "copysign", _CS_INS, _CSLIB["copysign(b,a)"],
                   _CSLIB, None, "copysign(b,a) -- operand ROLES exchanged"),
    "cs_alu":   _c("k_cs_alu", "copysign", _CS_INS,
                   [_copysign(f32(x * 2.0), f32(y + 0.0))
                    for x, y in zip(CS_A, CS_B)],
                   copysign_library([f32(x * 2.0) for x in CS_A],
                                    [f32(y + 0.0) for y in CS_B]), None,
                   "copysign of ALU-sourced operands"),
    # ---- AMENDMENT A: adversarial-input twins of the identity carriers ----
    "f3_fma_x":  _c("k_f3_fma", "falu3", _F3X_INS,
                    falu3_library(F3X_A, F3X_B, F3X_C)["a*b+c"],
                    falu3_library(F3X_A, F3X_B, F3X_C), None,
                    "fma with signed zero / inf / NaN / denormal / 2^24 inputs"),
    "f3e_sat_x": _c("k_f3e_sat", "falu3_ext", _FEX_INS,
                    falu3_library(FEX_A, FEX_B, FEX_C, sat=True)["a*b+c"],
                    falu3_library(FEX_A, FEX_B, FEX_C, sat=True), None,
                    "saturating fma with signed zero / denormal inputs"),
    "f12_abs_x": _c("k_f12_abs", "falu3_srcmod12", _F3X_INS,
                    [f32(abs(x) * y + z) for x, y, z in zip(F3X_A, F3X_B, F3X_C)],
                    falu3_library([f32(abs(x)) for x in F3X_A], F3X_B, F3X_C),
                    None, "abs-fma with adversarial inputs"),
    "cs_load_x": _c("k_cs_load", "copysign", _CSX_INS,
                    copysign_library(CSX_A, CSX_B)["copysign(a,b)"],
                    copysign_library(CSX_A, CSX_B), None,
                    "copysign with +-0, +-inf, NaN, denormal magnitudes"),
    "cs_swap_x": _c("k_cs_swap", "copysign", _CSX_INS,
                    copysign_library(CSX_A, CSX_B)["copysign(b,a)"],
                    copysign_library(CSX_A, CSX_B), None,
                    "copysign roles exchanged, adversarial inputs"),
    "cs_chain": _c("k_cs_chain", "copysign", _CS_INS,
                   [f32(r * 4.0 + 1.0) for r in _CSLIB["copysign(a,b)"]],
                   _CSLIB, None, "copysign result consumed by a following fma"),
}

# `f3_chain`, `f3_two`, `f3e_chain` and `cs_chain` post-process the tested
# instruction's result, so their `oracle` vector is the CARRIER's correct output
# and a library name cannot be read off the read-back directly.
for _n in ("f3_chain", "f3_two", "f3e_chain", "f3e_two", "cs_chain"):
    CARRIERS[_n]["identity_post"] = False


# --------------------------------------------------------------- measurement
def out_inputs(name):
    c = CARRIERS[name]
    ins = {0: ("poison_%s.bin" % name, poison_bytes(c["nwords"]))}
    ins.update(c["inputs"])
    return ins


def summarize(name, blob):
    """DETERMINISTIC observation payload only.

    `gputime_ns` and retry counts are recorded at the TOP LEVEL of the raw
    record, never inside `observed` -- see PRE_REGISTRATION section 7. An
    indexer that hashes the whole `observed` dict to compare two runs will
    otherwise measure the nanosecond timer, and that alone drove one field's
    apparent cross-run agreement from 100 % to 39 %.
    """
    c = CARRIERS[name]
    words = u32s(blob)
    vals = f32s(blob)
    obs = {
        "vals_u32": [words[i] for i in c["val_words"]],
        "sent_u32": words[c["sent_word"]] if c["sent_word"] < len(words) else None,
        "tail_u32": [words[i] for i in c["tail_words"] if i < len(words)],
    }
    if c["aux_words"]:
        obs["aux_u32"] = [words[i] for i in c["aux_words"] if i < len(words)]
    return obs, words, vals


def sentinel_ok(name, words):
    c = CARRIERS[name]
    i = c["sent_word"]
    if i >= len(words):
        return False
    return abs(struct.unpack("<f", struct.pack("<I", words[i]))[0]
               - c["sent_val"]) < 1e-6


def tail_ok(name, words):
    c = CARRIERS[name]
    return all(words[i] == POISON(i) for i in c["tail_words"] if i < len(words))


def unwritten(name, words):
    c = CARRIERS[name]
    return [i for i in c["val_words"] if i < len(words) and words[i] == POISON(i)]


INF = float("inf")


def _close(g, e):
    """NaN- and infinity-safe comparison. Phase 3 of the corrections requires
    signed zero, infinities, NaNs, denormals and rounding boundaries in the
    discriminating inputs, and a naive `abs(g-e)` is NaN for two equal
    infinities -- which would score a correct result as a mismatch."""
    if e != e:                                   # NaN expected
        return g != g
    if g != g:
        return False
    if e in (INF, -INF) or g in (INF, -INF):
        return g == e
    if e == 0.0 and g == 0.0:                    # +0.0 vs -0.0 IS a difference
        return _bits(g) == _bits(e)
    return abs(g - e) <= 1e-4 * max(1.0, abs(e))


def _bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def canon(vec):
    """Bit-pattern canonical form of an 8-lane vector, for distinctness tests.
    Value equality cannot be used: NaN != NaN, and +0.0 == -0.0 while the two
    are different results for a sign-combine op."""
    return tuple(_bits(x) for x in vec)


def vec_match(name, vals, expect):
    c = CARRIERS[name]
    got = [vals[i] for i in c["val_words"]]
    return all(_close(g, e) for g, e in zip(got, expect))


def classify(name, vals):
    """Which NAMED host-computed library member did the hardware produce?

    This is the substantive discrimination: a value that yields `copysign(b,a)`
    or `rsqrt(b)` has told us what the field selected, where "moved" alone only
    says the bits are not ignored. Returns None when nothing matches -- itself a
    result, and the refuter for a published operation map.
    """
    c = CARRIERS[name]
    if not c["identity_post"]:
        return None
    got = [vals[i] for i in c["val_words"]]
    for k, v in c["library"].items():
        if all(_close(g, e) for g, e in zip(got, v)):
            return k
    return None

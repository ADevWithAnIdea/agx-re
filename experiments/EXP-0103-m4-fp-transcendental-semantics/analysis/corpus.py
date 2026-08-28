#!/usr/bin/env python3
"""EXP-0103 frozen input corpora. Deterministic (no wall-clock/system
randomness): every randomized block is an explicit LCG with a fixed seed,
recurrence state = (state*1664525 + 1013904223) mod 2**32 (same recurrence
family as EXP-0074, distinct seed for this experiment)."""
import exact_ref as E

SEED = 0x0103F00D
MUL = 1664525
INC = 1013904223
MOD = 1 << 32


def lcg(seed, n):
    s = seed
    out = []
    for _ in range(n):
        s = (s * MUL + INC) % MOD
        out.append(s)
    return out


def lcg16(seed, n):
    return [v & 0xFFFF for v in lcg(seed, n)]


# ---------------------------------------------------------------- specials --

def special_f32():
    vals = [
        0x00000000, 0x80000000,          # +-0
        0x7F800000, 0xFF800000,          # +-inf
        0x7FC00000, 0xFFC00000,          # canonical qNaN +/-
        0x7FC12345, 0xFFC54321,          # payload qNaN +/-
        0x7FA00001, 0xFFA00001,          # signaling-pattern NaN (top mant bit clear) +/-
        0x7F800001, 0xFF800001,          # signaling-pattern NaN (min payload) +/-
        0x00000001, 0x80000001,          # +-min subnormal
        0x00000002, 0x80000002,
        0x007FFFFE, 0x807FFFFE,
        0x007FFFFF, 0x807FFFFF,          # +-max subnormal
        0x00800000, 0x80800000,          # +-min normal
        0x00800001, 0x80800001,
        0x7F7FFFFF, 0xFF7FFFFF,          # +-max normal (FLT_MAX)
        0x7F7FFFFE, 0xFF7FFFFE,
        0x3F800000, 0xBF800000,          # +-1.0
        0x40000000, 0xC0000000,          # +-2.0
        0x3F000000, 0xBF000000,          # +-0.5
        0x3F800001, 0x3F7FFFFF,          # 1+ulp, 1-ulp/2
        0x40490FDB, 0xC0490FDB,          # +-pi
        0x3FC90FDB, 0xBFC90FDB,          # +-pi/2
        0x40C90FDB,                      # 2*pi (approx, single rounding of 6.283185...)
        0x41200000,                      # 10.0
        0x42C80000,                      # 100.0
        0x453B8000,                      # 3000.0
    ]
    # exponent sweep: 2^e for e spanning the full normal+subnormal range, and
    # a small mantissa perturbation, to hit DAZ/FTZ / overflow / underflow
    # boundaries for every unary SFU op systematically.
    import struct
    def f32_of(x):
        return struct.unpack("<I", struct.pack("<f", x))[0]
    for e in range(-148, 128, 1):
        try:
            vals.append(f32_of(2.0 ** e))
            vals.append(f32_of(-(2.0 ** e)))
            vals.append(f32_of(1.5 * (2.0 ** e)))
        except OverflowError:
            pass
    # dedupe, keep order
    seen = set()
    out = []
    for v in vals:
        v &= 0xFFFFFFFF
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def special_f16():
    vals = [
        0x0000, 0x8000,                  # +-0
        0x7C00, 0xFC00,                  # +-inf
        0x7E00, 0xFE00,                  # canonical qNaN +/-
        0x7E23, 0xFE45,                  # payload qNaN +/-
        0x7D01, 0xFD01,                  # signaling-pattern NaN +/-
        0x0001, 0x8001,                  # +-min subnormal
        0x0002, 0x8002,
        0x03FE, 0x83FE,
        0x03FF, 0x83FF,                  # +-max subnormal
        0x0400, 0x8400,                  # +-min normal
        0x0401, 0x8401,
        0x7BFF, 0xFBFF,                  # +-max normal
        0x7BFE, 0xFBFE,
        0x3C00, 0xBC00,                  # +-1.0
        0x4000, 0xC000,                  # +-2.0
        0x3800, 0xB800,                  # +-0.5
        0x3C01, 0x3BFF,                  # 1+ulp, 1-ulp/2
        0x4248, 0xC248,                  # ~+-pi (rounded)
        0x3E48, 0xBE48,                  # ~+-pi/2
    ]
    seen = set()
    out = []
    for v in vals:
        v &= 0xFFFF
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def exhaustive_f16():
    return list(range(0, 0x10000))


def stratified_f16(seed, n_per_exp=128):
    """Every one of the 32 exponent fields, each with n_per_exp mantissa
    samples (LCG-selected), both signs. Covers every binade at least once
    even though it is not the full 65536-point enumeration."""
    out = []
    s = seed
    for exp_field in range(32):
        for _ in range(n_per_exp):
            s = (s * MUL + INC) % MOD
            mant = (s >> 16) & 0x3FF
            sign = (s >> 26) & 1
            bits = (sign << 15) | (exp_field << 10) | mant
            out.append(bits)
    return out


def random_pairs_f32(seed, n):
    stream = lcg(seed, 2 * n)
    return [(stream[2 * i], stream[2 * i + 1]) for i in range(n)]


def random_triples_f32(seed, n):
    stream = lcg(seed, 3 * n)
    return [(stream[3 * i], stream[3 * i + 1], stream[3 * i + 2]) for i in range(n)]


def random_pairs_f16(seed, n):
    stream = lcg16(seed, 2 * n)
    return [(stream[2 * i], stream[2 * i + 1]) for i in range(n)]


def random_triples_f16(seed, n):
    stream = lcg16(seed, 3 * n)
    return [(stream[3 * i], stream[3 * i + 1], stream[3 * i + 2]) for i in range(n)]


SPECIAL_PAIRS_F32 = [
    (0x00000000, 0x80000000), (0x80000000, 0x00000000),  # +-0 combos
    (0x80000000, 0x80000000), (0x00000000, 0x00000000),
    (0x7F800000, 0xFF800000), (0xFF800000, 0x7F800000),
    (0x7F800000, 0x7F800000), (0xFF800000, 0xFF800000),
    (0x7FC00000, 0x3F800000), (0x3F800000, 0x7FC00000),
    (0x7FC12345, 0x40000000), (0xFFC54321, 0x40000000),
    (0x3F800000, 0x3F800000), (0xBF800000, 0x3F800000),
    (0x00000001, 0x00000001), (0x007FFFFF, 0x00000001),
    (0x3F800000, 0x00000001), (0x00000001, 0x3F800000),
    (0x00800000, 0x3F800000), (0x7F7FFFFF, 0x40000000),
]

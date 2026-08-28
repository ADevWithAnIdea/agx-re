#!/usr/bin/env python3
"""EXP-0146 frozen input vectors + host-computed oracles.

Every oracle here is computed ON THE HOST from the frozen input vectors and the PUBLIC
definition of the operation (C/MSL/IEEE semantics). No GPU output is used to derive an
expected value; the baseline run is used only as a cross-check and is reported when it
disagrees with the host oracle.
"""
import math
import struct

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF

# ---------------------------------------------------------------- 64-bit rows
# Chosen so the low-word carry pattern is mixed [1,1,0,1,0,1,0,1] and the four
# 32-bit words of each row are mostly mutually distinct (needed to identify
# which register a swept operand descriptor selects).
U64_A = [0x0123456789ABCDEF, 0x00000001F0000000, 0x0000000312345678,
         0xFFFFFFFFFFFFFFFF, 0x0000000A7FFFFFFF, 0x0000000C80000000,
         0x0000000000000000, 0xDEADBEEFCAFEBABE]
U64_B = [0x00000000FEDCBA98, 0x0000000210000000, 0x0000000411111111,
         0x0000000000000001, 0x0000000B80000000, 0x0000000D80000000,
         0x0000000000000000, 0x1234567887654321]

# ---------------------------------------------------------------- logic rows
# each pair covers all four (bit_a, bit_b) combinations
LOGIC_A = [0xCCCCCCCC, 0xF0F0F0F0, 0x33333333, 0x0F0F0F0F,
           0xFF00FF00, 0x00FF00FF, 0xAAAA5555, 0x12345678]
LOGIC_B = [0xAAAAAAAA, 0xCCCCCCCC, 0x55555555, 0x33333333,
           0xF0F0F0F0, 0x0F0F0F0F, 0xCCCC3333, 0x9ABCDEF0]

# ---------------------------------------------------------------- 32-bit rows
U32_A = [0x00000001, 0x80000000, 0xFFFFFFFF, 0x12345678,
         0xDEADBEEF, 0x0000FFFF, 0xFFFF0000, 0xA5A5A5A5]
U32_B = [0, 1, 5, 31, 16, 7, 13, 32]

# ---------------------------------------------------------------- float rows
F32_SIN = [-3.0, -1.5, -0.5, 0.0, 0.5, 1.5, 2.5, 3.0]
F32_ROUND = [0.25, 1.75, 3.25, 4.75, 10.6, 100.4, 1000.9, 7.1]


def _assert_covering():
    for a, b in zip(LOGIC_A, LOGIC_B):
        seen = set()
        for i in range(32):
            seen.add(((a >> i) & 1) * 2 + ((b >> i) & 1))
        assert seen == {0, 1, 2, 3}, "pair %08x/%08x does not cover all 4 combos" % (a, b)


_assert_covering()


def pack64(vals):
    return b"".join(struct.pack("<Q", v & M64) for v in vals)


def pack32(vals):
    return b"".join(struct.pack("<I", v & M32) for v in vals)


def packf32(vals):
    return b"".join(struct.pack("<f", float(v)) for v in vals)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


# ------------------------------------------------------------------ oracles
def oracle_u64add():
    return [(a + b) & M64 for a, b in zip(U64_A, U64_B)]


def oracle_u64sub():
    return [(a - b) & M64 for a, b in zip(U64_A, U64_B)]


def oracle_u64and():
    return [a & b for a, b in zip(U64_A, U64_B)]


def oracle_u64eq():
    return [1 if a == b else 0 for a, b in zip(U64_A, U64_B)]


def oracle_u64mul():
    return [(a * b) & M64 for a, b in zip(U64_A, U64_B)]


def oracle_u32x32to64():
    return [(a * b) & M64 for a, b in zip(U32_A, U32_B)]


def _s32(u):
    return struct.unpack("<i", struct.pack("<I", u & M32))[0]


def oracle_s32x32to64():
    return [(_s32(a) * _s32(b)) & M64 for a, b in zip(U32_A, U32_B)]


def oracle_logic_and():
    return [a & b for a, b in zip(LOGIC_A, LOGIC_B)]


def oracle_zext16():
    return [a & 0xFFFF for a in U32_A]


def _rotl32(x, n):
    n &= 31
    return ((x << n) | (x >> (32 - n))) & M32 if n else x & M32


def oracle_rot_imm():
    return [_rotl32(a, 5) for a in U32_A]


def oracle_rot_var():
    return [_rotl32(a, b & 31) for a, b in zip(U32_A, U32_B)]


def oracle_sin():
    return [f32(math.sin(x)) for x in F32_SIN]


def _rint_half_even(x):
    f = math.floor(x)
    d = x - f
    if d > 0.5:
        return f + 1
    if d < 0.5:
        return f
    return f if (f % 2 == 0) else f + 1


def _round_half_away(x):
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def oracle_roundmodes():
    out = []
    for x in F32_ROUND:
        x = f32(x)
        s = (int(_rint_half_even(x)) + int(math.floor(x)) + int(math.ceil(x))
             + int(math.trunc(x)) + int(_round_half_away(x)))
        out.append(s & M32)
    return out


def derive_lut2(a_vals, b_vals, out_vals):
    """Given per-row (a, b, out) 32-bit words, recover the 2-input boolean LUT the
    hardware realized. Returns a 4-entry tuple indexed by (bit_a<<1)|bit_b, or None
    if the observed output is not a consistent bitwise function of (a, b)."""
    lut = [None] * 4
    for a, b, o in zip(a_vals, b_vals, out_vals):
        for i in range(32):
            idx = (((a >> i) & 1) << 1) | ((b >> i) & 1)
            bit = (o >> i) & 1
            if lut[idx] is None:
                lut[idx] = bit
            elif lut[idx] != bit:
                return None
    return tuple(lut)


LUT_NAMES = {
    (0, 0, 0, 0): "0", (0, 0, 0, 1): "and", (0, 0, 1, 0): "a_and_not_b",
    (0, 0, 1, 1): "a", (0, 1, 0, 0): "not_a_and_b", (0, 1, 0, 1): "b",
    (0, 1, 1, 0): "xor", (0, 1, 1, 1): "or", (1, 0, 0, 0): "nor",
    (1, 0, 0, 1): "xnor", (1, 0, 1, 0): "not_b", (1, 0, 1, 1): "a_or_not_b",
    (1, 1, 0, 0): "not_a", (1, 1, 0, 1): "not_a_or_b", (1, 1, 1, 0): "nand",
    (1, 1, 1, 1): "1",
}


# ---------------------------------------------- additional I64 functional oracles
def oracle_u64addimm():
    return [(a + 5) & M64 for a in U64_A]


def oracle_u64lt():
    return [1 if a < b else 0 for a, b in zip(U64_A, U64_B)]


def _s64(u):
    return struct.unpack("<q", struct.pack("<Q", u & M64))[0]


def oracle_s64lt():
    return [1 if _s64(a) < _s64(b) else 0 for a, b in zip(U64_A, U64_B)]


def oracle_u64min():
    return [min(a, b) for a, b in zip(U64_A, U64_B)]


def oracle_u64shl():
    return [(a << (n & 63)) & M64 for a, n in zip(U64_A, U32_B)]


def oracle_u64shr():
    return [(a >> (n & 63)) & M64 for a, n in zip(U64_A, U32_B)]


def oracle_u64clz():
    return [64 if a == 0 else 64 - a.bit_length() for a in U64_A]


def oracle_u64ctz():
    return [64 if a == 0 else (a & -a).bit_length() - 1 for a in U64_A]


def oracle_u64popcnt():
    return [bin(a).count("1") for a in U64_A]


def oracle_u64sel():
    return [a if c else b for a, b, c in zip(U64_A, U64_B, U32_B)]

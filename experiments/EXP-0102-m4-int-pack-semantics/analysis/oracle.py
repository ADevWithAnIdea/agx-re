#!/usr/bin/env python3
"""EXP-0102 host oracle -- pure Python, computed from operation DEFINITIONS
(NIR/GLSL/IEEE754 semantics as documented in public specs), NEVER from GPU
output. Every function here is independently unit-tested by verify.py
--selftest against hand-worked values before any hardware byte is compared
against it.

CLEAN-ROOM: pure host arithmetic. No Apple binary, no captured Apple data.
"""
import struct

MASK32 = 0xFFFFFFFF


def u32(x):
    return x & MASK32


def s32(x):
    x &= MASK32
    return x - (1 << 32) if x & 0x80000000 else x


# ---------------------------------------------------------------------------
# INT-01/02/03: bitfield extract (unsigned / signed)
# ---------------------------------------------------------------------------
def ubfe_model_a(data, off, cnt):
    """MODEL A ('masked-shift'): offset masked mod 32 (as if only the low 5
    bits of a GPR select the shift), width clamped to [0,32], then the usual
    C-style (data >> o) & mask -- overflowing width bits are naturally zero
    because they were already shifted out of a 32-bit value. cnt==0 -> 0."""
    data = u32(data)
    o = off & 31
    w = min(cnt, 32)
    if w == 0:
        return 0
    mask = MASK32 if w >= 32 else (1 << w) - 1
    return (data >> o) & mask


def ubfe_model_b_unmasked_offset(data, off, cnt):
    """MODEL B: offset NOT masked -- a literal shift amount. For off>=32 a
    32-bit shifter has nothing left to shift, so predict 0."""
    data = u32(data)
    w = min(cnt, 32)
    if w == 0:
        return 0
    if off >= 32:
        return 0
    mask = MASK32 if w >= 32 else (1 << w) - 1
    return (data >> off) & mask


def ubfe_model_d_width32_bypasses_offset(data, off, cnt):
    """MODEL D (pilot-phase discovery, M4, cnt fed at RUNTIME so this is a
    genuine hardware/codegen branch, not compile-time folding), refined
    after a first pilot dry run showed cnt>32 (33, 40, ...) does NOT share
    cnt==32's behavior: cnt==0 -> 0; cnt==32 EXACTLY -> data returned
    VERBATIM, offset ignored entirely (even for huge off); otherwise
    (cnt in 1..31 or cnt>32) offset is a literal (unmasked) shift amount --
    off>=32 -> 0, else (data>>off) & (full 32-bit mask if cnt>=32 else
    (1<<cnt)-1). Matches the public Metal Shading Language Specification's
    documented extract_bits(data,offset,bits) contract (bits==32 special-
    cased to ignore offset)."""
    data = u32(data)
    if cnt == 0:
        return 0
    if cnt == 32:
        return data
    if off >= 32:
        return 0
    w = min(cnt, 32)
    mask = MASK32 if w >= 32 else (1 << w) - 1
    return (data >> off) & mask


def sbfe_from_ubfe(u, cnt):
    """Signed extract = unsigned extract (MODEL A) + explicit sign extend
    over the low `min(cnt,32)` bits. cnt==0 -> 0 (no sign bit to extend)."""
    w = min(cnt, 32)
    if w == 0 or w >= 32:
        return s32(u)
    if u & (1 << (w - 1)):
        u -= (1 << w)
    return u


# ---------------------------------------------------------------------------
# INT-11: bitfield insert
# ---------------------------------------------------------------------------
def insert_bits(base, ins, off, cnt):
    """MODEL A: offset masked mod 32 (as if only the low 5 bits select the
    shift), width clamped [0,32]."""
    base = u32(base)
    ins = u32(ins)
    o = off & 31
    w = min(cnt, 32)
    if w == 0:
        return base
    mask = MASK32 if w >= 32 else (1 << w) - 1
    field = (ins & mask) << o
    clear = u32(~(mask << o))
    return u32((base & clear) | field)


def insert_bits_model_d(base, ins, off, cnt):
    """MODEL D (pilot-phase discovery, mirrors ubfe_model_d_width32_bypasses_
    offset exactly): cnt==0 -> base unchanged; cnt==32 EXACTLY -> result is
    `ins` VERBATIM (base and offset both ignored); otherwise offset is a
    literal (unmasked) shift -- off>=32 -> base unchanged (field shifted out
    entirely), else the usual mask/shift/clear/combine."""
    base = u32(base)
    ins = u32(ins)
    if cnt == 0:
        return base
    if cnt == 32:
        return ins
    if off >= 32:
        return base
    w = min(cnt, 32)
    mask = MASK32 if w >= 32 else (1 << w) - 1
    field = (ins & mask) << off
    clear = u32(~(mask << off))
    return u32((base & clear) | field)


# ---------------------------------------------------------------------------
# INT-04/05/06: rotate (funnel, amount mod 32)
# ---------------------------------------------------------------------------
def rotl32(x, n):
    x = u32(x)
    s = n & 31
    if s == 0:
        return x
    return u32((x << s) | (x >> (32 - s)))


# ---------------------------------------------------------------------------
# INT-07/08: IMAD wraps modulo 2^32
# ---------------------------------------------------------------------------
def imad_u32(a, b, c):
    return u32(u32(a) * u32(b) + u32(c))


def imad_s32(a, b, c):
    return s32(s32(a) * s32(b) + s32(c))


# ---------------------------------------------------------------------------
# INT-09/10: find-MSB / CLZ (derived relationship, cross-validated)
# ubfind_msb(x): highest set-bit index, x=0 -> convention-dependent (we test
# what NIR ufind_msb wants: -1 typically, but MSL clz(0)=32 is the anchor we
# HW-validate directly; find-MSB(0) is DERIVED as 31-32=-1 i.e. an implied
# 0xFFFFFFFF/-1 sentinel under the clz=31-findMSB decomposition).
# ---------------------------------------------------------------------------
def clz32(x):
    x = u32(x)
    if x == 0:
        return 32
    n = 0
    bit = 0x80000000
    while not (x & bit):
        n += 1
        bit >>= 1
    return n


def ctz32(x):
    x = u32(x)
    if x == 0:
        return 32
    n = 0
    while not (x & 1):
        x >>= 1
        n += 1
    return n


def find_msb_derived(x):
    """31 - clz(x) for x != 0; NIR ufind_msb convention says -1 for x==0
    (we report the derived value under the clz=31-findMSB decomposition,
    i.e. 31-32=-1, and separately record what clz(0) itself measures)."""
    x = u32(x)
    if x == 0:
        return -1
    return 31 - clz32(x)


def popcount32(x):
    return bin(u32(x)).count("1")


# ---------------------------------------------------------------------------
# INT-12: 16 two-input Boolean logic functions (standard truth-table index,
# input order (a,b), MSB-first truth table over (a,b)=(1,1),(1,0),(0,1),(0,0))
# ---------------------------------------------------------------------------
def logic_lut(idx, a, b):
    a = u32(a)
    b = u32(b)
    if idx == 0:
        return 0
    if idx == 1:
        return u32(a & b)
    if idx == 2:
        return u32(a & u32(~b))
    if idx == 3:
        return a
    if idx == 4:
        return u32(u32(~a) & b)
    if idx == 5:
        return b
    if idx == 6:
        return u32(a ^ b)
    if idx == 7:
        return u32(a | b)
    if idx == 8:
        return u32(~(a | b))
    if idx == 9:
        return u32(~(a ^ b))
    if idx == 10:
        return u32(~b)
    if idx == 11:
        return u32(a | u32(~b))
    if idx == 12:
        return u32(~a)
    if idx == 13:
        return u32(u32(~a) | b)
    if idx == 14:
        return u32(~(a & b))
    if idx == 15:
        return MASK32
    raise ValueError(idx)


LOGIC_EXPR = {
    0: "0u",
    1: "(a & b)",
    2: "(a & ~b)",
    3: "a",
    4: "(~a & b)",
    5: "b",
    6: "(a ^ b)",
    7: "(a | b)",
    8: "~(a | b)",
    9: "~(a ^ b)",
    10: "~b",
    11: "(a | ~b)",
    12: "~a",
    13: "(~a | b)",
    14: "~(a & b)",
    15: "0xFFFFFFFFu",
}


# ---------------------------------------------------------------------------
# PACK-05/06: unorm/snorm 2x16 (GLSL packUnorm2x16/packSnorm2x16 formulas,
# public spec semantics -- round(clamp(x,lo,hi)*scale), ties handled by
# Python round() [banker's/round-half-to-even] as the reference convention;
# hardware tie behavior is exactly the OBSERVED-vs-model question these
# items ask, so raw observed values are what get recorded, not silently
# forced to match this reference.
# ---------------------------------------------------------------------------
def _rte(v):
    """round-half-to-even, matching IEEE754 default rounding direction."""
    import math
    f = math.floor(v)
    diff = v - f
    if diff < 0.5:
        return f
    if diff > 0.5:
        return f + 1
    return f if f % 2 == 0 else f + 1


def clampf(x, lo, hi):
    if x != x:  # NaN
        return x
    return max(lo, min(hi, x))


def _as_f32(v):
    """Round a Python float (float64) to the nearest binary32 and promote
    back losslessly -- puts the oracle on the SAME precision the GPU's
    float32 ALU actually computes in, so a subsequent Python `==` against a
    GPU-readback float (itself an exact float32->float64 promotion) is a
    bit-exact comparison, not a float64-vs-float32 apples-to-oranges one."""
    return struct.unpack("<f", struct.pack("<f", v))[0]


def f32_exact_fraction(x):
    """EXACT Fraction value of the binary32 number nearest x (None for
    inf/nan). A naive `x * scale` computed in float64 (or even float32,
    twice) is NOT exact -- e.g. a constructed 'exact tie' fraction like
    (32767.5)/65535 rounds to a float32 whose TRUE value, times 65535, is
    off by ~1e-9 from N+0.5 (verified during this experiment's pilot phase,
    PROGRESS.md), which silently resolves what looks like a rounding-rule
    question into an ordinary non-tie correctly-rounded case. This function
    lets pack_unorm16/pack_snorm16 test the REAL rounding rule against the
    GPU's actual float32 input value, not an approximation of it."""
    (bits,) = struct.unpack("<I", struct.pack("<f", x))
    sign = -1 if (bits >> 31) else 1
    exp = (bits >> 23) & 0xFF
    mant = bits & 0x7FFFFF
    if exp == 0xFF:
        return None  # inf or nan
    if exp == 0:
        return sign * Fraction(mant, 1 << 23) * Fraction(2) ** (-126)
    return sign * (Fraction(1) + Fraction(mant, 1 << 23)) * Fraction(2) ** (exp - 127)


def _pack_norm_exact(x, scale, lo, hi):
    """Shared exact-rational packer for pack_unorm16/snorm16 (and the 4x8
    siblings via a different scale/range): snap x to float32, clamp
    (NaN -> 0.0 first, matching the observed hardware/MSL behavior for this
    boundary), take the EXACT Fraction of the clamped float32 value, scale
    by the exact integer `scale`, and round-half-to-even on the exact
    rational product -- never on a float64 approximation of it."""
    if x != x:
        x = 0.0
    xf32 = _as_f32(x)
    c = clampf(xf32, lo, hi)
    c32 = _as_f32(c)
    frac = f32_exact_fraction(c32)
    if frac is None:
        frac = Fraction(hi) if c32 > 0 else Fraction(lo)
    scaled = frac * scale
    sign = 1 if scaled < 0 else 0
    mag = _round_half_even_fraction(abs(scaled)) if scaled >= 0 else -_round_half_even_fraction(-scaled)
    return mag


def pack_unorm16(x):
    return _pack_norm_exact(x, 65535, 0.0, 1.0) & 0xFFFF


def unpack_unorm16(u):
    return _as_f32((u & 0xFFFF) / 65535.0)


def pack_snorm16(x):
    v = _pack_norm_exact(x, 32767, -1.0, 1.0)
    v = max(-32768, min(32767, v))
    return v & 0xFFFF


def unpack_snorm16(u):
    v = u & 0xFFFF
    if v & 0x8000:
        v -= 0x10000
    return _as_f32(max(-1.0, min(1.0, v / 32767.0)))


def pack_unorm2x16(x, y):
    return (pack_unorm16(x) | (pack_unorm16(y) << 16)) & MASK32


def unpack_unorm2x16(u):
    return (unpack_unorm16(u & 0xFFFF), unpack_unorm16((u >> 16) & 0xFFFF))


def pack_snorm2x16(x, y):
    return (pack_snorm16(x) | (pack_snorm16(y) << 16)) & MASK32


def unpack_snorm2x16(u):
    return (unpack_snorm16(u & 0xFFFF), unpack_snorm16((u >> 16) & 0xFFFF))


def pack_unorm8(x):
    if x != x:
        x = 0.0
    c = clampf(x, 0.0, 1.0)
    return int(_rte(c * 255.0)) & 0xFF


def unpack_unorm8(u):
    return _as_f32((u & 0xFF) / 255.0)


def pack_snorm8(x):
    if x != x:
        x = 0.0
    c = clampf(x, -1.0, 1.0)
    v = int(_rte(c * 127.0))
    v = max(-128, min(127, v))
    return v & 0xFF


def unpack_snorm8(u):
    v = u & 0xFF
    if v & 0x80:
        v -= 0x100
    return _as_f32(max(-1.0, min(1.0, v / 127.0)))


def pack_unorm4x8(v4):
    r = 0
    for i, c in enumerate(v4):
        r |= pack_unorm8(c) << (8 * i)
    return r & MASK32


def unpack_unorm4x8(u):
    return tuple(unpack_unorm8((u >> (8 * i)) & 0xFF) for i in range(4))


def pack_snorm4x8(v4):
    r = 0
    for i, c in enumerate(v4):
        r |= pack_snorm8(c) << (8 * i)
    return r & MASK32


def unpack_snorm4x8(u):
    return tuple(unpack_snorm8((u >> (8 * i)) & 0xFF) for i in range(4))


# ---------------------------------------------------------------------------
# PACK-01/02: pack_half_2x16 equivalent (float->fp16 RNE widen/narrow via
# Python's own IEEE-binary16 struct codec, exercised only through pure
# arithmetic -- never touches a GPU).
# ---------------------------------------------------------------------------
def f32_to_f16_bits(x):
    """Exact (Fraction-based) float64-input -> binary16 RNE conversion; does
    NOT delegate to struct's 'e' packer (which raises OverflowError instead
    of saturating to infinity for |x| >= 65520, e.g. our own overflow probe
    values), so this handles the full domain including overflow, inf, nan,
    and signed zero uniformly. Cross-checked against struct's 'e' packer for
    every in-range value in verify.py --selftest."""
    if x != x:  # NaN
        return F16_QNAN
    if x == float("inf"):
        return 0x7C00
    if x == float("-inf"):
        return 0xFC00
    sign = 1 if (struct.pack("<d", x)[7] & 0x80) else 0  # exact sign incl. -0.0
    mag = Fraction(abs(x))
    if mag == 0:
        return 0x8000 if sign else 0x0000
    return f16_encode_exact(sign, mag)


def f16_bits_to_f32(bits):
    return struct.unpack("<e", struct.pack("<H", bits))[0]


def pack_half_2x16(x, y):
    lo = f32_to_f16_bits(x)
    hi = f32_to_f16_bits(y)
    return (lo | (hi << 16)) & MASK32


def unpack_half_2x16(u):
    lo = u & 0xFFFF
    hi = (u >> 16) & 0xFFFF
    return (f16_bits_to_f32(lo), f16_bits_to_f32(hi))


# ---------------------------------------------------------------------------
# PACK-09/10: correctly-rounded binary16 add/mul/fma reference, built from
# exact rational arithmetic (fractions.Fraction) + a from-scratch
# round-to-nearest-even binary16 encoder -- NOT delegated to any GPU result
# and not reusing struct's rounding for the *fused* fma case (struct can
# only do a single float64->float16 narrow, which is NOT a fused multiply-
# add; a genuine fused reference needs one rounding step over the exact
# product+addend, computed here with Fraction).
# ---------------------------------------------------------------------------
from fractions import Fraction  # noqa: E402


def f16_decode(bits):
    """-> ('normal'|'zero'|'inf'|'nan', sign, Fraction value_if_finite)"""
    sign = 1 if (bits & 0x8000) else 0
    exp = (bits >> 10) & 0x1F
    mant = bits & 0x3FF
    if exp == 0:
        if mant == 0:
            return ("zero", sign, Fraction(0))
        val = Fraction(mant, 1024) * Fraction(2) ** (-14)
        return ("normal", sign, val)  # subnormal, treated as a normal value
    if exp == 0x1F:
        return ("nan", sign, None) if mant else ("inf", sign, None)
    val = (Fraction(1) + Fraction(mant, 1024)) * Fraction(2) ** (exp - 15)
    return ("normal", sign, val)


F16_QNAN = 0x7E00  # candidate canonical qNaN, cross-checked not assumed


def _round_half_even_fraction(x):
    """x: Fraction >= 0. Round to nearest integer, ties to even."""
    f = x.numerator // x.denominator
    r = x - f
    if r < Fraction(1, 2):
        return f
    if r > Fraction(1, 2):
        return f + 1
    return f if f % 2 == 0 else f + 1


def f16_encode_exact(sign, value):
    """value: Fraction (unsigned magnitude, exact). Round-to-nearest-even to
    the closest representable binary16 magnitude, then apply sign. Handles
    zero, subnormal, normal, and overflow-to-infinity. Exponent is located
    by an exact search (no float division), so this is exact for any input
    Fraction regardless of magnitude."""
    if value == 0:
        return 0x8000 if sign else 0x0000
    # Locate the true binary exponent e with 1 <= value/2^e < 2, by bit
    # length of numerator/denominator (fast initial guess) then exact
    # Fraction correction -- never uses float division, so it is exact.
    num, den = value.numerator, value.denominator
    e = num.bit_length() - den.bit_length()

    def scale(ee):
        return value / (Fraction(2) ** ee) if ee >= 0 else value * (Fraction(2) ** (-ee))

    v = scale(e)
    while v >= 2:
        e += 1
        v = scale(e)
    while v < 1:
        e -= 1
        v = scale(e)
    # v is now exactly in [1, 2); e is the true (unclamped) binary exponent.
    if e < -14:
        # True value magnitude is below the smallest normal -- subnormal
        # ladder: value = mant/1024 * 2^-14, exponent field 0.
        scaled = value * (Fraction(2) ** 14) * 1024
        mant = _round_half_even_fraction(scaled)
        if mant >= 1024:
            # Rounds up into the smallest normal (mant-1024 == 0 exactly).
            bits = (1 << 10) | 0
        else:
            bits = mant & 0x3FF
        return (0x8000 if sign else 0) | bits
    if e > 15:
        return (0x8000 if sign else 0) | 0x7C00  # overflow -> inf
    mant_scaled = (v - 1) * 1024
    mant = _round_half_even_fraction(mant_scaled)
    if mant == 1024:
        mant = 0
        e += 1
        if e > 15:
            return (0x8000 if sign else 0) | 0x7C00
    exp_field = e + 15
    bits = (exp_field << 10) | (mant & 0x3FF)
    return (0x8000 if sign else 0) | bits


def f16_op(bits_list, op):
    """op in {'add2','mul2','fma3'}. Returns (result_bits, is_nan_input,
    is_inf_involved). NaN propagation modeled as canonical F16_QNAN
    (hypothesis; the raw hardware bits are what actually get recorded)."""
    kinds = [f16_decode(b) for b in bits_list]
    if any(k[0] == "nan" for k in kinds):
        return F16_QNAN
    if op == "add2":
        (k0, s0, v0), (k1, s1, v1) = kinds
        sv0 = v0 if k0 != "inf" else None
        sv1 = v1 if k1 != "inf" else None
        if k0 == "inf" or k1 == "inf":
            i0 = (1 if s0 else -1) if k0 == "inf" else None
            i1 = (1 if s1 else -1) if k1 == "inf" else None
            if k0 == "inf" and k1 == "inf":
                if s0 != s1:
                    return F16_QNAN  # inf - inf
                return (0x8000 if s0 else 0) | 0x7C00
            inf_sign = s0 if k0 == "inf" else s1
            return (0x8000 if inf_sign else 0) | 0x7C00
        sa = -v0 if s0 else v0
        sb = -v1 if s1 else v1
        total = sa + sb
        if total == 0:
            # IEEE754: x+(-x) -> +0 except in round-toward-negative; RNE -> +0,
            # unless both operands are -0 -> -0
            neg = s0 and s1
            return 0x8000 if neg else 0x0000
        sign = 1 if total < 0 else 0
        return f16_encode_exact(sign, abs(total))
    if op == "mul2":
        (k0, s0, v0), (k1, s1, v1) = kinds
        rsign = s0 ^ s1
        if k0 == "zero" or k1 == "zero":
            if k0 == "inf" or k1 == "inf":
                return F16_QNAN  # 0 * inf
            return 0x8000 if rsign else 0x0000
        if k0 == "inf" or k1 == "inf":
            return (0x8000 if rsign else 0) | 0x7C00
        total = v0 * v1
        return f16_encode_exact(rsign, total)
    if op == "fma3":
        (k0, s0, v0), (k1, s1, v1), (k2, s2, v2) = kinds
        # product a*b
        if k0 == "zero" or k1 == "zero":
            if k0 == "inf" or k1 == "inf":
                return F16_QNAN
            psign = s0 ^ s1
            pval = Fraction(0)
            p_is_inf = False
        elif k0 == "inf" or k1 == "inf":
            p_is_inf = True
            psign = s0 ^ s1
            pval = None
        else:
            p_is_inf = False
            psign = s0 ^ s1
            pval = v0 * v1
        # addend c
        c_is_inf = (k2 == "inf")
        if p_is_inf and c_is_inf:
            if psign != s2:
                return F16_QNAN
            return (0x8000 if psign else 0) | 0x7C00
        if p_is_inf:
            return (0x8000 if psign else 0) | 0x7C00
        if c_is_inf:
            return (0x8000 if s2 else 0) | 0x7C00
        sp = -pval if psign else pval
        sc = -v2 if s2 else v2
        total = sp + sc
        if total == 0:
            neg = psign and s2
            return 0x8000 if neg else 0x0000
        sign = 1 if total < 0 else 0
        return f16_encode_exact(sign, abs(total))
    raise ValueError(op)

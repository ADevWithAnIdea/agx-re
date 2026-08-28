#!/usr/bin/env python3
"""EXP-0121 host oracle. Independently written reference implementations (PUBLIC:
IEEE-754-2019 / C99 Annex F semantics used only as portable, non-Apple-sourced
definitions) for every functional item in this experiment. Frozen before capture;
never adjusted post-hoc to match an observed hardware result.
"""
import math
import struct
from fractions import Fraction

# ---------------------------------------------------------------------------
# bit <-> float helpers
# ---------------------------------------------------------------------------

def f32_bits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def bits_f32(b):
    return struct.unpack('<f', struct.pack('<I', b & 0xFFFFFFFF))[0]


def i32_bits(b):
    b &= 0xFFFFFFFF
    return b - (1 << 32) if b & 0x80000000 else b


def u32(b):
    return b & 0xFFFFFFFF


def is_nan_bits(b):
    b &= 0xFFFFFFFF
    return (b & 0x7F800000) == 0x7F800000 and (b & 0x7FFFFF) != 0


def is_inf_bits(b):
    b &= 0xFFFFFFFF
    return (b & 0x7FFFFFFF) == 0x7F800000


def sign_bits(b):
    return (b >> 31) & 1


def is_subnormal_bits(b):
    b &= 0xFFFFFFFF
    return (b & 0x7F800000) == 0 and (b & 0x7FFFFF) != 0


def is_zero_bits(b):
    return (b & 0x7FFFFFFF) == 0


QNAN = 0x7FC00000

# ---------------------------------------------------------------------------
# OPT-01: correctly-rounded FP32 division, exact-Fraction method (lean version
# of EXP-0074's ref_A -- rewritten fresh for this experiment, same published
# IEEE-754 roundTiesToEven algorithm, no binary64 path so no double rounding).
# ---------------------------------------------------------------------------

def _split(bits):
    s = (bits >> 31) & 1
    e = (bits >> 23) & 0xFF
    m = bits & 0x7FFFFF
    return s, e, m


def _val_unsigned(e, m):
    if e == 0:
        return Fraction(m) * Fraction(2) ** -149
    return Fraction((1 << 23) | m) * Fraction(2) ** (e - 150)


def _round_frac_to_f32(sign, q):
    """Round a nonnegative exact Fraction q to binary32 bits, roundTiesToEven."""
    if q == 0:
        return sign << 31
    # find exponent E such that 2^E <= q < 2^(E+1)
    e = 0
    qq = q
    while qq >= 2:
        qq /= 2
        e += 1
    while qq < 1:
        qq *= 2
        e -= 1
    # normal range check
    if e < -126:
        # subnormal: scale to 2^-149 grid
        scaled = q / (Fraction(2) ** -149)
        n = int(scaled)
        rem = scaled - n
        if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and (n & 1)):
            n += 1
        if n >= (1 << 24):
            return (sign << 31) | (1 << 23)  # rounds up into smallest normal
        return (sign << 31) | n
    if e > 127:
        return (sign << 31) | 0x7F800000  # overflow -> inf
    # normal: 24 significant bits (implicit 1 + 23 fraction)
    m_exact = q / (Fraction(2) ** (e - 23))
    n = int(m_exact)
    rem = m_exact - n
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and (n & 1)):
        n += 1
    if n >= (1 << 24):
        n >>= 1
        e += 1
        if e > 127:
            return (sign << 31) | 0x7F800000
    m = n & 0x7FFFFF
    return (sign << 31) | ((e + 127) << 23) | m


def div_correctly_rounded(a_bits, b_bits):
    """Exact IEEE-754 binary32 division, roundTiesToEven, no flushing. Returns bits."""
    sa, ea, ma = _split(a_bits)
    sb, eb, mb = _split(b_bits)
    sign = sa ^ sb
    a_nan, b_nan = is_nan_bits(a_bits), is_nan_bits(b_bits)
    a_inf, b_inf = is_inf_bits(a_bits), is_inf_bits(b_bits)
    a_zero, b_zero = is_zero_bits(a_bits), is_zero_bits(b_bits)
    if a_nan or b_nan:
        return QNAN
    if a_inf and b_inf:
        return QNAN
    if a_zero and b_zero:
        return QNAN
    if a_inf:
        return (sign << 31) | 0x7F800000
    if b_inf:
        return sign << 31
    if b_zero:
        return (sign << 31) | 0x7F800000
    if a_zero:
        return sign << 31
    va = _val_unsigned(ea, ma)
    vb = _val_unsigned(eb, mb)
    q = va / vb
    return _round_frac_to_f32(sign, q)


def div_daz_ftz(a_bits, b_bits):
    """EXP-0074's proven precise-division model: DAZ (flush subnormal operands to
    signed zero before the op) + FTZ (flush a correctly-rounded subnormal RESULT to
    signed zero). Predicts EXP-0074's precise `/` path exactly (4171/4171)."""
    sa = sign_bits(a_bits)
    sb = sign_bits(b_bits)
    a2 = (sa << 31) if is_subnormal_bits(a_bits) else a_bits
    b2 = (sb << 31) if is_subnormal_bits(b_bits) else b_bits
    r = div_correctly_rounded(a2, b2)
    if is_subnormal_bits(r):
        return (sign_bits(r) << 31)
    return r


# ---------------------------------------------------------------------------
# OPT-04: ldexp, C99 semantics, via Python's math.ldexp with special-case
# pre/post handling (Python raises OverflowError instead of returning inf, and
# CPython's ldexp does not guarantee documented NaN/inf passthrough for every
# platform libm, so those are handled explicitly here rather than trusted to
# fall out of the call).
# ---------------------------------------------------------------------------

def ldexp_oracle_bits(x_bits, n):
    if is_nan_bits(x_bits):
        return QNAN
    if is_inf_bits(x_bits):
        return x_bits  # ldexp(±inf, n) = ±inf for any n, per C99
    if is_zero_bits(x_bits):
        return x_bits  # ldexp(±0, n) = ±0 for any n
    sign = sign_bits(x_bits)
    x = bits_f32(x_bits)
    try:
        r = math.ldexp(x, n)
    except OverflowError:
        return (sign << 31) | 0x7F800000  # exponent so extreme even binary64 overflows
    # narrow the double result to f32: ldexp is EXACT in binary except at the
    # overflow/underflow boundary (multiplying the mantissa by a power of two
    # never rounds); the only lossy step is narrowing Python's double (which has
    # strictly more precision than f32) down to f32, which correctly saturates to
    # +-inf on overflow and to +-0 on total underflow via struct.pack's own
    # IEEE-754 conversion -- except struct.pack raises OverflowError instead of
    # saturating for a double that is itself finite but out of f32 range, so that
    # case is handled explicitly here.
    if math.isfinite(r) and abs(r) > 3.4028235e38:
        return (sign << 31) | 0x7F800000
    try:
        rb = f32_bits(float(r))
    except OverflowError:
        rb = (sign << 31) | 0x7F800000
    return rb


# ---------------------------------------------------------------------------
# OPT-05/06: compare+select oracle
# ---------------------------------------------------------------------------

def select_f32(a, b, ca, cb, cond):
    ops = {
        'eq': ca == cb, 'ne': ca != cb, 'lt': ca < cb,
        'le': ca <= cb, 'gt': ca > cb, 'ge': ca >= cb,
    }
    return a if ops[cond] else b


def select_i32(a, b, ca, cb, cond):
    ops = {
        'eq': ca == cb, 'ne': ca != cb, 'lt': ca < cb,
        'le': ca <= cb, 'gt': ca > cb, 'ge': ca >= cb,
    }
    return a if ops[cond] else b


def select_u32(a, b, ca, cb, cond):
    return select_i32(a, b, ca, cb, cond)  # same Python semantics once operands are u32 ints


# ---------------------------------------------------------------------------
# OPT-10/11: concurrency invariant classification (no numeric oracle; the
# invariant is "mismatch==0 and no timeouts" vs not).
# ---------------------------------------------------------------------------

def concurrency_verdict(mismatch, prod_timeout, cons_timeout, completed, expected_completed):
    if prod_timeout or cons_timeout:
        return "incomplete"
    if completed != expected_completed:
        return "incomplete"
    return "exact" if mismatch == 0 else "broken"


if __name__ == "__main__":
    # --selftest hooks live in verify.py; this file has no side effects on import.
    # Quick hand check when run directly.
    assert div_correctly_rounded(f32_bits(10.0), f32_bits(2.0)) == f32_bits(5.0)
    assert div_daz_ftz(f32_bits(1.0), f32_bits(0.0)) == f32_bits(float('inf'))
    assert ldexp_oracle_bits(f32_bits(1.0), 3) == f32_bits(8.0)
    assert select_f32(1.0, 2.0, 3.0, 3.0, 'eq') == 1.0
    print("oracle.py: manual checks OK")

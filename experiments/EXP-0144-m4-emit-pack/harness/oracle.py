#!/usr/bin/env python3
"""EXP-0144 host-computed oracles. NOTHING here consults the GPU.

Every expected value is derived from IEEE-754 / the public Metal Shading
Language format-conversion definitions, computed in Python with exact integer
or `Fraction` arithmetic where a tie could otherwise be decided by float error.

Rounding modes assumed (each is TESTED, not asserted, by the tie cases in
casematrix.py::semantic_vectors):
  * unorm2x16 pack : round-half-to-EVEN of clamp(x,0,1)*65535   [EXP-0102 found
      RTE at the one true tie for this instruction; EXP-0133 found the PBE
      *storage* path for unorm16 ties DOWN instead, so the two paths are
      pre-registered here as COMPETING models and both are scored.]
  * snorm2x16 pack : round-half-away-from-zero of clamp(x,-1,1)*32767, the
      symmetric scale of EXP-0079/EXP-0133 (competing model: RTE).
  * float->half    : IEEE round-to-nearest-even (Python struct '<e').
  * float->bfloat  : pre-registered as RNE with competing model
      truncate-toward-zero (EXP-0079 found reduced-float STORES truncate).
  * int->float     : IEEE round-to-nearest-even.
  * float->int     : truncate toward zero (C semantics).
"""
import struct
from fractions import Fraction

MASK32 = 0xFFFFFFFF

# ---------- bit helpers -----------------------------------------------------
def f32_bits(x):  return struct.unpack("<I", struct.pack("<f", float(x)))[0]
def bits_f32(u):  return struct.unpack("<f", struct.pack("<I", u & MASK32))[0]
def f16_bits(x):  return struct.unpack("<H", struct.pack("<e", float(x)))[0]
def bits_f16(u):  return struct.unpack("<e", struct.pack("<H", u & 0xFFFF))[0]
def i32(u):       return struct.unpack("<i", struct.pack("<I", u & MASK32))[0]


def _round_half_even(fr):
    """Exact round-half-to-even of a Fraction."""
    fl = fr.numerator // fr.denominator
    rem = fr - fl
    if rem > Fraction(1, 2):
        return fl + 1
    if rem < Fraction(1, 2):
        return fl
    return fl if fl % 2 == 0 else fl + 1


def _round_half_away(fr):
    """Exact round-half-away-from-zero of a Fraction."""
    if fr >= 0:
        fl = fr.numerator // fr.denominator
        return fl + 1 if (fr - fl) >= Fraction(1, 2) else fl
    return -_round_half_away(-fr)


def _round_half_down(fr):
    """Exact round-half-toward-negative-infinity at the tie (EXP-0133 unorm16)."""
    fl = fr.numerator // fr.denominator
    rem = fr - fl
    return fl + 1 if rem > Fraction(1, 2) else fl


ROUNDERS = {"rte": _round_half_even, "away": _round_half_away, "down": _round_half_down}


# ---------- pack / unpack ---------------------------------------------------
def pack_unorm2x16(x, y, rounding="rte"):
    r = ROUNDERS[rounding]
    def lane(v):
        v = float(v)
        if v != v:            # NaN -> 0 (EXP-0102 observed; also the MSL rule)
            return 0
        v = min(1.0, max(0.0, v))
        return max(0, min(65535, r(Fraction(v) * 65535)))
    return (lane(x) | (lane(y) << 16)) & MASK32


def pack_snorm2x16(x, y, rounding="away"):
    r = ROUNDERS[rounding]
    def lane(v):
        v = float(v)
        if v != v:
            return 0
        v = min(1.0, max(-1.0, v))
        n = max(-32767, min(32767, r(Fraction(v) * 32767)))
        return n & 0xFFFF
    return (lane(x) | (lane(y) << 16)) & MASK32


def unpack_unorm2x16(u):
    u &= MASK32
    return (struct.unpack("<f", struct.pack("<f", (u & 0xFFFF) / 65535.0))[0],
            struct.unpack("<f", struct.pack("<f", (u >> 16) / 65535.0))[0])


def unpack_snorm2x16(u):
    u &= MASK32
    def lane(h):
        s = h - 0x10000 if h & 0x8000 else h
        return struct.unpack("<f", struct.pack("<f", max(-1.0, s / 32767.0)))[0]
    return (lane(u & 0xFFFF), lane(u >> 16))


# ---------- scalar converts -------------------------------------------------
def i2f(v):   return struct.unpack("<f", struct.pack("<f", float(i32(v))))[0]
def u2f(v):   return struct.unpack("<f", struct.pack("<f", float(v & MASK32)))[0]


def f2i(x):
    x = float(x)
    if x != x:
        return 0
    t = int(x)                      # truncate toward zero
    return max(-2**31, min(2**31 - 1, t)) & MASK32


def f2u(x):
    x = float(x)
    if x != x or x <= 0:
        return 0
    return min(2**32 - 1, int(x)) & MASK32


def f2h(x):   return f16_bits(x)     # IEEE RNE


def f2bf_rne(x):
    """float32 -> bfloat16 bits, round-to-nearest-even on the low 16 bits."""
    u = f32_bits(x)
    if (u & 0x7F800000) == 0x7F800000 and (u & 0x7FFFFF):   # NaN
        return ((u >> 16) | 0x0040) & 0xFFFF
    lsb = (u >> 16) & 1
    return ((u + 0x7FFF + lsb) >> 16) & 0xFFFF


def f2bf_trunc(x):
    return (f32_bits(x) >> 16) & 0xFFFF


def bf2f(b):  return bits_f32((b & 0xFFFF) << 16)


def hmul(a_bits, b_bits):
    return f16_bits(bits_f16(a_bits) * bits_f16(b_bits))


# ---------- self-test -------------------------------------------------------
def selftest():
    fails = []
    def chk(name, got, want):
        if got != want:
            fails.append("%s: got %r want %r" % (name, got, want))
    chk("unorm .25/.75", pack_unorm2x16(0.25, 0.75), 16384 | (49151 << 16))
    chk("unorm 0/1", pack_unorm2x16(0.0, 1.0), 0 | (65535 << 16))
    chk("unorm clamp", pack_unorm2x16(-3.0, 7.0), 0 | (65535 << 16))
    chk("unorm nan", pack_unorm2x16(float("nan"), 0.5), 0 | (32768 << 16))
    # exact tie: x*65535 == 32767.5 -> x = 0.5 exactly? 0.5*65535 = 32767.5 (a
    # true tie, representable in binary32). RTE -> 32768 (even); half-down -> 32767.
    chk("unorm tie rte", pack_unorm2x16(0.5, 0.0) & 0xFFFF, 32768)
    chk("unorm tie down", pack_unorm2x16(0.5, 0.0, "down") & 0xFFFF, 32767)
    chk("snorm .25", pack_snorm2x16(0.25, -0.25) & 0xFFFF, 8192)
    chk("snorm -.25", pack_snorm2x16(0.25, -0.25) >> 16, (-8192) & 0xFFFF)
    chk("snorm 1/-1", pack_snorm2x16(1.0, -1.0), 32767 | ((-32767 & 0xFFFF) << 16))
    x, y = unpack_unorm2x16(16384 | (49151 << 16))
    chk("unpack round", (round(x, 6), round(y, 6)), (round(16384/65535, 6), round(49151/65535, 6)))
    chk("i2f -3", i2f(0xFFFFFFFD), -3.0)
    chk("u2f -1", u2f(0xFFFFFFFF), 4294967296.0)
    chk("f2i 3.9", f2i(3.9), 3)
    chk("f2i -3.9", i32(f2i(-3.9)), -3)
    chk("f2h 3.5", f2h(3.5), 0x4300)
    chk("f2h 65504", f2h(65504.0), 0x7BFF)
    chk("f2bf rne 1.0", f2bf_rne(1.0), 0x3F80)
    chk("f2bf trunc pi", f2bf_trunc(3.14159265), (f32_bits(3.14159265) >> 16) & 0xFFFF)
    chk("f2bf rne pi", f2bf_rne(3.14159265), 0x4049)
    chk("bf2f", bf2f(0x3F80), 1.0)
    return fails


if __name__ == "__main__":
    f = selftest()
    print("oracle selftest: %s" % ("PASS" if not f else "FAIL\n  " + "\n  ".join(f)))

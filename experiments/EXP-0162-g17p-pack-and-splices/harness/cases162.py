#!/usr/bin/env python3
"""EXP-0162 FROZEN compute case matrix -- the three EXP-0144 shards that never
completed, on G17P.

Nothing here consults the GPU. Every expected value is HOST-computed from
IEEE-754 / bfloat16 / the public MSL conversion definitions.

CLEAN-ROOM: OWN-SHADER + PUBLIC.
"""
import struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oracle as O  # noqa: E402

M32 = 0xFFFFFFFF
PAD = 4072


def bf(x):
    return O.f32_bits(x)


def lo16(u):
    return u & 0xFFFF


# ---------------------------------------------------------------- bf16 oracle
def f32_to_bf16_rne(x):
    """float32 -> bfloat16 bits, round-to-nearest-EVEN, exact integer arithmetic.
    Public IEEE-754 / bfloat16 definition; no GPU consulted."""
    u = bf(x)
    e = (u >> 23) & 0xFF
    m = u & 0x7FFFFF
    if e == 0xFF:                       # inf / NaN
        if m:                           # quiet the NaN the way every bf16 impl must
            return (u >> 16) | 0x0040 if ((u >> 16) & 0x007F) == 0 else (u >> 16) & 0xFFFF
        return (u >> 16) & 0xFFFF
    r = u >> 16
    rem = u & 0xFFFF
    if rem > 0x8000 or (rem == 0x8000 and (r & 1)):
        r += 1
    return r & 0xFFFF


def f32_to_bf16_trunc(x):
    """Competing model: truncate toward zero (drop the low 16 bits)."""
    return (bf(x) >> 16) & 0xFFFF


def f32_to_bf16_ties_down(x):
    """Competing model: round to nearest, TIES TOWARD ZERO (= truncate on a tie).
    This is the model EXP-0133 measured for the unorm16 STORE path, where ties
    round DOWN while unorm8 ties round up -- so it is the live alternative to RNE
    here and MUST be separated by an odd-mantissa-lsb tie."""
    u = bf(x)
    e = (u >> 23) & 0xFF
    if e == 0xFF:
        return f32_to_bf16_rne(x)
    r = u >> 16
    rem = u & 0xFFFF
    if rem > 0x8000:
        r += 1
    return r & 0xFFFF


def f32_to_bf16_rna(x):
    """Competing model: round half AWAY from zero."""
    u = bf(x)
    e = (u >> 23) & 0xFF
    m = u & 0x7FFFFF
    if e == 0xFF:
        return f32_to_bf16_rne(x)
    r = u >> 16
    rem = u & 0xFFFF
    if rem >= 0x8000:
        r += 1
    return r & 0xFFFF


BF_MODELS = {"RNE": f32_to_bf16_rne, "TRUNC": f32_to_bf16_trunc,
             "RNA": f32_to_bf16_rna, "TIES_DOWN": f32_to_bf16_ties_down}


def bits_to_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & M32))[0]


def bf16_tie(hi16):
    """float32 whose low 16 mantissa bits are exactly 0x8000 -- an EXACT bf16 tie
    whose bf16 truncation is `hi16`. RNE rounds it to hi16 if hi16 is even and to
    hi16+1 if hi16 is odd; TIES_DOWN/TRUNC always give hi16; RNA always hi16+1."""
    return bits_to_f32((hi16 << 16) | 0x8000)


# ---------------------------------------------------------------- carriers
# Frozen anchors, asserted at run time against the freshly compiled carrier.
TARGETS = {
  "cvt_bf16":        dict(carrier="c_f2bf",    off=156, anchor="0101148105024000",
                          length=8, mode="B"),
  "cvt_f2h_dst":     dict(carrier="c_f2h_dst", off=156, anchor="c10114810402",
                          length=6, mode="B"),
  "packed_half2_hi": dict(carrier="c_ph2",     off=108, anchor="900405000020",
                          length=6, mode="A", synth="980424000020"),
}

FIXED = {
  "c_f2bf":    ("<6f", (1.5, 2.25, 3.125, -4.75, 5.5, 0.375)),
  "c_f2h_dst": ("<6f", (1.5, 2.25, 3.125, -4.75, 5.5, 0.375)),
  "c_ph2":     ("<8e", (1.5, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)),
}

# ---- semantic vectors ------------------------------------------------------
# The bf16 set is EXP-0144's frozen c_f2bf set (first six rows, verbatim, so the
# G17P number is comparable to the M4 measurement it converts) PLUS four rows of
# exact bf16 ties built here specifically so RNE / TRUNC / RNA disagree.
_T = bf16_tie
SEM = {
 "c_f2bf": [
   # --- EXP-0144's frozen rows, verbatim (v0 is the converted lane) ----------
   (1.5, 2.25, 3.125, -4.75, 5.5, 0.375),
   (3.14159265, 2.71828182, 1.41421356, 0, 0, 0),
   (1.00390625, 1.001953125, 1.005859375, 0, 0, 0),
   (float("nan"), float("inf"), float("-inf"), 0, 0, 0),
   (1e-45, 1e38, -1e38, 0, 0, 0),
   (0.1, 0.2, 0.3, 0.7, 0.5, 0.25),
   # --- ONLY v0 is converted, so every discriminating value goes at v0. ------
   # EXACT ties, both mantissa parities, both signs. The odd-lsb rows are the
   # load-bearing ones: they are the ONLY cases where RNE and TIES_DOWN differ.
   (bf16_tie(0x3F80), 1.0, 2.0, 3.0, 4.0, 5.0),      # even lsb  RNE 3F80 RNA 3F81
   (bf16_tie(0x3F81), 1.0, 2.0, 3.0, 4.0, 5.0),      # ODD  lsb  RNE 3F82 TIES_DOWN 3F81
   (bf16_tie(0x4000), 1.0, 2.0, 3.0, 4.0, 5.0),      # even lsb
   (bf16_tie(0x4001), 1.0, 2.0, 3.0, 4.0, 5.0),      # ODD  lsb
   (bf16_tie(0xBF80), 1.0, 2.0, 3.0, 4.0, 5.0),      # even lsb, negative
   (bf16_tie(0xBF81), 1.0, 2.0, 3.0, 4.0, 5.0),      # ODD  lsb, negative
   (bf16_tie(0x3F7F), 1.0, 2.0, 3.0, 4.0, 5.0),      # ODD lsb, carry INTO exponent
   (bf16_tie(0x7F7E), 1.0, 2.0, 3.0, 4.0, 5.0),      # even lsb at the top finite
   (bf16_tie(0x7F7F), 1.0, 2.0, 3.0, 4.0, 5.0),      # ODD lsb -> RNE overflows to +inf
   (bf16_tie(0xFF7F), 1.0, 2.0, 3.0, 4.0, 5.0),      # ODD lsb -> RNE overflows to -inf
   # just below / just above a tie: every model must agree, so a disagreement
   # here means the harness is wrong, not the hardware
   (bits_to_f32(0x3F807FFF), 1.0, 2.0, 3.0, 4.0, 5.0),
   (bits_to_f32(0x3F808001), 1.0, 2.0, 3.0, 4.0, 5.0),
   # bf16 SUBNORMAL and underflow territory (bf16 has the f32 exponent range, so
   # these are f32 subnormals -- the interesting question is whether they survive)
   (bits_to_f32(0x00008000), 1.0, 2.0, 3.0, 4.0, 5.0),   # f32 subnormal, exact tie
   (bits_to_f32(0x00000001), 1.0, 2.0, 3.0, 4.0, 5.0),   # smallest f32 subnormal
   (bits_to_f32(0x007FFFFF), 1.0, 2.0, 3.0, 4.0, 5.0),   # largest f32 subnormal
   # signed zeros, inf, and a NaN with a payload that must survive quieting
   (0.0, 1.0, 2.0, 3.0, 4.0, 5.0),
   (-0.0, 1.0, 2.0, 3.0, 4.0, 5.0),
   (float("inf"), 1.0, 2.0, 3.0, 4.0, 5.0),
   (float("-inf"), 1.0, 2.0, 3.0, 4.0, 5.0),
   (bits_to_f32(0x7F800001), 1.0, 2.0, 3.0, 4.0, 5.0),   # signalling NaN, low payload
   (bits_to_f32(0x7FC00000), 1.0, 2.0, 3.0, 4.0, 5.0),   # quiet NaN
   # ordinary values whose low 16 bits are strictly above / below the tie
   (1.0 / 3.0, 1.0, 2.0, 3.0, 4.0, 5.0),
   (2.0 / 3.0, 1.0, 2.0, 3.0, 4.0, 5.0),
   (123456.789, 1.0, 2.0, 3.0, 4.0, 5.0),
   (-123456.789, 1.0, 2.0, 3.0, 4.0, 5.0),
 ],
 "c_f2h_dst": [
   (1.5, 2.25, 3.125, -4.75, 5.5, 0.375),
   (65504.0, 65520.0, 65536.0, -65504.0, 0, 0),
   (1.0009765625, 1.00048828125, 1.00146484375, 0, 0, 0),
   (float("nan"), float("inf"), float("-inf"), 0, 0, 0),
   (0.1, 0.2, 0.3, 0.7, 0.5, 0.25),
 ],
 "c_ph2": [
   (1.5, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0),
   (0.5, -0.5, 2.0, -2.0, 1.0, 1.0, 1.0, 1.0),
   (65504.0, 1.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0),
   (6.0e-8, 1.0, 1.0, 1.0, 0, 0, 0, 0),
 ],
}

RESULT_SLOTS = {"c_f2bf": [0], "c_f2h_dst": [0], "c_ph2": [0]}

# The half/bfloat carriers store SEVEN 16-bit values, so the last output word has
# only its LOW half written; its high half legitimately keeps the read-back
# buffer's poison. Compare that word masked. (Discovered by the poisoned smoke
# run -- with EXP-0144's zero-initialised buffer the same word read back 0 and
# the mask was invisible. It is a property of the carrier, not of the hardware.)
EXPECT_MASK = {"c_f2bf": {3: 0xFFFF}, "c_f2h_dst": {3: 0xFFFF}, "c_ph2": {}}
NOUT_BYTES = 256


def invec_bytes(carrier, vals):
    fmt = FIXED[carrier][0]
    return struct.pack(fmt, *vals) + b"\x00" * PAD


def expect(carrier, v, bf_model="RNE"):
    """HOST oracle: {word_index: expected u32}. NEVER consults the GPU."""
    if carrier == "c_f2bf":
        f = BF_MODELS[bf_model]
        h = [f(v[0])] + [lo16(bf(v[i])) for i in (1, 2, 3, 4, 5)] + [lo16(bf(v[0]))]
        return {0: h[0] | (h[1] << 16), 1: h[2] | (h[3] << 16),
                2: h[4] | (h[5] << 16), 3: h[6]}
    if carrier == "c_f2h_dst":
        h = [O.f2h(v[0]), O.f2h(v[1]), O.f2h(v[2])] + \
            [lo16(bf(v[i])) for i in (3, 4, 5)] + [lo16(bf(v[0]))]
        return {0: h[0] | (h[1] << 16), 1: h[2] | (h[3] << 16),
                2: h[4] | (h[5] << 16), 3: h[6]}
    if carrier == "c_ph2":
        hb = [O.f16_bits(x) for x in v]
        w = lambda a, b: (a | (b << 16)) & M32
        return {0: w(O.hmul(hb[0], hb[2]), O.hmul(hb[1], hb[3])),
                1: w(hb[4], hb[5]), 2: w(hb[6], hb[7]),
                3: w(hb[0], hb[1]), 4: w(hb[2], hb[3])}
    raise KeyError(carrier)


def ph2_hi(v):
    """The HIGH-lane packed-half2 product v0.y * v1.y."""
    hb = [O.f16_bits(x) for x in v]
    return O.hmul(hb[1], hb[3])


def ph2_lo(v):
    """The LOW-lane packed-half2 product v0.x * v1.x."""
    hb = [O.f16_bits(x) for x in v]
    return O.hmul(hb[0], hb[2])


def expect_ph2_hi_only(v, low_word_if_unwritten):
    """H2 prediction A: HIGH lane carries the product, LOW lane never written
    (the read-back buffer's poison survives)."""
    return (low_word_if_unwritten & 0xFFFF) | (ph2_hi(v) << 16)


def expect_ph2_hi_lowzero(v):
    """H2 prediction B: the instruction writes the WHOLE 32-bit destination --
    HIGH lane the product, LOW lane zero (the destination register's prior half).
    Distinguishing A from B is exactly what the poisoned buffer buys."""
    return ph2_hi(v) << 16


def expect_ph2_both(v):
    """The refuter: BOTH lanes computed, i.e. the instruction is not `hi`-only."""
    return (ph2_lo(v) | (ph2_hi(v) << 16)) & M32


# ---- byte sweeps -----------------------------------------------------------
def byte_cases(key):
    """[(field_byte_label, byte_index_in_instr, value)] for one instrument.

    byte0 is split: the HIGH NIBBLE is the `dst` field and is swept dense 0..15
    with the LOW nibble held at the anchor's value (cannot change the length);
    the LOW nibble gets a bounded 8-value off-match probe recorded separately.
    """
    t = TARGETS[key]
    anchor = bytes.fromhex(t["synth"] if t["mode"] == "A" else t["anchor"])
    out = []
    lo = anchor[0] & 0x0F
    for hi in range(16):
        out.append(("dst", 0, (hi << 4) | lo))
    for lo2 in (0x00, 0x02, 0x03, 0x04, 0x07, 0x0c, 0x0e, 0x0f):
        if lo2 != lo:
            out.append(("byte0_lonib", 0, (anchor[0] & 0xF0) | lo2))
    for b in range(1, len(anchor)):
        for v in range(256):
            out.append(("byte%d" % b, b, v))
    return out

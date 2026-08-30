#!/usr/bin/env python3
"""EXP-0202 carrier definitions: dispatch shape, authored inputs, HOST oracles.

Every oracle here is computed ON THE HOST, in Python, from the MSL WE WROTE --
never from an observed GPU output. No expected value is 0 except lanes named in
`ambiguous_lanes`, which are excluded from the match test and reported
separately: on Apple9 a wrong field value usually produces a SILENT ZERO, and a
zero expectation would score that silent zero as a pass.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7, instrument 1). Every carrier
binds its OUTPUT slot as an INPUT file pre-filled with POISON(i) = 0xDEADBEEF+i,
so a word that reads back as its own poison is UNWRITTEN -- which against a
zero-initialised buffer is indistinguishable from a genuine silent zero.
EXP-0160 saw 25 dispatches report STATUS OK and write nothing at all with no
`InnocentVictim` string anywhere.

INTEGRITY SENTINEL (instrument 2). Every carrier writes 12345 to a word outside
the value region, through a device store independent of every instruction under
test, and BEFORE it. A measurement whose sentinel is missing is `invalid_run`,
is re-run, and is never scored.

Shape (not values) reused and cited from EXP-0184 harness/carriers184.py.
CLEAN-ROOM: OWN-SHADER. Only our own MSL in `kernels/` and its compiled bytes.
"""
import struct

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def pack_u32(v):
    return b"".join(struct.pack("<I", x & M32) for x in v)


def pack_f32(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def rotl(x, k):
    k &= 31
    x &= M32
    return ((x << k) | (x >> (32 - k))) & M32 if k else x


def popcnt(x):
    return bin(x & M32).count("1")


def clz32(x):
    x &= M32
    return 32 if x == 0 else 32 - x.bit_length()


def ctz32(x):
    x &= M32
    return 32 if x == 0 else (x & -x).bit_length() - 1


def revbits32(x):
    return int(("{:032b}".format(x & M32))[::-1], 2)


def s32(x):
    x &= M32
    return x - (1 << 32) if x >> 31 else x


def trunc_i(x):
    return int(x) if x >= 0 else -int(-x)


# --------------------------------------------------------------------- inputs
# Asymmetric, all bits populated, all distinct, none zero and none all-ones, so a
# rotate by a different amount always gives a different answer.
A_ROT = [(0x8000000B + t * 0x01234567) & M32 for t in range(8)]
B_AMT = [1 + t * 3 for t in range(8)]                    # 1,4,7,...,22
A_INT = [15, 16, 65535, 0x40000001, 0x7FFFFFFF, 0xFFFFFFFF, 3, 0x80000000]
B_INT = [1, 3, 7, 15, 31, 63, 127, 255]
F_IN = [3.9, -3.9, 2.5, -2.5, 100.75, 7.0, 0.5, 63.25]
G_IN = [3.9, -3.9, 2.5, -2.5, 100.75, 7.0, 12.25, 2147483904.0]
SH_UNI = 13
SH2_UNI = (5, 19)
S_UNI = 7.75

STD = {"nwords": 16, "sent_word": 8, "sent_val": 12345,
       "val_words": list(range(8)), "tail_words": list(range(9, 16)),
       "grid": 8, "tg": 8}


def _c(metal, func, oracle, inputs, doc, **kw):
    d = dict(STD)
    d.update({"metal": metal, "func": func, "oracle": oracle,
              "inputs": inputs, "doc": doc})
    d.update(kw)
    return d


# ------------------------------------------------------- shift/rotate carriers
SAM = "kernels/k_sam202.metal"
IN_A_ROT = {1: ("a_rot.bin", pack_u32(A_ROT))}
IN_A_ROT_B = {1: ("a_rot.bin", pack_u32(A_ROT)), 2: ("b_amt.bin", pack_u32(B_AMT))}
IN_A_ROT_SH = {1: ("a_rot.bin", pack_u32(A_ROT)), 2: ("sh.bin", pack_u32([SH_UNI]))}
IN_A_ROT_SH2 = {1: ("a_rot.bin", pack_u32(A_ROT)),
                2: ("sh2.bin", pack_u32(list(SH2_UNI)))}
IN_MIX = {1: ("a_rot.bin", pack_u32(A_ROT)), 2: ("b_amt.bin", pack_u32(B_AMT)),
          3: ("sh.bin", pack_u32([SH_UNI]))}

CARRIERS = {
 "sam_gpr": _c(SAM, "k_sam_gpr",
               [rotl(A_ROT[t], B_AMT[t]) for t in range(8)], IN_A_ROT_B,
               "rotate amount from a PER-THREAD device load -> GPR file"),
 "sam_uni": _c(SAM, "k_sam_uni",
               [rotl(A_ROT[t], SH_UNI) for t in range(8)], IN_A_ROT_SH,
               "rotate amount THREAD-INVARIANT -> uniform class"),
 "sam_shl_uni": _c(SAM, "k_sam_shl_uni",
                   [(A_ROT[t] << (SH_UNI & 31)) & M32 for t in range(8)],
                   IN_A_ROT_SH, "thread-invariant SHIFT amount (<<)"),
 "sam_shr_uni": _c(SAM, "k_sam_shr_uni",
                   [A_ROT[t] >> (SH_UNI & 31) for t in range(8)],
                   IN_A_ROT_SH, "thread-invariant SHIFT amount (>>)"),
 "sam_uni2": _c(SAM, "k_sam_uni2",
                [rotl(A_ROT[t], SH2_UNI[0]) ^ rotl(A_ROT[t], SH2_UNI[1])
                 for t in range(8)], IN_A_ROT_SH2,
                "TWO distinct thread-invariant amounts"),
 "sam_mix": _c(SAM, "k_sam_mix",
               [rotl(A_ROT[t], B_AMT[t]) ^ ((rotl(A_ROT[t], SH_UNI) * 3) & M32)
                for t in range(8)], IN_MIX,
               "a GPR amount and a uniform amount in ONE program"),

 "rot_k1":  _c(SAM, "k_rot_k1",  [rotl(A_ROT[t], 1) for t in range(8)],
               IN_A_ROT, "immediate rotate by 1"),
 "rot_k5":  _c(SAM, "k_rot_k5",  [rotl(A_ROT[t], 5) for t in range(8)],
               IN_A_ROT, "immediate rotate by 5"),
 "rot_k7":  _c(SAM, "k_rot_k7",  [rotl(A_ROT[t], 7) for t in range(8)],
               IN_A_ROT, "immediate rotate by 7"),
 "rot_k13": _c(SAM, "k_rot_k13", [rotl(A_ROT[t], 13) for t in range(8)],
               IN_A_ROT, "immediate rotate by 13"),
 "rot_k19": _c(SAM, "k_rot_k19", [rotl(A_ROT[t], 19) for t in range(8)],
               IN_A_ROT, "immediate rotate by 19"),
 "rot_k31": _c(SAM, "k_rot_k31", [rotl(A_ROT[t], 31) for t in range(8)],
               IN_A_ROT, "immediate rotate by 31"),
 "rot_alu": _c(SAM, "k_rot_alu",
               [((rotl(A_ROT[t], 5) * 3) + 7) & M32 for t in range(8)],
               IN_A_ROT, "immediate rotate CONSUMED BY AN ALU op"),
 "rot_two": _c(SAM, "k_rot_two",
               [rotl(A_ROT[t], 5) ^ ((rotl(A_ROT[t], 19) + 1) & M32)
                for t in range(8)], IN_A_ROT,
               "two immediate rotates, two occurrences"),
}

# ------------------------------------------------------------ ibitcount carriers
PC = "kernels/k_pc202.metal"
IN_A_INT = {1: ("a_int.bin", pack_u32(A_INT))}
IN_A_B_INT = {1: ("a_int.bin", pack_u32(A_INT)), 2: ("b_int.bin", pack_u32(B_INT))}


def _tg_oracle():
    out = []
    for t in range(64):
        g, l = t // 32, t % 32
        src = 32 * g + ((l + 1) & 31)
        out.append(((popcnt(A_INT[src & 7]) + 1) * 3 + 5) & M32)
    return out


CARRIERS.update({
 "pc_store": _c(PC, "k_pc_store", [popcnt(A_INT[t]) for t in range(8)],
                IN_A_INT, "popcount -> device store (STANDALONE)"),
 "pc_alu": _c(PC, "k_pc_alu", [(popcnt(A_INT[t]) * 3 + 7) & M32 for t in range(8)],
              IN_A_INT, "popcount CONSUMED BY AN ALU op"),
 "pc_cmp": _c(PC, "k_pc_cmp",
              [((A_INT[t] | 1) if popcnt(A_INT[t]) > 3 else (B_INT[t] | 2)) & M32
               for t in range(8)], IN_A_B_INT,
              "popcount consumed by a COMPARE"),
 "pc_two": _c(PC, "k_pc_two",
              [(popcnt(A_INT[t]) + popcnt(B_INT[t]) * 64) & M32 for t in range(8)],
              IN_A_B_INT, "two popcounts summed (two occurrences)"),
 "pc_clz": _c(PC, "k_pc_clz", [clz32(A_INT[t]) + 1 for t in range(8)],
              IN_A_INT, "find-msb form"),
 "pc_rev": _c(PC, "k_pc_rev", [revbits32(A_INT[t]) ^ 5 for t in range(8)],
              IN_A_INT, "reverse-bits form"),
 "pc_tg": _c(PC, "k_pc_tg", _tg_oracle(), IN_A_INT,
             "popcount -> THREADGROUP memory -> barrier -> store, grid 64 tg 32",
             nwords=80, sent_word=64, val_words=list(range(64)),
             tail_words=list(range(65, 80)), grid=64, tg=32),
})

# --------------------------------------------------------------- cvt carriers
CV = "kernels/k_cvt202.metal"
IN_F = {1: ("f_in.bin", pack_f32(F_IN))}
IN_F_S = {1: ("f_in.bin", pack_f32(F_IN)), 2: ("s_uni.bin", pack_f32([S_UNI]))}
IN_G = {1: ("g_in.bin", pack_f32(G_IN))}


def _v4():
    out = []
    for t in range(8):
        v = f32(F_IN[t])
        iv = [trunc_i(v), trunc_i(f32(v * 2.0)), trunc_i(f32(v * 4.0)),
              trunc_i(f32(v * 8.0))]
        out.append((iv[0] + iv[1] * 3 + iv[2] * 5 + iv[3] * 7) & M32)
    return out


def _rnd():
    out = []
    for t in range(8):
        v = f32(F_IN[t])
        # rint(): round half to even, exactly Python's round() on a float
        out.append((int(round(v)) + 1) & M32)
    return out


def _i64():
    out = []
    for t in range(8):
        v = trunc_i(f32(f32(F_IN[t]) * 1048576.0)) + 0x300000005
        u = v & M64
        out.append(u & M32)
        out.append((u >> 32) & M32)
    return out


CARRIERS.update({
 "cvt_s32": _c(CV, "k_cvt_s32", [trunc_i(f32(F_IN[t])) & M32 for t in range(8)],
               IN_F, "float -> int32, stored (EXP-0184 comparison point)",
               ambiguous_lanes=[6]),
 "cvt_alu": _c(CV, "k_cvt_alu",
               [(trunc_i(f32(F_IN[t])) * 3 + 7) & M32 for t in range(8)],
               IN_F, "convert CONSUMED BY A FOLLOWING ALU op"),
 "cvt_uni": _c(CV, "k_cvt_uni",
               [(trunc_i(f32(S_UNI)) * 1000 + t + 1) & M32 for t in range(8)],
               IN_F_S, "source is a THREAD-INVARIANT constant"),
 "cvt_v4": _c(CV, "k_cvt_v4", _v4(), IN_F, "four converts in one vector expr"),
 "cvt_rnd": _c(CV, "k_cvt_rnd", _rnd(), IN_F, "rint() then convert"),
 "cvt_i64": _c(CV, "k_cvt_i64", _i64(), IN_F,
               "64-bit destination -- a register PAIR",
               nwords=24, sent_word=16, val_words=list(range(16)),
               tail_words=list(range(17, 24))),
 "cvt_sgn": _c(CV, "k_cvt_sgn", [trunc_i(f32(G_IN[t])) & M32 for t in range(8)],
               IN_G, "H8 instruction arm; lane 7 is 2^31+2^8, out of int32 range",
               ambiguous_lanes=[7]),
})

# H8 (`cvt_f2i._instruction`). Lane 7 of G_IN is 2^31 + 2^8, OUTSIDE int32's
# range, so the language does not define the SIGNED result there and we must not
# assert one. What is asserted instead is DISCRIMINATION: the unsigned convert of
# that lane is exactly 0x80000100, while a signed convert can only produce one of
# the saturating / wrapping conventions below. The H8 arm is scored by comparing
# the UNMUTATED baseline's lane-7 word against the SPLICED case's lane-7 word --
# an observed-vs-observed comparison on the same carrier, with the host supplying
# the candidate set, not the answer.
H8_LANE = 7
H8_UNSIGNED_LANE7 = int(2147483904) & M32          # 0x80000100
H8_SIGNED_CANDIDATES = {
    0x7FFFFFFF: "signed convert saturates to INT_MAX",
    0x80000000: "signed convert saturates to INT_MIN",
    0x80000100: "signed convert wraps (bit pattern equals the unsigned answer)",
    0x00000000: "signed convert returns zero on overflow",
}
# The negative lanes discriminate a CLAMPING unsigned convention from a WRAPPING
# one; under a wrapping convention they are indistinguishable from signed, which
# is why lane 7 carries the test.
H8_NEG_LANES = [1, 3]

# --------------------------------------------------------------- iunary carriers
IU = "kernels/k_iu202.metal"


def _f2u(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def _h(x):
    """f32 -> IEEE binary16 -> back, matching MSL's half."""
    return struct.unpack("<e", struct.pack("<e", f32(x)))[0]


def _hbits(x):
    return struct.unpack("<H", struct.pack("<e", f32(x)))[0]


def _un4(x):
    return [((x >> (8 * i)) & 0xFF) / 255.0 for i in range(4)]


def _sn4(x):
    out = []
    for i in range(4):
        b = (x >> (8 * i)) & 0xFF
        sb = b - 256 if b > 127 else b
        out.append(max(sb / 127.0, -1.0))
    return out


def _packun(v):
    r = 0
    for i, x in enumerate(v):
        c = int(round(min(max(f32(x), 0.0), 1.0) * 255.0))
        r |= (c & 0xFF) << (8 * i)
    return r


def _packsn(v):
    r = 0
    for i, x in enumerate(v):
        c = int(round(min(max(f32(x), -1.0), 1.0) * 127.0))
        r |= (c & 0xFF) << (8 * i)
    return r


IUC = {
 "iu_ctz":   ("k_iu_ctz",   IN_A_INT, [ctz32(A_INT[t]) + 1 for t in range(8)]),
 "iu_absi":  ("k_iu_absi",  IN_A_INT, [(abs(s32(A_INT[t])) + 1) & M32 for t in range(8)]),
 "iu_sexth": ("k_iu_sexth", IN_A_INT,
              [(((A_INT[t] & 0xFFFF) - (0x10000 if A_INT[t] & 0x8000 else 0)) ^ 5) & M32
               for t in range(8)]),
 "iu_sextb": ("k_iu_sextb", IN_A_INT,
              [(((A_INT[t] & 0xFF) - (0x100 if A_INT[t] & 0x80 else 0)) ^ 5) & M32
               for t in range(8)]),
 "iu_zextb": ("k_iu_zextb", IN_A_INT, [((A_INT[t] & 0xFF) + 5) & M32 for t in range(8)]),
 "iu_i2f":   ("k_iu_i2f",   IN_A_INT, [_f2u(f32(f32(s32(A_INT[t])) * 0.5)) for t in range(8)]),
 "iu_u2f":   ("k_iu_u2f",   IN_A_INT, [_f2u(f32(f32(A_INT[t]) * 0.25)) for t in range(8)]),
 "iu_f2h":   ("k_iu_f2h",   IN_F,     [(_hbits(f32(F_IN[t] * 3.0)) + 1) & M32 for t in range(8)]),
 "iu_h2f":   ("k_iu_h2f",   IN_F,     [_f2u(f32(_h(F_IN[t]) + 1.5)) for t in range(8)]),
 "iu_h2i":   ("k_iu_h2i",   IN_F,     [(trunc_i(_h(f32(F_IN[t] * 4.0))) ^ 7) & M32 for t in range(8)]),
 "iu_bitcast": ("k_iu_bitcast", IN_F, [(_f2u(f32(F_IN[t])) ^ 0x55) & M32 for t in range(8)]),
 "iu_unorm": ("k_iu_unorm", IN_A_INT,
              [_f2u(f32(_un4(A_INT[t])[0] + _un4(A_INT[t])[1] * 2.0
                        + _un4(A_INT[t])[2] * 4.0 + _un4(A_INT[t])[3] * 8.0))
               for t in range(8)]),
 "iu_packun": ("k_iu_packun", IN_F,
               [(_packun([f32(F_IN[t] * 0.01), 0.25, 0.5, 0.75]) + 1) & M32
                for t in range(8)]),
 "iu_packsn": ("k_iu_packsn", IN_F,
               [(_packsn([f32(F_IN[t] * 0.01), -0.25, 0.5, -0.75]) + 1) & M32
                for t in range(8)]),
 "iu_unpsn": ("k_iu_unpsn", IN_A_INT,
              [_f2u(f32(f32(_sn4(A_INT[t])[0] * 3.0) + _sn4(A_INT[t])[3]))
               for t in range(8)]),
 "iu_addsat": ("k_iu_addsat", IN_A_B_INT,
               [(min(A_INT[t] + B_INT[t], M32) ^ 1) & M32 for t in range(8)]),
 "iu_subsat": ("k_iu_subsat", IN_A_B_INT,
               [(max(A_INT[t] - B_INT[t], 0) ^ 1) & M32 for t in range(8)]),
 "iu_sat":   ("k_iu_sat",   IN_F,
              [_f2u(f32(min(max(f32(F_IN[t] * 0.1), 0.0), 1.0) + 0.125)) for t in range(8)]),
 "iu_rint":  ("k_iu_rint",  IN_F, [_f2u(f32(float(round(f32(F_IN[t]))) + 0.5)) for t in range(8)]),
 "iu_trunc": ("k_iu_trunc", IN_F, [_f2u(f32(float(trunc_i(f32(F_IN[t]))) + 0.5)) for t in range(8)]),
 "iu_h2u":   ("k_iu_h2u",   IN_F,
              [(trunc_i(_h(f32(abs(F_IN[t]) * 8.0))) + 3) & M32 for t in range(8)]),
 "iu_us2f":  ("k_iu_ushort2f", IN_A_INT,
              [_f2u(f32(f32(f32(A_INT[t] & 0xFFFF) * 0.5) + 0.25)) for t in range(8)]),
}
for _k, (_f, _in, _o) in IUC.items():
    CARRIERS[_k] = _c(IU, _f, _o, _in, "iunary candidate: %s" % _f)


# ------------------------------------------------------------------- accessors
def out_inputs(name):
    """Input file specs INCLUDING the POISON pre-fill of the output slot."""
    c = CARRIERS[name]
    ins = {0: ("poison_%s.bin" % name, poison_bytes(c["nwords"]))}
    ins.update(c["inputs"])
    return ins


def summarize(name, blob):
    c = CARRIERS[name]
    words = u32s(blob)
    obs = {
        "vals_u32": [words[i] for i in c["val_words"] if i < len(words)],
        "sent_u32": words[c["sent_word"]] if c["sent_word"] < len(words) else None,
        "tail_u32": [words[i] for i in c["tail_words"] if i < len(words)],
    }
    return obs, words


def sentinel_ok(name, words):
    c = CARRIERS[name]
    i = c["sent_word"]
    return i < len(words) and words[i] == c["sent_val"]


def tail_ok(name, words):
    c = CARRIERS[name]
    return all(words[i] == POISON(i) for i in c["tail_words"] if i < len(words))


def unwritten(name, words):
    c = CARRIERS[name]
    return [i for i in c["val_words"] if i < len(words) and words[i] == POISON(i)]


def match_vector(name, words, expect):
    """Bit-exact u32 comparison of the value region against `expect`, skipping
    the carrier's declared ambiguous lanes."""
    c = CARRIERS[name]
    amb = set(c.get("ambiguous_lanes", []))
    for k, w in enumerate(c["val_words"]):
        if k in amb or w >= len(words):
            continue
        if (words[w] & M32) != (expect[k] & M32):
            return False
    return True


def match_oracle(name, words):
    return match_vector(name, words, CARRIERS[name]["oracle"])

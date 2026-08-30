#!/usr/bin/env python3
"""EXP-0188 carrier definitions: dispatch shape, authored inputs, host oracles.

Every oracle here is computed on the HOST, by simulating the MSL WE WROTE --
never from an observed GPU output. Every oracle value is NON-ZERO (asserted at
import), because on Apple9 a wrong field value usually produces a SILENT ZERO and
a zero oracle would score that silent zero as a pass.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7, instrument 1): every carrier
binds its OUTPUT slot as an INPUT file pre-filled with POISON(i) = 0xDEADBEEF+i.
A word that reads back as its own poison was never written, which against a
zero-initialised buffer is indistinguishable from a genuine silent zero.

INTEGRITY SENTINEL (instrument 2): every carrier stores 0x5A5A1234 through a path
independent of the instruction under test and BEFORE any divergent region --
out[32] for the 32-lane carriers, out[8] for the 8-lane ones. A measurement whose
sentinel is missing is `invalid_run`, is re-run, and is never scored.

CLEAN-ROOM: OWN-SHADER. Only our own MSL in `kernels/` and its compiled bytes.
Structure (not values, not oracles) reused and cited from EXP-0184
harness/carriers184.py.
"""
import struct

M32 = 0xFFFFFFFF
SENTINEL = 0x5A5A1234


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def pack_u32(v):
    return b"".join(struct.pack("<I", int(x) & M32) for x in v)


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


# ---------------------------------------------------------------- authored inputs
# Asymmetric, mixed-parity, and spanning the 32-bit range so that a wrong operand
# selection cannot coincidentally reproduce the right answer.
CF_A = [(0x01000001 + t * 0x00010001 + (t * t)) & M32 for t in range(32)]
SD_A = [(0x30000001 + t * 0x00010003 + (t * 7) % 5) & M32 for t in range(32)]
N1 = [(t % 4) + 1 for t in range(32)]            # outer trip count 1..4
N2 = [(t % 3) + 1 for t in range(32)]            # inner trip count 1..3
N3 = [(t % 2) + 1 for t in range(32)]            # third trip count 1..2
N4 = [((t >> 2) % 4) + 1 for t in range(32)]     # QUAD-UNIFORM trip count 1..4
NBUF = N1 + N2 + N3 + N4                         # 128 words, as the MSL indexes it

IA_A = [0x00000007, 0x0000FFFF, 0x12345678, 0x80000001,
        0x7FFFFFFF, 0x0000ABCD, 0xFFFFFFF0, 0x00010001]
IA_B = [0x00000003, 0x00000002, 0x0000000F, 0x00000005,
        0x00000009, 0x00001111, 0x0000000E, 0x00020002]


# ------------------------------------------------------------------- CF oracles
def _cf_oracle(kind):
    out = []
    for t in range(32):
        acc, n1, n2, n3 = CF_A[t], N1[t], N2[t], N3[t]
        if kind == "nl2" or kind == "wbrk":
            for _ in range(n1):
                for _ in range(n2):
                    acc = (acc * 3 + 7) & M32
        elif kind == "nl3":
            for _ in range(n1):
                for _ in range(n2):
                    for _ in range(n3):
                        acc = (acc * 3 + 7) & M32
        elif kind == "nlif":
            for _ in range(n1):
                for j in range(n2):
                    if (acc >> (j & 7)) & 1:
                        acc = (acc * 3 + 7) & M32
                    else:
                        acc = (acc * 5 + 11) & M32
        elif kind == "ifnl":
            if t & 1:
                for _ in range(n1):
                    for _ in range(n2):
                        acc = (acc * 3 + 7) & M32
            else:
                for _ in range(n2):
                    acc = (acc * 5 + 11) & M32
        elif kind == "lcont":
            for _ in range(n1):
                for j in range(n2):
                    if (t >> (j & 7)) & 1:
                        acc = (acc * 3 + 7) & M32
                acc = (acc + 1) & M32
        else:
            raise ValueError(kind)
        out.append(acc)
    return out


# ------------------------------------------------------------------- SD oracles
def _active_mask_bits(kind, t):
    """The lanes active in the region lane `t` executes in. Every divergence
    condition tests bit 2, 3 or 4 of the lane id, so every active set is a union
    of whole 4-lane quads -- which is why `simd_shuffle_xor(v,1)` and `(v,2)`
    always read an ACTIVE lane and are never undefined."""
    if kind == "flat":
        return list(range(32))
    if kind == "n1":
        return [L for L in range(32) if (L & 4) == (t & 4)]
    if kind == "n2":
        return [L for L in range(32) if (L & 12) == (t & 12)]
    if kind == "n3":
        return [L for L in range(32) if (L & 28) == (t & 28)]
    raise ValueError(kind)


def _tag(kind, t):
    if kind == "flat":
        return 1
    if kind == "n1":
        return 1 if (t & 4) else 2
    if kind == "n2":
        if t & 4:
            return 1 if (t & 8) else 2
        return 3 if (t & 8) else 4
    if kind == "n3":
        if t & 4:
            if t & 8:
                return 1 if (t & 16) else 2
            return 3 if (t & 16) else 4
        if t & 8:
            return 5 if (t & 16) else 6
        return 7 if (t & 16) else 8
    raise ValueError(kind)


def _ballot(lanes, pred_vals):
    m = 0
    for L in lanes:
        if pred_vals[L] & 1:
            m |= (1 << L)
    return m & M32


def _sd_oracle(kind):
    if kind == "loop":
        acc = list(SD_A)
        for i in range(max(N4)):
            act = [L for L in range(32) if N4[L] > i]
            bm = _ballot(act, SD_A)
            nxt = list(acc)
            for L in act:
                nxt[L] = (acc[L] * 3 + bm + acc[L ^ 1]) & M32
            acc = nxt
        return acc
    out = []
    for t in range(32):
        act = _active_mask_bits(kind, t)
        bm = _ballot(act, SD_A)
        x1, x2 = SD_A[t ^ 1], SD_A[t ^ 2]
        out.append((x1 * 3 + x2 * 5 + bm + _tag(kind, t)) & M32)
    return out


# ------------------------------------------------------------------- IA oracles
def _ia_oracle(kind):
    o = []
    for t in range(8):
        a, b = IA_A[t], IA_B[t]
        if kind == "u32" or kind == "s32":
            v = (a + b) & M32
        elif kind == "u16":
            v = ((a & 0xFFFF) + (b & 0xFFFF)) & 0xFFFF
        elif kind == "u64":
            s = ((a << 16) + (b << 32)) & 0xFFFFFFFFFFFFFFFF
            v = ((s >> 24) ^ (s & M32)) & M32
        elif kind == "imm":
            v = (a + 1234) & M32
        elif kind == "uni":
            v = (a + IA_B[0]) & M32
        elif kind == "chain":
            x = (a + b) & M32
            v = (x ^ ((x + a) & M32)) & M32
        else:
            raise ValueError(kind)
        o.append(v)
    return o


# ------------------------------------------------------------------- carriers
def _cf(func, kind):
    return {"metal": "kernels/k_cf188.metal", "func": func, "grid": 32, "tg": 32,
            "nwords": 40, "sent_word": 32, "sent_val": SENTINEL,
            "val_words": list(range(32)), "tail_words": list(range(33, 40)),
            "inputs": {1: ("cf_a.bin", pack_u32(CF_A)),
                       2: ("cf_n.bin", pack_u32(NBUF))},
            "oracle": _cf_oracle(kind),
            "doc": "nested/memory-bounded control flow, shape = %s" % kind}


def _sd(func, kind):
    return {"metal": "kernels/k_sd188.metal", "func": func, "grid": 32, "tg": 32,
            "nwords": 40, "sent_word": 32, "sent_val": SENTINEL,
            "val_words": list(range(32)), "tail_words": list(range(33, 40)),
            "inputs": {1: ("sd_a.bin", pack_u32(SD_A)),
                       2: ("cf_n.bin", pack_u32(NBUF))},
            "oracle": _sd_oracle(kind),
            "doc": "SIMD cross-lane ops at divergence depth = %s" % kind}


def _ia(func, kind):
    return {"metal": "kernels/k_ia188.metal", "func": func, "grid": 8, "tg": 8,
            "nwords": 16, "sent_word": 8, "sent_val": SENTINEL,
            "val_words": list(range(8)), "tail_words": list(range(9, 16)),
            "inputs": {1: ("ia_a.bin", pack_u32(IA_A)),
                       2: ("ia_b.bin", pack_u32(IA_B))},
            "oracle": _ia_oracle(kind),
            "doc": "integer add, operand format = %s" % kind}


CARRIERS = {
    "cf_nl2":   _cf("k_cf_nl2",   "nl2"),
    "cf_nl3":   _cf("k_cf_nl3",   "nl3"),
    "cf_nlif":  _cf("k_cf_nlif",  "nlif"),
    "cf_wbrk":  _cf("k_cf_wbrk",  "wbrk"),
    "cf_ifnl":  _cf("k_cf_ifnl",  "ifnl"),
    "cf_lcont": _cf("k_cf_lcont", "lcont"),

    "sd_flat": _sd("k_sd_flat", "flat"),
    "sd_n1":   _sd("k_sd_n1",   "n1"),
    "sd_n2":   _sd("k_sd_n2",   "n2"),
    "sd_n3":   _sd("k_sd_n3",   "n3"),
    "sd_loop": _sd("k_sd_loop", "loop"),

    "ia_u32":   _ia("k_ia_u32",   "u32"),
    "ia_s32":   _ia("k_ia_s32",   "s32"),
    "ia_u16":   _ia("k_ia_u16",   "u16"),
    "ia_u64":   _ia("k_ia_u64",   "u64"),
    "ia_imm":   _ia("k_ia_imm",   "imm"),
    "ia_uni":   _ia("k_ia_uni",   "uni"),
    "ia_chain": _ia("k_ia_chain", "chain"),
}

# Every expected value must be non-zero: a zero oracle would score Apple9's
# characteristic silent zero as a pass.
for _n, _c in CARRIERS.items():
    assert len(_c["oracle"]) == len(_c["val_words"]), _n
    assert all(v != 0 for v in _c["oracle"]), "zero oracle value in %s" % _n
    assert all(v != POISON(i) for i, v in enumerate(_c["oracle"])), \
        "oracle collides with poison in %s" % _n
del _n, _c


def out_inputs(name):
    """Input file specs, including the POISON pre-fill of the output slot."""
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


def match_oracle(name, blob):
    c = CARRIERS[name]
    words = u32s(blob)
    for k, w in enumerate(c["val_words"]):
        if w >= len(words) or words[w] != (c["oracle"][k] & M32):
            return False
    return True

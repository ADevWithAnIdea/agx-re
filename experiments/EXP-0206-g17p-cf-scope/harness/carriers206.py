#!/usr/bin/env python3
"""EXP-0206 carrier definitions: dispatch shape, authored inputs, HOST oracles.

Every oracle here is computed on the HOST by simulating the MSL WE WROTE -- never
read back from a GPU. Every oracle word is asserted non-zero and distinct from
its own poison word at import time, because on Apple9 a wrong field value usually
produces a SILENT ZERO and a zero oracle would score that silent zero as a pass.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7, instrument 1): every carrier
binds its OUTPUT slot as an INPUT file pre-filled with POISON(i) = 0xDEADBEEF + i.
A word that reads back as its own poison was never written -- which against a
zero-initialised buffer is indistinguishable from a genuine silent zero. For
control flow this is what separates "took the branch" from "never ran".

INTEGRITY SENTINEL (instrument 2): out[32] = 0x5A5A1234, stored FIRST and through
a path independent of every instruction under test. A measurement whose sentinel
is missing is `invalid_run`: it is re-run and never scored.

CLEAN-ROOM: OWN-SHADER. Only our own MSL in `kernels/` and its compiled bytes.
Structure (not values, not oracles) cited from
experiments/EXP-0188-g17p-dimension-carriers/harness/carriers188.py.
"""
import struct

M32 = 0xFFFFFFFF
SENTINEL = 0x5A5A1234
NWORDS = 40
SENT_WORD = 32
VAL_WORDS = list(range(32))
TAIL_WORDS = list(range(33, 40))


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def pack_u32(v):
    return b"".join(struct.pack("<I", int(x) & M32) for x in v)


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


# ------------------------------------------------------------ authored inputs
# Asymmetric, mixed-parity and spanning the 32-bit range, so a wrong operand
# selection cannot coincidentally reproduce the right answer.
CF_A = [(0x01000001 + t * 0x00010001 + (t * t)) & M32 for t in range(32)]
CL_A = [(0x21000003 + t * 0x00030007 + (t * t * 3)) & M32 for t in range(32)]

N1 = [(t % 4) + 1 for t in range(32)]          # outer trip count 1..4
N2 = [(t % 3) + 1 for t in range(32)]          # inner trip count 1..3
N3 = [(t % 2) + 1 for t in range(32)]          # third trip count 1..2
N4 = [((t >> 2) % 4) + 1 for t in range(32)]   # quad-uniform spare
NBUF = N1 + N2 + N3 + N4                       # 128 words, as the MSL indexes it


# ------------------------------------------------------------------ CF oracles
def _cf_oracle(kind):
    out = []
    for t in range(32):
        acc, n1, n2, n3 = CF_A[t], N1[t], N2[t], N3[t]
        if kind in ("nl2", "wbrk"):
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


# ------------------------------------------------------------------ CL oracles
def _pf(i):
    return (i * i * 5 + i * 3 + 13) & M32


def _lf_add(a, b):
    return (a * 3 + b + 7) & M32


def _lf_mul(a, b):
    return (a * 5 + b * 2 + 11) & M32


def _cl_oracle(kind):
    out = []
    for t in range(32):
        a, b = CL_A[t], t + 1
        if kind == "leaf":
            v = _lf_add(a, b)
        elif kind == "chain":
            v = _lf_add(a, b) ^ _lf_mul(b, a)
        elif kind == "deep":
            v = ((_lf_add(a, b) * 2 + 5) + _lf_mul(a, b)) & M32
        elif kind == "spill":
            v = (_lf_add(a, b) + a * (11 + 13 + 17 + 19 + 23 + 29)
                 + b * (31 + 37 + 41 + 43 + 47 + 53)) & M32
        elif kind == "pure":
            v = (_pf(b) * 3 + b * 7 + 9) & M32
        elif kind == "ldret":
            v = ((a * 3 + 7) + b) & M32
        elif kind == "ldacross":
            v = (a * 3 + _pf(b) + 7) & M32
        elif kind == "stacross":
            v = ((a * 3 + 7) ^ ((_pf(b) * 2) & M32)) & M32
        elif kind == "atomic":
            v = (POISON(t) ^ ((a * 3 + 7) & M32)) & M32
        else:
            raise ValueError(kind)
        out.append(v & M32)
    return out


# ---------------------------------------------------------------- carriers
def _cf(func, kind):
    return {"metal": "kernels/k_cf206.metal", "func": func, "grid": 32, "tg": 32,
            "group": "cf", "nwords": NWORDS, "sent_word": SENT_WORD,
            "sent_val": SENTINEL, "val_words": VAL_WORDS,
            "tail_words": TAIL_WORDS,
            "inputs": {1: ("cf_a.bin", pack_u32(CF_A)),
                       2: ("cf_n.bin", pack_u32(NBUF))},
            "oracle": _cf_oracle(kind),
            "doc": "memory-bounded nested control flow, shape=%s" % kind}


def _cl(func, kind, dim):
    return {"metal": "kernels/k_cl206.metal", "func": func, "grid": 32, "tg": 32,
            "group": "cl", "nwords": NWORDS, "sent_word": SENT_WORD,
            "sent_val": SENTINEL, "val_words": VAL_WORDS,
            "tail_words": TAIL_WORDS,
            "inputs": {1: ("cl_a.bin", pack_u32(CL_A))},
            "oracle": _cl_oracle(kind),
            "dim": dim,
            "doc": "out-of-line call, shape=%s, dimension point=%s" % (kind, dim)}


CARRIERS = {
    # H1/H2/H3 -- the REGION-KIND axis
    "cf_nl2":   _cf("k_cf_nl2",   "nl2"),
    "cf_nl3":   _cf("k_cf_nl3",   "nl3"),
    "cf_nlif":  _cf("k_cf_nlif",  "nlif"),
    "cf_wbrk":  _cf("k_cf_wbrk",  "wbrk"),
    "cf_ifnl":  _cf("k_cf_ifnl",  "ifnl"),
    "cf_lcont": _cf("k_cf_lcont", "lcont"),

    # H5 -- the LINK axis (leaf vs non-leaf frames)
    "cl_leaf":     _cl("k_cl_leaf",     "leaf",     "link:leaf"),
    "cl_chain":    _cl("k_cl_chain",    "chain",    "link:nonleaf-1"),
    "cl_deep":     _cl("k_cl_deep",     "deep",     "link:nonleaf-2"),
    "cl_spill":    _cl("k_cl_spill",    "spill",    "link:nonleaf-spill"),

    # H4 -- the ORDERING axis (nothing outstanding -> atomic RMW across the ret)
    "cl_pure":     _cl("k_cl_pure",     "pure",     "order:none"),
    "cl_ldret":    _cl("k_cl_ldret",    "ldret",    "order:load-in-callee"),
    "cl_ldacross": _cl("k_cl_ldacross", "ldacross", "order:load-across-ret"),
    "cl_stacross": _cl("k_cl_stacross", "stacross", "order:store-load-across-ret"),
    "cl_atomic":   _cl("k_cl_atomic",   "atomic",   "order:atomic-rmw-across-ret"),
}

for _n, _c in CARRIERS.items():
    assert len(_c["oracle"]) == len(_c["val_words"]), _n
    assert all(v != 0 for v in _c["oracle"]), "zero oracle value in %s" % _n
    assert all(v != POISON(i) for i, v in enumerate(_c["oracle"])), \
        "oracle collides with poison in %s" % _n
    assert _c["sent_val"] not in _c["oracle"], "oracle collides with sentinel in %s" % _n
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

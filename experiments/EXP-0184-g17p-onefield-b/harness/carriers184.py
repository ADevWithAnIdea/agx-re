#!/usr/bin/env python3
"""EXP-0184 carrier definitions: dispatch shape, authored inputs, host oracles.

Every oracle here is computed on the HOST from the MSL WE WROTE -- never from an
observed GPU output. Every oracle is NON-ZERO except where explicitly excluded,
because on Apple9 a wrong field value usually produces a SILENT ZERO and a zero
oracle would score that silent zero as a pass.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7, instrument 1). Every carrier
binds its OUTPUT slot as an INPUT file pre-filled with POISON(i) = 0xDEADBEEF+i.
A word that reads back as its own poison is UNWRITTEN, which against a
zero-initialised buffer is indistinguishable from a genuine silent zero.
EXP-0160 saw 25 dispatches report STATUS OK and write nothing at all with no
`InnocentVictim` string anywhere; against a zeroed buffer those would have been
25 confident silent zeros.

INTEGRITY SENTINEL (instrument 2). Every carrier writes a fixed sentinel through
a path independent of the instruction under test, and BEFORE it: `out[8]=7.5`
(copysign), `out[8]=12345` (convert), `out[32]=7.5` (control flow, stored before
any divergent region is entered), `out[1]=7.5` (ray query). A measurement whose
sentinel is missing is `invalid_run`, is re-run, and is never scored.

CLEAN-ROOM: OWN-SHADER. Only our own MSL in `kernels/` and its compiled bytes.
Shape (not values) reused and cited from EXP-0157 harness/carriers.py.
"""
import struct

M32 = 0xFFFFFFFF


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def pack_f32(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


def f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def i32s(b):
    return [struct.unpack("<i", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


# --------------------------------------------------------------------- inputs
CS_A = [5.0, -5.0, 3.25, -3.25, 9.5, -9.5, 1.75, -1.75]
CS_B = [-2.0, 2.0, -8.0, 8.0, -0.5, 0.5, -6.0, 6.0]
CVT_A = [3.9, -3.9, 2.5, -2.5, 100.75, 7.0, 0.5, 63.25]
CVT_B = [3.9, 12.25, 2.5, 250.5, 100.75, 7.0, 0.5, 63.25]
CF_A = [3.0 + t for t in range(32)]

# lane 6 of the convert carriers has expected value 0 (0.5 -> 0): the one lane
# where a silent zero is indistinguishable from a pass. It is EXCLUDED from the
# match test and reported separately, never load-bearing.
CVT_AMBIGUOUS_LANES = [6]


def _cs_oracle(kind):
    def cs(a, b):
        return f32(abs(a) * (-1.0 if b < 0 else 1.0))
    if kind == "load":
        return [cs(CS_A[t], CS_B[t]) for t in range(8)]
    if kind == "alu":
        return [cs(f32(CS_A[t] * 2.0), f32(CS_B[t] + 0.0)) for t in range(8)]
    if kind == "mix":
        return [cs(f32(CS_A[t] * 4.0), CS_B[t]) for t in range(8)]
    if kind == "two":
        return [f32(cs(CS_A[t], CS_B[t]) * 16.0 + cs(CS_B[t], CS_A[t]))
                for t in range(8)]
    if kind == "chain":
        return [f32(cs(CS_A[t], CS_B[t]) * 4.0 + 1.0) for t in range(8)]
    raise ValueError(kind)


def _trunc(x):
    return int(x) if x >= 0 else -int(-x)


def _cvt_oracle(kind):
    if kind == "s32":
        return [_trunc(f32(CVT_A[t])) for t in range(8)]
    if kind == "u32":
        return [_trunc(f32(CVT_B[t])) & M32 for t in range(8)]
    if kind == "s16":
        v = [_trunc(f32(CVT_A[t])) for t in range(8)]
        return [((x + 0x8000) & 0xFFFF) - 0x8000 for x in v]
    if kind == "u16":
        return [_trunc(f32(CVT_B[t])) & 0xFFFF for t in range(8)]
    if kind == "h32":
        # half(x) then truncate. struct '<e' is IEEE binary16, round-to-nearest.
        h = [struct.unpack("<e", struct.pack("<e", CVT_A[t]))[0] for t in range(8)]
        return [_trunc(x) for x in h]
    raise ValueError(kind)


def _cf_oracle(kind):
    out = []
    for t in range(32):
        v = f32(CF_A[t])
        if kind == "if1":
            r = f32(v * 2.0 + 1.0) if (t & 1) else f32(v + 100.0)
        elif kind == "if2":
            if t & 1:
                r = f32(v * 2.0 + 1.0) if (t & 2) else f32(v + 100.0)
            else:
                r = f32(v * 4.0 + 2.0) if (t & 2) else f32(v + 200.0)
        elif kind == "if3":
            if t & 1:
                if t & 2:
                    r = f32(v * 2.0 + 1.0) if (t & 4) else f32(v + 100.0)
                else:
                    r = f32(v * 4.0 + 2.0) if (t & 4) else f32(v + 200.0)
            else:
                if t & 2:
                    r = f32(v * 8.0 + 3.0) if (t & 4) else f32(v + 300.0)
                else:
                    r = f32(v * 16.0 + 4.0) if (t & 4) else f32(v + 400.0)
        elif kind == "loop":
            r = v
            for _ in range((t & 3) + 1):
                r = f32(r * 2.0 + 1.0)
        elif kind == "loopif":
            r = v
            for i in range((t & 3) + 1):
                r = f32(r * 2.0) if ((t >> i) & 1) else f32(r + 10.0)
        else:
            raise ValueError(kind)
        out.append(r)
    return out


# ------------------------------------------------------------------- carriers
def _cs(func, kind):
    return {"metal": "kernels/k_cs184.metal", "func": func, "grid": 8, "tg": 8,
            "nwords": 16, "dtype": "f32", "sent_word": 8, "sent_val": f32(7.5),
            "val_words": list(range(8)),
            "tail_words": list(range(9, 16)),
            "inputs": {1: ("cs_a.bin", pack_f32(CS_A)),
                       2: ("cs_b.bin", pack_f32(CS_B))},
            "oracle": _cs_oracle(kind), "accel": None,
            "doc": "copysign, operand provenance = %s" % kind}


def _cvt(func, kind):
    return {"metal": "kernels/k_cvt184.metal", "func": func, "grid": 8, "tg": 8,
            "nwords": 16, "dtype": "i32", "sent_word": 8, "sent_val": 12345,
            "val_words": list(range(8)),
            "tail_words": list(range(9, 16)),
            "inputs": {1: ("cvt_a.bin", pack_f32(CVT_A)),
                       2: ("cvt_b.bin", pack_f32(CVT_B))},
            "oracle": _cvt_oracle(kind), "accel": None,
            "ambiguous_lanes": CVT_AMBIGUOUS_LANES,
            "doc": "float->%s convert" % kind}


def _cf(func, kind):
    return {"metal": "kernels/k_cf184.metal", "func": func, "grid": 32, "tg": 32,
            "nwords": 40, "dtype": "f32", "sent_word": 32, "sent_val": f32(7.5),
            "val_words": list(range(32)),
            "tail_words": list(range(33, 40)),
            "inputs": {1: ("cf_a.bin", pack_f32(CF_A))},
            "oracle": _cf_oracle(kind), "accel": None,
            "doc": "divergent CF, shape = %s" % kind}


def _rq(func, want):
    return {"metal": "kernels/k_rq184.metal", "func": func, "grid": 1, "tg": 1,
            "nwords": 4, "dtype": "f32", "sent_word": 1, "sent_val": f32(7.5),
            "val_words": [0], "tail_words": [2, 3],
            "inputs": {}, "oracle": [f32(want)],
            "accel": 1, "accel_kind": "primitive",
            "doc": "intersection_query getter"}


CARRIERS = {
    "cs_load":  _cs("k_cs_load",  "load"),
    "cs_alu":   _cs("k_cs_alu",   "alu"),
    "cs_mix":   _cs("k_cs_mix",   "mix"),
    "cs_two":   _cs("k_cs_two",   "two"),
    "cs_chain": _cs("k_cs_chain", "chain"),

    "cvt_s32": _cvt("k_cvt_s32", "s32"),
    "cvt_u32": _cvt("k_cvt_u32", "u32"),
    "cvt_s16": _cvt("k_cvt_s16", "s16"),
    "cvt_u16": _cvt("k_cvt_u16", "u16"),
    "cvt_h32": _cvt("k_cvt_h32", "h32"),

    "cf_if1":    _cf("k_cf_if1",    "if1"),
    "cf_if2":    _cf("k_cf_if2",    "if2"),
    "cf_if3":    _cf("k_cf_if3",    "if3"),
    "cf_loop":   _cf("k_cf_loop",   "loop"),
    "cf_loopif": _cf("k_cf_loopif", "loopif"),

    "rq_mdist":  _rq("k_q_mdist",  1.0),
    "rq_mprim":  _rq("k_q_mprim",  2.0),
    "rq_cdist":  _rq("k_q_cdist",  10.0),
    "rq_ccount": _rq("k_q_ccount", 4.0),
}


def out_inputs(name):
    """Input file specs including the POISON pre-fill of the output slot."""
    c = CARRIERS[name]
    ins = {0: ("poison_%s.bin" % name, poison_bytes(c["nwords"]))}
    ins.update(c["inputs"])
    return ins


def decode(name, blob):
    c = CARRIERS[name]
    if c["dtype"] == "f32":
        return f32s(blob)
    return i32s(blob)


def summarize(name, blob):
    """(observed_values, raw_u32_words) for the value region + sentinel + tail."""
    c = CARRIERS[name]
    words = u32s(blob)
    vals = decode(name, blob)
    obs = {
        "vals": [vals[i] for i in c["val_words"]],
        "vals_u32": [words[i] for i in c["val_words"]],
        "sent_u32": words[c["sent_word"]] if c["sent_word"] < len(words) else None,
        "tail_u32": [words[i] for i in c["tail_words"] if i < len(words)],
    }
    return obs, words


def sentinel_ok(name, words):
    c = CARRIERS[name]
    i = c["sent_word"]
    if i >= len(words):
        return False
    if c["dtype"] == "f32":
        return abs(struct.unpack("<f", struct.pack("<I", words[i]))[0]
                   - c["sent_val"]) < 1e-6
    return words[i] == c["sent_val"]


def tail_ok(name, words):
    """The tail must still be POISON: nothing this program emits stores there."""
    c = CARRIERS[name]
    return all(words[i] == POISON(i) for i in c["tail_words"] if i < len(words))


def unwritten(name, words):
    """Value words still holding their own poison -> the program never wrote them."""
    c = CARRIERS[name]
    return [i for i in c["val_words"] if i < len(words) and words[i] == POISON(i)]


def match_oracle(name, blob):
    c = CARRIERS[name]
    got = decode(name, blob)
    amb = set(c.get("ambiguous_lanes", []))
    ok = True
    for k, w in enumerate(c["val_words"]):
        if k in amb:
            continue
        exp = c["oracle"][k]
        g = got[w]
        if c["dtype"] == "f32":
            if not (abs(g - exp) <= 1e-5 * max(1.0, abs(exp))):
                ok = False
        else:
            if (g & M32) != (exp & M32):
                ok = False
    return ok

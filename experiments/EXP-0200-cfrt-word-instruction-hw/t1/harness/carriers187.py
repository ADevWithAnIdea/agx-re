#!/usr/bin/env python3
"""EXP-0187 carrier definitions: dispatch shape, authored inputs, host oracles.

Every oracle here is computed on the HOST from the MSL WE WROTE -- never from an
observed GPU output. Every oracle is NON-ZERO, because on Apple9 a wrong field
value usually produces a SILENT ZERO and a zero oracle would score that silent
zero as a pass.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7, instrument 1). Every carrier
binds its OUTPUT slot as an INPUT file pre-filled with POISON(i) = 0xDEADBEEF+i.
A word that reads back as its own poison is UNWRITTEN, which against a
zero-initialised buffer is indistinguishable from a genuine silent zero.
EXP-0160 saw 25 dispatches report STATUS OK and write nothing at all with no
`InnocentVictim` string anywhere.

INTEGRITY SENTINEL (instrument 2). Every carrier writes `out[1] = 7.5` BEFORE
the ray query is reset, through a path independent of the instruction under
test, into a word no descriptor under test can name. A measurement whose
sentinel is missing is `invalid_run`, is re-run, and is never scored.

THE OBSERVABLE DOES NOT CO-VARY WITH THE FIELD (protocol 3a). The swept field is
byte+1 of a fixed `n4_rt_word` occurrence inside the traversal setup; the
observable is the ray-query RESULT the compiler already computed into out[0].
Nothing in the read-back path is derived from the swept value -- the store's own
data/index registers are untouched, and the store instruction is never the
instruction being mutated. EXP-0140 swept `uniform_mov.dst` while building its
read-back as `device_store(data_reg = the swept dst)`, so a correct hardware
result was a constant observed vector BY CONSTRUCTION; that shape is excluded
here by construction, not by inspection.

Shape (not values) reused and cited from EXP-0184 harness/carriers184.py.
CLEAN-ROOM: OWN-SHADER. Only our own MSL in `kernels/` and its compiled bytes.
"""
import struct

M32 = 0xFFFFFFFF


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def _rq(func, want, kind="primitive", doc=""):
    return {"metal": "kernels/k_rq187.metal", "func": func, "grid": 1, "tg": 1,
            "nwords": 4, "dtype": "f32", "sent_word": 1, "sent_val": f32(7.5),
            "val_words": [0], "tail_words": [2, 3],
            "inputs": {}, "oracle": [f32(want)],
            "accel": 1, "accel_kind": kind,
            "doc": doc or "intersection_query getter"}


# The eight carriers differ in the dimension `n4_rt_word.dst` plausibly controls
# -- which register the traversal setup targets -- along three axes: query PHASE
# (candidate vs committed), TRAVERSAL PATH (triangle / bounding-box / instance),
# and REGISTER PRESSURE (one getter vs three). Eight carriers that could not
# express the field would be ONE carrier (EXP-0164).
CARRIERS = {
    "rq_mdist":  _rq("k_q_mdist",   1.0, "primitive", "committed distance"),
    "rq_mprim":  _rq("k_q_mprim",   2.0, "primitive", "committed primitive id"),
    "rq_cdist":  _rq("k_q_cdist",  10.0, "primitive", "sum candidate distances"),
    "rq_ccount": _rq("k_q_ccount",  4.0, "primitive", "candidate count"),
    "rq_cgeom":  _rq("k_q_cgeom",   5.0, "primitive", "sum candidate geometry_id+1"),
    # ORACLE CORRECTED BEFORE THE FREEZE, from the pre-freeze pilot
    # (raw/prefreeze/pilot01): the host oracle was written as 100*1 + 10*2 + 4 =
    # 124 on the assumption that committing inside the loop still enumerates all
    # four candidates. The unmutated program returns 121 in every one of the 37
    # baseline dispatches, i.e. the loop runs ONCE: the traversal surfaces the
    # NEAREST triangle (t = 1, primitive 2) first, committing it shrinks the ray
    # interval, and nothing closer remains. 100*1 + 10*2 + 1 = 121. This is a
    # correction to OUR host arithmetic, made pre-freeze and recorded, not a
    # hardware result -- and the gate compares each case against the ARM-OPEN
    # BASELINE, never against the oracle, so the wrong constant could not have
    # fabricated movement either way.
    "rq_multi":  _rq("k_q_multi", 121.0, "primitive", "3 getters, higher pressure"),
    "rq_bbox":   _rq("k_q_bbox",    6.0, "bbox",      "bounding-box traversal path"),
    "rq_inst":   _rq("k_q_inst",   11.0, "instance",  "instancing traversal"),
}


def out_inputs(name):
    """Input file specs including the POISON pre-fill of the output slot."""
    c = CARRIERS[name]
    ins = {0: ("poison_%s.bin" % name, poison_bytes(c["nwords"]))}
    ins.update(c["inputs"])
    return ins


def decode(name, blob):
    return f32s(blob)


def summarize(name, blob):
    c = CARRIERS[name]
    words = u32s(blob)
    vals = decode(name, blob)
    return {
        "vals": [vals[i] for i in c["val_words"]],
        "vals_u32": [words[i] for i in c["val_words"]],
        "sent_u32": words[c["sent_word"]] if c["sent_word"] < len(words) else None,
        "tail_u32": [words[i] for i in c["tail_words"] if i < len(words)],
    }, words


def sentinel_ok(name, words):
    c = CARRIERS[name]
    i = c["sent_word"]
    if i >= len(words):
        return False
    return abs(struct.unpack("<f", struct.pack("<I", words[i]))[0]
               - c["sent_val"]) < 1e-6


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
    for k, w in enumerate(c["val_words"]):
        exp = c["oracle"][k]
        if not (abs(got[w] - exp) <= 1e-5 * max(1.0, abs(exp))):
            return False
    return True

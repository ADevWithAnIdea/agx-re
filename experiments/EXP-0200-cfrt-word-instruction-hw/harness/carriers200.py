#!/usr/bin/env python3
"""EXP-0200 carrier definitions: dispatch shape, authored inputs, host oracles.

Every oracle is computed on the HOST from MSL WE WROTE -- never from an observed
GPU output. Every oracle is NON-ZERO (protocol 3.6): on Apple9 a wrong value
usually produces a SILENT ZERO, and a zero oracle scores that silent zero as a
pass.

POISONED READ-BACK (protocol 7, instrument 1). Every carrier binds its OUTPUT
slot as an INPUT file pre-filled with POISON(i) = 0xDEADBEEF + i. This is not
decoration here -- it is the entire observable of the ruler arm, which reads
"the program halted before the result store" off `out[0]` still holding its own
poison. A zero-initialised buffer could not tell that from "wrote 0".

INTEGRITY SENTINEL (instrument 2). `out[1] = 7.5` is stored before any of the
holes, through a path independent of every byte we mutate. In the ruler arm the
sentinel does double duty: `sentinel_ok AND out[0] unwritten` is the signature
of *the program ran and stopped where we told it to*, which is exactly the
distinction between "it acted" and "it never ran".

THE OBSERVABLE DOES NOT CO-VARY WITH THE MUTATION (protocol 3a, EXP-0140). The
mutated bytes are an interior instruction run; the read-back is the store the
compiler already emitted. No register, index or value in the read-back path is
derived from the bytes we write.

The four `intersection_query` carriers are EXP-0187's, used through its VERBATIM
kernel file `t1/kernels/k_rq187.metal` (hash-checked by CAPTURE_CONTRACT.json);
their geometry contract is fixed by `t1/harness/agxrun_persist_as.m`, also
verbatim. Nothing in `t1/` is edited by this experiment.

CLEAN-ROOM: OWN-SHADER. Only our own MSL and its compiled bytes.
"""
import struct

M32 = 0xFFFFFFFF


def POISON(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(n):
    return b"".join(struct.pack("<I", POISON(i)) for i in range(n))


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


# Authored input buffer for every compute carrier: {4.0, 3.0, 2.0, 1.0}.
# It exists to defeat constant folding; every oracle below is derived on the
# host from kernels/k_w200.metal plus these four constants.
CW_IN = b"".join(struct.pack("<f", v) for v in (4.0, 3.0, 2.0, 1.0))


def _compute(func, want, doc):
    return {"metal": "kernels/k_w200.metal", "func": func, "grid": 1, "tg": 1,
            "nwords": 4, "sent_word": 1, "sent_val": f32(7.5),
            "val_words": [0], "tail_words": [2, 3],
            "extra_inputs": {1: ("in_w200.bin", CW_IN)},
            "oracle": [f32(want)], "tol": 1e-4,
            "accel": None, "accel_kind": None, "doc": doc}


def _rq(func, want, kind, doc):
    return {"metal": "t1/kernels/k_rq187.metal", "func": func, "grid": 1, "tg": 1,
            "nwords": 4, "sent_word": 1, "sent_val": f32(7.5),
            "val_words": [0], "tail_words": [2, 3],
            "extra_inputs": {},
            "oracle": [f32(want)], "tol": 1e-5,
            "accel": 1, "accel_kind": kind, "doc": doc}


CARRIERS = {
    # ---- compute carriers authored for this experiment ------------------
    "cw_trans": _compute("k_w_trans", 12.5, "sqrt+exp2+log2+rsqrt+atan+tanh"),
    "cw_sel":   _compute("k_w_sel",  122.0, "ternary / min / max / select / int test"),
    "cw_cf":    _compute("k_w_cf",   111.0, "divergent loop with continue and break"),
    "cw_half":  _compute("k_w_half",  22.0, "native half sqrt/exp2/mul"),
    "cw_mix":   _compute("k_w_mix",   18.0, "loop of device loads + branchy log2"),
    "cw_bar":   _compute("k_w_bar",   30.0, "threadgroup memory + two barriers"),
    # ---- EXP-0187's intersection_query carriers, kernel file VERBATIM ----
    "rq_mdist": _rq("k_q_mdist",  1.0, "primitive", "committed distance"),
    "rq_ccount": _rq("k_q_ccount", 4.0, "primitive", "candidate count"),
    "rq_inst":  _rq("k_q_inst",  11.0, "instance", "instancing traversal"),
    "rq_bbox":  _rq("k_q_bbox",   6.0, "bbox", "bounding-box traversal path"),
}


def out_inputs(name):
    c = CARRIERS[name]
    ins = {0: ("poison_%s.bin" % name, poison_bytes(c["nwords"]))}
    ins.update(c["extra_inputs"])
    return ins


def summarize(name, blob):
    c = CARRIERS[name]
    words = u32s(blob)
    vals = f32s(blob)
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
    c = CARRIERS[name]
    return all(words[i] == POISON(i) for i in c["tail_words"] if i < len(words))


def unwritten(name, words):
    c = CARRIERS[name]
    return [i for i in c["val_words"] if i < len(words) and words[i] == POISON(i)]


def match_oracle(name, blob):
    c = CARRIERS[name]
    got = f32s(blob)
    for k, w in enumerate(c["val_words"]):
        exp = c["oracle"][k]
        if not (abs(got[w] - exp) <= c["tol"] * max(1.0, abs(exp))):
            return False
    return True

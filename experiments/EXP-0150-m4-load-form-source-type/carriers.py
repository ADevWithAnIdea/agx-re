#!/usr/bin/env python3
"""EXP-0150 carrier definition, authored input buffers, poison, and decoding.

ONE carrier: `kernels/carrier.metal`, our own MSL, used purely as a splice site.
Every case replaces its whole `_agc.main` region with a hand-assembled program,
so the carrier's own arithmetic is never executed and never enters an oracle.

Oracles are host-computed per case in `sweepdefs.py` from the ISA semantics we
authored; nothing here is read off a GPU run.
"""
import hashlib
import struct

# ---------------------------------------------------------------------------
# authored memory image (buffer 1)
# ---------------------------------------------------------------------------
# Values are exactly representable in f32 and mutually distinct, so a relocated
# or dropped load is identifiable rather than aliasing onto the right answer.
# mem[1] and mem[2] are the two words every synthesised load reads.
MEM_F32 = [133.75, -8.5, 7.25, -3.125, 0.5, -64.0, 1024.0, 0.03125,
           2.0, -1.0, 16.0, -256.0, 0.25, 3.5, -0.5, 8.0,
           40.0, -40.0, 96.0, -96.0, 12.0, -12.0, 20.0, -20.0,
           5.0, -5.0, 9.0, -9.0, 17.0, -17.0, 33.0, -33.0]

V_A = MEM_F32[1]        # -8.5   loaded with idx_off=1
V_B = MEM_F32[2]        #  7.25  loaded with idx_off=2

# ---------------------------------------------------------------------------
# POISON (FIELD-SWEEP-PROTOCOL 7 / this experiment's contract item 6)
# ---------------------------------------------------------------------------
# The output buffer is pre-filled with 0xDEADBEEF and bound as BOTH an input and
# an output, so "the GPU wrote nothing" (0xDEADBEEF survives) is distinguishable
# from "the GPU wrote zero" (a genuine silent zero). agxrun_persist allocates an
# output buffer only if that index is not already bound as an input
# (`if (!bufs[outIdx[i]])`), so this needs no change to the tool.
POISON_U32 = 0xDEADBEEF
POISON_F32 = struct.unpack("<f", struct.pack("<I", POISON_U32))[0]
OUT_WORDS = 32
OUT_BYTES = OUT_WORDS * 4

SLOT_OUT, SLOT_MEM = 0, 1

# integrity sentinel: written by a path that does NOT involve the instruction
# under test, before it runs. Its absence means our shader did not really run.
SENTINEL_WORD = 4          # device_store idx_off unit is 16 B (EXP-0082)
SENTINEL_VALUE = 8.0


def _pack_f32(vals):
    return b"".join(struct.pack("<f", v) for v in vals)


def _f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


CARRIER = {
    "metal": "kernels/carrier.metal",
    "func": "k",
    "grid": 1,
    "tg": 1,
    "inputs": {SLOT_MEM: ("mem_f32.bin", _pack_f32(MEM_F32)),
               SLOT_OUT: ("poison_out.bin", struct.pack("<I", POISON_U32) * OUT_WORDS)},
    "outs": {SLOT_OUT: OUT_BYTES},
    "doc": "EXP-0101/0141-shaped low-register-pressure synthesis carrier; "
           "out=buffer(0) (poisoned 0xDEADBEEF), mem=buffer(1).",
}


def decode(raw):
    return _f32s(raw)


def sentinel_ok(outs):
    raw = outs.get(SLOT_OUT)
    if not raw:
        return False
    w = decode(raw)
    return len(w) > SENTINEL_WORD and w[SENTINEL_WORD] == SENTINEL_VALUE


def summarize(outs, oracle_word0):
    """Compare out[0] against the case's host-computed oracle.

    Returns (observed, match). `observed` keeps the first eight words verbatim
    plus a sha256 of the whole buffer so the two gated runs can be compared
    byte-for-byte, and records the sentinel and poison state explicitly."""
    observed = {}
    raw = outs.get(SLOT_OUT)
    if not raw:
        return {"out0": None, "no_output": True}, False
    vals = decode(raw)
    observed["sha_0"] = hashlib.sha256(raw).hexdigest()[:16]
    observed["out0"] = vals[:1]
    observed["head"] = vals[:8]
    observed["sentinel"] = vals[SENTINEL_WORD] if len(vals) > SENTINEL_WORD else None
    observed["poison_left"] = sum(1 for v in vals if v == POISON_F32)
    match = bool(vals) and vals[0] == oracle_word0
    return observed, match

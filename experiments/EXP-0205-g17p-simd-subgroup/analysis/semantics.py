#!/usr/bin/env python3
"""EXP-0205 NAMED SEMANTIC CATALOGUE -- host-computed, per carrier.

A `match` flag says only "the observation equalled the one thing we predicted".
That is enough for a gate and not enough for a spec.  This module builds, from
the AUTHORED INPUTS ALONE, a dictionary of named 32-word vectors covering every
semantic the descriptor could plausibly have selected -- all eight integer ops
and all four float ops in reduce / inclusive-scan / exclusive-scan shape, every
broadcast lane and every xor mask, both ballot masks, the all-active mask, the
all-zero vector -- and identifies each observation against it.

That turns "value 2 moved" into "value 2 produced the signed-maximum reduce",
which is what a documentation deliverable needs, and it does it WITHOUT looking
at the hardware first: every vector here is computed from our own input data and
our own model of the operation.

CLEAN-ROOM: pure host arithmetic over our own authored inputs.
"""
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import carriers205 as C          # noqa: E402

SHAPES = ("reduce", "incl", "excl")


def catalogue(carrier):
    """name -> 32-word u32 vector, for everything this carrier could produce."""
    cat = {}
    spec = C.CARRIERS[carrier]
    ins = spec["in_words"]

    cat["all_zero"] = [0] * 32
    cat["all_ones"] = [C.M32] * 32
    cat["identity_lane_input"] = [ins[t] & C.M32 for t in range(32)]

    base = C.baseline_oracle(carrier)
    if base is not None:
        cat["carrier_baseline"] = list(base)

    if carrier.startswith("sb_"):
        cat["ballot_mask_1"] = [C.BALLOT_MASK] * 32
        cat["ballot_mask_2"] = [C.BALLOT_MASK2] * 32
        cat["ballot_mask_1_inverted"] = [(~C.BALLOT_MASK) & C.M32] * 32
        cat["ballot_mask_2_inverted"] = [(~C.BALLOT_MASK2) & C.M32] * 32
        cat["active_all_lanes"] = [C.M32] * 32
        cat["active_mask_form_observed_shape"] = [
            C.M32 if ((C.BALLOT_MASK >> t) & 1) else C.INACTIVE_FILL
            for t in range(32)]

    if carrier.startswith("sr_"):
        if spec["float_in"]:
            fv = [float(x) for x in ins[:32]]
            iv = [C.bits_f32(x) for x in fv]
        else:
            iv = [x & C.M32 for x in ins[:32]]
            fv = [C.from_bits(x) for x in iv]
        for op in C.INT_OPS:
            for sh in SHAPES:
                cat["int:%s:%s" % (op, sh)] = C.int_model(op, sh, iv)
        for op in C.FLT_OPS:
            for sh in SHAPES:
                try:
                    cat["flt:%s:%s" % (op, sh)] = C.flt_model(op, sh, fv)
                except (OverflowError, ValueError):
                    pass

    if carrier.startswith("sh_"):
        src = [x & C.M32 for x in ins[:32]]
        for lane in range(32):
            cat["bcast:lane%d" % lane] = [src[lane]] * 32
            cat["xor:mask%d" % lane] = [src[t ^ lane] for t in range(32)]
        for d in range(1, 32):
            cat["up:delta%d" % d] = [src[max(t - d, 0)] for t in range(32)]
            cat["down:delta%d" % d] = [src[min(t + d, 31)] for t in range(32)]
            cat["rot:delta%d" % d] = [src[(t + d) & 31] for t in range(32)]
    return cat


_CACHE = {}


def identify(carrier, vals):
    """Every catalogue name whose vector equals `vals` exactly (may be empty)."""
    if carrier not in _CACHE:
        _CACHE[carrier] = catalogue(carrier)
    v = [x & C.M32 for x in vals]
    return sorted(k for k, w in _CACHE[carrier].items()
                  if len(w) == len(v) and all((a & C.M32) == b
                                              for a, b in zip(w, v)))

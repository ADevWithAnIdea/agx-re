#!/usr/bin/env python3
"""EXP-0203 HOST ORACLE.

This module is the whole point of the experiment.  It turns each case's OWN observed
pre-dump into a complete predicted 16-word post-dump, so that `observed == predicted` is a
statement about THE FIELD'S VALUE and not merely about the instruction having executed.

The models are FROZEN (PRE_REGISTRATION section 4).  The primary `half_alu_fma12` model was
fitted OFFLINE from our own committed EXP-0180 raw before this file existed and matched
256/256 on each of two carriers; the `half_pack` model is a pre-registered candidate list
whose member is selected by the pilot under a frozen rule and then VERIFIED on fresh gated
runs.  Every case additionally records which OTHER frozen models would have matched, so a
model refutation is visible in the raw rather than hidden behind a pass/fail bit.

PRECISION.  Expressions are evaluated in IEEE binary64 and rounded ONCE to binary16,
round-to-nearest-even -- i.e. a FUSED multiply-add with a single final rounding.  Every case
also carries `alt2r`, the two-rounding prediction, so a fused/unfused disagreement is
measured rather than assumed.  Overflow rounds to a signed infinity (RNE) and is flagged;
a subnormal prediction is flagged, because a flush-to-zero hardware behaviour is a hardware
fact and must not be charged against the field under test.

CLEAN-ROOM: pure host arithmetic over our own observations.
"""
import math
import struct

import isa_helpers as H


def to_f16(x):
    """binary64 -> (binary16 bits, flags).  RNE; overflow -> signed inf."""
    if isinstance(x, float) and math.isnan(x):
        return 0x7E00, {"nan": True, "overflow": False, "subnormal": False}
    try:
        b = struct.unpack("<H", struct.pack("<e", float(x)))[0]
    except (OverflowError, ValueError):
        b = 0xFC00 if x < 0 else 0x7C00
        return b, {"nan": False, "overflow": True, "subnormal": False}
    return b, {"nan": False, "overflow": False, "subnormal": H.f16_subnormal(b)}


def v16(bits):
    return H.bits_f16(bits)


# --------------------------------------------------------------------------
# FROZEN model families.
# Each model maps (a, b, c) fp16 VALUES -> a binary64 expression.
# --------------------------------------------------------------------------
FMA12_MODELS = {
    "abs(a)*b-c": lambda a, b, c: abs(a) * b - c,          # PRE-REGISTERED PRIMARY
    "abs(a)*b+c": lambda a, b, c: abs(a) * b + c,
    "a*b-c": lambda a, b, c: a * b - c,
    "a*b+c": lambda a, b, c: a * b + c,
    "-(a*b+c)": lambda a, b, c: -(a * b + c),
    "-abs(a)*b+c": lambda a, b, c: -abs(a) * b + c,
    "c*b-a": lambda a, b, c: c * b - a,
    "a-c": lambda a, b, c: a - c,
    "abs(a)*b": lambda a, b, c: abs(a) * b,
}
FMA12_PRIMARY = "abs(a)*b-c"

# half_pack candidate list.  `write` says which half of the destination receives the
# result; `pack` models write the whole 32-bit register.
HP_MODELS = {
    "hi=fp16(B+A)": {"kind": "half", "half": 1, "f": lambda B, A: B + A},   # CANDIDATE PRIMARY
    "lo=fp16(B+A)": {"kind": "half", "half": 0, "f": lambda B, A: B + A},
    "hi=fp16(B*A)": {"kind": "half", "half": 1, "f": lambda B, A: B * A},
    "hi=B": {"kind": "half", "half": 1, "f": lambda B, A: B},
    "hi=A": {"kind": "half", "half": 1, "f": lambda B, A: A},
    "pack(A<<16|B)": {"kind": "pack", "hi": "A", "lo": "B"},
    "pack(B<<16|A)": {"kind": "pack", "hi": "B", "lo": "A"},
}
HP_PRIMARY = "hi=fp16(B+A)"


def _apply_markers(post, lay):
    for m, v in lay.markers:
        post[m] = v
    post[lay.R_IDX] = 0
    return post


def fma12_predict(pre, blk, lay, model=FMA12_PRIMARY):
    """Predicted post-dump for a 12-byte fp16 fma instance, from this case's own pre-dump."""
    d = blk[0] >> 4
    ab, a_un = H.hval(pre, blk[1])
    bb, b_un = H.hval(pre, blk[3])
    cb, c_un = H.hval(pre, blk[5])
    a, b, c = v16(ab), v16(bb), v16(cb)
    res, fl = to_f16(FMA12_MODELS[model](a, b, c))
    # two-rounding variant: round the product to fp16 first
    p, _ = to_f16(abs(a) * b if model.startswith("abs(") else a * b)
    alt, _ = to_f16(v16(p) - c if model.endswith("-c") else v16(p) + c)
    post = list(pre)
    post[d] = (post[d] & 0xFFFF0000) | res
    _apply_markers(post, lay)
    fits = [n for n, f in FMA12_MODELS.items() if to_f16(f(a, b, c))[0] == res]
    return {"post": post, "result16": res, "model": model, "alt2r": alt,
            "dst": d, "dst_half": 0, "release_collision": False,
            "a": ab, "b": bb, "c": cb,
            "unseeded": bool(a_un or b_un or c_un),
            "subnormal": fl["subnormal"], "overflow": fl["overflow"], "nan": fl["nan"],
            "undecidable": ("dst_overwritten_by_infrastructure"
                            if d in lay.undecidable_dst else None),
            "model_fits_offline": fits}


def _release(post, blk, descs):
    """The half-ALU families ZERO the half-lane a source descriptor names when the
    operation's opflags request a source release.  `half_pack`'s byte+2 = 0x18 carries
    opflags 3 and MEASURED (pilot01, 80/80) releases BOTH named source lanes; the 12-byte
    fma form's byte+2 = 0x06 carries opflags 0 and releases nothing.  Which lane is zeroed
    depends on the descriptor, so for `half_pack` this makes the oracle MORE discriminating,
    not less."""
    for desc in descs:
        r, h = H.hreg(desc)
        if r < H.N_REGS:
            post[r] = post[r] & (0x0000FFFF if h else 0xFFFF0000)
    return post


def halfpack_predict(pre, blk, lay, model=HP_PRIMARY):
    d = blk[0] >> 4
    Bb, B_un = H.hval(pre, blk[1])
    Ab, A_un = H.hval(pre, blk[3])
    B, A = v16(Bb), v16(Ab)
    m = HP_MODELS[model]
    post = _release(list(pre), blk, (blk[1], blk[3]))
    collision = (H.hreg(blk[1])[0] == d) or (H.hreg(blk[3])[0] == d)
    if m["kind"] == "half":
        res, fl = to_f16(m["f"](B, A))
        if m["half"]:
            post[d] = (res << 16) | (post[d] & 0xFFFF)
        else:
            post[d] = (post[d] & 0xFFFF0000) | res
    else:
        hi = Bb if m["hi"] == "B" else Ab
        lo = Bb if m["lo"] == "B" else Ab
        res, fl = ((hi << 16) | lo), {"subnormal": False, "overflow": False, "nan": False}
        post[d] = res
    _apply_markers(post, lay)
    return {"post": post, "result16": res, "model": model, "alt2r": res,
            "dst": d, "dst_half": (m["half"] if m["kind"] == "half" else None),
            "release_collision": collision,
            "a": Bb, "b": Ab, "c": None,
            "unseeded": bool(A_un or B_un),
            "subnormal": fl["subnormal"], "overflow": fl["overflow"], "nan": fl["nan"],
            "undecidable": ("dst_overwritten_by_infrastructure"
                            if d in lay.undecidable_dst else None),
            "model_fits_offline": None}


def null_predict(pre, lay):
    """The `__fals_F1_null` falsifier: the block writes nothing at all."""
    post = list(pre)
    _apply_markers(post, lay)
    return {"post": post, "result16": None, "model": "null", "alt2r": None,
            "dst": None, "dst_half": None, "release_collision": False,
            "a": None, "b": None, "c": None, "unseeded": False,
            "subnormal": False, "overflow": False, "nan": False,
            "undecidable": None, "model_fits_offline": None}


def hp_model_fits(pre, post, blk, lay):
    """Which frozen half_pack models reproduce the OBSERVED post-dump.  Used by the pilot's
    frozen selection rule and recorded per case for diagnosis."""
    out = []
    for name in HP_MODELS:
        if halfpack_predict(pre, blk, lay, name)["post"] == list(post):
            out.append(name)
    return out


def digest(vec):
    return "".join("%08x" % (w & 0xFFFFFFFF) for w in vec)


# --------------------------------------------------------------------------
# Gate C bucket classification.  A per-case semantic class over the FROZEN competing model
# set, distinguishing the five buckets RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 3 Gate C
# requires: correct effect / a different but COHERENT effect / silent-zero-no-write /
# faulted-or-rejected / invalid measurement or contamination.
#
# "A difference from baseline is not a semantic oracle."  So `coherent_alt` is reported
# separately from `correct`, and `unexplained` is a real bucket that this classifier is
# allowed to return -- it is not a residual that gets rounded into a pass.
# --------------------------------------------------------------------------
def classify_semantics(o, blk, lay, instr, outcome, victim, orc):
    if outcome == "measurement_failed":
        return "measurement_failure", []
    if victim:
        return "contaminated", []
    if outcome in ("fault", "hang"):
        return "faulted_or_rejected", []
    if outcome in ("undecodable", "carrier_dead", "invalid_run") or o is None:
        return "invalid_measurement", []
    if orc is not None and orc.get("undecidable"):
        return "carrier_undecidable", []
    pre, post = o["pre"], o["post"]
    if orc is not None and post == orc["post"]:
        return "correct", [orc["model"]]
    fits = []
    if instr == "half_alu_fma12":
        for name in FMA12_MODELS:
            if fma12_predict(pre, blk, lay, name)["post"] == post:
                fits.append(name)
    else:
        for name in HP_MODELS:
            if halfpack_predict(pre, blk, lay, name)["post"] == post:
                fits.append(name)
    if fits:
        return "coherent_alt_model", fits
    if post == null_predict(pre, lay)["post"]:
        return "no_write", []
    if orc is not None and orc.get("dst") is not None:
        d, h = orc["dst"], (orc.get("dst_half") or 0)
        if H.lane(post[d], h) == 0 and H.lane(pre[d], h) != 0:
            return "silent_zero", []
    return "unexplained", []

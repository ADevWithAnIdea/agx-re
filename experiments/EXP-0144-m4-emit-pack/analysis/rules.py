#!/usr/bin/env python3
"""EXP-0144 rule extraction: turn a 256-value byte sweep into something an
EMITTER can use -- an exact bit rule, an operand/register map, or a format map.

Pure analysis over raw/. Never writes to raw/, never touches the GPU.
"""
import collections, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import oracle as O          # noqa: E402

M32 = 0xFFFFFFFF


def bit_rule(ok_values, universe):
    """Find (mask, req) with {v in universe : v & mask == req} == set(ok_values).

    Returns a dict describing the rule and how exactly it fits. This is the form an
    emitter needs: "these bits must hold these values, the rest are free"."""
    S = set(ok_values)
    if not S:
        return {"kind": "never_ok", "n_ok": 0}
    if S == set(universe):
        return {"kind": "always_ok", "n_ok": len(S),
                "emit": "any value 0..%d reproduces the documented behaviour" % max(universe)}
    ones, zeros = M32, M32
    for v in S:
        ones &= v
        zeros &= ~v & 0xFF
    mask = (ones | zeros) & 0xFF
    req = ones & 0xFF
    pred = {v for v in universe if (v & mask) == req}
    exact = pred == S
    free = [b for b in range(8) if not (mask >> b) & 1]
    return {"kind": "bitmask" if exact else "bitmask_approx",
            "mask": mask, "required": req, "exact": exact,
            "n_ok": len(S), "n_predicted": len(pred),
            "false_pos": sorted(pred - S)[:16], "false_neg": sorted(S - pred)[:16],
            "free_bits": free,
            "emit": "value & 0x%02x == 0x%02x  (bits %s are DON'T CARE)"
                    % (mask, req, free if free else "none")}


def operand_map(pairs):
    """pairs = [(byte_value, operand_index_or_None)]. Fit index = (v >> k) & m.

    A hit tells an emitter the field's SCALE: e.g. index = (v >> 2) & 0x3f means the
    field holds reg<<2. Returns the best exact fit, or the raw map if none fits."""
    obs = [(v, i) for (v, i) in pairs if i is not None]
    if len(obs) < 2:
        return {"kind": "insufficient", "n_points": len(obs)}
    best = None
    for shift in range(8):
        for width in range(1, 9):
            m = (1 << width) - 1
            if all(((v >> shift) & m) == i for v, i in obs):
                cand = {"kind": "linear", "shift": shift, "width": width,
                        "emit": "operand_index = (value >> %d) & 0x%x   i.e. field = index << %d"
                                % (shift, m, shift), "n_points": len(obs)}
                if best is None or shift > best["shift"]:
                    best = cand
    if best:
        return best
    return {"kind": "table", "n_points": len(obs), "map": dict(obs[:40])}


# ---------------------------------------------------------------------------
# Format models: given an input vector, what would each candidate format produce?
# ---------------------------------------------------------------------------
def pack_models(v):
    return {
        "unorm2x16":        O.pack_unorm2x16(v[0], v[1]),
        "unorm2x16_tiedown": O.pack_unorm2x16(v[0], v[1], "down"),
        "snorm2x16":        O.pack_snorm2x16(v[0], v[1]),
        "snorm2x16_rte":    O.pack_snorm2x16(v[0], v[1], "rte"),
        "half2x16":         (O.f16_bits(v[0]) | (O.f16_bits(v[1]) << 16)) & M32,
        "raw_v0":           O.f32_bits(v[0]),
        "raw_v1":           O.f32_bits(v[1]),
        "unorm8x2":         (max(0, min(255, round(min(1.0, max(0.0, v[0])) * 255)))
                             | (max(0, min(255, round(min(1.0, max(0.0, v[1])) * 255))) << 8)),
        "zero":             0,
    }


def unpack_models(v):
    x, y = O.unpack_unorm2x16(v[0])
    sx, sy = O.unpack_snorm2x16(v[0])
    return {
        "unorm2x16_lo":  O.f32_bits(x),
        "snorm2x16_lo":  O.f32_bits(sx),
        "half_lo":       O.f32_bits(O.bits_f16(v[0] & 0xFFFF)),
        "unorm8_lo":     O.f32_bits((v[0] & 0xFF) / 255.0),
        "snorm8_lo":     O.f32_bits(max(-1.0, ((v[0] & 0xFF) - 256 if (v[0] & 0x80) else (v[0] & 0xFF)) / 127.0)),
        "u2f":           O.f32_bits(O.u2f(v[0])),
        "i2f":           O.f32_bits(O.i2f(v[0])),
        "raw_v0":        v[0] & M32,
        "zero":          0,
    }


def format_map(records, models_fn, slot, vec_of):
    """records: X-arm records for ONE byte, many (value, vector) pairs.

    A byte value is an EMITTABLE FORMAT CODE only if one model explains its output
    for EVERY semantic vector tested -- one vector agreeing is a coincidence."""
    byval = collections.defaultdict(list)
    for r in records:
        byval[r["value"]].append(r)
    out = {}
    for val, rs in sorted(byval.items()):
        votes = None
        for r in rs:
            if r["validity"] != "valid" or not r.get("observed"):
                continue
            b = bytes.fromhex(r["observed"])
            w = struct.unpack("<%dI" % (len(b) // 4), b)
            got = w[slot] if slot < len(w) else None
            models = models_fn(vec_of(r))
            fit = {name for name, exp in models.items() if exp == got}
            votes = fit if votes is None else (votes & fit)
        if votes:
            out[val] = sorted(votes)
    return out

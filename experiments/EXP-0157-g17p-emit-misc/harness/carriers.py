#!/usr/bin/env python3
"""EXP-0157 carrier definitions (G17P).

Each entry names one of OUR OWN MSL kernels, its dispatch shape, its authored
input buffers, and a HOST-COMPUTED oracle derived from the source we wrote --
never from an observed GPU output.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7 / EXP-0140): `agxrun_persist`
reuses an input buffer when the same slot is also an output, so every carrier
binds its OUTPUT slot as an input file pre-filled with
POISON_WORD(i) = 0xDEADBEEF + i. A word that reads back as its own poison is
UNWRITTEN -- which on this ISA is otherwise indistinguishable from a genuine
silent zero.

NON-ZERO ORACLES. Every ray-query oracle here is non-zero by construction (the
acceleration structure has two geometries and its closest hit is primitive id
2), because a wrong field value on Apple9 usually produces a SILENT ZERO and a
zero oracle would score that silent zero as a pass.

CLEAN-ROOM: OWN-SHADER. Only our own MSL and its compiled bytes are used.
"""
import hashlib
import math
import struct

U32, F32, U64, F16 = "u32", "f32", "u64", "f16"
M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


def POISON_WORD(i):
    return (0xDEADBEEF + i) & M32


def poison_bytes(nwords):
    return b"".join(struct.pack("<I", POISON_WORD(i)) for i in range(nwords))


def pack_u32(v):
    return b"".join(struct.pack("<I", x & M32) for x in v)


def pack_f32(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


def pack_u64(v):
    return b"".join(struct.pack("<Q", x & M64) for x in v)


def pack_f16(v):
    return b"".join(struct.pack("<e", float(x)) for x in v)


def _u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def _f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def _u64s(b):
    return [struct.unpack("<Q", b[i:i + 8])[0] for i in range(0, len(b) - 7, 8)]


def _f16s(b):
    return [struct.unpack("<e", b[i:i + 2])[0] for i in range(0, len(b) - 1, 2)]


# ---------------------------------------------------------------- inputs
# EXP-0146's frozen SFU input row, verbatim, so a G17P number is comparable to
# the M4 number it is being tested against.  Rows 4..7 need range reduction
# (|x| > pi/2), which is the region EXP-0146 found `sfu_marker.byte+0` controls.
SFU_A = [0.0, 0.5, 1.0, 1.5, 3.0, 6.5, -4.25, 12.75]
ROUND_A = [0.0, 0.5, 1.5, 2.5, -0.5, -1.5, 7.25, -7.25]
U64_A = [0x0123456789ABCDEF, 0x00000001F0000000, 0x0000000312345678,
         0xFFFFFFFFFFFFFFFF, 0x0000000A7FFFFFFF, 0x0000000C80000000,
         0x0000000000000000, 0xDEADBEEFCAFEBABE]
U64_B = [0x0123456789ABCDEF, 0x0000000210000000, 0x0000000312345678,
         0x0000000000000001, 0x0000000B80000000, 0x0000000C80000000,
         0x0000000000000000, 0x1234567887654321]
# half4 / half3 inputs: asymmetric, exactly representable in fp16.
H_A = [1.5, -2.25, 0.5, 3.0,  -1.0, 4.5, 2.0, -0.75,
       0.25, 6.0, -3.5, 1.0,  8.0, -0.5, 1.25, 2.5,
       -4.0, 0.75, 5.0, -1.5, 3.25, -2.0, 0.125, 7.0,
       2.75, -6.5, 1.75, -0.25, 0.625, 5.5, -3.0, 4.25]
H_B = [2.0, 0.5, -1.5, 1.25,  3.5, -2.0, 0.75, 4.0,
       -0.5, 1.0, 2.25, -3.0, 0.375, 6.5, -1.25, 0.5,
       5.0, -4.5, 1.5, 2.5,  -0.75, 3.0, 8.0, -1.0,
       1.125, 0.25, -5.5, 2.0, 4.75, -0.5, 1.5, 3.75]
MEM_F32 = [133.75, -8.5, 7.25, -3.125, 0.5, -64.0, 1024.0, 0.03125,
           2.0, -1.0, 16.0, -256.0, 0.25, 3.5, -0.5, 8.0]
NIN = 8

RQ_WORDS = 4          # single-getter carriers: out[0] = value, out[1] = sentinel
SENTINEL = 7.5


def _rq(func, want0, doc):
    return {
        "metal": "kernels/k_rq_getters.metal", "func": func, "grid": 1, "tg": 1,
        "accel": 1, "accel_kind": "primitive",
        "inputs": {0: ("poison_rq.bin", poison_bytes(RQ_WORDS))},
        "outs": {0: 4 * RQ_WORDS}, "dtype": {0: F32},
        "oracle": {0: [want0, SENTINEL, None, None]},
        "src_exp": "EXP-0157", "doc": doc,
    }


CARRIERS = {
    # ---------------- ray-query carriers (need the acceleration structure) ---
    "rq_cprim":  _rq("k_cand_prim",  3.0,  "sum of candidate primitive ids 0+1+2+0"),
    "rq_cgeom":  _rq("k_cand_geom",  1.0,  "sum of candidate geometry ids 0+0+0+1"),
    "rq_cdist":  _rq("k_cand_dist",  10.0, "sum of candidate distances 3+2+1+4"),
    "rq_ccount": _rq("k_cand_count", 4.0,  "number of candidates"),
    "rq_mprim":  _rq("k_comm_prim",  2.0,  "committed (closest) primitive id"),
    "rq_mdist":  _rq("k_comm_dist",  1.0,  "committed (closest) distance"),
    "rq_mtype":  _rq("k_comm_type",  1.0,  "committed intersection type == triangle"),
    "rq_all": {
        "metal": "kernels/k_rq_prim.metal", "func": "k", "grid": 1, "tg": 1,
        "accel": 1, "accel_kind": "primitive",
        "inputs": {0: ("poison_rq8.bin", poison_bytes(8))},
        "outs": {0: 32}, "dtype": {0: F32},
        "oracle": {0: [4.0, 3.0, 1.0, 10.0, 2.0, 0.0, 1.0, 1.0]},
        "src_exp": "EXP-0157",
        "doc": "all eight ray-query quantities in one program; the widest oracle "
               "we have, used as the cross-check that the AS binding works.",
    },
    # ---------------- SFU / integer-misc carriers (EXP-0146 revalidation) ----
    "sfusin": {
        "metal": "kernels/k_sfu_sin.metal", "func": "k", "grid": NIN, "tg": NIN,
        "inputs": {0: ("sfu_a.bin", pack_f32(SFU_A)),
                   1: ("poison8.bin", poison_bytes(NIN))},
        "outs": {1: 4 * NIN}, "dtype": {1: F32},
        "oracle": {1: [math.sin(x) for x in SFU_A]}, "tol": 2e-3,
        "src_exp": "EXP-0146",
        "doc": "EXP-0146's fast::sin carrier, verbatim. Rows 4..7 need range "
               "reduction -- the region EXP-0146 found sfu_marker controls.",
    },
    "sfucos": {
        "metal": "kernels/k_provoke.metal", "func": "k_sfu_cos", "grid": NIN, "tg": NIN,
        "inputs": {0: ("sfu_a.bin", pack_f32(SFU_A)),
                   1: ("poison8.bin", poison_bytes(NIN))},
        "outs": {1: 4 * NIN}, "dtype": {1: F32},
        "oracle": {1: [math.cos(x) for x in SFU_A]}, "tol": 2e-3,
        "src_exp": "EXP-0157",
        "doc": "second, independent SFU lowering -- the adversarial cross-check "
               "for every sfu_marker / n2_op6 rule measured in sfusin.",
    },
    "sfumix": {
        "metal": "kernels/k_provoke.metal", "func": "k_sfu_sincos", "grid": NIN, "tg": NIN,
        "inputs": {0: ("sfu_a.bin", pack_f32(SFU_A)),
                   1: ("poison8.bin", poison_bytes(NIN))},
        "outs": {1: 4 * NIN}, "dtype": {1: F32},
        "oracle": {1: [math.sin(x) + math.cos(x) + math.tan(x) for x in SFU_A]},
        "tol": 2e-2,
        "src_exp": "EXP-0157",
        "doc": "sin+cos+tan in one program: the densest n2_op6 / sfu_marker site "
               "we can produce on G17P (7 n2_op6, 2 sfu_marker).",
    },
    "u64eq": {
        "metal": "kernels/k_u64eq.metal", "func": "k", "grid": NIN, "tg": NIN,
        "inputs": {0: ("u64a.bin", pack_u64(U64_A)), 1: ("u64b.bin", pack_u64(U64_B)),
                   2: ("poison8.bin", poison_bytes(NIN))},
        "outs": {2: 4 * NIN}, "dtype": {2: U32},
        "oracle": {2: [1 if a == b else 0 for a, b in zip(U64_A, U64_B)]},
        "src_exp": "EXP-0146",
        "doc": "EXP-0146's n3_mov / n2_op6 carrier, verbatim. Four of the eight "
               "rows compare EQUAL, so the oracle is not all-zero.",
    },
    "roundm": {
        "metal": "kernels/k_roundmodes.metal", "func": "k", "grid": NIN, "tg": NIN,
        "inputs": {0: ("round_a.bin", pack_f32(ROUND_A)),
                   1: ("poison8.bin", poison_bytes(NIN))},
        "outs": {1: 4 * NIN}, "dtype": {1: U32},
        "oracle": None,                 # filled in below (host-computed)
        "src_exp": "EXP-0146",
        "doc": "EXP-0146's n2_op10 carrier, verbatim.",
    },
    # ---------------- half-coordinate carriers -------------------------------
    "h4fma": {
        "metal": "kernels/k_provoke.metal", "func": "k_h4_fma", "grid": NIN, "tg": NIN,
        "inputs": {0: ("h_a.bin", pack_f16(H_A)), 1: ("h_b.bin", pack_f16(H_B)),
                   2: ("poison16.bin", poison_bytes(2 * NIN))},
        "outs": {2: 8 * NIN}, "dtype": {2: F16},
        "oracle": None, "tol": 8e-3,
        "src_exp": "EXP-0157",
        "doc": "half4 fma with a reversed second operand -- the only own-MSL "
               "provocation on G17P that emits h_coord_hi.",
    },
    "h3mix": {
        "metal": "kernels/k_provoke.metal", "func": "k_h3_mix", "grid": NIN, "tg": NIN,
        "inputs": {0: ("h_a.bin", pack_f16(H_A)), 1: ("h_b.bin", pack_f16(H_B)),
                   2: ("poison16.bin", poison_bytes(2 * NIN))},
        "outs": {2: 8 * NIN}, "dtype": {2: F16},
        "oracle": None, "tol": 8e-3,
        "src_exp": "EXP-0157",
        "doc": "half3 mix+fma -- the only own-MSL provocation on G17P that emits "
               "h_coord_hi_ext.",
    },
    # ---------------- whole-program synthesis carrier (arms L, M) ------------
    "synth": {
        "metal": "kernels/carrier_synth.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {0: ("poison_synth.bin", poison_bytes(16)),
                   1: ("mem_f32.bin", pack_f32(MEM_F32))},
        "outs": {0: 64}, "dtype": {0: U32},
        "oracle": None,                 # per case
        "src_exp": "EXP-0141",
        "doc": "EXP-0141's low-register-pressure synthesis carrier (via EXP-0153), "
               "verbatim. Its own arithmetic never runs: arms L and M replace the "
               "whole of _agc.main with a hand-assembled program.",
    },
}


def _host_roundmodes(x):
    import math as _m
    def _rint(v):                      # round-half-to-even, what rint() does
        return int(_m.floor(v + 0.5)) if (v - _m.floor(v)) != 0.5 else \
               int(2 * round(v / 2.0))
    def _round(v):                     # round-half-away-from-zero
        return int(_m.floor(v + 0.5)) if v >= 0 else int(_m.ceil(v - 0.5))
    tot = (_rint(x) + int(_m.floor(x)) + int(_m.ceil(x)) + int(x) + _round(x))
    return tot & M32


CARRIERS["roundm"]["oracle"] = {1: [_host_roundmodes(x) for x in ROUND_A]}


def _h4_oracle():
    out = []
    for g in range(NIN):
        x = H_A[4 * g:4 * g + 4]
        y = H_B[4 * g:4 * g + 4]
        yw = [y[3], y[2], y[1], y[0]]
        xw = [x[3], x[2], x[1], x[0]]
        yy = [y[1], y[0], y[3], y[2]]
        out += [(x[i] * yw[i] + xw[i]) * yy[i] for i in range(4)]
    return out


def _h3_oracle():
    """`device half3*` has an 8-byte stride, i.e. FOUR halves per element with
    the fourth unused -- so the oracle predicts words 4g+0..2 and leaves 4g+3
    unscored."""
    out = []
    for g in range(NIN):
        x = H_A[4 * g:4 * g + 3]
        y = H_B[4 * g:4 * g + 3]
        yz = [y[2], y[0], y[1]]
        out += [(x[i] + (y[i] - x[i]) * 0.25) * (x[i] * y[i] + yz[i]) for i in range(3)]
        out += [None]
    return out


CARRIERS["h4fma"]["oracle"] = {2: _h4_oracle()}
CARRIERS["h3mix"]["oracle"] = {2: _h3_oracle()}


def _decode_as(dt, raw):
    return {U32: _u32s, U64: _u64s, F16: _f16s}.get(dt, _f32s)(raw)


def summarize(carrier, outs, oracle=None, dtype=None, tol=None):
    """Compare a case's outputs against `oracle` (default: the carrier's own
    host-computed oracle). Returns (observed, match). A `None` entry in the
    oracle is recorded but never scored."""
    spec = CARRIERS[carrier]
    want = spec["oracle"] if oracle is None else oracle
    t = spec.get("tol", 0.0) if tol is None else tol
    observed, match = {}, True
    for idx, raw in sorted(outs.items()):
        dt = dtype[idx] if dtype and idx in dtype else spec["dtype"][idx]
        vals = _decode_as(dt, raw)
        observed["sha_%d" % idx] = hashlib.sha256(raw).hexdigest()[:16]
        w = (want or {}).get(idx)
        if w is None:
            observed["out%d" % idx] = vals[:12]
            continue
        bad = []
        for i in range(len(w)):
            if w[i] is None:
                continue
            if i >= len(vals):
                bad.append([i, "short", w[i]])
            elif dt in (F32, F16):
                v = vals[i]
                if v != v or abs(v - w[i]) > max(t, t * abs(w[i])):
                    bad.append([i, v, w[i]])
            elif vals[i] != w[i]:
                bad.append([i, vals[i], w[i]])
        observed["n_%d" % idx] = len(bad)
        observed["first_%d" % idx] = bad[:4]
        observed["out%d" % idx] = vals[:min(12, max(len(w), 1))]
        match = match and not bad
    return observed, match


def unwritten_words(carrier, outs):
    n = 0
    for idx, raw in sorted(outs.items()):
        for i, v in enumerate(_u32s(raw)):
            if v == POISON_WORD(i):
                n += 1
    return n


def sentinel_ok(carrier, outs):
    """RT carriers write out[1] = 7.5 on a query-independent path. Returns
    True/False, or None for a carrier with no sentinel word."""
    if not carrier.startswith("rq_") or carrier == "rq_all":
        return None
    raw = outs.get(0)
    if not raw or len(raw) < 8:
        return False
    return abs(_f32s(raw)[1] - SENTINEL) < 1e-6

#!/usr/bin/env python3
"""EXP-0141 carrier definitions: our own MSL kernels, their dispatch shape,
their authored input buffers, and a HOST-COMPUTED oracle for the unmutated
program (derived from the MSL we wrote, never from an observed GPU output).

Every oracle here is computed in Python from the kernel source semantics, so a
sweep case's `match` is a comparison against an independent prediction, and the
pre-capture gate can check the UNSPLICED carrier against it before any mutation.
"""
import hashlib
import struct

U32 = "u32"
F32 = "f32"

# ---------------------------------------------------------------------------
# authored input buffers
# ---------------------------------------------------------------------------
# synth carrier memory image: index 1 (-8.5) is the value every synthesised
# device_load reads. Values chosen exactly representable in f32 so the oracle
# -8.5 + 1.5 = -7.0 is exact, and mutually distinct so a relocated load is
# identifiable rather than aliasing onto the right answer.
MEM_F32 = [133.75, -8.5, 7.25, -3.125, 0.5, -64.0, 1024.0, 0.03125,
           2.0, -1.0, 16.0, -256.0, 0.25, 3.5, -0.5, 8.0,
           40.0, -40.0, 96.0, -96.0, 12.0, -12.0, 20.0, -20.0,
           5.0, -5.0, 9.0, -9.0, 17.0, -17.0, 33.0, -33.0]

# atomic carriers: a[j] = 1000*j + 7 -- four mutually distinguishable candidate
# RMW operands, none of them small enough to be confused with a descriptor byte
# or with 0.
ATOM_A = [1000 * j + 7 for j in range(32)]

# threadgroup-tile litmus ramp
TILE_A = list(range(256))

# device-fence carrier lane values
FENCE_A = list(range(8))


def _pack_u32(vals):
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in vals)


def _pack_f32(vals):
    return b"".join(struct.pack("<f", v) for v in vals)


def _u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def _f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


# ---------------------------------------------------------------------------
# carrier table
# ---------------------------------------------------------------------------
def _tile_oracle():
    return [((i + 1) & 255) + ((i + 2) & 255) for i in range(256)]


CARRIERS = {
    "synth": {
        "metal": "kernels/carrier.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {1: ("mem_f32.bin", _pack_f32(MEM_F32))},
        "outs": {0: 32}, "dtype": {0: F32},
        # oracle supplied per case (the whole body is replaced by synthesis)
        "oracle": None,
        "main_len": 170,
        "doc": "EXP-0101-shaped low-pressure synthesis carrier; out=buffer(0), "
               "mem=buffer(1). Its own arithmetic never runs -- every case "
               "replaces _agc.main[0:170] with a hand-assembled program.",
    },
    "atdev": {
        "metal": "kernels/atomic_dev.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {1: ("atom_a.bin", _pack_u32(ATOM_A))},
        "outs": {0: 4, 2: 16}, "dtype": {0: U32, 2: U32},
        "oracle": {0: [ATOM_A[0]], 2: [ATOM_A[1], ATOM_A[2], ATOM_A[3], 0]},
        "doc": "device atomic_fetch_add(o, a[0]) with a[1..3] live across the "
               "atomic -- so a byte that selects the RMW operand register shows "
               "up as 1007/2007/3007 landing in the counter.",
    },
    "atdevimm": {
        "metal": "kernels/atomic_dev_imm.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {1: ("atom_a.bin", _pack_u32(ATOM_A))},
        "outs": {0: 4, 2: 16}, "dtype": {0: U32, 2: U32},
        "oracle": {0: [5000], 2: [ATOM_A[0], ATOM_A[1], ATOM_A[2], ATOM_A[3]]},
        "doc": "same, literal 5000 operand; a[0..3] all live across the atomic.",
    },
    "attg": {
        "metal": "kernels/atomic_tg.metal", "func": "k", "grid": 16, "tg": 16,
        "inputs": {1: ("atom_a.bin", _pack_u32(ATOM_A))},
        "outs": {0: 8}, "dtype": {0: U32},
        "oracle": {0: [sum(ATOM_A[0:16]), ATOM_A[8]]},
        "doc": "threadgroup atomic_fetch_add over 16 lanes; o[0]=sum(a[0..15]), "
               "o[1]=a[8] (a second value kept live across the atomic).",
    },
    "tgtile": {
        "metal": "kernels/tg_tile.metal", "func": "k", "grid": 256, "tg": 256,
        "inputs": {1: ("tile_a.bin", _pack_u32(TILE_A))},
        "outs": {0: 1024}, "dtype": {0: U32},
        "oracle": {0: _tile_oracle()},
        "doc": "256-lane threadgroup-tile litmus: barrier removal makes lanes "
               "read stale zeros. Also the tg_addr_compute carrier (op at +0x2e).",
    },
    "devfence": {
        "metal": "kernels/dev_fence.metal", "func": "k", "grid": 8, "tg": 8,
        "inputs": {1: ("fence_a.bin", _pack_u32(FENCE_A))},
        "outs": {0: 32, 2: 4}, "dtype": {0: U32, 2: U32},
        "oracle": {0: [(22 | 0x10000) + v for v in FENCE_A], 2: [22 | 0x10000]},
        "doc": "device seq_cst fences around a divergent atomic region, made "
               "deterministic by a trailing threadgroup_barrier(mem_device).",
    },
}


def decode(carrier, idx, raw):
    return _u32s(raw) if CARRIERS[carrier]["dtype"][idx] == U32 else _f32s(raw)


def summarize(carrier, outs, oracle=None):
    """Compare a case's outputs against `oracle` (default: the carrier's own
    host-computed oracle). Returns (observed, match). Large buffers are
    summarised (mismatch count + first few) so a record stays compact; the full
    buffer is still fingerprinted by sha256 so the two gated runs can be
    compared byte-for-byte."""
    spec = CARRIERS[carrier]
    want = spec["oracle"] if oracle is None else oracle
    observed = {}
    match = True
    for idx, raw in sorted(outs.items()):
        vals = decode(carrier, idx, raw)
        observed["sha_%d" % idx] = hashlib.sha256(raw).hexdigest()[:16]
        w = (want or {}).get(idx)
        if w is None:
            observed["out%d" % idx] = vals[:8]
            continue
        n = len(w)
        bad = [(i, vals[i], w[i]) for i in range(min(n, len(vals))) if vals[i] != w[i]]
        if len(vals) < n:
            bad.append((-1, "short", n))
        observed["n_%d" % idx] = len(bad)
        observed["first_%d" % idx] = bad[:4]
        if len(w) <= 8 and not bad:
            observed["out%d" % idx] = vals[:len(w)]
        elif len(w) <= 8:
            observed["out%d" % idx] = vals[:len(w)]
        match = match and not bad
    return observed, match

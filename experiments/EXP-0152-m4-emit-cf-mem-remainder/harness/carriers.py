#!/usr/bin/env python3
"""EXP-0152 carrier table: our own MSL kernels, their dispatch shape, their
authored input buffers and a HOST-COMPUTED oracle for the unmutated program.

Every oracle here is computed in Python from the MSL semantics we wrote, so a
case's `match` is a comparison against an independent prediction, never against
an observed GPU output.

`kernels/carrier_cf.metal` is EXP-0112's CF carrier, reused byte-for-byte.
`kernels/atomic_dev.metal`, `atomic_dev_imm.metal`, `atomic_tg.metal` and
`dev_fence.metal` are EXP-0141's own-MSL carriers, reused unchanged (copied,
with this citation, so this experiment's `kernels/` is self-contained and
hash-frozen independently).
"""
import struct

SENT = 0xA5A5A5A5

# ---- authored inputs ------------------------------------------------------
CF_A = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]   # EXP-0112/EXP-0140
CF_N_MIXED = [0, 1, 2, 3, 4, 8, 16, 32]                    # EXP-0140's vector
CF_N_ZERO = [0] * 8                                        # EXP-0152: guard TRUE
ATOM_A = [1000 * j + 7 for j in range(32)]                 # EXP-0141
POISON_BASE = 0xDEADBEEF


def poison_word(i):
    return (POISON_BASE + i) & 0xFFFFFFFF


def pack_u32(v):
    return b"".join(struct.pack("<I", x & 0xFFFFFFFF) for x in v)


def pack_f32(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


def f32bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def poison_buf(nwords):
    return pack_u32([poison_word(i) for i in range(nwords)])


# ---- input file table (materialised by run.py into work/run_<id>/) --------
INPUT_FILES = {
    "poison64": lambda: poison_buf(64),
    "zeros4": lambda: pack_u32([0]),
    "cf_a": lambda: pack_f32(CF_A),
    "cf_n_mixed": lambda: pack_u32(CF_N_MIXED),
    "cf_n_zero": lambda: pack_u32(CF_N_ZERO),
    "atom_a": lambda: pack_u32(ATOM_A),
}

# ---- carriers -------------------------------------------------------------
# `ins` maps buffer index -> INPUT_FILES key; `outs` maps buffer index -> bytes.
CARRIERS = {
    "cfN": {
        "metal": "carrier_cf.metal", "grid": 8, "tg": 8, "mode": "float",
        "ins": {0: "poison64", 1: "cf_a", 2: "cf_n_mixed"}, "outs": {0: 32},
        "sentinel": None, "main_len": 152,
        "doc": "EXP-0112/EXP-0090 CF skeleton carrier, EXP-0140's mixed trip "
               "counts. The loop-entry guard is FALSE (some lane has cnt>0), so "
               "the jump_cond branch is NOT taken -- this is the configuration "
               "in which EXP-0140 found every jump_cond field inert.",
    },
    "cf0": {
        "metal": "carrier_cf.metal", "grid": 8, "tg": 8, "mode": "float",
        "ins": {0: "poison64", 1: "cf_a", 2: "cf_n_zero"}, "outs": {0: 32},
        "sentinel": None, "main_len": 152,
        "doc": "IDENTICAL program bytes; only the `n` INPUT buffer changes to "
               "all zeros, which makes the loop-entry guard uniformly TRUE and "
               "the jump_cond branch actually TAKEN. No program byte, no "
               "length and no displacement differs from cfN.",
    },
    "atdev": {
        "metal": "atomic_dev.metal", "grid": 1, "tg": 1, "mode": "int",
        "ins": {0: "zeros4", 1: "atom_a", 2: "poison64"}, "outs": {0: 4, 2: 16},
        "sentinel": ("2:3", SENT), "main_len": 108,
        "doc": "EXP-0141 device atomic_fetch_add(o, a[0]) with a[1..3] live "
               "across the atomic. dbg[3] is the integrity sentinel.",
    },
    "atdevimm": {
        "metal": "atomic_dev_imm.metal", "grid": 1, "tg": 1, "mode": "int",
        "ins": {0: "zeros4", 1: "atom_a", 2: "poison64"}, "outs": {0: 4, 2: 20},
        "sentinel": ("2:4", SENT), "main_len": 108,
        "doc": "EXP-0141 same-shape carrier, literal 5000 operand; an "
               "independent second device-atomic carrier.",
    },
    "attg": {
        "metal": "atomic_tg.metal", "grid": 16, "tg": 16, "mode": "int",
        "ins": {0: "poison64", 1: "atom_a"}, "outs": {0: 12},
        "sentinel": ("0:2", SENT), "main_len": 194,
        "doc": "EXP-0141 threadgroup atomic_fetch_add over 16 lanes; "
               "o[0]=sum(a[0..15]), o[1]=a[8], o[2]=sentinel.",
    },
}

# instruction sites, re-derived and asserted fresh by baseline.py
SITES = {
    "atdev": ("atomic_mem", 70, 14),
    "atdevimm": ("atomic_mem", 70, 14),
    "attg": ("atomic_tg", 128, 12),
}


def cf_oracle_words(n_vec, cf_oracle):
    """{"0:i": ieee-bits} for the 8 CF lanes."""
    return {"0:%d" % i: f32bits(cf_oracle(CF_A[i], n_vec[i])) for i in range(8)}


def atdev_oracle():
    return {"0:0": ATOM_A[0], "2:0": ATOM_A[1], "2:1": ATOM_A[2],
            "2:2": ATOM_A[3], "2:3": SENT}


def atdevimm_oracle():
    return {"0:0": 5000, "2:0": ATOM_A[0], "2:1": ATOM_A[1], "2:2": ATOM_A[2],
            "2:3": ATOM_A[3], "2:4": SENT}


def attg_oracle():
    return {"0:0": sum(ATOM_A[0:16]), "0:1": ATOM_A[8], "0:2": SENT}

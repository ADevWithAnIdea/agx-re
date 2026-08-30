#!/usr/bin/env python3
"""EXP-0156 carrier table (target: **A18 Pro / G17P**): our own MSL kernels, their dispatch shape, their
authored input buffers and a HOST-COMPUTED oracle for the unmutated program.

Every oracle here is computed in Python from the MSL semantics we wrote, so a
case's `match` is a comparison against an independent prediction, never against
an observed GPU output.

`kernels/carrier_cf.metal` is EXP-0112's CF carrier, reused byte-for-byte.
`kernels/tg_tile.metal` is EXP-M4-14's own `k_thr.metal`, reused byte-for-byte
so the A18 <-> M4 `tg_addr_compute` divergence is tested on the SAME source.
`kernels/bf_add.metal`, `bf_fma.metal`, `h_max.metal`, `h2_fma.metal` are
EXP-0145's own-MSL bf16/half carriers, reused unchanged.
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


# ---------------------------------------------------------------------------
# EXP-0156 additions: the tg_addr_compute divergence carrier and the bf16/half
# numeric carriers.  Everything above this line is EXP-0152's file (which in
# turn reuses EXP-0141/EXP-0112/EXP-0090), retargeted to G17P.
# ---------------------------------------------------------------------------

# tg_tile.metal (= EXP-M4-14's k_thr.metal, byte-for-byte): tile[li] = a[i];
# barrier; o[i] = tile[(li+1)&255] + tile[(li+2)&255].  With a[i] = i and a FULL
# 256-thread threadgroup the whole tile is written, so every read is defined and
# the host oracle is exact.  EXP-M4-14 quotes this carrier's signature as
# o[i] = 2i+3, which is exactly this formula for a[i]=i.
TG_N = 256
TG_A = [float(i) for i in range(TG_N)]
# lanes actually compared (reading all 256 would bloat every raw record)
TG_LANES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15]

def tg_oracle():
    return {"0:%d" % i: f32bits(TG_A[(i + 1) & 255] + TG_A[(i + 2) & 255])
            for i in TG_LANES}

# ---- bf16 / half inputs ---------------------------------------------------
# Values chosen so that BOTH a+b and a*b are EXACTLY representable in bfloat16
# (8-bit significand) and in fp16, so the numeric oracle does not depend on the
# rounding mode.  A separate `bf_round` pair (below) is what measures rounding.
BF_A = [1.0, 2.0, 3.0, 4.0, 1.5, 0.5, 6.0, 10.0]
BF_B = [0.5, 0.25, 1.0, 4.0, 2.5, 0.125, 2.0, 6.0]
BF_C = [0.25, 0.5, 1.0, 2.0, 0.75, 0.25, 1.5, 4.0]
# a+b = 1.5 2.25 4 8 4 0.625 8 16      (all exact in bf16 and fp16)
# a*b = 0.5 0.5  3 16 3.75 0.0625 12 60 (all exact in bf16 and fp16)

# ROUNDING probe: a + b lands strictly between two adjacent bf16 values, nearer
# the upper one.  round-to-nearest -> 1.0078125; truncate-toward-zero -> 1.0.
BF_RA = [1.0] * 8
BF_RB = [3.0 / 512.0] * 8            # 0.005859375


def bf16_bits(x):
    """Top 16 bits of the fp32 encoding (bfloat16 = truncated fp32)."""
    return (f32bits(x) >> 16) & 0xFFFF


def bf16_rne(x):
    """fp32 -> bfloat16 with round-to-nearest-even, as an oracle ALTERNATIVE
    to bf16_bits (truncation).  Which one the hardware implements is what the
    `bf.round` arm measures; neither is assumed."""
    u = f32bits(x)
    lsb = (u >> 16) & 1
    r = (u + 0x7FFF + lsb) >> 16
    return r & 0xFFFF


def fp16_bits(x):
    import struct
    return struct.unpack("<H", struct.pack("<e", float(x)))[0]


def pack16(vals):
    """Pack a list of 16-bit lane values into the u32 words a device store of a
    16-bit type produces (little-endian, lane 2j in the low half)."""
    return {"0:%d" % j: (vals[2 * j] | (vals[2 * j + 1] << 16)) & 0xFFFFFFFF
            for j in range(len(vals) // 2)}


def bf_pack_f32(vals):
    """An authored `device bfloat*` INPUT buffer: 2 bytes per element."""
    return b"".join(struct.pack("<H", bf16_bits(v)) for v in vals)


def h_pack_f16(vals):
    return b"".join(struct.pack("<H", fp16_bits(v)) for v in vals)


def h2_pack_f16(pairs):
    out = b""
    for (x, y) in pairs:
        out += struct.pack("<HH", fp16_bits(x), fp16_bits(y))
    return out


# half2 inputs: .x and .y deliberately DIFFERENT so a result written to the
# wrong half is visible (this is the h_alu_hi high-half test's whole point).
H2_A = [(1.0, 8.0), (2.0, 4.0), (3.0, 2.0), (4.0, 1.0),
        (1.5, 6.0), (0.5, 12.0), (6.0, 0.5), (10.0, 3.0)]
H2_B = [(0.5, 2.0), (0.25, 4.0), (1.0, 0.5), (4.0, 8.0),
        (2.5, 1.0), (0.125, 2.0), (2.0, 4.0), (6.0, 0.25)]
H2_C = [(0.25, 1.0), (0.5, 2.0), (1.0, 4.0), (2.0, 0.5),
        (0.75, 3.0), (0.25, 1.5), (1.5, 0.25), (4.0, 2.0)]

SENT_WORDS = 8


def bf_add_oracle():
    o = pack16([bf16_bits(BF_A[i] + BF_B[i]) for i in range(8)])
    o.update({"4:0": SENT, "4:7": SENT})
    return o


def bf_mul_oracle():
    return pack16([bf16_bits(BF_A[i] * BF_B[i]) for i in range(8)])


def bf_fma_oracle():
    o = pack16([bf16_bits(BF_A[i] * BF_B[i] + BF_C[i]) for i in range(8)])
    o.update({"4:0": SENT, "4:7": SENT})
    return o


def hmax_oracle():
    o = pack16([fp16_bits(max(BF_A[i], BF_B[i])) for i in range(8)])
    o.update({"4:0": SENT, "4:7": SENT})
    return o


def hmin_oracle():
    return pack16([fp16_bits(min(BF_A[i], BF_B[i])) for i in range(8)])


def h2fma_oracle():
    """half2 fma, per half.  out word g = (y<<16)|x for lane g."""
    o = {}
    for g in range(8):
        x = fp16_bits(H2_A[g][0] * H2_B[g][0] + H2_C[g][0])
        y = fp16_bits(H2_A[g][1] * H2_B[g][1] + H2_C[g][1])
        o["0:%d" % g] = (x | (y << 16)) & 0xFFFFFFFF
    o.update({"4:0": SENT, "4:7": SENT})
    return o


INPUT_FILES.update({
    "poison1024": lambda: poison_buf(256),
    "tg_a": lambda: pack_f32(TG_A),
    "bf_a": lambda: bf_pack_f32(BF_A),
    "bf_b": lambda: bf_pack_f32(BF_B),
    "bf_c": lambda: bf_pack_f32(BF_C),
    "bf_ra": lambda: bf_pack_f32(BF_RA),
    "bf_rb": lambda: bf_pack_f32(BF_RB),
    "h_a": lambda: h_pack_f16(BF_A),
    "h_b": lambda: h_pack_f16(BF_B),
    "h2_a": lambda: h2_pack_f16(H2_A),
    "h2_b": lambda: h2_pack_f16(H2_B),
    "h2_c": lambda: h2_pack_f16(H2_C),
})

CARRIERS.update({
    "tgac": {
        "metal": "tg_tile.metal", "grid": TG_N, "tg": TG_N, "mode": "float",
        "ins": {0: "poison1024", 1: "tg_a"}, "outs": {0: 64},
        "sentinel": None, "main_len": 134,
        "doc": "EXP-M4-14's own k_thr.metal, byte-for-byte. Threadgroup tile "
               "reduction; the tg_addr_compute at +46 is on the observed "
               "dataflow path (EXP-M4-14 and EXP-0141 H5 both used exactly "
               "this signature). No room for a sentinel without changing the "
               "compile, so the poisoned read-back is the integrity check.",
    },
    "bfadd": {
        "metal": "bf_add.metal", "grid": 8, "tg": 8, "mode": "int",
        "ins": {0: "poison64", 1: "bf_a", 2: "bf_b", 4: "poison64"},
        "outs": {0: 16, 4: 32}, "sentinel": ("4:0", SENT), "main_len": 80,
        "doc": "EXP-0145 own-MSL native bfloat add (out[g]=a[g]+b[g]). The "
               "0x11-group op sits at +32 as `21 00 1c 00 11 00 c0 81`.",
    },
    "bfround": {
        "metal": "bf_add.metal", "grid": 8, "tg": 8, "mode": "int",
        "ins": {0: "poison64", 1: "bf_ra", 2: "bf_rb", 4: "poison64"},
        "outs": {0: 16, 4: 32}, "sentinel": ("4:0", SENT), "main_len": 80,
        "doc": "IDENTICAL program bytes to bfadd; only the INPUT changes, to a "
               "pair whose exact sum falls between two adjacent bf16 values. "
               "This is what measures the bf16 rounding mode.",
    },
    "bffma": {
        "metal": "bf_fma.metal", "grid": 8, "tg": 8, "mode": "int",
        "ins": {0: "poison64", 1: "bf_a", 2: "bf_b", 3: "bf_c", 4: "poison64"},
        "outs": {0: 16, 4: 32}, "sentinel": ("4:0", SENT), "main_len": 96,
        "doc": "EXP-0145 own-MSL native bfloat fma; the 10-byte 0x1e form at +46.",
    },
    "hmax": {
        "metal": "h_max.metal", "grid": 8, "tg": 8, "mode": "int",
        "ins": {0: "poison64", 1: "h_a", 2: "h_b", 4: "poison64"},
        "outs": {0: 16, 4: 32}, "sentinel": ("4:0", SENT), "main_len": 78,
        "doc": "EXP-0145 own-MSL fp16 max; `hminmax` at +32 as `22 00 1c 00 10 c0`.",
    },
    "h2fma": {
        "metal": "h2_fma.metal", "grid": 8, "tg": 8, "mode": "int",
        "ins": {0: "poison64", 1: "h2_a", 2: "h2_b", 3: "h2_c", 4: "poison64"},
        "outs": {0: 32, 4: 32}, "sentinel": ("4:0", SENT), "main_len": 98,
        "doc": "EXP-0145 own-MSL half2 fma. The compiler emits TWO ops: a "
               "0x?0-group op at +46 and a 0x?8-group op at +54. Whether the "
               "second writes the HIGH half is this experiment's h_alu_hi test.",
    },
})

SITES.update({"tgac": ("tg_addr_compute", 46, 6)})

# Sites our own DECODER mis-tokenizes (a first-class db defect, see RESULTS):
# asserted by EXACT BYTES at an EXACT offset instead of by mnemonic.
RAW_SITES = {
    "bfadd":   [("bf_add_dst", 32, bytes.fromhex("21001c001100c081"))],
    "bfround": [("bf_add_dst", 32, bytes.fromhex("21001c001100c081"))],
    "bffma":   [("bf_fma_dst", 46, bytes.fromhex("21001e0086041000c081"))],
    "hmax":    [("hminmax", 32, bytes.fromhex("22001c0010c0"))],
    "h2fma":   [("half_alu_lo", 46, bytes.fromhex("20001e04810800c0")),
                ("h_alu_hi", 54, bytes.fromhex("28011b09"))],
}

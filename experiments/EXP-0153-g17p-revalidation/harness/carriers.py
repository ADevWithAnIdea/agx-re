#!/usr/bin/env python3
"""EXP-0153 carrier definitions: our own MSL kernels, their dispatch shape,
their authored input buffers, and a HOST-COMPUTED oracle for the unmutated
program (derived from the MSL we wrote, never from an observed GPU output).

Every input vector is copied VERBATIM from the M4 experiment being revalidated,
so a G17P/G16G comparison is a comparison of hardware, not of stimulus:

  synth   <- EXP-0141 (MEM_F32)
  uni     <- EXP-0138 (SEED / UNI_VALS)
  dag     <- EXP-0139 (SEED / IADD_N)
  bfe/shr <- EXP-0139 (A_IN / B_IN)
  u64     <- EXP-0146 (U64_A / U64_B) plus this experiment's own extra
             boundary rows, which the dispatch named explicitly.

POISONED READ-BACK (FIELD-SWEEP-PROTOCOL section 7 / EXP-0140).
`agxrun_persist` reuses an input buffer when the same slot is also requested as
an output, so every carrier binds its OUTPUT slot as an input file pre-filled
with POISON_WORD(i) = 0xDEADBEEF + i. A word that reads back as its own poison
is therefore UNWRITTEN, which on this ISA is otherwise byte-identical to a
genuine silent zero only when the buffer starts zeroed.
"""
import hashlib
import struct

U32, F32, U64 = "u32", "f32", "u64"

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# poison
# ---------------------------------------------------------------------------
def POISON_WORD(i):
    """0xDEADBEEF + i, as an unsigned 32-bit word. Positional, so an unwritten
    word identifies ITSELF, and no legal result of any carrier collides."""
    return (0xDEADBEEF + i) & M32


def poison_bytes(nwords):
    return b"".join(struct.pack("<I", POISON_WORD(i)) for i in range(nwords))


def poison_f32(nwords):
    """The same poison words, viewed as f32 -- what an f32 carrier reads back
    for an unwritten word (0xDEADBEEF+i is a quiet NaN / huge negative, never a
    value any of our oracles produce)."""
    return [struct.unpack("<f", struct.pack("<I", POISON_WORD(i)))[0]
            for i in range(nwords)]


# ---------------------------------------------------------------------------
# authored input buffers (verbatim from the experiments being revalidated)
# ---------------------------------------------------------------------------
# EXP-0141: index 1 (-8.5) is the word every synthesised device_load reads.
MEM_F32 = [133.75, -8.5, 7.25, -3.125, 0.5, -64.0, 1024.0, 0.03125,
           2.0, -1.0, 16.0, -256.0, 0.25, 3.5, -0.5, 8.0,
           40.0, -40.0, 96.0, -96.0, 12.0, -12.0, 20.0, -20.0,
           5.0, -5.0, 9.0, -9.0, 17.0, -17.0, 33.0, -33.0]

# EXP-0138: the uniform file contents bound at buffer(2) of carrier_uni.
UNI_VALS = [101.0, 202.0, 303.0, 404.0]

# EXP-0139: integer probe inputs (asymmetric + boundary).
A_IN = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF, 0x00000001,
        0x00000000, 0x80000000, 0x7FFFFFFF]
B_IN = [3, 5, 8, 1, 31, 32, 2, 0]
NIN = len(A_IN)

# EXP-0146 U64_A/U64_B, with the four rows the EXP-0153 dispatch named
# explicitly folded in. Rows 0..7 are EXP-0146's frozen set (so the M4 result
# is re-run on identical stimulus); rows 8..11 are the dispatch's boundary set.
U64_A = [0x0123456789ABCDEF, 0x00000001F0000000, 0x0000000312345678,
         0xFFFFFFFFFFFFFFFF, 0x0000000A7FFFFFFF, 0x0000000C80000000,
         0x0000000000000000, 0xDEADBEEFCAFEBABE,
         0x8000000000000000,          # + itself  -> 0 (carry out of bit 63)
         0x7FFFFFFFFFFFFFFF,          # + 1       -> 0x8000000000000000
         0xFFFFFFFF00000000,          # + 0xFFFFFFFF -> 0xFFFFFFFFFFFFFFFF
         0xFFFFFFFFFFFFFFFE]          # + 3       -> 1 (full wrap)
U64_B = [0x00000000FEDCBA98, 0x0000000210000000, 0x0000000411111111,
         0x0000000000000001, 0x0000000B80000000, 0x0000000D80000000,
         0x0000000000000000, 0x1234567887654321,
         0x8000000000000000,
         0x0000000000000001,
         0x00000000FFFFFFFF,
         0x0000000000000003]
N64 = len(U64_A)


def pack_u32(vals):
    return b"".join(struct.pack("<I", v & M32) for v in vals)


def pack_f32(vals):
    return b"".join(struct.pack("<f", float(v)) for v in vals)


def pack_u64(vals):
    return b"".join(struct.pack("<Q", v & M64) for v in vals)


def _u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def _f32s(b):
    return [struct.unpack("<f", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def _u64s(b):
    return [struct.unpack("<Q", b[i:i + 8])[0] for i in range(0, len(b) - 7, 8)]


# ---------------------------------------------------------------------------
# carrier table
# ---------------------------------------------------------------------------
SYNTH_OUT_WORDS = 8       # out[0..7]; canary at out[4]
UNI_OUT_WORDS = 16        # out[0], out[4], out[8], out[12]
DAG_OUT_WORDS = 8

CARRIERS = {
    # ---- arm A/D-load: whole-program synthesis (EXP-0141's shape) --------
    "synth": {
        "metal": "kernels/carrier_synth.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {0: ("poison_synth.bin", poison_bytes(SYNTH_OUT_WORDS)),
                   1: ("mem_f32.bin", pack_f32(MEM_F32))},
        "outs": {0: 4 * SYNTH_OUT_WORDS}, "dtype": {0: F32},
        "oracle": None,                      # supplied per case
        "src_exp": "EXP-0141",
        "doc": "EXP-0141-shaped low-pressure synthesis carrier; out=buffer(0), "
               "mem=buffer(1). Its own arithmetic never runs -- every case "
               "replaces the whole of _agc.main with a hand-assembled program.",
    },
    # ---- arm B/D-falu2: MODE-A synthesis with a live uniform file --------
    "uni": {
        "metal": "kernels/carrier_uni.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {0: ("poison_uni.bin", poison_bytes(UNI_OUT_WORDS)),
                   1: ("mem_f32.bin", pack_f32(MEM_F32)),
                   2: ("uni_f4.bin", pack_f32(UNI_VALS))},
        "outs": {0: 4 * UNI_OUT_WORDS}, "dtype": {0: F32},
        "oracle": None,
        "src_exp": "EXP-0138",
        "doc": "EXP-0138's uniform carrier: declares a `constant float4&` so "
               "the container preloads the UNIFORM register file, which is "
               "what falu2.mod_lo's non-GPR source class needs live.",
    },
    # ---- arm D-iadd2: MODE-A synthesis in the long DAG carrier -----------
    "dag": {
        "metal": "kernels/carrier_dag.metal", "func": "k", "grid": 1, "tg": 1,
        "inputs": {0: ("poison_dag.bin", poison_bytes(DAG_OUT_WORDS)),
                   1: ("mem_f32.bin", pack_f32(MEM_F32)),
                   2: ("imem_u32.bin", pack_u32(A_IN))},
        "outs": {0: 4 * DAG_OUT_WORDS}, "dtype": {0: U32},
        "oracle": None,
        "src_exp": "EXP-0139",
        "doc": "EXP-0139's long carrier; every case replaces _agc.main with a "
               "mov_imm seed of r0..r15 followed by the iadd2 under test and "
               "one device_store of r6.",
    },
    # ---- arm E: ibfe, spliced in place in its natural compiled anchor -----
    "bfe": {
        "metal": "kernels/ialu_probes.metal", "func": "k_bfe_const",
        "grid": NIN, "tg": NIN,
        "inputs": {0: ("a_u32.bin", pack_u32(A_IN)),
                   1: ("b_u32.bin", pack_u32(B_IN)),
                   2: ("poison_bfe.bin", poison_bytes(NIN))},
        "outs": {2: 4 * NIN}, "dtype": {2: U32},
        "oracle": {2: [(a >> 4) & 0xFF for a in A_IN]},
        "src_exp": "EXP-0139",
        "doc": "o[i] = extract_bits(a[i], 4u, 8u) -- EXP-0033's single-ibfe "
               "shape, the carrier EXP-0139 used for the offset/width rules.",
    },
    "shr": {
        "metal": "kernels/ialu_probes.metal", "func": "k_shr",
        "grid": NIN, "tg": NIN,
        "inputs": {0: ("a_u32.bin", pack_u32(A_IN)),
                   1: ("b_u32.bin", pack_u32(B_IN)),
                   2: ("poison_bfe.bin", poison_bytes(NIN))},
        "outs": {2: 4 * NIN}, "dtype": {2: U32},
        "oracle": {2: [(a >> (b & 31)) & M32 for a, b in zip(A_IN, B_IN)]},
        "src_exp": "EXP-0139",
        "doc": "o[i] = a[i] >> b[i] -- a SECOND, independent ibfe lowering, "
               "used as the adversarial cross-check for arm E.",
    },
    # ---- arm C: the native 64-bit add, spliced from the 64-bit subtract ---
    "u64": {
        "metal": "kernels/k_u64sub.metal", "func": "k",
        "grid": N64, "tg": N64,
        "inputs": {0: ("a_u64.bin", pack_u64(U64_A)),
                   1: ("b_u64.bin", pack_u64(U64_B)),
                   2: ("poison_u64.bin", poison_bytes(2 * N64))},
        "outs": {2: 8 * N64}, "dtype": {2: U64},
        "oracle": {2: [(a - b) & M64 for a, b in zip(U64_A, U64_B)]},
        "src_exp": "EXP-0146",
        "doc": "out[gid] = a[gid] - b[gid] on `ulong`: ONE iadd2 between an "
               "8-byte device_load pair and an 8-byte device_store. Flipping "
               "`addsub` is EXP-0146's I64-01 test.",
    },
}


def _decode_as(dt, raw):
    if dt == U32:
        return _u32s(raw)
    if dt == U64:
        return _u64s(raw)
    return _f32s(raw)


def decode(carrier, idx, raw):
    return _decode_as(CARRIERS[carrier]["dtype"][idx], raw)


def summarize(carrier, outs, oracle=None, dtype=None):
    """Compare a case's outputs against `oracle` (default: the carrier's own
    host-computed oracle). Returns (observed, match).

    `dtype` optionally overrides the carrier's read-back interpretation for
    this case (arm F reads the `uni` carrier's words as u32 because a
    `mov_imm` immediate is an integer, while arms B/D read the same carrier as
    f32). `oracle` values may be `None` for a word we make no prediction about
    (the word is still recorded, never scored). Buffers are fingerprinted by
    sha256 so the two gated runs can be compared word-for-word offline."""
    spec = CARRIERS[carrier]
    want = spec["oracle"] if oracle is None else oracle
    observed = {}
    match = True
    for idx, raw in sorted(outs.items()):
        vals = _decode_as(dtype[idx] if dtype and idx in dtype
                          else spec["dtype"][idx], raw)
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
            elif vals[i] != w[i]:
                bad.append([i, vals[i], w[i]])
        observed["n_%d" % idx] = len(bad)
        observed["first_%d" % idx] = bad[:4]
        observed["out%d" % idx] = vals[:min(12, max(len(w), 1))]
        match = match and not bad
    return observed, match


def unwritten_words(carrier, outs):
    """How many read-back words still hold their own poison. A fully poisoned
    output means the dispatch did not write anything -- the integrity signal
    the FIELD-SWEEP-PROTOCOL requires for carriers with no independent
    sentinel path."""
    n = 0
    for idx, raw in sorted(outs.items()):
        for i, v in enumerate(_u32s(raw)):
            if v == POISON_WORD(i):
                n += 1
    return n

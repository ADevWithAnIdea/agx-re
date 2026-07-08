# EXP-M4-12 S1-sfu — Transcendental SFU residue closure

Provenance: EXP-M4-12 OWN-SHADER isolated compile (Apple M4 / Apple9, AGX G17).
All bytes traced are the compiled form of MSL we wrote ourselves. No Apple binary
was inspected. We document per-op LENGTHS and byte0/op-select FIELDS only — we do
NOT reconstruct the sin/cos range-reduction algorithm (the 2-byte operand-words
below are treated as opaque immediate/coefficient injections).

## Toolchain
    CEN=/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census
    $CEN/shdump -o out.bin -f k_iso x.metal
    python3 $CEN/agxparse.py out.bin --extract-hex | tr -d '\n ' > out.hex
    python3 work/tok.py out.hex        # tokenizer bound to the LOCAL patched isadb copy

## Method
- Isolated every transcendental / round function as its own `k_iso` kernel.
- Confirmed exp2/log2/exp/log/pow/sqrt/rsqrt/recip/floor/ceil/trunc/rint/fract/abs
  are 100% CLEAN in isolation (0 residue). ALL k_transcend residue = sin+cos; the
  k_transcend_round @0x38/@0x44 residue is a combination effect (op-select 0x21 for
  high dst regs + resync misalignment).
- Reproduced the exact corpus kernels (transcend.metal, transcend_round.metal) —
  byte-identical to the census stream.
- Encoded candidate length rules in a LOCAL COPY of isadb.py (work/isadb.py, the
  shared DB was NOT edited) and iterated until k_transcend & k_transcend_round walk
  with ZERO undecoded bytes, cross-checked against a full-corpus regression.

## Result
- k_transcend: 52 -> 0 undecoded bytes.  k_transcend_round: 20 -> 0.
- Full-corpus regression (47 kernels): total undecoded 252 -> 164, every affected
  kernel IMPROVED, ZERO regressions. Bonus closures: k_tex_atomic -6, r_cent_f -4,
  k_atomics_tg -2, k_cf_loop -2, r_deriv_f -2 (all peel genuine 2-byte words /
  benefit from the op-select fixes; each still ends at its `stop`).

## Two op classes discovered

### A. low-nibble-2 op-select length fixes (byte0 hi-nibble = dst reg r0..r15)
- op-select 0x2b -> 6B  (was: 10 at dst r2, LEN_UNKNOWN at r4/r7/...). Confirmed
  uniform 6B across dst r2/r3/r7.
- op-select 0x03 -> 6B  (was LEN_UNKNOWN at dst r4).
- op-select 0x21 -> 10B (register-operand form with a trailing operand word; was
  10 only at dst r2 via the 0x22 fallback, LEN_UNKNOWN at r4). The census "6B"
  region for `42 81 21 81 22 b0` was a resync-gap artifact — the following
  `02 02 20 80` is this op's tail, NOT a separate iminmax. Proven by the isolated
  `sign` kernel and by transcend_round (8B overruns at @0x4e; only 10B walks clean).

### B. SFU 2-byte operand-words (little-endian immediate/coefficient injections)
Each cleanly bracketed between known-length ops; length 2; operands not bit-decoded
(clean-room: not reconstructing the polynomial). Observed (byte0, byte+1) gates:
  06 02 | 03 02(b2!=0x26) | 01 00 | 00 00 | 00 80 | 00 84 | 00 08*
  80 00 | 80 08 | 80 0c | 20 00 | 20 80 | a0 0c | 3c 01 | 3c 05*
  (* 00 08 / 3c 05 only seen in the fract+sign combo rnd_fs, not in the corpus.)
`80 04` and `00 8c` are pre-existing 2B rules in the shared DB — same family.

See ../S1-sfu/ for the isolated .metal sources and .hex, and work/isadb.py for the
candidate patch (proposed for the shared DB by the main agent, not applied here).

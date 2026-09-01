# EXP-0224 results — generated G17P FP32 fused multiply-add

Status: **canonical compiler recipe proven for FP32 FMA over the r0..r15 operand/destination
bank.**  EXP-0230 later bounded the `n3_mov` fallback: only values held in r16..r63 can be staged
into that bank with the compact move. See `AMENDMENT-04.md`.

Target: Apple A18 Pro / G17P, Metal family Apple9.  Clean-room classes: OWN-SHADER carrier and
HW-PROBE.  Every promoted instruction field was generated from the formulas below; no
compiler-emitted field or instruction byte was copied.

## Canonical encoding

Generate the eight-byte `falu3` form as:

```text
dst       = D
srcA      = (A << 1) | 1
op        = 0x06
srcB      = (B << 1) | 1
ctrl_len  = 0x01
srcC      = C << 1
ctrl      = 0x02
srcmods   = 0xc0
```

For A/B/C/D in r0..r15 this computes the binary32 fused operation:

```text
D = fma(A, B, C)
```

The suite includes `(1+2^-23)*(1-2^-23)-1`: hardware returns `0xa8800000` (`-2^-46`), while a
separately rounded multiply followed by add would return zero.  Thus the recipe is genuinely fused,
not merely multiply-plus-add on easy inputs.

`srcmods=0xc0` accepts a directly preceding group of load-produced operands.  This is consistent
with the independently developed Apple9 scoreboard-slot model's slot-6 consumer mode, but this
experiment proves the fixed emitter value and does not by itself rename or fully decode the field.

## Source lifetime

The conservative constants above retain all three sources.  Optional post-read releases are:

- `op` bit 3 releases A;
- `op` bit 4 releases B;
- `ctrl_len` bit 7 releases C.

Destination publication follows the releases, so D wins when it aliases a released source.  All
eight release combinations and D==A/B/C are hardware-covered.  `op` bit 5 preserves the tested
FP32 arithmetic and register state, but its general role remains unknown; it is not called unused.

## Formal evidence

V3 captures `g17p_e0224_run03` and `g17p_e0224_run04` ran in canonical and shuffled orders.  Each
contains eight binding probes and 200 FMA cases:

- 198/198 positive cases matched the independent complete-state oracle in each run;
- both wrong-source/wrong-operation refuters fired in each run;
- dense D=r0..r15 and each A/B/C role independently at r0..r15;
- all source/destination aliases, lifecycle settings, and directly preceding load roles at gaps
  0, 1, and 4;
- signed, zero, and fused-rounding-sensitive arithmetic;
- 100 deterministic FMA DAGs of 2..64 operations;
- zero field-decode disagreements, whole-program aliases, leftover bytes, copied fields, carrier
  fields, faults, hangs, restarts, sentinel failures, or cross-run program/output differences;
- recovery count stayed 27689 throughout, with zero foreign runners in six quiet samples.

Verify the raw captures rather than trusting these totals:

```sh
python3 experiments/EXP-0224-falu3-canonical/analysis/verify224_v3.py
```

## The failed wide-source matrix and the compiler fallback

The original V2 formal run is retained as `g17p_e0224_run01`.  Its 136 low-source/lifecycle/DAG
positives were exact and its refuters fired, but 88 cases constructed around multiple r20--r22
operands were wrong.  P2 then isolated the boundary:

- every one of 48 A/B/C tests over r0..r15 was exact;
- single high operands r16..r23 were mixed rather than following one emitter rule;
- a 64-instruction gap did not generally repair them;
- three high operands failed at gaps 1, 16, and 64.

Therefore the initial backend must not guess the wide FMA source encoding.  `n3_mov` moves an
arbitrary r0..r63 value into an r0..r15 destination as two generated half-register moves, with an
exactly tested aliasing period of 64. Values in r16..r63 can therefore be staged into temporary low
registers before this FMA. Values in r64..r95 cannot: EXP-0230 proves their source descriptors alias
r0..r31. The compact move also cannot move this FMA's result out to r16..r95. A wider native form
or a tested memory-mediated transfer is still required for those paths. See `AMENDMENT-04.md`.

## Claim boundary

Proven: FP32 fused multiply-add, compact source/destination bank r0..r15, direct load and ALU
provenance, conservative retention and optional release, aliases, and long chains.

Not claimed: FP16 FMA; saturating/extended/source-modifier forms; non-default rounding, denormal,
NaN, or signed-zero policy beyond existing bounded experiments; a direct r16+ FMA operand recipe;
or a complete semantic map for every fixed bit.

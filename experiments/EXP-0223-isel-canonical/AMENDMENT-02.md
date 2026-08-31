# AMENDMENT-02 — generated R1 candidate from the own-MSL differential

Frozen after compiling/tokenizing `select_lt` and `select_gt`, before dispatching any instruction
using the candidate below.

## Own-source observation

Both 162-byte mains tokenize cleanly.  Each contains one ten-byte `isel10`; the two tokens differ
only in `cc`:

```text
select_gt: 92 01 07 03 02 04 06 c0 00 06
select_lt: 92 01 07 03 02 04 07 c0 00 06
```

The authored source keeps all four inputs live and the surrounding generated load/store sequence
locates them as r0=a, r1=b, r2=true, r3=false.  This nominates, without yet proving:

```text
dst             = D
cmpA            = (A << 1) | 1
opsel           = 0
cmpB            = (B << 1) | 1
cmp_mode        = 0x02
selTrue         = T << 1
cc              = 0x07 signed LT; 0x06 signed GT
flags           = 0xc0
selFalse_file   = 0
selFalse        = F << 1
```

The tokens are evidence only for nominating the formula.  No token or field byte is copied into a
program; every next instruction is assembled from the formula and tagged `RULE`.

## Frozen H4 hardware cases

- signed LT and GT, each with one true and one false input ordering;
- relocate D, A, B, T, and F independently over distinct r0..r14 values;
- keep all four sources live and require the complete r0..r23 state to remain unchanged;
- wrong compare source and wrong selected source controls must mismatch;
- alias D separately with A, B, T, and F, using read-before-write semantics.

An arithmetic match accompanied by a zeroed source is a lifecycle failure, not a pass.  If H4
computes correctly but releases a source, localize `flags` before promoting the recipe.  If H4
faults, the own-MSL token has a context/provenance dependency and the next sweep crosses the fixed
fields rather than changing register packing again.


# AMENDMENT-04 — flags L1 result and operand-provenance cross

Frozen after `g17p_e0223_flags01`, before any P1 dispatch.

## L1 result

All 512 generated encodings (256 flags values times two compare outcomes) were accepted, with no
faults, hangs, measurement failures, Gate-A disagreements, decoder aliases, donor fields, foreign
retries, or sentinel failures.  No setting changed the dumped values of A, B, T, or F when those
values came from `mov_imm`.

Within this exact signed-LT, low-GPR, `mov_imm`-seeded carrier, the observed destination obeys:

```text
if flags & 0x10:          D is not updated
else if (flags & 7) == 0: D = comparison ? T : F
else if flags & 4:        D = F
else:                     D = T
```

Bits 3 and 5..7 produced no additional observable difference in this carrier.  That is a bounded
null result, not an unused-bit claim.  In particular, the fresh own-MSL instruction used 0xc0 after
device loads, so source provenance is an immediate competing explanation for the high bits.

The byte's database name `flags` remains intentionally unrefined.  L1 establishes an emitter fact
(bit 4 must be clear for an ordinary write, low three bits must be zero to use the in-instruction
comparison) but does not yet identify the architectural names of the controls.

## P1: frozen provenance matrix

Sweep all 16 combinations of bits 3, 5, 6, and 7 with bits 0..2 and bit 4 clear.  For each setting
and each predicate polarity, run:

1. A, B, T, or F individually overwritten by a directly preceding `device_load`;
2. all four operands overwritten by loads, reordered so each of A, B, T, and F is the final load
   immediately before `isel10`.

This is 256 semantic cases.  Integer codewords are chosen so the compare outcome and selected value
remain independently visible.  The full r0..r23 dump must distinguish:

- wrong/stale selected result;
- a dropped or released compare operand;
- a dropped or released selected or unselected value;
- destination non-publication;
- collateral changes.

P1 is a measurement matrix, not a prediction that every high-bit setting works.  Partition its
outputs by the exact full-state signature.  A high bit may be called provenance/lifecycle-related
only if the loaded-source matrix distinguishes it reproducibly; equality in P1 remains bounded to
the tested load distances and low-GPR 32-bit form.

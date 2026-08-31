# AMENDMENT-03 — freeze H4 and isolate the `flags` byte

Frozen after `g17p_e0223_pilot02`, before any dispatch in L1.

## H4 result

The generated R1 formula from AMENDMENT-02 executed correctly in all nine positive cases:

- signed LT and GT, each true and false;
- an independent relocation of D, A, B, T, and F;
- D aliasing A, B, T, and F separately.

Every positive case matched the complete r0..r23 and three-buffer oracle.  Both deliberately wrong
host predictors mismatched.  The semantic cases had zero command faults, hangs, byte-ledger
disagreements, decoder aliases, donor fields, foreign retries, or sentinel failures.

This promotes the fixed `flags=0xc0` R1 point to a working generated pilot recipe for signed-i32
LT/GT select over the tested low registers.  It is not yet a formal two-run result, and the meaning
of the flags byte remains open.

## L1: dense flags-byte sweep

Hold every R1 field and operand fixed except `flags`; dispatch every value 0x00..0xff for both
predicate polarities:

```text
D=r0, A=r1, B=r2, T=r3, F=r4, cc=0x07 (signed LT)
true case:  A < B
false case: A > B
```

The destination prediction remains `T` or `F` according to the predicate.  The complete-state
capture deliberately does **not** predict the lifetime effects of non-canonical flags.  For each
value record:

- accepted, contained fault, hang, or measurement failure;
- selected result and any write outside D;
- post-instruction values of all four sources, including aliases/collateral changes;
- requested fields, actual emitted bytes, archive reread, and independent decode;
- sentinel, runner ownership, and recovery state.

Classify equal results only by the full observed state.  If changing a bit produces no difference
in this carrier, report only a bounded null observation; never call it unused.  A bit may depend on
source provenance, width, aliasing, condition result, or another context absent here.

## Frozen interpretation order

1. Partition the 256 values by fault/result/full source-state signature, separately for true and
   false predicates.
2. Test whether signatures factor into independent bit controls.  Do not infer independence merely
   from single-bit flips around 0xc0.
3. Use the smallest accepted signature that retains all four sources as the conservative compiler
   point; keep 0xc0 if no strictly better-understood point exists.
4. Pre-register any provenance, alias, or width cross needed to distinguish competing meanings
   before dispatching it.

L1 maps only this byte.  It makes no claim about `cmp_mode`, condition codes, source-file selection,
high-register reach, alternate widths, or folded/immediate forms.

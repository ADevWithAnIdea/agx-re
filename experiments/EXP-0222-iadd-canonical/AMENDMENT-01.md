# AMENDMENT-01 — source-release localization after the frozen H1/H2/H3 pilots

Frozen after `work/pilot/g17p_e0222_pilot01` and `pilot02`, before compiling the new authored
lifecycle-differential kernels and before the first lifecycle-field dispatch.

## Observations that force this amendment

- H1 factor-of-four selectors compute addition correctly.
- H1 subtraction computes `B - A`, not the registered `A - B`.
- H2 pair-style selectors compute the wrong values.
- H3, which swaps the two factor-of-four selectors, computes logical `A - B` correctly.
- In every factor-of-four case, both named source registers read zero after the instruction.
- The destination is nevertheless correct and immediately usable in the chained cases.

Therefore the arithmetic recipe is reparameterized as:

```text
logical ADD(A,B): srcB_ext=A<<2, srcB_imm=B<<2
logical SUB(A,B): srcB_ext=B<<2, srcB_imm=A<<2
```

The frozen H1 lifecycle hypothesis is refuted. The current fixed-field point is a destructive
read of both sources.

## Authored compiler differential, now permitted

The user allows looking at the machine code of our own freshly compiled Metal shader only after
multiple independent attempts fail. H1, H2 and H3 have now run and failed the complete contract.

Compile two new authored kernels:

- `add_dead`: compute and store `A+B`, with A and B dead afterward;
- `add_live`: compute and store `A+B`, then separately store A and B so both remain live.

The compiler output may nominate differing lifecycle bits. It does not establish their hardware
meaning and is not copied into the generated recipe. If allocation prevents a single-token
differential, record that and proceed with the hardware sweep below.

## Hardware localization hypotheses

The candidate controls are the fixed fields not used by the now-established arithmetic map:
`store_en`, `b2_bit0`, `b2_fmt`, `opmode`, `srcA`, `opc_tail`, and `opc_tail2`.

1. `store_en` controls destination publication, not source retention. Clearing it should preserve
   sources but lose or suppress the destination.
2. One or two bits in `opc_tail` / `opc_tail2` control source release independently, analogous to
   `falu2.opflags`.
3. If the compiler differential nominates other bits, test each singly before interactions.
4. A retain recipe must preserve both source registers, publish the correct destination, remain
   correct when destination aliases either source, and work in chains of at least 64 operations.

For every candidate value, the host predictor includes the destination and post-instruction source
state. A value that merely computes the right destination but releases a source is not a retain
recipe. A value whose only observation is a correct final store cannot assign lifecycle semantics.


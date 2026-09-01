# AMENDMENT-03 — freeze the low-register compiler envelope (V3)

Frozen after `g17p_e0224_pilot02`, before any V3 dispatch.

P2 executed 99 generated cases with zero faults, hangs, resets, Gate-A errors, aliases, donor
fields, or sentinel failures:

- all 48 low-register cases were exact: each source role A/B/C independently covered r0..r15;
- the 48 single-high-source cases were mixed (20 exact, 28 wrong across gaps 1 and 64);
- all three r20/r21/r22 cases were wrong at gaps 1, 16, and 64.

The mixed high behavior does not support an emitter rule.  In particular, a long gap is not a
general repair, so this is not merely a fixed latency.  The exact interaction among high operand
descriptors, load-result group membership, and the consumer slot remains an ISA-capability question.

V3 therefore promotes the complete compiler-safe envelope:

- FMA sources are r0..r15;
- FMA destination is r0..r15;
- a backend stages high-register values into the low bank with the already generated and validated
  `n3_mov` recipe before FMA, and may move the result out afterwards;
- all other V2 semantic, lifecycle, load-adjacency, fused-rounding, alias, refuter, and DAG cases
  remain unchanged.

This is full emittability, not a claim that the wider native operand encoding is understood.  The
high-source question remains explicitly open for capability completeness.

V3 has 200 cases: 198 exact positives and two required refuters.  Promotion requires two quiet
G17P runs in different orders with zero cross-run differences.

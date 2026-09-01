# AMENDMENT-02 — formal run01 failed; isolate the high-source boundary

Frozen after `g17p_e0224_run01`, before any P2 dispatch.  The failed formal run is retained in
full and is not eligible to pair with a later promotion run.

Run01 had zero faults, hangs, restarts, Gate-A errors, decoder aliases, donor fields, or sentinel
failures.  Its 224 V2 cases split exactly as follows:

- 136 exact: all aliases, numeric cases (including fused cancellation), lifecycle cases,
  load-adjacency cases, and all 100 FMA DAGs;
- 2 expected refuters fired;
- 88 unexpected wrong-value cases: the 16 destination cases and the 72 source-reach cases.

Every unexpected case used high registers r20--r22 for two or three operands.  No other class
failed.  This refutes the V2 matrix as a promotion suite; it does not refute the low-register H3
recipe.

P2 separates three hypotheses without consulting a fresh compiler token:

1. FMA works for every source role over r0..r15 when all other operands are also low.
2. A single high source r16..r23 works when the other operands are low.
3. If (2) depends on load completion rather than operand encoding, 64 independent instructions
   between the last load and FMA change the result relative to a one-instruction gap.

P2 tests all three source roles, all low and high registers, both gaps for high registers, and a
three-high-source case at gaps 1/16/64.  All cases retain the complete-state oracle.  Results stay
in `work/pilot`; a new formal matrix is frozen only after P2 identifies a safe envelope.

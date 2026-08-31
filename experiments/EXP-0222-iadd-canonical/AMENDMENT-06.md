# AMENDMENT-06 — freeze the promotion capture

Frozen after `work/pilot/g17p_e0222_pilot06`, before either `raw/` capture.

P1 passed 11/11 exact cases with no faults, hangs, collateral changes, byte-ledger mismatch, or
sentinel failure.  A directly preceding `device_load` may feed either physical source of R1 without
changing `opmode`, the source-descriptor low bits, or `srcA`.  This includes logical subtraction,
whose operands are physically reversed.  The same recipe works for sources and destinations
r16..r23, including r23 in the first body instruction after its prologue load.

## Frozen capture matrix

Both runs execute exactly these arms plus the independently measured S0 slot probe:

| arm | cases | purpose |
|---|---:|---|
| C0 | 2 | exact generated baseline plus a deliberately wrong first-source selector |
| V1 | 16 | retain/release, aliases, consumers, last-use chain, fixed 64-op DAG |
| P1 | 11 | direct/delayed load provenance and r16..r23 |
| CROSS | 28 | add/sub covering two disjoint seven-register plans |
| DAG | 100 | deterministic random 2..64-op DAGs, 50 per disjoint plan |

The two plans are `{r0..r6}` and `{r16..r22}`.  DAG seed is `0xA9170222`; the case matrix is
constructed deterministically before dispatch.  All arithmetic cases retain sources except the
explicit release cases in V1.  The complete r0..r23 state and all three buffers remain the oracle.

Run 1 uses canonical case order.  Run 2 uses shuffled order with seed 222.  Required per-case
agreement ignores run id, sequence, timing, and GPU time and compares generated-program SHA-256,
full output-buffer SHA-256, outcome, semantic mismatch counts, actual-byte ledger, and sentinel.

Promotion requires:

- every exact case matches and the wrong-selector control mismatches;
- Gate A reports zero bad fields and zero decoder aliases;
- every executed instruction field is generated (`COPIED=0`, `CARRIER=0`);
- no hang, measurement failure, foreign runner, or unexplained fault;
- both runs agree per case on program and complete output.

The harness SHA-256 frozen for these captures is
`18736ba92f7e5fb12ccbcd846a342a44afa4a7cdb727534550574245b9a5d983`.


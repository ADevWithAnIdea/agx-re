# AMENDMENT-08 — adaptive completion of C2

Frozen after intentionally stopping `g17p_e0223_mode01`, before any C2B dispatch.

## Why the randomized run was stopped

C2's invalid mode values take about 0.5 seconds each to return a contained command-buffer fault.
The shuffled run was designed before that cost was known.  At the stop checkpoint it contained
1,480 semantic dispatches and had already reached every one of the 256 finite values:

- all 192 values with `(cmp_mode & 3) != 2` faulted on 2..9 distinct integer/float relations;
- all 64 values with `(cmp_mode & 3) == 2` executed on 2..9 relations and never faulted;
- no requested/actual byte disagreement, decoder alias, donor field, foreign retry, or integrity
  failure occurred.

There was no mixed mode.  Continuing the original ordering would add hundreds of redundant
half-second faults without improving the finite structural partition.  The SSH interrupt initially
left the remote Python process orphaned; its exact validated PID and child were terminated, and the
final immutable partial capture was pulled at 1,480 semantic records.  It has no completion manifest
and must always be described as an intentionally stopped pilot.

## C2B completion

Dispatch all nine pre-registered relations for each of the 64 structurally accepted values:

```text
cmp_mode in 0x00..0xff where (cmp_mode & 3) == 2
```

This is 576 semantic cases.  Duplicating already sampled valid cases is intentional: C2B supplies
one complete, internally ordered truth-vector capture.  The partial C2 run supplies the exhaustive
fault boundary; C2B supplies the complete accepted-mode semantics.  No invalid mode is re-run in
C2B.

The original C2 interpretation rules and clean-room gates remain unchanged.  No additional Metal
shader has been compiled or inspected.

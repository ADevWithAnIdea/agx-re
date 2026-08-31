# AMENDMENT-04 — freeze the generated retain/release recipe

Frozen after `work/pilot/g17p_e0222_pilot03`, before dispatching the alias, consumer, and
multi-instruction validation cases below.

## L1 direct observations

All 32 combinations completed successfully.  Every combination produced `r0=41+42=83`; no
combination faulted, hung, changed a collateral register, or suppressed the destination.
Post-instruction source state depended only on `opc_tail` bits 1 and 2:

| `opc_tail` | bit 2 | bit 1 | first physical source | second physical source |
|---|---:|---:|---|---|
| `0x11` | 0 | 0 | retained | retained |
| `0x13` | 0 | 1 | retained | zeroed |
| `0x15` | 1 | 0 | zeroed | retained |
| `0x17` | 1 | 1 | zeroed | zeroed |

The pattern repeated identically for all eight combinations of `opmode` bit 0,
`srcB_ext` bit 0, and `srcA` bit 2.  This is a bounded null observation for those three bits in a
single add sourced by the generated `mov_imm` prologue.  It does not make them unused, optional in
all contexts, or safe to randomize.

The natural destructive control (`opmode=2`, source low bits clear, `opc_tail=0x17`) reproduced
pilot01/pilot02 exactly.  The compiler-live nominee retained both sources, but L1 shows that only
its `opc_tail=0x11` transition was necessary in this context.

## Revised generated recipe R1

Use the PRE_REGISTRATION fixed point with `opc_tail=0x11` to retain both operands.  The physical
arithmetic order is:

```text
ADD(A,B): first=A, second=B
SUB(A,B): first=B, second=A       # hardware result is second - first
```

For an operand whose SSA value has no later use, set the release bit belonging to its **physical**
source position:

```text
release first physical source  -> opc_tail |= 0x04
release second physical source -> opc_tail |= 0x02
```

Consequently a logical subtraction swaps both the register selectors and the association of
logical operand to release bit.  Conservatively use the exact generated fixed values
`opmode=2`, `srcB_ext=(reg<<2)` with low bits clear, and `srcA=0xa8`; L1's null results do not yet
license other values as canonical.

## Frozen validation V1

The following cases are predicted before dispatch by the host register interpreter:

1. retained add and logical subtraction with disjoint registers;
2. `D==A`, `D==B`, and `A==B` aliases, with sources read before destination write;
3. immediate destination consumption and repeated source consumption;
4. each of the four release patterns for add, plus logical-A-only and logical-B-only release for
   subtraction to prove physical association;
5. a 64-instruction deterministic integer DAG over r0..r14, with destination reuse and no source
   releases, followed by a complete r0..r23 dump;
6. a separate chain that releases values exactly on their computed last use.

For a released source that aliases the destination, the existing pilot predicts the destination
write wins over the source zeroing; V1 includes both alias directions as an explicit check.  Any
wrong destination, unexpected source state, collateral write, fault, or hang refutes R1 in that
context.  The natural `0x17` destructive point and wrong-selector case remain controls.


# AMENDMENT-10 — float compare/select and compare-source lifecycle

Frozen after `g17p_e0223_float_opsel01`, before any S1 dispatch.

## Float result

The generated wide select implements IEEE/GLSL-useful float predicates without another compiler
consultation:

| Predicate | `cmp_mode` | `cc` |
|---|---:|---:|
| ordered A > B | `0x02` | `0x02` |
| ordered A < B | `0x02` | `0x03` |
| ordered A == B | `0x06` | `0x00` |
| unordered A != B | `0x06` | `0x00`, swap T/F |

The discriminators include +1/+2, -2/-1, -1/-2, -0/+0, and NaN/+1.  Thus the result cannot be
explained by signed comparison of IEEE bit patterns.  Equality treats -0 and +0 equal and NaN
unequal.

Ordered float LE/GE must preserve NaN-false semantics.  Generate them as strict LT/GT OR equality
(two selects), not by blindly swapping T/F on the opposite strict relation; that inversion would
make NaN true.  Fast-math lowering may choose differently when NaNs are excluded.

## `opsel` lifecycle map

For the ten-byte member, these Gate-A-clean values have identical arithmetic and differ in source
lifetime:

| `opsel` | compare A | compare B |
|---:|---|---|
| `0` | retain | retain |
| `1` | release to zero | retain |
| `2` | retain | release to zero |
| `3` | release to zero | release to zero |
| `6` | retain | release to zero |
| `7` | release to zero | release to zero |

Release occurs after the read and is visible regardless of predicate outcome.  Use `opsel=0` for
the conservative compiler recipe; use 1/2/3 only with allocator-proven last uses.  The additional
meaning distinguishing 2 from 6 and 3 from 7 is a bounded null here, not unused space.

`opsel=4/5` decode as more-specific sibling descriptors (`isel8`/`isel_reg`) and fail the descriptor
uniqueness gate for this experiment.  Values 8..31 violate the frozen ten-byte walk boundary and
desynchronize the decoder; their apparent output is inadmissible.  This is an instruction-member/
length boundary, not evidence that those opcode values are unused.

## Current safe fused-select recipe

The same register packing, `flags=0xc0`, `opsel=0`, `selFalse_file=0`, and retained GPR source-class
works for integer and float strict/equality predicates.  `cmp_mode` bit 7 is independently the true
value's release control; keep it clear unless T is at last use.

## S1: false-operand descriptor high byte

The remaining four-source lifecycle question is the false value.  Hold the complete safe recipe
fixed and sweep `selFalse_file=0x00..0xff` for both true and false predicates (512 cases), with all
four sources uniquely `mov_imm`-seeded and the complete register state dumped.

For every value record full destination/source state, fault/length behavior, and integrity gates.
Classify source class, false-value release, predicate-dependent behavior, and no-write separately.
No observed effect may be called unused; load provenance and high-register crosses follow any
bounded null class.  The compiler does not depend on S1 for correctness—fixed zero already retains
F—but S1 is required for complete capability/lifecycle discovery.

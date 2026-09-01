# AMENDMENT-11 — false-source classes and formal recipe gate

Frozen after `g17p_e0223_falsefile01`, before V2 formal captures.

## S1 result

All 512 values/polarities execute with clean byte, decoder, provenance, ownership, and sentinel
gates.  The high three bits of `selFalse_file` select:

| high class | false value when selected | F after instruction |
|---:|---:|---:|
| `000` | GPR F | retained |
| `001` | `0x0001d500` at fixed descriptor `0x08` | retained |
| `010` | zero | retained |
| `011` | zero | retained |
| `100` | GPR F | released to zero |
| `101` | zero | retained |
| `110` | zero | retained |
| `111` | zero | retained |

Class 100 releases F even when the predicate selects T.  The low five bits produce no observable
difference across either predicate outcome with mov-seeded sources.  That is a bounded open meaning,
not an unused-bit claim; keep them zero in the compiler recipe.

The four-source lifecycle controls are now localized:

- compare A/B: `opsel` low bits;
- true value T: `cmp_mode` high class 100;
- false value F: `selFalse_file` high class 100;
- load-produced operand availability: `flags` high mode 110.

## V2 formal gate

The discovery pilots are not yet the two-run promotion gate.  Freeze a formal no-donor suite with:

- exact integer UGT/ULT/SGT/SLT/EQ/NE recipes and float GT/LT/EQ, including signed/unsigned and
  negative-float/signed-zero/NaN discriminators;
- all compare/T/F release combinations required by the published lifecycle map;
- all destination alias positions under the conservative retained recipe;
- load-produced A/B/T/F in every final-load position with `flags=0xc0`;
- cross-register sources over r0..r23 and destinations r0..r15;
- at least 100 deterministic random 2..64-op signed-LT select/add DAGs per run, checked against a
  host-computed complete-state oracle;
- wrong-source and wrong-condition refuters;
- two clean G17P runs in different orders, with program/output hashes compared by case.

Formal compiler-safe constants are `opsel=0`, relational/equality `cmp_mode=0x02/0x06`,
`flags=0xc0`, and `selFalse_file=0`.  Optimized release forms may be promoted only where V2 exercises
their complete-state effects.  Alternate source classes and the bounded-null sub-bits stay outside
the compiler claim.

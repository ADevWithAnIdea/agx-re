# EXP-0228 Amendment 01 — full selector-0/1 class

Frozen after `g17p_e0228_pilot01` and before either formal run.

## Pilot result

All 22 selected byte+2 values completed with `status=OK` and uniquely inferred
length `[4]`. This includes upper-mode endpoints 0 and 31 for both selectors.
The compiler-observed points, EXP-0227 controls, and off-natural points agreed.
The wrong r6 host model was rejected. There were 24 quiet samples, zero foreign
runner, zero hangs, and zero recovery-count delta.

## Formal expansion

`run228_full.py` tests all 64 byte values satisfying `byte2 & 7 in {0,1}`:

```text
byte2 = (mode << 3) | selector
mode = 0..31
selector = 0 or 1
```

Every candidate remains `09 01 byte2 05`, followed by the r6 boundary marker
and the unchanged staircase. One duplicate-byte `0x20` wrong-model control is
added, for 65 non-slot cases and 73 total dispatches per run.

Formal captures:

| run | order | seed |
|---|---|---:|
| `g17p_e0228_run01` | canonical | 0 |
| `g17p_e0228_run02` | reverse | 1 |

## Acceptance

The frozen `analysis/formal228.py` must prove:

- all 64 distinct byte+2 values are present exactly once in each run;
- every one completes `OK`, uniquely infers `[4]`, executes every marker, keeps
  sentinel/poison integrity, has clean Gate A, and has zero donor fields;
- the wrong-model control is rejected;
- orders are exact reversals;
- generated program, all three complete output hashes, outcomes, and marker
  observations agree by case across runs;
- slot mapping reproduces; no restarts, foreign retries, stray writes, foreign
  runner, busy pre/post state, recovery delta, or target mismatch occurs;
- at least two measured quiet samples exist in each run.

Any status fault/hang or lost post marker is recorded, not reinterpreted. Device
unresponsiveness triggers the plan hard stop without recovery.

Passing validates the exact four-byte length rule for the full byte+2 selector
0/1 space at fixed `byte0=0x09`, `byte1=0x01`, `byte3=0x05`. Destination-nibble,
source/operand, alignment, and arbitrary adjacency generalization remain later
Step 1 work.

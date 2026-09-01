# EXP-0230 — RESULTS

Status: **strong partial; formal gate correctly remains red**.

## Headline

With r0..r95 independently seeded, `n3_mov`'s eight-bit source/half descriptor has an effective
**period of 128 descriptor values / 64 GPRs**. The pre-registered `mod64` model is the unique model
with zero destination mismatches. The apparent period-64 result in EXP-0174 was therefore not just
a small-carrier artefact.

This experiment does **not** close the complete r0..r127 row. Its seed/readiness witness failed for
S=92..95 in both register plans, so the frozen contract excludes those 16 source×half×plan cases
from semantic promotion even though their destination values also match `mod64`. A narrow successor
must materialize r92..r95 independently and rerun those encodings.

## Formal capture

Target: Apple A18 Pro / G17P, Metal family Apple9.

| | run01 canonical | run02 reverse |
|---|---:|---:|
| total dispatches | 522 | 522 |
| main reach cases | 512 | 512 |
| wrong-oracle controls | 2 | 2 |
| hangs/faults/victims | 0 | 0 |
| quiet samples | 47 | 49 |
| foreign runners | 0 | 0 |
| recovery-count delta | 0 | 0 |

Gate A passed for every main case: 256 distinct source-descriptor byte values under each of the two
index/readback plans, zero requested/actual field disagreements, zero descriptor aliases, and zero
cross-run program/ledger disagreements. Every program records `COPIED=0`, `CARRIER=0`. Both
wrong-oracle controls fired in both runs.

`analysis/formal230.py` reports:

```text
main cases seen                 512
byte-ledger disagreements        0
Gate-A failures                  0
donor failures                   0
selected model               mod64
model mismatches:
  full96_zero_oob              240
  mod64                          0
  low64_zero_high              236
  mod96                         240
semantically undecidable        16
full formal pass             false
```

The red result is deliberate evidence discipline, not a reset of the 496 decidable rows.

## Bounded semantic result

For every case that passed its source seed witness:

```text
byte0 = (D << 4) | 3
byte1 = (S << 1) | hs
byte2 = 1
byte3 = 0

r[D].lo = r[S mod 64].half(hs)
```

- S=0..63 directly reads r0..r63, both low and high halves.
- S=64..91 reads r0..r27 respectively, not the distinct live r64..r91 values.
- S=96..127 reads r32..r63 respectively, without a fault, hang, or silent zero.
- S=92..95 produced the r28..r31 values predicted by the same rule in both runs, but those rows
  remain formally unpromoted because their independent high-register seed witnesses failed.
- The destination is restricted by this form's four-bit nibble to r0..r15; this experiment held
  it to r2/r3 and does not re-probe destination reach already covered by EXP-0174.

Thus source bit 6 is not a distinct high-register address bit in this instruction form. The exact
finite-field transition is S=63 (last direct source) to S=64 (first modulo-64 alias); all 128 source
codes execute. This result says nothing yet about wider move encodings or memory-mediated transfer
paths to r64..r95.

## Why 16 rows are excluded

The 16 excluded names are both halves of S=92..95 under index plans r14 and r15. Their pre-source
stores usually read zero and three varied across run order, while the `n3_mov` destination itself
was stable and always matched the lower alias. This is a producer/publication failure in the test
carrier, not evidence that r92..r95 do not exist: EXP-0221 independently stored live values from
those registers. The frozen rule says a failed seed witness cannot advance move semantics, so no
post-hoc exception is made.

## Reproduction and evidence

```sh
python3 analysis/formal230.py raw/g17p_e0230_run01 raw/g17p_e0230_run02
```

The command intentionally exits nonzero until the narrow successor closes the 16 excluded rows.
Raw observations are in the two named `raw/` directories; the complete derived result is
`analysis/formal_result.json`.

Clean-room provenance: **OWN-SHADER + HW-PROBE**. Inputs inspected: our authored carrier, generated
programs, complete output records, and public Metal API status. Apple binary introspection:
**NONE**.

# EXP-0230 — RESULTS

Status: **source-register reach closed by the broad pair plus Amendment 02**.

## Headline

With r0..r95 independently seeded, `n3_mov`'s eight-bit source/half descriptor has an effective
**period of 128 descriptor values / 64 GPRs**. The pre-registered `mod64` model is the unique model
with zero destination mismatches. The apparent period-64 result in EXP-0174 was therefore not just
a small-carrier artefact.

The original broad pair did not close S=92..95 because its seed/readiness witness failed for those
16 source×half×plan cases. Amendment 02 independently materialized the high source and its lower
rival and closed exactly those missing rows without rerunning the 496 rows whose gates had passed.

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

The red broad result is deliberate evidence discipline, not a reset of the 496 decidable rows.

## Amendment 02 closure

The focused run03/run04 pair contains S=92..95 × both halves × both plans plus two controls:

| | run03 canonical | run04 reverse |
|---|---:|---:|
| total dispatches | 26 | 26 |
| focused main cases | 16 | 16 |
| controls | 2 | 2 |
| seed/Gate-A/donor/cross-run failures | 0 | 0 |
| quiet samples / foreign runners | 22 / 0 | 22 / 0 |
| recovery-count delta | 0 | 0 |

Every high source and lower rival carried its distinct expected codeword. `mod64` matched all 32
formal run-records; `direct96` and `zero` each mismatched all 32. Both wrong-source controls fired.
`analysis/formal230_r2.py` passes, and `analysis/combined230.py` verifies that its 16 rows are exactly
the broad run's excluded set. The aggregate source-reach result is green.

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
- S=92..95 reads r28..r31 respectively even while r92..r95 hold different, independently observed
  codewords; Amendment 02 proves both halves under both register plans.
- The destination is restricted by this form's four-bit nibble to r0..r15; this experiment held
  it to r2/r3 and does not re-probe destination reach already covered by EXP-0174.

Thus source bit 6 is not a distinct high-register address bit in this instruction form. The exact
finite-field transition is S=63 (last direct source) to S=64 (first modulo-64 alias); all 128 source
codes execute. This result says nothing yet about wider move encodings or memory-mediated transfer
paths to r64..r95.

## Why the broad pair excluded 16 rows

The 16 excluded names are both halves of S=92..95 under index plans r14 and r15. Their pre-source
stores usually read zero and three varied across run order, while the `n3_mov` destination itself
was stable and always matched the lower alias. This is a producer/publication failure in the test
carrier, not evidence that r92..r95 do not exist: EXP-0221 independently stored live values from
those registers. The frozen rule says a failed seed witness cannot advance move semantics, so no
post-hoc exception was made. Amendment 02 used the already-proven load-forwarding store path to
materialize only those sources, then passed a separately frozen formal gate.

## Reproduction and evidence

```sh
python3 analysis/formal230.py raw/g17p_e0230_run01 raw/g17p_e0230_run02
python3 analysis/formal230_r2.py raw/g17p_e0230_run03 raw/g17p_e0230_run04
python3 analysis/combined230.py
```

The first command intentionally remains red because raw evidence is immutable and its original
carrier did not pass 16 seed witnesses. The focused and combined commands pass. Raw observations
are in the four named `raw/` directories; derived reports are `formal_result.json`,
`formal_r2_result.json`, and `combined_result.json`.

Clean-room provenance: **OWN-SHADER + HW-PROBE**. Inputs inspected: our authored carrier, generated
programs, complete output records, and public Metal API status. Apple binary introspection:
**NONE**.

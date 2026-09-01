# EXP-0224 — generated FP32 FMA recipe

Result: a no-donor compiler recipe for NIR `ffma` is proven over the r0..r15 FMA bank, with
bounded `n3_mov` staging for values held in r16..r63. Physical r64..r95 are outside that move
form's direct source set. See `RESULTS.md` and `AMENDMENT-04.md`.

Read `PRE_REGISTRATION.md` before running the harness.

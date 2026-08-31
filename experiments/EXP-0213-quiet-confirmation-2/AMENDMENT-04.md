# EXP-0213 — AMENDMENT-04

**Frozen after HEALTH GATE 2 passed and before the probe it defines. Not Gate E evidence.**

## What is added

One bounded capture, `g17p_e0213_T1_cl_atomic_threshold`: EXP-0206's own unedited `run.py` on
`--carriers cl_atomic --only ret_luse.linkmode`, under a **900 s** external cap — one quarter
of stage 6B's, deliberately short.

## Why

Stage 6B measured a **hang-cascade threshold**: on `if_push.scope@cf_nl2._agc.main+106` the
first 40 values reproduce the busy machine's ok/not-ok partition exactly, and from value 40 on
**everything** hangs. That is the single most useful thing stage 6B produced, and it rests on
**one arm of one carrier**. This probe asks whether the threshold generalises to a structurally
different arm family (`ret_luse.linkmode`, a return-instruction field on a call carrier, whose
hazard rule on the busy machine is `(v & 7) ∈ {4,5}` rather than `(v & 2) == 0`).

It is **not** an attempt to reach stage 6C. 6C stays **NOT REACHED**: its arms carry ~64
expected hangs each, three times the measured ~20-hang cascade onset, so a clean sweep is not
obtainable from the frozen harness at any budget. This probe deliberately stops long before
that point.

## Rules it inherits and adds

* It runs only because HEALTH GATE 2 (AMENDMENT-03) **passed**.
* The 900 s cap is enforced by `drive_cap.sh`, which kills the whole capture (AMENDMENT-01).
* The capture is expected to leave the device degraded for several minutes; that is now a
  measured, documented recovery path (~8 min, 3 driver-initiated device resets), and a health
  gate must pass again before **any** later capture.
* Its records past the cascade onset are **cascade-contaminated by construction** and are
  reported as such, never as hardware outcomes for those values.

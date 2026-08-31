# EXP-0213 — AMENDMENT-05

**Frozen before the re-capture it defines. Retracts a decision, not a measurement.**

## What changed, and why — I stopped stage 6C on a premise the next measurement refuted

At 00:56Z I stopped stage 6C, reasoning from stage 6B that its arms carry ~64 expected hangs
each, "more than the measured ~20-hang cascade threshold, so a clean sweep is impossible with
the frozen harness." The AMENDMENT-04 threshold probe was run to generalise that threshold to
a second arm family. **It refuted the premise.**

`g17p_e0213_T1_cl_atomic_threshold`, on a healthy device, quiet, 900 s cap:

* **149 consecutive values, 37 hangs, NO cascade.** The outcome pattern is periodic mod 8 from
  value 0 to value 148 without a single deviation: `ok` at `(v & 7) ∈ {2,6}`, `hang` at
  `(v & 7) ∈ {4,5}`, `fault` at `(v & 7) ∈ {0,1,3,7}`.
* **149 / 149 ok/not-ok partition agreement with the committed busy `run03`.**
* `recoveryCount` **22871 → 23096**: 225 device resets, about six per hang, and the device
  recovered from every one.

Compare stage 6B's `if_push.scope@cf_nl2._agc.main+106`: 122 hangs and `recoveryCount`
**frozen at 22868 throughout** — not one reset in 4509 s. **There are two hang classes.** One
the driver recognises and recovers from, which is survivable and repeatable indefinitely; one
it does not, which accumulates until every dispatch on that carrier hangs and whose degraded
state outlives the process by ~8 minutes.

Stage 6C's arms are in the **recoverable** class. My stop was therefore correct for the
*device state at the time* — `L1_cl_atomic` could not even open its carrier, which is a
`measurement_failure` caused by stage 6B's residue — and wrong as a general claim about 6C.

## What is added

Stage 6C is re-captured under **new run ids** (`g17p_e0213_L3_*` / `L4_*`), pair-first, after
a passing health gate, at the budget already frozen for it (80 hangs / 2100 s per capture).
The measured cost from T1 makes that budget adequate: 64 hangs × ~24 s ≈ 1540 s, plus ~190
fast values, ≈ 1600 s.

`g17p_e0213_L1_cl_atomic` is **retained exactly as taken**, never topped up, never reused, and
supports no verdict — its `carrier_open` is recorded as `hang`, which is the evidence that the
device, not the encoding, failed.

## What this does NOT do

It does not revive stage 6B, which stays NOT REACHED for the reason stage 6B itself measured.
It changes no pair designation, no budget, no exclusion, no agreement key and no verdict
already computed.

# EXP-0210 — AMENDMENT 03, frozen 2026-08-30 before its first dispatch

**Trigger, and it is a defect in MY OWN frozen criterion.** During EXP-0202's first quiet
capture (`g17p_quiet01`, retained, never reused) the `AGXAcceleratorG17P` `recoveryCount`
rose from **12977 to 13752 — 775 device resets in ~7 minutes** — while Q1 measured **zero**
foreign dispatch runners and Q3 measured **no** foreign submitter. The machine was quiet.
**We were resetting the device ourselves**, from our own pre-registered faulting encodings:
at the same moment the run had logged **258 `fault` outcomes**, and EXP-0202's own frozen
contract expects faults in the `(v & 7) == 7` and `ctrl` length-selector regions.

`PRE_REGISTRATION.md` froze Q2 as "`recoveryCount` unchanged from first to last sample", with
the stated rationale "a device reset is exactly what manufactures `InnocentVictim` and hang
cascades **in a neighbour's** capture". The letter and the rationale diverge for a sweep that
faults by design: **as written, Q2 can never be satisfied by any fault-heavy experiment, no
matter how quiet the machine is.** That is a gate that cannot come out the other way — the
same failure class as DEF-0190-1 (an inertness verdict that cannot fail) and the
`moved >= 2*max(disagree,1)` width-1 trap, both of which this corpus found the hard way.

**The refutation stands and is reported.** `PRE_REGISTRATION.md` §2 refuter R1 lists "a
`recoveryCount` increase across a capture" as making a pair NOT MET. `EXP-0202`'s
`g17p_quiet01` therefore **fails Q2 as frozen**, is retained exactly as captured, is never
topped up or reused, and supports **no** Gate E verdict. It is reported as a refuted capture,
not quietly rescored.

## What changes

Q2 splits, and the *attribution* becomes the criterion rather than the raw count:

| | criterion | |
|---|---|---|
| **Q2a** (gating) | no device reset attributable to a **foreign** context | With Q1 = 0 foreign dispatch runners and Q3 = no foreign submitter in **every** sample of the capture, there is no other GPU client that could have caused a reset. Q2a therefore **passes only when Q1 and Q3 pass**, and it fails outright if either does. |
| **Q2b** (reported, not gating) | `recoveryCount` delta over the capture, and the run's own `fault`/`hang`/`InnocentVictim` counts | A reset from our own context still kills our own in-flight command buffers. So the cascade question is answered where it belongs — **in the pair's raw**: hard outcomes counted separately from payload agreement, `InnocentVictim` counted per run, and the two runs compared in opposite case order by `analysis/pairwise.py`. |

Gate E's actual words are "**no victim/cascade evidence**", not "no resets". Q2b is how that
is now tested: if our own resets were corrupting the measurement, the two opposite-order runs
would disagree on the affected cases. Agreement over a fault-heavy sweep in reversed order is
evidence *against* cascade contamination; a large hard-outcome disagreement would be evidence
for it, and would fail the pair.

**Q1, Q1b, Q3 and Q4 are unchanged.**

## Finding this hands to the orchestrator, independent of any gate

**One EXP-0202 capture produced 775 device resets in about seven minutes on an otherwise idle
machine.** Every one of those resets discards in-flight command buffers in *other* contexts —
that is the documented recovery behaviour and it is the mechanism behind
`kIOGPUCommandBufferCallbackErrorInnocentVictim`. This experiment did not sample
`recoveryCount` during the 2026-08-30 fan-out and so cannot attribute the wave's
contamination retrospectively; but it can say that **this family of sweeps is, by itself, a
large reset source**, which is a concrete reason the concurrent wave saw victim streaks.

## What this amendment may NOT do

It may not be applied to data already seen. `EXP-0202/raw/g17p_quiet01` (partial, deliberately
stopped) and `EXP-0210/raw/e0202_q01` are retained exactly as captured, are **not** re-scored
under Q2a, and support no verdict. EXP-0202's pair is re-dispatched under new run ids.
`EXP-0203`'s and `EXP-0205`'s already-verdicted pairs measured `recoveryCount` **unchanged**
and so pass Q2 under both the frozen and the amended wording; they are not re-dispatched.

Frozen before the first dispatch that uses it.

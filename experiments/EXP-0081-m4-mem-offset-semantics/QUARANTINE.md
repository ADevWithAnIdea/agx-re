# EXP-0081 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** (2026-08-28). Terminal disposition
recorded by the orchestrator after completing the contracted post-capture
sequence the interrupted agent never reached.

## What happened

MEM-01..MEM-05 splice experiment; successor to EXP-0080. Both contracted
capture runs completed (`raw/m4-20260828-run01`, `raw/m4-20260828-run02`,
2164 cases each). The agent was killed by an API usage limit in the
`RUN02_PRESENT` state, before running `post_second_run_sequence`. The
orchestrator then ran exactly that frozen sequence (no repair, no edit):

- `verify.py --selftest` **PASS 20/20**
- `verify.py --seqtest` **PASS 14/14** (contracted order walkable end to end)
- `analysis.py --run-a ... --run-b ... --write` → **ANALYSIS GATE: FAIL**
  (`issues: ["runs are not byte-identical"]`, plus 3 hand-set divergences)

## Why it cannot be promoted — a NEW contract-bug class

The contract's `cross_run_provenance_gate` requires **byte-identical results
files**, but the recorded per-case payload embeds `GPUTIME_NS` (inside
`stdout`) and `duration_ms`. GPU timing is inherently nondeterministic, so the
gate is **unsatisfiable by construction** — no pair of runs can ever pass it.

This is the fourth distinct frozen-contract defect class in this series, after
receipt-schema contradiction (EXP-0073), payload truncation (EXP-0072), and
gate-order contradiction (EXP-0075):

> **A byte-exactness gate must never be applied to a record containing
> nondeterministic fields (timing, durations, addresses, pids). Timing belongs
> outside the compared payload.**

Post-capture repair of `analysis.py`/`run.py` is forbidden by the
`00_inputs.json` hash binding, so no repair was attempted.

## What the data shows (characterization only — NOT promoted)

For the record, and to scope the successor: an orchestrator-side comparison of
the semantic payload only (`OUT`/`RESULT`/`STATUS`/`MAIN_LEN`/`FUNCTION`/
`PIPELINE_SOURCE`/`DEVICE` lines, timing excluded) found **0 divergences across
all 2164 paired cases**, and both runs record the identical deterministic
command-buffer errors (`ld_idxreg_r0x7f`, `ld_idxreg_r0xff`). The observations
therefore appear reproducible — but they are **not evidence**: the contracted
promotion gate is unmet, and this ad-hoc comparison is not the frozen check.
Treat every EXP-0081 observation as a hypothesis for the successor to
re-register and falsify.

## Successor

**EXP-0082-m4-mem-offset-semantics** — identical matrix, kernels and splice
form; the only changes: (1) move `GPUTIME_NS`/`duration_ms` out of the
byte-compared payload into a separate non-gated timing record; (2) make the
cross-run gate compare the semantic payload exactly; (3) add a selftest fixture
proving the cross-run gate PASSES for two runs differing only in timing and
FAILS on any semantic difference. EXP-0081's hand-set expectation divergences
(`ld_scale1_code1`, `ld_scale1_code2`) must be re-registered as
hypotheses-to-falsify, not as expectations.

```text
Clean-room status: quarantined process history; no MEM-01..05 claim
Apple binary/code/archive/BO inspection: NONE (own compiled kernels only)
Raw retention: append-only, non-evidence (two runs, gate unmet)
Successor: EXP-0082-m4-mem-offset-semantics
```

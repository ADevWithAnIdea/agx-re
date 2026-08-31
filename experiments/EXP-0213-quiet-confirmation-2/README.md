# EXP-0213 — quiet confirmation, part 2: the five Gate E rows EXP-0210 could not reach

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, `Mac17,5`, Metal family Apple9, `192.168.170.254`).

```text
Clean-room provenance: HW-PROBE -- re-running our OWN committed harnesses over shaders
                       compiled from our OWN MSL -- plus black-box IOKit registry PROPERTY
                       reads for the quiet measurement.
Inputs inspected:      this repository's own committed harnesses, kernels and raw; IOKit
                       registry property VALUES published by the driver (data, not code).
Apple binary introspection: NONE.
```

## The question

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate E requires **two clean G17P runs in reversed or
shuffled case order, with identical actual-byte ledgers and no victim/cascade evidence**, on a
machine that is **measured** quiet rather than assumed quiet. EXP-0210 met that for 17 of 22
named fields. It could not reach five things, and both failures were caused by one measured
hardware fact — **a quiet GPU fails harder**:

| left open | why |
|---|---|
| `tex_sample.mode`, `tex_write.amode`, `tex_write.rsv11` (EXP-0204) | both captures were stopped by EXP-0204's **own** cascade guard when `tex_write@twdyn` stopped reproducing its baseline; the pair covered 5055 of 9276 keys |
| `tex_deriv.dstsrc` (EXP-0204) | the frozen 8-hang-per-field budget is exhausted six times sooner on a quiet machine; the pair shared 216 keys |
| `cf_nl2`, `cl_atomic`, `cl_leaf`, `cl_chain` (EXP-0206) | those encodings **hang** on a quiet machine where they faulted on a busy one; the sweep rate collapsed from ~4.8 to ~0.2 cases/s |

## Method, in one paragraph

Each source experiment's **own committed harness and frozen contract are run unchanged**; only
the run id, the harness's own selectors (`--arms` / `--mnem` / `--carriers` / `--only`) and the
harness's own `--order` differ. The single design change is **where the harness is invoked
from**, not what it is: EXP-0204's `run.py` aborts the *whole arm loop* on a cascade, so it is
invoked **once per arm** through its own `--arms` selector, which confines an abort to the arm
that caused it. Every capture is wrapped in a measured quiet window (2 s sampling of the
process table plus the driver's own `recoveryCount`, `fLastSubmissionPID` and `fBusyCount`),
and the device reset counter is snapshotted immediately before and after every capture. Hang
budgets and hazard-family exclusions are **declared in `PRE_REGISTRATION.md` before the first
dispatch**, with exact numerators and denominators reported afterwards.

## Commands

```sh
export SSHPASS='...'                       # never written to any file
python3 harness/verify_repo_eq_neo.py ../EXP-0204-g17p-tex-carrier-dimensions agxre/EXP-0204
python3 harness/verify_repo_eq_neo.py ../EXP-0206-g17p-cf-scope             agxre/EXP-0206
python3 harness/drive.py work/plan_phase1.json      # EXP-0204 tex_*, 22 arms x 3 orders
python3 harness/drive.py work/plan_phase2.json      # EXP-0204 whole 22-arm set, 2 orders
python3 harness/drive.py work/plan_phase3.json      # EXP-0204 tex_deriv, 4 orders
python3 harness/drive.py work/plan_phase4a.json     # EXP-0206 stage 6A
python3 harness/drive.py work/plan_phase4b.json     # EXP-0206 stage 6B (capped; NOT REACHED)
python3 harness/drive.py work/plan_phase4c.json     # EXP-0206 stage 6C, first attempt (stopped)
python3 harness/drive.py work/plan_phase5.json      # characterisation, NOT Gate E evidence
python3 harness/drive.py work/plan_health{1,2,3}.json   # device-health gate (AMENDMENT-03)
python3 harness/health_gate.py <probe run dir>          # its verdict; exit 0 iff PASS
python3 harness/drive.py work/plan_threshold.json   # cascade-threshold probe (AMENDMENT-04)
python3 harness/drive.py work/plan_phase6c2.json    # stage 6C re-capture (AMENDMENT-05)
python3 harness/drive.py work/plan_phase6.json      # cold-device refuter (AMENDMENT-02)
python3 analysis/concat.py '<raw glob>' analysis/out/<name>.jsonl
python3 analysis/pairwise.py  <A.jsonl> <B.jsonl>
python3 analysis/per_field.py <A.jsonl> <B.jsonl>
python3 analysis/stability.py <field> <run1.jsonl> ... <runN.jsonl>
python3 analysis/arm_agreement.py <A.jsonl> <B.jsonl>       # hard outcomes not hidden
python3 analysis/hazard_map.py <arm> <run1.jsonl> ...       # ok/not-ok partition vs severity
python3 analysis/quiet_table.py                             # one row per capture
python3 analysis/gate_e_summary.py                          # recompute the headline numbers
python3 analysis/verify_pulls.py                            # every pulled file == the neo's
python3 analysis/e0206_scorer/verdicts206.py <run dirs...>  # EXP-0206's OWN scorer, byte-identical copy
```

## Layout

```
PRE_REGISTRATION.md   frozen before the first dispatch
CAPTURE_CONTRACT.json frozen hashes, budgets, exclusions, Gate E pair designations
AMENDMENT-01.md       adds a process-group wall-clock cap (frozen before stage 6A)
AMENDMENT-02.md       adds the cold-device refuter (phase 6); NOT Gate E evidence
AMENDMENT-03.md       adds a device-health gate after stage 6B degraded the device
AMENDMENT-04.md       adds a bounded cascade-threshold probe on a second carrier
AMENDMENT-05.md       re-captures stage 6C under new ids after that probe refuted the
                        premise on which stage 6C had been stopped
harness/              quiet sampler + gate, device counter snapshot, capture drivers, pullers
analysis/             comparators (pairwise/per_field/stability) and derived out/
raw/<tag>/            per-capture quiet samples, device counters, capture log, quiet verdict
work/                 plans, driver log, scratch (NOT evidence)
RESULTS.md            observation vs interpretation, per-field Gate E verdicts
```

The captures themselves live in each **source** experiment's own `raw/` tree under new
`g17p_e0213_*` run ids, pulled back one directory at a time. Nothing existing was edited.

## What this experiment does NOT do

It does not edit any label, `tools/agx-isa/`, `docs/`, `PROVENANCE.md`, any source
experiment's harness or contract, or any existing raw directory, and it commits nothing.
It re-runs **Gate E only**: Gates A, B, C and D are inherited from each source experiment and
are not re-audited here.

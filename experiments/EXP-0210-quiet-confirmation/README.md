# EXP-0210 — the quiet window: serialized Gate E confirmation for the 2026-08-30 G17P wave

**Target:** Apple A18 Pro / G17P, `192.168.170.254`, `AGXAcceleratorG17P`, `applegpu_g17p`,
5 GPU cores, macOS 26.6 (25G5043d), `Mac17,5`, Metal family Apple9.
**Clean-room provenance:** HW-PROBE (re-running our own committed harnesses) + black-box
IOKit property reads. **Apple binary introspection: NONE.**

## The question

Nine hardware experiments ran concurrently on 2026-08-30. Their Gates A, B and C passed to a
standard nothing in this corpus had previously reached, and **Gate E failed for almost all of
them** — because `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` says a confirmation run may not rely
on a busy machine, and the machine was never quiet. EXP-0204's dedicated quiet-window helper
took **86 samples and never once saw a quiet machine**, with up to **17** concurrent foreign
GPU processes.

The fan-out has now drained. This experiment asks one question, per field:

> Re-run the **same** confirmation captures, from each experiment's **own committed harness
> and frozen contract, unchanged**, strictly **one experiment at a time**, on a machine whose
> quietness is **measured**. Does Gate E now hold?

**It produces no new hypothesis and no new field claim.** No sweep is redesigned, widened or
narrowed; no case matrix is altered; no label, no file under `tools/agx-isa/`, `docs/` or
`PROVENANCE.md` is touched; no existing raw, contract or verdict file is edited. A
**NOT MET** verdict is a first-class outcome and is reported as one.

## Method

`PRE_REGISTRATION.md` (frozen at rev `1ea484d3c37dffc884cb12d92de597cbfefdc41b`, clean tree,
before the first dispatch) fixes the protocol; `AMENDMENT-01.md` and `AMENDMENT-02.md` are
two instrument corrections, each frozen **before** the dispatch that used it, each with the
superseded captures retained and explicitly **not** re-scored.

**Quiet is measured on four signals**, not asserted:

| | criterion | why it is independent |
|---|---|---|
| Q1 | `n_foreign_runner == 0` in every sample | the process class that contends for the GPU, faults, hangs, and makes a neighbour a victim |
| Q2 | `recoveryCount` unchanged first-to-last sample | the driver's cumulative **device-reset** counter — the event that manufactures `InnocentVictim` and hang cascades. Hardware-side; needs no process names |
| Q3 | `fLastSubmissionPID` never a PID outside our own session | a foreign submitter whose process name matches no pattern is invisible to Q1 and visible here |
| Q4 | sampler alive throughout (≥1 sample / 10 s) | a dead sampler cannot observe a busy machine |

Q1 reproduces the metric the fan-out itself recorded, so the numbers are directly comparable
with the busy measurements those experiments committed. `Device Utilization %` is recorded but
is **not** a criterion: it reads a constant 100 on this host with an idle GPU, zero submitters
and Renderer/Tiler at 0.

**Per capture:** push the source harness → verify remote hashes **as a separate step** → start
the sampler → run that experiment's own capture command with only a **new run id** changed →
stop the sampler → pull the new run into that experiment's own `raw/` → run that experiment's
own analysis. Capture *n+1* does not start until capture *n* is pulled. One experiment in
flight at any moment.

**Gate E is then computed three ways**, all of them from raw:

1. **identical actual-byte ledgers** — per-key `actual_bytes` from run A vs run B, plus each
   experiment's own `requested == decoded` counts;
2. **cross-run agreement keyed by (arm, value)** with volatile timing excluded
   (`analysis/pairwise.py`; the pooled-across-arms, `gputime_ns`-inclusive key is the known
   checker defect of EXP-0202 §3.1 and is not used);
3. **no victim/cascade evidence** — hard outcomes counted separately from payload agreement,
   `InnocentVictim` counted, and `recoveryCount` deltas from the quiet samples.

## Layout

```
PRE_REGISTRATION.md      frozen before the first dispatch
AMENDMENT-01.md          compiler-XPC attribution   (frozen before its first dispatch)
AMENDMENT-02.md          one-snapshot ownership     (frozen before its first dispatch)
RESULTS.md               per experiment, per field: Gate E MET / NOT MET, with the evidence
PROGRESS.md              append-only milestone log, including two self-disclosures
harness/quietsample.py   the quiet instrument (process table + IOKit properties)
harness/quietcheck.py    Q1..Q4 over one capture's samples
harness/drive_one.sh     runs ON the neo: sampler window strictly contains the capture
harness/capture.sh       one capture end-to-end, from the repo host
harness/neo.sh           ssh/scp with a hard alarm; SSHPASS env var only
harness/verify_repo_eq_neo.py   is the device running the COMMITTED code
harness/run_analysis.sh  run a source experiment's analysis without leaving its files modified
analysis/pairwise.py     Gate E pair comparison: ledger + (arm, value) agreement
analysis/out/            every comparison and every preserved generated verdict file
raw/<tag>/quiet.jsonl    append-only quiet samples, one directory per capture
```

The captures themselves land in each **source** experiment's own `raw/` under new run ids.
Nothing existing is touched.

## Reproduction

```sh
export SSHPASS='...'                       # SSHPASS only; never written to any file
sh harness/neo.sh sh 'mkdir -p ~/agxre/EXP-0210/samples'
sh harness/neo.sh put harness/quietsample.py harness/drive_one.sh user@$NEO:agxre/EXP-0210/
# then, ONE AT A TIME, per source experiment:
sh harness/capture.sh <tag> <sample_s> <alarm_s> '<that experiment's own capture command>'
python3 analysis/pairwise.py <A>/sweep.jsonl <B>/sweep.jsonl --label <...>
sh harness/run_analysis.sh <exp_dir> <tag> python3 analysis/verdicts.py raw/<A> raw/<B>
```

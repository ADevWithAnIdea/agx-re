# QUARANTINE -- m4-20260828-run01 (first attempt)

**Status: quarantined, retained untouched as append-only process history.** Not promoted
evidence. Per `experiments/SUBAGENT_BRIEF.md`: "never repair or rerun a quarantined
[capture] in place... a new run id" -- the corrected pair is `m4-20260828b-run01`/
`m4-20260828b-run02`.

## What happened

92/97 cases ran and matched their pre-registered expectation exactly. All 5
`regsplice_bias` cases failed with `STATUS PIPELINE_MISS` (`verdict: FAULT`).

## Root cause (own-code bug, not hardware)

`run.py`'s `build_regsplice_archives()` compiled the frozen archives via `harness/bin/shdump`
with **default fast-math (ON)**, but `run_regsplice_bias()`'s `harness/texrender --archive`
invocation passed `--no-fast-math` (inherited by copy-paste from the other five backends, which
correctly want fast-math off for their Inf/NaN sweeps). `texrender.m` recompiles the SAME source
in-process to obtain the `MTLFunction`'s AIR hash for archive pipeline-state lookup
(`MTLPipelineOptionFailOnBinaryArchiveMiss`); a fast-math mismatch between the archive-producing
compile and the identity-establishing compile changes the AIR hash, so the archive lookup
legitimately misses -- this is Metal behaving correctly given inconsistent compile options, not
a hardware fault or a splice-encoding problem.

## Why the other 92 cases are unaffected

Every other backend (`bias_sweep`, `grad_sweep`, `lodquery`, `cube_faceid`, `cube_grad`) compiles
directly from `--source` every time (no archive, no cross-compile hash matching needed), so this
mismatch class cannot occur there. Their results in this quarantined run are the SAME public-Metal
behavioral evidence the corrected run reproduces; they are superseded, not contradicted, by
`m4-20260828b-run01`.

## Fix applied for the successor

`run_regsplice_bias()`'s `texrender` invocation no longer passes `--no-fast-math`, matching
`build_regsplice_archives()`'s default-fast-math compile (both sides of this ONE backend now
agree; the other five backends are unaffected and keep `--no-fast-math`). The frozen splice
offset/native-byte values in `PRE_REGISTRATION.md` hypothesis 3 (`_agc.main`+69, A=0x06, B=0x08)
were themselves derived from a fast-math-ON pilot compile (PROGRESS.md T2), so they remain valid
unchanged -- only the harness invocation's flag mismatch needed correcting, not the pre-registered
values.

## Evidence retained

`quarantine-m4-20260828-run01/` (renamed from the raw `m4-20260828-run01/` capture; all 7 files
byte-for-byte as produced, including `04_results.jsonl` with the 5 `PIPELINE_MISS` lines and
`04_results_raw.jsonl` with the underlying stderr/Metal error text). Nothing here is edited.

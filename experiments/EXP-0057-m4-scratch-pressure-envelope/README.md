# EXP-0057: M4 public scratch-pressure envelope

> **QUARANTINED / NON-EVIDENCE — 2026-08-20.** Do not run, cite, promote, or
> derive a hardware claim from this experiment's live outputs. Independent audit
> found that `harness/metadata.py` opened a temporary pipeline archive as bytes
> and generically walked GPU images/Mach-O containers before selecting metadata.
> That exceeds this experiment's frozen metadata-only boundary. The retained
> records also lack full output/guard readbacks and a complete run-time
> environment/revision record. `raw/` is preserved append-only for process
> traceability only. A new experiment requires a fresh preregistration and an
> independently reviewed metadata-free or strictly bounded design.

This is a deliberately narrow P0.1 follow-up to EXP-0041. It uses only
complete authored MSL, public Metal APIs, its own pipeline metadata fields, and
its own guarded output buffers. It probes whether ordinary M4 Metal execution
accepts a bounded ladder of compiler-declared per-thread scratch sizes at two
threadgroup shapes. See `PRE_REGISTRATION.md` for the frozen question, safety
limits, and exclusions.

## Reproduce

Run IDs are append-only. The first run must complete its artifact checks before
starting the independent second run.

```sh
python3 -B experiments/EXP-0057-m4-scratch-pressure-envelope/run.py --run-id NEW_RUN01
python3 -B experiments/EXP-0057-m4-scratch-pressure-envelope/run.py --run-id NEW_RUN02
python3 -B experiments/EXP-0057-m4-scratch-pressure-envelope/analysis/analyze.py \
  --run-dir experiments/EXP-0057-m4-scratch-pressure-envelope/raw/NEW_RUN01
python3 -B experiments/EXP-0057-m4-scratch-pressure-envelope/analysis/compare.py \
  experiments/EXP-0057-m4-scratch-pressure-envelope/raw/NEW_RUN01 \
  experiments/EXP-0057-m4-scratch-pressure-envelope/raw/NEW_RUN02
python3 -B experiments/EXP-0057-m4-scratch-pressure-envelope/make_manifest.py
python3 -B experiments/EXP-0057-m4-scratch-pressure-envelope/verify.py
```

Every trial is a fresh process. The retained M4 batch comprises two runs, seven
source levels, and two fixed shapes: 28 public GPU processes total. The runner
has a 20-second compile timeout and 15-second execution timeout, stops on a
timeout, and never retries a fault/reset/device-loss outcome automatically.

## Evidence boundaries

The metadata helper deletes its temporary own-pipeline archive and emits only
the two existing project metadata fields (GPR field 0 and scratch field 41/14).
It retains no compiled code bytes. This experiment captures no IOKit metadata
and reads no command, state, code, helper, or unknown BO.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE
Apple command/state/code/unknown BO bytes inspected: NONE
Compiled non-authored code inspected: NONE
```

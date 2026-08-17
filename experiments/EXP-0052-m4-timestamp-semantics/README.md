# EXP-0052 — M4 timestamp semantics

## Question

What can public Metal timestamp APIs establish on the local M4 about clock
calibration, stage-sample ordering, range reuse, and resolve availability?

This is a bounded P1.6 experiment. It does not map the observations to Linux
`GET_TIME`, `command_timestamp_frequency_hz`, firmware timestamp objects, or a
private counter heap, and it does not validate A18 Pro.

## Process

`PRE_REGISTRATION.md` was committed before the first live run. The authored
Objective-C harness uses public Metal/Foundation APIs and embedded authored MSL.
It records:

- 64 calibration intervals, each containing two CPU/GPU paired timestamp calls,
  across four requested delay classes;
- four render-stage sample indices for light and heavy fragment work;
- two ordered passes with disjoint sample-index ranges in one command buffer;
- resolution before commit, immediately post-commit but before the host wait,
  and after completion; and
- five matched light/heavy repetitions per process, across two fresh processes.

`run.py` creates a new append-only run directory, records target/tool/source
hashes and the pre-registration hash, and applies compile and execution
timeouts. It captures stdout/stderr even when the authored process faults.

The first two run directories are deliberately retained failures. The original
harness requested a 64x64 texture readback into a four-byte stack buffer and
faulted after the GPU portion. Run 01 buffered stdout, so it retained no live
lines; run 02 added unbuffered stdout and proved that every timestamp operation
had completed before the same authored readback fault. The final correction
changed only that readback to a 1x1 region. Runs 03 and 04 are the canonical
successful repetitions. `verify.py` reconstructs and hashes both failed harness
versions from the retained canonical source, so those process iterations remain
cryptographically attributable even though they are not promoted as evidence.

## Reproduction and verification

A fresh run must use a new identifier; never overwrite `raw/`:

```sh
python3 run.py --run-id m4_YYYYMMDD_runNN
python3 analysis/analyze.py
python3 verify.py
```

The raw harness label `in-flight` means only immediate post-commit/pre-wait;
command-buffer status was not sampled at that instant. The deterministic
analyzer reads only the authored JSON logs. The verifier
checks every raw run inventory/hash, exact target and source bindings, preserved
failure-source reconstruction, canonical output grammar, regenerated analysis,
and manifest coverage without executing the GPU.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source
Inputs inspected: authored Objective-C/MSL and public Metal timestamp results
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
IOKit/BO payload tracing: NONE
Pointer following: NONE
Evidence: raw/, analysis/summary.json, analysis/report.txt, RESULTS.md, manifest.json
```

# EXP-0122 — M4 sparse/VM conventions (DRV-ROBUST-01, P1.5 second half)

## Question

`docs/P0-P1-CLOSURE.md` row P1.5 (`DRV-ROBUST-01`) was only half-covered: EXP-0076 and
EXP-0083 established the owned-buffer OOB/base-slot robustness model, but the **sparse and VM
conventions half had no coverage at all**. This experiment characterizes, through public Metal
API observation on the local M4 only:

1. VM layout as observable from our own process (BO alignment/size rules,
   `device.maxBufferLength` as an exact boundary, device-address assignment behaviour).
2. Whether the EXP-0076 "OOB buffer reads return zero" finding is a guard mapping, a zero page,
   or an addressing-level behaviour, and whether it holds at large distances / VM boundaries.
3. Sparse page-table/tile/mip-tail geometry by construction (not "a flag and 16 KiB"),
   residency-return behaviour on unmapped access, and synchronisation around residency changes.
4. Publicly observable timestamp/frequency parameters.

Full hypotheses, falsifiers, and the frozen case matrices are in `PRE_REGISTRATION.md` and
`run.py` (the single authoritative source for every case list and the raw-record schema).

## Method

- `harness/probe.m`: one Objective-C binary (`xcrun clang -fobjc-arc -O1 -framework Metal
  -framework Foundation`), one case per process invocation, public Metal API only. Every
  record is `{"meta":..., "gated":..., "raw":...}`; `gated` never contains a GPU address,
  absolute timestamp, or wall-clock duration (enforced by `verify.py --selftest`).
- `kernels/guard_access.metal`, `kernels/sparse_access.metal`: authored MSL, compiled at
  runtime from source (OWN-SHADER).
- `run.py`: builds the harness, runs the NON-RECORDED smoke gate (`work/`, never `raw/`), and
  drives the full frozen case matrix into `raw/<run-id>/*.jsonl` (append + `fflush` + `fsync`
  per record). One process per case; two independent timeout belts (outer Python `subprocess`
  timeout, inner in-process watchdog exiting 97/compile or 98/dispatch).
- `verify.py`: `--selftest` (structural + comparison-logic self-test against synthetic
  fixtures shaped from `run.py`'s real frozen constants), `--seqtest` (PRE_GPU /
  RUN01_PRESENT / RUN02_PRESENT state-machine gate availability), `--preflight` /
  `--between-runs` / `--captured` (real-tree gates).
- `analysis.py`: cross-run gated-equality check (refuses to write on any mismatch) plus
  derived per-domain summaries → `analysis/summary.json`, `analysis/report.txt`.
- `make_manifest.py`: hashes every authored file and every `raw/` artifact.

## Reproduce

```
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B run.py --build
python3 -B run.py --smoke
python3 -B verify.py --preflight
python3 -B run.py --execute --run-id m4-20260828-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260828-run02
python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --captured
```

## Clean-room provenance

```
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: committed authored MSL (kernels/), harness (harness/probe.m), runner
  (run.py), verifier (verify.py), analysis (analysis.py); Apple SDK public header files
  (Metal.framework/Headers/*.h) read only for public API method signatures (standard SDK
  usage for programming against a documented public framework -- not disassembly).
Apple binary introspection: NONE
Reproduction: see command sequence above
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/, analysis/summary.json, manifest.json
```

See `RESULTS.md` for observations vs. interpretation, `PRE_REGISTRATION.md` for the frozen
hypotheses and case matrices, and `CAPTURE_CONTRACT.json` for the machine-checked contract.

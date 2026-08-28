# EXP-0125 — M4 scratch/helper mechanism: init-time trace + ceiling bisection + concurrent exhaustion

P0.1 (`DRV-UAPI-01`) has now been probed by two prior experiments at
dispatch-time steady state (EXP-0041, EXP-0107) with a consistent negative:
no scratch/helper record correlates with declared per-thread scratch demand
in the resource-map boundary trace. This experiment changes METHOD, per its
dispatch brief, instead of pushing the same method further: it traces the
device/queue/pipeline **lifecycle from before any spilling work exists**
(H1/H2), **bisects** EXP-0107's already-located compile-time ceiling to an
exact byte and checks it per-stage against mesa's own constant (H3), and
probes **genuine concurrent** (not sequential) GPU pressure (H4).

See `PRE_REGISTRATION.md` for the full falsifiable-hypothesis writeup and
`CAPTURE_CONTRACT.json` for the frozen schema/bracket/timeout contract.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER / DATA-TRACE / PUBLIC
Inputs inspected: authored MSL (kernels/kernelgen.py); this process's own
  IOKit boundary traffic (harness/inittrace.c, interposing only the public
  IOServiceOpen/IOConnectCallMethod surface); mesa/include/drm-uapi/
  asahi_drm.h and mesa/src/asahi/lib/agx_scratch.{h,c} read as PUBLIC
  reference for search-target constants only (never copied)
Apple binary introspection: NONE
Reproduction: see "Reproduce" below
Evidence: raw/m4-20260828-run{01,02}/, analysis/, manifest.json
```

## Layout

- `harness/inittrace.c` — DYLD interposer: checkpointed BO-inventory +
  best-effort selector-5 shared-page snapshotting.
- `harness/initprobe.m` — I family: device/queue/pipeline/dispatch lifecycle
  walk, nospill vs spill variant, SIGUSR1 checkpoints.
- `harness/ceiling.m` — B family: compile + pipeline-creation-only ceiling
  probe (no dispatch).
- `harness/concurrent.m` — C family: N concurrent `MTLCommandQueue`s, all
  committed before any awaited.
- `kernels/kernelgen.py` — authored MSL generator (trivial + K-parametrized
  array-loop CS/VS/FS kernels).
- `casematrix.py` — single source of truth: I/B/C family definitions,
  `run_bisection()` (the deterministic B-family algorithm), gated schemas.
- `traceparse.py` — parses `inittrace.c` checkpoint dumps into the gated
  per-checkpoint record shape.
- `run.py` — capture runner (gates, smoke test, the three families, in
  order, append+fflush per record).
- `verify.py` — the five standing gates.
- `analysis/analyze.py` — repeatable report over a captured run.
- `raw/m4-20260828-run{01,02}/` — the two gated captures.

## Reproduce

```sh
cd experiments/EXP-0125-m4-scratch-helper-init
python3 verify.py --selftest && python3 verify.py --seqtest
python3 run.py --run-id m4-20260828-run01 --execute
python3 run.py --run-id m4-20260828-run02 --execute
python3 verify.py --check
python3 analysis/analyze.py raw/m4-20260828-run01 > analysis/report_run01.txt
python3 analysis/analyze.py raw/m4-20260828-run02 > analysis/report_run02.txt
```

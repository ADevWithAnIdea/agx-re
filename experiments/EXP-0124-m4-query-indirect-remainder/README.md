# EXP-0124 — M4 query/counter-heap and indirect/DGC remainder

**Closes remaining ground for P1.6 (`DRV-QUERY-01`) and P1.7 (`DRV-INDIRECT-01`)** on the
local Apple M4 (G16G), extending — not redoing — EXP-0027 (A18 DATA-TRACE), EXP-0052 (M4
public timestamp semantics), EXP-0053 (M4 indirect API semantics), EXP-0091 (occlusion
early/late interaction), and EXP-0098 (M4 GPU-driven draws / device-generated commands).

## Question

1. **P1.6**: counter-heap layout/alignment/limits, allocation rules, accumulation
   semantics, reset behavior, availability signaling, copy/resolve rules, simultaneous
   queries, tick frequency/conversion/wrap, occlusion query counting-vs-boolean/precision/
   overlap semantics, and whether pipeline statistics exist natively.
2. **P1.7**: direct vs. indirect CDM dispatch modes and parameter-memory formats,
   multi-draw/dispatch links and barriers, count buffers, indexed/non-indexed forms and
   primitive-restart/bounds rules, the writable device-generated (GPU-authored ICB)
   command grammar, and stream-limit boundary behavior.

Full falsifiable hypotheses: `PRE_REGISTRATION.md` (H-Q1..H-Q9, H-I1..H-I7).

## Method

Public Metal API only (`newLibraryWithSource:` runtime compilation of our own MSL) +
public Xcode SDK headers (struct/method declarations, not binary introspection) +
HW-PROBE (live GPU dispatch/readback). No `tools/*`, no assembler, no native VDM/CDM
grammar, no IOKit tracing — every question here was answerable at this layer. See
`RESULTS.md`'s clean-room attestation for the full inventory.

Two ObjC harness binaries, each running **exactly one case per process** (SAFETY: this
family can fault the GPU context and has crashed the calling process at high counts, per
the dispatch instructions):
- `harness/qbench.m` — Group Q (P1.6) cases, kernels in `kernels/q_common.metal`.
- `harness/ibench.m` — Group I (P1.7) cases, kernels in `kernels/i_common.metal`.

`harness/casematrix.py` freezes the 85-case fixed matrix. `harness/icbmax_bisect.py`
performs a separate, deterministic binary-search bisection of the
`newIndirectCommandBufferWithDescriptor:maxCommandCount:` crash boundary (adaptive on
real outcomes, hence not a fixed matrix case, but fully reproducible given fixed hardware
behavior — see its module docstring). `harness/run.py` drives one subprocess per case
under a hard timeout, splitting each result into a gated record (`case_id, family, kind,
params, status, verdict, observed`) and a non-gated sibling (`case_id, wall_ms, pid,
raw_tail, raw_ticks` — all raw nanosecond/tick values live here, never in the gated
record). `harness/verify.py` implements the five standing gates.

## Reproduction

```sh
# Rebuild both harness binaries.
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/qbench harness/qbench.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/ibench harness/ibench.m

# Standing gates.
python3 harness/verify.py --selftest
python3 harness/verify.py --seqtest

# Inspect the frozen matrix.
python3 harness/run.py --list

# One official capture run (writes raw/<run_id>/; refuses to overwrite an existing dir).
python3 harness/run.py --run <run_id> --out raw/<run_id>

# Cross-run gate (after two runs exist).
python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02
```

## Files

```text
PRE_REGISTRATION.md      hypotheses H-Q1..H-Q9 / H-I1..H-I7, frozen before harness code
CAPTURE_CONTRACT.json    frozen authored-file hashes, pinned revision, gate descriptions
PROGRESS.md              milestone log incl. every build-time bug found and fixed
RESULTS.md               observed vs. interpreted, finite-resource table, clean-room attestation
manifest.json            experiment metadata
harness/
  schema.py              gated/nongated record schema (gate (d) realized structurally)
  casematrix.py           the frozen 85-case matrix + nondeterministic_observed_keys()
  qbench.m / ibench.m     the two harness binaries (STATUS/DEVICE/OBSERVED/TICKS protocol)
  run.py                  driver: one subprocess per case, smoke gate, append+fflush
  icbmax_bisect.py        maxCommandCount crash-boundary bisection
  verify.py               the five standing gates
kernels/
  q_common.metal          Group Q MSL (occlusion, spin, marker kernels)
  i_common.metal          Group I MSL (indirect-dispatch, ICB-encoding, restart kernels)
fixtures/
  recorded_reality.json   5 real M4 captures backing verify.py --selftest (gate (e))
work/
  bin/qbench, bin/ibench  built binaries (rebuild from harness/*.m; not committed logic)
  trycompile.m, try*.metal, try_icb.m   MSL/ICB-grammar syntax discovery aids (Milestone 2)
raw/
  m4_20260828_run01/      official capture 1 (00_inputs/02_gated/03_nongated/04_manifest/05_icbmax_bisect)
  m4_20260828_run02/      official capture 2 (same shape)
```

## Clean-room provenance

See `RESULTS.md`'s attestation block. Summary: `HW-PROBE + OWN-SHADER + PUBLIC`. No Apple
binary was introspected anywhere in this experiment.

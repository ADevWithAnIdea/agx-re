# EXP-0093 — M4 fence/barrier instruction family (`0x07`) + raster-order-group interlock

**Question.** Decode the Apple9 `0x07`-family fence/barrier instruction group in full
(selectors, variants, finite-resource limits) and establish, with genuine concurrent
hardware evidence (not just byte-diff), the memory-scope/ordering semantics each
variant provides — closing `ATOM-07` through `ATOM-11`
(`APPLE9_RE_IMPLEMENTATION_GAPS.md`, "P0 — Atomics and synchronization") and `GLFS-A08`
(`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md:253-271`, raster-order-group / fragment-shader
interlock).

**Why it matters.** `EXP-0085-m4-memory-interlock-atomics` closed the atomic op-selector
table (ATOM-01..06) but explicitly deferred ATOM-07..11 to a dedicated `0x07`-family
splice campaign. `EXP-0091-m4-fragment-sample-discard` located a companion op in the
same family but did not decode it. `EXP-0029-fragment-isa` (A18 Pro) byte-diffed a
`pixel_order` acquire/release pair for raster-order-groups but explicitly flagged it
"not splice-proven for a stale read — needs overlapping-fragment geometry" — the exact
gap this experiment closes on M4, plus the compute-side device-memory-fence ordering
question `EXP-0051-m4-synchronization-litmus` left PARTIAL.

**Method.** Own-MSL differential compilation for the byte-level decode (`STRUCTURAL`/
`OWN-SHADER-DIFF`, no GPU dispatch needed for pure byte-shape claims), then genuine
concurrent hardware litmus tests for every ordering/mutual-exclusion claim:

1. **Fragment raster-order-group mutual exclusion** (`GLFS-A08`): N overlapping
   fragments (drawn as N instances of one full-screen triangle, all covering the same
   1×1 target pixel) each perform a non-atomic read-modify-write increment of a shared
   `read_write` texture or device-buffer counter, protected by
   `[[raster_order_group(0)]]`. A deterministic exact invariant (final == N) replaces
   the message-passing "did we happen to observe a stale flag" style test — a lost
   update is far easier to force under real hardware parallelism than a memory-
   reordering-only hazard, and both a WEAK (untagged) control and a HW splice control
   (neutering the compiled acquire/release or bracket-open bytes) are required to
   break the invariant before any ordering claim is promoted.
2. **Compute device-memory fence** (`ATOM-07`/`ATOM-08`): a cross-threadgroup
   message-passing mailbox (`EXP-0051`'s methodology) generalized from 1-2 threadgroups
   to `PAIRS` independent producer/consumer pairs in one dispatch, to reach genuine
   cross-core concurrency (EXP-0051's 1-2-threadgroup scale never exposed a violation;
   this experiment shows why, and shows the violation at larger `PAIRS`).
3. **Barrier execution convergence** (`ATOM-09`/`ATOM-10`): EXP-0025's `tgdiv2`
   per-lane variable-delay convergence kernel, HW-splice-validated bidirectionally on
   the compiled `threadgroup_barrier`/`atomic_thread_fence` byte that toggles execution
   convergence on and off.

**Target: local Apple M4 (G16G) only.** No A18 Pro claim (A18 hands-off).

## Layout

- `PRE_REGISTRATION.md` / `CAPTURE_CONTRACT.json` — hypotheses, matrix, frozen hashes.
- `harness/` — `roglitmus.m` (fragment ROG litmus + splice runner), `fencelitmus.m`
  (compute device-fence pairs runner), `splice.py` (archive byte-patcher),
  `schema.py`/`casematrix.py`/`run.py`/`verify.py` (the frozen 128-case matrix,
  executor, and standing-gate verifier).
- `kernels/` — all authored MSL (litmus kernels, structural-census kernels, the
  `tgdiv2_*` convergence family).
- `raw/m4_20260828_run01/`, `raw/m4_20260828_run02/` — the two official capture runs
  (128 cases each, append-only).
- `RESULTS.md` — observed/interpreted findings, per-item response blocks, verdicts.
- `PROGRESS.md` — timestamped milestone log.

## Reproduce

```sh
cd experiments/EXP-0093-m4-fence-barrier-interlock
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/shdump ../../tools/shdump/shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/agxrun ../../tools/agxtest/agxrun.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/roglitmus harness/roglitmus.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/fencelitmus harness/fencelitmus.m
python3 harness/verify.py --selftest
python3 harness/verify.py --seqtest
python3 harness/verify.py --preflight
python3 harness/run.py --run <new_run_id> --out raw/<new_run_id>
python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02
```

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL (kernels/*.metal), authored ObjC harnesses
  (harness/roglitmus.m, harness/fencelitmus.m), authored Python (harness/schema.py,
  harness/casematrix.py, harness/run.py, harness/verify.py, harness/splice.py),
  read-only use of tools/shdump, tools/agxtest, tools/agx-isa (unmodified) on our own
  compiled kernel bytes.
Apple binary introspection: NONE.
Target qualification: local M4/G16G only; no A18 Pro claim.
Reproduction: commands above.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/, CAPTURE_CONTRACT.json.
```

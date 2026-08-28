# EXP-0107 results: P0.1 negative extended ~454x; a real, precise compile-time ceiling located; helper program still not observed

## Verdict

**PARTIAL / strong, well-controlled negative, plus one precisely-located
positive boundary. P0.1 (`DRV-UAPI-01`) is not closed.**

On the local M4/G16G, this experiment pushed declared per-thread scratch from
0 to **261,728 bytes** (≈255.6 KiB, ~454x beyond EXP-0041's 208–576 B range),
varied stage (CS/VS/FS), total dispatched thread count from 64 to
**4,194,304**, threadgroup shape (32/256/1024), and genuine repeated
spill/fill traffic (up to 1,000 runtime passes) — 30 authored cases, captured
twice independently (`m4-20260827-run01`/`run02`), both fully hardware-run.
**No scratch-correlated BO, helper-program record, or doorbell/ABI structure
was located** through the widened DATA-TRACE boundary (every BO our own
process maps, not just EXP-0041's four pre-established roles). This
strengthens, at much higher pressure and broader shape, the same negative
EXP-0041 reported at 208–576 B — it is not evidence that a helper mechanism
does not exist, only a bound on what this trace vector exposes.

Separately, this experiment **did** locate a real, precise, hardware-
validated boundary: **declared per-thread scratch above 261,728 B fails
cleanly at pipeline-creation time** (`newComputePipelineStateWithFunction`
→ "Compute function exceeds available stack space"), reproducibly, with no
device fault, timeout, or corruption — see Sec. 4.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER / DATA-TRACE / PUBLIC API
Inputs inspected: authored MSL (kernels/generate.py); this experiment's own
  just-compiled archive metadata (harness/metadata.py, the established
  EXP-0041/EXP-0020 pattern); our own process's IOKit boundary traffic and
  every BO it registers via the resource-map selector, content included
  (harness/maptrace.c)
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE (none located to inspect)
Reproduction: README.md commands
Evidence: raw/m4-20260827-run{01,02}/, analysis/, manifest.json
```

## Process note: a mid-experiment directory-containment fix

`SUBAGENT_BRIEF.md` was updated during this experiment to explicitly forbid
writing outside the repository, even briefly. Auditing this experiment's own
code found two violations (`run.py`'s tool-build tempdir, `harness/
metadata.py`'s archive-compile tempdir, both defaulting to system `$TMPDIR`)
plus ad hoc `/tmp` files from pre-registration reconnaissance. **No Apple
data or forbidden material was ever involved** — only our own compiled
binaries and our own compiled shader archives, transiently, and all are now
deleted. Both files were fixed to route every temp/build directory through
this experiment's own `work/` subdirectory. The first `run01` capture and the
aborted first `run02` attempt (which failed a *different*, correct check —
see below) are retained, disclosed, and superseded in
`raw/SUPERSEDED_m4-20260827-run{01,02}_*_/SUPERSEDED.md`; **only
`raw/m4-20260827-run01/` and `raw/m4-20260827-run02/` (the fresh, corrected
captures) are reported below.**

## 1. OBSERVED: scratch scales linearly with K, decoupled from code size

`kernels/generate.py`'s array-loop kernel design (`thread float a[K]`, a
genuine runtime loop, not K manually-unrolled scalars) keeps compiled
`_agc.main` size roughly flat while declared scratch scales with K. Observed
(both runs, byte-identical):

| K | declared scratch (B) | GPR field 0 | compiled `_agc.main` bytes |
|---:|---:|---:|---:|
| 8 | 0 | 14 | 362 |
| 32 | 0 | 39 | 1,026 |
| 96 | 400 | 95 | 6,842 (outlier — see below) |
| 192 | 784 | 41 | 2,592 |
| 384 | 1,552 | 41 | 2,720 |
| 768 | 3,088 | 41 | 2,720 |
| 1,536 | 6,160 | 41 | 2,720 |
| 3,072 | 12,304 | 41 | 2,720 |
| 6,144 | 24,592 | 40 | 2,724 |
| 12,288 | 49,168 | 40 | 2,694 |
| 24,576 | 98,320 | 40 | 2,694 |
| 49,152 | 196,624 | 40 | 2,498 |
| 65,430 | 261,728 | 25 | 1,490 |
| 65,440 | *(pipeline creation fails — see Sec. 4)* | | |

For K≥192, `scratch_bytes = 4·K + 16` held exactly until the low-K-96
boundary region, where the compiler evidently takes a different codegen path
(GPR field jumps to 95, code size to 6,842 B — a single-point outlier, not
investigated further). Compiled code size stays in a **~2,500–2,720 B band
across more than two orders of magnitude of K** (192→49,152), then drops at
the very top of the range (65,430: 1,490 B) — genuinely decoupled from
scratch demand, not perfectly flat but never tracking it. This is
`OWN-SHADER` metadata evidence (our own compiled archive's own FlatBuffer,
walked by our own parser), independently reproduced byte-for-byte across both
runs for all 13 successful K-family cases.

## 2. OBSERVED: no boundary-trace signal tracks scratch demand

Every one of the 30 authored cases ran under `harness/maptrace.c`, which logs
(a) the full `(class, gpu_va, size)` resource-map entry for **every** BO our
own process registers (unconditional, not merely the four EXP-0041
allowlisted roles) and (b) a 16,384-byte content prefix of **every** such BO
(the widened capability this experiment adds over EXP-0041).

- **K family (CS, grid=64/tg=32 fixed, K = 0→261,728 B declared scratch):**
  `bo_count` (27) and `bo_total_bytes` (2,428,032) are **identical across
  every successful K level**, in both runs. The address-free
  `resource_map_shape` multiset is identical too.
- **S family (VS/FS at K∈{96,1536,6144}):** `bo_count`=38, `bo_total_bytes`
  =4,997,344, constant across all six cases (the render path naturally has
  more BOs than compute's 27, but that count/size is itself scratch-
  independent).
- **O family (CS, K=1,536 fixed, total threads 1,024→4,194,304):**
  `bo_total_bytes` **does** grow at the two largest grids (1,048,576 →
  6,491,264 B; 4,194,304 → 19,074,176 B). A positional per-BO diff
  (`analysis/analyze.py` Sec. 6) shows this is **fully explained by the
  harness's own output buffer** (`newBufferWithLength:grid*sizeof(float)`,
  `harness/probe.m`) becoming visible as its own large resource-map entry —
  a benign, expected artifact of the probe design, not a hardware scratch
  pool. Nothing else in the resource-map shape changes with grid.
- **X family (compound: K=49,152×grid=1,048,576; K=65,430×grid=4,194,304):**
  `bo_total_bytes` and `resource_map_shape` are **byte-identical** to the
  O-family case at the *same grid* with K=1,536 — i.e. multiplying declared
  per-thread scratch by 32x (49,152/1,536) or 42.6x (65,430/1,536) at fixed
  grid changes **nothing** in the address-free footprint. This is the
  cleanest negative in the dataset: aggregate registered-BO footprint tracks
  **grid size only**, never declared scratch, across the full tested compound
  range.
- **Numerical plausibility at extreme scale (informational, not part of the
  gated schema):** `X_cs_k65430_g4194304` (261,728 B/thread × 4,194,304
  threads) completed in ~38 s with checksum `3.41202781e+10`, matching the
  expected order of magnitude (`K × mean-input-value × threads ≈ 65,430 ×
  0.126 × 4,194,304 ≈ 3.46e10`) — not corrupted. A naive
  `declared_bytes × total_threads` allocation would require **≈1.10 TB** on
  a 16 GB host. This is strong (though indirect) evidence that whatever
  backs declared scratch is a **bounded/pooled resource sized by hardware
  concurrency, not by total dispatched thread count** — consistent with,
  though not proof of, the public Mesa hypothesis of a small per-core pool.

## 3. OBSERVED: a positive-but-inconclusive lead, checked and not promoted

A positional diff between the no-spill (K=8) and max-tested-spill (K=65,430)
K-family cases found that **12 of the 27 BOs are byte-identical** and the
remaining differences are: the code-window BO (`0x…0000`, expected — the
compiled program itself differs), a set of ~256-byte-per-BO differences in
eleven `0x20000`-sized queue-context BOs (`0x…18700`…`0x…1c500`), and small
(10–14 byte) differences in two other queue-context BOs (`0x…40000`,
`0x…98000`).

Extending this to **every** K level (not just the two endpoints) shows these
small differences do **not** track scratch demand cleanly: the exact same
byte pattern at these offsets is shared by K=384 through K=24,576 (a 63x
scratch-byte range, spanning both GPR-field-41 and GPR-field-40 codegen), and
only changes at K=8/32 (no spill), K=96 (the codegen outlier), K=49,152, and
K=65,430. This plateau-then-shift pattern is not a monotonic function of
declared scratch bytes, nor of GPR field, nor of compiled code length in any
simple way tested. **This experiment does not promote these bytes as a
scratch/helper record** — the evidence is genuinely ambiguous (most
consistent with compiler-internal state, a pipeline hash/UUID, or padding
that happens to correlate loosely with a handful of specific K values) and a
single before/after pair would have been a false positive here. Recorded as
a bounded, honest **inconclusive lead** for a dedicated follow-up (a proper
change-one-variable sweep isolating exactly which K transition moves each of
these specific offsets, analogous to EXP-0011's config-word correlation
method) — see Sec. 6.

## 4. OBSERVED: a precise, clean, reproducible compile-time scratch ceiling

Both runs independently, byte-identically, locate the same boundary:

- **K=65,430 (scratch=261,728 B) succeeds.** Compiles, creates a compute
  pipeline, dispatches, and completes correctly (checksum reproducible
  across runs).
- **K=65,440 would declare ~261,776+ B and fails at
  `newComputePipelineStateWithFunction`** with the public Metal error
  string `"Compute function exceeds available stack space"` — a clean,
  documented API-level rejection, not a device fault, hang, timeout, or
  silent wrong answer. It fails identically via both `harness/metadata.py`
  (the `tools/shdump` compile path) and `harness/probe.m` (the runtime
  dispatch path), in both runs.
- Pre-registration-stage reconnaissance (not evidence; recorded in
  `PRE_REGISTRATION.md`) narrowed this further, off the gated record: success
  persists through K=65,430 (scratch=261,728 B) and fails from K=65,440
  onward, with the true crossover somewhere in scratch∈(261,728, 261,776] B —
  suspiciously close to but not exactly 262,144 B (256 KiB). This experiment
  reproduces the K=65,430/65,440 **endpoints** as gated evidence; it does not
  re-run the finer bisection under the gate (a next experiment could, in
  under a dozen cases, if the exact byte boundary matters to the driver).
- This ceiling is a **compile-time property of the compiled function**,
  determined before any dispatch parameter (grid/threadgroup) is even
  specified — by construction it cannot depend on occupancy, and this
  experiment did not (and does not need to) separately test the ceiling at
  every grid size to support that inference.

**Failure-mode classification for P0.1's "allocation-failure and growth
behavior" requirement:** within the tested range, the *only* failure mode
found is this clean, deterministic, compile-time API rejection. No silent
corruption, no device fault, no timeout, and no "graceful growth" (there is
no larger backing that gets allocated on demand past this point — the
compiler refuses to produce the function at all) was observed anywhere in
the tested range for either scratch size or total thread count.

## 5. OBSERVED: no VS/FS-specific state, no occupancy-specific state (within tested range)

S-family (stage) and O/X-family (occupancy) cases show the same pattern as
the K family: `bo_count`/`bo_total_bytes`/`resource_map_shape` never
correlate with declared scratch. The render path (VS/FS) has more total BOs
than compute (38 vs 27, expected — texture/render-target/argument-buffer
infrastructure a draw needs that a dispatch does not) but that difference is
present already at K=96 (near-zero scratch) and does not grow further with
K. H-family (n=1,000/n=200 genuine repeated spill/fill passes, not the
degenerate n=1 init+reduce check) completed correctly with finite,
reproducible checksums and the same footprint as their n=1 counterparts —
sustained spill/fill traffic across many passes does not itself surface a
new record either.

## 6. A genuinely new, discovered, non-gated field (methodology finding)

Cross-run comparison (`verify.py --check`) found that **`bo_content_seq_sha256`
is not reproducible on 9/30 cases** (`S_fs_k96`, `S_vs_k1536`, `S_vs_k6144`,
`S_fs_k6144`, `O_cs_k1536_g1048576_t32`, `O_cs_k1536_g4194304_t256`,
`X_cs_k49152_g1048576`, `X_cs_k65430_g4194304`, `H_cs_k1536_n1000`) — every
other `CASE_KEYS` field, including `scratch_field_41_or_14`, `gpr_field_0`,
`checksum`, `resource_map_shape`, `bo_count`, and `bo_total_bytes`,
reproduced **exactly** on all 30/30 cases in both runs. The mismatching
cases cluster around some (not all) render-stage cases and every case with
either grid≥1,048,576 or n>1 — consistent with a small amount of execution-
timing/scheduling-dependent incidental content inside one or two specific
BOs (plausibly a pipeline UUID/hash embedded by the compiler, or a
counter/timestamp — not further isolated in this experiment), not with a
GPU address (`casematrix.py`'s `NONDETERMINISTIC_CASE_KEYS` already excluded
raw VAs from the gate by design; this is a second, independently-discovered
nondeterministic field, found empirically rather than assumed). Per the
standing gate's own instruction, it was moved out of the cross-run gated
payload (`casematrix.GATED_CASE_KEYS`), and the exclusion itself is proven
by a dedicated `verify.py --selftest` case (a synthetic tree differing only
in this field must pass `gate_captured`) — `verify.py --selftest` and
`--check` both pass against the real captures.

## Exact tested range

- **Declared per-thread scratch:** 0 – 261,728 B (last success); first clean
  failure at ≥~261,776 B. Formula `scratch_bytes = 4·K + 16` holds for
  K∈[192, 65,430] (13 points); K∈{8,32} are no-spill controls; K=96 is a
  single-point codegen outlier.
- **Stages:** CS (24 cases), VS (3 cases), FS (3 cases).
- **Total dispatched threads:** 64 (K/S-family default) through 4,194,304
  (harness's own hard-coded safety cap, `harness/probe.m`).
- **Threadgroup shapes:** 8 (smoke only), 32, 256, 1,024.
- **Runtime pass count `n`:** 1 (26 cases, degenerate init+reduce
  correctness check) and 200/1,000 (H family, genuine repeated spill/fill
  traffic).
- **Compound (K × grid) stress:** K=49,152 at 1,048,576 threads;
  K=65,430 at 4,194,304 threads. Untested: K above the ~261.7 KiB ceiling
  combined with a large grid (moot — the pipeline never compiles regardless
  of grid), and grid above 4,194,304 (the harness's own safety cap, not an
  observed hardware limit).
- **Target:** local M4/G16G only. No A18 Pro replication (per `CLAUDE.md`
  target discipline — A18 is hands-off).
- **Repetitions:** 2 independent full captures (`m4-20260827-run01`/`run02`),
  every `GATED_CASE_KEYS` field identical across both for all 30/30 cases.

## What P0.1 still requires (unchanged in kind, extended in scale)

All of the following remain **completely unestablished** by this or any
prior experiment:

- helper program `binary`/`cfg`/`data` tags and every `cfg` bit for
  VS/FS/CS/preamble;
- helper `data` input special registers and NEXT/ACK/NACK doorbell
  encodings;
- scratch header, per-core block list, block descriptor, alignment/address
  shift, bucket rules, maximum active subgroups, and block size/count;
- topology/core-mask → helper-core mapping;
- reset/growth/concurrency semantics for whatever backs scratch (this
  experiment establishes only that it is *not* naively sized by
  `declared_bytes × total_threads`, and that the one failure mode found is a
  clean compile-time rejection — it does not establish what, if anything,
  is allocated at dispatch time, or how);
- proof that G16/G17 consume the existing `drm_asahi_helper_program` fields
  at all;
- A18 Pro replication (out of scope per target discipline).

**A specific, actionable scope gap this experiment surfaces:** `harness/
maptrace.c` (like EXP-0041's) only captures content for BOs registered via
the resource-map selector (IOKit selector 9). It logs only the *presence* of
the firmware-shared submission-ring pages (selector 5) — `docs/
kernel-interface.md` §2 documents the doorbell as "a store into a
firmware-shared page + barrier," a region this trace never reads the content
of. If a scratch/helper doorbell protocol lives there rather than in a
sel-9-mapped BO, this experiment could not have found it. Extending the
interposer to also snapshot the shared-pages content (still DATA-TRACE-clean
— it is memory our own process itself maps) is the most concrete next step,
followed by a proper multi-point isolation of the Sec. 3 inconclusive lead.

## Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` — frozen hypotheses,
  boundary, case-matrix design constraints.
- `casematrix.py` — the 30-case matrix (single source of truth).
- `kernels/generate.py`, `harness/probe.m`, `harness/metadata.py`,
  `harness/maptrace.c` — authored generators/harness.
- `run.py`, `verify.py`, `traceparse.py` — capture runner and the five
  standing gates (`--selftest`/`--seqtest`/smoke-before-raw/schema-exact
  gating/fixtures-from-recorded-reality).
- `raw/m4-20260827-run{01,02}/` — the two real captures (append-only,
  gated `02_cases.jsonl`, ungated `03_timing.jsonl`/`05_raw_maps.jsonl`,
  per-case maptrace `.log` + per-BO `.hex` prefixes under `dumps/`).
- `raw/SUPERSEDED_m4-20260827-run{01,02}_tmpdir-violation/` — disclosed,
  retained, non-evidence artifacts from the pre-fix attempts (see their own
  `SUPERSEDED.md`).
- `analysis/analyze.py`, `analysis/report_run{01,02}.txt` — repeatable
  per-run report (scratch-vs-footprint tables, boundary summary, positional
  BO diffs).
- `manifest.json` — hashes of every committed artifact.

## Limitations

- No A18 Pro replication (target discipline).
- The Sec. 3 small state-word differences are reported as an inconclusive,
  bounded lead, not a located record — see the explicit statement there.
- `bo_content_seq_sha256` (Sec. 6) is excluded from the cross-run gate for
  the reason stated; it remains in `raw/` for anyone who wants to
  investigate it further.
- The shared-pages (doorbell) content gap (see "What P0.1 still requires")
  means a helper/scratch mechanism living exclusively in that region would
  not have been observable by this experiment at all.
- `raw/` totals ~120 MB across the two real captures plus the two disclosed
  superseded attempts (all plain-text hex/JSON, no binaries) — larger than
  most experiments in this repo; flagged for the orchestrator's own judgment
  on retention/pruning of the superseded copies.

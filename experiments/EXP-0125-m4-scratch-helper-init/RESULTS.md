# EXP-0125 results: init-time trace confirms EXP-0107's negative at a THIRD point (before dispatch, before compile); exact stage-uniform compile ceiling located (~half of mesa's constant); concurrent pressure reproducibly corrupts output above a session-dependent queue count

## Verdict

**Three independent, well-controlled results, none of which locate a
scratch/helper record on the macOS boundary, plus one new positive
hardware boundary (H4) and one exact ceiling (H3). P0.1 (`DRV-UAPI-01`) is
still not closed — but its negative is now established at every point in
the userspace lifecycle this project's tooling can reach, and the ceiling
and exhaustion-semantics gaps it still needs are narrowed to a precise,
reproducible shape.**

- **H1 (device-wide pool visible at init): REFUTED for the tested design.**
  The full address-free BO inventory (`resource_map_shape`, `nbo`,
  `bo_total_bytes`) is **byte-identical** between a process that never
  spills and a process that spills 98,320 B/thread, at **every one of six
  lifecycle checkpoints** — `DEVICE_CREATED`, `QUEUE_CREATED`, after the
  first (trivial) pipeline, after the second (variant-dependent) pipeline,
  immediately before dispatch, and immediately after — in **both** gated
  runs, byte-for-byte cross-run identical too. No pool, static or
  otherwise, is visible anywhere in this trace, at any point from process
  start to dispatch completion.
- **H2 (distinct helper-program binary): REFUTED for the tested design.**
  The one plausible executable-code region (EXP-0042/EXP-0108's code
  window, VA `0x10000000000`) is present and exactly `0x10000` B (64 KiB)
  at **every** checkpoint in **both** variants, **including
  `DEVICE_CREATED`, before this process has compiled a single line of
  MSL** — extending EXP-0108's "constant size across 40 render configs"
  finding one step further back: constant size across the ENTIRE lifecycle,
  present from the very first moment, never growing when a second
  (spilling) pipeline is added. No second/distinct code-shaped region was
  found anywhere. Selector-5 ("shared pages") was never observed to be
  called at all, in either variant, either run — a clean, reproduced
  negative for that avenue too. (A clean-room correction was required and
  self-disclosed mid-experiment before this became gated evidence — see
  "Clean-room correction" below; the code window's own CONTENT was never
  read as a matter of design, only its presence/size.)
- **H3 (ceiling bracket + stage uniformity): CONFIRMED, exactly, stage-
  uniform.** All three stages (CS/VS/FS) independently bisect to the
  identical boundary: **last success K=65,431 (261,740 B declared
  scratch), first failure K=65,432 (261,744 B)** — a 4-byte (one array
  element) resolution, the finest this design can measure. Byte-identical
  across both gated runs, for all three stages. This is **≈2.003x below**
  mesa's own `AGX_MAX_SCRATCH_DWORDS` (131,072) — real, not noise, and not
  fully explained by a units artifact (see "H3 ceiling relationship"
  below).
- **H4 (concurrent exhaustion): CONFIRMED — a real, reproducible-in-KIND-
  but-not-in-THRESHOLD failure mode.** Escalating concurrent
  `MTLCommandQueue` pressure (1→32 queues, all committed before any
  awaited, each running the same validated-safe K=24,576 kernel) produces
  **silent numerical corruption (`checksum_mismatch`) and outright command-
  buffer errors (`EXEC_FAIL`)**, never at `n_queues` ≤ 4 in either run, but
  starting between `n_queues=8` and `n_queues=32` — **the exact onset
  point differs between the two gated runs** (run01: first failures at
  `n_queues=8`, worst at `n_queues=16` with 45 mismatched-checksum queue-
  instances across 6 trials; run02: clean through `n_queues=16`, first
  failures only at `n_queues=32`, 48 mismatches). This session-to-session
  variability is itself the finding — see below.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER / DATA-TRACE / PUBLIC
Inputs inspected: authored MSL (kernels/kernelgen.py); this process's own
  IOKit boundary traffic (harness/inittrace.c, interposing only the public
  IOServiceOpen/IOConnectCallMethod surface, reading only memory this
  process itself registered); mesa/include/drm-uapi/asahi_drm.h and
  mesa/src/asahi/lib/agx_scratch.{h,c} read as PUBLIC reference for
  search-target constants only (AGX_MAX_SCRATCH_DWORDS, AGX_SPILL_UNIT_
  DWORDS, etc.) -- never copied, never treated as Apple9 ground truth
Apple binary introspection: NONE
Apple auxiliary/helper program bytes committed: NONE. The EXP-0042/EXP-0108
  code window's content is excluded from capture entirely, by construction,
  in the corrected harness/inittrace.c (never merely by policy statement) --
  see "Clean-room correction" below for the one place this was not true
  from the start, and how it was handled.
Reproduction: see README.md
Evidence: raw/m4-20260828-run{01,02}/, analysis/, manifest.json,
  raw/SUPERSEDED_*/ (disclosed, retained, non-evidence)
```

## Clean-room correction (self-disclosed, before any gated evidence was promoted)

This experiment's own novelty over EXP-0041/EXP-0107 (tracing BEFORE our
first compile, not only after) introduced a risk those experiments never
faced. A dry run under the first-written `harness/inittrace.c` (which
captured a content prefix of every BO unconditionally, inherited from
EXP-0107's `harness/maptrace.c`) found the code-window BO already has
non-zero content at `DEVICE_CREATED`, before this process has compiled
anything — a check EXP-0107 never needed (its own captures always happened
after our own shader had already compiled, so any code-window content it
saw was attributable to OWN-SHADER by construction). This experiment's
harness had not carried forward `EXP-0108-m4-bg-eot-programs/harness/
wtrace.c`'s own deliberate, already-reviewed policy of excluding that exact
VA range (`[0x10000000000, 0x10000020000)`) from content capture entirely.

This was caught, disclosed, and corrected before any gated capture was
promoted: `harness/inittrace.c` now excludes code-window content by
construction (recording only presence/size, exactly like EXP-0108); the
one dry-run capture that had the uncorrected behavior is retained,
disclosed, and had its code-window `.hex` files redacted-to-hash (content
replaced with `sha256`/length/nonzero-count only — no bytes retained) at
`raw/SUPERSEDED_m4-20260828-run01_codewindow-precompile-content/`. **No
disassembly, decoding, instruction-level interpretation, or byte-pattern
analysis beyond a single zero/nonzero-count check was ever performed** on
that content, by any tool or by the agent running this experiment.
`PRE_REGISTRATION.md`'s addendum 1 has the full account. A second,
unrelated supersession (`raw/SUPERSEDED_m4-20260828-run01_c-family-single-
trial-design/`) recorded a design revision to the C family (see H4 below)
before any gated C-family evidence existed; `raw/SUPERSEDED_m4-20260828-
run01_missing-analysis-script/` recorded one pre-flight software crash with
zero captured content. All three are disclosed in place, per
`SUBAGENT_BRIEF.md` ("a partial capture is retained, never reused") and
`EXP-0107-m4-scratch-helper-abi`'s own established precedent for exactly
this situation.

## 1. H1/H2 — OBSERVED: init-time checkpoint trace

`harness/initprobe.m` walks two process variants ("nospill": both compiled
pipelines are a trivial, provably non-spilling kernel; "spill": the second
pipeline is a real K=24,576 array-loop kernel, ~98,320 B/thread declared
scratch, actually dispatched at grid=65,536/tg=256) through six identical
checkpoints, SIGUSR1-triggering `harness/inittrace.c` to snapshot the full
BO inventory at each:

| cp | label | nospill.nbo | spill.nbo | bytes (both) | shape_eq | code window (both) |
|---:|---|---:|---:|---:|:---:|:---:|
| 0 | DEVICE_CREATED | 2 | 2 | 79,872 | **True** | present, 65,536 B |
| 1 | QUEUE_CREATED | 18 | 18 | 2,045,952 | **True** | present, 65,536 B |
| 2 | PIPELINE1_CREATED | 18 | 18 | 2,045,952 | **True** | present, 65,536 B |
| 3 | PIPELINE2_CREATED | 18 | 18 | 2,045,952 | **True** | present, 65,536 B |
| 4 | PRE_DISPATCH | 27 | 27 | 2,559,104 | **True** | present, 65,536 B |
| 5 | POST_DISPATCH | 27 | 27 | 2,559,104 | **True** | present, 65,536 B |

Identical in **both** gated runs (`i_checkpoints_sha256` byte-identical
run01 vs run02, all 12 records, all fields including the address-free
`resource_map_shape`). **`shape_eq` is `True` at every single checkpoint** —
the nospill/spill comparison never diverges, not even once, not even at
`PIPELINE2_CREATED` (creating a heavily-spilling pipeline, no dispatch yet)
or `PRE_DISPATCH` (fully encoded, about to commit).

**INTERPRETED:** if a device-wide static scratch pool is registered via the
resource-map selector our interposer covers, it either (a) already exists
before `MTLCreateSystemDefaultDevice()` even returns (impossible to
distinguish from "does not exist at all" by this method, since we cannot
trace before device creation), or (b) is not visible through this boundary
at all — e.g. firmware-resident, never registered through the userspace
resource-map call, or registered through a call this interposer does not
cover (`IOConnectMapMemory`/`IOConnectCallAsyncMethod`; see
"Limitations"). This is the **same negative** EXP-0041/EXP-0107 found at
dispatch-time steady state, now independently confirmed at **six points
spanning the entire process lifetime**, with the two process variants
otherwise identical. It is the strongest form of this negative this
project has produced: not merely "no correlation with pressure," but "no
difference whatsoever, anywhere in the traced lifecycle, between a process
that spills and one that provably never does."

**A structural, appropriately-hedged partial lead (not promoted further):**
of the 9 BOs added at `PIPELINE2_CREATED`→`PRE_DISPATCH` (command encoding),
two sizes (16,384 B and 262,144 B) numerically coincide with two outputs of
mesa's own `block_size_bytes = 128 << (2·log4_bsize)` formula (log4=2 and
log4=4 respectively) — but both appear **identically in both variants**,
which is exactly what a genuinely demand-independent shared pool would look
like, and is equally consistent with these being ordinary command-encoding
state buffers that happen to be power-of-two sized. Content of these BOs
was not decoded; this is recorded as `STRUCTURAL`-strength, not promoted to
`INFERRED`.

**Cross-experiment corroboration:** the 14,336 B region at VA
`0x6f00000000` (present from `DEVICE_CREATED` onward, before anything else)
matches EXP-0108's own "one distant, unclassified one-off region" finding
exactly (same VA, same size) — independent confirmation that this trace is
seeing the same hardware/driver state EXP-0108 saw, strengthening
confidence in the negative rather than being a new lead.

## 2. H3 — OBSERVED: exact, stage-uniform compile-time ceiling

`harness/ceiling.m` (compile + pipeline-creation only, **no dispatch** —
independently re-confirming EXP-0107 Sec. 4's finding that the ceiling is a
pure compile-time property, via a completely different code path that
never specifies a grid or threadgroup at all) drove `casematrix.
run_bisection()`, a deterministic binary search from `K_LOW=1,024`
(established-OK) to `K_HIGH=131,072` (mesa's own `AGX_MAX_SCRATCH_DWORDS`,
used explicitly as the search target per the dispatch brief, not assumed to
apply). Both bracket points held their expected direction in every trial
(no hardcap escalation needed), and bisection converged, **for all three
of CS/VS/FS independently, to the identical boundary**:

| stage | last success K | first failure K | last success bytes (4K+16) | n trials |
|---|---:|---:|---:|---:|
| cs | 65,431 | 65,432 | 261,740 | 19 |
| vs | 65,431 | 65,432 | 261,740 | 19 |
| fs | 65,431 | 65,432 | 261,740 | 19 |

Byte-identical across both gated runs for all three stages (`b_trials_
sha256`/`b_results_sha256` run01 == run02, all 57 trials plus 3 summaries).
Failure mode at the boundary: `newComputePipelineStateWithFunction`
(CS) / `newRenderPipelineStateWithDescriptor` (VS/FS) returns a clean
`nil` with the public error string `"Compute function exceeds available
stack space"` — no crash, no timeout, no device fault, matching EXP-0107's
own characterization exactly.

**Monotonicity spot-check (adversarial, per `PRE_REGISTRATION.md`'s stated
confounder):** K=60,000 (below boundary) and K=70,000/100,000/131,072
(above) were independently re-tested for all three stages, outside the
bisection algorithm itself — every point held the expected direction, no
oscillation found (informational/exploratory, `work/`-only, not part of the
gated schema, reported here for the record).

### H3 ceiling relationship to mesa's `AGX_MAX_SCRATCH_DWORDS`

`last_ok=65,431` (K, ≈ dwords in mesa's own compiler accounting) vs mesa's
`AGX_MAX_SCRATCH_DWORDS=131,072`: **ratio 2.0032×** — real and
stage-uniform, not noise (identical to 4 significant figures across CS/VS/
FS and across both runs). Applying mesa's OWN byte→dwords conversion
formula (`agx_compile.c`: `scratch_size_B = align(declared_bytes, 16)`;
`stack_size = align(ceil(scratch_size_B/4) + 10, 4)`) to our measured
261,740 B boundary gives `stack_size = 65,448` dwords — **ratio to
131,072 = 2.0027×**, marginally closer to exactly 2 than the raw K
comparison (65,431 vs 65,536) but still not exact. **The ~2x relationship
is real; the residual ~0.1–0.3% is not resolved by this experiment** — it
is not a clean dword-vs-byte units artifact (that would give exactly 1x or
4x, not ~2x), and Apple's own Metal/AGX compiler is a completely different,
closed implementation from mesa's asahi NIR backend, so an exact match to
mesa's own accounting constants was never guaranteed. The most defensible
reading: **mesa's `AGX_MAX_SCRATCH_BLOCK_LOG4=6` (hence
`AGX_MAX_SCRATCH_DWORDS=131,072`) — already flagged in mesa's own source as
"Unknown if this goes higher" — is measured, on this Apple9 hardware, to be
too high by very close to a factor of 2** for the compile-time per-thread
stack ceiling; this experiment does not determine whether that is because
the true hardware limit is `AGX_MAX_SCRATCH_BLOCK_LOG4=5` (which would
actually predict a 4x gap, not 2x — so this alone does not explain it
either) or some other accounting difference specific to Apple's own
compiler.

## 3. H4 — OBSERVED: concurrent pressure produces a real, session-variable failure mode

`harness/concurrent.m` (N `MTLCommandQueue`s, one `MTLDevice`, all
committed before any awaited, K=24,576, grid=65,536) ran 6 independent
trials at each of `n_queues` ∈ {1,2,4,8,16,32}, in both gated runs (the
design was revised mid-experiment from a single-trial escalation ladder
after reconnaissance showed the failure mode is intermittent, not a
monotonic wall — see `PRE_REGISTRATION.md` addendum 2):

| n_queues | run01: ok/degraded/6 | run01 execfail/nonfinite/mismatch (totals) | run02: ok/degraded/6 | run02 totals |
|---:|---|---|---|---|
| 1 | 6/0 | 0/0/0 | 6/0 | 0/0/0 |
| 2 | 6/0 | 0/0/0 | 6/0 | 0/0/0 |
| 4 | 6/0 | 0/0/0 | 6/0 | 0/0/0 |
| 8 | 3/3 | 7/0/3 | 6/0 | 0/0/0 |
| 16 | 0/6 | 5/0/45 | 6/0 | 0/0/0 |
| 32 | 4/2 | 2/0/21 | 4/2 | 0/0/48 |

**OBSERVED, both runs agreeing:** `n_queues` ≤ 4 is **always** clean (12/12
trials OK across both runs, 0 failures of any kind). Some level ≥ 8 always
eventually fails in both runs. The dominant failure signature at the
highest-pressure levels is `checksum_mismatch` (queues that complete
without a Metal-reported error, with finite output, but a **numerically
wrong answer** relative to the single-queue reference) — not `EXEC_FAIL`
(an outright Metal-reported command-buffer error) and not `NONFINITE_
OUTPUT` (garbage/NaN). This is a materially different, and more
concerning, failure class than anything EXP-0041/EXP-0107 observed: **it
is silent numerical corruption under load**, not a clean rejection.

**OBSERVED, runs disagreeing:** the exact `n_queues` where failures begin,
and their severity, differ substantially between the two runs (run01:
first failures at 8, worst at 16 with 45 mismatches/6 trials; run02: clean
through 16, first failures only at 32, with 48 mismatches at that level).
This is why the per-trial outcome fields are excluded from the cross-run
byte-exact gate (`casematrix.C_NONDETERMINISTIC_TRIAL_KEYS`) — proven, not
merely asserted, by `verify.py --selftest`'s dedicated tolerance case.

**INTERPRETED:** this is consistent with a genuinely shared, capacity-
limited resource whose effective headroom varies with ambient system state
(other processes, thermal state, scheduler decisions) rather than a fixed
architectural constant tied only to `n_queues` — exactly the kind of
behavior a device-wide pool contended by concurrent GPU clients would
produce, though this experiment does not and cannot prove the specific
mechanism (it is equally consistent with contention over some other shared
GPU resource, not necessarily the scratch pool specifically). **What is
established, reproducibly, in both runs:** (1) `n_queues` ≤ 4 is safe in
the tested range; (2) some level of concurrent pressure beyond that
produces real, non-crash, non-timeout, silently-wrong output; (3) the
onset threshold is not a fixed constant across sessions on this hardware.

## Exact tested range

- **I family:** 2 process variants (nospill/spill) × 6 checkpoints, K=24,576
  spill kernel, grid=65,536, threadgroup=256. 2 gated runs, byte-identical.
- **B family:** K ∈ [1,024, 131,072] bracket, bisected to adjacent-K
  (4-byte) resolution, independently for CS/VS/FS. 57 gated trials + 3
  results, byte-identical across 2 runs. Adversarial spot-check at
  K ∈ {60,000, 65,431, 65,432, 70,000, 100,000, 131,072} (exploratory,
  informational).
- **C family:** `n_queues` ∈ {1,2,4,8,16,32}, 6 repeats each, K=24,576,
  grid=65,536, threadgroup=256. 2 gated runs (72 trials each), structural
  fields byte-identical, outcome fields legitimately nondeterministic
  cross-run (see above).
- **Target:** local M4/G16G only (`CLAUDE.md` target discipline). No A18 Pro
  replication.

## What P0.1 still requires

- **Helper program `binary`/`cfg`/`data` tags, scratch header/block-list/
  bucket/topology geometry:** still completely unestablished. This
  experiment adds a third independent negative (init-time, not just
  dispatch-time) but does not locate the mechanism.
- **Whether the macOS boundary can ever answer this at all:** after three
  independent methods (EXP-0041's narrow allowlist, EXP-0107's wide-content
  dispatch-time sweep at 454x pressure, this experiment's init-time
  lifecycle trace) all reach the same negative, the honest conclusion is
  that **the scratch/helper mechanism is not observable from userspace's
  own IOKit resource-map boundary on macOS**, within the scope this
  project's DATA-TRACE tooling covers (`IOServiceOpen`/
  `IOConnectCallMethod` only — see Limitations). A Linux implementer should
  not expect a captured Apple template for this UAPI struct; the helper
  program and scratch-pool layout most likely need to be **constructed
  from first principles against the hardware's actual behavior** (ISA-level
  spill/fill instruction semantics, the exact compile-time ceiling this
  experiment establishes, and whatever the kernel/firmware team can observe
  from their own privileged vantage point), not decoded from a macOS
  capture.
- **The exact compile-time per-thread scratch ceiling is now established**
  (261,740 B declared / K=65,431, stage-uniform, HW-VALIDATED, both runs
  byte-identical) — this is a concrete, usable number for a driver's own
  validation/rejection logic, independent of whatever the true pool
  geometry turns out to be.
- **Concurrent-exhaustion failure mode is now established as real and
  characterized** (silent numerical corruption above some session-variable
  `n_queues` threshold, never below `n_queues=4` in the tested range) —
  DATA-TRACE/HW-PROBE evidence a driver's own concurrency-limiting logic
  (if any is needed) should account for; the mechanism producing it (pool
  contention vs. something else) remains unestablished.
- **A18 Pro replication:** out of scope (target discipline).

## Limitations

- The interposer covers only `IOServiceOpen`/`IOConnectCallMethod`;
  `IOConnectMapMemory`/`IOConnectCallAsyncMethod`/mach-message-level traffic
  are not interposed (same scope as EXP-0041/EXP-0107) — a mechanism living
  exclusively behind one of those calls would not be observable here.
- Selector-5 "shared pages" content capture is best-effort and was never
  exercised in either run (selector 5 was never called during this
  experiment's traced call sequence, in either variant, either run) — this
  neither confirms nor refutes anything about the doorbell mechanism
  `docs/kernel-interface.md` already documents as not observable from this
  boundary; it is an honest, reproduced null result for this specific
  avenue.
- The code window's pre-first-compile content (whether Apple-resident code,
  reserved-but-uninitialized memory, or something else) was deliberately
  never determined — out of scope by clean-room design, not merely
  untested.
- H4's mechanism is not established, only its existence, onset range, and
  failure signature.
- H3's ~2x-not-exactly-2x residual against mesa's constant is reported, not
  resolved.
- No A18 Pro replication.
- `raw/` totals ~7.4 MB across 2 real captures + 3 disclosed superseded
  attempts (plain-text hex/JSON only, no binaries; code-window content
  redacted-to-hash in the relevant superseded directory).

## Gate results

`verify.py --selftest`: PASS (clean tree accepted; 7/7 injected defects
correctly rejected — missing file, extra nondeterministic-shaped key in
both `c_levels` and `i_checkpoints`, missing schema key, corrupted summary
hash, run01/run02 semantic divergence in a gated field, authored-code hash
drift — plus 1/1 documented-nondeterministic-field-only divergence
correctly tolerated for both the pre-existing `bo`-style case and this
experiment's own new C-family case).
`verify.py --seqtest`: PASS (`--preflight`/`--between-runs`/`--captured`
each satisfiable only in their own tree state — `PRE_GPU`/
`RUN01_PRESENT`/`RUN02_PRESENT`).
NON-RECORDED smoke gate: PASS, both official run attempts (one I-family
nospill checkpoint walk + one B-family trial + one C-family n_queues=1
level, into `work/`, before any `raw/` artifact).
`verify.py --check` (officially gated pair `m4-20260828-run01`/
`m4-20260828-run02`): **PASS.** All 5 gated files, all families, byte-exact
on every `GATED_*_KEYS` field; only the documented C-family nondeterministic
outcome fields differ, as designed and proven tolerable by selftest.

## Files

- `PRE_REGISTRATION.md` (+ 2 addenda), `CAPTURE_CONTRACT.json` — frozen
  hypotheses and the two disclosed mid-experiment corrections.
- `harness/inittrace.c`, `harness/initprobe.m` — I family.
- `harness/ceiling.m` — B family.
- `harness/concurrent.m` — C family.
- `kernels/kernelgen.py` — authored MSL generator.
- `casematrix.py`, `traceparse.py` — single source of truth + parsing.
- `run.py`, `verify.py` — capture runner and the five standing gates.
- `raw/m4-20260828-run{01,02}/` — the two real, gated captures.
- `raw/SUPERSEDED_m4-20260828-run01_{missing-analysis-script,
  codewindow-precompile-content,c-family-single-trial-design}/` — three
  disclosed, retained, non-evidence attempts (see each `SUPERSEDED.md`).
- `analysis/analyze.py` — per-run human-readable report;
  `analysis/report_run{01,02}.txt` — generated reports.
- `analysis/redact_codewindow.py` — the one-shot redaction tool used on the
  code-window-content superseded directory.
- `manifest.json` — hashes of every committed artifact.

# EXP-0125 pre-registration — scratch/helper mechanism located by INIT-TIME trace + bisected compile ceiling + concurrent exhaustion

Date frozen: 2026-08-28. Target: local Apple M4 / G16G only (`CLAUDE.md` target
discipline; A18 Pro is hands-off, never touched, never SSH'd, never
`macvdmtool`'d). Frozen git revision: `87d02c34f56357734f448695cf62d37ab555fcb0`
(informational provenance only — see `CAPTURE_CONTRACT.json` — never a live
gate; other in-flight sibling experiments (EXP-0112..0124) may move HEAD
during this experiment's own execution, which is not contamination).

## Predecessors and why the method must change (not repeat)

- **EXP-0041** (208–576 B declared scratch, 4-BO allowlist trace): found
  nothing correlated.
- **EXP-0107** (up to 261,728 B/thread, ~454x EXP-0041's range, CS/VS/FS, up
  to 4,194,304 threads, full-content-prefix trace of *every* BO the process
  maps — not an allowlist): found nothing correlated with declared scratch at
  the resource-map level, **at dispatch time**, but did locate a precise
  compile-time ceiling (last success K=65,430/261,728 B; first failure
  K=65,440) and made a strong *indirect* argument (a naive
  `declared_bytes × total_threads` allocation at K=65,430/grid=4,194,304 would
  need ≈1.10 TB on a 16 GB host, yet the dispatch completed correctly) that
  whatever backs scratch is bounded/pooled by hardware concurrency, not by
  per-thread declared size times total dispatched threads.
- **The reason both negatives are expected, not just unlucky:** the pinned
  Asahi UAPI header (`mesa/include/drm-uapi/asahi_drm.h`,
  `struct drm_asahi_helper_program`, ~line 881) states the helper program
  "dynamically allocat[es] scratch/stack memory for individual subgroups, by
  partitioning **a static allocation shared for the whole device**" and is
  "**internally dispatched by the hardware as needed**." A pool allocated
  ONCE, device-wide, and sized independent of demand will not correlate with
  a per-dispatch pressure sweep at STEADY STATE — the pool, if visible at
  all, should already exist BEFORE the first spilling dispatch, and should be
  IDENTICAL in size whether or not spilling ever occurs. A hardware-dispatched
  helper program never appears in userspace's own submission/command-stream
  records by construction — it can only show up as a static resource
  registered once (an executable-code-shaped or scratch-shaped BO), not as a
  per-dispatch event. **This is why this experiment traces the
  device/queue/pipeline-creation LIFECYCLE, not another dispatch-time
  pressure sweep**, and separately bisects the compile-time ceiling
  EXP-0107 located but did not resolve to an exact byte, and separately
  probes concurrent (not sequential) pressure, which neither predecessor
  reached.

## Question and driver decision

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-UAPI-01 / `docs/P0-P1-CLOSURE.md` row
P0.1 requires: helper program `binary`/`cfg`/`data` tags, scratch header/
block-list/bucket/topology geometry, and growth/failure/concurrency semantics
— all assigned to **userspace** by the unchanged UAPI. This experiment asks,
via three independent methods:

- **H1/H2 (init-time trace):** does a device-wide, demand-independent pool
  and/or a distinct helper-program binary appear in userspace's own IOKit
  boundary traffic BEFORE any spilling work exists, and does it differ
  between a process that never spills and one that spills heavily?
- **H3 (ceiling bisection):** what is the EXACT compile-time per-thread
  scratch ceiling on this hardware, per stage (CS/VS/FS), and how does it
  relate to mesa's own `AGX_MAX_SCRATCH_DWORDS` (131,072) constant —
  is the ~2x gap EXP-0107 flagged (last success ≈65,432 dwords vs mesa's
  131,072) real, and is it stage-uniform?
- **H4 (concurrent exhaustion):** under GENUINE concurrent GPU-side pressure
  (many queues committed before any is awaited) instead of EXP-0107's
  sequential single-dispatch sweep, does the (hypothesized) shared pool
  degrade, serialize, fault, or corrupt — and at what queue count, if any?

The driver decision: whether any of the three methods locates the pool/
helper directly (letting P0.1 proceed to field-level decoding), or instead
extends the negative to a THIRD independent vector (init-time presence,
compile-time ceiling exactness, and concurrent behavior) — in which case the
UAPI-required split can no longer be characterized as "not yet tried hard
enough" and the honest conclusion becomes "not observable from the macOS
boundary at all," which is itself the answer P0.1 needs to record before a
Linux implementer is told to construct the helper program from scratch.

## Falsifiable hypotheses

- **H1 (device-wide, demand-independent pool, visible at init).** A BO whose
  (class, size) is IDENTICAL between the "nospill" and "spill" process
  variants at every checkpoint UP TO AND INCLUDING `PIPELINE2_CREATED`
  (i.e., before any dispatch), but which is ABSENT in some earlier
  no-device/no-queue state, is the pool. *Falsified* if no such BO exists —
  i.e., the (class,size) resource-map shape at every checkpoint is IDENTICAL
  between the two variants at every one of the six checkpoints, including
  post-dispatch (this is the outcome EXP-0107 itself measured at
  steady-state dispatch time; H1 asks whether it ALSO holds at
  device/queue/pipeline-creation time, before pressure exists at all).
  *Confounder:* an allocation that depends on OS/process-level nondeterminism
  (allocator placement, warm vs cold cache) rather than on GPU scratch demand
  — controlled by requiring the finding to be class+size stable across BOTH
  gated runs (run01/run02), not just within one run's nospill/spill pair.
- **H2 (distinct helper-program binary observable pre-dispatch).** A
  BO/region whose class or location is consistent with executable code
  (the EXP-0042/EXP-0108 code window at VA `0x10000000000`, or any newly
  registered region) exists BEFORE our own first compiled pipeline (i.e., at
  `DEVICE_CREATED` or `QUEUE_CREATED`) or grows/appears independent of our
  own compiled function count. *Falsified* if the code window is absent
  until our own first pipeline compiles and its size never exceeds what our
  own compiled functions plausibly account for (EXP-0108: constant
  `0x10000` B across 40 render configurations) — i.e., no evidence of a
  separate, pre-existing, or additionally-appearing helper program.
- **H3 (ceiling is exactly at/near a clean boundary, and is stage-uniform).**
  Each of CS/VS/FS has a compile-time-rejection boundary
  (`newComputePipelineStateWithFunction`/`newRenderPipelineStateWithDescriptor`
  → "Compute function exceeds available stack space" or equivalent) at K
  (array-loop elements ≈ declared scratch dwords) within [K_LOW, K_HIGH]
  (1,024 – 131,072 — the upper bound is mesa's own `AGX_MAX_SCRATCH_DWORDS`,
  used here explicitly as a search target, not an assumption). *Falsified
  for "stage-uniform"* if CS/VS/FS boundaries differ by more than a small
  constant offset (consistent with each stage's own fixed compiler
  bookkeeping overhead, e.g. mesa's own `+10` dwords fudge in
  `agx_compile.c`) — a large stage-to-stage difference would mean the
  ceiling is NOT a single shared hardware/pool constant but a per-stage
  compiler policy. *Falsified for "within bracket"* if even K_HIGH (131,072)
  succeeds (ceiling ≥ mesa's constant, contradicting EXP-0107's ~2x-lower
  measurement) or if K_LOW (1,024) itself fails (no valid bracket at all;
  bisection reports this explicitly rather than guessing).
- **H4 (concurrent pressure degrades/serializes/faults/corrupts a shared
  pool).** As `n_queues` escalates (1→32, all committed before any awaited,
  each running a real, EXP-0107-validated-safe K=24,576 spill workload),
  SOME level shows non-`OK` status: an `EXEC_FAIL` (fault/error surfaced by
  Metal), a wall-clock cliff (serialization, not observable as a hard
  failure but visible in `03_timing.jsonl`'s ungated timing), a checksum
  mismatch between queues (silent corruption), or a process timeout (hang).
  *Falsified* if every tested `n_queues` level completes with `status=OK`,
  all queues individually `OK`, and all checksums match the single-queue
  reference — i.e., no exhaustion signature found in the tested range
  (1–32 queues × K=24,576 × grid=65,536).

## Independent/controlled variables

- **I family:** independent = variant (nospill/spill); controlled = every
  other lifecycle step (device creation, queue creation, first pipeline,
  dispatch grid/threadgroup, input data). Both variants create exactly two
  pipelines and dispatch exactly once, so checkpoint COUNT and STRUCTURE are
  identical; only the SECOND pipeline's kernel and the dispatch's actual
  scratch demand differ.
- **B family:** independent = K (per stage, chosen by deterministic
  bisection); controlled = kernel shape (identical array-loop design across
  all K, so compiled code size stays flat — EXP-0107's own established
  design rationale, reused here), stage-specific harness path.
- **C family:** independent = n_queues; controlled = per-queue kernel (fixed
  K=24,576), grid, threadgroup, input data — identical to the I-family spill
  kernel's K, chosen because EXP-0107 already validated it correct at up to
  grid=1,048,576 run ALONE, so any failure at higher n_queues here is
  attributable to concurrency, not to K itself being unsafe.

## Expected observations if hypotheses are TRUE vs FALSE

See the falsifier clause embedded in each hypothesis above; RESULTS.md
reports the actual outcome against each, explicitly, per hypothesis.

## Known confounders

- **Allocator/OS-level nondeterminism.** BO placement addresses are excluded
  from every gated schema (address-free `resource_map_shape`); cross-run
  (run01 vs run02) reproducibility of `nbo`/`bo_total_bytes`/shape is the
  actual falsification bar, not single-run repeatability.
- **`mach_absolute_time()` values** are process-relative and not expected to
  reproduce run-to-run; excluded from every gated schema (see
  `CAPTURE_CONTRACT.json`'s `excluded_nondeterministic_fields`), retained
  only in the ungated `dumps/*.checkpoints.jsonl`/trace logs for ordering
  cross-checks.
- **Selector-5 "shared pages" content is EXPLORATORY, best-effort, and NOT
  gated.** `docs/kernel-interface.md` already documents that the CPU→GPU
  doorbell store itself is "not observable from the userspace interposer."
  `harness/inittrace.c`'s attempted read of the two selector-5 output
  pointers may find nothing, find unrelated queue-context state, or fail
  closed (invalid address) — any of these is a legitimate, reported outcome,
  not evidence either way about the doorbell itself.
- **The interposer covers only `IOServiceOpen`/`IOConnectCallMethod`.**
  `IOConnectMapMemory`/`IOConnectCallAsyncMethod`/mach-message-level traffic
  are NOT interposed (same scope as EXP-0041/EXP-0107); a mechanism that
  lives exclusively behind one of those calls would not be observable here.
  This is stated as a limitation, not silently assumed away.
- **Compiler/runtime caching.** `newLibraryWithSource:` may cache compiled
  artifacts across processes; each B-family trial and each I-family variant
  runs in its own fresh process (no cross-process compiler cache reuse
  assumed to matter for BO *registration* behavior, only for compile speed).
- **The B-family bracket assumes monotonicity** (once compilation fails at
  some K, it fails for all larger K, for a fixed stage). This is consistent
  with EXP-0107's own full K-sweep (single crossover, no oscillation
  observed from K=8 to K=65,440) but is stated as an assumption; RESULTS.md
  records a small adversarial post-bisection spot check (a few K values
  above the found boundary re-tested) rather than asserting monotonicity
  unchecked.
- **C-family "concurrent" is limited to multiple queues within ONE process
  on ONE `MTLDevice`.** A genuinely cross-PROCESS concurrency test (multiple
  OS processes contending for the same physical device/pool) is explicitly
  OUT OF SCOPE for this registration (safety/complexity budget); if reached
  as a stretch, it is reported separately and not folded into the gated
  C-family schema.

## Method summary (full detail: harness/*, casematrix.py)

- **I family:** `harness/initprobe.m` (public Metal API), DYLD-interposed by
  `harness/inittrace.c` (public IOKit surface only), SIGUSR1-triggered
  checkpoint dumps. 2 variants × 6 checkpoints = 12 gated checkpoint records
  + 2 summary records per run.
- **B family:** `harness/ceiling.m` (compile + pipeline-creation only, no
  dispatch), driven by `casematrix.run_bisection()` (pure, deterministic
  given a reproducible oracle) for each of CS/VS/FS. ~15–20 trials/stage
  expected (bracket-finding + binary search to adjacent-K resolution).
- **C family:** `harness/concurrent.m` (public Metal API, N
  `MTLCommandQueue`s from one device, all committed before any awaited).
  6 escalating levels (1/2/4/8/16/32 queues), escalation-stop policy on
  first non-`OK` level (later levels recorded `executed=false`).

## Standing gates (all five, `verify.py`)

`--selftest` (synthetic-fixture accept/reject, 7 injected defects);
`--seqtest` (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT); a NON-RECORDED smoke gate
in `run.py` before any `raw/` artifact; schema-exactness (`==` key-set match
against `casematrix.py`'s `*_KEYS`, which contain no GPU address or
timestamp field by construction — proven, not just asserted, by the selftest
mutation cases); fixtures built FROM RECORDED REALITY (the real
`casematrix.py` constants and the real `run_bisection()` algorithm).

## Addendum (2026-08-28, before any gated capture is promoted): code-window content exclusion

A dry run under the originally-written `harness/inittrace.c` (which captured
a content prefix of every registered BO unconditionally, inherited from
EXP-0107's `harness/maptrace.c`) found that the EXP-0042/EXP-0108-established
code-window BO (VA `0x10000000000`) already exists and has non-zero content
at checkpoint 0 (`DEVICE_CREATED`) — **before** this process has compiled any
MSL of its own. Unlike EXP-0107 (whose single capture always happened after
our own shader had already compiled, making any code-window content
attributable to OWN-SHADER), this experiment's I family captures before that
attribution holds. `EXP-0108-m4-bg-eot-programs/harness/wtrace.c` already
established the correct, reviewed policy for exactly this risk — exclude the
code-window VA range `[0x10000000000, 0x10000020000)` from content capture
entirely, recording only presence/size — and `harness/inittrace.c` did not
originally carry that exclusion forward. It has been corrected to do so (see
the `CODE-WINDOW CONTENT EXCLUSION` comment in `harness/inittrace.c`); the
first (content-uncorrected) `m4-20260828-run01` capture is retained,
disclosed, and its code-window content redacted-with-hash, at
`raw/SUPERSEDED_m4-20260828-run01_codewindow-precompile-content/`. This
addendum does not change any hypothesis, falsifier, variable, or gated
schema above — `code_window_present`/`code_window_size` (both already
content-free, structural fields) are unaffected; only the underlying content
CAPTURE mechanism, which was never part of the gated schema in the first
place, is corrected.

## Addendum 2 (2026-08-28, before any gated C-family capture is promoted): repeats, not a single ladder

Pre-capture reconnaissance for the C family (non-recorded, `work/`-only,
standard practice for calibrating a design before it is gated -- same
status as EXP-0107's own pre-registration-stage boundary reconnaissance)
found the originally-registered design ("escalate n_queues, stop the ladder
at the first non-`OK` level") does not fit the observed failure mode: FOUR
repeated trials at the SAME `n_queues=4` in the same short session produced
3x `STATUS OK` and 1x a real `EXEC_FAIL` cascade (3 of 4 queues failed
outright; the 4th reported `STATUS OK` with a zero checksum); a follow-up
8-trial batch at `n_queues=4` and `n_queues=8` then ran clean 8/8 at both.
This is an INTERMITTENT, low-frequency degradation, not a monotonic
"N and above always fails" wall — a single-trial-per-level ladder would
either wrongly report a clean bill of health (if the flake didn't land on
the tested trial) or wrongly stop escalation early (if it did), neither of
which honestly characterizes the phenomenon.

**Design revision:** each of the six `n_queues` levels (1/2/4/8/16/32) now
runs `C_REPEATS=6` independent trials, unconditionally (no escalation-stop
— a flake at a low level must not suppress data at higher levels); the
reported finding is the PER-LEVEL FAILURE RATE across repeats, not a single
pass/fail. Only a hard fault (process timeout, or an exit code outside
{0,1}) aborts the run early — that remains a genuine safety stop, unchanged
from the original registration.

**Consequence for the gate:** the per-trial outcome fields (`status`,
`ok_queues`, `execfail_queues`, `nonfinite_queues`, `checksum_mismatch`) are
therefore this experiment's own directly-observed NONDETERMINISTIC fields —
the C-family analogue of EXP-0107's discovery that `bo_content_seq_sha256`
did not reproduce cross-run. They remain in the full per-trial schema
(`casematrix.C_TRIAL_KEYS`, so an extra/missing key is still caught by
schema-exactness) but are excluded from the cross-run byte-exact comparison
(`casematrix.C_GATED_TRIAL_KEYS` = `C_TRIAL_KEYS` minus those five fields);
`verify.py --selftest` gained a dedicated case proving a run01/run02 tree
that differs ONLY in the nondeterministic fields still PASSES
`gate_captured`, mirroring EXP-0107's own proof for its analogous
exclusion. This is a data-capture/schema revision made BEFORE any gated
capture was promoted as evidence (the two "SUPERSEDED_..." directories in
`raw/` predate it and were superseded for unrelated reasons); H4's
falsifier is unchanged in substance — "does concurrent pressure ever
produce a non-`OK` outcome in the tested range" — only the reporting unit
(rate over repeats, not one pass/fail per level) is revised to fit what was
actually observed.

## Clean-room boundary (see also each RESULTS.md attestation)

Public Metal API only for all compilation/dispatch (`harness/initprobe.m`,
`harness/ceiling.m`, `harness/concurrent.m`); DATA-TRACE of our own process's
IOKit boundary traffic via `harness/inittrace.c`, an interposer over the
public `IOServiceOpen`/`IOConnectCallMethod` surface, reading only memory
this process itself has registered/mapped; PUBLIC reference reading of
`mesa/include/drm-uapi/asahi_drm.h` and `mesa/src/asahi/lib/agx_scratch.{h,c}`
for search-target constants only (never copied, never treated as Apple9
ground truth). No Apple binary, framework, kext, or firmware is ever opened,
disassembled, or introspected.

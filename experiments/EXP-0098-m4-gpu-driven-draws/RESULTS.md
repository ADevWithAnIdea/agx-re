# EXP-0098 RESULTS — M4 GPU-driven draws (Bundle H) and compute-emulated transform feedback (Bundle I)

**Target: local Apple M4 (G16G) only**, Mac16,10, macOS 26.6.2 (25G82), Metal 4, 10 GPU cores.
**No A18 Pro claim anywhere in this document** (A18 hands-off; every finding below is M4-only
unless explicitly marked otherwise). Two official capture runs (`raw/m4_20260828_run01b/`,
`raw/m4_20260828_run02b/`), **111 cases each, byte-identical (modulo declared order-sensitive
keys) from pinned revision `39af7f9314e5d6c49eea21465cd02682bf48d117`**. **Cross-run gate: PASS,
0 issues.** Both runs: **78 PASS, 0 FAIL, 0 TIMEOUT, 33 N/A** (the N/A cases are the
deliberately-unsynchronized/asymmetric-fence controls, whose per-trial outcome is legitimately
observational — see "Standing gate results"). `verify.py --selftest` (17/17), `--seqtest` (9/9),
`--preflight`/`--between-runs`/`--captured` all PASS. **Zero unexplained FAIL. Zero unexpected
hang.** One process-contained crash (a build-time-predicted, twice-reproduced finding, not an
anomaly — see finite-resource table) and one fault-contained GPU command-buffer error (likewise
predicted and twice-reproduced). **Zero host wedges caused by this experiment's own dispatches**
(a host restart interrupted an earlier, non-promoted capture attempt for reasons external to any
GPU dispatch this experiment made — see "Operational note" below; both official runs completed
cleanly afterward).

**Clean-room scope note, stated explicitly per the relaunch instruction:** this experiment uses
**no assembler, no `tools/agx-isa`, no native VDM/CDM grammar, and no `tools/*` of any kind** —
public Metal API surface only, per the addendum's own instruction for Bundles H and I. The
`db.json` ALU source-register decoding-bug analysis (`work/COMPILER-EXPLAINER-INTERACTION-20260828.md`)
and its confirming experiment (`EXP-0099`, refuting both proposed ALU register-lifetime models) are
therefore **structurally inapplicable** to anything in this document; nothing here depends on, cites,
or could be affected by either.

## Headline verdicts

| item | verdict | evidence class |
|---|---|---|
| **GLPRE-A01** (compute-to-draw visibility for GPU-generated geometry/parameter/indirect-draw records) | **YES for `encoder_order` and `fence_sym`; NO guarantee otherwise — `HW-VALIDATED`.** A compute-shader-written vertex buffer + indirect-draw-argument record is reliably visible to a following draw with default (Tracked) hazard tracking in a prior encoder of the same command buffer, or with an explicit symmetric `MTLFence`. Splitting producer and consumer across two command buffers with `MTLResourceHazardTrackingModeUntracked` and no fence, or a fence asserted on only one side, is **not** safe: it exposed real data staleness in every configuration tested, up to 100% of tested indices | genuinely nondeterministic (0/16 to 8/8 trials raced depending on configuration — see table below), **both official runs concur exactly on which configurations are safe vs. observationally unsafe** |
| **GLPRE-A02** (device-generated draw/index grammar, field legality, finite limits) | **All tested `MTLDraw[Indexed]PrimitivesIndirectArguments` fields are read and honored exactly as written by a compute kernel — `HW-VALIDATED`, 16/16 `h_fields` cases PASS both runs.** `[[instance_id]]` is confirmed **absolute** (`baseInstance`-inclusive), not local — a real ABI fact, not merely a harness detail. `executeCommandsInBuffer:indirectBuffer:` honors a compute-written `{location,length}` range as `max(0,min(length,maxCommandCount-location))` when `location<maxCommandCount`, but **faults** (`kIOGPUCommandBufferCallbackErrorPageFault`) when `location>maxCommandCount` — a real, sharp, twice-confirmed boundary | `HW-VALIDATED`, deterministic, byte-identical both runs |
| **GLXFB-A01** (compute-emulated transform feedback: capacity, no-partial-primitive, multistream, streamout→draw sync) | **All tested capacity/multistream/discard semantics behave exactly per the closed-form model — `HW-VALIDATED`, 32/32 `xfb_capacity`+`xfb_multistream`+`xfb_discard` cases PASS both runs.** The streamout→draw synchronization contract is the SAME safe/unsafe split as GLPRE-A01's, but Bundle I's specific (atomic-heavy) producer shows a **materially different unsafe-mode failure signature**: zero observed data staleness across 18/18 unsafe-mode trials (both runs), but a large, extremely consistent ≈15.6–15.8s completion-latency penalty (vs. ≈40ms for the safe modes) — a ≈400× slowdown, not corruption | `HW-VALIDATED` for capacity/multistream/discard; `HW-VALIDATED` (negative-for-corruption, positive-for-latency) for the sync contract's Bundle-I-specific failure mode |

## 1. GLPRE-A01 — the exact synchronization contract for compute-generated draws

### 1.1 Mechanism (public Metal API only)

Every producer/consumer pair below has the record bytes written by a compute kernel's own store
instructions (never CPU `-[MTLBuffer contents]`). "Unsynchronized" is realized with
`MTLResourceHazardTrackingModeUntracked` (`MTLResource.h`: "may optionally be specified for
non-heap resources" — public, documented Metal API, not native command-stream RE) on every
producer/consumer-shared buffer, plus two independent `MTLCommandBuffer`s on one queue committed
back-to-back with no CPU wait. See `PRE_REGISTRATION.md` for the complete mechanism description
and the six named sync strategies.

### 1.2 OBSERVED — h_sync race rates, both official runs combined (8 trials per row)

| index mode | sync mode | trials that showed `n_stale>0` | verdict |
|---|---|---:|---|
| nonindexed | `cpu_baseline` | 0/4 | always correct |
| nonindexed | `encoder_order` | 0/4 | always correct |
| nonindexed | `fence_sym` | 0/4 | always correct |
| nonindexed | `unsync_split` | **2/8** | genuinely nondeterministic |
| nonindexed | `asym_producer` | **3/8** | genuinely nondeterministic |
| nonindexed | `asym_consumer` | **5/8** | genuinely nondeterministic |
| indexed | `cpu_baseline` | 0/4 | always correct |
| indexed | `encoder_order` | 0/4 | always correct |
| indexed | `fence_sym` | 0/4 | always correct |
| indexed | `unsync_split` | **8/8** | **always raced** |
| indexed | `asym_producer` | **8/8** | **always raced** |
| indexed | `asym_consumer` | **8/8** | **always raced** |

Every safe-mode trial (`cpu_baseline`/`encoder_order`/`fence_sym`, both index modes, 24 total
trials across both runs) showed **exactly** `n_correct==n, n_stale==0`. Peak observed corruption
in an unsafe-mode trial: `n_correct=0/65536` (100% stale) for nonindexed `unsync_split`; the
indexed variant's worst trial was `n_correct=1/65536`, and its typical raced trial was
`n_correct=2/65536` (99.997% stale) — reproduced consistently in **every one of 24 indexed unsafe
trials across both runs**, not a single outlier.

**INTERPRETED.** Metal's documented automatic inter-encoder hazard tracking (default `Tracked`
mode, `encoder_order`) and an explicit symmetric `MTLFence` (`fence_sym`) are both fully sufficient
— zero staleness in 48 combined trials. Disabling hazard tracking and splitting producer/consumer
across command buffers is **not** safe even when one side still asserts a fence: `asym_producer`
(release only) and `asym_consumer` (a wait on a fence that was never updated, which Metal's fence
model treats as vacuous — nothing to wait for) are **not** meaningfully safer than no
synchronization at all, matching `EXP-0093`'s ATOM-08 finding (asymmetric device-memory fencing is
unsafe at real concurrency) **at the command-buffer/resource-hazard layer** rather than the shader
instruction layer. This experiment was explicitly run at a scale (65,536 vertices, a
100,000-iteration per-thread sequential-dependency producer workload — calibrated, see
`PRE_REGISTRATION.md` §"Build-time findings" #1) chosen to actually expose the hazard, per the
relaunch instruction, rather than at a token 1–2-element scale where `EXP-0051` originally saw
nothing.

**The indexed variant is a materially stronger (not just "also present") finding**: every one of
24 unsafe-mode indexed trials raced, vs. 10/24 for the nonindexed variant. The plausible mechanism
(not independently isolated by this experiment, flagged `INFERRED`): a stale/uninitialized index
buffer feeds directly into `[[vertex_id]]` computation, so a race corrupts not just the *data* a
vertex invocation reads but *which* vertex slot it reads from at all (`n_z_wrong` — invocations
whose raw `[[vertex_id]]` did not match their intended sequential position — was correspondingly
high in every raced indexed trial, up to 65,535/65,536), compounding the failure rather than
merely delaying visibility of otherwise-correctly-addressed data.

**Falsifier check (required per dispatch): the unsynchronized/asymmetric controls were shown to
actually break**, in both the weaker (nonindexed, genuinely intermittent — 2–5 of 8 trials) and
stronger (indexed, 8/8 trials, every trial) forms, across two independent official capture runs
that agree exactly on which configurations are safe and which are not.

## 2. GLPRE-A02 — device-generated draw/index grammar, field legality, finite limits

### 2.1 Field legality (`h_fields`, 16/16 PASS both runs, `HW-VALIDATED`)

All of `vertexCount`/`instanceCount`/`vertexStart`/`baseInstance` (non-indexed) and
`indexCount`/`instanceCount`/`indexStart`/`baseVertex`/`baseInstance` (indexed) were written by a
compute kernel and independently verified against a closed-form expected invocation count and
per-invocation data correctness (`run.py`'s formula computed independently of the ObjC harness's
own bookkeeping). Selected exact observations (both runs identical):

| case | observed | note |
|---|---|---|
| `ic_zero` (`instanceCount=0`) | `n_invoked=0` | zero-instance draw invokes nothing (not `max(instanceCount,1)` — a real build-time formula bug in this harness's OWN verdict logic was caught and fixed by this exact case; see `PRE_REGISTRATION.md` finding #8) |
| `baseinstance5_ic3` (`baseInstance=5, instanceCount=3`) | `n_invoked=24` (`=8×3`), `minIid=5, maxIid=7` | **`[[instance_id]]` is ABSOLUTE (baseInstance-inclusive)**, not a local 0-based index — discovered as a genuine ABI fact during build-time calibration (an under-sized verification buffer, sized to `instanceCount` alone, initially silently dropped these invocations) |
| `indexed_negative_basevertex` (`baseVertex=-3`, indices pre-offset `+3`) | `n_invoked=8`, `minVid=0, maxVid=7` | signed `baseVertex` correctly recombines with an unsigned fetched index to land in-range; no wraparound/fault |
| `indexed_16bit` | `n_invoked=8`, all correct | `MTLIndexTypeUInt16` works identically to 32-bit for field-legality purposes |
| `indexed_restart_sentinel` (index value `0xFFFFFFFF` at one position, `MTLPrimitiveTypePoint`) | `n_invoked=8`, `maxVid=4294967295`, all correct | the restart-sentinel index is **not specially interpreted for a non-strip topology** — fetched and consumed as an ordinary (very large) index value. Primitive-assembly-level restart-splitting is a strip-topology-specific effect **not observable by this experiment's per-vertex-invocation verification method**; explicitly deferred, `UNKNOWN`, not silently skipped |
| `indirect_offset_misaligned` (`indirectBufferOffset=2`, `indexed_offset_misaligned` likewise) | `n_invoked=8`, all correct | a non-4-byte-aligned `indirectBufferOffset` was accepted without rejection or fault in both tested cases |

### 2.2 Device-generated draw-count grammar (`h_icbrange`, 9/9 PASS both runs, `HW-VALIDATED`)

A compute kernel writes `MTLIndirectCommandBufferExecutionRange{location,length}`, consumed by
`executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:` against a fixed 8-command
CPU-pre-encoded ICB. Exact closed form, confirmed for every one of 9 cases both runs:

```
n_executed = max(0, min(length, maxCommandCount - location))   if location < maxCommandCount
n_executed = 0                                                  if location == maxCommandCount
n_executed = FAULTS (kIOGPUCommandBufferCallbackErrorPageFault)  if location  > maxCommandCount
```

The `location==maxCommandCount` and `location>maxCommandCount` cases are **not the same
behavior** — this is the sharpest single finding in this section. `location==maxCommandCount`
(`hicbrange_loc_at_max_len0`/`len1`) safely executes zero commands regardless of `length`.
`location>maxCommandCount` (`hicbrange_loc_past_max`, `location=10` against `maxCommandCount=8`)
**faults the command buffer**, reproduced identically in both official runs
(`status=CMDBUF_ERROR`, `kIOGPUCommandBufferCallbackErrorPageFault`), fault-contained both times
(host and GPU confirmed responsive immediately after). An oversized `length` alone (`length=20`
against `maxCommandCount=8`, `location=0`) is **silently clamped** to `n_executed=8`, not
rejected and not faulting.

### 2.3 Finite-resource: maximum ICB size (`h_icbmax`, `HW-VALIDATED`, both runs identical)

| `maxCommandCount` tried | result |
|---:|---|
| 1,024 | allocates, `size` reads back exactly `1024` |
| 65,536 | allocates, exact |
| 1,048,576 | allocates, exact |
| **4,194,304** | allocates, exact — **largest confirmed-working value** |
| **8,388,608** | **CPU-side process crash (`SIGSEGV`) inside `newIndirectCommandBufferWithDescriptor:` itself, before any GPU dispatch** — reproduced in both official runs plus twice during build-time calibration (4/4 total). Fault-contained to that one process each time; host and GPU confirmed responsive immediately after every occurrence |

This is a genuine **first-illegal-value** finding for the finite-resource mandate: a driver must
never let a client request an ICB in this size range — Metal's own public API provides no graceful
rejection path here, only a raw process crash. The exact boundary between 4,194,304 and 8,388,608
was not narrowed further (not required by the addendum; a coarse, confirmed bracket is sufficient
to document the hazard and is cheaper/safer than a fine binary search that would multiply the
crash count for no additional driver-relevant precision).

## 3. GLXFB-A01 — compute-emulated transform feedback

### 3.1 Mechanism

`kernels/xfb.metal`'s `xfb_capture` models the OpenGL transform-feedback capture stage: one thread
per synthetic input primitive, up to four independent streams, each reserving whole-primitive
vertex blocks via `atomic_fetch_add` and writing only if the reservation fits the declared
capacity (see `PRE_REGISTRATION.md` H4). `xfb_finalize` (a second compute kernel) copies the
captured `written` counter into a `MTLDrawPrimitivesIndirectArguments.vertexCount` field — the
same compute-writes-the-indirect-record pattern as Bundle H, reused for the streamout-generated
replay draw.

### 3.2 Capacity / no-partial-primitive / multistream (`xfb_capacity`+`xfb_multistream`+`xfb_discard`, 32/32 PASS both runs, `HW-VALIDATED`)

Every case matched the closed form `written = floor(min(requests, capacity/vpp)) × vpp` **exactly**
across both runs, with **zero** partial-primitive writes detected (a phase-correct byte-wise scan
of the buffer at the computed written-boundary; a build-time bug in this exact check — a
4-byte-aligned comparison against a repeating sentinel pattern, invalid at non-4-byte-aligned
boundaries — was caught and fixed by the deliberately-misaligned-stride/offset case before the
official captures). Selected exact observations:

| case | observed | interpretation |
|---|---|---|
| `cap_one_short` (`64` triangles, capacity for `63.67` triangles) | `gen=64, wr=189 (=63×3)`, `noPartialAtBoundary=1` | exactly the last WHOLE triangle fits; the would-be-64th triangle is dropped in its entirety, not partially written |
| `cap_zero` | `gen=64, wr=0`, `noPartialAtBoundary=1`, `replay_vertexCount=0` | `GL_PRIMITIVES_GENERATED`-equivalent counter still counts all 64 even though none were written — matches OpenGL's generated-vs-written distinction |
| `gsshaped_replay0`/`replay1` (one primitive → stream0 @ 3 verts/prim AND stream1 @ 1 vert/prim, simultaneously) | `wr0=96 (=32×3), wr1=32 (=32×1)`; replaying stream0 draws 96 vertices, replaying stream1 draws 32 | a single synthetic "GS-shaped" producer correctly fans out **different vertex counts to different streams from the same primitive**, and each stream's replay is independently addressable |
| `discard_on` | capture proceeds (`wr0=48`) but `n_invoked=0, replay_vertexCount=0` | rasterizer-discard-equivalent: the capture pass is unaffected; only the replay draw is skipped |
| `interleaved_2attr` (two attributes, one buffer, offsets 0/16, stride 32) | `wr0=wr1=30`, `noPartialAtBoundary=1` for both | interleaved dual-attribute layout works with independent per-stream atomic counters into shared buffer regions |
| `misaligned_stride_off` (`stride=17, offset=3`) | `wr0=60`, `noPartialAtBoundary=1` | arbitrary (non-power-of-2, non-4-byte-aligned) byte stride/offset is correctly handled by the byte-wise capture kernel |

### 3.3 Streamout → draw synchronization contract — a materially different failure signature than Bundle H

The same six sync labels apply to the (capture+finalize compute encoder) → (replay render draw)
handoff (`xfb_sync`, `numPrimitives=4096`, `spinIters=500000`, `cap0=20000`, single stream).
`encoder_order`/`fence_sym` were correct in all 4 combined trials (`n_stale=0`, exact expected
`replay_vertexCount`), matching Bundle H exactly.

**The unsafe modes did NOT reproduce Bundle H's data-corruption signature** — 0/18 combined
trials across both official runs showed `n_stale>0` for `unsync_split`/`asym_producer`/
`asym_consumer` — **but every one of those 18 trials showed a large, extremely consistent
completion-latency penalty**:

| sync mode | safe-mode wall time | unsafe-mode wall time (18 trials, both runs) |
|---|---:|---:|
| `encoder_order` | 39.2–41.3 ms | — |
| `fence_sym` | 37.7 ms | — |
| `unsync_split` | — | 15,626.8–15,655.7 ms |
| `asym_producer` | — | 15,644.5–15,750.2 ms |
| `asym_consumer` | — | 15,637.6–15,738.9 ms |

A ≈**400×** slowdown, present in **every single unsafe-mode trial with no exceptions**, tightly
clustered (a ≈120ms spread across 18 trials at a ≈15,650ms mean — under 1% relative variance),
never observed in any safe-mode trial.

**INTERPRETED.** This is recorded as its own first-class finding, not assumed to generalize from
Bundle H's result (which showed fast-but-wrong-data corruption with no comparable latency
penalty): Bundle I's specific (atomic-heavy: three `atomic_fetch_add`s plus a 16-byte byte-copy
loop per captured vertex) producer shape did not expose the same data-race window at the tested
scale, but exhibits a large, highly reproducible stall under the identical nominally-unsynchronized
resource/command-buffer configuration that Bundle H's simpler single-store producer completes in
under a second. The exact mechanism is **`UNKNOWN`** — plausibly some fault/coherency-recovery
path specifically triggered by the untracked-resource-plus-atomic-plus-two-command-buffer
combination, or a scheduling artifact of the heavier kernel — and is flagged as `UNKNOWN`, not
silently dropped or guessed at. A secondary anomaly, `n_invoked` reporting exactly one more
touched slot than the expected written count, appeared in most (not all) of the slow trials and
never in a fast trial (see `run01b`/`run02b` raw data: `n_invoked=12289` vs. expected `12288` in
most unsafe-mode trials) — consistent with, but not proof of, an internal retry mechanism;
recorded as `UNKNOWN`/informational, not promoted to a claim.

**Practical consequence for a driver/compiler targeting a software transform-feedback path**: the
same synchronization discipline required by Bundle H (symmetric fencing or same-command-buffer
encoder ordering) is required here too — the ABSENCE of a corruption signature in this specific
producer shape must **not** be read as "streamout is safe without synchronization"; it is read as
"this producer shape's particular race window did not manifest as data corruption at the tested
scale, but the same missing-synchronization condition triggers a severe, unexplained performance
cliff instead, which is itself a correctness-adjacent hazard (a real driver cannot tolerate a
possible 400× stall on an unsynchronized path)."

## 4. Finite-resource mandate — summary table

| resource | exact range/behavior tested | first-illegal / boundary | evidence |
|---|---|---|---|
| `MTLDrawPrimitivesIndirectArguments` fields | `vertexCount∈{0,1,8,32}`, `instanceCount∈{0,1,3,4}`, `vertexStart∈{0,10}`, `baseInstance∈{0,5}` | `instanceCount=0` → 0 invocations (not 1); no other tested value rejected | `HW-VALIDATED` |
| `MTLDrawIndexedPrimitivesIndirectArguments` fields | as above + `indexCount∈{0,8}`, `baseVertex∈{0,-3}`, `idxbits∈{16,32}` | none rejected; restart-sentinel index treated as ordinary value for point topology | `HW-VALIDATED` |
| `[[instance_id]]` addressing | `baseInstance∈{0,5}` | ABSOLUTE (`baseInstance`-inclusive), not local | `HW-VALIDATED` |
| `indirectBufferOffset` alignment | `0`, `2` (misaligned) | no rejection observed at `+2`; general alignment rule beyond this one offset `UNKNOWN` | `HW-VALIDATED` (single point), `PARTIAL` (not a full alignment sweep) |
| `MTLIndirectCommandBufferExecutionRange{location,length}` | `location∈{0,2,4,8,10}`, `length∈{0,1,3,4,8,20}` against `maxCommandCount=8` | `location==maxCommandCount`: safe, 0 executed. `location>maxCommandCount`: **faults**. Oversized `length` alone: silently clamped | `HW-VALIDATED` |
| `newIndirectCommandBufferWithDescriptor:maxCommandCount:` | `1024`…`4,194,304` (works) vs. `8,388,608` (crashes) | boundary bracketed between these two values, both directions reproduced 2×+ | `HW-VALIDATED` |
| XFB stream/buffer count | tested exactly the API-fixed 4 streams (`0..3`), all independently addressable, independent counters | **not tested**: any lower native hardware descriptor/atomic-slot limit — out of scope for a public-API-only bundle, correctly left `UNKNOWN` per the addendum's own instruction not to search for native GS/streamout hardware in this bundle | `HW-VALIDATED` (API-level), `UNKNOWN` (native-hardware-level, deliberately out of scope) |
| XFB per-stream capacity/stride/offset | capacities `0`…`1000` vertices; strides `16`(tight)/`17`(misaligned)/`32`(interleaved); offsets `0`/`3`(misaligned)/`16` | no rejection at any tested boundary; capacity strictly enforced at whole-primitive granularity, confirmed to the exact byte | `HW-VALIDATED` |
| XFB atomic counter width | `atomic_uint` (32-bit) per stream per counter (generated/reserved/written) | MSL's base spec provides no wider (64-bit) device atomic in this path; a driver targeting GL's 64-bit `PRIMITIVES_GENERATED`/`PRIMITIVES_WRITTEN` query semantics at counts `>2^32` needs a software-widened counter (e.g. two 32-bit atomics combined, or periodic CPU-side accumulation) — not itself tested here, flagged as a real driver requirement | `STRUCTURAL` (MSL language fact) + `INFERRED` (driver consequence) |

## 5. Standing gate results

| gate | result |
|---|---|
| (a) shared schema, `verify.py --selftest` | **PASS, 17/17 checks** (matrix well-formed, schema frozen, three independent finite-resource formulas cross-checked against `harness/fixtures/recorded_reality.json`'s real M4 captures, cross-run gate correctly passes an order-sensitive-only diff and correctly fails both a `verdict` diff and a non-excluded-field (`n`) diff) |
| (b) `verify.py --seqtest` | **PASS, 9/9** (the original 7 `PRE_GPU`/`RUN01_PRESENT`/`RUN02_PRESENT` × gate combinations, plus 2 new checks proving a `QUARANTINE.md`-marked directory is correctly excluded from the run-directory state machine — added after `m4_20260828_run01`'s interruption, see "Operational note") |
| (c) non-recorded smoke gate | **PASS** both official runs; `work/m4_20260828_run01b_smoke.json`/`..._run02b_smoke.json` (never `raw/`), a real GPU dispatch, checked before either run's `raw/` directory was created |
| (d) nondeterminism exclusion | **PASS, and empirically exercised on REAL data across two independent official runs**, not just the selftest: `h_sync` unsafe-mode `n_correct`/`n_stale`/`n_other`/`n_z_wrong` and `xfb_sync` unsafe-mode `n_invoked`/`n_correct`/`n_stale`/`replay_vertexCount` genuinely differ trial-to-trial and run-to-run (§1.2, §3.3 tables above) while every gated field — `status`, `verdict`, and every producer-side-only field (e.g. `xfb_sync`'s `gen0`/`res0`/`wr0`, always exact and identical) — matched exactly across both runs, `issues_total=0` |
| (e) recorded-reality selftest fixtures | **PASS**; `harness/fixtures/recorded_reality.json` holds four real M4 captures (an `xfb_capacity` boundary case, an `h_icbrange` middle-range case, a genuinely-raced `h_sync unsync_split` trial, and the `h_icbmax` crash boundary), referenced (not hand-typed) by `verify.py --selftest` |

Plus: single-threaded harness (`run.py` executes all 111 cases strictly sequentially; each case is
its own `work/bin/{gddraws,xfbdraws}` subprocess; both ObjC binaries use `fflush(NULL)`/
`ferror(stdout)` exit discipline on every exit path); `raw/` append-only (`run.py` refuses to
write into an existing `--out` directory; the interrupted `m4_20260828_run01` was never edited,
only quarantined); hard timeout (`RUN_TIMEOUT_S=90`, comfortably above the calibrated ≈15.7s
`xfb_sync` unsafe-mode latency penalty) on every subprocess call; each case its own process; faults
and a crash are recorded as first-class results (`CMDBUF_ERROR`/`HARNESS_CRASH` are valid `status`
values, matched against build-time-predicted `expect_fault`/`expect_crash` annotations rather than
treated as unexplained failures); run ids never reused (`m4_20260828_run01` retired and
quarantined rather than repaired or reused; the two official runs are `m4_20260828_run01b`/
`m4_20260828_run02b`); no post-capture repair of any hash-frozen file (the one post-freeze change,
`harness/verify.py`'s quarantine-awareness fix, happened **before** either official run started
and is recorded with its own amendment note and updated hash in `CAPTURE_CONTRACT.json`, not
applied retroactively to already-captured evidence).

## 6. Operational note — host restart between build-time calibration and the official captures

A first attempt at the official capture (`m4_20260828_run01`, started `2026-08-28T04:24:08Z`) was
interrupted after 7/111 records by a host/terminal problem unrelated to any GPU dispatch this
experiment made (no case up to that point had reported a fault, hang, or unexpected verdict). On
resume, `uptime` showed a fresh host boot; this agent's own tooling never issued any reboot command
of any kind (no `macvdmtool`, no other tool-based reboot) — recovery was external. Per the standing
"never reuse a run id" rule, `raw/m4_20260828_run01/` was retained exactly as written and marked
with `QUARANTINE.md`; `harness/verify.py` was amended (before any further capture) to make its
directory-scanning gates skip a quarantine-marked directory, re-verified green (`--selftest` 17/17,
`--seqtest` 9/9 including two new checks proving the exclusion itself), and its updated hash was
recorded transparently in `CAPTURE_CONTRACT.json` with an amendment note. The two official captures
(`m4_20260828_run01b`, `m4_20260828_run02b`) then ran to completion cleanly, each launched as a
detached background process and polled in a bounded loop (rather than a single blocking call) so a
repeat host/terminal interruption could not silently kill the capture unnoticed. Full detail:
`PROGRESS.md`.

## 7. Required response blocks

**GLPRE-A01.** Can the unchanged Asahi UAPI express a fully GPU-driven sequence in which a compute
dispatch writes parameter/vertex/index/indirect-draw records that a following draw consumes
without a CPU round trip, and what synchronization does it need? — **YES at the public-Metal-API
level, with an exact, `HW-VALIDATED` synchronization contract: default (Tracked) automatic
inter-encoder hazard tracking within one command buffer, OR an explicit symmetric `MTLFence`
across two command buffers, are both fully sufficient (0/48 combined safe-mode trials showed any
staleness across two independent official runs). Splitting the producer and consumer across two
command buffers with hazard tracking disabled and no fence, or a fence asserted asymmetrically, is
NOT safe** — it produced genuine data staleness in 2/8 to 8/8 trials depending on configuration
(indexed draws raced in every single one of 24 unsafe-mode trials), directly generalizing
`EXP-0093`'s ATOM-08 finding (asymmetric device-memory fencing unsafe at real concurrency) from the
shader-instruction layer to the command-buffer/resource-hazard layer. A driver targeting this
pattern must either keep the producer and consumer in the same command buffer with tracked
resources, or use symmetric fences — never an asymmetric or absent one.

**GLPRE-A02.** What are the exact records/limits for a shader-produced draw? — **Every tested
`MTLDraw[Indexed]PrimitivesIndirectArguments` field is read and honored exactly as a compute
kernel writes it (16/16 field-legality cases, both runs), including the ABI fact that
`[[instance_id]]` is absolute (`baseInstance`-inclusive). The device-generated draw-COUNT grammar
(`MTLIndirectCommandBufferExecutionRange`) has an exact, sharp boundary: `location==maxCommandCount`
is safe (executes nothing); `location>maxCommandCount` faults the command buffer; an oversized
`length` alone is silently clamped, never rejected or faulting. `newIndirectCommandBufferWithDescriptor:`
has a practical ceiling between 4,194,304 (works) and 8,388,608 (crashes the calling process) —
a driver must enforce a client-visible cap well below that boundary, since the public API itself
provides no graceful rejection there.**

**GLXFB-A01.** Are Apple9's documented global-memory/atomic/generated-draw primitives sufficient
for a compute-emulated OpenGL transform-feedback path, and what is the exact streamout→draw
synchronization contract? — **YES for the capture/capacity/multistream mechanics — every tested
case (32/32, including a differentiated-per-stream GS-shaped fan-out, interleaved and
deliberately-misaligned buffer layouts, and rasterizer-discard) matched a closed-form
no-partial-primitive model exactly, byte-verified. The streamout→draw handoff needs the SAME
synchronization discipline as GLPRE-A01 (symmetric fencing or same-command-buffer ordering), but
this bundle's specific atomic-heavy producer shape shows a DIFFERENT unsafe-mode failure
signature than Bundle H's: instead of (or in addition to, at some untested scale) data
corruption, an unsynchronized producer/consumer pair here incurred a consistent ≈400× completion-
latency penalty (≈15.6–15.8s vs. ≈40ms) in every one of 18 combined unsafe-mode trials across
both runs, with zero observed data staleness. This must NOT be read as "safe without
synchronization" — it is a different, still-unacceptable hazard (a real driver cannot tolerate a
possible 400× stall), and the underlying mechanism is UNKNOWN, not assumed benign.** Query-counter
semantics (`GL_PRIMITIVES_GENERATED`/`WRITTEN`-equivalent) are directly modeled by this
experiment's `generated`/`written` atomic counters (32-bit `atomic_uint` per stream); a driver
needing GL's full 64-bit query range must widen this in software, since MSL's base device-atomic
path is 32-bit only.

## 8. Limitations and confounders

- The exact `n_stale`/staleness-magnitude COUNTS in unsafe-mode `h_sync` trials are genuinely
  nondeterministic GPU-scheduling artifacts (confirmed to differ trial-to-trial and run-to-run);
  only the coarse per-mode race-rate pattern (§1.2's table) and the invariant that every safe mode
  never raced are promoted as repeatable facts.
- `xfb_sync`'s unsafe-mode latency-penalty mechanism is `UNKNOWN` — this experiment establishes
  that it exists, is large, and is highly consistent, but does not isolate its cause (fault
  recovery vs. scheduling artifact vs. something else). A dedicated follow-up (e.g. GPU-side
  timestamp instrumentation across the two command buffers, or a parametric sweep of which
  specific kernel feature — atomics vs. the byte-copy loop vs. buffer count — triggers it) would
  be needed to close this; not attempted here as out of this bundle's scope.
- Primitive-assembly-level effects of the restart-sentinel index (strip-topology splitting) are
  not observable by this experiment's per-vertex-invocation verification method; recorded `UNKNOWN`,
  explicitly deferred, not silently dropped.
- `indirectBufferOffset` alignment was tested at exactly one misaligned value (`+2`); a full
  alignment-boundary sweep (odd/prime offsets, larger misalignments) was not performed.
- XFB stream/buffer count was tested only at the OpenGL-API-fixed value of 4; any LOWER native
  hardware descriptor/atomic-slot limit is explicitly out of scope for this public-API-only bundle
  (per the addendum's own instruction not to search for native GS/streamout hardware here) and is
  `UNKNOWN`, not assumed absent.
- No claim about A18 Pro/G17P anywhere in this document; per `CLAUDE.md`, M4 observations are the
  operational Apple9 evidence for this workstream but a G17P-specific fact would need an explicit
  `INFERRED`-by-family label, which this document does not need to invoke since it makes no
  G17P-specific claim.
- The `h_icbmax` crash boundary (4,194,304 works / 8,388,608 crashes) was bracketed but not
  narrowed to an exact byte-level threshold; deliberately not pursued further to avoid multiplying
  process crashes for no additional driver-relevant precision (a driver-safe cap needs only to be
  well below the confirmed-working value, which this data already establishes).

## Verification

```sh
python3 harness/verify.py --selftest      # PASS (17 checks)
python3 harness/verify.py --seqtest       # PASS (9 state/gate combinations)
python3 harness/verify.py --captured m4_20260828_run01b m4_20260828_run02b
  # cross_run_gate_pass=true, issues_total=0, verdict_counts_a/b={"PASS":78,"FAIL":0,"TIMEOUT":0,"N/A":33}
python3 harness/run.py --list             # regenerate/inspect the frozen 111-case matrix
```

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC (Xcode SDK public headers)
Inputs inspected: authored MSL (kernels/h_chain.metal, kernels/h_icbrange.metal, kernels/xfb.metal
  -- the only machine code this experiment produced or inspected), authored Objective-C
  (harness/gddraws.m, harness/xfbdraws.m), authored Python (harness/schema.py,
  harness/casematrix.py, harness/run.py, harness/verify.py), Metal.framework's public SDK headers
  (struct/method declarations only, MacOSX26.5.sdk -- public developer documentation, not binary
  introspection).
Apple binary introspection: NONE.
Apple auxiliary/helper/program bytes inspected: NONE.
Compiled shader bytes inspected: NONE (only our own MSL, compiled via newLibraryWithSource: and
  run; never extracted or disassembled).
Command/BO payload tracing: NONE.
tools/agx-isa / assembler / native VDM-CDM grammar: NOT USED anywhere in this experiment, per the
  addendum's own instruction for Bundles H and I -- confirmed structurally inapplicable to the
  db.json ALU-register-field finding and EXP-0099's refutation of both proposed models.
Target: M4/G16G-class only; A18 Pro untested.
Reproduction: README.md command sequence.
Evidence: raw/m4_20260828_run01b/, raw/m4_20260828_run02b/, raw/m4_20260828_run01
  (quarantined, retained, not promoted), CAPTURE_CONTRACT.json, PRE_REGISTRATION.md,
  harness/fixtures/recorded_reality.json.
```

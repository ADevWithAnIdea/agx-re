# RESULTS — EXP-0124-m4-query-indirect-remainder

**Target: local Apple M4 (G16G) only**, Mac16,10, macOS 26.6.2 (25G82), Metal 4. No A18 Pro
claim anywhere in this document (A18 hands-off; every finding is M4-only, which is the
operational Apple9 evidence per `CLAUDE.md`). Two official capture runs
(`raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`), **85 cases each, byte-identical
outside the one declared nondeterministic exclusion** (`i_icbb_trial` unbarriered race
trials), pinned revision `24cec78d1ff3e57d709614342d630a4839d8528c`. **Cross-run gate:
PASS, 0 issues.** Both runs: **73 PASS / 4 FAIL / 0 TIMEOUT / 8 N/A** (the 4 FAIL verdicts
are genuine hypothesis refutations, not harness defects — see below; the 8 N/A are the
deliberately-unbarriered ICB race trials, correctly observational). `verify.py --selftest`
PASS (0 issues), `--seqtest` PASS (7/7 checks). Non-recorded smoke gate PASS both runs
(`work/m4_20260828_run01_smoke.json`, `work/m4_20260828_run02_smoke.json`, real GPU
dispatches, written before either `raw/` directory existed). The `maxCommandCount`
crash-boundary bisection (separate from the fixed matrix, see below) **converged to the
identical exact boundary in both runs**: 24 probes each, `6,391,319` works /
`6,391,320` crashes, zero monotonic violations.

## Headline findings

| # | finding | evidence |
|---|---|---|
| 1 | M4 supports **only stage-boundary** counter sampling (`MTLCounterSamplingPointAtStageBoundary`); Draw/Dispatch/TileDispatch/Blit-boundary sampling are all unsupported, and calling the per-command `sampleCountersInBuffer:atSampleIndex:withBarrier:` API for them is not a graceful rejection — it **hard-aborts the process** | `HW-VALIDATED`, `q_caps`, build-time crash reproduced 3x |
| 2 | Pipeline statistics **do not exist natively on M4** — `device.counterSets` contains only `"timestamp"`; no `"statistic"`/`"stageUtilization"` set is present | `HW-VALIDATED` (clean negative), `q_caps`, both runs identical |
| 3 | Counter-heap **exact allocation ceiling**: `sampleCount=4096` succeeds, `8192` is gracefully rejected (`MTLCounterSampleBufferErrorOutOfMemory`) — for the `timestamp` set, Shared storage | `HW-VALIDATED`, `q_alloc_sweep`, both runs identical |
| 4 | `resolveCounterRange:` on a **Private**-storage-mode sample buffer **SIGSEGVs uncatchably**; Managed mode is silently *accepted* at allocation and resolve works fine (no distinct Managed behavior from Shared observed) | `HW-VALIDATED`, `q_alloc_mode`, crash reproduced every trial |
| 5 | **maxCommandCount crash boundary narrowed to an exact integer**: `6,391,319` works, `6,391,320` SIGSEGVs — both official runs converge to the identical value | `HW-VALIDATED`, `icbmax_bisect`, 2/2 runs identical |
| 6 | Occlusion **counting mode sums across repeated `setVisibilityResultMode` activations at the same offset within one encoder** (accumulates, does not overwrite); an intervening `Disabled` call does not reset the accumulator; distinct offsets never interfere | `HW-VALIDATED`, `q_occoverwrite`, both runs identical |
| 7 | GPU-side `resolveCounters:` (blit) issued in a **later encoder of the SAME command buffer** as the sampling encoders reads **stale/zero data**; issued in a separate, later command buffer it matches the CPU-side resolve exactly | `HW-VALIDATED`, `q_copy_match` / `q_copy_samecb_hazard`, both runs identical |
| 8 | The GPU-authored (MSL `render_command`/`compute_command`) **writable ICB grammar works end-to-end**: `set_vertex_buffer`/`set_kernel_buffer`, `draw_primitives`/`draw_indexed_primitives`, `reset()`, `inheritBuffers=YES` inheritance, and out-of-bounds command indices are all silently absorbed without fault or corruption of in-range slots | `HW-VALIDATED`, `i_icbwrite` family, both runs identical |
| 9 | GPU-authored `.set_barrier()` on a `ConcurrentDispatch` ICB command is **fully effective** (0/16 trials raced across both runs); omitting it exposes a **real, substantial race** (6/16 = 37.5% combined) with the exact predicted stale-sentinel signature every time | `HW-VALIDATED`, `i_icbbarrier`, both runs |
| 10 | **Primitive restart is honored for `MTLPrimitiveTypeTriangleStrip`** (0xFFFFFFFF/0xFFFF sentinel splits the strip, never consumed as ordinary vertex data) but **not** for `MTLPrimitiveTypePoint` (sentinel treated as an ordinary huge index) — extends EXP-0098's point-topology finding with a strip-topology positive | `HW-VALIDATED`, `i_restart`, both runs identical |
| 11 | Indirect-dispatch parameter format confirmed byte-exact: `(X,Y,Z)` written by a compute kernel into a `MTLDispatchThreadgroupsIndirectArguments`-shaped buffer produces exactly `X×Y×Z` threadgroups in that axis order; a non-4-byte-aligned `indirectBufferOffset` (tested at 2) is accepted without rejection | `HW-VALIDATED`, `i_cdmfmt`, both runs identical |
| 12 | An **empty encoder** (sample-buffer attachments set, zero real commands) never reaches its stage-boundary HW sample point — both slots read back untouched-zero, not `MTLCounterErrorValue` | `HW-VALIDATED`, discovered fixing `q_reset`/`q_copy`/`q_simul`/`q_tick`, both runs identical |

## Group Q — P1.6 / DRV-QUERY-01

### Counter-heap layout, allocation, and limits

`device.counterSets` on M4 returns exactly one set, named `"timestamp"`
(`MTLCommonCounterSetTimestamp`). No `"statistic"` (`MTLCommonCounterSetStatistic`) or
`"stageUtilization"` set is present, even though both are documented, named public
constants (`MTLCounters.h`) — the header's own text ("Implementations may omit some of
the counters from these sets") anticipates exactly this. **Conclusion for the pipeline-
statistics sub-question: they do not exist natively on M4 and must be emulated entirely**
if a driver needs GL/D3D-style `vertexInvocations`/`fragmentsPassed`/etc. counters — a
clean, direct negative answer (`q_caps_census`, both runs: `counterSets=timestamp,
hasStatisticSet=0`).

`supportsCounterSampling:` is `TRUE` only for `MTLCounterSamplingPointAtStageBoundary`;
`AtDrawBoundary`, `AtDispatchBoundary`, `AtTileDispatchBoundary`, and `AtBlitBoundary` are
all `FALSE`. This is consistent with, and now independently confirms via a second
(PUBLIC-API) method, EXP-0027's A18 DATA-TRACE finding ("only stage-boundary sampling is
supported (dispatch/draw boundary = unsupported)"), and extends it to tile-dispatch and
blit boundaries. **The consequence is sharper than a capability flag**: calling the
per-command `-[MTLBlitCommandEncoder/MTLComputeCommandEncoder sampleCountersInBuffer:
atSampleIndex:withBarrier:]` API for an unsupported point does not fail gracefully — it
hits a hard, **uncatchable process-aborting assertion** on this device family:
```
-[AGXG16GFamilyBlitContext sampleCountersInBuffer:atSampleIndex:withBarrier:]:812:
  failed assertion `MTLBlitCommandEncoder:sampleCountersInBuffer:atSampleIndex:withBarrier
  not supported on this device'
```
reproduced identically from both a blit and a compute encoder during build-time
calibration (`PROGRESS.md` milestone 3.1). **A driver targeting M4 must never call this
selector; it must use the pass-descriptor `sampleBufferAttachments[i].
startOfEncoderSampleIndex/endOfEncoderSampleIndex` mechanism exclusively.**

`sampleCount` allocation sweep (`q_alloc_sweep`, `timestamp` set, `MTLStorageModeShared`),
identical both runs:

| `sampleCount` | result |
|---:|---|
| 0 | `ALLOC_REJECTED` (`errCode=1` = `MTLCounterSampleBufferErrorOutOfMemory`) |
| 1 – 4096 | allocates exactly (readback `sampleCount` matches request) |
| **8192** | **`ALLOC_REJECTED`** — first illegal value |
| 16384, 32768, 65536, 2^20, 2^24, 2^26, 2^40 | all `ALLOC_REJECTED`, no crash at any tested size |

**Exact, sharp, crash-free ceiling: 4096 samples (32 KiB at 8 bytes/sample) for the
`timestamp` counter set with Shared storage.** Unlike the ICB `maxCommandCount` ceiling
(finding #5), every illegal value here is gracefully rejected via `error`, never a crash —
a materially friendlier API surface for a driver to rely on.

`storageMode` (`q_alloc_mode`): `Shared` and `Managed` both allocate successfully and
`resolveCounterRange:` succeeds on both with no thrown exception (`resolveThrew=0`,
`resolveNil=0`) — Managed is *accepted*, not rejected, contradicting a strict reading of
the header's "Only MTLStorageModeShared and MTLStorageModePrivate may be used" (Managed is
neither of those two); no behavioral difference from Shared was observed in this narrow
test. **`Private` storage mode allocates successfully but `resolveCounterRange:` SIGSEGVs
the calling process uncatchably** — isolated via temporary `NSLog` checkpoints
(`PROGRESS.md` milestone 3.4) to originate strictly inside the Metal runtime call itself,
not our code, and reproduced on every trial including both official runs
(`expect_crash: true`, `status=HARNESS_CRASH` both runs). **A driver must never call
`resolveCounterRange:` on a non-Shared sample buffer on this device family; the public API
provides no graceful path there.**

### Accumulation, reset, and availability semantics

Re-sampling the same slot of a reused `MTLCounterSampleBuffer` in a second, later command
buffer produces a strictly larger, different value (`q_reset_reuse`: `v2GTv1=1, v2NEv1=1`
both runs) — a plain overwrite by the fresh sample, not an accumulation with the prior
value (timestamps are inherently monotonic so this cannot by itself prove overwrite vs.
accumulate for a hypothetical *counting*-type counter set, but M4 has no such set — see
above — so this is the complete answer available for this device). `resolveCounterRange:`
itself is **idempotent**: resolving the same unchanged range twice returns byte-identical
data both times (`q_reset_idempotent`, both runs).

**Availability sentinel (fixes EXP-0052's open ambiguity directly):**

| point | observed | interpretation |
|---|---|---|
| never sampled at all (`pre_commit`) | `v0=0, v1=0` (both runs) | reads the buffer's zero-initialized backing memory, **not** `MTLCounterErrorValue` |
| committed, confirmed `status=Committed` (2) at the instant of resolve, **not yet Completed** (`post_commit_unwaited`) | `v0=0, v1=0`, `sawNonCompletedAtResolve=1`, `statusAtResolve=2` (both runs) | same zero read as the never-sampled case — **not** the sentinel either |
| after `waitUntilCompleted` (`post_completed`) | real, large, monotonically increasing ns values (e.g. `v0=8035642146666, v1=8035680193791`) | the genuine post-completion value |

**This resolves EXP-0052's flagged ambiguity with a rigorous status check**: an in-flight
(committed-but-not-completed, confirmed via `cb.status`) resolve is **indistinguishable
from a never-sampled one** — both read plain zero. `MTLCounterErrorValue` (`~0ULL`) is
**not** a "not ready yet" signal on this path; per the header it denotes a genuine resolve
*error* (e.g. a counter absent from the requested set), never observed in this experiment.
**A driver must not poll for `MTLCounterErrorValue` to detect in-flight samples; it must
track completion via the command buffer / fence itself.**

### Copy/resolve rules — a genuine same-command-buffer ordering hazard

CPU-side `resolveCounterRange:` and GPU-side `-resolveCounters:inRange:destinationBuffer:
destinationOffset:` (blit) produce **byte-identical** data when the GPU-side resolve runs
in a command buffer **after** the sampling command buffer has fully completed
(`q_copy_gpu_matches_cpu`, both runs: `gpuResolveMatchesCpuResolve=1`). But issuing the
same GPU-side resolve in a **later blit encoder of the SAME command buffer** as the
sampling encoders reads **stale data** — all zeros in one build-time trial, a mix of zero
and partial garbage in the official runs (`q_copy_samecb_hazard`: `sameCbCpuAllNonzero=1,
sameCbGpuAllZero` varies, `sameCbMatch=0` in every trial including both official runs).
**This is a real synchronization gap a driver must respect: a GPU-side counter resolve is
not implicitly ordered after prior stage-boundary counter writes within the same command
buffer; it must be issued in a separate, later command buffer (or otherwise explicitly
synchronized) to reliably see sampled values.**

An out-of-range CPU resolve (`range=[2,6)` against `sampleCount=4`) returns `nil`, no
thrown exception (`q_copy_oob`, both runs) — a clean, safe negative.

### Simultaneous queries

Two independent `MTLCounterSampleBuffer`s sampled within **one** encoder (two
`sampleBufferAttachments` slots) both read correct, monotonic, non-error values with no
cross-contamination (`q_simul_two_in_encoder`, both runs). **The
`sampleBufferAttachments` array is capped at exactly 4 slots per encoder**: `n=1..4`
all succeed; `n=5` hits a hard CPU-side assertion abort
(`attachmentIndex(4) must be < 4`), reproduced identically both runs
(`expect_abort: true`). Two independent command queues sampling independent buffers fully
concurrently (two `MTLCommandBuffer`s committed on two separate `MTLCommandQueue`s, no
ordering between them) both complete with correct, non-error values
(`q_simul_two_queues`, both runs). **Simultaneous queries are supported, bounded at 4
concurrently-attached counter sample buffers per single encoder, unbounded (not
specifically tested beyond 2) across independent queues.**

### Occlusion query semantics

Counting mode reports **exactly `overlap × 4096`** for `overlap` full-viewport
64×64-pixel draws issued under one `setVisibilityResultMode:` activation
(`overlap=1→4096`, `overlap=2→8192`, both runs) — **counts per fragment invocation, not
per unique covered pixel** (no deduplication across overlapping draws). Boolean mode
reports exactly `1` regardless of overlap count (`overlap=1→1`, `overlap=2→1`, both runs).
Zero-coverage geometry (fully clipped) reports exactly `0` (`q_occ_zero_coverage`, both
runs).

**Overlapping/nested queries — refutes the pre-registered overwrite hypothesis (H-Q8)**:
calling `setVisibilityResultMode:offset:` **twice at the same offset** within one encoder,
with a draw under each activation, **accumulates** — the final value is the *sum* of both
activations' expected counts (`8192 = 2×4096`), not the second activation's value alone
(`4096`). Inserting a `Disabled` mode call between the two `Counting` activations does
**not** reset the accumulator — same accumulated `8192` result. The distinct-offsets
control confirms no cross-offset interference (`v0=4096, v1=4096`, matching the
non-accumulating, non-interfering expectation for genuinely separate memory locations).
All three sub-cases identical both runs. **A driver must treat visibility-result-buffer
offsets as persistent accumulators for the life of the encoder, not overwritten by
subsequent mode activations at the same offset — reusing an offset within one encoder
without an explicit reset means summed, not replaced, counts.**

### Tick frequency, conversion, and wrap

A `timestamp`-counter-set sample resolved via the counter heap falls strictly between two
`device sampleTimestamps:gpuTimestamp:` calls bracketing it in time
(`heapValBetweenPublicBounds=1`, both runs; e.g. `gpuBefore=8036316485208 ≤
heapVal=8036318369750 ≤ gpuAfter=8036318495291`), on the same order of magnitude and the
same apparent nanosecond unit as the public GPU timestamp. This is a PUBLIC-API
cross-check that the counter-heap `timestamp` values and `sampleTimestamps`' `gpuTimestamp`
share one clock domain on M4, consistent with (though not independently re-deriving) EXP-
0027's A18 DATA-TRACE finding of "uint64 nanoseconds, period 1.0."

**WRAP is not empirically tested** — a 64-bit nanosecond counter wraps after
2⁶⁴ ns ≈ 584,942 years of continuous operation, which is not reachable by any real
experiment. This is documented as `INFERRED` (a direct arithmetic consequence of the
established 8-byte/ns-unit fact), not `HW-VALIDATED`: no driver code path needs to handle
wrap for this counter.

## Group I — P1.7 / DRV-INDIRECT-01

### Direct vs. indirect CDM dispatch modes; parameter-memory format

Public-header census (PUBLIC, `MTLComputeCommandEncoder.h`/`MTL4ComputeCommandEncoder.h`):
classic `MTLComputeCommandEncoder` exposes `dispatchThreadgroups:threadsPerThreadgroup:`
(direct, threadgroup units), `dispatchThreads:threadsPerThreadgroup:` (direct, thread
units), and `dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:
threadsPerThreadgroup:` (indirect, **threadgroup units only**) — there is **no**
indirect-*threads* dispatch on the classic encoder, even though a
`MTLDispatchThreadsIndirectArguments` struct is declared (orphaned in the classic API).
**Metal 4's new `MTL4ComputeCommandEncoder` adds `dispatchThreadsWithIndirectBuffer:`**
(over a raw `MTLGPUAddress`, not an `MTLBuffer`) — flagged here as a real, structurally
confirmed capability difference between the classic and MTL4 command-encoding models, but
**not runtime-tested** in this experiment (out of scope; every other EXP in this family
uses the classic API and this experiment follows that convention) — a residual item for
P1.7 (see "What P1.6/P1.7 still require" below).

`MTLDispatchThreadgroupsIndirectArguments`'s byte layout is confirmed exactly: a compute
kernel writing three consecutive `uint32` values `(3,5,2)` into a buffer, consumed by
`dispatchThreadgroupsWithIndirectBuffer:`, produces exactly `30 = 3×5×2` invocations
(`i_cdm_axis_order_proof`, both runs: `nInvoked=30, match=1`) — confirms X,Y,Z order (not
reversed/interleaved) directly, not merely trusting the header. Zero in any single axis
produces zero invocations, no fault (`i_cdm_zero_{x,y,z}`, both runs). A non-4-byte-
aligned `indirectBufferOffset` (tested at `2`, vs. the header's documented "must be a
multiple of 4") is **accepted without rejection or fault** (`i_cdm_misaligned_offset`,
both runs) — extending EXP-0098's identical finding for the **draw**-indirect-buffer-
offset case to the **dispatch**-indirect-buffer-offset case.

Boundary sweep (`i_cdm_sweep`, both runs identical): `(1,1,1)` and `(8,8,1)` verified
byte-exact against a closed-form atomic-counter check; `(65535,1,1)`, `(65536,1,1)`,
`(2^20,1,1)`, and `(2^24,1,1)` all complete without fault (the largest, 16,777,216
invocations, confirmed exactly via the same atomic counter: `nInvoked=16777216,
match=1`) — **no silent clamp, no crash, no timeout at any tested size up to 2^24**. Larger
grids were not pursued further (diminishing driver-relevant value against real dispatch
time; the boundary-crash-risk budget for this experiment was spent on the maxCommandCount
cliff instead, per the dispatch's own "map, don't sample randomly" priority).

### The writable device-generated command grammar (GPU-authored ICB commands)

This is new ground beyond EXP-0053/EXP-0098, both of which had a compute kernel write an
**argument struct** consumed by a CPU-issued indirect draw/dispatch call. Here, a compute
kernel directly calls MSL's ICB-encoding intrinsics
(`render_command`/`compute_command`/`command_buffer` from `<metal_command_buffer>`) to
construct the command **records themselves**. Syntax was discovered by iterative
compilation against our own trial `.metal` files and the public runtime compiler's own
diagnostics (`PROGRESS.md` milestone 2), not from memory of documentation.

**All tested grammar elements work correctly, `HW-VALIDATED`, both runs identical:**

| grammar element | test | result |
|---|---|---|
| `set_vertex_buffer` + `draw_primitives`, computed (non-constant) per-command buffer offset | `i_icbw_basic_render_n8` | last-encoded command's color read back exactly (`lastCmdColorMatch=1`) |
| `reset()` on a GPU-encoded command | `i_icbw_reset_after_encode` | the reset slot paints nothing (`resetSlotIsClear=1`); an untouched neighboring slot still paints (`otherSlotPainted=1`) |
| field legality: `vertexStart`/`vertexCount`/`instanceCount`/`baseInstance` passed directly as encode-time kernel-computed arguments (not via an argument struct) | `i_icbw_fields_00..05` | `vertexCount<3` or `instanceCount=0` → no paint; `vertexCount≥3, instanceCount≥1` → paints, **including** `vertexStart=10` (confirms `[[vertex_id]]` is absolute for GPU-authored commands too, matching EXP-0098's CPU-issued-indirect-draw finding) and `baseInstance=500` |
| `inheritBuffers=YES`: GPU-encoded command omits `set_vertex_buffer` entirely | `i_icbw_inherit_buffers_yes` | correctly uses the buffer bound on the executing render encoder (`inheritedBufferUsed=1`) |
| `draw_indexed_primitives` | `i_icbw_indexed` | indexed draw via a GPU-encoded command paints correctly (`indexedDrawPainted=1`) |
| out-of-bounds command index: dispatching 8 threads against a 4-slot ICB, so 4 threads construct a `render_command` past the end | `i_icbw_oob_command_index` | encode completes without fault (`encodeOk=1`); the legal `[0,4)` range still executes correctly afterward (`executeInRangeOk=1`) — **out-of-bounds GPU-side command construction is silently absorbed, does not fault, and does not corrupt in-range slots** |

Two pipeline-authorship pitfalls were found and fixed at build time, both promoted as
findings in their own right (`PROGRESS.md` milestones 3/4):
- A GPU-authored `render_command`'s pipeline is inherited (`inheritPipelineState=YES`) in
  every render test above; **mixing** a GPU-authored *compute* command's other fields with
  a CPU-side `-[MTLIndirectComputeCommand setComputePipelineState:]` call crashed
  unconditionally. Root cause: the producer/consumer `MTLComputePipelineState`s needed
  `supportIndirectCommandBuffers = YES` (built via `MTLComputePipelineDescriptor`, not the
  plain factory method) — the same opt-in EXP-0053 found necessary for render pipelines,
  here newly confirmed for compute pipelines used from an ICB.
- Once that flag was set, pipeline state was moved to be **entirely** GPU-authored (a
  `compute_pipeline_state` argument-buffer field + `.set_compute_pipeline_state()`
  in-kernel) rather than split CPU/GPU per command; this combination worked cleanly and
  is the tested configuration for finding #9 below.

### Multi-dispatch links and barriers

`MTLIndirectCommandTypeConcurrentDispatch` (2 GPU-authored compute commands: a producer
that writes `slot=42` after a calibrated spin delay, and a consumer that reads `slot` and
writes `slot*2`) with the consumer's command GPU-authoring calling `.set_barrier()`:

| condition | trials (both runs combined) | raced |
|---|---:|---:|
| `.set_barrier()` present | 16 | **0/16** |
| `.set_barrier()` absent | 16 | **6/16** (37.5%) |

Every raced unbarriered trial showed the exact predicted stale-read signature:
`result = 3,176,889,822 = (0xDEADBEEF × 2) mod 2^32`, i.e. the consumer read the
pre-producer-write sentinel, not a torn or unrelated value — confirming the mechanism, not
just its presence. **`.set_barrier()`/`.clear_barrier()` in the MSL ICB-encoding grammar is
a real, effective, GPU-authorable synchronization primitive for concurrent-dispatch ICBs**;
its absence is not merely theoretically unsafe but empirically races over a third of the
time at this scale. This is the P1.7 "multi-dispatch links and barriers" answer for the
one native mechanism Metal exposes for this (there is no separate "link" object — ordering
is expressed entirely via `set_barrier`/`clear_barrier` calls on specific command indices).

### Count buffers / multi-draw — confirms a clean negative

No public Metal API provides a native "multi-draw-indirect-with-count" call (Vulkan's
`vkCmdDrawIndirectCount` equivalent) outside the ICB mechanism (PUBLIC header census,
`MTLRenderCommandEncoder.h`/`MTLComputeCommandEncoder.h`: only single-draw/single-dispatch
indirect variants exist at the encoder level). **The ICB execution-range mechanism IS the
count-buffer equivalent**: EXP-0098 already established its exact closed-form semantics
(`n_executed = max(0, min(length, maxCommandCount-location))`); this experiment adds no
new execution-range cases (deliberately, to avoid redundant re-testing of an already-
`HW-VALIDATED` fact) but confirms via the header census that **no other native multi-draw
primitive exists** — a driver implementing indirect multi-draw-with-count must lower to
one ICB `executeCommandsInBuffer:indirectBuffer:` call per Vulkan/GL "multi-draw-indirect"
call, there is no lower-level native equivalent.

### Indexed vs. non-indexed forms; primitive restart and bounds rules

`MTLPrimitiveTypeTriangleStrip` with an index sequence `0,1,2,RESTART,3,4,5` (RESTART =
`0xFFFFFFFF` for 32-bit indices, `0xFFFF` for 16-bit): the rendered framebuffer shows
**only** the two intended disjoint triangles' colors (green cluster, blue cluster); the
sentinel-tagged third position's color (red) **never appears anywhere**
(`anyRed=0, anyGreen=1, anyBlue=1`, both runs, both index widths). **Primitive restart IS
honored for strip topology on M4.** The `MTLPrimitiveTypePoint` internal control (same
index buffer, same vertex/fragment shaders, point topology) shows the sentinel-tagged red
position **does** appear (`anyRed=1`, both runs) — the sentinel is consumed as an ordinary
(very large but in-bounds-for-the-shader's-arithmetic) index value for a non-strip
topology, freshly reproducing EXP-0098's original point-topology finding through an
independent kernel and harness. **Together these resolve EXP-0098's explicitly flagged
`UNKNOWN`: restart is a strip-topology-specific hardware/runtime behavior, not a
general index-value convention, and Metal provides no toggle to disable it** (no such
control exists in the public API surface examined).

### Stream-limit behavior at the boundaries

EXP-0098's `h_icbmax` bracketed `newIndirectCommandBufferWithDescriptor:maxCommandCount:`'s
crash boundary between `4,194,304` (works) and `8,388,608` (SIGSEGV) without narrowing
further. This experiment's dedicated bisection (`harness/icbmax_bisect.py`, a deterministic
binary search between those exact bracket points, one probe per process, both bracket ends
re-confirmed before bisecting) converges to an **exact** boundary, identically in both
official runs (24 probes each, 0 monotonic violations):

**`maxCommandCount = 6,391,319` allocates successfully; `6,391,320` SIGSEGVs.**

An arithmetic check (flagged `INFERRED` — not independently confirmed by a separate byte-
size probe, since `MTLIndirectCommandBuffer.size` reads back as the **command count**, not
a byte size, on this device: `readbackSize` exactly equals the requested `maxCommandCount`
at every tested value): `128 + 6,391,320 × 336 = 2,147,483,648 = 2³¹` **exactly**. This is
consistent with a plausible internal model of a 128-byte fixed ICB header plus 336 bytes
per Draw-type command, with the crash triggered by the total backing-storage size reaching
or exceeding a signed-32-bit (2 GiB) limit. The exact integer boundary itself is
`HW-VALIDATED` (measured directly, reproduced twice); the 128-byte-header/336-byte-per-
command byte-layout explanation is `INFERRED` (a very precise arithmetic fit, but not
independently cross-checked against a real byte-size readback). **A driver-safe cap must
sit strictly below 6,391,319**, not merely "well below 8,388,608" as EXP-0098's coarser
bracket required.

## Finite-resource summary table

| resource | exact range/behavior tested | first-illegal / boundary | evidence |
|---|---|---|---|
| Counter sample buffer `sampleCount` (`timestamp` set, Shared) | `0`…`2^40` | **4096 works, 8192 first rejected** (graceful, no crash) | `HW-VALIDATED` |
| Counter sample buffer `storageMode` | Shared, Private, Managed | Private: allocates, but `resolveCounterRange:` **SIGSEGVs**; Managed: fully accepted, behaves like Shared in this test | `HW-VALIDATED` |
| `sampleBufferAttachments` slots per encoder | `n=1..5` | **n=4 works, n=5 hard-aborts** (CPU-side assertion) | `HW-VALIDATED` |
| Counter availability signal | pre-commit / in-flight (confirmed `Committed` status) / post-completion | in-flight reads **zero**, indistinguishable from never-sampled; **never** `MTLCounterErrorValue` | `HW-VALIDATED` |
| `MTLIndirectCommandBuffer` `maxCommandCount` | `1024`…`8,388,608` | **6,391,319 works / 6,391,320 SIGSEGVs** (exact, bisected) | `HW-VALIDATED` |
| GPU-authored ICB command index | dispatched threads > `maxCommandCount` | out-of-bounds construction silently absorbed, no fault, no corruption of in-range slots | `HW-VALIDATED` |
| Indirect-dispatch grid `(X,Y,Z)` | up to `(2^24,1,1)` | no crash/clamp/timeout at any tested size; larger not pursued (see limitations) | `HW-VALIDATED` |
| `indirectBufferOffset` alignment (dispatch) | `0`, `2` (misaligned) | not rejected at `+2`; full alignment sweep not performed | `HW-VALIDATED` (one point), `PARTIAL` |
| Occlusion counting-mode offset reuse | same-offset re-activation, disabled-between, distinct-offset control | **accumulates**, not overwrite; `Disabled` does not reset | `HW-VALIDATED` |
| Concurrent-dispatch ICB barrier | 16 barriered + 16 unbarriered trials | barriered: 0/16 raced; unbarriered: 6/16 (37.5%) raced | `HW-VALIDATED` |

## Standing gate results

| gate | result |
|---|---|
| (a) `verify.py --selftest` | **PASS, 0 issues** (matrix well-formed, schema shapes, gate-(d) exclusion scope proven structurally, all 5 fixtures from `fixtures/recorded_reality.json` validate) |
| (b) `verify.py --seqtest` | **PASS, 7/7 checks** (deterministic scratch-directory unit test of PRE_GPU/RUN01_PRESENT/RUN02_PRESENT plus a quarantine-exclusion check, independent of real `raw/` state; informational real-state line included) |
| (c) non-recorded smoke gate | **PASS both runs**; `work/m4_20260828_run01_smoke.json` / `..._run02_smoke.json`, real GPU dispatches via both binaries, written before either `raw/<run_id>/` directory was created |
| (d) nondeterminism exclusion | **PASS**, and empirically exercised on real data: `i_icbb_trial` unbarriered `result`/`correct` genuinely differ run-to-run (run01: t1,t2,t4,t5 raced; run02: t2,t6 raced) while every other field, every other case, and every top-level field (`status`/`verdict`/`family`/`kind`/`params`) matched byte-for-byte across both runs (`verify.py --captured`: `issues_total=0`) |
| (e) recorded-reality fixtures | **PASS**; `fixtures/recorded_reality.json` holds 5 real M4 captures generated via `run.run_case()` itself (not hand-typed), referenced by `--selftest` |

Plus: append+fflush per record (`run.py`'s `gated_f.flush()`/`nongated_f.flush()` after
every case; `icbmax_bisect.py`'s `f.flush()`+`os.fsync()` after every probe);
`PROGRESS.md` milestone log; hard timeouts on every subprocess call (60s per matrix case,
30s per icbmax probe, 20s smoke); each case its own process throughout (no case reused a
process; the two known-crash cases and the icbmax probes near the boundary confirmed
fault-containment — host and GPU responsive immediately after every crash observed in this
experiment, zero host wedges); no run id reused; no post-freeze repair of any hash-frozen
file; pinned revision recorded at freeze time in `CAPTURE_CONTRACT.json`, not re-gated
against live `HEAD`.

## Limitations and confounders

- Indirect-dispatch grid-size boundary sweep stopped at `2^24` per axis (16,777,216
  invocations) — chosen to stay well clear of the demonstrated crash-risk budget already
  spent on the `maxCommandCount` bisection; larger grids (up to `UINT32_MAX`) remain
  `UNKNOWN`, not assumed safe.
- `indirectBufferOffset` alignment was tested at exactly one misaligned value (`+2`) for
  the dispatch path, matching EXP-0098's single-point draw-path test; a full alignment
  boundary sweep (odd/prime offsets, larger misalignments) was not performed for either
  path.
- The `maxCommandCount=6,391,320` byte-layout explanation (128-byte header + 336
  bytes/command) is `INFERRED` from an exact arithmetic fit against `2^31`, not
  independently confirmed by a real byte-size readback (Metal's own `.size` property
  reports command count, not bytes, on this device) — flagged, not promoted as
  `HW-VALIDATED`.
- `Managed` storage-mode counter sample buffers were tested only for allocate+resolve
  success; no test distinguishes any Managed-specific synchronization behavior (e.g. an
  explicit `-synchronize` requirement) from Shared — `PARTIAL`.
- The concurrent-dispatch-ICB barrier race rate (6/16, 37.5%) is a property of this
  specific producer/consumer shape and spin-delay calibration (`ICBB_SPIN_ITERS =
  4,000,000`, chosen at build time to reliably expose *some* races without dominating
  wall time); it is not claimed as a universal race probability — only the qualitative
  claim (barrier: never races; no barrier: races a real, substantial fraction of the time)
  is promoted.
- `MTL4ComputeCommandEncoder`'s `dispatchThreadsWithIndirectBuffer:` (over a raw
  `MTLGPUAddress`) is confirmed to exist by public header census only; not runtime-tested
  anywhere in this experiment (deliberately out of scope — see "still requires" below).
- Pipeline-statistics and stage-utilization absence is established for M4/G16G only; no
  A18 Pro/G17P claim is made (M4 is the operational Apple9 evidence per `CLAUDE.md`, but a
  G17P-specific negative would need its own `INFERRED`-by-family label if ever promoted to
  `docs/`).
- No claim anywhere in this document about A18 Pro/G17P; A18 is hands-off per the standing
  directive.

## What P1.6 / P1.7 still require

**P1.6 remaining:**
- `GET_TIME`/Linux frequency calibration and conversion formula against a real Linux UAPI
  object (this experiment only cross-checks two *macOS public-API* clock paths against
  each other; no Linux kernel object was inspected or is inspectable from this stack).
- The private counter-heap's Linux-visible object layout/packing (this experiment
  continues to establish only the public `NSData`/blit-copy payload shape, which EXP-0052
  already flagged as not proof of the private layout).
- MSAA interaction with occlusion counting mode (does per-sample vs. per-fragment-
  invocation counting change under multisampling?) — not tested here, flagged `UNKNOWN`.
- A18 Pro replication (suspended per standing directive, not a closure blocker).

**P1.7 remaining:**
- `MTL4ComputeCommandEncoder`'s indirect-*threads* dispatch and the broader MTL4
  GPU-address-based command-encoding model generally — confirmed to exist (PUBLIC header
  census) but entirely untested at runtime by this experiment or any prior one in this
  family.
- Full alignment-boundary sweeps for `indirectBufferOffset` (both dispatch and draw paths)
  beyond the single misaligned point each has now been tested at.
- Grid-size boundaries beyond `2^24` per axis for indirect dispatch.
- Draw-type ICB writable-grammar coverage for `DrawPatches`/`DrawIndexedPatches`/
  `DrawMeshThreadgroups`/`DrawMeshThreads` command types (only `Draw`, `DrawIndexed`, and
  `ConcurrentDispatch` were exercised here).
- Native validation/cache-transition rules beyond what was directly observed (this
  experiment characterizes *behavior* at several boundaries; it does not claim to have
  inventoried every validation rule Metal's runtime applies before accepting a GPU-authored
  ICB record).
- A18 Pro replication (suspended per standing directive, not a closure blocker).

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER + PUBLIC (Xcode SDK public headers)
Inputs inspected: authored MSL (kernels/q_common.metal, kernels/i_common.metal -- the
  only machine code this experiment produced or inspected), authored Objective-C
  (harness/qbench.m, harness/ibench.m, work/trycompile.m, work/try_icb.m), authored
  Python (harness/schema.py, harness/casematrix.py, harness/run.py, harness/verify.py,
  harness/icbmax_bisect.py), Metal.framework's public SDK headers (struct/method
  declarations only, MacOSX26.5.sdk -- public developer documentation, not binary
  introspection).
Apple binary introspection: NONE.
Apple auxiliary/helper/program bytes inspected: NONE.
Compiled shader bytes inspected: NONE (only our own MSL, compiled via
  newLibraryWithSource: and run; never extracted or disassembled).
Command/BO payload tracing: NONE (no tools/iotrace use in this experiment -- every
  question here was answerable at the public-API + HW-PROBE layer).
tools/agx-isa / assembler / native VDM-CDM grammar: NOT USED anywhere in this experiment.
Target: M4/G16G-class only; A18 Pro untested, no A18 claim anywhere in this document.
Reproduction: README.md command sequence.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/, CAPTURE_CONTRACT.json,
  PRE_REGISTRATION.md, PROGRESS.md, fixtures/recorded_reality.json.
```

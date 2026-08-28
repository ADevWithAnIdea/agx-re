# PRE_REGISTRATION — EXP-0124-m4-query-indirect-remainder

Frozen before any build. Target: P1.6 (`DRV-QUERY-01`) and P1.7 (`DRV-INDIRECT-01`)
remainder, extending (not redoing) EXP-0027, EXP-0052, EXP-0053, EXP-0091, EXP-0098.
**Local M4/G16G only. A18 hands-off.** Clean room: public Metal API (`newLibraryWithSource:`
runtime compilation of our own MSL) + public SDK headers (struct/method declarations,
documentation, not binary introspection) + HW-PROBE (live GPU dispatch/readback). No
`tools/*`, no assembler, no native VDM/CDM grammar, no IOKit tracing in this experiment
(all questions here are answerable at the public-API layer; DATA-TRACE is not needed and
is explicitly out of scope to keep the experiment single-method and auditable).

## Pinned environment

- Repository revision pinned at freeze time (recorded in `CAPTURE_CONTRACT.json`,
  authored-blob-hash gated, **not** gated on live `HEAD`).
- Device: Apple M4 (G16G), Mac16,10, 10 GPU cores, macOS 26.6.x, Metal 4.
- Compiler: runtime `newLibraryWithSource:` only (no offline `metal` CLI), matching
  `SUBAGENT_BRIEF.md` and every prior M4 experiment in this family.

## Public-header groundwork (recorded here so hypotheses below cite it precisely; this is
PUBLIC SDK header text — struct/method declarations, not any Apple binary — read from
`MacOSX26.5.sdk/.../Metal.framework/Headers/*.h`)

- `MTLCounters.h`: `MTLCounterErrorValue = ~0ULL`; `MTLCommonCounterSet{Timestamp,
  StageUtilization,Statistic}` are *named constants* the docstring says an implementation
  "may omit ... from these sets" — i.e. the header declares the possible vocabulary, not
  M4's actual support. `MTLCounterSampleBufferDescriptor.storageMode` "Only
  MTLStorageModeShared and MTLStorageModePrivate may be used." `resolveCounterRange:`
  "may only be used with sample buffers that have MTLStorageModeShared."
- `MTLDevice.h`: `counterSets`, `supportsCounterSampling:` over
  `MTLCounterSamplingPointAt{Stage,Draw,Dispatch,TileDispatch,Blit}Boundary`,
  `sampleTimestamps:gpuTimestamp:`, `newIndirectCommandBufferWithDescriptor:maxCommandCount:
  options:`.
- `MTLComputeCommandEncoder.h`: `MTLDispatchThreadgroupsIndirectArguments{uint32
  threadgroupsPerGrid[3]}` consumed only by `dispatchThreadgroupsWithIndirectBuffer:...`
  (classic API has **no** indirect-*threads* dispatch on the classic
  `MTLComputeCommandEncoder`, despite a declared-but-orphaned
  `MTLDispatchThreadsIndirectArguments` struct). `MTL4ComputeCommandEncoder.h` (new Metal 4
  encoder family) **does** add `dispatchThreadsWithIndirectBuffer:` over a raw
  `MTLGPUAddress` — out of scope for this experiment (classic API only, matching every
  prior EXP in this family); flagged as residual MTL4-specific work.
- `MTLIndirectCommandBuffer.h` / `MTLIndirectCommandEncoder.h`: `MTLIndirectCommandType`
  bits (`Draw`, `DrawIndexed`, `ConcurrentDispatch`, `ConcurrentDispatchThreads`, ...);
  "`MTLCommandTypeDispatch` cannot be mixed with any other command type"; CPU-side
  `MTLIndirectComputeCommand`/`MTLIndirectRenderCommand` protocols expose
  `setBarrier`/`clearBarrier`/`reset` even on a GPU-encoded command (post-hoc CPU
  modification of a GPU-authored ICB record).
- `MTLRenderCommandEncoder.h`: `MTLVisibilityResultMode{Disabled,Boolean,Counting}`,
  `setVisibilityResultMode:offset:`.
- `MTLBlitCommandEncoder.h`: `sampleCountersInBuffer:atSampleIndex:withBarrier:`,
  `resolveCounters:inRange:destinationBuffer:destinationOffset:` (GPU-side resolve, distinct
  from the CPU-side `resolveCounterRange:`).

These are cited as `PUBLIC` (structural) facts throughout; every semantic claim below is
independently tested on live hardware, not inferred from the header alone.

## Hypotheses, variables, falsifiers

### Group Q — P1.6 counter heap / query semantics

**H-Q1 (counter-set census).** M4's `device.counterSets` contains a `timestamp`-named set
and does **not** contain a working `statistic`-named set (i.e. pipeline statistics are not
natively exposed on M4), matching Apple's public Apple-GPU feature-set documentation history.
*Independent variable:* none (device capability query). *Expected if true:* `counterSets`
names include "timestamp" only (`MTLCommonCounterSetTimestamp`); no "statistic"/
"stageUtilization" entry, or an entry present but empty/all-`MTLCounterErrorValue` on
resolve. *Falsifier:* a "statistic" or "stageUtilization" set present AND its resolved
values are real (nonzero, matching a closed-form invocation count) after a draw/dispatch —
that would flip this to a **positive** capability finding, which is exactly the desired
outcome either way (a clean negative or a clean positive both close the P1.6 pipeline-stats
question).

**H-Q2 (availability sentinel).** An index in a `MTLCounterSampleBuffer` that has never been
targeted by any `sampleCountersInBuffer:` call resolves to exactly `MTLCounterErrorValue`
(`~0ULL`), and an index sampled by a command buffer that has been committed but has not yet
reached `MTLCommandBufferStatusCompleted` resolves to a value distinguishably different from
its post-completion value (either the sentinel or a stale pre-write value) — this is the
exact ambiguity EXP-0052 left open ("did not sample command-buffer status at that instant").
*Independent variable:* whether resolve happens before commit / after commit-but-unwaited
(polled via `status`) / after `waitUntilCompleted`. *Falsifier:* the pre-commit resolve
returns anything other than `MTLCounterErrorValue`, or the post-completion resolve is
indistinguishable from the pre-commit one.

**H-Q3 (allocation limits).** `newCounterSampleBufferWithDescriptor:error:` accepts a wide
range of `sampleCount` values with `storageMode=Shared`, rejects (via `error`, not a crash)
`storageMode=Managed`, and has a finite ceiling before either a graceful `nil`+`error` or a
process-level crash (per the `h_icbmax` precedent in EXP-0098, GPU allocation APIs on this
stack are not uniformly crash-safe at extreme sizes). *Falsifier:* `Managed` succeeds, or no
ceiling is found below a machine-safe cutoff, or a graceful `nil` appears instead of the
predicted crash-style failure (also informative, not a falsifier of the overall family, but
recorded either way).

**H-Q4 (index reuse is overwrite, not accumulation).** Re-sampling the same index (same
`MTLCounterSampleBuffer`, same slot, in a later command buffer) simply overwrites the prior
value; `resolveCounterRange:` itself is idempotent (non-destructive; resolving the same
range twice returns identical bytes both times). *Falsifier:* a second resolve of the same
unchanged range returns different bytes than the first (destructive resolve), or a reused
index's second sample is influenced by (e.g. summed with) the first.

**H-Q5 (GPU-side resolve matches CPU-side resolve).** `-resolveCounters:inRange:
destinationBuffer:destinationOffset:` (blit-encoder, GPU-side, writes into an
`MTLBuffer`) produces byte-identical payload to `-resolveCounterRange:` (CPU-side,
`NSData`) for the same range of the same sample buffer. *Falsifier:* any byte difference for
a range with no error values.

**H-Q6 (concurrency).** Two independent `MTLCounterSampleBuffer` objects (same or different
counter sets) can be sampled within the same encoder, or on two independently in-flight
command buffers on two queues, without cross-contamination — each buffer's values depend
only on its own sample calls. *Falsifier:* any observed cross-buffer contamination, silent
serialization producing wrong per-buffer values, or an outright fault/rejection when a
second concurrent sample buffer is used.

**H-Q7 (occlusion: counting is per-fragment-invocation, not per-unique-pixel; boolean
saturates at 1).** With depth/stencil test disabled, two fully-overlapping full-viewport
draws under one active `counting`-mode query report `2N` for an `N`-pixel viewport (each
draw's fragment invocations both count), while the same scenario under `boolean` mode
reports exactly `1`. *Falsifier:* counting reports `N` (deduplicated) or something other
than `2N`; boolean reports anything other than `0`/`1`.

**H-Q8 (offset reuse within one encoder is overwrite, not accumulation).** Calling
`setVisibilityResultMode:offset:` twice at the **same** offset within one encoder, with an
intervening draw under each activation, leaves the buffer holding only the **second**
activation's count (overwrite), not the sum of both (accumulation). *Falsifier:* the final
value equals the sum of both draws' expected counts.

**H-Q9 (tick unit cross-check).** A `timestamp`-counter-set sample resolved via the counter
heap and a `device sampleTimestamps:gpuTimestamp:` call taken in the same narrow window are
on the same clock domain: their values are close in magnitude (same order, monotonically
consistent with a controlled CPU-side delay between them), consistent with EXP-0027's A18
DATA-TRACE finding of "uint64 nanoseconds, period 1.0" carrying over to M4's public-API
timestamp counter set. *Falsifier:* the counter-heap timestamp value is off by several
orders of magnitude from the paired `sampleTimestamps` GPU value, or is not monotonic with
it under a controlled delay.

**WRAP** is **not** empirically tested (would require ~584,942 years of continuous operation
for a 64-bit ns counter to wrap); this is answered by direct arithmetic from the established
8-byte/ns-unit fact and documented as `INFERRED`, not `HW-VALIDATED`, with the derivation
shown in `RESULTS.md`.

### Group I — P1.7 indirect / device-generated commands

**H-I1 (indirect-dispatch parameter format, byte-exact).** A compute kernel that writes
three consecutive `uint32` values `(X,Y,Z)` at the start of a buffer, consumed by
`dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:threadsPerThreadgroup:`,
produces a dispatch grid of exactly `X × Y × Z` threadgroups in that axis order (not
reversed/interleaved). *Falsifier:* a swapped/reversed axis order, or invocation count not
matching `X*Y*Z*threadsPerThreadgroup.x*...`.

**H-I2 (indirect-dispatch boundary behavior).** Zero in any axis produces zero invocations
with no fault; very large single-axis values (up to the tested ceiling) either complete
(possibly slowly) or time out under a hard per-process timeout, but do not silently truncate
to a smaller-than-requested grid. *Falsifier:* a nonzero-axis case that dispatches strictly
fewer invocations than `X*Y*Z*(threads per threadgroup)` predicts (silent clamp), or a crash
signature symmetrical to the `h_icbmax` finding at a specific boundary (also a first-class
result if found, not a falsifier of the overall hypothesis structure).

**H-I3 (writable ICB grammar — render).** A compute kernel using MSL's ICB-encoding
intrinsics (`render_command`/`command_buffer`, from `<metal_command_buffer>`, over an ICB
created with `inheritPipelineState=YES, inheritBuffers=NO`) can legally call
`set_vertex_buffer`/`set_fragment_buffer`/`draw_primitives`/`draw_indexed_primitives`/
`reset` with computed (not compile-time-constant) offsets and counts, and the resulting
GPU-authored command executes identically to an equivalent CPU-encoded one. *Falsifier:* a
compile failure for any construct in this list against the *documented* MSL ICB API surface,
or an executed GPU-authored command producing incorrect pixel output that a CPU-encoded
equivalent gets right.

**H-I4 (writable ICB grammar — inheritBuffers).** With `inheritBuffers=YES`, a GPU-authored
command that does **not** call `set_vertex_buffer` correctly uses the buffer bound on the
render encoder via `setVertexBuffer:` before `executeCommandsInBuffer:`. *Falsifier:* the
inherited buffer is not used (garbage/zeroed output) or the omission faults.

**H-I5 (concurrent-dispatch barrier).** For an ICB created with
`commandTypes=MTLIndirectCommandTypeConcurrentDispatch` containing a producer compute
command (writes X) and a consumer compute command (reads X, writes `2*X`), calling
`-setBarrier` (CPU-side, on the `id<MTLIndirectComputeCommand>` for the consumer, obtained
via `indirectComputeCommandAtIndex:` after GPU encoding) makes the consumer's read
deterministically observe the producer's write across repeated trials; omitting the barrier
exposes at least one trial (of a repeated sweep) where the consumer observes the
pre-write value. *Falsifier:* the unbarriered control never races across the full repeated
sweep (would mean concurrent-dispatch ICBs are safely ordered by default, itself a valid
and useful negative), or the barriered case ever races (would mean `setBarrier` does not
enforce the documented ordering).

**H-I6 (stream-limit cliff, narrowed).** EXP-0098 bracketed the `newIndirectCommandBuffer
WithDescriptor:maxCommandCount:` crash boundary between 4,194,304 (works) and 8,388,608
(SIGSEGV) but did not narrow it ("not required by the addendum"). This experiment's
addendum explicitly asks for the exact cliff: a bisection between those two bracket points
converges to a single exact `maxCommandCount` value `V` such that `V` allocates successfully
and `V+1` (or the next tested granularity) crashes, reproduced at least once independently
after the bisection converges. *Falsifier:* the boundary is not monotonic (a larger value
succeeds after a smaller one crashed) — itself an important, reportable anomaly, not a
disqualification of the experiment.

**H-I7 (primitive restart on strip topology).** `MTLPrimitiveTypeTriangleStrip` with a
`0xFFFFFFFF` (32-bit) or `0xFFFF` (16-bit) sentinel index placed mid-strip is interpreted as
a strip-restart marker (splitting the strip into independent pieces, matching Vulkan/GL/D3D
strip-restart conventions), the same way EXP-0098 found the sentinel is **not** special for
non-strip (`MTLPrimitiveTypePoint`) topologies. *Independent variable:* topology
(strip vs. point, the latter as an internal control reproducing EXP-0098's finding).
*Falsifier:* the strip case also treats the sentinel as an ordinary (huge) index value
(fault or garbage-but-no-restart), which would mean Metal's public API provides no strip
restart at all and a driver must never rely on it.

## Confounders

- Metal's device-side scheduler/coalescing may reorder or batch commands in ways invisible
  to this experiment; only externally observable readback/status/fault outcomes are
  promoted, never assumed internal mechanism.
- Extreme-size allocation/dispatch cases risk process crash or GPU fault; every such case is
  isolated to its own process with a hard timeout per the SAFETY directive, and a crash/fault
  is recorded as the result, not treated as harness failure.
- `MTLCounterErrorValue` collides bit-for-bit with a legitimate (if enormous) resolved
  counter value only in the practically-unreachable case of an actual `2^64-1`-tick count;
  not treated as a source of ambiguity.
- All findings are M4/G16G-only; no A18 Pro claim is made anywhere in this experiment.

## Method summary (detail in `README.md`)

Two ObjC harness binaries (`harness/qbench.m` for Group Q, `harness/ibench.m` for Group I),
each compiled once, each invocation running **exactly one case** selected by `--family`/case
parameters (SAFETY: one case per process for this entire family, per dispatch instructions),
printing a `STATUS`/`DEVICE`/`OBSERVED` text protocol to stdout (the established convention
from EXP-0098's `gddraws.m`/`xfbdraws.m`, reused here as our own prior authored code — not
Apple code). `harness/casematrix.py` freezes the case list; `harness/run.py` drives one
subprocess per case under a hard `timeout`, splitting each result into a **gated** record
(`case_id, family, kind, params, status, verdict, observed` — no raw tick values) and a
**non-gated sibling** record (`case_id, wall_ms, pid, raw_tail, raw_ticks` — where
`raw_ticks` holds any nanosecond-valued fields for that case, explicitly excluded from the
cross-run byte-compare gate). `harness/verify.py` implements the five standing gates.

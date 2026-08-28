# EXP-0098 pre-registration — M4 GPU-driven draws (Bundle H) and compute-emulated transform feedback (Bundle I)

Date: 2026-08-28. Target: local Apple M4 / G16G only (Mac16,10, macOS 26.6.2 build 25G82, Metal
4). A18 Pro remains hands-off per `CLAUDE.md`; nothing here depends on it.

This file must be committed (in this experiment's working state) before any *official* capture
run. Build-time calibration (below) preceded this freeze, per `CODEX.md` step 2/3 and the
`EXP-0093` precedent for pre-freeze parameter tuning; the frozen matrix, hypotheses, and
falsifiers are locked as of this file's commit and were not modified afterward.

**Pinned revision (recorded now, gated on at capture time by authored-blob hash, not on live
`HEAD` — `SUBAGENT_BRIEF.md`'s explicit guidance, since sibling experiments commit continuously):**
`39af7f9314e5d6c49eea21465cd02682bf48d117` (repository dirty: 11 untracked/modified paths outside
this experiment's own tree at pin time — pre-existing sibling-experiment work, not touched by
this experiment).

## Addendum items in scope

- **GLPRE-A01** — compute-to-draw visibility for GPU-generated geometry/parameter/indirect-draw
  records; exact CDM/VDM-equivalent synchronization requirement at the **public Metal API**
  boundary (per the addendum's own instruction, this bundle does not build native command-stream
  grammar).
- **GLPRE-A02** — device-generated draw/index grammar and hard limits: exact fields, address/
  count/stride/index-type/restart/base-vertex/instance fields after a shader (not CPU state)
  writes them; which fields are read at execution time; finite-resource boundaries (max ICB
  commands, count-buffer semantics).
- **GLXFB-A01** — compute-emulated OpenGL transform feedback via global-memory writes + atomic
  counters into all four buffers/streams, feeding a generated draw; exact synchronization for the
  streamout→draw handoff; capacity/no-partial-primitive semantics.

## Clean-room scope note (per the addendum's own instruction)

Both bundles stay on the **public Metal API surface**. No assembler, no native VDM/CDM grammar,
no `tools/agx-isa`, no splicing, no `tools/agxtest`/`tools/shdump`. All facts referenced from
Apple's SDK headers below are **public developer documentation** (Xcode's shipped
`Metal.framework/Headers`, freely distributed to any developer — struct layouts and method
signatures, not executable code), consulted the same way CLAUDE.md's PUBLIC category covers any
other public specification; no Apple binary was disassembled, decompiled, or otherwise
introspected.

**`work/COMPILER-EXPLAINER-INTERACTION-20260828.md` (a `tools/agx-isa/db.json` ALU
source-register decoding-bug analysis) is read and is structurally inapplicable to this
experiment**: EXP-0098 uses no assembler, no `tools/agx-isa`, and no native instruction encoding
anywhere in its design. Stated explicitly in RESULTS.md per the relaunch instruction, not left
implicit.

## Mechanism used to force a "compute writes it, not the CPU" record

Every producer/consumer pair below has its record bytes written by a **compute kernel's own store
instructions** (`kernels/h_chain.metal`, `kernels/h_icbrange.metal`, `kernels/xfb.metal` — all
OWN-SHADER, authored MSL compiled via the public `newLibraryWithSource:` runtime path), never by
CPU `-[MTLBuffer contents]` writes to the record itself. The one CPU-authored control
(`cpu_baseline` in the h_sync family) exists solely as a ground-truth sanity check that the
verification pipeline itself is correct, and is labeled as such throughout.

## Mechanism used to force a genuinely unsynchronized producer/consumer pair

Public, documented Metal API only:

- `MTLResourceHazardTrackingModeUntracked` (`MTLResource.h`: "may optionally be specified for
  non-heap resources") on every buffer touched by both the producer and the consumer.
- Two independent `MTLCommandBuffer`s on one `MTLCommandQueue`, committed back-to-back with **no**
  CPU-side wait between commits (`unsync_split`), or with a `MTLFence` (`updateFence:`/
  `waitForFence:beforeStages:`) asserted on only one side (`asym_producer`/`asym_consumer`).
- The correctly-synchronized controls are `encoder_order` (default `MTLResourceHazardTrackingModeTracked`,
  producer and consumer in two encoders of **one** command buffer — Metal's documented automatic
  inter-encoder dependency tracking) and `fence_sym` (`Untracked` resources, explicit
  `updateFence:`/`waitForFence:beforeStages:` on **both** sides).

This is the direct generalization the relaunch message asks for: `EXP-0093` proved asymmetric
device-memory fencing is unsafe at ≥4 concurrent producer/consumer pairs at the **shader
instruction** level (`ATOM-08`); this experiment asks the analogous question at the **command-
buffer/resource-hazard** level, and is calibrated (below) to run at a concurrency/duration scale
that actually exposes it, not at a token 1–2-thread scale.

## Verification technique ("did the consumer see fresh or stale producer data")

`v_verify` (a vertex function present in all three kernel files) is bound as the consuming draw's
vertex stage; its only job is `seen[clamp(iid)*vertexCap + clamp(vid)] = uint4(vtxIn[clamp(vid)].x,
vtxIn[clamp(vid)].y, vid, iid)` — a device-buffer side effect, decoupled from rasterization (a
degenerate `pos=(0,0,0,1)` every time; nothing depends on what actually rasterizes). Every
resource is pre-filled with a `SENTINEL=0xDEADBEEF` pattern before dispatch. A slot whose read-back
`.x` still equals `SENTINEL` after the consuming draw completed means the consumer observed data
older than the producer's writes despite program-order submission — the staleness signature used
throughout. `.z`/`.w` are written directly from vertex-shader builtins (never read from the
racing buffer), so they are always correct regardless of staleness and serve as an
invocation-identity sanity check independent of the race question.

## Pre-registered hypotheses and falsifiers

**H1 (h_sync).** A compute-shader-written vertex buffer + `MTLDraw[Indexed]PrimitivesIndirectArguments`
record, placed in a **prior encoder of the same command buffer** as the consuming draw
(`encoder_order`, default Tracked hazard mode) is visible to the draw with no explicit fence,
exactly as `EXP-0053` found for the simpler indirect-dispatch case. `fence_sym` (explicit
symmetric `MTLFence`) is equally safe. `unsync_split`/`asym_producer`/`asym_consumer` are **not**
guaranteed safe and are expected to show genuine staleness (`n_stale>0`) in at least one repeat at
scale, though — being a genuine race — not necessarily in every repeat.

- Falsifier for the safe modes: any `n_stale>0` or `n_correct != n` in `cpu_baseline`,
  `encoder_order`, or `fence_sym` at the calibrated scale.
- Falsifier for the unsafe modes as a *class*: **zero** staleness across all
  `H_SYNC_UNSAFE_REPEATS × 2 index-modes × 2 official runs` (20) unsafe-mode repeats — would mean
  the calibrated scale fails to exercise a real hazard, not that none exists.

**H2 (GLPRE-A02 field legality).** Every field of `MTLDraw[Indexed]PrimitivesIndirectArguments`
that a compute kernel writes (`vertexCount`/`instanceCount`/`vertexStart`/`baseInstance`/
`indexCount`/`indexStart`/`baseVertex`) is read and honored at draw-execution time, including
zero-count draws (no invocations), `instanceCount>1` with nonzero `baseInstance` (an **absolute**,
not local, `[[instance_id]]` — a specific sub-hypothesis added after the build-time finding
below), 16- and 32-bit indices, a deliberately out-of-range restart-sentinel index value against a
non-strip topology, a safely-bounded negative `baseVertex`, and a misaligned `indirectBufferOffset`.

- Falsifier: any case's invoked-vertex count or per-invocation data mismatches the value computed
  independently in `run.py` from the same written fields.

**H3 (GLPRE-A02 count-buffer/ICB limits).** `executeCommandsInBuffer:indirectBuffer:
indirectBufferOffset:` honors a compute-written `MTLIndirectCommandBufferExecutionRange
{location,length}` record as `max(0, min(length, maxCommandCount-location))` executed commands
when `location<maxCommandCount`, else 0 — i.e. an oversized or past-the-end range is **silently
clamped/ignored, not rejected or faulting**. `newIndirectCommandBufferWithDescriptor:
maxCommandCount:` has a practical ceiling between 4,194,304 (succeeds) and 8,388,608 (a CPU-side
process crash, build-time-confirmed twice) — a first-class finite-resource boundary.

- Falsifier: any executed-command count that does not match the closed-form formula above, or a
  GPU-side fault/hang (as opposed to a clean CPU-side allocation crash) at any tested
  `maxCommandCount`.

**H4 (GLXFB-A01 capacity).** A compute streamout kernel that atomically reserves whole-primitive
vertex blocks per stream (`atomic_fetch_add` by exactly `vertsPerPrimitive`, write only if
`reserved+vertsPerPrimitive <= capacity`) writes **exactly** `floor(min(requests, capacity/vpp)) ×
vpp` vertices per stream, deterministically (order-independent, since every request reserves the
identical size) regardless of GPU thread-scheduling order, and **never** a partial primitive: the
first byte at/after the expected-written boundary remains `SENTINEL`.

- Falsifier: `written` count deviating from the closed form, or any non-`SENTINEL` byte found
  beyond the computed boundary (a real partial-primitive write).

**H5 (GLXFB-A01 streamout→draw sync).** The same six-way (five for XFB, `cpu_baseline` is not
meaningful for an inherently GPU-generated capture) synchronization contract from H1 applies to
the streamout-capture → indirect-args-finalize → replay-draw chain.

- Falsifier: staleness in `encoder_order`/`fence_sym`, or **zero** staleness/anomaly across all
  unsafe-mode repeats at the calibrated scale.

## Build-time findings (informed the frozen matrix; not themselves promoted as capture-run facts)

All of the following were observed interactively on this M4 before this file was committed, using
the same authored binaries (`work/bin/gddraws`, `work/bin/xfbdraws`) that the frozen matrix calls,
built from source hashes identical to what `CAPTURE_CONTRACT.json` freezes:

1. **h_sync calibration.** `n=65536` with a per-thread `spinIters=100000` sequential-dependency
   busy-loop (LCG recurrence, folded into an otherwise-unread output word so the compiler cannot
   eliminate it) in the producer kernel: `cpu_baseline`/`encoder_order`/`fence_sym` were correct in
   **every** trial (≥16 combined trials across both index modes); `unsync_split` raced in 4/5
   trials (one showed `n_correct=447/65536`, one `n_correct=0/65536` = 100% stale, one clean);
   `asym_producer` showed `n_correct=0/65536` on one trial and clean on others; `asym_consumer`
   raced on 1/3 trials shown (`n_correct=3359/65536`). Pure thread-count scaling **without** the
   spin loop (`n` up to 16,777,216, no spin) never raced — the sequential-dependency **duration**
   of the producer dispatch, not its total thread count, is what exposes the hazard. Indexed h_sync
   at the same scale raced in **all 6/6** unsync/asym-producer trials shown, more severely
   (`n_correct=1/65536` twice) — plausibly because a stale index buffer amplifies the effect
   through `vid` itself, not just through the fetched vertex data.
2. **xfb_sync calibration — a materially different failure signature than h_sync.**
   `numPrimitives=4096` with `spinIters=500000` in the (heavier: atomics + a 16-byte byte-copy
   loop) capture kernel: `unsync_split`/`asym_producer`/`asym_consumer` **never** showed data
   staleness in build-time trials, but **consistently** (4/4, 3/3, and 2/2 trials respectively)
   took ≈15.5s to complete versus ≈0.02–0.6s for `encoder_order`/`fence_sym` or for `unsync_split`
   at a tiny/zero-spin scale. This is recorded as its own finding, not assumed to generalize from
   h_sync's result: Bundle I's specific (atomic-heavy) producer shape did not reproduce Bundle H's
   corruption signature at the tested scale, but exhibits a large, reproducible **completion-
   latency penalty** under the same nominally-unsynchronized configuration that Bundle H's
   simpler producer does not show. The exact mechanism is `UNKNOWN` (plausibly some
   fault/coherency-recovery path triggered by the untracked+atomic combination) and is flagged,
   not silently dropped. A secondary anomaly, `n_invoked` reporting exactly one more touched slot
   than the expected written count, was observed **only** alongside this latency penalty (never
   in a fast trial) — consistent with, but not proof of, an internal retry mechanism; recorded as
   `UNKNOWN`/informational.
3. **`[[instance_id]]` is absolute, not local.** `baseInstance=5, instanceCount=3` produced
   `[[instance_id]]` values `{5,6,7}`, not `{0,1,2}` — discovered when an under-sized verification
   buffer (sized to `instanceCount` alone) silently zero'd its invocation count; fixed by sizing
   `seen[]` to `baseInstance+instanceCount` before any official capture. Recorded as a genuine
   `H2` sub-finding, not merely a harness bug footnote.
4. **`supportIndirectCommandBuffers` is required on the render pipeline used via
   `executeCommandsInBuffer:`**, even though `MTLIndirectCommandBufferDescriptor.inheritBuffers`
   was initially (incorrectly) left `YES` while also calling `-setVertexBuffer:` per ICB command —
   the combination faulted the command buffer (`kIOGPUCommandBufferCallbackErrorPageFault`) until
   both were corrected (`inheritBuffers=NO` to match per-command explicit buffer binding, and
   `supportIndirectCommandBuffers=YES` on the pipeline descriptor). Fault was command-buffer-level
   and fully contained; host and GPU were confirmed responsive immediately after both occurrences.
5. **ICB restart-sentinel index against a non-strip topology (`MTLPrimitiveTypePoint`) is treated
   as an ordinary (very large) index value**, not specially interpreted — `vid=0xFFFFFFFF` was
   safely fetched (clamped by this harness's own defensive `min(vid,capacity-1)`, never by
   hardware/driver rejection) and its data was correct at the clamped slot. Primitive-assembly-
   level restart-splitting (a strip-topology-specific effect) is **not observable** by this
   experiment's per-vertex-invocation verification method and is explicitly deferred, `UNKNOWN`,
   not silently skipped.
6. **A misaligned (`+2` byte) `indirectBufferOffset` was accepted without rejection or fault** for
   `drawPrimitives:indirectBuffer:offset:` in the tested case.
7. **`newIndirectCommandBufferWithDescriptor:maxCommandCount:` boundary:** 1,024 / 65,536 /
   1,048,576 / 4,194,304 all allocate successfully (`size` reads back exactly as requested);
   8,388,608 crashes the calling **process** (`SIGSEGV`, before any GPU dispatch — confirmed twice
   independently) — a CPU-side (not GPU-side) failure, fault-contained to that one process; host
   and GPU confirmed responsive immediately after both occurrences.
8. **Full-matrix pilot dry-run (`trial01`, written to a scratch `/tmp` directory, never
   `raw/`) surfaced three further build-time findings before this file's freeze:**
   - **A real hardware/driver finding, reproduced twice:** an `h_icbrange` case with
     `location` (10) STRICTLY GREATER than `maxCommandCount` (8) — as opposed to
     `location==maxCommandCount` (finding #-adjacent above: safely executes 0 commands) —
     causes a genuine GPU-side `kIOGPUCommandBufferCallbackErrorPageFault`, not a silent
     no-op. Both occurrences were command-buffer-level faults only; host and GPU were
     confirmed responsive immediately after each. This case (`hicbrange_loc_past_max`) is
     frozen into the matrix with an explicit `expect_fault=True` annotation so its verdict
     correctly means "faulted as predicted," not "unexpectedly broke."
   - **Two harness bugs, found and fixed, not hardware facts:** (1) `run.py`'s expected-
     invocation formula for `h_fields` used `vc*max(ic,1)`, silently treating
     `instanceCount=0` as `instanceCount=1`; a real dispatch with `ic=0` correctly produces
     zero invocations (`n_invoked=0`), so the formula is `vc*ic`. (2) `xfbdraws.m`'s
     no-partial-primitive boundary check compared a raw 4-byte read against the literal
     constant `0xDEADBEEF`, which is only valid when the checked byte offset is itself
     4-byte-aligned relative to the fill pattern's own phase — for a deliberately
     misaligned stride/offset case the check read a rotated phase of the SAME untouched
     sentinel fill and falsely reported a violation. Fixed to a phase-correct, per-byte
     comparison against the repeating `EF BE AD DE` pattern over a full 16-byte span. Both
     fixes were verified against fresh individual dispatches before being folded back into
     the frozen matrix; host/GPU health was reconfirmed after the fault-reproducing case.

9. **Session-continuity note.** An early, uncalibrated interactive probe
   (`unsync_split --n 65536 --spin 100000`, before finding #1's later, correctly-calibrated
   result) was launched without an explicit hard timeout and the session was interrupted by an
   unrelated host/terminal problem (not a GPU wedge — confirmed on resume: no stray process, `ps`/
   `uptime` normal, a fresh tiny dispatch completed immediately). Every GPU-touching command from
   that point forward in this experiment's build-time work used an explicit hard timeout; the
   frozen `run.py` enforces `RUN_TIMEOUT_S=90` (comfortably above the ~15.5s xfb_sync stall) via
   `subprocess.run(timeout=...)` for every official case regardless.

## Frozen matrix

`harness/casematrix.py` (111 cases): `h_sync` (36: 2 index-modes × [3 safe modes × 2 repeats + 3
unsafe modes × 4 repeats]), `h_fields` (16: baseline + one-variable-at-a-time perturbations,
`CODEX.md` step 3), `h_icbrange` (9: location/length boundary sweep against a fixed
`maxCommandCount=8`), `h_icbmax` (5: allocation census including the confirmed crash boundary),
`xfb_capacity` (18: 9 cases × 2 repeats — exact-fit/one-short/way-under/zero/huge capacity,
`vpp∈{1,3}` boundaries, one interleaved-2-attribute layout, one deliberately misaligned
stride/offset layout), `xfb_multistream` (10: 5 cases × 2 repeats — all-4-active, alternating
pairs, GS-shaped differing-per-stream fan-out replayed from each of its two active streams,
single-stream passthrough), `xfb_discard` (4: 2 cases × 2 repeats), `xfb_sync` (13: 2 safe modes ×
2 repeats + 3 unsafe modes × 3 repeats).

Every deterministic case (`h_fields`, `h_icbrange`, `h_icbmax`, `xfb_capacity`,
`xfb_multistream`, `xfb_discard`, and the safe-mode halves of `h_sync`/`xfb_sync`) has a verdict
independently computed in `run.py` from a closed-form expected value, gated for byte-identical
cross-run agreement with **no** exclusion. Every unsafe-mode `h_sync`/`xfb_sync` case has verdict
`N/A` (a single trial cannot confirm or refute a probabilistic hazard) gated strictly (an `N/A` is
still compared for byte-identity across runs, and a producer-side invariant — `gen`/`wr` counts,
which are unaffected by the *consumer's* racy read timing — is still checked and can flip the
verdict to `FAIL`), with the noisy consumer-observed fields (`n_correct`/`n_stale`/`n_other`/
`n_z_wrong` for h_sync; `n_invoked`/`n_correct`/`n_stale`/`replay_vertexCount` for xfb_sync)
declared order-sensitive per `casematrix.case_order_sensitive_keys` and excluded from the strict
byte-identity comparison, exactly as `EXP-0093` did for its `devfence_pairs`/`rogbuf_splice`
families. `harness/verify.py --selftest` proves this separation mechanically (gate passes when
only excluded keys differ; gate fails when `verdict` or a non-excluded key differs), grounded in
`harness/fixtures/recorded_reality.json` (real M4 captures, not hand-typed constants).

## Standing gate set (implemented; see RESULTS.md §"Standing gate results" for the pass record)

(a) one authoritative shared key set (`harness/schema.py`), imported by both `run.py` and
`verify.py`, `verify.py --selftest` runnable in every tree state (pure data/offline).
(b) `verify.py --seqtest`: `PRE_GPU → RUN01_PRESENT → RUN02_PRESENT` state machine, each state's
gate proven to pass only in its contracted state.
(c) NON-RECORDED smoke gate (`run_smoke()` in `run.py`) — a real GPU dispatch written to `work/`,
never `raw/`, before any raw artifact for that run is created; a smoke failure aborts before any
`raw/` write.
(d) no nondeterministic field inside any strictly byte-compared record; the deliberately-
unsynchronized/asymmetric controls are legitimately nondeterministic — handled by the
order-sensitive-key exclusion above, proven separately in `verify.py --selftest`, with the raw
per-run values preserved verbatim in `raw/<run>/03_nongated.jsonl`'s `raw_tail` (the full captured
stdout `OBSERVED` line) as the "sibling non-gated file."
(e) selftest fixtures built from `harness/fixtures/recorded_reality.json` — four real M4 captures
recorded during this build-time calibration, referenced (not hand-typed) by `verify.py --selftest`.

Plus: single-threaded harness (`run.py` runs cases strictly sequentially; each case is its own
`work/bin/{gddraws,xfbdraws}` subprocess); both ObjC binaries use `fflush(NULL)`/`ferror(stdout)`
exit discipline on every exit path (`fail()`); `raw/` is append-only (`run.py` refuses to write
into an existing `--out` directory); hard timeout (`RUN_TIMEOUT_S=90`) on every subprocess call;
each case its own process; faults and hangs are recorded as results (`CMDBUF_ERROR`/`HANG`/
`HARNESS_CRASH` are valid `status` values in the frozen schema, not exceptions); run ids are never
reused (`run.py` refuses an existing `--out`); no post-capture repair of a hash-frozen file (any
defective run is retained and superseded by a **new** run id, never edited in place, per
`SUBAGENT_BRIEF.md`'s `EXP-0085` warning).

## Process and stop rules

- This file, `CAPTURE_CONTRACT.json`, and every file `CAPTURE_CONTRACT.json` hashes must be
  committed to this experiment's own tree (not `git commit`d — the orchestrator commits; "frozen"
  here means "not edited again") before the first official capture run.
- Two official capture runs, `m4_20260828_run01` and `m4_20260828_run02`, executed with
  `harness/run.py --run <id> --out raw/<run_id>`. Neither run id may be reused; a defective run is
  retained and a new run id is used for its replacement, never edited or deleted.
- If the host wedges or behaves strangely during either official run: **stop immediately**, mark
  this experiment `BLOCKED` in `PROGRESS.md` with the exact last-completed case, and wait for the
  user to reboot manually. No `macvdmtool`, no tool-based reboot, ever.
- `tools/*` is read-only and unused by this experiment (no assembler needed, per the addendum's
  own instruction — confirmed above).

## Clean-room boundary

```text
Clean-room provenance: HW-PROBE + OWN-SHADER + PUBLIC (Xcode SDK public headers)
Inputs permitted: this pre-registration; authored Objective-C (harness/gddraws.m,
  harness/xfbdraws.m) and MSL (kernels/h_chain.metal, kernels/h_icbrange.metal, kernels/xfb.metal);
  authored Python (harness/schema.py, harness/casematrix.py, harness/run.py, harness/verify.py);
  public Metal command completion status and bytes in resources allocated by this process;
  Metal.framework's public SDK headers (struct/method declarations only, MacOSX26.5.sdk)
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE (only our own MSL, compiled and run, never extracted/
  disassembled)
IOKit/BO payload tracing: NONE
tools/agx-isa / assembler: NOT USED (public Metal API surface only, per addendum instruction)
Pointer following: NONE beyond this process's own allocated MTLBuffers
Mutation/splice: NONE
```

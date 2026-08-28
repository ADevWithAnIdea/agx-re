# EXP-0098 PROGRESS (timestamped milestones)

All timestamps UTC. Target: local Apple M4 only. No A18 touch. No git commits (orchestrator owns
commits). tools/* read-only (not used at all by this experiment -- public Metal API surface only,
per the addendum's own instruction, no assembler needed).

## 2026-08-28T03:10Z -- start
- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, work/ADDENDUM-TRIAGE-20260828.md
  (Bundle H / Bundle I sections), APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md (GLPRE-A01, GLPRE-A02,
  GLXFB-A01 exact wording), predecessors EXP-0053 (harness/probe.m -- extension basis),
  EXP-0027, EXP-0093 (RESULTS.md, harness/{schema,casematrix,run,verify}.py -- adopted as the
  standing-gate-set template, harness/roglitmus.m for ObjC/Metal idiom).
- Confirmed public Metal API surface for the whole design via the Xcode SDK's public headers
  (MacOSX26.5.sdk, Metal.framework/Headers -- public developer documentation, not binary
  introspection): MTLDrawPrimitivesIndirectArguments / MTLDrawIndexedPrimitivesIndirectArguments
  (MTLRenderCommandEncoder.h), MTLIndirectCommandBufferExecutionRange (MTLIndirectCommandBuffer.h),
  MTLFence updateFence:/waitForFence:/updateFence:afterStages:/waitForFence:beforeStages:
  (MTLFence.h, MTLComputeCommandEncoder.h, MTLRenderCommandEncoder.h),
  MTLResourceHazardTrackingModeUntracked as a legal option for standalone (non-heap) buffers
  (MTLResource.h: "may optionally be specified for non-heap resources").
- Designed the sync-variant matrix (cpu_baseline / encoder_order / fence_sym / unsync_split /
  asym_producer / asym_consumer) using MTLResourceHazardTrackingModeUntracked + two independent
  MTLCommandBuffers on one queue, committed back-to-back with no CPU wait, as the sanctioned
  public-API mechanism for a genuinely unsynchronized producer/consumer pair (Metal's own docs:
  disabling hazard tracking requires the app to synchronize manually via MTLFence or risk
  incorrect results -- this is documented behavior we are validating empirically, not native
  command-stream RE).
- Authored kernels/h_chain.metal, kernels/h_icbrange.metal, kernels/xfb.metal (OWN-SHADER) and
  harness/gddraws.m (Bundle H binary). Compiles clean (`clang -fobjc-arc -framework Metal
  -framework Foundation`). Smoke-tested h_sync family (cpu_baseline/encoder_order/fence_sym,
  indexed and non-indexed) at n=16: all OBSERVED n_correct==n, n_stale=0 -- mechanism works.
- Added a `spinIters` per-thread busy-loop to the h_sync producer kernels (folded into an
  otherwise-unused output word so the compiler cannot dead-code-eliminate it) to calibrate how
  much producer GPU time is needed to expose a real cross-command-buffer race under
  `unsync_split`/`asym_*`, mirroring EXP-0093's own build-time calibration of its N sweep
  (PRE_REGISTRATION.md "Build-time findings" precedent -- calibration before freezing the matrix
  is within CODEX step 2/3, not a violation of "capture baseline before mutation").

## 2026-08-28T03:41Z -- INCIDENT: session interruption, host verified healthy, resuming
- A calibration probe (`--sync unsync_split --n 65536 --spin 100000` = 6.55e9 loop iterations
  total) was launched via an untimed shell call and the session was interrupted (coordinator:
  "killed by a host/terminal problem, not by anything you did"). On resume: `ps aux` showed no
  stray gddraws process (nothing left running/hung); `date`/`uptime` responded normally
  (load 1.8-3.0, not pegged); a fresh tiny GPU dispatch
  (`--family h_sync --sync encoder_order --n 16 --spin 0`, 15s hard timeout) completed
  immediately with the correct result. **No GPU wedge. No BLOCKED state warranted.** All
  experiment files (harness/gddraws.m, kernels/*.metal, work/bin/gddraws) were intact on disk,
  contrary to the relaunch message's "scaffolding only" assumption -- resuming in place rather
  than rebuilding.
- Read work/COMPILER-EXPLAINER-20260828.md (db.json falu2/falu2i source-register decoding bug,
  confirmed by an external compiler engineer's per-source-lifetime model). **This experiment
  uses no assembler, no tools/agx-isa, no db.json, and no native VDM/CDM grammar anywhere in its
  design (public Metal API surface only, per the addendum's own instruction) -- the bug is
  structurally inapplicable to Bundle H/I.** Recorded verbatim in RESULTS.md's response blocks
  per the coordinator's instruction to state this explicitly rather than leave it implicit.
- **Safety correction going forward:** every GPU-touching shell call from here on passes an
  explicit hard timeout to the Bash tool (not relying on the tool's 120s default, and no shell
  `timeout`/`gtimeout` binary is available on this host); the frozen matrix's `spinIters` value
  will be chosen from a calibration sweep that stays well inside a 60s per-case budget once
  official captures begin (`run.py` itself enforces this via `subprocess.run(timeout=...)`, the
  actual safety net for the two official runs).

## 2026-08-28T04:20Z -- harness built, calibrated, gates green; CORRECTION recorded
- Wrote kernels/xfb.metal, harness/xfbdraws.m (Bundle I); wrote harness/schema.py,
  casematrix.py (111-case frozen matrix), run.py, verify.py -- adopting EXP-0093's exact
  standing-gate architecture (shared schema, --selftest/--seqtest, non-recorded smoke gate,
  order-sensitive-key exclusion, recorded-reality fixtures).
- Fixed a real safety issue found during h_fields calibration: `[[instance_id]]` is
  ABSOLUTE (baseInstance-inclusive), not local -- the verification buffer was originally
  sized to `instanceCount` alone, an out-of-bounds device-buffer write risk at
  `baseInstance>0`. Fixed before any further dispatch; confirmed correct afterward
  (`baseInstance=5, instanceCount=3` -> observed `[[instance_id]] in {5,6,7}` exactly).
- Fixed an ICB setup bug (`inheritBuffers=YES` combined with per-command
  `-setVertexBuffer:` calls, and a missing `supportIndirectCommandBuffers=YES` on the
  render pipeline) that caused a real but fully contained
  `kIOGPUCommandBufferCallbackErrorPageFault`; corrected, reproduced clean afterward, host/
  GPU confirmed healthy both times.
- Calibrated h_sync (n=65536, spinIters=100000) and xfb_sync (numPrimitives=4096,
  spinIters=500000) workloads against real dispatches until the safe sync modes were
  reliably clean and the unsafe modes reliably (if nondeterministically) exposed either
  data staleness (h_sync) or a large completion-latency penalty (xfb_sync, a materially
  different failure signature -- see PRE_REGISTRATION.md).
- Ran two full-matrix PILOT DRY RUNS (not official captures) to validate run.py/verify.py
  end-to-end. **CORRECTION:** both were mistakenly written to `/tmp/exp0098_trial{,2}`,
  outside this repository -- a violation of `CLAUDE.md`'s "never leave this directory"
  rule. Caught before any official capture; both directories were deleted immediately
  (`rm -rf /tmp/exp0098_trial /tmp/exp0098_trial2`, confirmed gone) and
  `CAPTURE_CONTRACT.json` records the correction explicitly rather than silently omitting
  it. No file outside this experiment's own tree was read, only written-then-deleted
  scratch output; no data was retained anywhere outside this repository. Root cause: an
  absolute path typed without checking it resolved outside the experiment directory.
  Going forward, every scratch/dry-run path is confined under this experiment's own
  `work/` subtree.
- The first pilot dry-run surfaced three further build-time findings before matrix
  freeze (folded into `PRE_REGISTRATION.md` "Build-time findings" #8): a real,
  reproduced-twice hardware fault (`h_icbrange` `location>maxCommandCount` ->
  `kIOGPUCommandBufferCallbackErrorPageFault`, fault-contained), and two harness-logic
  bugs (an `instanceCount=0` verdict-formula error; a phase-insensitive sentinel-byte
  comparison bug in the no-partial-primitive boundary check) -- both fixed and
  re-verified. Second pilot dry-run: 0 unexpected FAIL (78 PASS / 33 N/A / 0 TIMEOUT).
- `harness/fixtures/recorded_reality.json` written from four genuine M4 captures.
  `verify.py --selftest`: 17/17 PASS. `verify.py --seqtest`: 7/7 PASS.
- `CAPTURE_CONTRACT.json` written with real SHA-256 hashes of every authored file, pinned
  revision `39af7f9314e5d6c49eea21465cd02682bf48d117`.
- **PRE_REGISTRATION.md and CAPTURE_CONTRACT.json are now frozen.** No further changes to
  the matrix, kernels, or harness logic before the two official capture runs.

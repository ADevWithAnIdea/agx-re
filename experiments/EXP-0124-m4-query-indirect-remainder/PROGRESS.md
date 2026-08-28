# PROGRESS — EXP-0124-m4-query-indirect-remainder

Append-only milestone log. Times approximate (session-local), target Apple M4/G16G,
macOS 26.6.2 (25G82), Metal 4.

## Milestone 1 — pre-registration and public-header groundwork

Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (DRV-QUERY-01/DRV-INDIRECT-01), `docs/P0-P1-CLOSURE.md`
rows P1.6/P1.7, and prior `RESULTS.md` for EXP-0027, EXP-0052, EXP-0053, EXP-0098.
Read the public Metal SDK headers (`MacOSX26.5.sdk/.../Metal.framework/Headers/*.h` —
struct/method declarations only, PUBLIC developer documentation per CODEX, not any Apple
binary) for `MTLCounters.h`, `MTLIndirectCommandBuffer.h`, `MTLIndirectCommandEncoder.h`,
`MTLComputeCommandEncoder.h`, `MTLDevice.h`. Wrote `PRE_REGISTRATION.md` with H-Q1..H-Q9,
H-I1..H-I7 before any harness code.

## Milestone 2 — MSL ICB-encoding syntax discovery (OWN-SHADER, compiler-guided)

Public MSL exposes `render_command`/`compute_command`/`command_buffer` types
(`#include <metal_command_buffer>`) for GPU-authored indirect-command-buffer encoding.
Exact syntax was NOT assumed from memory of documentation; it was discovered by writing
small trial `.metal` files and compiling them via our own `newLibraryWithSource:`-based
`work/trycompile.m` tool, reading the *compiler's own diagnostic error text* to correct
syntax (ordinary iterative software development against a public compiler, not Apple
binary introspection). Key discoveries, each confirmed by an actual successful compile:
- A `command_buffer` cannot be a plain `[[buffer(N)]]` kernel argument; it must be a field
  of a struct passed as an argument-buffer (`struct ICBContainer { command_buffer icb; };`),
  bound via `-[MTLArgumentEncoder setIndirectCommandBuffer:atIndex:]`.
- `render_command`/`compute_command` support `.set_vertex_buffer()`/`.set_kernel_buffer()`,
  `.draw_primitives()`/`.draw_indexed_primitives()`, `.reset()`,
  `.concurrent_dispatch_threadgroups()`, `.set_barrier()`/`.clear_barrier()`.
- `compute_pipeline_state`/`render_pipeline_state` can ALSO be struct fields in the same
  argument buffer, bound via `-[MTLArgumentEncoder setComputePipelineState:atIndex:]`, and
  set in-kernel via `.set_compute_pipeline_state()`.
`work/try_icb.m` end-to-end validated the full round trip (compute kernel encodes one
render command into a fresh ICB; a render pass executes it): pixel(4,4) read back
`255 0 0 255`, exactly the authored red -- confirms the mechanism works on real M4
hardware, not just that it compiles.

## Milestone 3 — qbench.m Group Q build-time bugs found and fixed

1. **`sampleCountersInBuffer:atSampleIndex:withBarrier:` (the per-draw/per-dispatch/
   per-blit-command encoder-level counter-sampling call) hard-aborts the process on M4**:
   `-[AGXG16GFamilyBlitContext sampleCountersInBuffer:atSampleIndex:withBarrier:]:812:
   failed assertion \`... not supported on this device'` (also reproduced from a compute
   encoder). Traced directly to `q_caps`'s own finding: `supportsCounterSampling:` is TRUE
   only for `MTLCounterSamplingPointAtStageBoundary`; Draw/Dispatch/TileDispatch/Blit
   boundaries are all FALSE on this device. Fixed by rewriting every counter-sampling call
   site to use the pass-descriptor `sampleBufferAttachments[i].startOfEncoderSampleIndex/
   endOfEncoderSampleIndex` mechanism instead (the only one M4 supports). This negative
   finding is itself promoted to RESULTS.md, not just a bug fixed silently.
2. **A totally empty sampled encoder (attachments set, zero real commands) reads back all
   samples as untouched-zero**, not a real timestamp and not `MTLCounterErrorValue`. Fixed
   every blit-only sampled encoder to issue one trivial real `fillBuffer:` first
   (`touchBlit()` helper). Promoted as a documented stage-placement nuance.
3. **`q_avail`'s original 400,000,000-iteration spin kernel occasionally triggered a
   `CMDBUF_ERROR`** (plausibly a GPU command-timeout watchdog) in the `post_commit_unwaited`
   case, contaminating the availability-sentinel measurement. Reduced to 3,000,000
   iterations (still measurably non-instant; the buffer's status was still observed as
   `Committed`, not `Completed`, at resolve time) -- comfortably clear of the watchdog with
   zero observed CMDBUF_ERROR since.
4. **`q_alloc_mode` (Private storage mode) SIGSEGVs uncatchably inside
   `-[MTLCounterSampleBuffer resolveCounterRange:]` itself** (confirmed by bisecting with
   temporary `NSLog` checkpoints around every call in the function -- the crash happens
   strictly between "about to resolve" and "resolved", i.e. inside the Metal runtime call,
   not our code). This matches the header's documented precondition ("may only be used
   with sample buffers that have MTLStorageModeShared") but as an unrecoverable crash
   rather than a graceful rejection -- promoted as a first-class negative/hazard finding,
   `expect_crash: true` in the frozen matrix.
5. **`q_copy_match`'s GPU-side `resolveCounters:` read back all zeros** when issued in a
   LATER blit encoder of the SAME command buffer as the sampling encoders, while the
   CPU-side `resolveCounterRange:` (called after full command-buffer completion) saw the
   correct nonzero values. Isolated by comparing raw bytes with a temporary debug print.
   Splitting the GPU-side resolve into a fully separate, later command buffer fixed it
   (bytes then matched exactly). The same-command-buffer version was kept as its OWN
   deliberate case (`q_copy_samecb_hazard`) to make the ordering hazard itself a
   first-class, reproducible finding rather than a fixed-and-forgotten bug.
6. **`MTLBlitPassSampleBufferAttachmentDescriptorArray`/compute equivalent caps out at 4
   attachment slots**: `n=4` succeeds, `n=5` hits a hard CPU-side assertion abort
   (`attachmentIndex(4) must be < 4`) -- discovered while testing `q_simul_many_in_encoder`
   at `n=8`; the matrix was rebuilt to sweep `n=1..4` (all succeed) plus `n=5`
   (`expect_abort: true`) to pin the exact cliff instead of just confirming a crash at an
   arbitrarily-chosen larger value.

## Milestone 4 — ibench.m Group I build-time bugs found and fixed

1. **`icbw_vertex`'s fullscreen-triangle vertex shader indexed a 3-element local array
   directly by `[[vertex_id]]`**, which is documented (and reconfirmed here) to be
   ABSOLUTE (`vertexStart`-inclusive, matching EXP-0098's `[[instance_id]]` finding) --
   so `vertexStart=10` produced an out-of-bounds local-array read (undefined shader
   behavior, observed as "nothing painted" even though the draw should have succeeded).
   Fixed with `p[vid % 3]`; re-tested and `vertexStart=10` now paints correctly.
2. **`i_icbb_trial` (concurrent-dispatch producer/consumer ICB) crashed unconditionally**
   in its first version, which mixed a GPU-authored command (buffers + dispatch params via
   `compute_command` in-kernel) with a CPU-authored pipeline-state field
   (`-[MTLIndirectComputeCommand setComputePipelineState:]` called from Objective-C after
   GPU encoding). Root-caused to the producer/consumer `MTLComputePipelineState`s not
   having `supportIndirectCommandBuffers = YES` set (the same opt-in EXP-0053 found
   necessary for render pipelines used via `executeCommandsInBuffer:`, here missed for
   compute pipelines) -- fixed by building both via `MTLComputePipelineDescriptor` with
   the flag set, AND by moving pipeline-state authorship fully into the GPU-encoding
   kernel itself (`compute_pipeline_state` argument-buffer fields +
   `.set_compute_pipeline_state()`) rather than mixing CPU/GPU authorship of one command.
   Re-tested clean across repeated trials; unbarriered trials now show a real,
   reproducible race (`result=3176889822 = (0xDEADBEEF*2) mod 2^32`, i.e. the consumer
   read the pre-write sentinel) in some but not all trials, exactly as H-I5 predicted.

## Milestone 5 — full fixed-matrix dry run (work/dryrun_test, deleted after inspection)

`python3 harness/run.py --run dryrun_test --out work/dryrun_test --skip-icbmax`: all
85 cases completed, 0 unexpected crashes/timeouts (verdict counts 73 PASS / 4 FAIL
[genuine refutations: `q_copy_samecb_hazard`, `q_occ_overwrite_same_offset`,
`q_occ_overwrite_disabled_between` -- see RESULTS.md; these are correct, informative
negative results, not harness defects] / 8 N/A [unbarriered race trials, observational
by design]). `verify.py --selftest` and `--seqtest` both green. Deleted per the standing
"dry runs live in work/, never raw/, and are removed before the official capture" rule.

## Milestone 6 — icbmax bisection dry run (work/icbmax_dryrun.jsonl, deleted after inspection)

`icbmax_bisect.run_bisection()` converged in 24 probes (bracket re-confirmed at both
ends, then true binary search) to an EXACT boundary: **`maxCommandCount=6,391,319`
allocates successfully; `6,391,320` SIGSEGVs**, zero monotonic violations. This
dramatically narrows EXP-0098's coarse `[4,194,304 works, 8,388,608 crashes]` bracket to
a single exact integer. Arithmetic check (not independently HW-measured, flagged
`INFERRED` in RESULTS.md): `128 + 6,391,320 * 336 = 2,147,483,648 = 2^31` exactly --
consistent with a 128-byte fixed ICB header plus 336 bytes per Draw-type command, capped
by a signed-32-bit (2 GiB) total-size overflow. Deleted per the dry-run rule; the official
runs each redo this bisection independently and are compared in `verify.py --captured`.

## Milestone 7 — freeze

`CAPTURE_CONTRACT.json` written with authored-file SHA-256 hashes, pinned git revision
(recorded at freeze time, NOT re-gated against live `HEAD` on later runs per the standing
rule), matrix summary, timeouts, and gate descriptions. `fixtures/recorded_reality.json`
populated from 5 real (non-hand-typed) captures via `run.run_case()` itself. No further
harness/kernel edits after this point except as explicitly logged below.

## Milestone 8 — official capture runs

See RESULTS.md and CAPTURE_CONTRACT.json `run_ids` for the two official run identifiers,
their `verify.py --captured` cross-run gate result, and the icbmax bisection outcome from
each.

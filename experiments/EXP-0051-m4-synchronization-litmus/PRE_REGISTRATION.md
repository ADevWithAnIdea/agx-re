# EXP-0051 pre-registration: M4 synchronization litmus

Date: 2026-08-17

Target: local Apple M4 / G16G only. No A18 Pro claim may be derived from this
experiment.

This file is frozen before the first EXP-0051 compilation or hardware run. It
records competing hypotheses, falsifiers, controls, and the strict evidence
boundary. Later results must not edit it. Every run must verify and retain its
SHA-256 before building.

## Clean-room evidence boundary

Allowed inputs and observations:

- complete Metal Shading Language authored under this experiment;
- the authored Objective-C runner and exact build/run commands;
- compile acceptance or complete compile errors for those authored sources;
- bytes in buffers allocated by the authored process and live GPU completion,
  error, timeout, and counter/readback results; and
- exact machine-code bytes compiled only from the complete authored MSL, if a
  later analysis needs them. This experiment does not initially require them.

Forbidden absolutely:

- inspecting, scanning, disassembling, symbol-dumping, tracing, or otherwise
  introspecting an Apple binary, framework implementation, kernel collection,
  firmware, system shader, compiler executable, helper, or auxiliary program;
- generic BO capture/scanning, pointer following, or command-buffer content
  inspection; and
- inferring native instruction semantics solely from Metal/API behavior.

The public Metal API and runtime are treated as a black box. No interposer or BO
tracer is used. All saved memory bytes originate in buffers owned by this
process.

## Bounded matrix

### A. Threadgroup execution and memory flags

Each case launches 1,024 workgroups of 64 threads. Every lane writes a unique
asymmetric value, synchronizes, and reads a different lane. Counters record
checked values and mismatches.

1. threadgroup memory + `threadgroup_barrier(mem_threadgroup)`;
2. threadgroup memory + `threadgroup_barrier(mem_none)`;
3. within-simdgroup peer + `simdgroup_barrier(mem_threadgroup)`;
4. device memory + `threadgroup_barrier(mem_device)`;
5. device memory + `threadgroup_barrier(mem_threadgroup)` as a deliberately
   wrong memory-class negative control; and
6. device memory + `threadgroup_barrier(mem_device|mem_threadgroup)`.

### B. Atomic publication litmus

Producer and consumer use asymmetric four-word payloads plus separate atomic
ready/ack counters. Every wait is bounded and reports timeout rather than
hanging. Cases are:

1. producer/consumer in different simdgroups of one threadgroup, relaxed atomics;
2. same topology with device, seq-cst, device-scope fences around relaxed flag
   publication/consumption;
3. same topology with threadgroup-scope device fences;
4. producer and consumer in two distinct threadgroups, relaxed atomics; and
5. distinct threadgroups with device-scope device fences.

Separate authored compile probes test whether this MSL/runtime exposes
acquire-load/release-store, acquire-release RMW, relaxed RMW, seq-cst device
fence, and release device fence. Compile rejection is a first-class result. If
an acquire/release source compiles, the runner must also create and execute its
pipeline, but its two-thread output is only an exposure smoke test, not a memory
model proof.

### C. Dispatch, encoder, command-buffer, queue, and host boundaries

An authored producer fills 4,096 words with an epoch/index-dependent pattern;
an authored consumer copies them to a second buffer. Each case repeats 128
epochs, resets both buffers to different asymmetric sentinels, and validates
every word on the CPU after the relevant completion boundary:

1. adjacent dispatches in one compute encoder without an explicit barrier;
2. same encoder with `memoryBarrierWithScope:MTLBarrierScopeBuffers`;
3. adjacent compute encoders in one command buffer;
4. two command buffers committed in order to one queue, no intermediate wait;
5. two command buffers on one queue with a CPU wait between them;
6. two queues, consumer deliberately committed first, no synchronization;
7. two queues with producer completion waited on CPU before consumer commit;
8. two queues ordered by a `MTLSharedEvent` signal/wait;
9. CPU write to shared storage followed by GPU consumer and completion wait; and
10. GPU producer followed by completion wait and CPU read.

## Competing hypotheses and falsifiers

H1 — Correctly flagged threadgroup barriers provide execution rendezvous and
visibility for their named memory class at the tested 64-thread width.

- Support: zero mismatches and exactly 65,536 checks in both runs for cases 1,
  3, 4, and 6 in section A.
- Falsifier: any mismatch, missing check, command error, or run disagreement in
  a correctly scoped case.
- Competing explanation retained: a wrong/no-memory flag may also pass because
  the tested implementation is coherent or scheduling hides the race. Passing
  a deliberately racy case never proves a guarantee.

H2 — Metal-exposed acquire/release atomics either compile as explicit source
operations or are cleanly rejected; their absence must not be silently replaced
by a native encoding claim.

- Support for exposure: source compiles, pipeline executes, and output is saved.
- Support for non-exposure: reproducible complete compiler rejection for the
  isolated authored source.
- Falsifier: run-to-run acceptance changes or a pipeline/runtime failure after
  compile acceptance.

H3 — In the publication litmus, device-scope seq-cst fences plus relaxed flags
prevent payload mismatch at both same-threadgroup and cross-threadgroup topology.

- Support: all planned messages complete with zero timeouts/mismatches twice.
- Falsifier: any timeout or mismatched payload.
- Competing explanation retained: relaxed/no-fence cases may also pass on M4;
  that would establish only observed behavior, not acquire/release semantics or
  a portable guarantee. A failure in cross-threadgroup cases can also reflect
  lack of global scheduling/progress guarantees rather than visibility alone.

H4 — An explicit Metal buffer barrier in one compute encoder, an encoder
boundary, same-queue command order, a CPU completion wait, and a shared-event
wait each produce complete producer-to-consumer visibility in the tested shared
buffers.

- Support: 128/128 epochs and all 524,288 copied words match twice per ordered
  case.
- Falsifier: any stale word, command error, timeout, or disagreement.
- Competing explanation retained: a no-barrier same-encoder case may happen to
  pass but cannot promote an API guarantee; a consumer-first unsynchronized
  two-queue case is expected to expose stale sentinels but its exact scheduling
  is deliberately not assumed.

H5 — Shared-storage CPU visibility is complete at the documented completion
boundaries used here: CPU write before commit is visible to the GPU, and GPU
write is visible to the CPU after `waitUntilCompleted`.

- Support: all 128 epochs and 524,288 words match in each direction twice.
- Falsifier: any mismatch after successful completion.

## Interpretation boundary

Positive results in sections B/C are Metal/runtime ordering observations. They
may include compiler-inserted fences, command processor barriers, cache policy,
queue scheduling, or CPU/runtime work. They are not isolated native instruction
semantics, not a Vulkan/GL memory-model mapping, and not proof of Linux UAPI
barrier fields. The deliberately unsynchronized cases are diagnostic negative
controls only.

## Safety and repetition

All shader compilation, pipeline creation, and suite execution has a hard host
timeout. GPU loops have bounded spins. Any compile rejection, timeout, command
error, partial stdout, or mismatching output is retained. Run directories are
append-only. Two independent full-suite repetitions are required, with exact
runner/kernel hashes and a complete artifact manifest.

# EXP-0052 pre-registration — M4 timestamp and query semantics

Date: 2026-08-17

Target: local Apple M4 / G16G only. A18 Pro remains the primary project target,
but is not available for this run.

## Question

Which M4 behaviors exposed through the public Metal timestamp-counter API can
bound P1.6 without inferring Linux UAPI values or inspecting implementation code?
Specifically: clock scale/calibration, monotonicity, render-stage ordering,
multi-pass sample-index behavior, and when resolved samples become usable.

## Pre-registered hypotheses and falsifiers

H1 — `[MTLDevice sampleTimestamps:gpuTimestamp:]` exposes CPU and GPU values on
the same nanosecond-scale monotonic clock on this M4.

- Support: at least 64 paired samples remain monotonic; CPU/GPU deltas track with
  near-unit slope over multiple sleep intervals; offset stays bounded.
- Falsifier: either side regresses, slopes materially diverge, or offset drifts
  with elapsed time.

H2 — one render pass with four stage-boundary sample indices produces nonzero
`startVertex <= endVertex <= startFragment <= endFragment` values after command
completion. A deliberately heavier fragment path should increase its measured
fragment interval relative to an otherwise matched light path.

- Falsifier: zeros after successful completion, inverted stage order, or no
  reproducible duration separation between light and heavy paths.

H3 — two render passes submitted in order on the same queue and assigned disjoint
sample-index ranges retain both ranges without overwrite; the second range begins
no earlier than the first range ends.

- Falsifier: either completed range is missing/overwritten or cross-pass ordering
  reverses.

H4 — resolved data is only promoted as available after successful command-buffer
completion. Any pre-commit or in-flight resolved bytes are recorded but treated as
undefined API/runtime behavior, not a hardware guarantee.

H5 — the public resolved payload is an array of consecutive 64-bit values, one per
requested sample index. This experiment does not infer the private backing BO or
the Linux counter-heap ABI from that public representation.

## Authored probe and repetition plan

The harness will use only public Metal/Foundation APIs and MSL embedded in the
committed Objective-C source. It will run:

1. a 64-pair CPU/GPU timestamp calibration sweep using several bounded delays;
2. repeated light and heavy 64x64 render passes with four stage samples each;
3. two ordered render passes using disjoint ranges in one counter sample buffer;
4. a pre-commit, in-flight, and post-completion resolve observation; and
5. two fresh process repetitions with exact output capture and hard timeouts.

All result values, compile/run commands, source/tool hashes, target identity,
failures, and analyzer outputs will be retained append-only. Claims will be
Metal API source-path behavior only. They will not establish wrap duration,
Linux `GET_TIME`, UAPI heap packing, cache maintenance, firmware address handoff,
pipeline statistics, or A18 behavior.

## Clean-room boundary

```text
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs permitted: this authored pre-registration; authored Objective-C/MSL;
  public Metal timestamp/counter API results
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE (out of scope for this experiment)
IOKit/BO payload tracing: NONE
Pointer following: NONE
Failure handling: hard subprocess timeouts; preserve all output and errors
```

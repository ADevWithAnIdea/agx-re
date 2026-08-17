# EXP-0052 results — M4 public timestamp behavior

## Verdict

**PARTIAL; P1.6 remains open.** Two fresh M4 processes completed the
pre-registered public-API matrix. Across 128 calibration intervals, all 256
CPU/GPU paired API calls were exactly equal and strictly monotonic in these
captures. All 28 completed render-pass
sample groups were nonzero and ordered within each pass. Every one of ten warm
matched comparisons separated the deliberately heavy fragment path from the
light path.

The strict cross-pass portion of H3 was falsified: in both processes, the second
pass's start-of-vertex timestamp preceded the first pass's end-of-fragment
timestamp, by 500 ns and 1,000 ns respectively. Public stage boundaries therefore
must not be documented as globally serial pass boundaries from this evidence.

These are M4 Metal source-path observations only. A18 Pro remains untested, and
no Linux frequency/conversion, firmware object, heap packing, cache operation,
or UAPI value is inferred.

## Direct observations

Canonical runs 03 and 04 were captured on Apple M4 / Mac16,10, macOS 26.6.2
build 25G82. Both exited zero, ended in `RESULT OK`, produced the same first
pixel `5340bfff`, and reported completed command buffers without Metal errors.

### Clock pairs

Each process retained 64 calibration intervals and two calls to
`sampleTimestamps:gpuTimestamp:` per interval. For all 256 paired calls across
both processes:

- CPU timestamp equaled GPU timestamp exactly;
- CPU and GPU sequences were strictly monotonic; and
- the CPU delta equaled the GPU delta exactly across requested delays of 0,
  100 us, 1 ms, and 5 ms.

This supports one shared nanosecond-valued public clock on this M4 path. It does
not prove the Linux-reported clock frequency, conversion formula, wrap duration,
or how Metal implements the public API.

### Stage samples and workload separation

Each pass requested start/end vertex and start/end fragment samples. Across 28
completed pass ranges, every sample was nonzero and every range satisfied:

```text
startVertex <= endVertex <= startFragment <= endFragment
```

For the ten matched warm repetitions, light fragment intervals were 5,083–6,791
ns and heavy intervals were 107,541–297,166 ns; heavy exceeded light every time.
The first run's initial light pass was a cold outlier and exceeded its initial
heavy pass, so the result is deliberately limited to the pre-registered repeated
matched comparisons rather than a universal timing claim.

### Multi-pass ordering falsifier

Both disjoint four-index ranges survived in a shared counter sample buffer. But
for two passes encoded into one command buffer, the boundary deltas
`second.startVertex - first.endFragment` were `-500 ns` and `-1000 ns`.
Within-pass ordering is supported; strict non-overlap between adjacent pass-stage
ranges is not.

### Resolve timing and payload shape

The tested pre-commit and immediate post-commit/pre-wait resolves returned four
zero values in both runs. The raw harness called the latter `in-flight`, but it
did not sample command-buffer status at that instant; the command may already
have completed. Post-completion resolves returned the requested consecutive
64-bit values, with exact requested counts of four or eight. These early values
are recorded observations but remain undefined runtime/API behavior, not a
hardware availability guarantee. The public `NSData` shape does not establish
the private counter-buffer layout.

## Preserved failures and correction

Runs 01 and 02 exited with SIGBUS because the authored harness read a 64x64 RGBA8
texture into a four-byte local array. Run 01's buffered stdout was empty. Run 02
used unbuffered stdout and retained every calibration and stage sample through
`post-pair-4`, proving the failure happened after the GPU probe. The correction
narrowed the readback to one pixel; no raw run was removed or overwritten.

The verifier reconstructs the exact run-01 and run-02 harness byte strings and
matches their SHA-256 values to each run's environment record. Canonical runs 03
and 04 bind directly to the retained final harness and runner hashes.

## Remaining work

- Repeat the same matrix on A18 Pro/G17P.
- Map the public clock against Linux `GET_TIME` and the queried
  `command_timestamp_frequency_hz` on the same device.
- Establish wrap, reset, accumulation, availability-bit, copy, simultaneous-query,
  and reuse behavior.
- Locate and validate the Linux-visible timestamp objects/heap without assuming
  that the public Metal resolve payload is their layout.
- Expand render/compute/blit boundaries, cross-command/cross-queue cases, faults,
  cancellation, and long-running rollover tests.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
IOKit/BO payload tracing: NONE
Target: M4/G16G-class only; A18 Pro untested
```

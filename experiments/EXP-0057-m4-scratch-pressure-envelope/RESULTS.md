# EXP-0057 results: bounded M4 ordinary-Metal scratch success

> **QUARANTINED / NON-EVIDENCE — 2026-08-20.** Nothing in this file, the
> associated raw runs, analysis JSON, or manifest may support an M4, A18, Apple9,
> Linux UAPI, or helper/scratch claim. Audit found that the metadata collector
> read a temporary pipeline archive and generically enumerated GPU-image/Mach-O
> containers, exceeding the pre-registered metadata-only boundary. It also found
> that raw records did not retain full output/guard data or complete
> environment/revision provenance. This historical text is retained to disclose
> the failed process, not as an observation. P0.1 remains OPEN on the basis of
> valid prior evidence only (not EXP-0057).

## Verdict

**PARTIAL / lower bound only. P0.1 remains OPEN.** Two fresh M4 runs completed
all 14 pre-registered public-Metal trials (seven source levels x `tg32` and
`tg256`) with exact full output and exact prefix/suffix guards. The largest
retained authored pipeline declared 16,400 bytes of per-thread scratch and
completed with 32,768 threads for both shapes.

This establishes only that this M4/macOS/compiler/workload combination serviced
those ordinary private-scratch declarations. It does not reveal, generate, or
validate a userspace helper, helper data ABI, scratch BO, block list, tag, cfg,
special register, doorbell, Linux limit, A18 value, or hardware allocation
geometry. It therefore cannot be used to populate `drm_asahi_helper_program`.

## Direct observations

Both fresh runs had exactly the same semantic records; see
`analysis/m4_20260819_repeat.json`. `MTLCommandBufferStatusCompleted` is 4.
Every successful entry had `exact=true`, `prefix_guard=true`, and
`suffix_guard=true` over the full 32,768-word authored output.

| source request (B) | own metadata scratch (B) | own metadata GPR field 0 | `tg32` | `tg256` |
| ---: | ---: | ---: | --- | --- |
| 0 | absent | 2 | completed/exact | completed/exact |
| 576 | 592 | 51 | completed/exact | completed/exact |
| 1024 | 1040 | 41 | completed/exact | completed/exact |
| 2048 | 2064 | 41 | completed/exact | completed/exact |
| 4096 | 4112 | 41 | completed/exact | completed/exact |
| 8192 | 8208 | 41 | completed/exact | completed/exact |
| 16384 | 16400 | 41 | completed/exact | completed/exact |

Each shape dispatched exactly 32,768 threads: `tg32` used 1,024 threadgroups
of 32 and `tg256` used 128 threadgroups of 256. No command error, compilation
rejection, timeout, device loss/reset, GPU fault, or `STOP.json` occurred in
either retained run. The fixed 16 KiB/thread ceiling is a safety cap, not a
measured maximum; the successful 16,400-byte declared value is a lower bound.

## Interpretation and limits

The requested source array size and declared metadata scratch differ by 16
bytes for the six nonzero cases. This is an observation of this compiler's own
metadata for the exact retained sources, not an Apple9 scratch-header or
allocation rule. The GPR-field change between 592 and 1040 bytes shows that
the compiler's register allocation changes across this source family; it does
not prove a helper transition.

Equal success for the two threadgroup shapes falsifies a shape-specific public
failure boundary within this small, capped matrix. It does not measure active
subgroups/core, backing allocation concurrency, growth, exhaustion, reset,
or the Linux userspace allocator's failure semantics. EXP-0041's negative
boundary observation remains in force: ordinary Metal scratch can be serviced
without exposing a helper/scratch record through that restricted trace.

## Remaining P0.1 requirements

All of the load-bearing requirements remain unknown: helper binary/cfg/data;
helper SR and NEXT/ACK/NACK ABI; pointer tags; scratch headers, block lists,
alignment, buckets and topology mapping; limits and failure semantics under the
unchanged UAPI; preamble support; generated helper execution; and replication
on A18 Pro. The safe fallback remains rejecting paths that require the missing
userspace scratch/helper ABI rather than guessing values.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE
Apple command/state/code/unknown BO bytes inspected: NONE
Compiled non-authored code inspected: NONE
```

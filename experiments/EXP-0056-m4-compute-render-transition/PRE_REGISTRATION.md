# EXP-0056 pre-registration — M4 compute-to-render transition framing

Frozen before any source build or live GPU process. Target is local Apple M4 /
G16G only; this makes no A18 Pro or M5 claim. Gap: P0.5.

## Question

Does a public-Metal compute encoder that writes an authored `Scene` buffer and
is immediately consumed by an authored render encoder cause a stable,
observable framing difference inside only the preclassified EXP-0043 CDM/VDM
command mappings, relative to matched compute-only and CPU-initialized-render
controls?

This is a bounded state-transition/barrier framing test, not a command replay,
link mutation, packet decode, or complete packing specification.

## Clean boundary and allowlist

Only exact allocation starts `0x100000b8000`, `0x10000158000`, `0x18000`, and
`0x88000` may ever have bytes retained or inspected, with a 0x10000 cap each.
Their CDM-segment-0, CDM-segment-1, VDM-segment-0, and VDM-segment-1 roles are
preclassified from EXP-0043, using the provenance bridge in EXP-0049.
Metadata is checked before any payload read. Unknown BO data, compiled shader
bytes, Apple binaries, helper programs, pointers encoded in payloads, and
command mutation/replay are forbidden.

The fixed interposer is compile-time incapable of retaining a mapping CPU
address unless the allocation start equals one of those four VAs. It logs only
metadata for all other mappings. The runner rejects unexpected retained files,
symlinks, malformed metadata, oversized reads, duplicate VAs, snapshot errors,
and unknown trace-line grammar before opening a payload.

## Frozen matrix and controls

Two append-only top-level runs each build once and launch six fresh processes:
three variants times two schedules (`plain`, or a retained authored 64 KiB
client padding buffer initialized before pipeline/resources):

| variant | authored sequence | readback falsifier |
| --- | --- | --- |
| `compute-only` | compute writes `Scene` | scene values differ |
| `cpu-render` | CPU initializes identical `Scene`, render reads it | center BGRA differs from `bf8040ff` |
| `compute-render` | compute writes `Scene`, render immediately reads it in one command buffer | center BGRA differs from `bf8040ff` |

All compute and render source is authored in `harness/probe.m`. The two render
paths share pipeline, render pass, scene values, texture, and expected image;
only the producer is changed. The dependency case must see compute-produced
positions and color, so a stale/incorrect transition falsifies it.

## Hypotheses and stop rules

H1: every dependency trial completes and has the exact public readback. A
command error, timeout, wrong scene/image, or failed guard/status falsifies H1.

H2: if a CDM/VDM fixed-allowlist payload is present, its same-VA difference
between the dependency and its matching isolated control repeats identically
across the two top-level runs and schedules. Such a difference is only a
`STRUCTURAL` transition candidate, never proof of barrier semantics or hardware
consumption. No difference is a valid bounded negative.

H3: padding must not change matching transition candidate offsets/bytes. A
schedule-only difference is retained as opaque allocation correlation; it is
not decoded, treated as an address, or followed.

If a required CDM0/VDM0 payload is missing for its relevant variant, or any
metadata boundary check fails, retain the failure and stop interpretation. Do
not locate an alternative mapping.

Builds have 60-second timeouts; processes and analysis each have 45/15-second
timeouts. Raw output is append-only under `raw/`. The pre-registration commit
must include this file and all authored runner/harness sources before the first
build or live run.

Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER source. Apple binary
introspection: NONE. Apple auxiliary/program-byte inspection: NONE.

# EXP-0048 pre-registration: M4 BG/EOT/PBE state and behavior

Date: 2026-08-17

Target: the local Apple M4 (`G16G`) only.

This file is frozen before the first live-hardware run. It records the bounded
questions, predicted observations, falsifiers, and analysis allowlist. Later
results must not edit this file. Its SHA-256 is captured before every run.

## Clean-room boundary

This experiment uses only:

- Metal Shading Language source authored in this experiment;
- bytes returned from our own buffer-backed render targets and counter buffers;
- live allocation/map and command/state bytes crossing our own process boundary;
- four command/state buffer virtual addresses previously correlated by live M4
  experiments in this repository; and
- public, independently developed Mesa hypotheses, always labelled as such.

It must never inspect, scan, disassemble, dereference, or follow a pointer into
an Apple binary, framework, kernel collection, firmware image, generated helper
program, or other Apple auxiliary code. It must not dump an unknown BO. It must
not scan every mapped BO. Shader compiler output is out of scope even though the
shader source is ours: no shader-code BO is dumped or analyzed here.

The only command/state BO allowlist is:

| GPU VA | Previously correlated role on local M4 | Maximum dumped bytes |
| --- | --- | ---: |
| `0x18000` | VDM command/state | `0x10000` |
| `0x58000` | fixed-function render state | `0x10000` |
| `0x68000` | tiling state | `0x10000` |
| `0x10000018200` | relocated MRT attachment descriptor array | `0x1000` |

The tracer compares an allocation's exact starting GPU VA to that allowlist.
It does not infer a target from contents, scan non-allowlisted mappings, or
follow any value found in a dump. Analysis rejects filenames/VAs outside the
same allowlist and reads only fixed offsets or reports bytewise diffs inside
one allowlisted dump.

## Authored workload matrix

All cases render into two buffer-backed 32 x 32 attachments so that the
previously correlated MRT descriptor array is present. Attachment 1 is a
constant RGBA8Unorm control unless the case explicitly says `mixed-r32f`.

The planned minimal matrix is:

1. `rgba8-clear-store-draw`: RGBA8Unorm, Clear/Store, draw, no blend/atomic.
2. `rgba8-clear-store-empty`: RGBA8Unorm, Clear/Store, no draw.
3. `rgba8-load-store-empty`: RGBA8Unorm, Load/Store, no draw.
4. `rgba8-dontcare-store-draw`: RGBA8Unorm, DontCare/Store, draw.
5. `rgba8-clear-dontcare-draw`: RGBA8Unorm, Clear/DontCare, draw.
6. `bgra8-clear-store-draw`: BGRA8Unorm, Clear/Store, draw.
7. `rgba8srgb-clear-store-draw`: RGBA8Unorm_sRGB, Clear/Store, draw.
8. `r32f-clear-store-draw`: R32Float, Clear/Store, typed float output.
9. `r32u-clear-store-draw`: R32Uint, Clear/Store, typed uint output.
10. `rgba8-load-store-blend`: RGBA8Unorm, Load/Store, alpha blend, draw.
11. `rgba8-clear-store-atomic`: RGBA8Unorm, Clear/Store, draw plus an authored
    fragment atomic increment into a separate counter buffer.
12. `mixed-r32f-clear-store`: RGBA8Unorm plus R32Float, Clear/Store, draw.

Every case is run in each of two independent run directories. Each process has
a hard timeout. Failures are retained rather than deleted or overwritten.

## Pre-registered observations and falsifiers

H1 (live-M4 structural hypothesis): changing only the render-target pixel
format changes the fixed format/component/swizzle fields in the load/render and
store/PBE records at pre-established fixed offsets in `0x10000018200`, while
the dimension fields remain constant for equal 32 x 32 targets.

- Support: reproducible format-specific byte/word deltas at the same fixed
  descriptor offsets in both runs, with stable dimensions.
- Falsifier: identical descriptor words for distinct formats, dimensions that
  do not decode to 32 x 32 under the existing hypothesis, or run-to-run layout
  movement that invalidates the fixed-offset comparison.

H2 (live-M4 behavioral hypothesis): an empty Clear/Store pass writes the clear
color to every pixel, while an empty Load/Store pass preserves the initialized
surface bytes. This establishes observable background/load and end/store
behavior without relying on program-code inspection.

- Support: exact per-pixel results for lossless RGBA8 cases in both runs.
- Falsifier: any pixel differs from the expected clear/preserved value after a
  successful command buffer, excluding an explicitly undefined DontCare result.

H3 (live-M4 structural hypothesis): load/store action changes alter bounded
attachment/command state, including a poisoned or disabled store surface for
StoreActionDontCare, without changing format/dimension identity fields.

- Support: stable, action-specific deltas at fixed offsets in the allowlist in
  both runs and correct defined readbacks for Clear/Store and Load/Store.
- Falsifier: no action-correlated delta anywhere in the allowlisted state,
  format/dimension identity mutates for action-only cases, or deltas do not
  reproduce.

H4 (live-M4 structural hypothesis): alpha blending changes the previously
correlated fixed-function render-state flags at fixed offsets in `0x58000` and
produces the mathematically expected RGBA8 result, while the attachment's PBE
format/dimension identity remains that of the non-blended RGBA8 case.

- Support: correct blended readback plus reproducible fixed-state delta.
- Falsifier: wrong blend result after successful completion, no fixed-state
  delta, or unexplained PBE format/dimension mutation.

H5 (live-M4 boundary hypothesis): an authored fragment atomic side effect is
visible in the counter result but does not require a different PBE
format/dimension record for an otherwise identical RGBA8 target.

- Support: nonzero deterministic counter, unchanged fixed PBE identity, and
  any other state deltas reproducible and confined to the allowlist.
- Falsifier: zero/unstable counter after successful full-screen draws, changed
  PBE identity, or nonreproducible state deltas.

H6 (live-M4 format-behavior hypothesis): typed stores obey the requested
format at the process boundary: BGRA channel order, sRGB encoding, R32Float bit
pattern, and R32Uint value are observable in raw target bytes.

- Support: both runs match precomputed expected bytes (with an explicit small
  rounding tolerance for sRGB conversion only).
- Falsifier: stable but incompatible bytes, or run-to-run variation for a
  defined Store result.

## Public hypotheses, not Apple facts

Public Mesa code at repository-pinned revision `3c4d3e46` motivates looking for
a tagged background/end-of-tile program address plus a packed resource
specification and for programmable load/clear/resolve/store paths. No bit field
from that public implementation is accepted as a live-M4 fact unless this
experiment independently observes it. This bounded matrix is not expected to
close the BG/EOT ABI, partial-render ABI, multisample resolve, depth/stencil,
layer/mip, memoryless, compression, or the ownership/meaning of program ID
`0x6f`; negative evidence is reported only for the exercised cases.

## Stop conditions

Stop a case on a Metal command-buffer error, timeout, missing allowlisted dump,
or analyzer allowlist violation. Preserve its source, stderr/stdout, and partial
raw capture. Do not broaden capture to diagnose it. Any new BO role requires a
separate pre-registered experiment.

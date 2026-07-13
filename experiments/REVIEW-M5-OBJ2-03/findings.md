# REVIEW-M5-OBJ2-03 — Adversarial OBJ-2 acceptance review (M5 / Apple10 / G17g)

Empty-context reviewer, `docs/` capability docs (incl. Addenda 1/2/3). Run 3.
**VERDICT: PASS — 0 BLOCKER · 0 MAJOR · 0 mis-classified · 5 MINOR.**

No Metal-exposed hardware capability is entirely absent or mis-classified. All 6 run-02 findings VERIFIED
RESOLVED (rate-map present-NYC [M5-measured], vertex-fetch native-lowered-NYC, YUV/YCbCr NYC, MSAA resolve
filter native, MTLFence/Event kernel; ISA-integration reconcile memory/subgroup/atomics/texture/matrix → native).

## MINOR (none fails the gate; all closed in Addendum 4)
- **MINOR-1** Depth bounds test — Metal-*unexposed* → emulate (parity with conservative-raster / pipeline-stats).
- **MINOR-2** `MTLHeap` (placement heaps / resource aliasing) — VM/allocation API → kernel-managed/out-of-scope row.
- **MINOR-3** Stencil reference value + read/write masks — dynamic sub-fields of the native stencil row.
- **MINOR-4** Blend constant color — dynamic state subsumed under the native programmable-blend row.
- **MINOR-5** In-table §3–§7 classes + summary counts are stale vs Addenda 2/3 (reader over-counts NYC) — the
  final class (native) is correct in the addenda; refresh the pointer + counts.

## What's well-covered
Complete against the yardstick: datatypes/ALU (bf16+int64+logic+SFU, fp64 emulated); memory/atomics (float-add
present vs min/max+64-bit absent, M5-reprobed); subgroup/quad+scan; matrix/tensor (int-coopmat-absent vs
int8-via-MTLTensor-NYC + Neural-Accelerator marquee-NYC); full RT tail; graphics FF (layered render, multi-
viewport, line-fill, conservative-raster-emulate); TBDR (memoryless, MSAA, sample positions, occlusion); indirect
dispatch+draw, native tessellation, mesh-NYC, GS/XFB-emulate; formats/tiling (BC/ASTC, sparse, rate-map, YUV,
attribute fetch); arg-buffers Tier-2/bindless, residency/IO/fence-kernel, printf. Broad honest emulation list.

**OBJ-2 gate: PASS.**

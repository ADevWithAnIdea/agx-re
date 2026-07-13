# REVIEW-M5-OBJ2-02 — Adversarial OBJ-2 re-review of the M5 capability census

Empty-context reviewer, `docs/`-only truth. Run 2. **VERDICT: FAIL (narrow)** — prior findings 6/6 RESOLVED;
1 MAJOR + 1 MODERATE + 3 MINOR new enumeration gaps (all "add a row", only the rate-map is a new probe).

## Prior findings (REVIEW-M5-OBJ2-01) — all RESOLVED ✅
Layered rendering, fragment depth-output + early_fragment_tests, fragment sample-mask in/out, RT custom-AABB+curve,
int8-matrix split, stale FF/TBDR rows reconciled to EXP-M5-10. No regressions.

## New gaps (closed in EXP-M5-15)
- **MAJOR-1 — Variable rasterization rate map / foveated rendering** (`MTLRasterizationRateMap`) entirely absent
  (also missing from A18 base). Coarse side of Vulkan fragment-density-map / fragment-shading-rate.
- **MODERATE-2 — Vertex input state / attribute fetch** (`MTLVertexDescriptor`/`[[stage_in]]`) — characterized in
  `isa/README.md` but no capability row; on M5 rides the `0x18` memory delta → NYC.
- **MINOR-3** YUV/video + YCbCr sampler conversion (A18 §14 had ⏳, M5 dropped it). **MINOR-4** MSAA depth/stencil
  resolve filter. **MINOR-5** GPU sync primitives (`MTLFence`/`MTLEvent`/`MTLSharedEvent`).
- Mis-classified: **0** (every present row's class defensible).

## Resolution (EXP-M5-15, committed)
Added all 5 rows to `capability-matrix-m5.md` + `capability-completeness-m5.md` addenda. **Rate-map presence
MEASURED on M5** (`supportsRasterizationRateMapWithLayerCount:` = YES 1–2 layers, NO ≥3 — `raw/rrm_probe.txt`).
Tallies → native 85 / NYC 64 / emulated 13 / kernel 8 / microarch 5 = 175. No Metal-exposed capability
unaccounted-for. (Rate-map BO + tiler record logged as a new NYC probe target.)

## Well-covered (reviewer credit)
ISA/ALU (bfloat+int64+logic+SFU+bitops), atomics (float-add-present / min-max+64-bit-absent split), textures/
samplers/subgroup/quad/scan, int8 split + Neural-Accelerator marquee-NYC, full RT tail (AABB/curve/motion/
RT-from-render/companion), mesh-NYC + tessellation-native + GS/XFB-emulated, EXP-M5-10 FF/TBDR reconciliation,
arg-buffers/bindless/residency/IO/Dynamic-Caching, honest negative-results table.

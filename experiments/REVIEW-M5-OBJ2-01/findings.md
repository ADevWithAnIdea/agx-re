# REVIEW-M5-OBJ2-01 — Adversarial OBJ-2 acceptance review (M5 / Apple10 / G17g)

Empty-context reviewer, `docs/`-only truth (`capability-matrix-m5.md` + `capability-completeness-m5.md`),
Metal/MSL/Family-10 surface as yardstick. Bar: FAIL only if a Metal-exposed capability is entirely absent
or mis-classified; the 72 encoding-NYC rows are acceptable. Run 1 (interim gap-finder).

## VERDICT: FAIL — 1 BLOCKER · 4 MAJOR · 5 MINOR
Census is strong on the big surface (compute/ISA/RT/mesh/tensor/textures/blend); a few standard Metal-exposed
**graphics** capabilities have no row anywhere → unenumerated, so they fail the gate.

## BLOCKER
- **B-1. Layered rendering `[[render_target_array_index]]`** — HW basis for Vulkan multiview / single-pass
  cubemap / layered shadows / GL `gl_Layer`. Zero hits across `docs/`. `viewport_array_index` is documented
  (its own PPP bit); the layer-index output is a distinct capability with its own PPP bit, named nowhere.
  Add a row parallel to `viewport_array_index` (§10/§11).

## MAJOR
- **M-1. Fragment depth output `[[depth(...)]]` + `[[early_fragment_tests]]`** — core MSL, early-Z-affecting on
  TBDR; not enumerated (no depth-emit/`zs_emit` op in the M5 ISA tables either).
- **M-2. Fragment `[[sample_mask]]` output + input coverage mask** — Vulkan `SampleMask`, distinct from
  alpha-to-coverage; referenced only as an A18 op name, never classified for M5.
- **M-3. RT custom bounding-box (AABB) + curve primitives** — A18 §8 had the row; M5 §8 dropped it. Metal
  exposes custom-AABB + native curve geometry (first-class RT geometry types).
- **M-4. int8/integer cooperative matrix mis-classified "absent"** — the REJECT tested `simdgroup_matrix<int>`
  only; the Metal-4 `MTLTensor`/MPP neural path (present-but-NYC) is exactly where int8 matmul would live.
  Split `simdgroup_matrix<int>` REJECT (confirmed) from int8-via-`MTLTensor` (NYC).

## MINOR
- m-1. Metal-4 residency sets (`MTLResidencySet`) unlisted (→ kernel-managed bucket). m-2. Metal-4 IO command
  queues unlisted. m-3. RT companion ops (`rt_transform_test`/`ray_move`) folded away. m-4. conservative
  rasterization + pipeline-statistics queries (Metal-unexposed → emulate) omitted. m-5. indirect-*draw* has no
  capability row (though `cmdstream/README-M5-deltas.md` resolved `0x6c04` — matrix rows are stale-conservative).

## What's well-covered
Datatypes incl. bf16/int64 (fp64 correctly emulated); memory→atomics delta with float-atomic-min/max + all
64-bit atomics correctly re-probed absent; sampler byte-identical; subgroup/quad; Neural-Accelerator
dedicated-opcode question correctly left NYC; RT intersect/IFT/motion-blur/RT-from-render enumerated;
mesh/tess/TBDR/formats/tiling/compression/sparse/arg-buffers-Tier2 enumerated. Negative-results list is broad.

## Gate
FAILs not on the 72 NYC rows, but because ≥1 Metal-exposed capability (layered rendering) is entirely absent,
3 more graphics capabilities are unenumerated, and 1 classification is over-strong. Adding a census row for
each (any class, even NYC, satisfies the bar) + reconciling int8 clears it.

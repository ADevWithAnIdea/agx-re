# Hardware Capability Hypotheses — register of what we tried

Living log of the **extrapolate-and-test** work (see `../CLAUDE.md` → Methodology). Every
speculative probe of a capability the AGX hardware *might* have goes here — **including the
ones that didn't work**. Negative results tell the implementation team what Vulkan/OpenGL
features must be software-emulated.

Outcome vocabulary:
- **WORKS** — hardware does the thing; encoding/behavior documented in `docs/`.
- **NO-OP** — encoding is accepted but has no observable effect.
- **FAULTS** — hangs/crashes the GPU or faults (still informative).
- **PARTIAL** — works under some conditions; note them.
- **INCONCLUSIVE** — needs a better test.

| # | Capability hypothesis | Why we suspect it (extrapolation basis) | How tested | Outcome | Experiment |
|---|-----------------------|-----------------------------------------|-----------|---------|------------|
| _ | _(none yet — Phase 0 first establishes the encode→run→observe loop)_ | | | | |

## Candidate probe backlog (Metal-subset heuristic)
Seed list of Vulkan/GL-vs-Metal gaps worth probing once the tooling exists. Not commitments —
prioritize as phases dictate.
- Blend: logic ops; dual-source / extended blend factors Metal doesn't expose.
- Samplers: arbitrary border color; LOD-bias / anisotropy range beyond Metal limits; compare modes.
- Raster: polygon line/point fill mode; wide lines; provoking-vertex selection; depth clip vs clamp.
- Geometry pipeline: any hardware tessellation / geometry-shader / transform-feedback hooks
  (Apple HW historically lacks these — confirm for A18; mesh shading is expected present on Apple9).
- ISA: integer add-with-carry / wide multiply; bitfield insert/extract variants; rounding-mode
  variants; subgroup/quad shuffle/reduce ops beyond Metal's exposed set; ray-tracing intrinsics.
- Formats: texture/vertex/render formats the HW supports but Metal doesn't surface.

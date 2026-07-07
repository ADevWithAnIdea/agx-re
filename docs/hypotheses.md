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
| 1 | HW bitwise op is a general 2-input LUT (all 16 boolean funcs), not just and/or/xor | Vulkan/GL need logic ops beyond Metal's set; a LUT would cover them | swept the `0x0b ilogic` selector across all 16 truth tables on hardware | **WORKS** — all 16 boolean functions realized by one op ⇒ every Vulkan/GL logic op is a single native instruction | EXP-0013 |
| 2 | HW exposes float round modes beyond Metal's defaults | GL/Vulkan want floor/ceil/trunc/nearest; a round-mode field would give them free | spliced the byte+8 round-mode field of the `0x2f/0xaf` group | **WORKS** — 0=nearest, 2=floor, 4=ceil, 6=trunc all validated | EXP-0013 |
| 3 | Compare is one op over float/sint/uint with a type field | fewer opcodes if type is a field | swept `0x12` byte+6 type bits | **WORKS** — bits[1:3] select float/uint/sint; one icmpsel op | EXP-0013 |

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

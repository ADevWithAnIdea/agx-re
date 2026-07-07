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
| 4 | HW sampler supports arbitrary (Vulkan custom) border color | Vulkan wants RGBA border color | inspected the 8-byte sampler descriptor border field | **PARTIAL/NO** — only a 2-bit preset (transparent/black/white); arbitrary RGBA must be emulated | EXP-0015 |
| 5 | HW anisotropy exceeds Metal's 16× cap | field is 3-bit log2 (→128×) | read the aniso field width | **PARTIAL** — field can encode up to 128×; >16× not yet run on hardware (probe candidate) | EXP-0015 |
| 6 | Texture format/swizzle/sRGB/numeric-type are independent (Vulkan-shaped) | Vulkan separates these | varied each independently in the descriptor | **WORKS** — fully orthogonal; bgra8=rgba8+swizzle, depth32f=r32f code, sRGB is a flag | EXP-0015 |
| 7 | Texture read & write use different HW paths (write is a plain store, not a sampler op) | asymmetry lets image stores bypass the filter unit | disassembled read vs write; write = 0xd7 store family | **WORKS** — read=format-converting sampler op, write=0xd7 store; relevant for Vulkan storage images | EXP-0016 |
| 8 | Sample op+2 dimension/mode byte has spare encodings (offset-gather / extra gather comps) | only a subset of 256 values used | mapped the used op+2 values | **INCONCLUSIVE** — spare room exists; specific extra variants (texel-offset gather) not yet probed | EXP-0016 |
| 9 | HW does float atomic min/max | Vulkan/GL want them | tried MSL `atomic_fetch_min<float>` | **NO (via MSL)** — MSL rejects float atomic min/max & 64-bit atomic-add; only float atomic add + 64-bit min/max exist ⇒ Vulkan must emulate | EXP-0018 |
| 10 | Subgroup prefix-scan is native (not a shuffle-tree lowering) | fewer instrs if native | disassembled inclusive/exclusive scan | **WORKS** — single `simd_reduce` scan op (byte+7 shape) | EXP-0018 |
| 11 | HW supports depth clamp (Vulkan depthClampEnable) natively | GL/Vulkan want clamp vs clip | read the raster packet clip/clamp field | **WORKS** — native 2-bit field [11:10] in raster packet | EXP-0019 |
| 12 | Blend is programmable (any factor/op) rather than a fixed LUT | Apple TBDR programmable blend | varied blend factors, watched shader BO vs state pool | **WORKS** — blend compiles into the fragment shader; dual-source + logic-ops free via the shader path | EXP-0019 |
| 13 | Polygon line-fill (Vulkan POLYGON_MODE_LINE) is native | GL wglPolygonMode | set Metal triangle-fill line mode | **WORKS** — raster nibble 0x5 + flags bit26; polygon-point fill partial | EXP-0019 |

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

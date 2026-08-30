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
| 4 | HW sampler supports arbitrary (Vulkan custom) border color | Vulkan wants RGBA border color | EXP-0015 inspected the 8-byte sampler descriptor border field; **EXP-0136 drove the unused 4th 2-bit code from all three creation contexts** | **NO** — only a 2-bit preset (transparent/black/white); **the 4th code aliases to preset 0 from every creation context**, so there is no hidden fourth colour. Arbitrary RGBA must be emulated. `target: G16G` for the EXP-0136 half | EXP-0015 → **EXP-0136** |
| 5 | HW anisotropy exceeds Metal's 16× cap | field is 3-bit log2 (→128×) | EXP-0015 read the field width; **EXP-0136 patched the live descriptor-pool entry (our own process; descriptor DATA only) to aniso values Metal's API cannot produce and compared rendered sharpness against a ratio sweep** | **WORKS — to at least 128×, threshold-exact** (supersedes the earlier PARTIAL). Sharpness flips crisp exactly when `patched_aniso ≥ ratio`: ratio 16 blurs at 1/2/4/8 and is crisp from 16; ratio 64 blurs at 16/32, crisp from 64; ratio 128 blurs at 16/32/64, crisp at 128. Descriptor nibble = `log2(aniso)`; patched codes 5/6/7 read back intact. **Metal's 16× cap is pure software.** `target: G16G` | EXP-0015 → **EXP-0136** |
| 6 | Texture format/swizzle/sRGB/numeric-type are independent (Vulkan-shaped) | Vulkan separates these | varied each independently in the descriptor | **WORKS** — fully orthogonal; bgra8=rgba8+swizzle, depth32f=r32f code, sRGB is a flag | EXP-0015 |
| 7 | Texture read & write use different HW paths (write is a plain store, not a sampler op) | asymmetry lets image stores bypass the filter unit | disassembled read vs write; write = 0xd7 store family | **WORKS** — read=format-converting sampler op, write=0xd7 store; relevant for Vulkan storage images | EXP-0016 |
| 8 | Sample op+2 dimension/mode byte has spare encodings (offset-gather / extra gather comps) | only a subset of 256 values used | mapped the used op+2 values | **INCONCLUSIVE** — spare room exists; specific extra variants (texel-offset gather) not yet probed | EXP-0016 |
| 9 | HW does float atomic min/max | Vulkan/GL want them | tried MSL `atomic_fetch_min<float>` | **NO (via MSL)** — MSL rejects float atomic min/max AND ALL 64-bit atomics (every spelling, EXP-O2D corrects EXP-0018) ⇒ Vulkan int64 + float-min/max atomics must emulate | EXP-0018 |
| 10 | Subgroup prefix-scan is native (not a shuffle-tree lowering) | fewer instrs if native | disassembled inclusive/exclusive scan | **WORKS** — single `simd_reduce` scan op (byte+7 shape) | EXP-0018 |
| 11 | HW supports depth clamp (Vulkan depthClampEnable) natively | GL/Vulkan want clamp vs clip | read the raster packet clip/clamp field | **WORKS** — native 2-bit field [11:10] in raster packet | EXP-0019 |
| 12 | Blend is programmable (any factor/op) rather than a fixed LUT | Apple TBDR programmable blend | varied blend factors, watched shader BO vs state pool | **WORKS** — blend compiles into the fragment shader; dual-source + logic-ops free via the shader path | EXP-0019 |
| 13 | Polygon line-fill (Vulkan POLYGON_MODE_LINE) is native | GL wglPolygonMode | set Metal triangle-fill line mode | **WORKS** — raster nibble 0x5 + flags bit26; polygon-point fill partial | EXP-0019 |
| 14 | Tile size is fixed (not bpp-shrunk like G13/G14) | Apple9 Dynamic Caching may decouple tile from RF | varied RT format incl. rgba32f+4×MSAA | **WORKS/CONFIRMED** — 32×32 fixed regardless of bpp; don't port G13 shrink-tile logic | EXP-0021 |
| 15 | Programmable MSAA sample positions are userspace-emittable | Metal exposes programmableSamplePositions | diffed custom vs default sample positions — **RT-4 re-diffed the correct client BOs** (EXP-0021 diffed the wrong BOs) | **WORKS — userspace-emittable @+0x40** — written to a client BO (`0x100000e8000` 4× / `0x100000e0000` 2×) at +0x40 as N `(x,y)` f32 pairs on a 1/16 grid; native-decoded, **NOT** kernel-managed (corrects EXP-0021) | EXP-0021 / RT-4 |
| 16 | Apple9 has a dedicated matrix unit (not FMA-emulated coopmat) | WWDC hints; ML workloads | diffed simdgroup_matrix vs hand FMA/shuffle matmul | **WORKS** — dedicated op 0xcf, 8×8×8 tile MAC; fp16/fp32/bf16; no int8 via Metal | EXP-0022 |
| 17 | Apple9 has dedicated ray-tracing HW (not pure SW BVH) | Metal supportsRaytracing=YES; WWDC intersector | diffed ray_query vs hand Möller-Trumbore loop | **WORKS (HYBRID)** — HW intersect ops (rt_intersect/rt_as_load) + shader traversal loop; BVH build firmware-managed | EXP-0023 |
| 18 | G17P needs G13-style software scoreboard waits | G13 had explicit wait ops | compiled load->use, atomic->use; searched for wait ops | **NO — inverted** — HW register interlock handles RAW; no software wait exists; simpler backend than G13 | EXP-0025 |
| 19 | rcp/rsqrt/exp2/log2 are single-op HW (SFU), not multi-instr | Apple perf; G13 had SFU | disassembled fast-math rcp/rsqrt/exp2 | **WORKS** — `0x2f/0xaf` SFU single op; ~8-bit estimate seed for precise NR | EXP-0026 |
| 20 | Built-in sin/cos has full-range accuracy | GL/Vulkan conformance | HW readback at large args | **NO** — ~1 ULP moderate, ~5e5 ULP large args; driver must add SW range reduction | EXP-0026 |
| 21 | Perspective-correct interpolation is a HW mode bit | fewer instrs if native | diffed linear vs perspective vs flat fragment | **PARTIAL** — flat=iter_flat(0x1f), linear/centroid/sample are `iter` modes, but perspective = multi-instr (W-denom iter + rcp + fmul) | EXP-0029 |
| 22 | Raster-order-groups have a dedicated pixel wait/signal op | Metal ROG; G13 had wait_pix/signal_pix | diffed ROG vs non-ROG fragment | **PARTIAL** — no dedicated op; ROG reuses the 0x07 fence family (acquire/release) | EXP-0029 |
| 23 | HW has a bit-scan / find-MSB primitive Metal doesn't name | GLSL findMSB; useful for clz | swept the 0x27/0xa7 bit-count op-select | **WORKS** — find-MSB = `a7 05 56`; clz/ctz lower from it | EXP-0033 |
| 24 | HW has native single-op 64-bit integer add with carry-out | 64-bit atomics exist; perf | EXP-0033 spliced `0x1f` (u64 sub) → `0x9f`; **EXP-0146 re-ran it on M4 against an independently recomputed oracle over 8 boundary rows of a second input set** | **WORKS** — one-op 64-bit add/sub with the carry produced **inside** the single instruction (`iadd2`, `1f 01 56 00 02 08 00 50 17 05`; `0x1f`→`0x9f`). Oracle rows include `0x8000…0 + 0x8000…0 = 0`, `0x7FFF…F + 1 = 0x8000…0`, `0xFFFFFFFF00000000 + 0x00000000FFFFFFFF = 0xFFFF…F`, `0xFFFF…E + 3 = 1`; 5/5 serial reps, zero fault classes, both gated runs. **Apple's compiler emits a 5-instruction chain instead.** LIMITATION: bit-flipped from the compiler's own subtract, **not synthesized from scratch**. `target: G16G` for the EXP-0146 half | EXP-0033 → **EXP-0146** |
| 25 | Image/texture atomics are native | Vulkan storage-image atomics | MSL atomic on texture2d<uint,rw>/texture_buffer | **WORKS** — lower to memory-family device atomic (0x67) with in-shader texel addr; 256 contended adds=256 | EXP-0034 |
| 26 | `falu2`'s unexplained `mod_lo` modifier hides an operand-source-class selector, and the register field may reach something other than a GPR | the field was `raw`/unlabelled while `falu2` is the ISA's most-used instruction; ISA structure suggested a source-class rather than a modifier | dense sweep of all 8 `mod_lo` values × 8 operand configurations, plus a 33-point `srcB_reg` sweep at `mod_lo = 2`, on hardware | **WORKS** — `mod_lo` bit0 selects `srcA`'s source class, bits[2:1] select `srcB`'s (`0` GPR, `1` non-GPR file, `2`/`3` read `0.0`, **bit2 dominates bit1**). In class 1, **`srcB_reg` 64..127 is an inline 8-bit minifloat immediate** (`k = v − 64`, `e = k>>3`, `m = k&7`; `m·2^-5` if `e == 0` else `(8+m)·2^(e−6)`), 10 HW-confirmed points. The pre-registered hypothesis was **REFUTED in both halves** and replaced. `falu2` is now EMITTABLE. `target: G16G` | EXP-0138 |
| 27 | The Apple9 matrix unit can negate its accumulator (a mode Metal never emits) | `H-M5-1` found a product-negate bit on Apple10/G17g; the analogous Apple9 field was modelled as opaque `raw` | dense 128-value sweep of `matrix_mac` `b11hi`, twice, with a per-tile-row readback | **WORKS** — `b11hi` bits 0–1 are **accumulator sign controls resolved per tile row**: `0`→`+C`, `1`→`−C` rows 0–3, `2`→**`A·B − C`** (all rows), `3`→`−C` rows 4–7. Correct `A·B + C` requires `(b11hi & 3) == 0`. This is a *different* bit and a *different* operand from `H-M5-1`'s Apple10 product-negate; neither transfers to the other. `target: G16G` | EXP-0147 |
| 28 | MSL's `[[barycentric_coord, center_perspective]]` qualifier selects the interpolation mode in hardware (and would fix the position-read barycentric bug) | MSL exposes the qualifier and the unqualified form returns unnormalized numerators when the FS reads `[[position]]` | compiled both qualified spellings and the unqualified form from our own MSL; compared disassembly and hardware readback | **NO-OP** — both qualified forms produce **identical disassembly** (`iter = 2`, `fspecial = 0`) and identical results. **There is no MSL-level escape hatch**; a driver needing correct perspective barycentrics alongside a `[[position]]` read must normalize the numerators itself. `target: G16G` | EXP-0137 |
| 29 | `uniform_mov`'s byte+1 top bit widens the uniform-register index | the field is 8 bits but the uniform file was believed ≤128 entries (7-bit index) | dense 0..255 sweep of `usrc` against a host-computed oracle, with four bound magic constants | **WORKS, but not as hypothesised** — `usrc ≥ 0x80` **materialises the immediate `usrc & 0x7F`** into the destination GPR (**128/128** matched the oracle); it is not a uniform read at all. Below `0x80` the field is a **pair-quantised** uniform index (`usrc` and `usrc ^ 1` read the same word; consecutive uniforms step by 4), and unallocated indices return a **silent zero**. Gives an emitter a second 7-bit constant-materialisation path. `target: G16G` | EXP-0140 |
| 30 | `pack_convert` can reach pack formats Apple's compiler never emits from MSL | byte+9 was modelled as part of an opaque 40-bit `fmt_word`, and our corpus only ever showed two 16-bit forms | dense 0..255 sweep of byte+9, each candidate code scored against **8 independent semantic vectors** (NaN and out-of-range included) | **WORKS** — byte+9 is a **format selector**: `0x42/46/4A/4E` snorm2x16, `0x82/86/8A/8E` unorm2x16, and **`0xC2/C6/CA/CE` an 8-bit unorm-lane pack (scale 255)** that the compiler never emitted here. Bits 2–3 don't-care; bits 6–7 select. `target: G16G` | EXP-0144 |
| 31 | The hardware implements NIR's `ibfe` `offset`-mod-32 masking (so a back-end need not mask) | NIR defines `ubfe`/`ibfe` offsets mod 32; the field is 6 bits | dense out-of-range sweep of `offset` and `width`, scored against competing literal / mod-32 / clamp models | **NO — and the two fields disagree with each other.** `offset` is **LITERAL** (32..63 shift the field out; literal model 64/64 vs mod-32 32/64), so **a back-end must mask in software**; `width` **IS** mod-32 (64/64 vs 37/64), so `width = 32` ≡ `width = 0`. The `width` result refuted the experiment's own pre-registration. `target: G16G` | EXP-0139 |
| 32 | A18/Apple9 has a native geometry-shader stage or a stream-output unit | Vulkan/GL need both; Apple historically lacks them, but this had never been probed on Apple9 | drove `rasterizationEnabled = NO` and looked for a distinct pipeline path, using an atomic side effect to prove the vertex stage ran | **NO — they do not exist.** `rasterizationEnabled = NO` runs the **vertex stage on the same VDM/tiler path** with the fragment stage merely elided. GL/Vulkan GS and transform feedback must be **permanently emulated**; this row converts a carried-over assumption into a measurement. `target: G16G` | EXP-0136 |
| 33 | Apple9 has a polygon **point** fill mode and/or conservative rasterization | Vulkan `VK_POLYGON_MODE_POINT` and `VK_EXT_conservative_rasterization`; `MTLTriangleFillMode` might hide a third value | rendered a reference triangle in each documented fill mode; separately rendered four tiny triangles covering only a *corner* of one pixel, explicitly not its centre | **NO, both.** `MTLTriangleFillMode` is a functionally distinct **two**-valued enum (`.fill` 72 lit px / `.lines` 38 lit px on the same triangle) with no third case. The corner-sliver triangles lit **zero pixels in all four cases, both runs** — standard centre-sample rasterization, no conservative mode anywhere in the public surface. Both must be emulated. `target: G16G` | EXP-0123 |
| 34 | Apple9 supports wide lines (Vulkan `wideLines` / `glLineWidth`) | GL/Vulkan both want it; a fixed-function width field would be cheap | rendered horizontal and diagonal lines using **only** the documented, SDK-header-declared encoder surface | **NO via the documented API** — no line-width, line-rasterization-mode or conservative-raster selector exists in the current public SDK headers; every line renders at the same fixed narrow band. Must be emulated geometrically. ⛔ An **undocumented private selector** was observed to have a real GPU-visible effect and was ruled **OUT OF BOUNDS** (selector probing is symbol-level introspection of Apple software, not hardware observation); it backs no claim. `target: G16G` | EXP-0123 |
| 35 | The provoking-vertex convention is selectable (OpenGL wants last-vertex) | GL's default is the last vertex; D3D/Metal use the first | drew a triangle list, a reversed-index list, and a strip, and read back which vertex's flat attribute won | **NO — fixed to the FIRST-fetched vertex, with no Metal API alternative.** A GL driver must emulate the last-vertex default by index rewriting or attribute duplication. `target: G16G` | EXP-0097 |

## Candidate probe backlog (Metal-subset heuristic)
Seed list of Vulkan/GL-vs-Metal gaps worth probing once the tooling exists. Not commitments —
prioritize as phases dictate.
- Blend: logic ops; dual-source / extended blend factors Metal doesn't expose.
- Samplers: ~~arbitrary border color~~ (**answered NO**, #4); ~~anisotropy range beyond Metal limits~~
  (**answered WORKS to ≥128×**, #5); LOD-bias range beyond Metal limits; compare modes.
- Raster: **all answered** — polygon **line** fill is native (#13), polygon **point** fill does not
  exist (#33), **wide lines** do not exist via the documented API (#34), the **provoking vertex is
  fixed to the first-fetched vertex** with no API alternative (#35), depth clip **and** clamp are
  both native (#11, EXP-0123). **Conservative rasterization** does not exist (#33). Remaining:
  the exact subpixel snap granularity of line rasterization (EXP-0123 flagged it, did not bisect it).
- Geometry pipeline: ~~any hardware tessellation / geometry-shader / transform-feedback hooks~~ —
  **all three answered**: tessellation is **NATIVE** (EXP-O2H), mesh shading is **NATIVE**
  (EXP-0030, re-validated EXP-0135), geometry shaders and transform feedback **do not exist**
  (#32, EXP-0136).
- ISA: ~~integer add-with-carry~~ (**answered**, #24); ~~bitfield extract out-of-range semantics~~
  (**answered**, #31); wide multiply; bitfield *insert* variants; rounding-mode variants;
  subgroup/quad shuffle/reduce ops beyond Metal's exposed set; ray-tracing intrinsics.
  **Still open and cheap:** `cvt_bf16`'s rounding mode (EXP-0144 withdrew its own claim — one
  shard, ~2,048 cases) and `compute_fence_scoped.mask`, the one fence field that showed a live
  signal (EXP-0147).
- Formats: texture/vertex/render formats the HW supports but Metal doesn't surface.

> **Target labels (added 2026-08-28).** Rows #1–#25 were established on the **A18 Pro / G17P**
> unless a row says otherwise. Rows **#26–#32**, and the EXP-0136/0146 halves of #4, #5 and #24,
> were measured on the **M4 / G16G** and carry `target: G16G`. All live testing has since moved to
> the A18 Pro / G17P and **closure is measured against full G17P** (`../CODEX.md`, "Target
> discipline"); the M4 results stay **valid on their own target** and are **not** relabelled G17P.
> **G17P revalidation is under way (`EXP-0153`).** Cross-target promotion needs a recorded
> validation or an explicit `INFERRED` label.

---

## M5 (Apple10/G17g) hypotheses

### H-M5-1 — cooperative-matrix MAC can NEGATE the A·B product (Metal-unexposed)  ✅ WORKS
**Hypothesis (extrapolate):** the `simdgroup_matrix` MAC op might have modifier bits beyond what MSL's
`simdgroup_multiply_accumulate` exposes. **Test (EXP-M5-20, splice-and-observe, A=2·I B=3·I C=5·I → R=11·I):**
splicing `m5_matrix_mac` **byte+13 bit6 (0x40)** flips the result to **−(A·B)+C** (R = −6/−4/−3/−1 for
C∈{none,r2,r4,r6}). **Outcome: WORKS** — a fused *negated* multiply-accumulate the Metal API does not surface.
A driver targeting Vulkan cooperative-matrix (or a fast-math path) could emit it directly. HW-validated on M5.

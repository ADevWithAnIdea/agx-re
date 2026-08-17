# A18 Pro (G17P) Mesa Userspace Porting Guide

The top-level **synthesis** a from-scratch implementer follows to add A18 Pro (SoC **T8140**,
GPU **G17P**, Metal feature-family **Apple9**) support to the Mesa `asahi` userspace driver. It
maps every Mesa `src/asahi` userspace **module** to the A18-specific hardware facts documented in
`docs/`, tells you **what to reuse from the M1/M2 (G13/G14) driver**, **what is different for G17P
(with the doc section and the key facts)**, and **what to software-emulate or route to the
kernel/firmware**.

This is the capstone document for the project's Definition of Done ("implement a full GPU userspace
from `docs/` alone"). It is **navigational**: it does not restate the encodings — it cites the doc
section that owns each fact so you can jump straight to the bit layout you need.

> **Status: synthesis (host-only, no new RE).** Every fact below is traceable to an already-
> established finding in another `docs/` file; the citation is inline. This file introduces no new
> reverse-engineering. Per `../CLAUDE.md`, we document the **hardware**, not Apple's driver; `mesa/`
> is a read-only reference for the *shape* of what a userspace driver must produce. No Apple binary
> was disassembled.

---

## 0. How to read this guide (find the doc by implementation task)

Pick the task you are implementing; the guide section and the owning `docs/` file are named.

| I am implementing… | Guide § | Owning `docs/` (jump here for bit layouts) |
|---|---|---|
| NIR→AGX code generation, instruction packing | §1 Compiler | `isa/README.md` + `isa/encoding-tables.md` |
| Register allocation / spilling / scheduling | §1 Compiler | `isa/README.md` "Machine model" (EXP-0020) |
| Wait/scoreboard insertion (RAW hazards) | §1 Compiler | `isa/README.md` "Async completion" (EXP-0025) |
| Transcendentals / trig / reciprocal lowering | §1 Compiler | `isa/README.md` "Transcendentals" (EXP-0026) |
| Vertex attribute fetch | §1 Compiler | `isa/README.md` "SR enum + ABI" (EXP-0031) |
| Compute dispatch record (CDM) | §2 Cmdstream | `cmdstream/README.md` "Compute launch" |
| Draw / VDM / tiler stream, USC binding | §2 Cmdstream | `cmdstream/README.md` "Graphics (draw)", "USC bind grammar" |
| Fixed-function state (depth/stencil/raster/blend) | §2 Cmdstream | `cmdstream/README.md` "state packets"; blend → §1/§7 |
| Indirect draw/dispatch, occlusion, timestamps | §2 Cmdstream | `cmdstream/README.md` "Completeness…" (EXP-0027) |
| Multi-viewport, clip, primitive restart, point size | §2 Cmdstream | `cmdstream/README.md` "Geometry-output pipeline" (EXP-O2A) |
| Mesh / task shading | §2 Cmdstream + §1 | `cmdstream/README.md` "Mesh/object"; `isa/README.md` (EXP-0030) |
| Texture / sampler / buffer descriptors | §3 Descriptors | `descriptors/README.md` + `descriptors/format-table.md` |
| pipe_format → hardware format code | §3 Descriptors | `descriptors/format-table.md` |
| Bindless / sampler-heap | §3 Descriptors | `descriptors/README.md` "Sparse/…/bindless" (EXP-O2B) |
| Texture memory layout (twiddle, mip, compression) | §4 Tiling | `tiling/README.md` |
| Tile size, imageblock budget, MSAA, memoryless | §5 Pipeline | `pipeline/README.md` |
| Submit / BO / VM bind / sync; firmware-managed items | §6 Kernel | `kernel-interface.md` |
| Native-vs-emulate decisions for a Vulkan/GL feature | §7 Capabilities | `capability-matrix.md` + `capability-completeness.md` |
| The honestly-open items and their fallbacks | §8 Gaps | this file §8 |

### Four framing facts that change the whole port vs M1/M2

Read these before touching any module — each retires or rewrites a chunk of the M1/M2 driver:

1. **The AGX ISA is entirely new.** `AGX2.xml` (G13/G14) does not decode G17P; opcodes and field
   positions are different (`isa/README.md` "Confirmed: wholly different ISA"). The instruction
   **table** and the **layout math constants** are the real per-generation content — the C
   algorithms mostly carry over (`mesa-userspace-requirements.md` §1).
2. **Async completion is a hardware register interlock, not a software scoreboard** — *simpler*
   than G13. There is **no `wait` op and no `AGX_MAX_PENDING`**; a consumer that reads a still-
   pending destination stalls in hardware (`isa/README.md` "Async completion", EXP-0025). The
   G13 wait-insertion pass becomes essentially inert (§1).
3. **The fragment tile is a fixed 32×32** and does **not** shrink with bpp — do **not** port the
   G13/G14 tile-shrink logic (`pipeline/README.md` "Tile size", EXP-0021).
4. **Blend / logic-op / dual-source are compiled into the fragment shader**, not emitted as a
   fixed-function packet (`cmdstream/README.md` "Blend is programmable", EXP-0019). This is a
   *compiler* responsibility, exactly as Asahi already does for M1/M2.

Generation is threaded through Mesa as `dev->chip ∈ {G13G, G13X, G14G, G14X}`
(`mesa-userspace-requirements.md` §1); **there is no G15/16/17 path anywhere** — G17P is entirely
out-of-tree. A port adds a new `chip` value and re-populates the encoding tables + layout constants.

---

## 1. Compiler backend (NIR → AGX)

**Mesa modules:** `compiler/` (`agx_compile.c`, `agx_pack.c`, `agx_opcodes.py`,
`agx_register_allocate.c`, `agx_spill.c`, `agx_insert_waits.c`, the `agx_nir_lower_*` passes),
`isa/` (`AGX2.xml`, disassembler), and the fast-link stitching in `lib/agx_linker.c` /
`lib/agx_nir_prolog_epilog.c`. It lowers NIR to AGX machine code, allocates registers, schedules,
inserts hazard synchronization, and stitches prolog/main/epilog.

**SAME as M1/M2 (reuse):**
- The overall NIR→AGX backend **structure and algorithms**: SSA form, the pass pipeline, the
  register-allocation and pressure-scheduling *algorithms*, and the prolog/main/epilog fast-link
  model are portable. Only the encoding tables and machine-model **constants** are A18-specific
  (`mesa-userspace-requirements.md` §2a).
- The `genxml`/`isa`-style toolchain shape (a machine-readable DB driving assemble+disassemble). Our
  clean-room equivalent is `tools/agx-isa/` (`db.json`/`isadb.py`), round-trip validated.

**DIFFERENT for G17P** — read `isa/README.md` and the per-instruction tables in
`isa/encoding-tables.md`:
- **Whole instruction set is new** (`isa/README.md`). The authoritative, self-contained per-
  instruction bit tables (byte0 group, length rule, match bits, every field + enum) are in
  `isa/encoding-tables.md`, grouped by family. Length is **not** encoded in the first parcel (unlike
  G13): it is a function of the byte-0 group plus a per-group length bit (`isa/README.md`
  "Instruction-length rule").
- **Machine model** (`isa/README.md` "Machine model", EXP-0020): **96 addressable 32-bit GPRs**
  (not G13's 128), **2 independently-addressable 16-bit halves per GPR**, a **uniform register
  file** + a separate **uniform program** (the `_agc.main.constant_program`, a thread-invariant
  scalar datapath), and **spill to per-thread scratch above 96 GPRs** (Dynamic Caching). Footprint
  is declared in the shader's own `__GPU_METADATA`; the launch descriptor carries only a coarse
  **2-level occupancy tier by PEAK register pressure** (config bit23; NOT a fixed ~12-GPR threshold — EXP-M4-09/CMD-8). Register-field widths differ by form (nibble
  dst in the compact `falu2`, 7-bit `(reg<<1)|size` for integer/wide forms).
- **Async = HW register interlock, NO scoreboard waits** (`isa/README.md` "Async completion",
  EXP-0025 — CRITICAL): do **not** emit G13-style scoreboard `wait` ops or slot assignments; they do
  not exist. `agx_insert_waits.c`'s job largely disappears. The **only** ordering primitive is the
  barrier: `threadgroup_barrier` = byte0 `0x07`, 6 B, **byte+3 = fenced memory scope** (`0x61`
  threadgroup / `0x85` device); `simdgroup_barrier` emits no op (lockstep SIMD). Getting the barrier
  scope wrong is a **silent-corruption** surface (splice-proven).
- **Instruction families** (heads; full tables in `isa/encoding-tables.md`): float ALU `0x09`
  (fadd/fmul/fma) + `0x0b` unary + `0x12` fmin/max + `0x10`/`0x11` native-half & bfloat; integer
  spread across `0x9f`/`0x1f` (add/sub/mul/mad/shift-left), `0x02` (min/max), `0x0b` (logic LUT),
  `0x12` (compare→select), `0xa7`/`0x27` (shift/bfe/popcount/find-MSB/rotate), `0x32` (u64 carry);
  memory/atomics `0x67`/`0xe7`/`0xd7`/`0x57`; control flow + call/return `0x0f`/`0x8f` + frame
  `0x6f`/`0x43`; SR read `get_sr` (low-nibble `0xc`); textures `0xb0`/`0x90` (+companion `0x05`),
  write `0xd7`, deriv `0x37`; SIMD `0xbf`/`0x3f`/`0x47`/`0xc7`/`0x17`; **matrix `0xcf`**; **RT**
  `rt_intersect` (low-nibble `0x4`/byte+1 `0xea`), `rt_as_load` `0xdf`, `0x5f`; fragment `iter`
  `0x2f`/`0x1f` + `frag_color_store` `0xe7/06` + `tile_read` `0x67/0e`. A broad-corpus byte0 census
  tokenizes **~88%** of bytes with **no whole undecoded family remaining**.
- **Numerical edge behavior is not closed:** EXP-0047 provides a repeatable M4
  no-fast-math Metal source-path baseline (fp32 DAZ/FTZ-like add/mul, preserved
  tested fp16 subnormals, operand-B min/max ties, tested rounding rules). Do not
  treat it as native-instruction semantics or promote it to A18; retain the
  relevant NIR lowerings until independent native-op and A18 tests pass.
- **Transcendental / trig lowering** (`isa/README.md` "Transcendentals", EXP-0026): SFU group
  `0x2f`/`0xaf` computes rcp/rsqrt/exp2/log2/sqrt/round as **single ops** (fast-math); precise mode
  uses a `0x29` ~8-bit estimate seed + **2 Newton-Raphson iterations**. Composites: `pow =
  exp2(b·log2 a)`, `a/b = a·rcp(b)`, `exp/log` scaled. **Driver-facing gap:** built-in range
  reduction is good to ~1 ULP for moderate args but blows up (~5·10⁵ ULP) at large args — a
  conformant Vulkan/GL `sin/cos` **must add software Payne-Hanek range reduction** (§8).
- **Vertex attribute fetch is in-shader software** (`isa/README.md` "SR enum + ABI", EXP-0031):
  there is **no fixed-function vertex fetch**. The driver must **generate attribute-fetch code from
  the vertex format** into the VS prologue (exactly what `agx_nir_lower_vbo.c` does): per attribute a
  `device_load` from the vertex-buffer base (uniform **slot 3**) at `index×stride + offset` + a
  format-convert ALU, `index` from `get_sr` `vertex_id` (`0xdd`) / `instance_id` (`0xd8`). Stride/
  offset/format are baked into the shader; the attribute table supplies only the base pointer.
- **SR enum + preload ABI** (`isa/README.md` EXP-0031): `get_sr` SR number is in **byte1** (full
  table in the doc). **No stage preloads IDs into GPRs** — IDs are read via `get_sr` on demand; only
  buffer/vertex bases and scalar uniforms are preloaded into the uniform register file.
- **The `tools/agx-isa` DB is the encoder/decoder** — the executable form of the ISA
  documentation. `docs/isa/agx3.xml` (Mesa-schema render of the DB, ROADMAP W3) is the artifact the
  impl team drops into `src/asahi/isa/` to generate the G17P disassembler; still-inferred operand
  sub-fields render as reserved/`<zero>` bits, tightened as decoded.

**EMULATE / route:**
- **Programmable blend / framebuffer logic ops / dual-source** are a **compiler** job: lower blend
  state into the FS blend microprogram and logic ops through the `0x0b` 16-function bitwise LUT
  (`isa/README.md` "Bitwise"; `cmdstream/README.md` "Blend is programmable"). See §2/§7.
- **Transcendental large-arg trig** → software range reduction (above).
- Nothing else in the compiler routes to the kernel; the compiler owns all code generation.

---

## 2. Command / control stream (`docs/cmdstream/`)

**Mesa modules:** `genxml/` (`cmdbuf.xml`, `gen_pack.py`), `lib/agx_ppp.h`, `lib/agx_usc.h`,
`lib/agx_bg_eot.c`, plus the Gallium/Vulkan state-emit that builds the VDM/CDM/PPP records. Encodes
GPU work word-by-word in BOs: **VDM** (draw/tiler "TA"), **CDM** (compute "CL"), and the **PPP**
fixed-function state records they reference, plus the **USC** shader-binding programs.

**SAME as M1/M2 (reuse):**
- The three-control-stream model (VDM tiler / CDM compute / PPP fixed-function state referenced by
  them) and the two graphics channels (**TA** tiler/vertex + **3D** fragment) carry over
  (`cmdstream/README.md` "Graphics (draw)"). The genxml packing *framework* concept is reusable;
  the struct/enum contents are re-derived.

**DIFFERENT for G17P** — read `cmdstream/README.md`:
- **Compute launch (CDM)**: a stream of **0x2c-byte records** + `0x40000000` terminator.
  `+0x08 = shaderVA>>6` (64-byte units), grid `+0x10/+0x14/+0x18` **in threads** (not
  threadgroups), threadgroup `+0x1c..`, config word `+0x00` bit23 = occupancy tier. Threadgroup-
  memory size lives in the **shader BO** as `(bytes<<2)|0x80`, not the CDM record (EXP-0011/0024).
- **Graphics selection = queue-relative code window + separate stage selectors**
  (`cmdstream/README.md`, M4 EXP-0042): VS changes emit a VDM `(0x500, token)` pair; FS uses a
  32-bit code-window-relative selector at `0x58000+0x08`. Authored code appears in 0x40-header,
  aligned-size records with constant program + main + padding. The USC program
  `0x10000130000` retains per-stage uniform-preamble programs. Exact mapping of the stable
  `0x10000000000` window to queue `usc_exec_base`, general token synthesis, and the record
  consumer remain open; do not assume a positional walk or a per-render code-base field.
- **PPP header = length word, not a present mask** (`cmdstream/README.md` "PPP fixed-function
  header", EXP-0024): the 8 VDM bind-pairs/pool layout are fixed; presence is a monotonic **length
  word** (VDM `0x18000+0x0c` / pool `0x58000+0x14`, +0x400 when a depth/stencil block is appended);
  per-group presence = **enable bits inside each packet**.
- **State packets** in `0x58000` (`cmdstream/README.md` "state packets", EXP-0019, all HW-validated):
  depth `+0x38` / stencil `+0x3c` (compare 0–7, stencil-op 0–7 tables in the doc); **rasterizer**
  `+0x70` — cull[1:0], winding bit16, **native 2-bit depth clip-vs-clamp [11:10]** (good for Vulkan),
  polygon line-fill nibble `0x5`+bit26, depth bias in the tiler-param region.
- **Programmable blend (compile into FS)** — blend factors/ops are lowered into the FS shader-code
  BO, not a fixed-function LUT; `0x58000` keeps only color-write-mask + blend-class/constant/enable
  flags (`cmdstream/README.md` "Blend is programmable"). Compile blend state into fragment shaders
  (§1, §7).
- **Indirect / occlusion / timestamp** (`cmdstream/README.md` "Completeness", EXP-0027):
  indirect draw swaps VDM opcode `0x61c4→0x6404` (indexed `0x61f2→0x6432`) + an args pointer;
  **indirect dispatch injects a 2nd CDM + a grid-setup helper shader** to multiply
  `threadgroups × threadsPerThreadgroup` (the driver **must replicate this multiply**); occlusion
  mode = bit14 of `0x58000+0x8c` (Boolean vs Counting), offset `+0xa0 = byteOffset<<14`; GPU
  timestamps are u64 ns (`timestampPeriod=1.0`) but **only stage-boundary sampling works** (dispatch/
  draw-granular reads all-zero → a Vulkan emulation flag).
- **Geometry-output pipeline** (`cmdstream/README.md` "Geometry-output", EXP-O2A): **multiple
  viewports** `0x68000` (count `+0x900 = ((count-1)<<12)|0x0C00`, max 16, 6-float per-viewport
  transform); PPP **output-select word `0x58000+0x20`** — bits[7:0] = **clip-distance plane mask**
  (max 8), bit18 = point_size, bit19 = viewport_array_index; **primitive restart** = all-ones index
  at VDM `+0x68` (no separate enable); alpha-to-coverage = FS-lowered + FF bits.
- **Mesh / object shading** (`cmdstream/README.md` "Mesh/object", EXP-0030): reuses the **graphics
  path** (no CDM, single unified submit); replaces the primitive record with a **mesh-grid-dispatch
  record `0x70000600` + grid dims**, plus a mesh dispatch-descriptor BO. Emit is **compute-style
  `0xe7` stores** into a firmware-managed UVB buffer (§1); UVB sizing/wiring is a **kernel item**.
- **Tile-shader mid-render dispatch** (`isa/README.md` EXP-O2D): **no separate submission** — the
  tile-dispatch record is appended inline to the render control stream; a draw vs
  draw+`dispatchThreadsPerTile` is byte-identical IOKit.

**EMULATE / route through the existing UAPI fields** (§6 has the contract): **ZLS / depth store**
(`zls_ctrl`) and **scissor** (`isp_scissor_base`) are not emitted in the captured client stream;
userspace must compute their existing render-command values. Graphics shader selection is different:
M4 EXP-0042 observes per-draw VS-token and FS-relative selectors within a queue-wide code window.
The exact mapping of its base to queue `usc_exec_base` remains open, and there is no per-render
code-base field to add or assume.
*(**Sample positions are NOT in this list — RT-4:** they are userspace-emittable to a client BO `@+0x40`,
emitted directly, not a submit param — see §5.)*

---

## 3. Resource descriptors (`docs/descriptors/` + `format-table.md`)

**Mesa modules:** `cmdbuf.xml` TEXTURE/PBE/SAMPLER/BORDER structs, `lib/agx_border.c`, the
Vulkan descriptor-set packing (`vulkan/hk_descriptor_set*.c`, `hk_nir_lower_descriptors.c`,
`hk_sampler.c`, `hk_image_view.c`). Packs texture/sampler/buffer descriptors and the bindless
argument-buffer / descriptor-set model.

**SAME as M1/M2 (reuse):**
- The **Tier-2 argument-buffer / bindless substrate** shape: an 8-byte slot per bound resource in
  binding order; buffers inline a GPU VA, textures/samplers point to a descriptor block
  (`descriptors/README.md` binding model). Bindless indexing logic is portable.
- **Format/swizzle/sRGB/numeric-type orthogonality is Vulkan-shaped** (`descriptors/README.md`
  "Capability notes"): `bgra8 = rgba8 + swizzle`, `depth32f = r32f` code, sRGB an independent flag —
  maps directly to Vulkan without lowering.

**DIFFERENT for G17P** — read `descriptors/README.md` + `descriptors/format-table.md`:
- **Texture descriptor is 32 bytes** (not G13's 24) with new bit positions (EXP-0015): type
  byte0[0:2], format `(byte1<<8)|byte0`, swizzle word0[16:27] (4×3-bit), width/height, **base VA =
  `VA>>4`** (16-byte units), sRGB word3 bit12, mip/compression flags, secondary (aux) VA. Full field
  table in `descriptors/README.md`; **texture-type codes** (4-bit) and the **31-format code table**
  in `format-table.md`.
- **Sampler descriptor is 8 bytes** (EXP-0015): LOD min/max fixed-point, aniso log2 [20:22]
  (encodes 128× though Metal caps 16×), mag/min/mip filters, address modes [29:37], compare (sense
  bit39 + test [40:42], all 8 funcs → native PCF), **border color = 2-bit preset only**.
- **Buffer descriptor** = bare inline 8-byte GPU VA, no length/format word.
- **format → code table**: `descriptors/format-table.md` is self-contained (defers to no
  experiment) — pipe_format ↔ (byte0/byte1) code, numtype/sizeclass/channel-arrangement, BC/ASTC
  sizeclasses, depth/stencil (no packed D24S8 — Z/S separate resources).
- **Bindless sampler-heap** (`descriptors/README.md` "Sparse/…/bindless", EXP-O2B): a sampler in an
  argument buffer is an **8-byte little-endian `gpuResourceID`** = a sequential **index into a
  device-global sampler table** (capacity 500000, stride 8); shader-computed dynamic index works.
  Distinct from the Metal-auto pointer-to-descriptor form.
- **Sparse tier flag** (EXP-O2B): the descriptor carries a **sparse-tier flag** (byte0 hi-nibble
  `(byte0 & ~0x20)|0x10`; word1 bits[28:29]); **tile residency is NOT in the descriptor** — it lives
  in the GPU page table (kernel/firmware-managed, §6). Sparse tile = 16 KiB.
- **Render-target ("PBE") is not a per-texture descriptor bit** (EXP-O2B): a sampled descriptor is
  byte-identical with/without RenderTarget usage — RT state is structural via the attachment path
  (§5). Only `ShaderWrite` + `PixelFormatView` disables lossless compression.

**EMULATE / route:**
- **Arbitrary sampler border color** → software-emulate (only a 3-preset field exists;
  Mesa's M1/M2 two-sampler-plane trick, `mesa-userspace-requirements.md` §4). `clampToZero ==
  clampToBorder(transparent-black)` (one HW mode).
- **Sparse residency** → page-table updates via the **kernel** (§6), not a descriptor write.

---

## 4. Texture / image memory layout (`docs/tiling/`)

**Mesa modules:** `layout/tiling.cc`, `layout/layout.c`, `layout/formats.c`, `libagx/compression.cl`.
Computes twiddle order, mip trees, and lossless-compression metadata so the texture/PBE units can
address memory.

**SAME as M1/M2 (reuse):**
- The **Morton/Z-order twiddle math shape** and the **linear (buffer-backed) row-major** path carry
  over conceptually; the tiling *algorithm* is portable — verify the exact order on A18
  (`tiling/README.md` §1–§2).

**DIFFERENT for G17P** — read `tiling/README.md`:
- **Twiddle = ROW-MAJOR GRID OF MORTON TILES (RT-3), tile edge bpp-dependent** (§1.1, EXP-0017/RT-3):
  the texture is a **row-major grid of square Morton tiles** of edge **T** texels, where **T = largest pow2 with T²·bpp≤16KiB** (bpp1→**128**, bpp2/4→64, bpp8/16→32; EXP-M4-06) — NOT the old flat 64 for
  bpp ≤ 4, T = 32 for bpp ≥ 8** (bpp-DEPENDENT). With `tx = x>>log2(T)`, `ty = y>>log2(T)`,
  **`cols = round_up(ceil(W/T), G)`**, G=0x4000/(T²·bpp) (RT-9/EXP-M4-06: whole tiles, 16KiB-row granule — NOT flat ceil or nextpow2):
  `element_index(x,y) = (ty·cols + tx)·T² + morton_D(x & (T−1), y & (T−1))`,
  `byte_offset = element_index · bpp`. Within one tile it is plain Morton (which is why all ≤128-px
  validations passed); the tiled structure only appears once both dims exceed T. **Allocation pads each
  axis to a MULTIPLE OF T** (`padDim(d)=ceil(d/T)·T` for d≥T, `nextpow2(d)` for d<T; RT-9) — **NOT nextpow2**;
  e.g. a 1920-wide RT has cols=30 not 32, and 384²→0x90000 not 0x100000. Mip levels use the same `padDim`.
  This **supersedes the G13/G14 per-format tile table, the "pure full-texture Morton" model, AND RT-3's
  `cols=nextpow2(W)/T`** (all wrong for non-pow2 widths).
- **Mip packing** (§3): levels packed consecutively, each an independent pow2-padded Morton plane,
  floored to a 0x80-byte minimum slot (offset formula in the doc, HW-validated).
- **3D / cube / array / MSAA variants** (§1.6, EXP-0028): 3D = stacked 2D-Morton planes (not 3D
  Morton); 2DArray/Cube/CubeArray = per-layer pow2-padded Morton planes linear-stacked; 1DArray =
  linear rows; **MSAA sample-major** interleave `offset = (N·morton(x,y)+sample)·bps` (N=2,4; 8×
  unsupported). BC/ASTC/ETC = same Morton curve over **block** coordinates (§1.5).
- **Lossless compression** (§4): enabled iff **no ShaderWrite** AND image ≥ ~16×16. Allocate an
  **aux metadata buffer** = `numTexels/32` = `paddedImageBytes/(32·bpp)` (1 state byte per 8×4-texel block; = image_bytes/128 only at bpp4 — EXP-M4-07) placed **immediately
  after** the image (`secondaryVA = baseVA + paddedImageBytes`); set descriptor flags word1 bit27 /
  word3 bit31 + secondary VA (§3). Aux bytes are Morton-of-blocks ordered.

**EMULATE / route:**
- **The compressed block codec (8×4 block bit-layout) is opaque** (§4.5) — a driver can allocate +
  wire up compression (flags/aux placement/size) but must treat block *contents* as opaque, **or
  disable compression** (make the image ShaderWrite-eligible / clear the flags) to fall back to the
  plain uncompressed twiddle. See §8.

---

## 5. TBDR pipeline (`docs/pipeline/`)

**Mesa modules:** `lib/agx_tilebuffer.c`, `lib/agx_scratch.c`, the attachment/render-pass setup in
the Vulkan/Gallium layers. Configures the tile-based deferred renderer: tile size, imageblock/tile
memory, MSAA, memoryless targets, load/store actions.

**SAME as M1/M2 (reuse):**
- The overall TBDR model (a tiler (TA) phase writes a parameter buffer that the fragment (3D) phase
  consumes; load/store actions per attachment) carries over (`pipeline/README.md`).

**DIFFERENT for G17P** — read `pipeline/README.md`:
- **Fixed 32×32 tile — do NOT port the G13/G14 bpp-shrink logic** (§ "Tile size", EXP-0021): the
  tile stays 32×32 even for rgba32f+4×MSAA where the imageblock exceeds the 32 KiB tile SRAM. Encoded
  in `0x68000`: `+0x904 = 0x80000000 | (ceil(W/32)−1)`, `+0x908 = ceil(H/32)−1`.
- **Imageblock budget** (§ "Imageblock / tile memory"): each color attachment declares a 0x20-byte
  record in the tiler heap (stride 0x1000 for bgra8); budget = `Σ(tile_area · bpp · samples)` against
  **32 KiB** tile SRAM (~32 B/sample). This is the check for imageblock / programmable-blend
  feasibility. (32 KiB is per-generation — verify against `maxThreadgroupMemoryLength=32768`.)
- **MSAA** (§ "MSAA"): sample count in attachment word `+0x24` (2×/4×; bit24 count LSB, bit27
  store). Under MSAA the color descriptor relocates into the tiler heap.
- **Memoryless render targets** (§ "Memoryless"): clears `+0x24` bit27, poisons the surface
  address, shrinks the tile reservation — TBDR tile-only, no main-memory backing.
- **Tile shaders**: mid-render compute dispatch is appended inline to the render stream (§2;
  `isa/README.md` EXP-O2D). `tile_read` (`0x67/0e`) and `frag_color_store` (`0xe7/06`) are the ISA
  path (§1).

**NATIVE / userspace-emitted:**
- **Programmable MSAA sample positions** (RT-4, corrects EXP-0021) — **userspace-emittable**, written
  directly to a **client BO** (`0x100000e8000` 4× / `0x100000e0000` 2×) at **+0x40** as N `(x,y)` f32
  pairs on a 1/16 grid. **NOT kernel-managed** — do not route `ppp_multisamplectl` via the kernel.

**EMULATE / route to KERNEL** (§6):
- **Depth store-action / ZLS** — firmware-managed; route `zls_ctrl` + depth/stencil buffers.
- **Partial-render / tiler-param overflow trigger** — firmware detects overflow; no userspace knob;
  userspace supplies `partial_bg`/`partial_eot` programs.

---

## 6. Kernel interface (`docs/kernel-interface.md`)

**Mesa modules:** `lib/agx_device.c`, `lib/agx_bo.c`, `lib/agx_va.c`, `vulkan/hk_queue.c`, and the
`drm-uapi/asahi_drm.h` UAPI. The boundary contract: what userspace builds and hands down vs what the
kernel/firmware owns. (The kernel driver itself is out of scope; this is the interface note.)

**SAME as M1/M2 (reuse):**
- The **overall split**: userspace owns essentially all GPU *programming* (shaders, VDM/CDM/PPP
  streams, descriptors, layout); the kernel/firmware owns **submission** + a **small set of render-
  pass control registers** it programs on userspace's behalf (`kernel-interface.md` §1). The
  `drm_asahi` VM/Queue/Bind/Submit UAPI shape and the `drm_asahi_cmd_render`/`cmd_compute` field
  sets are the target model (§6.1). This shape is assumed identical for A18.

**DIFFERENT for G17P** — read `kernel-interface.md`:
- **Submission is a shared-memory ring + doorbell, not per-call ioctl** (§2, EXP-0009/0011): the
  IOKit call count is invariant under submit count. Work crosses as **BOs + a submit**; the ring
  producer index advances +0x58/submit; the **doorbell store is a firmware-shared-page write** (not
  an IOKit call). On Linux the natural split: userspace builds BOs + calls a submit ioctl, the
  **kernel advances the ring and rings the doorbell**.
- **Resource mapping = sel-9 (map BO → GPU VA)** (§3): in@0x38 CPU base, in@0x48 size, out@0x00 GPU
  VA (→ Linux `GEM_CREATE` + `VM_BIND`). **16 KiB pages / alignment** on all binds
  (`hardware-overview.md` §2).
- The observed **VA-space layout** (§3.2): queue-context BOs (`0x18000`/`0x58000`/`0x68000`) vs the
  resource heap (`≥0x10000000000`); the tiler parameter buffer is allocated by userspace but
  **written by the tiler HW**.

**What userspace hands the kernel** (§6.1, `drm_asahi_cmd_render` — userspace computes the value,
firmware writes the register):
- `zls_ctrl` + `depth`/`stencil` (**ZLS / depth
  store**), `isp_zls_pixels` / `isp_scissor_base` / `isp_dbias_base` / `isp_oclqry_base`,
  tilebuffer sizing (`samples`/`utile_*`/`width_px`/`height_px`), `isp_merge_upper_*`,
  `vdm_ctrl_stream_base` and `bg`/`eot`/`partial_bg`/`partial_eot` programs. The executable
  window is established at queue creation by `usc_exec_base`; its exact Apple9 mapping is
  still open (§4.5). The compute counterpart is much thinner.

**Firmware-managed items to route** (§4 — userspace does NOT emit these in the command stream):
ZLS/depth store, **RT BVH build + node format** (userspace supplies vertices +
build descriptor + an 8-byte AS VA; the GPU builds an opaque BVH), partial-render trigger,
**sparse tile residency** (page table,
§3), the **doorbell/ring advance**, the **timestamp sample-buffer** address, and mesh **UVB**
sizing. `kernel-interface.md` §6.2 has the unambiguous emit-vs-submit-vs-firmware table.

---

## 7. Capabilities — native vs emulate (`docs/capability-matrix.md` + `capability-completeness.md`)

**Mesa modules:** the native-vs-emulated boundary drives which `libagx/` emulation engines (GS/
tess/XFB compute lowering, `agx_streamout.c`) and which native paths a Vulkan/GL driver needs.
`capability-matrix.md` is the **decided** matrix; `capability-completeness.md` is the full 214-row
census (native-decoded 189 / emulated 11 / kernel-managed 4 / NOT-YET-CHARACTERIZED 10 after
EXP-0042 reopened graphics code-window/stage-selector integration).

**Native — emit a native instruction / packet / descriptor field** (`capability-matrix.md` §1;
census §1–§15):
- **Framebuffer logic ops** (all 16 boolean funcs, `0x0b` LUT), **depth clamp** (native raster
  [11:10]), **dual-source blend** (via FS epilog), **PCF / `sample_compare`** (native 2×2 hardware
  PCF, all 8 funcs), **image / texture atomics** (native, memory-family `0x67`), **matrix unit**
  (`0xcf` 8×8×8 MAC), **hybrid ray tracing** (`rt_intersect`/`rt_as_load` + compiler traversal
  loop), **mesh shading** (HW pipeline, store-based emit), **native tessellation** (`drawPatches` →
  VDM patch-dispatch record `0x40`, half-float factor buffer, ordinary post-tess VS — EXP-O2H),
  **sample positions** (userspace-emittable to a client BO `@+0x40` — RT-4), programmable blend,
  subgroup prefix-scan, float round modes, typed compare, native single-RMW atomics incl. float-add,
  format/swizzle/sRGB orthogonality.

**Emulate — HW lacks it or Metal exposes no path** (`capability-matrix.md` §2; census §16c):
- **Geometry shaders / transform feedback** → compute-emulated (VS→GS 4 sub-programs; GS-path
  streamout) — classically-Apple-absent, **not re-probed native on A18** (open, §8). **Tessellation is
  NOT in this list — it is NATIVE HW on A18 (EXP-O2H); see the native list above.** The `libagx`
  compute-tessellation stack is now only an **OPTIONAL** portable fallback.
- **64-bit integer atomics** — entirely absent from MSL (all `atomic<ulong/long>` rejected; corrects
  the earlier "min/max only") ⇒ **Vulkan int64 atomics must be emulated** (census §4, EXP-O2D).
- **Float atomic min/max** — not exposed (only float atomic add is native) → emulate (int-bitcast
  CAS loop).
- **int8 cooperative matrix** — `0xcf` supports fp16/fp32/bf16 only; integer types rejected →
  emulate.
- **Arbitrary sampler border color** — 3-preset field only → emulate (two-sampler-plane trick, §3).
- **Large-argument trig** — software Payne-Hanek range reduction (§1, §8).
- **Cull distance** (MSL has clip only) and **polygon-point fill** (Metal fill/lines only) are
  **Metal-unreachable** → emulate (`cmdstream/README.md` "Geometry-output"; §8).

**Kernel/firmware-managed** (`capability-matrix.md` §3; §6): ZLS/depth store, RT BVH build, partial
render, and scissor. Graphics stage selection is an **open queue/userspace mapping**, not proven
kernel-owned (EXP-0042). *(Sample positions are **not** kernel-managed — RT-4:
userspace-emittable to a client BO `@+0x40`.)*

Use `capability-completeness.md` §16 to see **which Metal-exposed features are still NOT-YET-
CHARACTERIZED** (tile-shader dispatch encoding — now decoded EXP-O2D, RT completion tail, sampler-
heap packing, etc.) before committing to native-vs-emulate for a corner feature. The matrix's own §4
"Unknown/untested" list is the honest set of things to probe before relying on them.

---

## 8. Gaps a driver author must know (honestly-open items + the fallback for each)

These are the items `docs/` flags as **not fully closed**. Each has a driver fallback so the port is
never blocked — cite the doc section rather than guessing.

**Undecoded / opaque hardware formats**
- **Lossless compression block codec** (`tiling/README.md` §4.5): the 8×4-block bit-layout and the
  exact state-byte meanings are **opaque** (per-generation, HW-internal — not a Metal-exposed
  capability). **Fallback:** allocate + wire the aux buffer and flags (§4) treating block *contents*
  as opaque, **or disable compression** (ShaderWrite-eligible / clear the flags) and use the plain
  uncompressed twiddle. Never blocks correctness.
- **RT BVH node format** (`isa/README.md` EXP-0023; `kernel-interface.md` §4.1): firmware-owned by
  design. **Fallback:** supply vertices + build descriptor + an AS VA; treat the built structure as
  opaque (the *traversal* ISA is native).

**Operand sub-fields marked ⏳ (byte-diff-inferred, not yet HW-round-tripped)** — render as
reserved/`<zero>` in `agx3.xml` and tighten as decoded (`ROADMAP.md` "Final ISA-consolidation"):
- Integer source-register exact widths and the bitwise/shift/compare operand sub-fields
  (`isa/README.md` "Integer ALU"); the **float GPR-vs-uniform per-source mode bits** are byte-diff-
  inferred, not splice-validated (`isa/README.md` "Machine model").
- **Texture array/3D/cube/MSAA index-operand bit positions** and result/coord register decode
  (`isa/README.md` "Texture variants" ⏳); **`pixel_order` (ROG) acquire/release** bytes are byte-
  diff inferred (`isa/README.md` "Fragment ISA").
- **Fallback:** the *principal* encoding of every one of these is decoded and HW-validated (the
  family works); single-resource / common-case shaders always encode slot 0, so a first driver runs.
  Validate the sub-field before shipping bindless/multi-dim variants.

**Metal-unreachable features (Vulkan/GL want them; Metal can't provoke them → not HW-confirmable
here)**
- **Cull distance, polygon-point fill, a *custom* primitive-restart index, anisotropy >16×, wide/
  smooth lines, conditional rendering** (`capability-matrix.md` §4; `capability-completeness.md`
  §16c). Spare HW encodings sometimes exist (e.g. restart-index field at VDM `+0x68`; aniso field
  encodes 128×) but Metal always drives the fixed value. **Fallback:** emulate in the Vulkan/GL
  driver (as Mesa does today), or probe the spare encoding on hardware before relying on it.
- **GS / transform-feedback A18-native status** is **not independently re-probed** — classified
  emulate by the M1/M2 default (`capability-matrix.md` §4). **Fallback:** keep the compute-emulation
  stack; a probe could retire it (mesh shading is the plausible native amplification path).
  **Tessellation is NO LONGER open — EXP-O2H proved it NATIVE HW** (VDM patch-dispatch `0x40`,
  half-float factors, ordinary post-tess VS); the compute-tessellation path is an optional fallback.

**Microarchitectural claims with no emittable encoding (document, do not gate)** —
`capability-completeness.md` §16b: **Dynamic Caching dynamic behavior**, **2× ALU dual-issue**,
**flexible unified on-chip memory**, **RT reorder stage**, and the **full occupancy/latency curve**.
These are observable only via throughput/occupancy microbenchmarks + Xcode counters. **Fallback:**
use the *static* model that **is** decoded (96 GPRs, spill threshold, peak-pressure occupancy tier) — it
is correct; the dynamic curves are performance-only (wrong = slow, not broken).

**Kernel-side open items** (`kernel-interface.md` §8): the exact CPU→GPU doorbell store, the
3-segment (load/render/store) attachment grammar + store-program id `0x6f`, and the raw accel-node
config values (`num_gps`/`num_frags`/`is_sksm`) are firmware/kernel questions to close with the
kernel team — they do not block userspace bring-up.

---

## Provenance

Synthesis of the whole `docs/` tree: `isa/README.md` + `isa/encoding-tables.md` (EXP-0001–0038,
O2C/O2D), `cmdstream/README.md` (EXP-0009/0011/0014/0019/0024/0027/0030, O2A/O2D),
`descriptors/README.md` + `descriptors/format-table.md` (EXP-0015/0017/0028, O2B), `tiling/README.md`
(EXP-0017/0028), `pipeline/README.md` (EXP-0021), `kernel-interface.md`, `capability-matrix.md`,
`capability-completeness.md`, `hardware-overview.md` (EXP-0002), and `mesa-userspace-requirements.md`
(the Mesa `src/asahi` module survey). No new experiment; no Apple binary introspected. This document
is navigational — it cites the owning doc section for every hardware fact rather than restating the
encoding.

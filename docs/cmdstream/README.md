# A18 Pro (G17P) Command Submission & Control Stream

Clean-room documentation of how userspace hands GPU work to the kernel, and the control-stream
structures it builds. Learned by **black-box data tracing** (DATA-TRACE) of our *own* Metal
programs via a DYLD IOKit interposer (`tools/iotrace/`) — command buffers/descriptors are
non-copyrightable hardware data. No Apple binary was disassembled. See `../../CLAUDE.md`.

> **Status: foundation established (EXP-0009).** The submission *mechanism* and the userspace↔kernel
> IOKit interface are mapped; the individual control-stream structures are located and partially
> correlated, with full bit-level decode deferred to follow-up cmdstream experiments.

## Submission model — shared-memory + doorbell (NOT per-call ioctl)
Modern macOS 26 Metal does **not** issue one ioctl per submit (unlike the M1-era 2021
`SUBMIT_COMMAND_BUFFERS` selector). Evidence: the IOKit call count is **invariant** under the
number of submits (compute: 49 calls whether 1/3/5 submits; draw: 58), while each submit
demonstrably ran (correct output each time). Work is encoded into ordinary userspace VM buffers
that are registered into the GPU address space; submission is via a shared-memory ring + doorbell
(ring BO + doorbell write proven to exist, exact location pending — see Open items).

## Userspace↔kernel IOKit interface (G17P)
Userspace opens two user clients: **`IOSurfaceRoot`** and **`AGXAcceleratorG17P`**. All GPU work is
`IOConnectCall*` on the AGX connection. Selectors identified:

| selector | role | notable payload |
|---|---|---|
| `0x8` | create queue | — |
| `0x7` | one-time setup (1040-byte struct in) | candidate for ring/doorbell setup |
| **`9`** | **map resource (register BO into GPU VM)** | in@0x38 = CPU base, in@0x48 = size, **out@0x00 = GPU VA** (HW-confirmed: returned `0x10000030000` = our buffer's `gpuAddress`) |
| `0x11` | completion/notify queue | candidate for doorbell/notify |

A compute dispatch makes ~30 sel-9 maps; a draw ~39 plus a second IOSurface map. No graphics-specific
"submit" selector exists — draw uses the same shape as compute.

## ✅ Compute launch (CDM) descriptor — decoded (EXP-0011)
BO `gpu_va 0x100000b0000` is a stream of **0x2c-byte records** (one per dispatch) + a
`0x40000000` terminator. Per-record fields (grid/tg HW-validated by single-word diffs):

| offset | field | notes |
|---|---|---|
| `+0x00` | shader config/register word | e.g. `0x00080000`→`0x00880000` for a register-heavy shader ⏳ |
| `+0x08` | **shader-code pointer = shaderVA >> 6** | 64-byte units. HW-confirmed: shaders at 0x90000/0x90100 → `0x2400`/`0x2404` (Δ=4) |
| `+0x10/+0x14/+0x18` | grid x / y / z | **in threads**, not threadgroups (`dispatchThreadgroups(2)×32` ≡ `dispatchThreads(64)`) |
| `+0x1c/+0x20/+0x24` | threadgroup x / y / z | |

The arg-buffer pointer is **not** in this record — binding flows via the argument buffer, whose VA
lives in the uniform/USC BO (`0x10000000000`). ⏳ threadgroup-memory-size field is elsewhere (not here).

## ✅ Argument buffer (Tier-2) — decoded (EXP-0011)
BO `gpu_va 0x100000e0000`, resource table at **+0x14a0**, **8 bytes/slot** in binding order:
- **buffers** = inline 8-byte GPU VA (HW-validated for 1/2/4/8 buffers).
- **textures / samplers** = 8-byte pointer to a descriptor block appended in the same BO. Raw 32-byte
  texture descriptor + sampler descriptor captured for `../descriptors/` (Phase 3 seed).

## Shader BO (EXP-0011)
Captured code BO = `[main][14-byte constant-program stub 03 00 07 00 02 00 00 00 60 00 0e 00 00 00]`,
ending in `0e` stop; no header. Structurally validated against `shdump` (the stub matches
`_agc.main.constant_program`'s head). Note a **codegen difference between API paths**:
`newComputePipelineStateWithFunction:` inlines the arg-load preamble into main (~182 B) while the
binary-archive `_agc.main` that `shdump` extracts is lean (~56 B) — same semantics, different framing.

## Submission ring / doorbell (partial, EXP-0011)
No per-submit mapping syscalls (confirms ring+doorbell). The ring lives in shared memory
(~`gpu_va 0x10000050000`): a **producer index increments by 0x58 bytes/submit** with fixed-size
completion records at the same cadence. The exact CPU→GPU doorbell store is **not** an IOKit/mach-vm
call — likely a store into a firmware-shared page + barrier (invisible to this interposer). sel `0x7`'s
1040-byte struct was reclassified: it is the **executable-path string**, not ring config.

## Graphics (draw) command stream — first pass (EXP-0014)
A draw registers ~39 BOs (vs ~13 for compute) via the **same** shared-mem+doorbell path (no
graphics-specific submit selector). Two channel types are involved: **TA** (tiler/vertex) and
**3D** (fragment). Control BOs by GPU VA:

| GPU VA | role |
|---|---|
| `0x18000` (fw ctx) | **VDM / tiler draw stream (TA)** |
| `0x58000` (fw ctx) | **3D fixed-function state pool** (depth/stencil/blend/raster packets) |
| `0x68000` (fw ctx) | **viewport / tiling context** |
| `0x10000000000` | shader code (VS + FS; 6 constant-program stubs) |
| `0x10000100000` | vertex-attribute table |
| `0x10000110000` | **3D attachment (render-target) descriptor** |
| `0x10000130000` | **USC shader-binding program** |

- **TA** binds VDM `0x18000` + viewport `0x68000` + attr table; **3D** binds attachment `0x110000` + FF-state `0x58000`.
- **Shader binding:** unlike compute's single `shaderVA>>6`, VS/FS are bound **indirectly through USC
  bind-pairs** in the VDM (changing either shader touches `{0x10000000000, 0x10000130000}`). ⏳ the exact
  graphics shader-entry word inside the USC blocks is not yet decoded.
- **VDM draw record:** header (state-size @+0x0c) + USC bind-pairs (control-word, addr) + primitive word:
  **primitive type @+0x65** (point 0x00, line 0x01, tri 0x06, strip 0x09), **vertexCount @+0x68**,
  **instanceCount @+0x6c**. Indexed draws switch opcode `0x61c4→0x61f2` and add **index-buffer VA @+0x70**
  (HW-correlated) + index count @+0x74.
- **Viewport** = 4 transform floats @ `0x68000+0x910` (`{w/2, h/2, w/2, −h/2}` — Y-flip) + depth range
  @+0x920/+0x924; pointed to from the VDM.
- **Attachment descriptor** (`0x10000110000`): **pixel format** byte @+0x22 (BGRA8=0x0a, RGBA8=0x88);
  **clear color** = 4 floats @+0x170, in chained 0x300-byte segments (⏳ load/render/store meaning).
- **Fixed-function state** (`0x58000`): raster line/point @+0x54, depth @+0x38, blend @+0x08 — bound via
  the VDM USC-pairs. ⏳ per-packet bit decode is a follow-up.

## Graphics fixed-function state packets & USC bind grammar (EXP-0019)

### ⚠ Blend is programmable (compiled into the fragment shader), not a fixed-function packet
The single most important structural fact for a Mesa port: **blend factors/ops are lowered into the
fragment shader's blend microprogram in the shader-code BO `0x10000000000`**, not emitted as a
fixed-function LUT (changing a blend factor rewrites ~40 shader words; `0x58000` barely moves). This is
Apple's TBDR programmable-blend model — the driver **must compile blend state into fragment shaders**
(as Asahi does for M1/M2). `0x58000` keeps only: color-write-mask (R=bit0…A=bit3, reverse of Metal),
blend-class/constant-color/enable flags. Dual-source blend and framebuffer logic ops both work through
this shader path (the ISA has the 16-function bitwise LUT, EXP-0013). *(The blend microprogram is
compiler-generated code — located, deliberately NOT disassembled, per CLAUDE.md clean-room rule 5.)*

### ✅ Depth/stencil packet (`0x58000`, HW-validated)
Per-face blocks: FRONT depth `+0x38` / stencil `+0x3c`, BACK depth `+0x40` / stencil `+0x44`, flags `+0x34`.
- **Depth word:** stencil-ref[7:0], depth-write-DISABLE bit21, compare[26:24].
- **Stencil word:** write-mask[7:0], read-mask[15:8], pass-op[18:16], zfail-op[21:19], sfail-op[24:22], compare[27:25].
- **Compare 0–7** = never/less/equal/lessEqual/greater/notEqual/greaterEqual/always.
- **Stencil-op 0–7** = keep/zero/replace/incrClamp/decrClamp/invert/incrWrap/decrWrap.

### ✅ Rasterizer packet (`0x58000+0x70`, HW-validated)
cull[1:0] = none/front/back; winding bit16 = CW/CCW; **depth clip-vs-clamp = native 2-bit field [11:10]**
(depth clamp is HW-supported — good for Vulkan); polygon line-fill = raster nibble `0x5` + flags bit26;
depth bias: enable = flags `+0x34` bit17, constant/slope/clamp = 3 floats in the tiler-param region
(`…+0x2a8000`).

### USC bind grammar + graphics shader binding (EXP-0019, resolved EXP-0024)
The VDM (`0x18000`) holds a **fixed 8-pair template** (control-word, address) into `0x58000`/viewport/
context — invariant under state changes (only the `+0x0c` length word grows, see PPP below).

**✅ How graphics binds shaders (EXP-0024) — there is NO `shaderVA>>N` word in userspace.** Unlike compute
(CDM `+0x08 = shaderVA>>6`), a draw does **not** carry a shader pointer anywhere in the client command
stream (exhaustive delta-search: growing FS moves the VS code entry +0x80, and the *only* words that track
it are **sizes**, never an 8-byte pointer). Instead:
- The **code BO `0x10000000000`** is a self-describing walk of `[size-header][machine-code]` blocks,
  walked from the BO base: `+0x00` = `0x340` (offset to first block), `+0x340` = FS(#1) block size,
  `+0x500` = VS(#2) size; stage order `[helpers][FS][VS]…`. Code sizes also mirror at `0x58000+0x08`
  (FS code size) and `0x10000000000+0x340` (FS block header).
- The **USC program `0x10000130000`** holds three `0x240`-byte per-stage **uniform-preamble programs**
  (block0 ≡ block1 = vertex, block2 = fragment), each led by config `0x008800XX` (XX = stage×0x0c);
  `+0x10/+0x18/+0x250/+0x490` = uniform-data pointers, `+0x14…` = per-shader slot ids.
- **Driver guidance:** emit compiled code as sized blocks + emit the USC uniform-preamble programs. The
  **code-BO-base → firmware handoff is a userspace↔kernel item** (not a client descriptor — flag for the
  kernel team, see `kernel-interface`).

### ✅ PPP fixed-function header / emission order (EXP-0024) — length word, not a present mask
There is **no present-bit mask**. The 8 VDM bind-pairs and pool layout are **fixed**; presence is a
**monotonic length word**: VDM `0x18000+0x0c` and pool `0x58000+0x14` both grow **+0x400** only when a
depth/stencil block is appended (blend/cull alone → 0 VDM diff). **Per-group presence = enable bits inside
each packet**: depth `+0x34` bit18 / `+0x38`; stencil `+0x34` bits[19:18] / `+0x3c`; blend `+0x18`,`+0x50`;
cull `+0x70`. So a driver assembles state by writing packets + toggling their enable bits, and bumps the
length word when the depth/stencil block is present.

### ✅ Compute config word + threadgroup-memory size (EXP-0024)
- **CDM config word** (`0x100000b0000+0x00`) = `0x00080000` (bit19 always set) + **bit23 = register/occupancy
  tier** (EXP-0020); atomics/barriers/simd/tgmem do **not** touch it.
- **Threadgroup (shared) memory size** is in the **shader BO `0x10000090000`**, not the CDM:
  **`field = (tgmem_bytes << 2) | 0x80`** (HW-validated 256→32768 B) — static at `+0x40`, dynamic at
  `+0x4c` bits[31:16].

### Tooling note (macOS 26)
The `iotrace` interposer **must be built `-arch arm64e`** or captures silently fail; shader size-probes
need a non-zero coefficient (≈1e-9) to survive dead-code elimination.

## Completeness: indirect commands, occlusion queries, timestamps (EXP-0027)
- **Indirect draw** (`drawPrimitives…indirectBuffer:`): VDM opcode changes **`0x61c4→0x6404`** (non-indexed) /
  **`0x61f2→0x6432`** (indexed); inline counts are replaced by an 8-byte pointer to the public
  `MTLDraw[Indexed]PrimitivesIndirectArguments` struct — non-indexed ptr at VDM `+0x68`(hi32)/`+0x6c`(lo32)
  (stored **high32-then-low32**); indexed keeps index-buf ptr inline at `+0x70`, args ptr at `+0x74`/`+0x78`.
- **Indirect dispatch:** because the CDM grid is in *threads* but indirect args give *threadgroups*, Metal
  injects a **2nd CDM record + a grid-setup helper shader** to multiply `threadgroups × threadsPerThreadgroup`
  (args VA staged at `0x10000080000+0xb0`). **A Mesa driver must replicate this multiply.**
- **Full ICB** (`executeCommandsInBuffer:`): each command expands to an inline state-block + draw (same
  `0x61c4`, inline vertexCount); header `+0x04` = command count. (Distinct from the args-pointer form above.)
- **Occlusion query:** result-buffer base pointer at `0x10000100000+0x00`; per-draw **mode = bit14 of
  `0x58000+0x8c`** (Boolean=1 writes 1 / Counting=0 writes exact passed-sample count, both u64); per-draw
  **offset = `0x58000+0xa0` = byteOffset<<14**. Per-tile→total summation is firmware-managed.
- **GPU timestamps:** format = **uint64 nanoseconds, `timestampPeriod = 1.0`** (cpu==gpu clock). ⚠ **Only
  stage-boundary sampling is supported** — dispatch- and draw-boundary timestamps read all-zero (a Vulkan
  emulation flag). Sample-buffer address is firmware/kernel-managed (see `../kernel-interface.md`).
- **MSAA** (HW-PROBE): N independent samples with 1:1 sample-id ordering (`read(coord,s)` = sample s);
  resolve = arithmetic average; physical interleave is on-chip tile SRAM (not byte-visible).

## Mesh/object shading submission (EXP-0030)
A mesh draw is **not a new work type** — it reuses the graphics path (same `IOSurfaceRoot` +
`AGXAcceleratorG17P` clients, same selectors, ~39 sel-9 maps; **no CDM launch descriptor** → a single
unified graphics submit, not compute+draw). It builds the same tiler/VDM stream at `0x18000` but replaces
the draw's `0x61c4` primitive record with a **mesh-grid-dispatch record (`0x70000600` + grid dims)**; same
3D state (`0x58000`) + viewport (`0x68000`), plus a **mesh-only dispatch-descriptor BO `0x100000f8000`**.
The mesh-output **UVB buffer** is a driver/firmware-allocated intermediate (tiler-heap + `0x100000f8000`),
reached via USC/uniform binding like the vertex-shader **UVS** varying buffer — **not user-visible**; its
sizing and the UVB→rasterizer wiring are a **kernel-interface** item (see `../kernel-interface.md`).

## Geometry-output pipeline (EXP-O2A)
- **Multiple viewports** (`0x68000`): count word `+0x900 = ((count-1)<<12)|0x0C00` (max 16); a per-viewport
  control-word header; then a **6-float / 0x18-byte per-viewport transform array** (the single-viewport block
  `+0x910`, arrayed). Index selected by the VS `[[viewport_array_index]]` output.
- **PPP output-select word `0x58000+0x20`** (which shader outputs are live): **bits[7:0] = clip-distance plane
  mask** (max 8 planes), **bit18 = point_size**, **bit19 = viewport_array_index**. Clip-distance = a shader-output
  varying + this mask; point-size *value* is shader-driven (no descriptor field).
- **Primitive restart** (indexed VDM record `0x18000`): **cut/restart index at `+0x68` = all-ones of the index
  width** (0xffff / 0xffffffff); opcode `+0x6c` bit0=strip/bit1=u32; count `+0x74`, extent-dwords-1 `+0x80`,
  idxBuf VA `+0x70`. **No separate enable bit.**
- **Alpha-to-coverage** = shader-lowered (FS epilog) + FF bits `0x58000+0x18` bit0 (MSAA-only) and `+0x50`
  bits[30,26]. **Alpha-to-one has no FF field** — realized entirely in the FS epilog (output alpha → 1.0).
- **Kernel-managed:** the multi-scissor rectangle array is in **no** client BO — it routes via the `isp_scissor`
  submit param (see `../kernel-interface.md`); only the scissor *enable* bit (`0x58000+0x34` bit16) + tile-grid
  clamp (`0x68000+0x904/908`) are client-side.
- **Metal-unreachable → emulate:** cull distance (MSL has clip only), polygon-point fill (fill/lines only), a
  *custom* restart index (HW field exists at `+0x68` but Metal always uses all-ones).

## Open items (next cmdstream experiments)
- Compute: decode `+0x00` config/register word; find the threadgroup-memory-size field.
- Graphics: USC bind-pair grammar + graphics shader-entry word; per-packet bit decode of depth/stencil/
  blend/raster; attachment dims/stride + the 3-segment (load/render/store) meaning; **tiler parameter
  buffer** (`0x10000088000/140000`); ZLS / partial-render (restructures on `--depth`).
- Texture/sampler descriptor bit layouts → `../descriptors/`.

Source: `experiments/EXP-0009-iotrace-bringup/`. Tool: `tools/iotrace/`.

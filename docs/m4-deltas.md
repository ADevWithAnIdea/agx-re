# Apple M4 (Mac16,10) vs A18 Pro (G17P) — GPU userspace deltas

**Purpose:** This is the **delta layer** for the Apple **M4** (local Mac Mini M4, 10-core GPU,
Metal 4). The A18 Pro docs in this directory are the baseline; **A18 docs + this delta file =
enough to implement an M4 userspace GPU driver.** Each subsystem below is marked:
- **✅ IDENTICAL** — validated same as A18 (with the experiment that showed it), or
- **⚠ DELTA** — differs from A18 (exact difference + bit-level detail + experiment), or
- **⏳ PENDING** — not yet validated on M4.

Method is the same clean-room loop as the A18 work, run on the **local M4 host** (OWN-SHADER /
DATA-TRACE / HW-PROBE; no Apple binary disassembled). Validation experiments live in
`experiments/EXP-M4-*/`.

---

## 0. Device identity & configuration
| | A18 Pro | **M4** |
|---|---|---|
| SoC / model | T8140 | **Mac16,10** |
| GPU codename (`architecture.name`) | `applegpu_g17p` | **`applegpu_g16g`** (both Apple9; note G16G < G17P — the M4 GPU predates the A18 Pro yet shares the family) |
| Metal feature family | Apple9 | **Apple9** (Metal 4) |
| **GPU cores** | 5 (of 6, one fused) | **⚠ 10** |
| threadExecutionWidth (SIMD) | 32 | **✅ 32** |
| maxThreadsPerThreadgroup | 1024 | **✅ 1024** |
| maxThreadgroupMemoryLength | 32768 | **✅ 32768** |
| sparse tile / page size | 16384 | **✅ 16384** |
| argument-buffer / RW-texture tier | Tier 2 / Tier 2 | **✅ Tier 2 / Tier 2** |
| **maxBufferLength** | 4.000 GiB (hard `0x1_0000_0000`) | **⚠ 8.88 GiB** (9534832640) — M4 allows buffers > 4 GiB |
| recommendedMaxWorkingSetSize / RAM | 5.33 GiB / 8 GiB | 11.84 GiB / **16 GiB** |
| supportsFamily (max) | Apple9 + Metal4 | **✅ Apple9 + Metal4** (no Apple10/Metal5) |

The core count (10 vs 5) is a throughput/config delta, not an architectural one; it affects
occupancy/dispatch sizing but not encodings. (Any driver-visible core-count field is a
kernel-interface item — see §7.)

## 1. Shader ISA — ✅ IDENTICAL (EXP-M4-01)
M4 runs the same AGX Apple9 ISA. All 57 A18-corpus shaders compile on M4; the A18 DB
disassembles them at **88.6% tokens / 91.5% bytes** (same as A18), matching **including the
red-team corrections** (byte+5 memory index, `scoreboard_fence`, `imad` byte+2=0x56). Encoding
byte-diff M4-vs-A18 and the undecoded-group closure are in progress (EXP-M4-01). No ISA delta
found so far.

## 2. Machine model — ⏳ PENDING
96 GPRs / halves-2-per-GPR / uniform file / async HW-interlock / SR table — to be re-validated by
splice-run on M4 (expected identical; A18 baseline in `isa/README.md`).

## 3. Command stream (CDM/VDM/USC/state) — ✅ IDENTICAL (EXP-M4-03)
`iotrace` works on the M4 host (interposes IOKit, SIP disabled). Every cmdstream field byte-identical to A18:
CDM compute (config `0x00080000`@+0x00, shaderVA>>6@+0x08, grid-threads@+0x10, effective-tg@+0x1c), VDM draw
(prim@+0x65, opcode 0x61c4@+0x66, vertexCount@+0x68, instanceCount@+0x6c; **indexed shifts identically** —
0x61f2@+0x6e, indexCount@+0x74, instanceCount@+0x78), USC (**sampler stride 0x20**, `num_samplers=(term−samp)/0x20` —
RT-2a fix holds), state packets (depth@+0x38, stencil@+0x3c, raster@+0x70, PPP-output@+0x20, **PPP length +0x400
bump**), indirect (0x6404/0x6432), occlusion (bit14 @0x58000+0x8c), mesh (0x70000600), native tessellation (VDM
record high-byte 0x40, domain@+0x8c). `cmdstream/README.md` applies unchanged. *(Inferred-identical, not re-run:
u32-index opcode 0x61f4, timestamps.)*

## 4. Resource descriptors — ✅ IDENTICAL (EXP-M4-04)
Texture (32B — byte0 type/chanArr, byte1=numtype<<5|sizeclass, swizzle word0[16:27], **14-bit dims confirmed to
16384**: 8192→0x1fff/16384→0x3fff, base VA>>4, sRGB word3.b12, mip/MS), sampler (8B — all address modes/filters/
aniso/lod/3 border presets/8 compare funcs), PBE/storage-image (two-descriptor read_write; M4 even validates the
A18-*inferred* width-high field word1[0:5]), format→code rule — **all byte-identical**. `descriptors/` applies unchanged.

## 5. Texture tiling & compression — ✅ IDENTICAL + 1 refinement (EXP-M4-04)
Tiled Morton (T=64 bpp≤4 / 32 bpp≥8), cols=ceil(W/T), mult-of-T padding, mip (384²→0xcd600 exact), compression
(≥16×16 threshold, aux=image/128, secondaryVA=base+paddedImageBytes, ShaderWrite **and PixelFormatView** disable it)
— all reproduce with 0 mismatch, incl. the decisive non-pow2-tile widths. **Refinement M4 surfaced (improves the A18
doc):** for **bpp-8** the tile column count must be **even** (`cols=round_up_even(ceil(W/T))`), because a Morton tile is
0x2000 B at bpp8 vs 0x4000 B at bpp4/16 → the tile-row stride is **16-KiB-aligned**. A18 never probed bpp-8 non-pow2
widths (where it's a no-op), so this was latent; now folded into `tiling/README.md §1.1/§1.4`. Likely general AGX.

## 6. TBDR / pipeline — ✅ IDENTICAL (EXP-M4-03)
Tile **32×32 fixed** (0x68000 +0x904/+0x908 = ceil(W/32)−1), MSAA count byte3=0x09@+0x24, **userspace sample
positions @0x100000e8000+0x40** (default D3D + custom decode exact — RT-4 fix holds), memoryless poison
`0x0eeee000`, per-attachment 0x20-stride tile-memory records. `pipeline/README.md` applies unchanged.
**10-core effect: NONE in userspace** — no cmdstream/pipeline field encodes/scales with core count; the tiler
geometry/parameter heaps vary in size but are firmware/kernel-managed (below the userspace boundary).

## 7. Kernel interface — ✅ mostly IDENTICAL (EXP-M4-03) + 2 per-part deltas
Same shared-mem ring + doorbell submission, same `IOSurfaceRoot`, same selectors, same **sel-9 map-resource→GPU-VA**
ABI. **Deltas a driver must handle per part:** (1) the **AGX user-client class name is `AGXAcceleratorG16G`** (vs
`AGXAcceleratorG17P` on A18) — match by part; (2) the config the userspace/kernel must know differs — **10 GPU cores**
(vs 5) and **maxBufferLength ~8.88 GiB** (vs hard 4 GiB) — query the device, don't hard-code. `kernel-interface.md`
otherwise applies. (Firmware-managed heap sizes scale with the part but stay below the userspace boundary.)

## 8. Capabilities — ✅ IDENTICAL (EXP-M4-02)
The M4 and A18 Pro have the **identical Metal/MSL capability envelope — zero capability deltas.** All 32 MSL
accept/reject probes match: int8/int32 cooperative-matrix REJECTED, all 64-bit atomics REJECTED, float atomic-min
REJECTED, MSL `printf` REJECTED (os_log path), only 3 sampler border presets; native (compile): bf16/fp16/fp32
`simdgroup_matrix` 8×8, RT intersector/inline-query/custom+`ray_data`, mesh+object pipeline, post-tessellation
`[[patch]]`, quad/simd scan/shuffle/ballot, texture atomics, os_log, Metal-4 `<metal_tensor>`/MPP (both parts).
Device caps identical (arg-buffer Tier 2, RW-texture Tier 2, RT+motionBlur, funcPtrs, dynLibs, 32-bit-float
filter/MSAA, BC, pull-model, barycentric, programmable sample positions, raster-order-groups; depth24stencil8 = NO).
So the A18 `capability-matrix.md` / `capability-completeness.md` (189 native / 11 emulated / 5 kernel / 9 NYC)
**apply unchanged to the M4.** Only capacity/config differs (see §0): 10 cores, maxBufferLength > 4 GiB, 16 GiB RAM.

---

## Delta summary (running)
| Subsystem | Status |
|---|---|
| Device config | ⚠ 10 cores (vs 5); maxBufferLength 8.88 GiB (vs 4 GiB); codename g16g |
| Capabilities | ✅ identical (EXP-M4-02) — zero capability deltas |
| ISA | ✅ identical (EXP-M4-01) |
| Command stream | ✅ identical (EXP-M4-03) |
| TBDR / pipeline | ✅ identical (EXP-M4-03) |
| Kernel interface | ✅ identical except user-client class `AGXAcceleratorG16G` + config (10 cores, buf>4GiB) |
| Resource descriptors | ✅ identical (EXP-M4-04) |
| Tiling & compression | ✅ identical + bpp8 even-column refinement (EXP-M4-04, improves A18 doc) |
| Machine model | ⏳ validating |

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

## 1. Shader ISA — ✅ IDENTICAL (EXP-M4-01/10/12)
M4 runs the same AGX Apple9 ISA. All 57 A18-corpus shaders compile on M4; the A18 DB disassembles
them at **100.0% byte coverage — 0 undecoded regions, 0 undecoded byte0 groups** (EXP-M4-12 drove
the census from 97.4% to complete; round-trip suite ALL PASS incl. the whole-program walk with 0
leftover bytes). **No ISA delta** — every encoding matches A18, and every coverage-sweep correction
(high-register `(reg<<1)|is32`, saturate = native byte+7 bit1, integer-immediate inline ≥65536,
device_store byte+8 inert, +3 non-2D texture read codes) applies to BOTH parts (they were A18-doc
gaps, not M4 differences).

The final residue (the "last 2.6%") closed in EXP-M4-12 was **entirely length-rule gaps and 2-byte
over-reads, not unknown opcodes** — closed by isolating each mystery op in its own single-op shader
and reading its true length from anchored bracketing. Headline families: the transcendental residue
is only the **sin/cos argument range-reduction** (exp2/log2/exp/log/pow/sqrt/rsqrt are clean in
isolation); the big texture desyncs were one mis-lengthed `0x17` coordinate-projection setup (→12B)
and a `0x2e` coord transform (→12B); the `r_blend_f` residue was **not** Apple's blend microprogram
(a cmdstream artifact absent from the shader corpus) but our own shader's tilebuffer-unpack + iter +
float-accumulate ops (fragment `0x17` unpack corrected 10→8B). One prior fact was corrected:
`unpack_convert` is **8 bytes** (EXP-0033 recorded 10 by a 2-byte over-read; HW readback had
validated the value, not the length). See `experiments/EXP-M4-12-isa-residue-closure/`.

Every instruction byte is now tokenized with a known length and byte0-group family; ~79% carry a
full decode descriptor (mnemonic), the remainder are family-labeled "length-only" tokens whose
operand bit-fields are deliberately left undecoded where decoding them would amount to transcribing
a compiler-generated sequence (clean-room rule 5) — chiefly the SFU range-reduction immediate words.

## 2. Machine model — ✅ IDENTICAL (EXP-M4-11)
Splice-validated on M4, all identical to A18: **96 GPRs, hard boundary** (r96 memory-index →
CMDBUF_ERROR, no mod-64 aliasing; metadata caps at exactly 96; spill/scratch numbers match),
halves 2/GPR (64→f0=50), **both uniform-source encodings** (srcB byte+2bit4+byte+5bit1, srcA bit39),
occupancy 2-tier by peak register pressure, **SR table** (tpig 0xa0/simd_lane 0x82/vertex_id 0xdd/
instance_id 0xd8/front_facing 0xc5/…), in-shader software vertex fetch, and **async = HW register
interlock** (dependent chains correct with 0 scoreboard ops; >8 loads in flight). `isa/README.md`
machine-model section applies unchanged.

## 3. Command stream (CDM/VDM/USC/state) — ✅ IDENTICAL (EXP-M4-03)
`iotrace` works on the M4 host (interposes IOKit, SIP disabled). Every cmdstream field byte-identical to A18:
CDM compute (config `0x00080000`@+0x00, shaderVA>>6@+0x08, grid-threads@+0x10, effective-tg@+0x1c), VDM draw
(prim@+0x65, opcode 0x61c4@+0x66, vertexCount@+0x68, instanceCount@+0x6c; **indexed shifts identically** —
0x61f2@+0x6e, indexCount@+0x74, instanceCount@+0x78), USC (**sampler stride 0x20**, `num_samplers=(term−samp)/0x20` —
RT-2a fix holds), state packets (depth@+0x38, stencil@+0x3c, raster@+0x70, PPP-output@+0x20, **PPP length +0x400
bump**), indirect (0x6404/0x6432), occlusion (bit14 @0x58000+0x8c), mesh (0x70000600), native tessellation (VDM
record high-byte 0x40, domain@+0x8c). `cmdstream/README.md` applies unchanged. u32-index opcode `0x61f4` and stage-boundary timestamps (period 1.0) are now **HW-run on M4** (EXP-M4-11), identical.

## 4. Resource descriptors — ✅ IDENTICAL (EXP-M4-04)
Texture (32B — byte0 type/chanArr, byte1=numtype<<5|sizeclass, swizzle word0[16:27], **14-bit dims confirmed to
16384**: 8192→0x1fff/16384→0x3fff, base VA>>4, sRGB word3.b12, mip/MS), sampler (8B — all address modes/filters/
aniso/lod/3 border presets/8 compare funcs), PBE/storage-image (two-descriptor read_write; M4 even validates the
A18-*inferred* width-high field word1[0:5]), format→code rule — **all byte-identical**. `descriptors/` applies unchanged.

## 5. Texture tiling & compression — ✅ IDENTICAL + 1 refinement (EXP-M4-04)
Tiled Morton (T=64 bpp≤4 / 32 bpp≥8), cols=ceil(W/T), mult-of-T padding, mip (384²→0xcd600 exact), compression
(≥16×16 threshold, **aux = numTexels/32 = paddedImageBytes/(32·bpp)** — EXP-M4-07 CORRECTS the old image_bytes/128 which over-counts 2×/4× at bpp8/16; secondaryVA=base+paddedImageBytes; ShaderWrite **and PixelFormatView** disable it)
— all reproduce with 0 mismatch, incl. the decisive non-pow2-tile widths. **Refinement M4 surfaced, then CROSS-CONFIRMED on the real A18 (EXP-M4-05) — NOT a delta, a general AGX rule the
A18 shares:** the tile-row stride must be a whole number of 16-KiB pages, so `cols = round_up(ceil(W/T), G)`, `G =
0x4000/(T²·bpp)` → bpp8 needs even columns (A18: 96→4, 160→6, 288→10, 0 mismatch; flat `ceil(W/T)` off by thousands).
This closes an original A18 coverage gap (A18 only probed bpp-4 widths where G=1). Folded into `tiling/README §1.1/§1.4`;
bpp2 confirmed (G=2, even). **bpp1 REFUTED the G=4 prediction and found a doc ERROR: bpp1 uses tile edge T=128 (not 64)** — A18 320-wide r8 → cols 3 (odd), tile=128²·1=16KiB, G=1 (EXP-M4-06). Corrected `tiling/README §1.1-1.4`: T = largest pow2 with T²·bpp≤16KiB (bpp1→128, bpp2/4→64, bpp8/16→32).

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
So the A18 `capability-matrix.md` / `capability-completeness.md` capability envelope applies to
M4. The current integration classification is 189 native / 11 emulated / 4 proven kernel / 10 NYC
after M4 EXP-0042 reopened graphics code-window/stage-selector mapping; that mapping still needs an
A18 run. Only capacity/config otherwise differs (see §0): 10 cores, maxBufferLength > 4 GiB, 16 GiB RAM.

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
| Machine model | ✅ identical (EXP-M4-11) |

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

## 3. Command stream (CDM/VDM/USC/state) — ⏳ PENDING
CDM compute launch, VDM draw, USC bind grammar (0x20 sampler stride), state packets, indirect/
occlusion/timestamp, mesh, native tessellation — to be traced on M4 via `iotrace` and diffed vs
`cmdstream/README.md`.

## 4. Resource descriptors — ⏳ PENDING
Texture (14-bit dims) / sampler (0x20 stride) / buffer / PBE / bindless — to be probed on M4 vs
`descriptors/`.

## 5. Texture tiling & compression — ⏳ PENDING
Row-major Morton tiles (T=64/32 by bpp, cols=ceil(W/T), multiple-of-T padding), mip, compression
(≥16×16, aux/128) — to be re-derived on M4 vs `tiling/README.md`.

## 6. TBDR / pipeline — ⏳ PENDING
32×32 tile, imageblock, MSAA, sample positions (userspace @+0x40), memoryless — to be traced on
M4 vs `pipeline/README.md`. (Watch for tile-memory/occupancy effects of the 10-core config.)

## 7. Kernel interface — ⏳ PENDING
Submit/BO/VM contract + firmware-managed items + the core-count/config the userspace must know —
vs `kernel-interface.md`.

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
| Machine model / cmdstream / descriptors / tiling / pipeline / kernel-iface / capabilities | ⏳ validating |

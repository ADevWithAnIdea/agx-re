# EXP-M4-03 RESULTS — M4 cmdstream + TBDR pipeline vs A18 Pro

**DUT:** Apple **M4** (Mac Mini M4), macOS 26.4.1 (25E253), **10 GPU cores**, Metal 4, SIP
disabled. Everything below ran LOCALLY on the M4 (no SSH). Baselines: `docs/cmdstream/README.md`
+ `docs/pipeline/README.md`. Every field decoded by `work/decode_all.py`; full byte evidence in
`raw/decode_summary.txt`.

## Step 0 — does iotrace work on the M4 host? **YES.**
`tools/iotrace` built `-arch arm64e` and interposed `IOConnectCallMethod`/`Struct`/`Scalar`,
`IOServiceOpen`, `IOConnectMapMemory` on a trivial local Metal compute dispatch with no
dyld/AMFI obstruction (SIP disabled). One `./iohello_compute --dump` produced **50 IOKit CALLs,
2 user-client OPENs, 30 BO snapshots**, and the correct result (`o[0]=1000.5`). BO dump via the
`kill(SIGUSR1)` path works identically to the A18 setup. **DATA-TRACE is fully available on the
M4 host** — no fallback needed.

### DELTA (device identity, not encoding): AGX user-client class
| | A18 Pro | **M4** |
|---|---|---|
| AGX user client | `AGXAcceleratorG17P` | **`AGXAcceleratorG16G`** |
| IOSurface client | `IOSurfaceRoot` | `IOSurfaceRoot` (same) |
| resource-map selector | `9` (in@0x38 cpu, in@0x48 size, out@0x00 GPU VA) | **`9`, same shape** |
| IOKit calls (compute / draw) | 49 / 58 | 50 / 60 |

The client-class **name** differs (`G16G` = M4 GPU vs `G17P` = A18 Pro); the submission model
(shared-memory + doorbell, no per-submit ioctl), the selector set, and the sel-9 map ABI are
identical. The small call-count deltas (+1 / +2) are macOS-version noise, not structural.
**A driver must match on the G16G/G17P class name per part; everything below is byte-identical.**

---

## Item-by-item confirm-or-delta

### 1. CDM compute launch — **IDENTICAL** (HW-validated)
CDM launch descriptor at the **same** `gpu_va 0x100000b0000`; every A18 field at the same offset:

| field | offset | M4 value | A18 baseline |
|---|---|---|---|
| config/register word | +0x00 | `0x00080000` (bit19) | `0x00080000` |
| shader ptr = shaderVA>>6 | +0x08 | `0x00002400` (=0x90000>>6) | `shaderVA>>6` |
| grid xyz (threads) | +0x10 | `64,1,1` | threads, not tg |
| effective tg xyz | +0x1c | `32,1,1` | driver-chosen tg |
| terminator | +0x2c | `0x40000000` | `0x40000000` |

### 2. VDM draw — **IDENTICAL** (HW-validated)
Tiler/VDM stream at `gpu_va 0x18000`; primitive record decodes byte-for-byte to A18:
- **Non-indexed** (`draw_tri`): `… 00 06 c4 61 | 03 00 00 00 | 01 00 00 00` → **prim@+0x65=0x06**
  (tri), **opcode 0x61c4@+0x66**, **vertexCount@+0x68=3**, **instanceCount@+0x6c=1**. `--prim line`
  → prim@+0x65=**0x01**; `--inst 5` → instanceCount@+0x6c=**5**.
- **Indexed** (`draw_idx`): the record **shifts** exactly as A18 RT-2a says — **opcode 0x61f2@+0x6e**
  (u16), **restart index 0xffff@+0x68**, prim@+0x6d=0x06, **indexCount@+0x74=3**,
  **instanceCount@+0x78=1**. (u32-index opcode `0x61f4` not separately re-run; the u16 form matches,
  so the u32 form is *inferred*-identical.)

### 3. USC bind grammar / sampler stride — **IDENTICAL** (HW-validated)
Textures+samplers argument buffer at the **same** `gpu_va 0x10000248000`, 2-pointer header at
`+0x600` = `[texture-array VA][sampler-array VA]`, `0x60000000` terminator. **Sampler stride is
0x20** and the count split is `num_textures=(samp−tex)/0x20`, `num_samplers=(term−samp)/0x20` — the
A18 red-team RT-2a fix holds exactly. HW-validated over three tex/samp counts:

| run | tex_ptr | samp_ptr | term | num_tex | num_samp |
|---|---|---|---|---|---|
| 1 tex / 1 samp | …620 | …640 | …660 | 1 | 1 |
| 2 tex / 3 samp | …620 | …660 | …6c0 | 2 | 3 |
| 3 tex / 1 samp | …620 | …680 | …6a0 | 3 | 1 |

(Samplers 0x20 apart, not 8 — no 4× overcount. Buffers still inline 8-byte VAs.)

### 4. Fixed-function state packets (0x58000) — **IDENTICAL** (HW-validated)
| packet | offset | tb_base | tb_ds (depth+stencil) |
|---|---|---|---|
| depth word | +0x38 | `0x07200f00` (write-disable bit21, cmp=7 always) | `0x01000f01` (write-enable, cmp=1 less, ref=1) |
| stencil word | +0x3c | `0x0e000000` | `0x0e02ffff` (write/read masks 0xff) |
| enable flags | +0x34 | `0x00040200` | `0x000c0200` (bits[19:18] set) |
| rasterizer | +0x70 | `0x00000480` | `0x00000480` |
| PPP output-select | +0x20 | `0x00010000` | `0x00010000` |
| UVS scalar count | +0x2c | `0x00000008` (= 4+4·1) | `0x00000008` |
| **PPP length word** | +0x14 | `0x4c19` | **`0x5019`** |

The **PPP length bumps +0x400** exactly when the depth/stencil block is appended
(`0x4c19 → 0x5019`, Δ=0x400) — the A18 EXP-0024 monotonic-length rule, confirmed. All packet
offsets (depth +0x38, stencil +0x3c, raster +0x70, PPP-output +0x20) are unchanged.

### 5. Indirect / occlusion / mesh / tessellation — **IDENTICAL** (HW-validated)
- **Indirect draw:** non-indexed opcode **0x6404@+0x66** (`0x61c4→0x6404`), indexed opcode
  **0x6432@+0x6e** (`0x61f2→0x6432`). Both match A18 EXP-0027.
- **Occlusion query:** per-draw mode = **bit14 of 0x58000+0x8c**: Boolean → `0x0004c200` (bit14=1),
  Counting → `0x00048200` (bit14=0). Matches A18.
- **Mesh:** the tiler stream carries the **mesh-grid-dispatch record `0x70000600`** (+ grid dims
  `1,1,1`) in place of the draw primitive record; single unified graphics submit, **no CDM launch
  descriptor**. Matches A18 EXP-0030.
- **Tessellation (native):** `drawPatches` emits the **VDM patch-dispatch record with high-byte
  0x40@+0x67**, **domain type @+0x8c = 1 (tri) / 2 (quad)**, packed config @+0x68
  (`0x47a00000` tri / `0x47b00000` quad), factor pointer @+0x74. Native tiler-path tessellation,
  same as A18 EXP-O2H (NOT M1/M2-style compute-only emulation). Factor buffer = IEEE half
  (triangle = 4 halfs / 8 B, per harness `FACTOR_BYTES 8`).
- **GPU timestamps** (stage-boundary only; `timestampPeriod=1.0`): **not separately re-run** on
  M4 — no structural opcode to diff, and all other item-5 opcodes matched, so *inferred*-identical.
  Flagged for a follow-up if the acceptance reviewer wants it HW-confirmed on M4.

### 6. TBDR pipeline — **IDENTICAL** (HW-validated), including the 10-core question
- **Tile size 32×32 fixed:** tiling context `0x68000` `+0x904 = 0x80000000|(ceil(W/32)−1)`,
  `+0x908 = ceil(H/32)−1`. w=64 → `0x80000001 / 1`; w=200 → `0x80000006 / 6`. Viewport transform
  @+0x910 = `{w/2, h/2, w/2, −h/2}` (Y-flip): `{32,32,32,−32}` / `{100,100,100,−100}`. **No
  shrink-tile scaling; identical to A18.**
- **MSAA sample count** @ attachment `+0x24`: 1× = `0x0000fc03`, 4× = **`0x0900fc03`** (byte3 = 0x09,
  bit24 count-LSB + bit27 MSAA-store). Matches A18. Color descriptor relocates into the tiler geom
  heap `0x10000018200` on MSAA/MRT/memoryless, arrayed as **fixed 0x20-byte per-attachment records**
  (verified MRT×4: records at +0x20/+0x40/+0x60/+0x80). Matches A18 RT-4/G1b.
- **Programmable sample positions — userspace-emittable @+0x40:** written to the client BO
  `0x100000e8000+0x40` as N (x,y) f32 pairs on a 1/16 grid. Default 4× = the D3D pattern
  `(0.375,0.125)(0.875,0.375)(0.125,0.625)(0.625,0.875)`; custom `--sampos` decodes exactly to the
  requested positions `(0.125,0.125)(0.875,0.3125)(0.3125,0.875)(0.6875,0.6875)`. The A18 RT-4 fix
  (NOT kernel-managed) holds on M4.
- **Memoryless poison:** `MTLStorageModeMemoryless` MSAA color writes poison **`0x0eeee000`** into
  the relocated tiler-heap color descriptor `0x10000018200+0x28`. Matches A18.

### 10-core effects — **none observed in the userspace cmdstream**
The M4 has 10 GPU cores vs the A18 Pro's 5, but **no userspace-visible cmdstream/pipeline field
encodes or scales with core count**: tile grid is 32×32 fixed (screen-space, core-independent),
viewport/attachment/state packets are byte-identical, and the per-attachment tile-memory records
are the same 0x20-byte stride. The tiler **geometry/parameter heaps** (`0x10000018xxx`,
`0x10000088000`) vary in size run-to-run and are **firmware/kernel-managed** (already flagged
kernel-side in the docs), so any core-count-dependent heap sizing lives below the userspace
boundary and is out of scope for the userspace driver — no client descriptor changed.

---

## Bottom line
**The M4 command-stream and TBDR-pipeline encodings are byte-identical to the documented A18 Pro
(G17P) baseline across all six probed areas** — CDM launch, VDM draw (direct+indexed), USC/sampler
bind grammar (0x20 stride), fixed-function state packets (depth/stencil/raster/PPP + the +0x400
length rule), indirect/occlusion/mesh/native-tessellation opcodes, and the full TBDR config
(32×32 fixed tile, MSAA count, userspace sample positions, memoryless poison). The **only delta is
the AGX user-client class name** (`AGXAcceleratorG16G` vs `AGXAcceleratorG17P`) — a per-part device
identity string, not an encoding. No 10-core effect surfaces in userspace. The A18 `docs/cmdstream`
and `docs/pipeline` specs describe the M4 GPU's userspace interface unchanged (modulo the class
name); the two open non-M4-tested items are the u32-index draw opcode `0x61f4` and stage-boundary
timestamps, both *inferred*-identical from adjacent matching evidence.

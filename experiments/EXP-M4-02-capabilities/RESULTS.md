# EXP-M4-02 — M4 capability delta vs A18 Pro

**Hypothesis:** The Apple **M4** (Mac16,10, this local host — Mac Mini M4, 10-core GPU, Metal 4)
exposes the **same hardware/Metal capability envelope** as the A18 Pro (G17P / Apple9). Re-run the
A18 capability probes on the M4 and report IDENTICAL or DELTA per capability.

**Method (clean-room, OWN-SHADER + HW-PROBE, all LOCAL — no SSH, no Apple binary inspected):**
- `metal_caps.m` — read-only `MTLDevice` capability properties + a `supportsFamily:` sweep + the
  max accepted MSL language version + `threadExecutionWidth` from **our own** 1-line compute kernel
  (compiling a pipeline state; **no** command buffer / encoder / GPU submission).
- `msl_probes.m` — a battery of **our own** MSL sources compiled with runtime
  `newLibraryWithSource:`; each records **COMPILED / REJECTED** + the first diagnostic line, scored
  against the documented A18 result (`docs/capability-{matrix,completeness}.md`).
- `bf16_matrix_probe.m` — focused follow-up on the one apparent delta (below).
- `run.sh` — builds + runs everything; raw output in `raw/` (`metal_caps.txt`, `msl_probes.txt`,
  `bf16_matrix_probe.txt`, `gpu_config.txt`).

Build: `clang -fobjc-arc -framework Metal -framework Foundation …` (Command Line Tools).

---

## Headline

**The M4 and A18 Pro have the SAME Metal/MSL capability envelope.** Every feature flag, every
argument-buffer/RW-texture tier, every MSL accept/reject probe is **IDENTICAL**. The only deltas are
**capacity/config** (core count, memory-proportional sizes) and **GPU codename string** — none of
which changes an instruction encoding, descriptor layout, or a native-vs-emulate decision.

Notable: the M4 reports GPU architecture **`applegpu_g16g`** (G16G), **not** G17P. Despite the
different codename, EXP-M4-01 already showed the two share the AGX **Apple9** ISA byte-for-byte, and
this experiment shows they share the capability envelope. (G16G's codename number is *lower* than
G17P — the M4 GPU predates the A18 Pro GPU — yet both are the Apple9 feature family.)

The one apparent capability delta in the first battery run — **bfloat `simdgroup_matrix` REJECTED on
M4** — was run down and proven to be a **probe-syntax artifact in our own source, not a hardware
difference** (see §4). bf16 cooperative-matrix is fully supported on M4, identical to A18.

---

## 1. MTLDevice numbers — side by side

| Property | A18 Pro (G17P) | **M4 (Mac16,10)** | Verdict |
|---|---|---|---|
| `name` | Apple A18 Pro | **Apple M4** | (identity) |
| `architecture.name` | `applegpu_g17p` | **`applegpu_g16g`** | ⚠ DELTA (codename) |
| GPU cores (ioreg `gpu-core-count`) | 5 (of 6, one fused) | **10** | ⚠ DELTA (config) |
| `threadExecutionWidth` (SIMD) | 32 | **32** | ✅ IDENTICAL |
| `maxThreadsPerThreadgroup` | (1024,1024,1024) | **(1024,1024,1024)** | ✅ IDENTICAL |
| `maxTotalThreadsPerThreadgroup` (trivial pso) | — | **1024** | ✅ (consistent) |
| `maxThreadgroupMemoryLength` | 32768 (32 KiB) | **32768** | ✅ IDENTICAL |
| `hasUnifiedMemory` | YES | **YES** | ✅ IDENTICAL |
| `hw.memsize` | 8 GiB | **16 GiB** | ⚠ DELTA (capacity) |
| `recommendedMaxWorkingSetSize` | 5.333 GiB (5726633984) | **11.840 GiB (12713115648)** | ⚠ DELTA (∝ RAM) |
| **`maxBufferLength`** | **4.000 GiB (0x1_0000_0000)** | **8.880 GiB (0x2_3852_0000 = 9534832640)** | ⚠ DELTA (**M4 > 4 GiB**) |
| `argumentBuffersSupport` | Tier 2 | **Tier 2** | ✅ IDENTICAL |
| `readWriteTextureSupport` | Tier 2 | **Tier 2** | ✅ IDENTICAL |
| `maxArgumentBufferSamplerCount` | 500000 | **500000** | ✅ IDENTICAL |
| `sparseTileSizeInBytes` | 16384 (= page size) | **16384** | ✅ IDENTICAL |
| `hw.pagesize` | 16384 | **16384** | ✅ IDENTICAL |
| `supportsRaytracing` / `…FromRender` | YES / YES | **YES / YES** | ✅ IDENTICAL |
| `supportsPrimitiveMotionBlur` | YES | **YES** | ✅ IDENTICAL |
| `supportsFunctionPointers` / `…FromRender` | YES / YES | **YES / YES** | ✅ IDENTICAL |
| `supportsDynamicLibraries` / `…RenderDynamicLibraries` | YES / YES | **YES / YES** | ✅ IDENTICAL |
| `supports32BitFloatFiltering` | YES | **YES** | ✅ IDENTICAL |
| `supports32BitMSAA` | YES | **YES** | ✅ IDENTICAL |
| `supportsBCTextureCompression` | YES | **YES** | ✅ IDENTICAL |
| `supportsPullModelInterpolation` | YES | **YES** | ✅ IDENTICAL |
| `supportsShaderBarycentricCoordinates` / `barycentricCoordsSupported` | YES / YES | **YES / YES** | ✅ IDENTICAL |
| `programmableSamplePositionsSupported` | YES | **YES** | ✅ IDENTICAL |
| `rasterOrderGroupsSupported` | YES | **YES** | ✅ IDENTICAL |
| `supportsQueryTextureLOD` | YES | **YES** | ✅ IDENTICAL |
| `depth24Stencil8PixelFormatSupported` | NO | **NO** | ✅ IDENTICAL |
| counter sets | `timestamp` | **`timestamp`** | ✅ IDENTICAL |

### Feature-set table (`supportsFamily:`)

| Family | A18 Pro | **M4** |
|---|---|---|
| Apple1 … **Apple9** | YES (all) | **YES (all)** |
| **Apple10 / Apple11** | (not probed) | **NO / NO** |
| Mac1 / Mac2 | YES / YES | **YES / YES** |
| Common1–3 | YES | **YES** |
| MacCatalyst1 / 2 | (not probed) | **NO / NO** |
| **Metal3 / Metal4** | YES / YES | **YES / YES** |
| Metal5 (speculative 5003) | (n/a) | **NO** |

Both cap out at **Apple9 + Metal4**. The M4 claims **nothing** beyond Apple9/Metal4 (no Apple10,
no Metal5). ✅ IDENTICAL max family.

### Max MSL language version (compile a trivial shader per version)

M4 accepts MSL **3.0, 3.1, 3.2, 4.0**; **rejects 4.1** (`invalid value 'metal4.1' in '-std=metal4.1'`).
Max = **MSL 4.0**. This is toolchain/OS-bound (both parts run macOS 26 / Metal 4), so it is expected
identical on A18. ✅ (no chip-level delta).

### Metal-4 device selectors (`respondsToSelector:`)
`newResidencySetWithDescriptor:error:`, `newIOCommandQueueWithDescriptor:error:`,
`sizeOfCounterHeapEntry:`, `newCommandQueueWithDescriptor:`,
`sparseTileSizeInBytesForSparsePageSize:` → **YES**. These are Metal 3/4 API surface present on both
Metal-4 devices. `newTensorWithDescriptor:offset:error:` (guessed name) → NO, but the **MSL** tensor
type is available (§3). No M4-exclusive device capability found.

---

## 2. MSL capability probes — M4 vs A18 (all IDENTICAL)

Every probe returns the same accept/reject as the documented A18 result. "REJECTED" rows are the
**expected** absences (they define what a Vulkan/GL driver must emulate — same on both parts).

| Probe | A18 (docs) | **M4** | Verdict |
|---|---|---|---|
| bfloat scalar ALU | COMPILED | **COMPILED** | ✅ IDENTICAL |
| half (fp16) ALU | COMPILED | **COMPILED** | ✅ IDENTICAL |
| 64-bit (`long`) integer ALU | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `simdgroup_matrix` fp16 8×8 | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `simdgroup_matrix` fp32 8×8 | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `simdgroup_matrix` **bf16** 8×8 (load+matmul) | COMPILED | **COMPILED** | ✅ IDENTICAL (see §4) |
| `simdgroup_matrix` **int8** (char) | REJECTED | **REJECTED** | ✅ IDENTICAL (→ emulate) |
| `simdgroup_matrix` **int32** | REJECTED | **REJECTED** | ✅ IDENTICAL (→ emulate) |
| device **float** atomic **add** | COMPILED | **COMPILED** | ✅ IDENTICAL (native) |
| device **float** atomic **min** | REJECTED | **REJECTED** | ✅ IDENTICAL (→ emulate) |
| **64-bit** atomic add (`atomic<uint64_t>`) | REJECTED | **REJECTED** | ✅ IDENTICAL (→ emulate) |
| **64-bit** atomic min (`atomic<ulong>`) | REJECTED | **REJECTED** | ✅ IDENTICAL (→ emulate) |
| int32 atomic add | COMPILED | **COMPILED** | ✅ IDENTICAL |
| quad ops (`quad_shuffle`/`quad_broadcast`) | COMPILED | **COMPILED** | ✅ IDENTICAL |
| simd prefix scan (incl/excl sum) | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `simd_shuffle_and_fill_up/down` | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `simd_is_helper_thread()` (fragment) | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `simd_ballot` / vote | COMPILED | **COMPILED** | ✅ IDENTICAL |
| RT `intersector<triangle_data,instancing>` | COMPILED | **COMPILED** | ✅ IDENTICAL (native RT) |
| RT inline `intersection_query` | COMPILED | **COMPILED** | ✅ IDENTICAL |
| RT custom `[[intersection(bounding_box…)]]` + `ray_data` payload | COMPILED | **COMPILED** | ✅ IDENTICAL |
| mesh + object pipeline (`[[mesh]]`/`[[object]]`) | COMPILED | **COMPILED** | ✅ IDENTICAL (native mesh) |
| tessellation post-tess vertex (`[[patch(triangle,3)]]`) | COMPILED | **COMPILED** | ✅ IDENTICAL (native tess) |
| tessellation-factor compute kernel (half factors) | COMPILED | **COMPILED** | ✅ IDENTICAL |
| `os_log` shader logging | COMPILED | **COMPILED** | ✅ IDENTICAL |
| MSL `printf` | REJECTED (os_log is the path) | **REJECTED** | ✅ IDENTICAL (no MSL printf; use os_log) |
| sampler border presets (opaque-white / transp-black / opaque-black) | COMPILED (3 presets only) | **COMPILED** | ✅ IDENTICAL (arbitrary border still → emulate) |
| MSL tensor type (`<metal_tensor>`) | Metal-4 (native MPP→`0xcf`) | **COMPILED** | ✅ IDENTICAL (both Metal 4) |
| MPP header (`MetalPerformancePrimitives`) | Metal-4 | **COMPILED** | ✅ IDENTICAL (both Metal 4) |
| texture atomics (`access::read_write`) | COMPILED | **COMPILED** | ✅ IDENTICAL |

**Result: 0 capability deltas.** All the A18 native-vs-emulate boundaries (int cooperative-matrix
absent, float-atomic-min/max absent, all 64-bit atomics absent, only-3 border-color presets, no MSL
printf) reproduce **exactly** on the M4.

---

## 3. Metal 4 / M4-new assessment

- The M4 exposes **nothing beyond Apple9 / Metal4**: no Apple10, no Apple11, no Metal5; no
  M4-exclusive device selector. Same max family as the A18 Pro.
- The Metal-4 **tensor** surface (`metal_tensor` MSL type + `MetalPerformancePrimitives`) compiles on
  the M4 — but this is a **Metal-4** feature the A18 Pro already has (both are Metal 4), and the A18
  census already documents the MPP tensor ops lowering to the `0xcf` matrix MAC (EXP-O2C). So it is
  **not** an M4-vs-A18 delta.
- Max MSL version 4.0 on both (OS/toolchain-bound).

Conclusion: **there is no Metal-4 capability the M4 exposes that the A18 baseline does not already
record.** Nothing "M4-new" surfaces at the Metal/MSL capability level.

---

## 4. The bf16-matrix "delta" — a probe artifact, resolved

The first battery run reported `simdgroup_matrix_bf16` **REJECTED** on the M4, which would have been
the only real capability delta. Follow-up (`bf16_matrix_probe.m`) shows this was a **flaw in our own
source**, not a hardware/compiler difference:

- The failing spelling was `simdgroup_matrix<bfloat,8,8> a(1.0)` — a scalar-broadcast constructor
  from a bare `1.0` double literal.
- The compiler diagnostic (about **our own** source) is *"no matching constructor … no known
  conversion from 'float' to storage_type (aka `vec<bfloat, 64>`)"*: the matrix scalar-broadcast
  constructor takes a full `vec<T,64>` and there is **no implicit `float`→`bfloat`** element
  conversion, whereas `half`/`float` typedefs (`simdgroup_half8x8`/`simdgroup_float8x8`) accept a
  `1.0` literal via implicit conversion. This is an MSL **language/header** quirk, not a HW gate.
- Every correct bf16-matrix spelling **COMPILES** on the M4:
  `simdgroup_matrix<bfloat,8,8> a(bfloat(1.0))`, default-ctor + `simdgroup_load`,
  `make_filled_simdgroup_matrix<bfloat,8,8>(…)`, **bf16-in / fp32-accumulate matmul**, and
  **all-bf16 matmul**. → bf16 cooperative matrix is supported, **IDENTICAL to A18**.

The battery probe was corrected to the real load+matmul spelling (now COMPILED); the artifact is
documented here so the trail is honest.

> Clean-room note: the diagnostic surfaced a path inside a **public MSL standard-library header**
> (`metal_simdgroup_matrix`) as part of a **compiler error message about our own code**. No Apple
> **binary** was disassembled/decompiled; we read a compiler diagnostic on our own source. The fact
> learned (a header constructor takes `vec<bfloat,64>` with no implicit scalar broadcast) is an MSL
> language surface fact, not copyrightable hardware.

---

## 5. Driver-impact flags (things an implementer must parameterize)

None of the deltas changes an encoding or a native/emulate decision, but three are **driver-visible
config** and must not be hard-coded from the A18 numbers:

1. **GPU core count = 10** (vs A18's 5). Affects occupancy/dispatch sizing and any core-count field
   handed to the kernel; it is a **kernel-interface / config** value, not an encoding. (Already noted
   in `docs/m4-deltas.md` §0/§7.)
2. **`maxBufferLength` = ~8.88 GiB on M4 vs exactly 4 GiB on A18.** The A18's 4 GiB is a hard cap
   (0x1_0000_0000); the **M4 permits single buffers > 4 GiB**. A driver that assumed a 4 GiB buffer
   ceiling (or 32-bit intra-buffer offsets) from the A18 baseline would be wrong on the M4 — query the
   device, do not hard-code. Both scale roughly with total RAM (A18 4/8 GiB; M4 8.88/16 GiB).
3. **`recommendedMaxWorkingSetSize`** scales with RAM (5.33 GiB → 11.84 GiB) — advisory only.

**GPU codename** `applegpu_g16g` (vs `g17p`) is an identity string; it resolves the "TBD exact" note
in `docs/m4-deltas.md` §0. It does **not** imply an ISA/capability difference (EXP-M4-01 proved the
ISA is identical; this experiment proves the capability envelope is identical).

---

## Provenance

Harness (OUR OWN): `metal_caps.m`, `msl_probes.m`, `bf16_matrix_probe.m`, `run.sh`.
Raw device output: `raw/metal_caps.txt`, `raw/msl_probes.txt`, `raw/bf16_matrix_probe.txt`,
`raw/gpu_config.txt`. Method: **OWN-SHADER** (runtime `newLibraryWithSource:` on our own MSL;
accept/reject + diagnostics only) + **HW-PROBE** (read-only `MTLDevice` capability properties;
IORegistry/`system_profiler`/`sysctl` runtime config values). One trivial compute **pipeline state**
was built from our own 1-line kernel to read `threadExecutionWidth` — **no** command buffer, encoder,
or GPU submission. **No Apple binary was disassembled, decompiled, or introspected.** Baseline for
comparison: `docs/hardware-overview.md` §3 (A18 `MTLDevice` probe, EXP-0002),
`docs/capability-matrix.md`, `docs/capability-completeness.md`.

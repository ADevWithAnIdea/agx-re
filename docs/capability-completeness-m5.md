# Apple M5 (Apple10 / G17g / T8142) — Capability Completeness Tracker (OBJ-2)

The **OBJ-2 tracker** for the M5 (`ROADMAP-M5.md` §5.2 / §5.5). It grades one question: *is every
capability the M5 GPU exposes — everything Metal surfaces + everything Apple advertises for Family-10 —
enumerated and characterized?* The full row-by-row classification lives in `capability-matrix-m5.md`;
**this file is the gap list**: it separates capabilities whose M5 encoding is **characterized** from those
**confirmed present but NOT yet mapped on M5** (the backlog the ISA-semantics and cmdstream waves must close),
and names the exact probe that closes each.

> **Method.** The M5 is a **G17g sibling of the A18 Pro (G17P / Apple9)**. Presence is established on M5 HW
> (EXP-M5-04 `MTLDevice` probe + EXP-M5-08 own-MSL acceptance probe). Encoding status is: **measured on M5**
> where EXP-M5-05 (ISA tokenization) / EXP-M5-06 (cmdstream+descriptor) covered it, otherwise **inherited
> from the A18 encoding** (round-trip-green on the M5 corpus) or **NYC** where a G17g delta touches the
> encoding and has not been re-characterized. No Apple binary introspected.

## Status vocabulary

- **characterized-M5** — presence confirmed AND the M5 HW representation is measured on M5 hardware
  (EXP-M5-05/06) or is inherited from A18 and confirmed transferring (round-trip-green / measured identical).
- **PRESENT-ENCODING-NYC** — presence confirmed on M5 (device flag / MSL-accept / advertised) **but the M5
  HW representation is NOT yet mapped.** ← the OBJ-2 work items. Two sub-kinds:
  - `splice-TODO` — an ISA op in a G17g-delta family; leader/length restored + round-trip-green, but its
    **field-semantics are not yet splice-validated on M5**.
  - `open-record` — a cmdstream/descriptor record not yet probed on M5.
- **emulated** — HW-absent on M5 → software-emulate (negative result).
- **kernel-managed** — firmware/submit-managed; transfers (M5 submission model identical, EXP-M5-06).
- **microarch-only** — Apple-advertised property with no single emittable encoding (counters only).

---

## A. Confirmed present, ENCODING CHARACTERIZED on M5 (no OBJ-2 action)

These have both presence and an M5-available encoding. **Measured directly on M5** (EXP-M5-05/06):

- **Compute dispatch core** — CDM 0x2c-byte record (shader-ptr `+0x08=shaderVA>>6`, grid-in-threads
  `+0x10`, threadgroup `+0x1c`); config word `+0x00` bit23 occupancy tier (bit19-base dropped);
  threadgroup-mem size at shader-BO `+0x38` (segmented `0x0c00000f|(fine<<11)|(coarse<<19)`, HW-validated
  16 B…32 KiB). → EXP-M5-06.
- **Draw core** — VDM record (opcodes `0x69c4`/`0x69f2`, primitive-type byte, vertex/instance counts,
  indexed config, restart comparand); viewport transform `0x68000+0x9d0`; cull/winding `0x58000+0x1a8`.
  → EXP-M5-06.
- **Argument buffers Tier-2 / bindless** — resource table `+0x14a0`, 8-byte slots (buffers inline VA,
  tex/samp ptr-to-descriptor); byte-identical to A18. → EXP-M5-06.
- **Texture descriptor (32 B)** — type/format-code/swizzle/baseVA/sRGB/arrayLen/sampleCount; the one delta
  is the width/height split (+1 bit). → EXP-M5-06.
- **Sampler descriptor (8 B)** — address modes / filters / mip / LOD clamp / aniso ≤16× / compare / border
  presets; **byte-identical to A18**, sweeps HW-confirmed. → EXP-M5-06.
- **Buffer binding** — bare inline 8-byte GPU VA. → EXP-M5-06.
- **`get_sr` / special registers / sysvals** — HW-confirmed decoding `get_sr(position_in_grid)` on M5.
  → EXP-M5-01.
- **Device limits / feature flags** — SIMD 32, maxThreadsPerTG 1024, 32 KiB tgmem, timestamp counters
  (stage-boundary only), all measured. → EXP-M5-04.
- **FF-pool depth/stencil/raster/blend + occlusion (EXP-M5-10)** — depth `0x58000+0x170`/`+0x174`
  (compare[26:24]), stencil `+0x178`/`+0x17c` (pass/zfail/sfail/compare), rasterizer `+0x1a8`
  (cull[1:0]·winding bit16·**depth-clip/clamp[11:10]**), depth-bias enable `+0x16c` bit17, color
  write-mask `+0x194`, **polygon line-fill** bit (`+0x16c`/`+0x170` bit18/`+0x188`); **blend is
  programmable** (compiled into the FS, 0-pool-diff); alpha-to-one FS-epilog (no pool field); occlusion
  mode `+0x1c4` bit14 + result offset `+0x1d8` (Boolean=1 / Counting=4096, HW-validated). Enums
  **bit-identical to A18**. → EXP-M5-10.
- **TBDR render-control (EXP-M5-10)** — tile **32×32 fixed on the 8-core M5** (`0x68000+0x9c4/+0x9c8`);
  MSAA sample count at attachment record+0x30 (1×/2×/4×; 8× rejected); **programmable sample positions
  userspace-emittable** at client BO `0x100000d8000+0x40` (1/16 grid, HW-validated); memoryless (poison
  VA + zeroed backing); load/store actions (0x300-byte LOAD/RENDER/STORE segments + clear color `+0x170`).
  → EXP-M5-10.
- **Draw / indirect / tessellation records (EXP-M5-10)** — indirect dispatch (2nd CDM + multiply helper);
  **indirect draw** opcodes `0x6c04` (non-indexed) / `0x6c32` (indexed); **tessellation is a NATIVE HW
  stage** (VDM patch-dispatch record in tiler stream `0x18000`, half-float factor buffer, no CDM).
  → EXP-M5-10.
- **Graphics presence probes (EXP-M5-12)** — own-MSL compile ACCEPT on M5 for **layered rendering**
  (`[[render_target_array_index]]`), **fragment depth output** (`[[depth(any/greater/less)]]`),
  **`[[early_fragment_tests]]`**, **fragment `[[sample_mask]]`** output + input coverage mask (plus the
  documented `viewport_array_index` / `barycentric_coord` controls). → EXP-M5-12
  (`raw/msl_acceptance_m512.txt`).

**Inherited from A18, confirmed transferring (round-trip-green on the M5 corpus):** scalar/half/bfloat/64-bit
integer ALU; logic ops (16-func LUT); round modes; SFU transcendentals; int/bit ops; control flow
(branch/loop/exec-mask/predication); derivatives `0x37`; interpolation/varying `iter` `0x2f`; broadcast/shuffle/
ballot subgroup ops; `simd_shuffle_and_fill`; quad ops; programmable-blend-in-FS mechanism; provoking-vertex
`iter_flat`. **bfloat ALU and the subgroup/quad tail were re-confirmed present via our own M5 MSL (EXP-M5-08).**

---

## B. Confirmed present, ENCODING NOT-YET-MAPPED on M5 — **the OBJ-2 backlog**

Every item is present on M5 (device flag / MSL-accept / advertised); only the **M5 encoding** is missing.
Prioritized. Each names the probe that closes it.

### B.1 ISA field-semantics — the splice-and-observe wave (device is fault-recoverable, SIP-off)

The G17g moved several ISA families; EXP-M5-05 restored leaders/lengths (round-trip green) but explicitly
deferred **field-semantics** to this wave. Each row = "compile our own single-op MSL that provokes the op,
extract, splice-and-observe on M5 HW, decode the field map."

| # | Capability cluster | M5-delta family | Closing probe |
|---|---|---|---|
| 1 | **device/constant/threadgroup load & store** (incl. sub-32-bit extend, element addressing) | memory load `0x18`, store `0x41`/`0xc1` (**#1 delta, 204 kernels**) | splice single load/store; sweep space/base_slot/count/width/elem_size bytes on M5 |
| 2 | **Atomics** (int add/sub/and/or/xor/min/max, xchg/store/load, cmpxchg, **float add**, scope) | memory-family RMW (rides `0x18`/`0x41`) | splice each RMW; locate op byte + scope bit on M5 |
| 3 | **Texture sample / gather / image-read / LOD-query / sample_compare** | typed/sample `0x78`/`0x58`/`0x50` | splice sample/gather/read; map op+2 dim/mode + companion component bytes on M5 |
| 4 | **Image write (store)** / imageblock read+write / tile_read / vertex-varying store `0x57` | store `0xd7`/`0xe7`-class (rides memory delta) | splice image/imageblock/tile store; map slice addressing + format bytes on M5 |
| 5 | **`simdgroup_matrix` MAC** (fp16/fp32/bf16) + load/store/transpose | matrix MAC (`0xcf`-equivalent) | splice `simdgroup_multiply_accumulate`; map A/B/C/dst/dtype/accum operand bytes on M5 |
| 6 | **Ray tracing** — `rt_intersect`, `rt_as_load`, `ray_data`, traversal loop, inline `intersection_query`, RT-from-render, motion blur, intersection-function-table | RT ops (ride RT/memory delta) | splice ray_query + intersector; map intersect/as-load/ray-data field maps + motion time-form on M5 |
| 7 | **Function calls / indirect call / dylibs / recursion / spill frame** | call `0xef`/`0xff`; frame `0x07`/`0x6f` | splice a `[[visible]]` call + `visible_function_table` indirect; map target/link/arg ABI on M5 |
| 8 | **Barriers & fences** — `threadgroup_barrier`, atomic fences, ROV pixel-order, tilebuffer ordering | fence/barrier `0x07` (flagged delta) | splice barrier + `atomic_thread_fence` + ROV; map scope bytes on M5 |
| 9 | **Subgroup reduce / prefix-scan** (sum/product/min/max/and/or/xor, inclusive/exclusive) | `0x3f`/`0xbf` simd_reduce (flagged delta) | splice reduce+scan; map byte+7 dtype/shape on M5 |
| 10 | **Mesh / object emit** (vertex/prim/index export, object_data payload, amplification) | store-based emit (rides memory delta) | splice object+mesh kernels; confirm `0xe7` store emit + child-count write on M5 |

> **Marquee M5 item (folded into #5).** Apple10 markets a **Neural Accelerator per GPU core.** On A18 all
> `MTLTensor`/MPP tensor ops lowered to the `0xcf` matrix MAC with **no** dedicated tensor opcode. **Whether
> the M5 keeps that lowering or introduces a dedicated neural/tensor instruction path is UNRESOLVED and is
> the single highest-value M5 OBJ-2 characterization target.** Probe: compile `MTLTensor` /
> `tensor_ops::matmul2d` kernels, extract, and diff the M5 op stream against the `0xcf` MAC — a new leader
> means a dedicated neural path; all-`0xcf` means the A18 lowering transfers. (`<metal_tensor>` compiles and
> `newTensorWithDescriptor:error:`=YES on M5, so the surface is present.)
>
> **int8 matmul lives here, not in the "absent" bucket.** `simdgroup_matrix<int/char>` is a **confirmed
> absence** (MSL REJECT, §C) — but **int8 GEMM via the `MTLTensor` / MPP neural path** is a *present-but-NYC*
> capability in exactly this cluster (§7 matrix row): the same tensor surface that carries fp16/bf16 also
> carries int8, and its M5 lowering is unmapped. Do **not** conflate "no integer `simdgroup_matrix`" with
> "no int8 matmul." (OBJ-2 review M-4.)

### B.2 Cmdstream / descriptor records — the data-trace wave (EXP-M5-06 open items)

> **Largely CLOSED by EXP-M5-10** (own-process data-trace + own-MSL HW-probe). Rows #11, #12, #16, #17, #18,
> #19 are **resolved and moved to §A / native**; #13 and #15 are **partially** resolved (line-fill closed;
> the PPP output-select word and the PBE storage-image descriptor remain open). #14 and #20 are still open.

| # | Capability cluster | Status on M5 | Residual open |
|---|---|---|---|
| 11 | **Depth/stencil state** (compare funcs, stencil ops), **depth clamp/clip**, **depth bias** | ✅ **CLOSED (EXP-M5-10)** — depth `+0x170/+0x174`, stencil `+0x178/+0x17c`, raster clip/clamp `+0x1a8[11:10]`, bias enable `+0x16c` bit17; enums bit-identical to A18, all 8+8 HW-validated | — |
| 12 | **Blend enable/factors/ops**, **color write mask**, **alpha-to-coverage/one**, **logic-op flags** | ✅ **CLOSED (EXP-M5-10)** — blend programmable-in-FS (0-pool-diff); write-mask `+0x194`; alpha-to-one FS-epilog (no pool field); logic-ops via `0x0b` LUT | per-channel write-mask packing ⏳ |
| 13 | **Polygon fill mode (line)**, **point size**, **clip distances**, **multi-viewport**, **layered rendering**, **provoking** | ◐ **PARTIAL (EXP-M5-10 + EXP-M5-12)** — **line-fill CLOSED** (`+0x16c`/`+0x170` bit18/`+0x188`); provoking = `iter_flat` native; **layered rendering + multi-viewport present** (EXP-M5-12 MSL ACCEPT), mechanism = PPP output-select bit | **PPP output-select word** (point-size / clip / layer / viewport bit offsets) — the last open FF-pool record |
| 14 | **VS→FS varying linkage** (UVS slot layout + count) | ❓ open | `0x58000+0x2c`-class count in reorganized FF-pool — reorder-varying data-trace on M5 |
| 15 | **Render-target attachment** + **PBE/storage-image descriptor** + packed format word | ◐ **PARTIAL (EXP-M5-10)** — color attachment chain + format word + clear color CLOSED (BO `0x10000118000`, 3-seg LOAD/RENDER/STORE) | **PBE storage-image (`access::write`) descriptor** W/H bit-solve — still open |
| 16 | **Load/store actions**, **memoryless**, **MSAA sample count**, **programmable sample positions**, **tile size** | ✅ **CLOSED (EXP-M5-10)** — all measured on the 8-core M5 (tile still 32×32; sample-pos userspace-emittable @`0x100000d8000+0x40`; MSAA 1×/2×/4×) | **imageblock/tile memory + explicit tile-shader dispatch** record ⏳ |
| 17 | **Indirect dispatch**, **indirect draw**, **ICB / device-generated commands** | ◐ **PARTIAL (EXP-M5-10)** — indirect dispatch (2nd CDM + multiply helper) + indirect draw (`0x6c04`/`0x6c32`) CLOSED | full **ICB inline-command record** + draw-mesh-into-ICB — still open |
| 18 | **Tessellation record**, **mesh-grid-dispatch record**, **vertex amplification** | ◐ **PARTIAL (EXP-M5-10)** — **tessellation NATIVE HW** VDM patch-dispatch record CLOSED | mesh-grid-dispatch (pipeline-create aborted, re-probe) + vertex amplification — still open |
| 19 | **Occlusion / visibility queries**, **USC bind-pair grammar** | ◐ **PARTIAL (EXP-M5-10)** — occlusion CLOSED (mode `+0x1c4` bit14, offset `+0x1d8`; Boolean=1/Counting=4096 HW-validated) | **USC graphics bind-pair grammar** — still open |
| 20 | **Texture tiling/twiddle + mip packing + lossless compression aux + BC/ASTC + 3D/cube/array/MSAA layout + sparse-tier flag + linear stride** | ❓ open | tiling/compression/sparse not probed on M5 — known-pattern-in / read-layout-out (as EXP-0017/0028 did for A18) |

> **EXP-M5-12 newly-enumerated graphics capabilities — where they land (OBJ-2 review B-1 / M-1 / M-2 / M-3).**
> These had **no capability row** before this pass; presence is now confirmed on M5 (own-MSL ACCEPT,
> `raw/msl_acceptance_m512.txt`), and each is classified **native (mechanism)** with an honest
> encoding-status tag:
> - **Layered rendering** `[[render_target_array_index]]` (B-1 BLOCKER) — native (mechanism); PPP
>   output-select bit parallel to `viewport_array_index`; exact M5 bit = the still-open PPP output-select
>   word (B.2 #13).
> - **Fragment depth output** `[[depth(any/greater/less)]]` **+ `[[early_fragment_tests]]`** (M-1) — native
>   (mechanism); depth emitted via an FS-epilog Z-store into the ZLS path; the exact depth-emit **store op
>   rides the `0xe7` store delta** (B.1 #4). *Honest MSL rule observed: depth-write output is mutually
>   exclusive with `[[early_fragment_tests]]` (compiler rejects the combination).*
> - **Fragment `[[sample_mask]]`** output + input coverage (M-2) — native (mechanism); output = FS-epilog
>   coverage write (rides B.1 #4 store), input = coverage read via `get_sr` (HW-confirmed on M5).
> - **RT custom bounding-box (AABB) + curve primitives** (M-3) — native (mechanism); the primitive tag does
>   not change the intersect op — discrimination is in the AS + `intersection_function_table` (the custom-AABB
>   intersection-function **call ABI rides `0xef`/`0xff`**, B.1 #7). **RT companion ops**
>   (`rt_transform_test`/`ray_move`) ride the RT delta (B.1 #6).

### B.3 Extrapolate-and-test (Metal exposes no path; native-or-emulate decision open on M5)

| # | Capability | Note |
|---|---|---|
| 21 | **Anisotropy > 16×** | sampler field encodes 128× (byte-identical to A18); Metal caps 16× — untested on M5 HW |
| 22 | **Wide / smooth lines** | Metal line width fixed — extrapolate-and-test on M5 |
| 23 | **Conditional rendering** | CPU-emulated in Mesa — likely emulate; not probed on M5 |

### B.4 Machine model re-confirmation (OBJ-1-adjacent, listed for completeness)

| # | Capability | Note |
|---|---|---|
| 24 | **GPR count / register width / spill base** | re-confirm `__GPU_METADATA` footprint on M5 (Phase 1.4); A18 = 96 GPRs, 2 halves/GPR |

---

## C. Confirmed ABSENT on M5 — emulation flags (negative results)

Re-confirmed on M5 via our own MSL / device flags (EXP-M5-08 / EXP-M5-04) unless marked *inherit*:

| Capability | Evidence on M5 | Driver implication |
|---|---|---|
| **Float atomic min / max** | MSL REJECT (our own kernel) | emulate (int-bitcast CAS) |
| **All 64-bit atomics** (add/min/max, every spelling) | MSL REJECT (our own kernel) | emulate |
| **`simdgroup_matrix<int/char>`** (integer cooperative matrix) | MSL REJECT (char & int `simdgroup_matrix`) | emulate (integer MAC in ALU). **NB:** int8 matmul via the `MTLTensor`/MPP neural path is **present-but-NYC** (§7 / §B.1 #5), *not* an absence — do not conflate. |
| **Packed depth24-stencil8** | `depth24Stencil8PixelFormatSupported=NO` | use D32/D16 + separate S8 |
| **Texture sampleCount 8× / 16×** | `supportsTextureSampleCount(8/16)=NO`; MSAA sample-count field measured 1×/2×/4× only (EXP-M5-10) | cap MSAA at 4× |
| **Conservative rasterization** | Metal exposes no conservative-raster API (*Metal-unexposed*) | emulate (shader-side bbox expansion) |
| **Pipeline-statistics queries** (primitives-generated / clipping / stage-invocations) | Metal has no pipeline-statistics counter set — only STAGE-boundary timestamps (*Metal-unexposed*) | emulate the queries |
| **Double precision (fp64)** | not exposed by MSL (*inherit*) | emulate / refuse |
| **Arbitrary sampler border color** | 2-bit 3-preset field (*inherit*; sampler desc byte-identical) | 2-sampler-plane trick |
| **Polygon-point fill** | Metal-unreachable (*inherit*) | emulate |
| **Cull distance** | MSL clip-only (*inherit*) | emulate |
| **Custom primitive-restart index** | Metal always all-ones (*inherit*) | emulate |
| **Geometry shaders** | no Metal path (*inherit*) | compute-emulate (VS→GS) |
| **Transform feedback / streamout** | no Metal path (*inherit*) | compute-emulate |

> **Honesty note.** Float atomic min/max, all 64-bit atomics, integer `simdgroup_matrix`, D24S8, and
> sampleCount 8×/16× are **HW/toolchain-confirmed absences on M5** (our own probes). **Conservative
> rasterization and pipeline-statistics queries** are **Metal-unexposed** (no API path on Apple → a Vulkan/GL
> driver must emulate) — same class as GS/XFB. fp64, border color, polygon-point, cull distance, and custom
> restart are carried from A18's absences; the sampler-descriptor half (border color) is on the
> byte-identical sampler so it transfers with high confidence, while GS/XFB are classically-Apple-absent
> stages not independently re-probed on M5 (a `newRenderPipelineState` build-failure probe would re-confirm).
> **Correction (OBJ-2 review M-4):** the earlier single "int8/integer cooperative matrix = absent" row was
> over-strong — it split here into a confirmed absence (`simdgroup_matrix<int>`) and a present-but-NYC row
> (int8-via-`MTLTensor`, §7).

---

## D. Honestly excluded from OBJ-2 (microarch-only + kernel-managed)

**Microarch-only** (no emittable encoding; throughput/occupancy counters only) — inherited from A18:
- **2× ALU** (dual-issue FP16/FP32/int) — advertised Family-10; throughput microbench.
- **Flexible on-chip memory** (unified L1) — cache-hit/eviction counters.
- **Dynamic Caching dynamic behavior** — register-file-as-cache alloc/dealloc curve (static model transfers).
- **RT reorder stage** — firmware/microarch grouping of intersection calls.
- **Lossless compression block codec** — HW-internal per-generation codec (documented disable-fallback).
- **Full occupancy / latency-throughput curve** — a perf measurement, not an encoding.

**Kernel-managed** (real HW state via the kernel submit; M5 submission model identical, EXP-M5-06):
- **RT BVH build + node format** — GPU/firmware builds; node format not userspace-visible.
- **Depth store-action / ZLS** (`ZLS_CTRL`) — firmware-programmed at render-pass granularity.
- **Partial-render / tiler-param overflow** — firmware detects overflow.
- **Scissor test** (`isp_scissor_base`) — submit param.
- **Graphics shader-entry bind** — a draw carries no `shaderVA>>N`; code-BO base reaches firmware out-of-band.
- **Metal-4 residency sets** (`MTLResidencySet`) — userspace declares the resource set; page residency
  (wiring) is firmware/kernel-managed via the submit (no userspace ISA/cmdstream encoding).
- **Metal-4 IO command queues** (`MTLIOCommandQueue`) — **out of GPU-execution scope**: a storage→memory
  DMA/streaming path managed by the OS/kernel IO subsystem, not the GPU userspace driver's ISA/cmdstream.
  Listed for completeness (OBJ-2 review m-2).

---

## E. OBJ-2 scorecard (M5)

| Metric | State |
|---|---|
| Metal-exposed / advertised capabilities **enumerated** | **100%** — every A18 capability + Family-10 advertised feature is in `capability-matrix-m5.md`; the OBJ-2 review's B-1 BLOCKER (layered rendering unenumerated) + 4 MAJOR + 5 MINOR gaps are **closed** (EXP-M5-12) |
| Presence **confirmed on M5** | **100%** — EXP-M5-04 device probe + EXP-M5-08 / **EXP-M5-12** own-MSL probes |
| Encoding **characterized on M5** | **substantial** — cmdstream/descriptor core (EXP-M5-06) + **EXP-M5-10** FF-pool/TBDR/draw/tessellation + ISA tokenization (EXP-M5-05, round-trip-green) + device limits; **84 native rows** (was 65; +19 via the EXP-M5-10 reconciliation and EXP-M5-12 additions) |
| **OBJ-2 backlog** (present, encoding-NYC) | **~61 rows** (was ~72; EXP-M5-10 moved 13 out), in closable waves: **B.1** ISA field-semantics (10 clusters, splice-and-observe — largely untouched), **B.2** cmdstream/descriptor records (**mostly CLOSED by EXP-M5-10**; residual: PPP output-select word, USC-graphics grammar, PBE storage-image, mesh/amplification, tiling/compression, VS→FS linkage), **B.3/B.4** extrapolate-and-test + machine-model (4) |
| Missing hardware functionality (Metal expects but M5 lacks and we did not classify) | **none found** — every gap is "encoding not yet mapped," never "capability unaccounted for" |

**OBJ-2 gate status: closer, not yet passing.** Presence is fully mapped, **no Metal-exposed capability is
unaccounted for or mis-classified** (the OBJ-2 review's blocker + majors + minors are closed — layered
rendering / depth output / sample_mask / RT bbox-curve enumerated, int8-coopmat split, stale FF/TBDR/draw
rows reconciled to their EXP-M5-10 measurements). ~61 capabilities remain **confirmed-present-encoding-NYC**
— **the residual is now dominated by the B.1 ISA-semantics splice wave** (memory/atomics, texture, matrix,
RT, mesh emit, calls, fences, subgroup-reduce), since EXP-M5-10 already closed most of the B.2
cmdstream/descriptor wave. The **single highest-value item** is the **Apple10 Neural Accelerator /
`MTLTensor` path** (B.1 #5) — including where **int8 matmul** lands: confirm whether it lowers to the A18
`0xcf` MAC or a new dedicated neural instruction.

## Provenance / clean-room attestation

Synthesis of `capability-matrix-m5.md` (this OBJ-2 census), the A18 baseline
(`capability-matrix.md` / `capability-completeness.md` / `hypotheses.md`), the M5 baselines
(EXP-M5-04 `m5-capability-matrix.md` + `m5-hardware-overview.md`, EXP-M5-05 ISA tokenization,
EXP-M5-06 + **EXP-M5-10** `docs/cmdstream/README-M5-deltas.md` + `docs/pipeline/README-M5-deltas.md`), and
our own M5 MSL-acceptance probes (EXP-M5-08 `experiments/EXP-M5-08-capability-census/raw/msl_acceptance.txt`
+ **EXP-M5-12** `experiments/EXP-M5-12-capability-reconcile/raw/msl_acceptance_m512.txt`). Presence facts are
driver/compiler responses to our own programs or bytes our own process observed at the IOKit boundary.
No Apple binary was disassembled, decompiled, or otherwise introspected.

## Addendum — REVIEW-M5-OBJ2-02 (EXP-M5-15)
Added to the §B present-but-encoding-NYC backlog:
- **Rasterization rate map / foveated rendering** — presence M5-measured (`supportsRasterizationRateMapWithLayerCount:` YES 1–2 layers); the rate-map BO layout + tiler render-control record are NOT yet probed. New probe target.
- **Vertex attribute fetch** (`MTLVertexDescriptor`→VS-prologue) — the per-attribute load+format-convert lowering rides the `0x18` memory-load split; format-convert map completes with the memory-family field work.
- YUV/YCbCr (⏳ untested), MSAA resolve-filter (store-record field), `MTLFence`/`MTLEvent`/`MTLSharedEvent` (kernel-managed) — enumerated in `capability-matrix-m5.md` addendum.

## Addendum 2 — ISA-integration reconcile (EXP-M5-11)
Moved from §B (NYC) to encoding-characterized: device load/store, subgroup reduce/scan/shuffle, uniform-address
atomics (incl. float-add), compute ALU — now emittable in `tools/agx-isa-m5/db.json` (HW-validated EXP-M5-07/09/11).
Residual §B backlog: texture sampling (EXP-M5-16), divergent-address atomics (EXP-M5-16), simdgroup-matrix MAC
(EXP-M5-16), call ABI (pipeline-linked extraction), RT AS-load (AS-bound testbed), + the rate-map probe (EXP-M5-15).

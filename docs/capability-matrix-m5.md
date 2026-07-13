# Apple M5 (Apple10 / G17g / T8142) — Capability Census & Native-vs-Emulated Matrix

**Objective 2 deliverable** (`ROADMAP-M5.md` §5.2). Enumerates **every** hardware capability the M5
GPU exposes — from (a) the Metal/MSL surface and (b) Apple's advertised Family-10 features — and
classifies how each is realized on the M5: **native / emulated / kernel-managed / NOT-YET-CHARACTERIZED**.

> **Status: synthesis + targeted probe.** The M5 is a **G17g sibling of the A18 Pro (G17P / Apple9)** —
> EXP-M5-01/02/03 measured ~84% ISA byte-overlap, and EXP-M5-06 found the cmdstream/descriptor model is
> "the A18 model with a small set of precise deltas." The method here (per the task and `../CLAUDE.md`)
> is **inherit each A18 classification, then downgrade to NOT-YET-CHARACTERIZED wherever a G17g delta is
> known to touch the encoding and that delta has not yet been re-characterized on M5 hardware.** Presence
> is established from the M5 `MTLDevice` probe (EXP-M5-04) and our own M5 MSL-acceptance probe
> (EXP-M5-08, `raw/msl_acceptance.txt`). No Apple binary was introspected.

## Legend — M5 realization class

| Class | Meaning |
|---|---|
| **✅ native** | Present on M5 **and** its HW representation is available for the M5: either **measured on M5** (EXP-M5-05 tokenization / EXP-M5-06 cmdstream+descriptor) or **inherited from A18 and confirmed transferring** (round-trip-green on the M5 corpus, or measured byte-identical). |
| **❓ NYC** | **Present on M5** (device flag / MSL-accept / advertised) **but its M5 HW representation is NOT yet mapped** — a G17g-delta ISA family whose field-semantics are splice-TODO, or an open cmdstream/descriptor record. **This is the OBJ-2 backlog.** |
| **⛔ emulated** | Absent on M5 (MSL rejects / device flag NO) → a Vulkan/GL driver must software-emulate. |
| **🔥 kernel** | Real HW state routed via the kernel submit (firmware/register-managed). Submission model is **identical** on M5 (EXP-M5-06) → inherited. |
| **⚙ microarch** | Apple-advertised microarchitectural property with **no single emittable encoding** (observable only via throughput/occupancy counters). Inherited NYC. |

**M5-evidence tags** (right column): `M5-measured` = field measured on M5; `M5-delta` = a measured
G17g delta; `inherit✓` = transfers (A18 encoding, round-trip-green / measured identical on M5);
`splice-TODO` = ISA op in a G17g-delta family, leader/length fixed but field-semantics not yet
splice-validated on M5; `open-record` = cmdstream/descriptor record not yet probed on M5;
`device-flag` / `MSL-probe` = presence source.

---

## G17g delta map — what moved from A18 (the axis this census pivots on)

**Measured & characterized on M5 (EXP-M5-05 / EXP-M5-06):**
- **Submission model** — identical (2 clients `IOSurfaceRoot`+`AGXAcceleratorG17G`, shared-mem+doorbell,
  49 compute / 58 draw IOKit calls, sel-9/sel-5 byte-identical). `inherit✓`.
- **Compute CDM record** — shader-ptr/grid/threadgroup SAME; **config word `+0x00`: A18 bit19-base dropped**,
  bit23 = same 2-tier occupancy/register class. Threadgroup-mem size **MOVED +0x40→+0x38** (new segmented
  encoding `0x0c00000f|(fine<<11)|(coarse<<19)`). Arg-buffer Tier-2 table `+0x14a0` byte-identical.
- **Graphics VDM record** — draw opcodes **shifted +0x0800** (`0x61c4→0x69c4`, `0x61f2→0x69f2`);
  primitive-type / counts / restart-comparand / indexed-config SAME. Viewport transform **MOVED +0x910→+0x9d0**.
  FF-state pool `0x58000` same fields, **reorganized offsets** (cull/winding at `+0x1a8`).
- **Texture descriptor** (32 B) — one delta: **width/height bit split shifted +1 bit** (W−1 =
  word0[28:31]‖word1[0:10], H−1 = word1[11:24]); type/format/swizzle/baseVA/sRGB/arrayLen/sampleCount SAME.
  **Sampler descriptor (8 B) byte-identical. Buffer binding identical.**
- **ISA tokenization** — leaders+lengths restored to 96.6% own / 98.0% tp byte-coverage, round-trip green
  (`tools/agx-isa-m5`). `get_sr` HW-confirmed (EXP-M5-01).

**Known G17g ISA deltas whose FIELD-SEMANTICS are NOT yet splice-validated on M5 (→ NYC rows below):**
memory load `0x18` / store `0x41`/`0xc1`; atomics (memory family); typed/sample texture ops
(`0x78`/`0x58`/`0x50`); matrix MAC (`0xcf`); RT ops (`rt_intersect`/`rt_as_load`/`ray_data`); mesh emit;
call/function `0xef`/`0xff`; fence/barrier `0x07`; subgroup reduce/scan `0x3f`; and misc delta leaders
`0x24`/`0x3f`/`0xa0`/`0x3e`/`0xbe`/`0xNe`/`0xb7`. (EXP-M5-02 first-desync list + EXP-M5-05 splice-TODO list.)

**Still-open cmdstream/descriptor records on M5 (→ NYC rows below):** FF-pool per-bit depth/stencil/blend
enums, USC bind-pair grammar, attachment/PBE/storage-image descriptors + packed format word,
indirect/mesh/tessellation records, sample-position BO, tile/imageblock memory, MSAA, memoryless,
load/store actions, occlusion/timestamp, tiling/twiddle + lossless compression, sparse/heap flags.

---

## 1. Shader data types & scalar ALU

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| 32-bit int ALU (add/sub/mul/mad) | YES | ✅ native | `0x9f`/`0x1f` (A18 map; round-trip green) | inherit✓ |
| 32-bit float ALU (add/sub/mul) + FMA | YES | ✅ native | `0x09` falu2 (A18 map; round-trip green) | inherit✓ |
| 16-bit (`half`) ALU, 2 halves/GPR; free FP16↔FP32 | YES | ✅ native | `0x10`/`0x11` half group | inherit✓ |
| `bfloat` general ALU | YES (MSL-probe ACCEPT) | ✅ native | distinct `0x11` bfloat group (A18) | MSL-probe; inherit✓ |
| int↔float convert (RTZ), int↔uint reinterpret | YES | ✅ native | `0x27`/`0xa7`; free reinterpret | inherit✓ |
| min/max (int & float), typed compare→select | YES | ✅ native | `0x02`/`0x12` icmpsel | inherit✓ |
| Boolean logic / **all 16 logic ops** | YES | ✅ native | `0x0b` ilogic 2-input LUT | inherit✓ |
| Float round modes (floor/ceil/trunc/rint) | YES | ✅ native | `0x2f/0xaf` round-mode field | inherit✓ |
| exp2/log2/rcp/rsqrt/sqrt (SFU); sin/cos/tan/pow | YES | ✅ native | `0x2f/0xaf` SFU + poly compose | inherit✓ |
| Shifts / `extract_bits` / `insert_bits`(lowered) | YES | ✅ native | `0x9f`/`0xa7` | inherit✓ |
| popcount / clz / ctz / reverse_bits / rotate | YES | ✅ native | `0x27`/`0xa7` bit ops | inherit✓ |
| min3/max3/median3 (lowered); pack/unpack normalized | YES | ✅ native | `0x02` / `0x97`/`0x17` | inherit✓ |
| 64-bit (`long`/`ulong`) integer ALU (add/sub carry, 32×32→64 mul) | YES | ✅ native | `0x1f`/`0x32`/`0x9f` (A18) | inherit✓ |
| **2× parallel FP16/FP32/int ALU pipelines** | advertised | ⚙ microarch | dual-issue throughput (no opcode) | Family-10; NYC |
| Double precision (fp64) | NO | ⛔ emulated | not exposed by MSL on Apple GPUs | inherit |

**§1 tally: native 13 · emulated 1 · microarch-NYC 1.**

> Note: the M5 census flagged `0x3e/0xbe` "short-ALU" and several multi-word length rules as G17g deltas.
> These are **length-rule** deltas (leader/length restored, round-trip green) — the ALU *capabilities* are
> present and realized natively; only per-field splice-validation on M5 is a downstream ISA-doc (OBJ-1) item,
> not an OBJ-2 presence gap. `bfloat`, MSL-reprobed on M5, ACCEPTs.

---

## 2. Control flow & functions

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| if/else / predication / SIMD divergence | YES | ✅ native | compare→exec-mask→masked op (`0x0f` sub-ops) | inherit✓ |
| Loops / back-edge / break | YES | ✅ native | `0x0f` signed back-edge | inherit✓ |
| Early return / program termination | YES | ✅ native | predication + out-of-band length | inherit✓ |
| Function calls / `[[visible]]` / call-return ABI | YES | ❓ NYC | **call family moved to `0xef`/`0xff`** on M5 (was `0x0f 05`); ABI splice-TODO | splice-TODO |
| Indirect call / `visible_function_table` | YES (`supportsFunctionPointers`) | ❓ NYC | rides the `0xef`/`0xff` call delta | device-flag; splice-TODO |
| Recursion (compute) | YES | ❓ NYC | lowered to call/loop; rides call delta | splice-TODO |
| Function constants (uber-shader) | YES | ✅ native | compile-time fold (no runtime HW encoding) | inherit✓ |
| Dynamic libraries / render dynamic libraries | YES (`supportsDynamicLibraries`) | ❓ NYC | Mach-O `MH_DYLIB`; symbol-resolve at build; call ABI rides `0xef`/`0xff` delta | device-flag; splice-TODO |
| Stack / scratch spill (fill) | YES | ❓ NYC | non-leaf frame link save/restore in the `0x07`/`0x6f` delta families | splice-TODO |
| Shader `printf` / `os_log` | YES | ✅ native (mechanism) | `os_log`→`MTLLogState` buffer (Metal 4 stack; A18 EXP-O2G) | inherit✓ |

**§2 tally: native 5 · NYC 5.**

---

## 3. Memory, address spaces & barriers

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| `device`/`constant` load/store (RW), vectorized | YES | ❓ NYC | **memory load `0x18` / store `0x41`/`0xc1` = the #1 G17g delta** (204 kernels first-desync); field-semantics splice-TODO | splice-TODO |
| `threadgroup` load/store | YES | ❓ NYC | rides the memory `0x18`/`0x41` delta | splice-TODO |
| Sign/zero-extend sub-32-bit loads; element addressing | YES | ❓ NYC | rides the memory delta | splice-TODO |
| Buffer base-pointer / scalar-uniform preload | YES | ✅ native | uniform register file; USC preamble (submission model identical) | inherit✓ |
| **Async completion = HW register interlock** (no scoreboard) | YES | ✅ native | microarch (consumer stalls in HW; no `wait` op) | inherit✓ |
| `threadgroup_barrier` (mem-scope) / atomic fences | YES | ❓ NYC | **`0x07` fence family is a flagged G17g delta**; scope bytes splice-TODO | splice-TODO |
| `simdgroup_barrier` | YES | ✅ native | no op (lockstep SIMD) | inherit✓ |
| Fragment/tilebuffer ordering (`wait_pix`/`signal_pix`) | YES | ❓ NYC | `pixel_order` rides the `0x07` fence delta | splice-TODO |
| Memory order / `coherent(device)` | YES | ❓ NYC | ordering = fence presence (`0x07` delta) | splice-TODO |
| Flexible on-chip memory (unified cache) | advertised | ⚙ microarch | unified L1 (cache-hit counters) | Family-10; NYC |

**§3 tally: native 3 · NYC 6 · microarch-NYC 1.**

---

## 4. Atomics

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Int atomic add/sub/and/or/xor/min/max (signed & unsigned) | YES (MSL-probe) | ❓ NYC | memory-family RMW (rides `0x18`/`0x41`/atomics delta), op byte splice-TODO | MSL-probe; splice-TODO |
| Atomic exchange / store / load / compare-exchange | YES | ❓ NYC | memory-family (rides delta) | splice-TODO |
| **Float atomic add** | YES (MSL-probe ACCEPT) | ❓ NYC | memory-family fadd op (rides delta) | MSL-probe; splice-TODO |
| Atomic scope device vs threadgroup | YES | ❓ NYC | rides memory delta | splice-TODO |
| Texture / image atomics | YES | ❓ NYC | lower to memory-family device atomic (rides delta) | splice-TODO |
| **Float atomic min / max** | **NO** (MSL-probe REJECT) | ⛔ emulated | no MSL path (== A18) | M5-reprobed |
| **All 64-bit atomics (add / min / max)** | **NO** (MSL-probe REJECT, every spelling) | ⛔ emulated | entirely absent from MSL (== A18/EXP-O2D) | M5-reprobed |

**§4 tally: native 0 · NYC 5 · emulated 2.** *(All present atomics ride the un-splice-validated memory
delta → NYC; the two absences are M5-reprobed via our own MSL and transfer from A18.)*

---

## 5. Textures & samplers

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Sample (implicit-LOD) / bias / level / gradient | YES | ❓ NYC | **sample/typed ops `0x78`/`0x58`/`0x50` are a flagged G17g delta**; op-byte semantics splice-TODO | splice-TODO |
| Gather (2×2) / gather_compare / texel-offset variants | YES | ❓ NYC | rides the sample/typed delta | splice-TODO |
| Image read (load) / MSAA sample-indexed read | YES | ❓ NYC | rides the sample/typed delta | splice-TODO |
| Image write (store) | YES | ❓ NYC | store `0xd7`-class rides the memory/store delta | splice-TODO |
| Read-write textures (Tier 2) | YES (`readWriteTextureSupport=2`) | ❓ NYC | write path + image atomics (ride deltas) | device-flag; splice-TODO |
| `sample_compare` (depth PCF, 8 funcs) | YES | ❓ NYC | rides sample/typed delta; sampler compare field measured (below) | splice-TODO |
| Derivatives dfdx/dfdy/fwidth | YES | ✅ native | `0x37` (not a flagged delta; round-trip green) | inherit✓ |
| Texture queries (width/height/mips/samples/array) | YES | ✅ native | preloaded-uniform read from descriptor | inherit✓ |
| Texture types 1D/2D/2DArray/2DMS/3D/Cube/CubeArray/2DMSArray | YES | ✅ native | **descriptor type field measured on M5** (byte0[0:2]; 1D=0/2D=2/2DArray=3…) | M5-measured |
| Texture LOD query (`calculate_clamped_lod`) | YES (`supportsQueryTextureLOD`) | ❓ NYC | rides sample/typed delta | device-flag; splice-TODO |
| Sampler: address modes / filters / mip / LOD clamp | YES | ✅ native | **sampler descriptor (8 B) byte-identical to A18** (addr S/T/R, mag/min/mip, LOD, aniso) | M5-measured |
| Sampler compare (all 8 funcs), unnormalized coords, aniso ≤16× | YES | ✅ native | sampler-descriptor bits (byte-identical, sweeps HW-confirmed) | M5-measured |
| **Arbitrary sampler border color** (Vulkan custom) | NO | ⛔ emulated | only 2-bit 3-preset field (== A18) | inherit (desc identical) |
| Anisotropy >16× | field encodes 128× | ❓ NYC | descriptor field (Metal caps 16×; untested) | inherit; extrapolate-test |

**§5 tally: native 5 · NYC 7 · emulated 1 · extrapolate-NYC 1.**

---

## 6. Subgroup / SIMD-group & quad ops

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| SIMD width = 32 | YES | ✅ native | microarch constant (measured EXP-M5-04) | M5-measured |
| Broadcast / broadcast_first / shuffle (xor/up/down/rotate) | YES | ✅ native | `0x47`/`0xc7` shuffle group (not flagged delta) | inherit✓ |
| Reduce sum/product/min/max/and/or/xor; **prefix scan** | YES (MSL-probe) | ❓ NYC | **`0x3f` simd_reduce is a flagged G17g delta**; dtype/shape bytes splice-TODO | MSL-probe; splice-TODO |
| Ballot / vote / all / any / is_first | YES | ✅ native | `0x17` ballot (not flagged delta) | inherit✓ |
| Quad ops (broadcast/shuffle/reduce, width 4) | YES (MSL-probe `quad_shuffle`) | ✅ native | shuffle group width 4 | MSL-probe; inherit✓ |
| `simd_shuffle_and_fill_up/down` | YES (MSL-probe) | ✅ native | `0x47`/`0xc7` fill variant | MSL-probe; inherit✓ |
| `simd_is_helper_thread` (fragment) | YES | ✅ native | `get_sr` (transfers; `get_sr` HW-confirmed on M5) | inherit✓ |

**§6 tally: native 6 · NYC 1.**

---

## 7. Matrix / cooperative / tensor (Apple10 headline: GPU Neural Accelerator)

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| `simdgroup_matrix` 8×8×8 MAC, dtypes fp16/fp32/**bf16** | YES (MSL-probe ACCEPT fp16/fp32/bf16) | ❓ NYC | **matrix MAC (`0xcf`-equivalent) field map is splice-TODO on M5** | MSL-probe; splice-TODO |
| Matrix accumulate-enable / load/store/make_filled / transpose | YES | ❓ NYC | MAC field map + memory-family load/store (both ride deltas) | splice-TODO |
| MPP `tensor_ops::matmul2d`, cooperative-tensor / other tensor ops | YES (`<metal_tensor>` compiles) | ❓ NYC | A18: all lowered to `0xcf`; **M5 lowering unverified** (see below) | MSL-probe; splice-TODO |
| **Metal 4 `MTLTensor` / GPU Neural Accelerator path** | YES (`newTensorWithDescriptor:error:`=YES) | ❓ NYC | **UNKNOWN whether M5 keeps A18's `0xcf` lowering or adds a dedicated neural/tensor instruction path** — the single highest-value M5 OBJ-2 target | device-flag; NYC |
| **int8 / integer cooperative matrix** | **NO** (MSL-probe REJECT char & int) | ⛔ emulated | all integer coopmat rejected by Metal (== A18) | M5-reprobed |

**§7 tally: native 0 · NYC 4 · emulated 1.**

> **M5-specific escalation.** Apple markets a **Neural Accelerator in each GPU core** for the Apple-Family-10
> / M5 generation. On the A18 (Apple9) every `MTLTensor`/MPP tensor op lowered to the `0xcf` matrix MAC with
> **no** dedicated tensor opcode. Whether the M5 preserves that lowering or introduces a **new dedicated
> neural/tensor instruction path** is **unresolved and is the marquee OBJ-2 characterization item.** The
> `<metal_tensor>` header compiles and `newTensorWithDescriptor:error:` responds YES, so the surface is
> present; the ISA realization is unmapped.

---

## 8. Ray tracing

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| HW ray/box/triangle intersect | YES (`supportsRaytracing`; MSL intersector ACCEPT) | ❓ NYC | **`rt_intersect` field map splice-TODO on M5** | MSL-probe; splice-TODO |
| Acceleration-structure / ray-data node loads | YES | ❓ NYC | `rt_as_load` (rides memory/RT delta) | splice-TODO |
| Intersector object / traversal loop; `intersection_query` (inline) | YES (MSL-probe both ACCEPT) | ❓ NYC | shader BVH-traversal loop + RT ops (splice-TODO) | MSL-probe; splice-TODO |
| AS referenced by 8-byte VA (Tier-2 arg buffer) | YES | ✅ native | 8-byte GPU VA in arg buffer (Tier-2 table measured identical) | inherit✓ |
| Intersection functions / `intersection_function_table` | YES | ❓ NYC | bound as Tier-2 slot; call ABI rides `0xef`/`0xff` delta | splice-TODO |
| `ray_data` payload address space | YES | ❓ NYC | `0x5f`-class (rides RT/memory delta) | splice-TODO |
| **Ray tracing from render** | YES (`supportsRaytracingFromRender`) | ❓ NYC | A18: lowers identically to compute RT; M5 RT ISA splice-TODO | device-flag; splice-TODO |
| **Primitive / instance motion blur** | YES (`supportsPrimitiveMotionBlur`) | ❓ NYC | A18: `rt_intersect` time-form; M5 RT ISA splice-TODO | device-flag; splice-TODO |
| **BVH build + node format** | YES | 🔥 kernel | GPU/firmware builds BVH; node format not userspace-visible; submission model identical on M5 | inherit (submit identical) |
| **RT reorder stage** | advertised | ⚙ microarch | firmware/microarch (RT-scratch counters) | Family-10; NYC |

**§8 tally: native 1 · NYC 7 · kernel 1 · microarch-NYC 1.**

---

## 9. Mesh / geometry pipeline

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| **Hardware mesh shading** (object + mesh stages) | YES (M5 pipeline build SUCCESS, EXP-M5-04) | ❓ NYC | A18: compute-style `0xe7` stores into firmware UVB + `0x70000600` grid-dispatch; **M5 store ISA + mesh-dispatch record splice-TODO/open** | device-build; splice-TODO/open-record |
| Object→mesh amplification grid; `object_data` payload | YES | ❓ NYC | rides the store (`0xe7`/memory) delta + open cmdstream mesh record | splice-TODO/open-record |
| Mesh vertex/prim/index export buffer layout | YES | ❓ NYC | store runs into UVB (rides memory delta); UVB firmware-managed | splice-TODO |
| Vertex amplification 1/2/4/8 | YES (all, EXP-M5-04) | ❓ NYC | amplification cmdstream record not yet probed on M5 | device-flag; open-record |
| **Geometry shaders** | NO (Metal no path) | ⛔ emulated | no HW GS stage → compute-emulate (== A18) | inherit |
| **Transform feedback / streamout** | NO (Metal no path) | ⛔ emulated | no streamout unit → compute-emulate (== A18) | inherit |
| **Tessellation** (`drawPatches`, Apple9+) | YES (family) | ❓ NYC | A18: native VDM patch-dispatch record `0x40`; **M5 tessellation record not yet probed** | inherit; open-record |
| Tessellation compute-emulation fallback | YES | ⛔ emulated | `libagx` optional portable fallback (== A18) | inherit |

**§9 tally: native 0 · NYC 4 · emulated 3.** *(Mesh/tessellation/amplification are all present on M5 but
their M5 encodings — store ISA + the mesh/tess/amplification cmdstream records — are unmapped.)*

---

## 10. Fixed-function raster / blend / depth-stencil

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Face cull / winding order | YES | ✅ native | **FF-pool `0x58000+0x1a8`** cull[1:0]/winding bit16 (measured on M5) | M5-measured/delta |
| Viewport transform + depth range | YES | ✅ native | **`0x68000+0x9d0`** 4 floats {tx,sx,ty,sy} (measured on M5) | M5-measured/delta |
| Indexed/non-indexed draw + primitive type + index-buffer VA | YES | ✅ native | **VDM `0x69c4`/`0x69f2`** (+0x0800 shift, measured); primitive byte / counts / restart SAME | M5-measured/delta |
| Primitive restart (all-ones comparand) | YES | ✅ native | restart comparand tracks index width (measured on M5) | M5-measured |
| Depth/stencil compare (8 funcs) + stencil ops (8) | YES | ❓ NYC | FF-pool depth `~+0x134/+0x16c–0x174`; **per-bit compare/stencil-op enum decode is a follow-up** | open-record |
| **Depth clamp vs clip** (`depthClampEnable`) | YES | ❓ NYC | raster packet clip/clamp field — position in reorganized `0x58000` not yet pinned on M5 | open-record |
| **Polygon line fill** (`POLYGON_MODE_LINE`) | YES | ❓ NYC | raster nibble+flags in reorganized FF-pool — not yet located on M5 | open-record |
| Depth bias (constant/slope/clamp) | YES | ❓ NYC | FF-pool enable + tiler-param floats — not yet located on M5 | open-record |
| **Programmable blend** (any factor/op) / **dual-source** / **16 logic ops** | YES | ✅ native (mechanism) | compiled into fragment shader (TBDR); logic-op via `0x0b` LUT (round-trip green) | inherit✓ |
| Color write mask | YES | ❓ NYC | FF-pool `0x58000` mask bits — reorganized offset not yet pinned on M5 | open-record |
| Provoking vertex / flat-shading (`[[flat]]`) | YES | ✅ native | `iter_flat` `0x1f` (round-trip green) | inherit✓ |
| Alpha-to-coverage / alpha-to-one | YES | ❓ NYC | FS epilog + FF bits in reorganized `0x58000` — not yet located on M5 | open-record |
| Point size (`[[point_size]]`) / clip distances / multi-viewport | YES | ❓ NYC | PPP output-select in reorganized `0x58000` — not yet located on M5 | open-record |
| Polygon **point** fill | NO (Metal-unreachable) | ⛔ emulated | fill/lines only (== A18) | inherit |
| Cull distance / custom restart index | NO (Metal-unreachable) | ⛔ emulated | MSL exposes clip only / always all-ones (== A18) | inherit |
| Scissor test | YES | 🔥 kernel | `isp_scissor_base` submit param (submission identical) | inherit |
| Packed depth24-stencil8 | NO (`depth24Stencil8=NO`) | ⛔ emulated | Z/S separate resources (== A18) | M5-reprobed (device flag) |
| Wide / smooth lines; conditional rendering | Metal caps/absent | ❓ NYC | extrapolate-and-test (Metal line width fixed; cond-render CPU-emulated) | inherit; extrapolate |

**§10 tally: native 6 · NYC 9 · emulated 4 · kernel 1.**

---

## 11. Interpolation / varyings / fragment built-ins

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Varying interpolation (persp/no-persp/flat/centroid/sample) | YES | ✅ native | `iter` `0x2f` family (not a flagged delta; round-trip green) | inherit✓ |
| Pull-model interpolation (`interpolate_at_*`) | YES (`supportsPullModelInterpolation`) | ✅ native | matching `iter_at` qualifier (`0x2f` family) | device-flag; inherit✓ |
| Barycentric-coord built-in | YES (`supportsShaderBarycentricCoordinates`) | ✅ native | interpolated via `0x2f` family | device-flag; inherit✓ |
| Fragment built-ins (primitive_id/sample_id/position/front-facing) | YES | ✅ native | `get_sr` (HW-confirmed on M5) + flat tiler load | inherit✓ |
| Sample-rate shading (`[[sample_perspective]]`) | YES | ✅ native | `iter` mode + `iter_at` setup | inherit✓ |
| `discard_fragment()` | YES | ✅ native | predication (round-trip green) | inherit✓ |
| VS→FS varying linkage (UVS slots) | YES | ❓ NYC | UVS slot layout + `0x58000+0x2c` count in reorganized FF-pool — not yet re-pinned on M5 | open-record |
| Vertex varying store | YES | ❓ NYC | `0x57` store — rides the store/memory delta | splice-TODO |

**§11 tally: native 6 · NYC 2.**

---

## 12. TBDR / imageblock / tile

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Tile size (32×32 fixed?) | present | ❓ NYC | `0x68000` tile-count fields — **re-measure on M5 (8 cores vs A18's 5)** | open-record |
| Tile-memory budget (32 KiB) | YES (`maxThreadgroupMemoryLength=32768`) | ✅ native | budget measured (EXP-M5-04); compute tgmem encoding measured (`+0x38`) | M5-measured |
| Memoryless render targets | YES | ❓ NYC | attachment `+0x24`-class flag — attachment record not yet probed on M5 | open-record |
| Load/store actions (load/clear/dontCare, store/resolve) | YES | ❓ NYC | load/render/store segments — not yet probed on M5 | open-record |
| Hidden Surface Removal (HSR) | YES | ✅ native (implicit) | automatic; no userspace encoding | inherit✓ |
| MSAA sample count (2×/4×/8×; 16=NO) | YES (`supports32BitMSAA`; 16 NO) | ❓ NYC | attachment sample-count field — not yet probed on M5 | device-flag; open-record |
| **Programmable MSAA sample positions** | YES (`programmableSamplePositions`) | ❓ NYC | A18: client BO @+0x40; **M5 sample-position BO not yet probed** | device-flag; open-record |
| Imageblocks (explicit/implicit, `[[color(n)]]` slots) | YES | ❓ NYC | read/write = `0x67`/`0xe7` (ride memory delta); slice addressing splice-TODO | splice-TODO |
| Tile shaders (mid-render compute) | YES | ❓ NYC | inline tile-dispatch in render stream — not yet probed on M5 | open-record |
| Programmable-blend `[[color(m)]]` tile read | YES | ❓ NYC | `tile_read` (rides memory delta) | splice-TODO |
| **Raster order groups** (frag interlock) | YES (`rasterOrderGroupsSupported`) | ❓ NYC | `pixel_order` rides the `0x07` fence delta | device-flag; splice-TODO |
| Depth store-action / ZLS | YES | 🔥 kernel | `ZLS_CTRL` firmware-programmed (submission identical) | inherit |
| Partial-render / tiler-param overflow | YES | 🔥 kernel | firmware detects overflow (submission identical) | inherit |
| Occlusion / visibility queries | YES | ❓ NYC | result-ptr + mode bit in FF-pool — not yet re-located on M5 | open-record |
| Timestamps / GPU counters (STAGE-boundary only) | YES (`counterSets=timestamp`) | ✅ native | u64 ns; stage-boundary only (device flags measured on M5) | M5-measured (device flag) |

**§12 tally: native 3 · NYC 10 · kernel 2.**

---

## 13. Compute dispatch

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Direct dispatch (grid + threadgroup in threads) | YES | ✅ native | **CDM 0x2c-byte record** measured on M5 (grid `+0x10`, tg `+0x1c`) | M5-measured |
| Non-uniform grid (`dispatchThreads`) | YES | ✅ native | grid-in-threads (measured on M5) | M5-measured |
| Threadgroup (shared) memory size | YES | ✅ native | **shader-BO `+0x38` segmented encoding** (measured on M5, HW-validated 16 B…32 KiB) | M5-measured/delta |
| Max threads/threadgroup 1024; occupancy tier | YES | ✅ native | limit (measured); **CDM config `+0x00` bit23** occupancy tier (measured; bit19-base dropped) | M5-measured/delta |
| Shader-code pointer (compute) | YES | ✅ native | **CDM `+0x08 = shaderVA>>6`** (measured on M5) | M5-measured |
| Indirect dispatch (`dispatchThreadgroupsWithIndirectBuffer`) | YES | ❓ NYC | 2nd CDM + grid-setup helper — indirect record not yet probed on M5 | open-record |
| Indirect command buffers / device-generated commands | YES | ❓ NYC | ICB inline state-block+draw — not yet probed on M5 | open-record |
| Draw-mesh into ICB | YES | ❓ NYC | A18: same `0x70000600` mesh record — not yet probed on M5 | open-record |

**§13 tally: native 5 · NYC 3.**

---

## 14. Format support & texture memory layout

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Color/int/float format codes (r8…rgba32f, packed 10a2/11b10/9e5) | YES | ✅ native | **descriptor format code `numtype<<5\|sizeclass` measured on M5** (rgba8=0x0a, r32f=0x88, rgba16f=0x8c, rgb10a2=0x09) | M5-measured |
| Format/swizzle/sRGB/numeric-type orthogonality; full channel swizzle | YES | ✅ native | descriptor fields measured on M5 (swizzle word0[16:27], sRGB word3[12]) | M5-measured |
| Texture width/height/depth/arrayLen/baseVA | YES | ✅ native | **W/H split shifted +1 bit** (measured on M5); baseVA=word2‖word3[0:11] | M5-measured/delta |
| Linear (buffer-backed) layout + stride | YES | ❓ NYC | descriptor stride word — texel-buffer path not yet probed on M5 | open-record |
| Morton/Z-order twiddle (optimal layout); mip-tree packing | YES | ❓ NYC | tiling/twiddle **not yet probed on M5** | open-record |
| Lossless compression aux (placement + flags) | YES | ❓ NYC | compression descriptor/aux **not yet probed on M5** | open-record |
| Block-compressed BC / ASTC / ETC | YES (`supportsBCTextureCompression`) | ❓ NYC | sizeclass codes + twiddle — not yet probed on M5 | device-flag; open-record |
| depth16unorm / stencil8 / depth32float | YES | ✅ native | reuse color codes (format code measured on M5) | M5-measured |
| Extended-range/wide-gamut/16-bit snorm/unorm variants | YES | ✅ native | numtype orthogonal (measured on M5) | M5-measured |
| 3D/cube/array/MSAA twiddle layout; sample interleave | YES | ❓ NYC | tiling **not yet probed on M5** | open-record |
| Sparse / tile textures (16 KiB tile) | YES (`sparseTileSizeInBytes=16384`) | ❓ NYC | sparse-tier descriptor flag + PTE mapping — not yet probed on M5 | device-flag; open-record |
| 32-bit float texture filtering | YES (`supports32BitFloatFiltering`) | ✅ native | unconditional; nearest/linear = sampler filter field (byte-identical sampler) | device-flag; inherit✓ |
| Per-format renderable / PBE storage-image descriptor | YES | ❓ NYC | PBE/storage-image descriptor **not yet probed on M5** | open-record |
| Lossless compression block codec | (HW) | ⚙ microarch | opaque codec (disable-fallback) | inherit; opaque |

**§14 tally: native 6 · NYC 7 · microarch-NYC 1.**

---

## 15. Machine model / Dynamic Caching / binding

| Capability | Present on M5 | Class | HW representation (M5) | Evidence |
|---|---|---|---|---|
| Addressable 32-bit GPRs; 2 halves/GPR | YES | ❓ NYC | register-file footprint — **re-confirm GPR count/width on M5** (`__GPU_METADATA`) | open (Phase 1.4) |
| Uniform register file + uniform program | YES | ✅ native | per-source GPR-vs-uniform mode bit (round-trip green) | inherit✓ |
| Occupancy 2-level tier | YES | ✅ native | **CDM `+0x00` bit23** (measured on M5) | M5-measured |
| Spill to per-thread scratch above GPR limit | YES | ❓ NYC | non-leaf frame link save/restore in `0x07`/`0x6f` delta families | splice-TODO |
| **Dynamic Caching** (register file as cache) | advertised | ⚙ microarch | static model transfers; dynamic alloc curve = counters | Family-10; NYC |
| Argument buffers Tier 2 / bindless | YES (`argumentBuffersSupport=Tier 2`) | ✅ native | **Tier-2 table `+0x14a0`, 8-byte slots byte-identical** (measured on M5) | M5-measured |
| Buffer / texture / sampler binding via arg buffer | YES | ✅ native | buffers inline VA; tex/samp ptr-to-descriptor (measured on M5) | M5-measured |
| Sampler heap (large count, bindless `gpuResourceID`) | YES (`maxArgumentBufferSamplerCount=500000`) | ✅ native | 8-byte `gpuResourceID` index (arg-buffer model measured identical) | device-flag; inherit✓ |
| Special-register (SR) enum + preload ABI; sysvals | YES | ✅ native | `get_sr` HW-confirmed on M5 (EXP-M5-01); sysvals via `get_sr` on demand | M5-measured (get_sr) |
| **Graphics shader-entry bind** (draw carries no `shaderVA>>N`) | YES | 🔥 kernel | code-BO base reaches firmware out-of-band (submission identical) | inherit |

**§15 tally: native 6 · NYC 2 · kernel 1 · microarch-NYC 1.**

---

## Summary counts (M5)

| Class | Count | What it means for a Vulkan/GL implementer on M5 |
|---|---|---|
| **✅ native** | **65** | Present on M5 and its HW representation is available: measured on M5 (EXP-M5-05/06) or inherited from A18 and confirmed transferring (round-trip-green / measured identical). Emit as documented. |
| **❓ NYC (present, encoding unmapped)** | **72** | **The OBJ-2 backlog.** Confirmed present on M5 (device flag / MSL-accept / advertised) but the M5 HW encoding is not yet mapped — a G17g-delta ISA family whose field-semantics are splice-TODO (46), or an open cmdstream/descriptor record (26). |
| **⛔ emulated** | **15** | Absent on M5 → software-emulate. 6 re-probed on M5 via our own MSL/device flags (float atomic min/max, all 64-bit atomics, int8/int coopmat, no-D24S8); the rest inherit from A18 (fp64, arbitrary border color, polygon-point fill, cull distance, custom restart index, geometry shaders, transform feedback, compute-tess fallback). |
| **🔥 kernel-managed** | **5** | RT BVH build, ZLS/depth store, partial-render trigger, scissor, graphics shader-entry bind. Submission model is identical on M5 → transfer. |
| **⚙ microarch-NYC** | **7** | 2× ALU, flexible on-chip memory, Dynamic Caching dynamic behavior, RT reorder stage, lossless compression codec, full occupancy curve — no single emittable encoding (counters only). Inherited. |

Per-section (native / NYC / emulated / kernel / microarch-NYC):
§1 13/0/1/0/1 · §2 5/5/0/0/0 · §3 3/6/0/0/1 · §4 0/5/2/0/0 · §5 5/8/1/0/0 · §6 6/1/0/0/0 ·
§7 0/4/1/0/0 · §8 1/7/0/1/1 · §9 0/4/3/0/0 · §10 6/9/4/1/0 · §11 6/2/0/0/0 · §12 3/10/0/2/0 ·
§13 5/3/0/0/0 · §14 6/7/0/0/1 · §15 6/2/0/1/1.
**Totals: native 65 · NYC 72 · emulated 15 · kernel 5 · microarch-NYC 7 = 164 capability rows.**
(§5 aniso>16× and §10 wide-lines/cond-render counted under NYC as extrapolate-and-test items.)

### The two OBJ-2 truths for M5

1. **Presence is fully mapped; encoding is partially mapped.** Every Metal-exposed and Apple-advertised
   capability is **enumerated and its presence confirmed** on M5 (device probe EXP-M5-04 + our MSL probe
   EXP-M5-08). No Metal-exposed capability is missing from this census.
2. **The OBJ-2 backlog (72 NYC) is "present-but-encoding-unmapped," not "absent."** It splits into
   (a) **ISA field-semantics splice-TODO** for the G17g-delta families (memory/atomics, texture-sample,
   matrix, RT, mesh emit, call/function, fence/barrier, subgroup-reduce) — the ISA-semantics wave; and
   (b) **open cmdstream/descriptor records** (FF-pool enums, attachment/PBE, tessellation/mesh/indirect
   records, tiling/compression, sparse, sample positions, tile size). Closing these is a
   re-characterization effort on M5 hardware, **not** a discovery of new missing hardware functionality.

### Absences a Vulkan/GL driver on M5 must emulate (negative results, HW-confirmed)

float atomic min/max; all 64-bit atomics (add/min/max); int8/integer cooperative matrix; fp64; packed
depth24-stencil8; sampleCount 16; arbitrary sampler border color; polygon-point fill; cull distance;
custom primitive-restart index; geometry shaders; transform feedback. The first six are **re-confirmed on
M5** (our own MSL / device flags, EXP-M5-08); the rest inherit from A18's HW-validated absences.

## Clean-room attestation

Every M5 presence fact is a value the Metal driver returned to our own program (EXP-M5-04 device probe),
the compiler's ACCEPT/REJECT of **our own** MSL (EXP-M5-08, `raw/msl_acceptance.txt`), or a byte our own
process observed crossing the IOKit boundary (EXP-M5-06). Every classification is either measured on M5 or
inherited from an already-established A18 finding in `docs/` (cited). No Apple binary was disassembled,
decompiled, or introspected. Reproducible via the cited experiments' `run.sh`/probe sources.

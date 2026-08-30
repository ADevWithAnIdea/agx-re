# A18 Pro (G17P) Native-vs-Emulated Capability Matrix

A **decided** capability matrix for a Vulkan/GL implementer targeting the A18 Pro (G17P / Apple9):
for each feature, **is it hardware-native**, what is the **evidence**, and what is the
**implication** for the driver (emit a native instruction / packet, software-**emulate**, or route
to the **kernel/firmware**).

> **Status: synthesis (host-only).** Every row is decided from an already-established finding in
> `docs/` — the Evidence column cites the source. This introduces **no new RE**; it consolidates
> `hypotheses.md` and the subsystem docs into the single "native-vs-emulated" decision document
> that `mesa-userspace-requirements.md` §2g and `reviews/GAP-ANALYSIS-01.md` (gap #11) call for.
> Rows the docs mark **untested / unknown** are labelled as such — this matrix is honest about what
> is *decided* vs *still open*.

> **Legend — HW-native?**
> - **✅ Native** — the hardware does it; there is a native instruction / packet / descriptor field.
> - **⛔ Emulate** — the hardware lacks it, or Metal does not expose it and no HW path is proven →
>   the Vulkan/GL driver must software-emulate.
> - **🔥 Kernel/FW** — real hardware state, but firmware/register-managed → routed via the kernel
>   submit, not emitted by userspace (see `kernel-interface.md`).
> - **❓ Unknown** — MSL/Metal exposes it or the docs suspect it, but the A18 HW encoding is **not
>   yet shown** in `docs/`; treat as an open probe, do not rely on it.

---

## 1. Native — emit a native instruction / packet / descriptor field

| Feature | HW-native? | Evidence (doc §) | Implication |
|---|---|---|---|
| **Dedicated matrix / cooperative-matrix unit** | ✅ Native | `isa/README.md` "Dedicated matrix unit" (EXP-0022); `hypotheses.md` #16 | Single novel opcode **`0xcf`**, 8×8×8 tile MAC (512 MACs). fp16 / fp32 / bfloat / mixed→fp32. Larger shapes software-tiled over the 8×8×8 primitive. Emit `0xcf`, don't lower to FMA. |
| **Hardware ray tracing (hybrid)** | ✅ Native (hybrid) | `isa/README.md` "Hardware ray tracing" (EXP-0023); `hypotheses.md` #17; `hardware-overview.md` §3 (`supportsRaytracing=YES`) | Dedicated **`rt_intersect`** + **`rt_as_load`** ISA driving a **compiler-generated traversal loop** (not one fire-and-forget op). AS referenced by 8-byte VA in the arg buffer. **BVH build/node-format is firmware-managed** → see `capability §3` and `kernel-interface.md` §4.1. |
| **Programmable blend (any factor / op)** | ✅ Native (via shader) | `cmdstream/README.md` "Blend is programmable" (EXP-0019); `hypotheses.md` #12 | Blend factors/ops are **lowered into the fragment shader's blend microprogram** (Apple TBDR model), *not* a fixed-function LUT. Driver **must compile blend state into fragment shaders** (as Asahi does for M1/M2). `0x58000` keeps only write-mask + blend-class/constant/enable flags. |
| **Framebuffer logic ops (all 16 boolean funcs)** | ✅ Native | `isa/README.md` "Bitwise" (EXP-0013); `hypotheses.md` #1 | The `0x0b ilogic` op is a **full 2-input LUT covering all 16 boolean functions** → **every Vulkan/GL logic op is a single native instruction** (routed through the same FS path as blend). |
| **Depth clamp (`depthClampEnable`)** | ✅ Native | `cmdstream/README.md` "Rasterizer packet" (EXP-0019); `hypotheses.md` #11 | Native **2-bit depth clip-vs-clamp field, raster packet bits [11:10]**. Good for Vulkan depth-clamp; no emulation. |
| **Dual-source blend** | ✅ Native (via shader) | `cmdstream/README.md` "Blend is programmable" (EXP-0019); `hypotheses.md` #12 | Works through the programmable-blend **shader path** (same as blend/logic-op). Emit dual-source output via the FS epilog; no fixed-function field. |
| **Polygon line fill (`POLYGON_MODE_LINE`)** | ✅ Native | `cmdstream/README.md` "Rasterizer packet" (EXP-0019); `hypotheses.md` #13 | Raster nibble **`0x5`** + flags **bit26**. (Polygon-**point** fill only partially confirmed — treat point-fill as ⏳.) |
| **Subgroup prefix-scan (inclusive/exclusive)** | ✅ Native | `isa/README.md` "Subgroup / SIMD-group" (EXP-0018); `hypotheses.md` #10 | Single **`simd_reduce`** scan op (byte+7 shape `0x0b` exclusive / `0x09` inclusive), **not** a shuffle-tree lowering. SIMD width = **32**. |
| **Float round modes (floor/ceil/trunc/nearest)** | ✅ Native | `isa/README.md` "Transcendental/round group" (EXP-0013); `hypotheses.md` #2 | Round-mode field **byte+8** of the `0x2f/0xaf` group: 0=nearest, 2=floor, 4=ceil, 6=trunc. All four HW-validated. Gives GL/Vulkan rounding for free. |
| **One-op typed compare (float/sint/uint)** | ✅ Native | `isa/README.md` "Compare condition codes" (EXP-0013); `hypotheses.md` #3 | Single **`0x12` icmpsel** with a type field (bits[1:3] = float/uint/sint, bit0 = lt/gt) handles all comparisons in one op. |
| **Texture format / swizzle / sRGB / numeric-type orthogonality** | ✅ Native | `descriptors/README.md` "Capability notes" (EXP-0015); `hypotheses.md` #6 | Fully **orthogonal (Vulkan-shaped)**: `bgra8 = rgba8 + swizzle`, `depth32f = r32f` code, sRGB is an independent flag. Maps directly to Vulkan format/swizzle without lowering. |
| **Separate texture-read vs image-write paths** | ✅ Native | `isa/README.md` "Texture / sample family" (EXP-0016); `hypotheses.md` #7 | Read = format-converting **sampler op** (`0xb0/0x90`); write = **`0xd7` store** (memory family), *not* the sampler path. Relevant for Vulkan storage images. |
| **Native single-RMW atomics (int add/sub/and/or/xor/min/max/xchg/cmpxchg, + float-add)** | ✅ Native | `isa/README.md` "Atomics" (EXP-0018) | Native single-RMW ops in the memory family (`0x67`), op at byte+12 — **including `fadd` (`0x26`)**. `cmpxchg` is one op + a compare (no CAS loop). Emit natively. *(Float min/max and all 64-bit atomics are the exception — see §2.)* |
| **Programmable MSAA sample positions** | ✅ Native | `pipeline/README.md` MSAA § (EXP-0021/RT-4); `hypotheses.md` #15 | **Userspace-emittable, NOT kernel-managed (RT-4 corrects EXP-0021):** written to a **client BO** (`0x100000e8000` 4× / `0x100000e0000` 2×) at **+0x40** — an array of N `(x,y)` f32 pairs on a **1/16 grid**. EXP-0021's "byte-identical" diffed the wrong BOs. Emit directly into the sample-position BO; do **not** route via the kernel. |
| **Tessellation (native hardware stage)** | ✅ Native | `cmdstream/README.md` "Tessellation — NATIVE hardware stage" (EXP-O2H); `PROVENANCE.md` (EXP-O2H) | **A18 has NATIVE HW tessellation (corrects the M1/M2 compute-emulation default):** `drawPatches` → native VDM patch-dispatch record **`0x40`**, half-float factor buffer (`MTLTessellationFactorsHalf`), ordinary post-tess `__vertex` shader; domain generator firmware-managed. NOT compute-emulated. The `libagx` compute-emulation path is now an **OPTIONAL** portable fallback. (GS + transform feedback stay emulate — §2.) |
| **Native single-instruction 64-bit integer ADD (with internal carry)** | ✅ Native — `target: G16G` | `isa/README.md` "Native single-instruction 64-bit integer ADD" (EXP-0146); `hypotheses.md` #24 | `ulong` subtract compiles to **one** arithmetic op (`iadd2`, `1f 01 56 00 02 08 00 50 17 05`). Flipping **byte0 bit 7, `0x1f` → `0x9f`**, gives an exact **64-bit ADD with carry across the 32-bit word boundary** — the carry is produced *inside* the single instruction. **Apple's compiler emits a 5-instruction chain instead**, so this is unreachable from Metal. Verified against an independently recomputed oracle on all 8 boundary rows, 5/5 serial reps, both gated runs. **LIMITATION:** validated by flipping one bit in the compiler's own 64-bit subtract, **not synthesized from scratch**; the operand-widening byte was located (byte+7 `0x50` vs `0xA8`) but not isolated. *(Distinct from 64-bit **atomics**, which do not exist — §2.)* |
| **Sampler anisotropy beyond Metal's 16× cap — up to at least 128×** | ✅ Native — `target: G16G` | `descriptors/README.md` sampler §; `hypotheses.md` #5 (EXP-0136) | **Metal's 16× cap is pure software.** Patching the live descriptor-pool entry (our own process; descriptor **data**, no Apple binary read or modified) to aniso values Metal's API cannot produce yields a monotonic, **threshold-exact** quality effect: sharpness flips crisp exactly when `patched_aniso ≥ ratio` — ratio 16 blurs at 1/2/4/8 and is crisp from 16; ratio 64 blurs at 16/32, crisp from 64; ratio 128 blurs at 16/32/64, crisp at 128. Descriptor nibble = `log2(aniso)`; patched codes 5/6/7 read back intact. **Supersedes the earlier "field can encode 128×, >16× not yet run" status.** |
| **Matrix multiply-SUBTRACT (`A·B − C`) and a half-tile sign variant** | ✅ Native — `target: G16G` | `isa/README.md` "The matrix unit also computes `A·B − C`" (EXP-0147) | `matrix_mac` byte+11 bits 1–2 (`b11hi` bits 0–1) are **accumulator sign controls resolved per tile row**, not padding: `0`→`+C` both halves, `1`→`−C` rows 0–3, `2`→`−C` all rows (**full `A·B − C`**), `3`→`−C` rows 4–7. Correct `A·B + C` therefore requires **`(b11hi & 3) == 0`** (32 of 128 values). `simdgroup_multiply_accumulate` never emits any of the other three. Also resolved: `dst_desc` correct iff **bit6 = 1, bit7 = 0**; 128 of 256 values **silently zero**. `matrix_mac` is now **EMITTABLE**. |
| **A second way to materialise an immediate: `uniform_mov` with `usrc ≥ 0x80`** | ✅ Native — `target: G16G` | `isa/README.md` "MOV / select / uniform-move families" (EXP-0140) | **`usrc ≥ 0x80` materialises the immediate `usrc & 0x7F`** into the destination GPR — a 7-bit immediate move, *not* a uniform read (**128/128** matched a host oracle). Below `0x80` it selects a uniform register, **pair-quantised** (`usrc` and `usrc ^ 1` read the same 32-bit word; consecutive uniforms step by 4); unallocated uniform indices return a **silent zero**. So an emitter has two independent 7-bit constant-materialisation paths: `mov_imm` and this. Previously documented as a uniform read only. |
| **Primitive restart** | ✅ Native | `cmdstream/README.md`; EXP-0136 | **Upgraded to HW-VALIDATED (EXP-0136):** triggers at **exactly and only the all-ones sentinel**; adjacent values are used as **literal out-of-bounds indices with no fault**. |

**Count: 20 native capabilities** (15 established through EXP-O2H; **5 added 2026-08-28** from the emitter wave and the Metal-unreachable-encoding probe — native 64-bit integer ADD, anisotropy >16x, matrix multiply-subtract, the `uniform_mov` immediate form, and primitive restart upgraded to HW-VALIDATED. All five are `target: G16G`.)

---

## 2. Emulate — the hardware lacks it, or Metal exposes no path (Vulkan/GL must software-emulate)

| Feature | HW-native? | Evidence (doc §) | Implication |
|---|---|---|---|
| **Float atomic min / max** | ⛔ Emulate | `isa/README.md` "Atomics" (EXP-0018); `hypotheses.md` #9 | MSL rejects `atomic_fetch_min/max<float>` — **not exposed**. Only float atomic **add** exists natively. Vulkan float-atomic min/max → **emulate** (e.g. int-bitcast CAS loop). |
| **64-bit atomics (add / min / max)** | ⛔ Emulate | `isa/README.md` "Atomics" (EXP-O2D corrects EXP-0018); `hypotheses.md` #9 | **ALL** 64-bit atomics are rejected by MSL — every `atomic<ulong/long/uint64_t>` spelling (add **and** min/max). The earlier "64-bit min/max exist" claim was **WRONG** (EXP-O2D corrects EXP-0018): there is no reachable HW path → **emulate**. |
| **Arbitrary sampler border color** | ⛔ Emulate | `descriptors/README.md` "Sampler descriptor" + "Capability notes" (EXP-0015); `hypotheses.md` #4 | The 8-byte sampler encodes only a **2-bit preset** (transparent / black / white). Arbitrary Vulkan RGBA border color must be **emulated** (Mesa's M1/M2 uses a 2-sampler-plane trick — `mesa-userspace-requirements.md` §4). Also: `clampToZero == clampToBorder(transparent-black)` (one HW mode). **Reinforced by EXP-0136 (`target: G16G`): border colours beyond the 3 presets do not exist — the 4th 2-bit code aliases to preset 0 from all three creation contexts**, so there is no hidden fourth colour to reach by patching the descriptor. |
| **int8 cooperative matrix** | ⛔ Emulate | `isa/README.md` "Dedicated matrix unit" (EXP-0022) | The `0xcf` matrix unit supports fp16/fp32/bf16 only; **all integer types are rejected** by Metal for `simdgroup_matrix`. Vulkan int8 cooperative-matrix → **emulate** (integer MAC in the ALU). |
| **Geometry shaders** | ⛔ Emulate — **DECIDED** (`target: G16G`) | `mesa-userspace-requirements.md` §2g / §4; **EXP-0136** | ~~*A18 status not independently probed; treat as emulate until shown otherwise.*~~ **SETTLED by EXP-0136: native geometry shaders / stream output DO NOT EXIST.** `rasterizationEnabled = NO` runs the **vertex stage** (proven by its atomic side effect) on the **same VDM/tiler path** with the fragment stage merely elided — there is no separate geometry or streamout unit to reach. GL/Vulkan GS must be **permanently emulated** (VS→GS lowering, 4 sub-programs); this is no longer a carried-over assumption. Measured on M4/G16G; not revalidated on G17P. |
| **Transform feedback / streamout** | ⛔ Emulate — **DECIDED** (`target: G16G`) | `mesa-userspace-requirements.md` §2g / §4 (`agx_streamout.c`); **EXP-0136** | ~~*A18 streamout unit not independently probed.*~~ **SETTLED by EXP-0136 together with the GS row above: there is no stream-output unit** — the `rasterizationEnabled = NO` path is the ordinary VDM/tiler vertex path with the fragment stage elided. GL/Vulkan XFB must be **permanently emulated**. Measured on M4/G16G; not revalidated on G17P. |
| **Wide lines** (`wideLines` / `glLineWidth`) | ⛔ Emulate (`target: G16G`) | `pipeline/README.md` "Rasterization rules" (EXP-0123) | Through the **documented public API** there is no line-width, line-rasterization-mode or conservative-raster control anywhere in the SDK headers; every line renders at the same fixed narrow band regardless of documented pipeline/encoder state. **Expand each line into a quad/triangle pair** in a geometry stage or vertex shader. *(An undocumented private selector was observed to have an effect and was ruled **OUT OF BOUNDS** — see the clean-room ruling in `pipeline/README.md`; it backs no claim.)* |
| **Polygon mode POINT** (`VK_POLYGON_MODE_POINT` / `GL_POINT`) | ⛔ Emulate (`target: G16G`) | `pipeline/README.md` "Rasterization rules" (EXP-0123) | `MTLTriangleFillMode` is a functionally distinct **two**-valued enum (`.fill` 72 lit px / `.lines` 38 lit px on the same reference triangle) with **no third case**. **Re-emit each triangle's three vertices as a point-topology draw.** (Fill mode is inert for line-topology primitives — a functioning no-op.) |
| **Conservative rasterization** | ⛔ Emulate (`target: G16G`) | `pipeline/README.md` "Rasterization rules" (EXP-0123) | **Clean negative with no API surface at all.** Four tiny triangles each covering ~0.2×0.2 px at a *corner* of pixel (4,4), explicitly not its centre, lit **zero pixels in all four cases, both runs** — exactly what standard centre-sample rasterization predicts. **Inflate primitive edges outward by the pixel diagonal** in the vertex/geometry stage. |
| **Last-vertex provoking convention** (OpenGL default) | ⛔ Emulate (`target: G16G`) | `cmdstream/README.md` "Varying / UVS capacity and pre-raster output boundaries" (EXP-0097) | **The provoking vertex is FIXED to the first-fetched vertex** — confirmed via a triangle list, a reversed-index list and a strip — **with no Metal API alternative.** A GL driver must emulate the last-vertex default by **index rewriting or attribute duplication**. |

**Count: 10 emulate capabilities — all ten HW-validated as absent/not-exposed via our own
probes.** The original six: float-atomic-min/max, all-64-bit-atomics, arbitrary border color and int8 coopmat were
already measured; **GS and transform feedback stopped being carried-over assumptions on
2026-08-28**, when EXP-0136 showed `rasterizationEnabled = NO` runs the vertex stage on the same
VDM/tiler path with the fragment stage elided — there is no geometry or streamout unit
(`target: G16G`, not revalidated on G17P). **Four more were added 2026-08-28 from EXP-0123 and
EXP-0097** (`target: G16G`): wide lines, polygon-mode POINT, conservative rasterization, and the
last-vertex provoking convention — each a clean measured negative with a named emulation path.
**Tessellation is NO LONGER here — it is NATIVE HW (EXP-O2H), see §1.**

---

## 3. Kernel / firmware-managed — real HW state, routed via the kernel submit (not emitted by userspace)

See `kernel-interface.md` for the full contract and the G-11 reconciliation. Userspace **computes
the value** and hands it to the kernel; the **firmware writes the register**.

| Feature | HW-native? | Evidence (doc §) | Implication |
|---|---|---|---|
| **Depth store-action / ZLS** | 🔥 Kernel/FW | `pipeline/README.md` load/store § (EXP-0021) | ZLS control not captured in any BO; userspace computes `zls_ctrl` + depth/stencil buffers → kernel submit (`kernel-interface.md` §4.3/§6.1). |
| **RT acceleration-structure (BVH) build + node format** | 🔥 Kernel/FW | `isa/README.md` RT § (EXP-0023) | Userspace supplies vertices + build descriptor + an 8-byte AS VA; the **GPU/firmware builds the BVH**; node format is **not userspace-visible** (`kernel-interface.md` §4.1). (The *traversal* ISA is native — see §1.) |
| **Partial-render / tiler-param overflow trigger** | 🔥 Kernel/FW | `pipeline/README.md` partial-render § (EXP-0021) | No userspace knob for the trigger; userspace supplies `partial_bg`/`partial_eot` programs; firmware detects overflow and triggers the partial render (`kernel-interface.md` §4.4). |

**Count: 3 kernel/firmware-managed capabilities.** (Sample positions were moved OUT of this bucket
by RT-4 → they are **userspace-emittable / native**, §1.)

---

## 4. Unknown / untested — do not rely on; open probes

Honest carry-over of what the docs mark unresolved. These are **not decided** and must be probed
before an implementer commits to native vs emulate.

| Feature | Status | Evidence (doc §) | Note |
|---|---|---|---|
| **Graphics code-window / VS+FS selector mapping** | ❓ Partial/open | `cmdstream/README.md`; EXP-0042 | M4 proves separable VDM VS token and FS window-relative selector. Exact queue `usc_exec_base`, general token construction, HW/FW consumer and A18 behavior remain open; it is not proven kernel-managed. |
| **Mesh shaders** | ✅ Native (EXP-0030 A18; **re-validated on M4, EXP-0135**) | `mesa-userspace-requirements.md` §4; `hypotheses.md` backlog; `GAP-ANALYSIS-01.md` gap #10 | **Native HW graphics pipeline** (EXP-0030): object/mesh compile as compute-style `0xe7`-store kernels + a child-count write; submission reuses the graphics TA/VDM path with a mesh-grid-dispatch record `0x70000600` (no CDM); UVB output buffer is firmware-managed. EXP-0135 re-ran this on M4 rather than assuming transfer and found **no divergence** (helper lengths 128 B / 576 B identical, `43 00 00 01` marker invariant, IOKit call count 58 = ordinary draw). **Two hard limits a driver must self-enforce:** grid amplification tops out at **exactly 65,536** and going over produces *silently zero* output — no error, `CMDBUF_STATUS` still 4 — while Metal reflects `meshGridMax=1048576`, 16× higher; and the object→mesh payload ceiling is **exactly 16,384 B**, enforced at pipeline creation (16384 builds, 16385 fails). `payloadMemoryLength` also accepts values *smaller* than the declared struct with no validation. See `isa/README.md` + `cmdstream/README.md`. |
| ~~**Geometry shaders / transform feedback — A18-native?**~~ | ⛔ **RESOLVED — Emulate, see §2** (`target: G16G`) | `mesa-userspace-requirements.md` §4; **EXP-0136** | **EXP-0136 settles it: native geometry shaders / stream output DO NOT EXIST.** `rasterizationEnabled = NO` runs the vertex stage (atomic side effect proves it) on the same VDM/tiler path with the fragment stage elided. GL/Vulkan GS + XFB must be permanently emulated. Measured on M4/G16G; **G17P revalidation is under way (EXP-0153)**. **Tessellation stays DECIDED: NATIVE HW (EXP-O2H) — see §1.** |
| ~~**Anisotropy > 16×**~~ | ✅ **RESOLVED — Native, see §1** (`target: G16G`) | `descriptors/README.md`; `hypotheses.md` #5; **EXP-0136** | ~~*>16× not yet run on hardware; don't assume it works.*~~ **It works, to at least 128×, threshold-exact** — Metal's 16× cap is pure software. Moved to §1. |
| **Polygon-point fill; extra gather/offset sample variants; 1D/CubeArray/MSArray texture types** | ❓ Unknown / ⏳ | `cmdstream`/`descriptors`/`isa` (EXP-0016/0015) | Spare encodings exist but specific variants are untested; several texture *types* are ⏳. |
| **BC/ASTC/ETC twiddle; 3D/cube/array/MSAA layout** | ✅ Native (EXP-0028) | `tiling/README.md` §1.5/§1.6, `descriptors/format-table.md` | BC/ASTC = Morton-of-blocks (HW-confirmed); 3D=stacked Morton planes; array/cube=linear-stacked planes; MSAA=sample-major. Only the **compression block codec** stays opaque (documented disable-fallback). |

---

## 5. Summary counts

| Bucket | Count | Members |
|---|---|---|
| **✅ Native** | **20** | matrix (`0xcf`), hybrid RT, programmable blend, logic ops (16-func LUT), depth clamp, dual-source blend, polygon line fill, subgroup prefix-scan, float round modes, typed compare, format/swizzle/sRGB orthogonality, separate read/write texture paths, native single-RMW atomics, **sample positions (userspace-emittable @+0x40, RT-4)**, **native tessellation (VDM patch-dispatch `0x40`, EXP-O2H)**, **+5 added 2026-08-28 (`target: G16G`): native 64-bit integer ADD (EXP-0146), anisotropy to ≥128× (EXP-0136), matrix multiply-subtract `A·B − C` (EXP-0147), the `uniform_mov usrc ≥ 0x80` immediate form (EXP-0140), primitive restart upgraded to HW-VALIDATED (EXP-0136)** |
| **⛔ Emulate** | **10** | float atomic min/max, all 64-bit atomics (add/min/max), arbitrary sampler border color, int8 cooperative-matrix, **geometry shaders and transform feedback — now measured absent, not assumed (EXP-0136)**, **+4 added 2026-08-28 (`target: G16G`): wide lines, polygon-mode POINT, conservative rasterization (EXP-0123), last-vertex provoking convention (EXP-0097)** |
| **🔥 Kernel/FW** | **3** | ZLS/depth store, RT BVH build, partial render |
| **❓ Unknown/untested** | **2 clusters** (was 4) | Graphics code-window/selector mapping; polygon-point & exotic gather/tex-type variants. **Resolved 2026-08-28: aniso >16× → ✅ native (§1); GS/XFB → ⛔ emulate, measured (§2).** (Mesh, **tessellation**, BC/3D/cube/MSAA tiling ✅ native; compression codec opaque.) |
| **⚠️ Silent-failure limits a driver must self-enforce** | **12** | See §6 — mesh amplification 65,536; object→mesh payload 16,384 B; `tile_read` read-enable; attachment `slice` destroys slice 0; `unorm16` ties round DOWN; `ibfe` offset literal / width mod-32; `device_load` R ≥ 64; `matrix_mac` descriptors; format-eligibility `abort()`; swizzle codes 6/7 fault; `fspecial` bit 7 hangs; `get_sr`/`psel`/`ret` control bytes |

**Honesty note (per `../CLAUDE.md`).** All **6** "emulate" rows are now HW-validated absences from
our own probes: float atomic min/max, all 64-bit atomics, arbitrary border color and int8 coopmat
were already measured, and **GS / transform feedback stopped being an inherited assumption on
2026-08-28** — EXP-0136 showed the `rasterizationEnabled = NO` path is the ordinary VDM/tiler
vertex path with the fragment stage elided, so no geometry or streamout unit exists to reach.
**Tessellation is NOT emulate: it is NATIVE HW (EXP-O2H)** — see §1. **Mesh shading is native
(EXP-0030, re-validated on M4 by EXP-0135)** — HW graphics pipeline with store-based emit.

**Target discipline for this matrix (read before relying on any row).** The 15 original rows were
established on **A18 Pro / G17P**. The five rows added on 2026-08-28, the two "emulate" rows
settled the same day, and every row of §6 were measured on **M4 / G16G** and are labelled
`target: G16G`. All live testing has since moved to the A18 Pro / G17P and **closure is measured
against full G17P** (`CODEX.md`, "Target discipline"); the M4 evidence stays **valid on its own
target** and is not retracted, but it is **not** relabelled G17P. **G17P revalidation is under way
(`EXP-0153`)**, and cross-target promotion requires a recorded validation or an explicit
`INFERRED` label. `docs/isa/memory-model.md` §2A.5 records a live counterexample to blanket
family equality (`tg_addr_compute`), so do not treat A18↔M4 transfer as automatic.

---

## 6. Silent-failure envelope — limits a driver must SELF-ENFORCE

**Every row here is a case where the hardware or the API accepts an out-of-envelope value and
produces a wrong result with NO error, NO fault, and (where applicable) `CMDBUF_STATUS` still 4.**
On Apple9 the default failure mode of a bad field value is a **silent zero**, not a fault
(`../docs/evidence-classification.md` §5). A driver cannot discover any of these at runtime; it
must encode the limit statically. All rows measured on **M4 / G16G** (`target: G16G`) and not
promoted to G17P — G17P revalidation is under way (`EXP-0153`).

| # | Limit | What the API/hardware says vs what it does | Evidence |
|---|---|---|---|
| 1 | **Mesh grid amplification tops out at exactly 65,536** | Metal reflects `meshGridMax = 1048576` — **16× higher**. Amplification 65535 covers 917 px; **65536, 65537, 65600 and 1048576 all cover 0 px** with no error, no fault, `CMDBUF_STATUS` still 4. Identical in both runs, and reproduced independently via the indirect-draw path. | EXP-0135, `HW-PROBE` + `DATA-TRACE` + `OWN-SHADER` |
| 2 | **Object→mesh payload ceiling is exactly 16,384 bytes** | Enforced at **pipeline creation** (16384 builds, 16385 fails) — this one is loud. But `payloadMemoryLength` **accepts values smaller than the declared struct with no validation at all**. | EXP-0135 |
| 3 | **`tile_read` byte+6 bit 0 is a read-enable** | All 128 **odd** values read the tilebuffer correctly; all 128 **even** values return a **silent zero**. Identical on `tile_read_mrt`. A wrong `rt_index` (anything but `0x00/0x01/0x80/0x81` with one attachment bound) does the same. **In a BG/EOT program this is a black tile, not a failed command buffer.** | EXP-0147, `HW-VALIDATED` |
| 4 | **Invalid attachment `slice` DESTRUCTIVELY ZEROES slice 0** | `slice = arrayLength` (out of range) is **silently accepted** and destroys the contents of slice 0. By contrast an invalid `level` (`= mipCount`) is silently accepted as a **pure no-op**. Two different silent behaviours at two adjacent boundaries — a driver must range-check both itself. | EXP-0132, `HW-PROBE` + `DATA-TRACE` + `OWN-SHADER` |
| 5 | **`unorm16` ties round DOWN — the OPPOSITE of `unorm8`** | Storage path: `1.5/65535` → texel `0x0001`, `2.5/65535` → `0x0002`, with a non-tie control `5.9/65535` → `0x0006` excluding truncation. `unorm8` ties round **UP** (EXP-0079). **Naively extending the 8-bit rule to 16-bit is a silent off-by-one on every tie.** `snorm16` *does* follow `snorm8`'s symmetric scale. Note also that the **ALU pack path rounds differently again** — `pack_float_to_unorm2x16` ties round to **nearest-even** (EXP-0144) — so there are three distinct rules and none may be reused for another. | EXP-0133 (storage) / EXP-0079 (`unorm8`) / EXP-0144 (ALU pack) |
| 6 | **`ibfe`'s `offset` is LITERAL while its `width` is mod-32** | `offset` 32..63 shifts the field out (literal model 64/64 vs mod-32 32/64) — **the hardware does NOT implement NIR's `offset`-mod-32 masking**, so a NIR back-end must mask in software. `width` **is** mod-32 (64/64 vs 37/64), so **`width = 32` ≡ `width = 0`**. Opposite rules on two fields of one instruction. | EXP-0139, `HW-VALIDATED` |
| 7 | **`device_load` destination register `R ≥ 64` silently zeroes** | `extmode = 2·R` reaches `R = 0..63` only: `extmode` 0..127 all match, **128..255 all fail** with no fault. | EXP-0141, `HW-VALIDATED` |
| 8 | **`matrix_mac` accumulator/destination descriptors silently zero** | `dst_desc` outside `bit6 = 1, bit7 = 0`: 128 of 256 values **silently zero**, 64 return a wrong value. `b11hi & 3 != 0` silently changes the accumulator sign (§1). | EXP-0147, `HW-VALIDATED` |
| 9 | **Render/blend/MSAA/resolve/depth-stencil format eligibility is enforced by unconditional `abort()`, not a soft query** | There is **no safe runtime probe** — a driver needs a **static allowlist**. `Depth24Unorm_Stencil8` / `X24_Stencil8` are header-available but **rejected by this GPU**. Also: Metal enforces sample positions in `[0,1)` with a **process-terminating assertion**, not a catchable error. | EXP-0133; EXP-0126 |
| 10 | **Texture swizzle codes 6/7 HARD-FAULT the command buffer** | GPU-hang class, contained. **Never emit them.** (Contrast: sampler address-mode codes 4/6/7 are deterministic *aliases* — 4→`clampToEdge`, 6/7→`clampToBorder` — while code 5 is genuinely distinct.) | EXP-0136, `HW-PROBE` |
| 11 | **`fspecial` byte+3 bit 7 hangs the GPU** | Values 192..255 fault or hang; on an isolated host 192/193/194 each hung three times in a row under a 12 s watchdog. Only values 2 and 3 give the correct `rsqrt(4) = 0.5`; 188 values silently return `0.0`. **An emitter must never set that bit.** | EXP-0138, `HW-PROBE` |
| 12 | **A wrong `get_sr` / `psel` / `ret` control byte returns a silent wrong value** | `get_sr.dp_width` accepts only `(v & 0xD3) == 0x10` (faults on 32 of 256, silently wrong on 216); `get_sr.dp_marker` only `(v & 0xE6) == 0x06`; `psel.mode` only `(v & 0xC0) == 0x00` (127 values fault); `ret.linkmode` only `(v & 7) == 4` (the other 224 fault). | EXP-0140, `HW-VALIDATED` |

**Corollary for the implementation team.** Rows 1, 2, 4, 5 and 9 are *API-level* limits that a
Vulkan/GL driver must encode in its own limit tables and validation, because Metal's reflected
values and the hardware's real envelope disagree. Rows 3, 6, 7, 8, 10, 11 and 12 are *encoding*
limits that belong in the emitter, because the ISA will not tell you when you get them wrong.

---

## Provenance
Synthesis of: `hypotheses.md` (#1–#17 — the extrapolate-and-test register), `isa/README.md`
(EXP-0013/0016/0018/0022/0023 — ISA capabilities), `descriptors/README.md` (EXP-0015 — sampler /
format capabilities), `cmdstream/README.md` (EXP-0019/0024 — programmable blend, shader binding),
`pipeline/README.md` (EXP-0021 — sample positions, ZLS, partial render), `hardware-overview.md`
(§3 — Metal capability values), `mesa-userspace-requirements.md` (§2g / §4 — the emulate-vs-native
boundary and the classically-Apple-absent stages), `reviews/GAP-ANALYSIS-01.md` (gap #10/#11 — the
missing decided matrix). Firmware/kernel rows cross-reference `kernel-interface.md`. No new
experiment; no Apple binary introspected.

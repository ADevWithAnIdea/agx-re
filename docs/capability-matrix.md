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
| **Native single-RMW atomics (int add/sub/and/or/xor/min/max/xchg/cmpxchg, + float-add)** | ✅ Native | `isa/README.md` "Atomics" (EXP-0018) | Native single-RMW ops in the memory family (`0x67`), op at byte+12 — **including `fadd` (`0x26`)**. `cmpxchg` is one op + a compare (no CAS loop). Emit natively. *(Float min/max and 64-bit add are the exception — see §2.)* |

**Count: 13 native capabilities.**

---

## 2. Emulate — the hardware lacks it, or Metal exposes no path (Vulkan/GL must software-emulate)

| Feature | HW-native? | Evidence (doc §) | Implication |
|---|---|---|---|
| **Float atomic min / max** | ⛔ Emulate | `isa/README.md` "Atomics" (EXP-0018); `hypotheses.md` #9 | MSL rejects `atomic_fetch_min/max<float>` — **not exposed**. Only float atomic **add** exists natively. Vulkan float-atomic min/max → **emulate** (e.g. int-bitcast CAS loop). |
| **64-bit atomic-add** | ⛔ Emulate | `isa/README.md` "Atomics" (EXP-0018); `hypotheses.md` #9 | MSL rejects 64-bit `atomic_fetch_add`. (64-bit **min/max** exist; 64-bit **add** does not.) → **emulate**. |
| **Arbitrary sampler border color** | ⛔ Emulate | `descriptors/README.md` "Sampler descriptor" + "Capability notes" (EXP-0015); `hypotheses.md` #4 | The 8-byte sampler encodes only a **2-bit preset** (transparent / black / white). Arbitrary Vulkan RGBA border color must be **emulated** (Mesa's M1/M2 uses a 2-sampler-plane trick — `mesa-userspace-requirements.md` §4). Also: `clampToZero == clampToBorder(transparent-black)` (one HW mode). |
| **int8 cooperative matrix** | ⛔ Emulate | `isa/README.md` "Dedicated matrix unit" (EXP-0022) | The `0xcf` matrix unit supports fp16/fp32/bf16 only; **all integer types are rejected** by Metal for `simdgroup_matrix`. Vulkan int8 cooperative-matrix → **emulate** (integer MAC in the ALU). |
| **Geometry shaders** | ⛔ Emulate | `mesa-userspace-requirements.md` §2g / §4 (compute-emulated on M1/M2; historically absent on Apple) | No HW geometry-shader stage found; assume **compute-emulated** (VS→GS lowering, 4 sub-programs). *A18 status not independently probed — see §4; treat as emulate until shown otherwise.* |
| **Tessellation** | ⛔ Emulate | `mesa-userspace-requirements.md` §2g / §4 (VS→TCS→D3D11-reference tessellator as compute) | No fixed-function tessellator found; assume **compute-emulated**. *A18 not independently probed — see §4.* |
| **Transform feedback / streamout** | ⛔ Emulate | `mesa-userspace-requirements.md` §2g / §4 (`agx_streamout.c`: GS-path + CPU primitive counting) | Metal does not expose streamout; assume **compute-emulated**. *A18 streamout unit not independently probed — see §4.* |

**Count: 7 emulate capabilities** (4 HW-validated as absent/not-exposed via our own probes:
float-atomic-min/max, 64-bit-atomic-add, arbitrary border color, int8 coopmat; 3
classically-Apple-absent geometry-pipeline stages carried from `mesa-userspace-requirements.md`,
not yet independently re-probed on A18 — see §4).

---

## 3. Kernel / firmware-managed — real HW state, routed via the kernel submit (not emitted by userspace)

See `kernel-interface.md` for the full contract and the G-11 reconciliation. Userspace **computes
the value** and hands it to the kernel; the **firmware writes the register**.

| Feature | HW-native? | Evidence (doc §) | Implication |
|---|---|---|---|
| **Programmable MSAA sample positions** | 🔥 Kernel/FW | `pipeline/README.md` MSAA § (EXP-0021); `hypotheses.md` #15 | Not in any userspace BO (msaa4-vs-custom captures byte-identical). Userspace packs the value (`PPP_MULTISAMPLECTL`); route via kernel submit (`kernel-interface.md` §4.2/§6.1). |
| **Depth store-action / ZLS** | 🔥 Kernel/FW | `pipeline/README.md` load/store § (EXP-0021) | ZLS control not captured in any BO; userspace computes `zls_ctrl` + depth/stencil buffers → kernel submit (`kernel-interface.md` §4.3/§6.1). |
| **RT acceleration-structure (BVH) build + node format** | 🔥 Kernel/FW | `isa/README.md` RT § (EXP-0023) | Userspace supplies vertices + build descriptor + an 8-byte AS VA; the **GPU/firmware builds the BVH**; node format is **not userspace-visible** (`kernel-interface.md` §4.1). (The *traversal* ISA is native — see §1.) |
| **Partial-render / tiler-param overflow trigger** | 🔥 Kernel/FW | `pipeline/README.md` partial-render § (EXP-0021) | No userspace knob for the trigger; userspace supplies `partial_bg`/`partial_eot` programs; firmware detects overflow and triggers the partial render (`kernel-interface.md` §4.4). |
| **Graphics shader-entry bind (code-BO → firmware handoff)** | 🔥 Kernel/FW | `cmdstream/README.md` USC/EXP-0024 | A draw carries **no `shaderVA>>N`** anywhere in the client stream; userspace emits sized code blocks + USC preambles, and the code-BO base reaches the firmware out-of-band (`kernel-interface.md` §4.5). |

**Count: 5 kernel/firmware-managed capabilities.**

---

## 4. Unknown / untested — do not rely on; open probes

Honest carry-over of what the docs mark unresolved. These are **not decided** and must be probed
before an implementer commits to native vs emulate.

| Feature | Status | Evidence (doc §) | Note |
|---|---|---|---|
| **Mesh / task shaders** | ❓ Unknown (likely native) | `mesa-userspace-requirements.md` §4; `hypotheses.md` backlog; `GAP-ANALYSIS-01.md` gap #10 | **MSL exposes mesh on Apple9** and A18 is the plausible first mesh-capable generation, but the **HW command/ISA decode is still TODO** — no AGX encoding exists in `docs/`. If native, it could retire the VS→GS/TCS compute-emulation stack. **Probe before deciding.** |
| **Geometry shaders / tessellation / transform feedback — A18-native?** | ❓ Unknown | `mesa-userspace-requirements.md` §4 | §2 assumes **emulate** (the M1/M2 default). Whether A18 gained any native path (or subsumes them under mesh) is **not independently probed on A18**. Scoping-critical: native support retires large emulation paths. |
| **Anisotropy > 16×** | ❓ Unknown (field can encode 128×) | `descriptors/README.md`; `hypotheses.md` #5 | The sampler aniso field is **3-bit log2 (→128×)** though Metal caps 16×; **>16× not yet run on hardware**. Probe candidate; don't assume >16× works. |
| **Polygon-point fill; extra gather/offset sample variants; 1D/CubeArray/MSArray texture types** | ❓ Unknown / ⏳ | `cmdstream`/`descriptors`/`isa` (EXP-0016/0015) | Spare encodings exist but specific variants are untested; several texture *types* are ⏳. |
| **Block-compressed (BC/ASTC/ETC) twiddle; 3D/cube/array/MSAA layout; compression codec** | ❓ Unknown / inferred | `tiling/README.md` §1.5 / §4.5; `GAP-ANALYSIS-01.md` gap #14 | BC twiddle is *inferred, not probed*; volume/cube/array/MSAA layouts untested; the compression **codec** is opaque (documented disable-fallback exists). Affects whether compressed/volume textures can be laid out with confidence. |

---

## 5. Summary counts

| Bucket | Count | Members |
|---|---|---|
| **✅ Native** | **13** | matrix (`0xcf`), hybrid RT, programmable blend, logic ops (16-func LUT), depth clamp, dual-source blend, polygon line fill, subgroup prefix-scan, float round modes, typed compare, format/swizzle/sRGB orthogonality, separate read/write texture paths, native single-RMW atomics |
| **⛔ Emulate** | **7** | float atomic min/max, 64-bit atomic-add, arbitrary sampler border color, int8 cooperative-matrix, geometry shaders, tessellation, transform feedback |
| **🔥 Kernel/FW** | **5** | sample positions, ZLS/depth store, RT BVH build, partial render, graphics shader-entry handoff |
| **❓ Unknown/untested** | 6 clusters | mesh/task shaders; GS/tess/XFB A18-native status; aniso >16×; polygon-point & gather variants & exotic tex types; BC/3D/cube/array/MSAA tiling; compression codec |

**Honesty note (per `../CLAUDE.md`).** Of the 7 "emulate" rows, **4** are HW-validated absences from
our own probes (float atomic min/max, 64-bit atomic-add, arbitrary border color, int8 coopmat); the
**3 geometry-pipeline stages** (GS / tessellation / transform feedback) are marked emulate on the
strength of the M1/M2 driver + Apple's historical absence of these stages, and have **not been
independently re-probed on A18** — they are cross-listed in §4 as open. Mesh shading is explicitly
**unknown** (MSL-exposed, HW decode TODO), not native.

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

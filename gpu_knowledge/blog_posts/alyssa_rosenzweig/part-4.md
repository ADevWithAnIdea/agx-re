# Dissecting the Apple M1 GPU, Part IV

**Source URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-4.html  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 2 May 2021  
**Project:** Asahi Linux  

---

## Overview

This post describes the development of a Gallium3D driver for the Apple M1 GPU within Mesa, enabling OpenGL workloads. At the time of writing, the driver could run `glxgears` and scenes from `glmark2`, achieving approximately 75% pass rate on OpenGL ES 2.0 conformance tests. Code was upstreamed to Mesa.

---

## Achievement

With compiler (Part III) and Gallium driver combined:

- `glxgears` runs on M1 with open-source stack
- `glmark2` scenes render correctly
- ~75% of OpenGL ES 2.0 conformance tests pass
- Code upstreamed to Mesa mainline

---

## Mesa Gallium Architecture

Gallium3D is Mesa's internal driver framework. It splits GPU driver functionality into two components:

- **Frontends (state trackers):** Implement graphics APIs (OpenGL, OpenCL, Vulkan). Written once, used by all backends.
- **Backends (pipe drivers):** Implement hardware-specific translation. One per GPU family (Intel, AMD, AGX, Mali/Panfrost, etc.).

**Common infrastructure** shared between all Gallium drivers:
- Shader caching
- CPU-side optimization
- Resource management utilities

This means the AGX Gallium driver benefits from decades of accumulated Mesa infrastructure.

---

## Hardware Packet Description: GenXML Approach

### Problem with Alternative Approaches

**C bitfields:**
- Performance concerns (compiler may not generate efficient code)
- Safety issues (undefined behavior, endianness)
- Hard to debug (no introspection)

**Hand-coded structures with magic numbers:**
- Accumulated magic numbers become unmaintainable
- Difficult to debug (no field names at runtime)
- Error-prone

### Solution: GenXML

The AGX driver adopted **GenXML** for describing hardware packet formats. GenXML is an XML-based format for describing hardware register and packet layouts.

**Precedent:**
- Intel uses GenXML for their GPU command packets (gen_pack_header)
- Nouveau uses envytools for similar purposes
- Panfrost uses a similar approach (pandecode/pan_pack)

GenXML generates:
- Pack/unpack macros for hardware packets
- Decoder tools for debugging (printing packet contents)
- Documentation-as-code

---

## Hardware Packet: Index Size Encoding

A concrete example of reverse-engineering hardware packet field encoding:

### Observed Data (from Metal driver captures)

```xml
<enum name="Index size">
  <value name="U16" value="1"/>
  <value name="U32" value="2"/>
</enum>

<struct name="Indexed draw" size="32">
  ...
  <field name="Index size" size="2" start="2:17" type="Index size"/>
  ...
</struct>
```

### Analysis

The 2-bit field for index size uses:
- `01` (binary) = U16 (16-bit indices)
- `10` (binary) = U32 (32-bit indices)

**Unused encodings:** `00` and `11` are not used by Metal.

**Hypothesis:** Applying logarithmic encoding:
```
log₂(8 / 8)  = 0  → encoding 00 = U8  (8-bit indices)
log₂(16 / 8) = 1  → encoding 01 = U16 (16-bit indices) ✓
log₂(32 / 8) = 2  → encoding 10 = U32 (32-bit indices) ✓
```

Encoding `00` likely represents **8-bit index buffers**, a feature inaccessible via Metal but required by OpenGL.

---

## Hardware Packet: Primitive Type Discovery

### Situation

The primitive type field is **4 bits wide**, allowing 16 possible encodings. Metal only uses 5 of these (points, lines, line strips, triangles, triangle strips).

**Remaining 11 encodings** are unknown/undocumented. These likely include:
- Triangle fans
- Line loops
- Patches (for tessellation)
- Adjacency primitives
- Others

### Discovery Methodology

**Brute-force testing:** Since there are only 11 unknown values, each can be tested by:
1. Setting the primitive type field to the test value
2. Submitting a draw call
3. Observing the rendered output

---

## Hardware Features Inaccessible via Metal

The AGX hardware supports features that Metal does not expose, but which are required by OpenGL and Vulkan:

| Feature | Metal Support | OpenGL/Vulkan Required |
|---------|--------------|------------------------|
| 8-bit index buffers | No | Yes (OpenGL) |
| Triangle fans | No | Yes (OpenGL) |
| Optional primitive restart disable | No | Yes (OpenGL/Vulkan) |
| Additional primitive types | No | Various |

**Note:** These limitations also affect MoltenVK (Khronos issue: KhronosGroup/MoltenVK#229), which translates Vulkan to Metal.

---

## Texture and Sampler Support

Recent reverse-engineering at time of writing documented texture and sampler hardware packets. These mapped closely to both Metal's API surface and Gallium's texture/sampler state, facilitating straightforward driver integration.

Dougall Johnson contributed significant compiler updates enabling texture sampling support.

---

## Design Philosophy: Shader-Based Fixed Function

Apple's GPU philosophy: **reduce hardware surface area by implementing fixed-function operations in shaders**.

This applies to:
- Vertex attribute fetch (compiler generates load instructions)
- Blending (compiler generates blend equations as shader code)

**Impact on driver:** More work for the driver/compiler, but simpler hardware.

**Benefit for Mesa:** Mesa already has `nir_lower_blend` — a pass that lowers blend operations to NIR instructions. This could be reused directly for the AGX driver.

---

## macOS Kernel Interface Challenges

### IOGPU vs. Standard Linux DRM

The macOS `IOGPU` kernel extension differs fundamentally from Linux's DRM (Direct Rendering Manager):

**Linux model:**
- Thin kernel driver (memory mapping, interrupt handling, work submission)
- Complex userspace (Mesa handles most logic)

**macOS IOGPU model:**
- Kernel extension is **GPU-state-aware**
- Kernel requires knowledge of surface dimensions, mipmap levels, and other GPU state
- Memory mapping descriptors and surface descriptors must be understood

**Implication:** For native Vulkan on macOS (rather than via MoltenVK), the IOGPU interface must be more thoroughly reverse-engineered. Sufficient knowledge existed at time of writing for current macOS GPU driving.

---

## Contributors

- **Dougall Johnson** (GitHub: dougallj) — Instruction set reverse-engineering, compiler contributions

---

## Conformance Testing

- **Test suite used:** VK-GL-CTS (Khronos)
- **Pass rate at time of post:** ~75% of OpenGL ES 2.0 conformance tests
- **Next goal:** Full OpenGL ES 2.0 conformance, then OpenGL ES 3.0+

---

## Related Links

- Previous post: `/blog/asahi-gpu-part-3.html`
- Mesa repository: GitLab Freedesktop
- MoltenVK issue: KhronosGroup/MoltenVK#229
- VK-GL-CTS: KhronosGroup conformance test suite

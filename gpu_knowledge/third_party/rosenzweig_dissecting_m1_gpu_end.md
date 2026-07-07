# Dissecting the Apple M1 GPU - The End

**Source:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-n.html  
**Also at:** https://rosenzweig.io/blog/asahi-gpu-part-n.html  
**Author:** Alyssa Rosenzweig  
**LWN.net coverage:** https://lwn.net/Articles/1035332/

---

## Summary

Final installment in the series, written after the project reached completion. Documents the full scope of achievement and novel technical work required.

---

## Completed Driver Capabilities

| Milestone | Status |
|-----------|--------|
| OpenGL 3.1 on Asahi Linux | Shipped within one month of full-time work |
| OpenGL ES 3.1 conformance | Officially certified by Khronos |
| OpenGL 4.6 compliance | January 2024 |
| Vulkan 1.3 conformance | Shipped |
| Vulkan 1.4 conformance | Shipped upon spec release |
| OpenCL 3.0 | Via Rusticl frontend |
| Sparse textures (Direct3D 12 via Proton) | Shipped |

---

## Novel Technical Innovations

### Geometry/Tessellation Shader Emulation
Apple Silicon and ARM hardware **do not have hardware geometry or tessellation shaders** as required by OpenGL/Vulkan/DirectX specs.

The implementation required original engineering:
- **No open source prior art** existed for this emulation approach in Mesa drivers
- Tessellation uses compute shader-based generation
- Geometry shaders emulated with compute dispatch
- Microsoft reference tessellator code (converted to OpenCL C) used as reference

Apple's hardware tessellator is missing required features:
- Point mode
- Isoline support

### Software Blending
Apple relies on shader code for blending operations, enabling "sophisticated compiler optimizations" for this normally fixed-function stage.

---

## Methodology: Leveraging Mesa Infrastructure

The reverse engineering approach leveraged "the mature common code in Mesa," allowing rapid initial progress by:
- Reusing 30+ years of accumulated OpenGL/graphics driver infrastructure
- Focusing reverse engineering effort specifically on Apple hardware-specific parts
- Contributing discoveries back to upstream projects

---

## Performance Results

- Xonotic: 800+ FPS on M2 (exceeding macOS's ~600 FPS)
- Open-source reverse-engineered drivers demonstrably beating vendor's own drivers

---

## Project Conclusion

After completing all stated objectives:
- Drivers fully upstreamed in Mesa
- Performance deemed competitive (often exceeding macOS Metal)
- Alyssa Rosenzweig transitioned to Intel Xe-HPG graphics work
- Challenged the myth that "Vulkan isn't suitable for Apple hardware"

The work also enabled **LunarG's KosmicKrisp** - bringing compliant Vulkan to macOS itself using the reverse-engineered knowledge.

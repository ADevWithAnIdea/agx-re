# Dissecting the Apple M1 GPU, Part IV

**Source:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-4.html  
**Author:** Alyssa Rosenzweig  
**Also mirrored at:** https://rosenzweig.io/blog/asahi-gpu-part-4.html

---

## Summary

Part IV digs into the command stream structure - specifically index buffers, primitive types, and how the kernel-userspace interface works for the M1 GPU.

---

## Shader-Based Implementation of Fixed-Function Features

Apple's M1 GPU uses **shader code in lieu of fixed-function graphics hardware** for tasks like:
- Vertex attribute fetch
- Blending operations

This is a deliberate design choice to maximize programmable compute at the cost of driver/compiler complexity.

---

## Index Buffer Format

A **2-bit index size field** encodes buffer widths as base-2 logarithms:

| Field value | Width |
|-------------|-------|
| 0 | 8-bit (not exposed in Metal) |
| 1 | 16-bit |
| 2 | 32-bit |

Method: Pattern analysis of the field deduced potential 8-bit support even though Metal only exposes 16-bit and 32-bit variants. This suggests reserved/hidden capabilities in the hardware.

---

## Primitive Types

A **4-bit primitive type field** theoretically supports 16 different configurations:
- Metal only exposes 5 primitive types
- Investigation used brute-force testing to identify additional variants:
  - Triangle fans (not in Metal's public API)
  - Triangle strips (additional variants beyond Metal's capabilities)

---

## Primitive Restart

A **single enable bit** controls primitive restart functionality:
- Identified through: "few bits vary between an indexed draw of triangles (no primitive restart) and an indexed draw of triangle strips (with primitive restart)"
- Consistent with other GPU architectures

---

## Kernel Interface Complexity

The IOGPU kernel interface is unusual in its statefulness:
- Made aware of graphics state like surface dimensions
- Aware of mipmapping details
- This creates challenges for an independent driver that needs to replicate all this state management
- Differs significantly from typical GPU kernel interfaces (e.g., Adreno, Mali)

---

## Methodology Notes

Several discovery techniques used:
1. **Differential binary analysis** - small source changes, compare binary output
2. **Brute force field enumeration** - try all values of unknown fields
3. **Cross-reference with Metal API** - known API capabilities constrain possible encodings

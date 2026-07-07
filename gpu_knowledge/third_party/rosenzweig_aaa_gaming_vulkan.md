# AAA Gaming on Asahi Linux (Vulkan 1.3 Technical Details)

**Source:** https://alyssarosenzweig.ca/blog/aaa-gaming-on-m1.html  
**Author:** Alyssa Rosenzweig  
**Context:** Accompanies XDC 2024 talk "AAA!! She's a Witch!"  
**XDC 2024 talk:** https://indico.freedesktop.org/event/6/contributions/284/

---

## Summary

Technical deep dive into the Vulkan 1.3 driver ("Honeykrisp") and the AAA gaming translation stack for Apple Silicon. Documents how Apple GPU hardware limitations were overcome through software.

---

## Vulkan 1.3 Driver Architecture (Honeykrisp)

### Tessellation Implementation
Apple M1 hardware tessellator **lacks required features**:
- Missing: point mode
- Missing: isoline support
- These are hard requirements for OpenGL, Vulkan, and DirectX

**Software solution:**
- Replaced hardware tessellator with **compute shader-based generation**
- Used Microsoft reference tessellator code (converted to OpenCL C)
- Performance comparison on M2:
  - Software-only implementation: <1 fps
  - OpenCL-based: 265 fps
  - Hardware (where possible): 820 fps

### Geometry Shaders
Similarly **unsupported in Apple GPU hardware**.

**Software solution:**
- Emulated with compute dispatch
- Shader-based geometry generation pipeline

### Out-of-Bounds Memory Robustness
Required for DirectX/Vulkan spec compliance.

**Naive approach:** Per-element address validation (too slow)

**Apple implementation:**
- "Reserve 64 gigabytes of zeroes using virtual memory"
- Replace out-of-bounds addresses with pointer into the zero region
- Efficient: just two compare-and-select operations per access
- Exploits Apple's 64GB+ virtual address space

---

## AAA Gaming Translation Stack

### The Problem: Three Incompatibilities
1. Games are x86 binaries; Apple Silicon is ARM64
2. Games are Windows binaries; Asahi Linux is Linux
3. Games use DirectX; Apple has Metal

### Solution Stack
```
DirectX game (Windows x86)
  → DirectX → Vulkan translation (DXVK / vkd3d-proton)
  → Windows → Linux translation (Wine)
  → x86 → ARM64 emulation (FEX-Emu or Box64)
  → Honeykrisp Vulkan driver
  → Apple AGX GPU
```

### Memory Page Size Problem
Critical hardware incompatibility:
- x86 applications expect **4K memory pages**
- Apple Silicon uses **16K memory pages**
- Linux cannot mix page sizes within a single process

**Solution:** Virtualization
- **muvm**: Lightweight VM running a 4KB guest kernel inside 16KB host
- GPU passthrough via DMA-BUF sharing
- Controller passthrough
- All constraints satisfied without changing the host kernel

### Games Running Successfully
- Portal, Portal 2
- Castle Crashers
- The Witcher 3
- Fallout 4
- Control (45 fps on M1 MAX)
- Ghostrunner
- Cyberpunk 2077

---

## Performance Philosophy

> "Correctness comes first. Performance improves next."

- Indie titles: full speed
- AAA titles: below 60fps currently but functional

---

## Prior Work: OpenGL vs. Vulkan Path

The Vulkan (Honeykrisp) driver replaced the original OpenGL Gallium3D (Asahi) driver:
- Old driver: Mesa Gallium3D framework, OpenGL 2.1 → 4.6
- New driver: Native Vulkan implementation, more suitable for AAA game compatibility
- OpenGL 4.6 is now layered over Vulkan via zink (Gallium → Vulkan)

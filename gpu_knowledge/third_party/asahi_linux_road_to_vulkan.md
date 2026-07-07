# Paving the Road to Vulkan on Asahi Linux

**Source:** https://asahilinux.org/2023/03/road-to-vulkan/  
**Author:** Asahi Linux team  
**Published:** March 2023

---

## Summary

Documents the architectural decisions made in designing the Vulkan-capable userspace API (UAPI) for the Apple AGX GPU driver, including the shift from synchronous to asynchronous GPU submission and explicit synchronization.

---

## TBDR Architecture and Batching

Apple Silicon GPUs use **tile-based deferred rendering (TBDR)**:

> "Collects a whole scene of geometry first, then it runs through vertex shaders, gets split up into tiles based on screen position, and is finally rendered tile by tile."

### Implications for Driver Design
- Cannot process draw calls individually - must batch entire render passes
- Driver must implement batch tracking to group rendering operations
- Must avoid expensive framebuffer loads/saves between passes
- Deferred rendering enables on-chip tile buffer storage, reducing external bandwidth

---

## UAPI Design Evolution

### Original (Problematic) Design: Synchronous UAPI
Copied from Panfrost (Mali driver):
> "The whole GPU rendering process was synchronous: when an app submitted work to the GPU it would be queued to be executed by the firmware, then executed, and only when everything was complete would the UAPI call return back to the app."

**Problems:**
- Prevented CPU-GPU parallelism
- CPU was idle while GPU worked
- GPU was idle while CPU prepared next frame
- Significant performance penalty

### New Design: Explicit Synchronization with DMA Fences

The updated UAPI uses:
- **DMA fences** and **sync objects**
- Asynchronous operations: "the driver checks all the input sync objects and registers their fences as dependencies"
- CPU and GPU can operate in parallel

---

## Synchronization Mechanisms

### Implicit Synchronization (Legacy)
- Kernel tracks buffer dependencies automatically
- Problem: kernel overhead tracking hundreds of buffers per render job
- Does not scale well with complex workloads

### Explicit Synchronization (Modern - Vulkan-native)
- Applications specify dependencies via Vulkan barriers, events, timeline semaphores
- Breakthrough: **Linux 6.0's generic DMA-BUF fence import/export APIs**
- Enables bridging between implicit and explicit sync worlds

---

## Critical Technical Discoveries

### Buffer Sharing Edge Cases
OpenGL allows textures to become shareable **retroactively** after creation:
- `flush_resource` callbacks implemented to reallocate buffers as shareable when needed
- Not typically an issue in Vulkan (all resources explicitly shareable from creation)

### Deferred Fence Attachment
Batches can be shared before their completion fences are attached:
- Infrastructure to "retroactively attach the fences" to buffers was required
- Necessary for correct explicit sync in OpenGL compatibility path

---

## Performance Results

After UAPI redesign:
- **Xonotic: 800+ FPS on M2** (vs macOS ~600 FPS)
- Open-source drivers demonstrably exceeding Apple's own Metal drivers
- "Open source reverse engineered GPU drivers really have the power to beat Apple's drivers"

---

## Conformance Achievement

- 100% pass rate on dEQP-GLES2 conformance tests
- 100% pass rate on dEQP-EGL conformance tests
- Exceeds macOS OpenGL conformance for those versions

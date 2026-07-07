# Asahi Linux Apple AGX GPU Driver: Upstreaming Status

**Sources:**
- https://rust-for-linux.com/apple-agx-gpu-driver
- https://asahilinux.org/2025/05/progress-report-6-15/
- https://asahilinux.org/2025/08/progress-report-6-16/
- https://asahilinux.org/2025/10/progress-report-6-17/
- https://asahilinux.org/2026/02/progress-report-6-19/

---

## Development Team

Four main contributors to the GPU driver effort:

| Person | Role |
|--------|------|
| **Dougall Johnson** | Reverse engineering of GPU shader ISA |
| **Alyssa Rosenzweig** | OpenGL driver and shader compiler |
| **Asahi Lina** | Kernel driver (Rust), firmware interface, OpenGL support |
| **Ella Stanforth** | Vulkan driver (Honeykrisp) |

---

## Upstreaming Timeline

### Linux 6.15 (May 2025): UAPI Merged
- Graphics driver **userspace API (uAPI) merged** into mainline Linux kernel
- Historic milestone: "the only time a graphics driver's uAPI has been merged into the kernel independent of the driver itself"
- DRM maintainers granted one-time exception to facilitate upstream Mesa integration while Rust abstractions mature
- Enables OpenGL, OpenCL, and Vulkan for Apple Silicon in upstream Mesa

### Linux 6.16 (August 2025): Mesa Drivers Upstreamed
- Asahi (OpenGL) and Honeykrisp (Vulkan) Mesa drivers upstream
- Project can work directly with Mesa upstream community

### Linux 6.17 (October 2025): Platform Work
- Devicetree bindings for GPU accepted and merged
- Allows stabilization of m1n1 GPU initialization
- Core SMC driver accepted (shutdown, reboot, WiFi/BT, USB-A)

### Linux 6.19 (February 2026): Progress
- Patch set shrinking: from 1232 patches (with 6.13.8) → 858 patches (6.18.8)
- Lines of code: 95,000 → 83,000

---

## Remaining Work (as of early 2026)

Still not upstream:
- Display controller driver (largest remaining piece)
- Full GPU kernel driver (Rust abstractions still maturing)
- M3/M4/M5 GPU support still ongoing

---

## Driver Architecture Summary

The driver is implemented in three layers:

1. **Kernel driver (Rust):** Memory management, UAT (GPU MMU), firmware communication, work submission
2. **Mesa userspace (C):** Graphics API translation (OpenGL/Vulkan → AGX commands), shader compiler
3. **Shader compiler:** NIR → AGX ISA via Asahi compiler backend

**Kernel driver repository:** https://github.com/AsahiLinux/linux (branch bits/210-gpu)

### Why Rust for the Kernel Driver

Key technical motivations:
- Complex firmware ABI with shared memory structures and pointer chains
- Firmware crashes are fatal (no restart) → memory safety critical
- Object lifetime complexity (circular references between scheduler, fence, driver objects)
- Rust's type system prevents use-after-free at compile time

**Result:** No memory safety bugs required fixes after initial implementation — only logic bugs.

---

## UAPI Design

The final UAPI uses **explicit synchronization**:
- DMA fences and sync objects
- Asynchronous GPU submission (CPU and GPU overlap)
- Bridges with Linux 6.0's generic DMA-BUF fence import/export APIs
- Seven submission iterations to kernel mailing lists required for UAPI stability

Earlier UAPI used synchronous submission (inherited from Panfrost) — abandoned due to performance problems.

---

## Fork Consolidation (2025-2026)

After upstream Mesa acceptance:
- Sunset forked Mesa, virglrenderer, and Flatpak runtime repositories
- Fedora Asahi Remix discontinuing forked packages from Fedora 43
- Other distributions (Debian, Gentoo) can now provide native GPU support without custom packaging

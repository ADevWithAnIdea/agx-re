# Apple GPU Drivers Now in Asahi Linux

**Source URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-7.html  
**Original URL (redirected):** https://rosenzweig.io/blog/asahi-gpu-part-7.html → 301 redirect to alyssarosenzweig.ca  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 7 December 2022  
**Project:** Asahi Linux  

---

## Overview

This post announces the first public release of Apple GPU drivers for Asahi Linux, delivering hardware-accelerated graphics for Apple M-series systems. The drivers support OpenGL 2.1 and OpenGL ES 2.0, enabling smooth desktop experiences and some games at up to 60fps at 4K resolution.

---

## Key Announcement

The Asahi Linux project shipped work-in-progress GPU drivers that are:

> "already good enough to run a smooth desktop experience and some games"

This represents the culmination of two years of reverse-engineering work, from the initial instruction set analysis (January 2021) through the full driver stack.

---

## Technical Capabilities

### Graphics API Support

- **OpenGL:** 2.1
- **OpenGL ES:** 2.0
- **Target hardware:** All current Apple M-series processors (M1, M1 Pro, M1 Max, M1 Ultra, M2)

### Performance

- Up to **60 frames per second at 4K** for compatible applications

### Conformance Status (at time of release)

> "These drivers have not yet passed the OpenGL (ES) conformance tests."

Conformance was a later milestone (achieved August 2023 for ES 3.1, see first-conformant-driver.md).

---

## Supported Applications

### Working at Launch

- **GNOME** desktop environment
- **KDE** Plasma desktop environment
- **Quake3** (game)
- **Neverball** (game)
- **SuperTuxKart** (deferred renderer mode)

### Limitations

- Applications requiring newer OpenGL versions fall back to software rendering (llvmpipe)
- Some OpenGL ES 3 features not yet implemented

---

## GPU Driver Architecture

The post explains the three-layer GPU driver architecture for readers unfamiliar with graphics internals:

### Hardware Layers

| Layer | Description |
|-------|-------------|
| Memory Management Unit | Manages GPU virtual address space, controls work submission interface |
| Fixed-Function 3D Hardware | Rasterization, depth/stencil testing, blending (in hardware) |
| Programmable Shader Cores | Executes vertex, fragment, and compute shaders |

### Software Driver Stack

| Component | Responsibility |
|-----------|---------------|
| **Kernel driver** | Memory mapping between CPU and GPU address spaces, submitting work to GPU hardware queues |
| **Userspace driver** | Translates OpenGL/Vulkan API calls into hardware command structures and packets |
| **Compiler** | Converts GLSL/SPIR-V shader source into AGX machine code |

**Framework used:** Mesa Gallium3D

> "Thirty years of accumulated OpenGL driver development knowledge" embedded in Mesa infrastructure.

### Technical Foundation

- **NIR** (New Intermediate Representation) — Mesa's standard shader compiler IR
- **Direct Rendering Manager (DRM)** — Linux kernel graphics subsystem
- **Gallium3D** — Mesa driver framework providing common infrastructure

---

## OpenGL ES 3 Roadmap

Features in active development at time of post:

- **Multiple render targets** (MRT) — Draw to multiple framebuffer attachments simultaneously
- **Multisampling** — Anti-aliasing via multiple samples per pixel
- **Transform feedback** — Capture vertex shader outputs back to buffers

> "Every time somebody asks when a feature will be done, it delays that feature by a month."

---

## Vulkan Status

At time of release, Vulkan was not yet available. Rationale for prioritizing OpenGL first:

- **Hardware-accelerated desktops** (GNOME, KDE) use OpenGL
- More immediate user impact from OpenGL
- Vulkan development ongoing in parallel (Ella Stanforth working on it)

---

## Development Team

| Developer | Role |
|-----------|------|
| **Alyssa Rosenzweig** | OpenGL driver and shader compiler |
| **Asahi Lina** | Kernel driver, OpenGL support infrastructure |
| **Dougall Johnson** | Instruction set reverse-engineering |
| **Ella Stanforth** | Vulkan driver development |

---

## Installation Instructions

### Requirements

- `linux-asahi-edge` — Edge kernel package with GPU support
- `mesa-asahi-edge` — Mesa with AGX driver

### Optional (for KDE Wayland)

- `plasma-wayland-session`

### Installation Commands

```bash
$ sudo pacman -Syu
$ sudo pacman -S linux-asahi-edge mesa-asahi-edge
$ sudo update-grub
```

After installation, reboot into the new kernel.

### Important Notes

- Mesa and kernel packages must be kept in sync (matching versions)
- Updating one without the other requires a reboot before using GPU acceleration
- The UAPI (kernel/userspace interface) remains unstable during development

---

## Known Issues at Launch

### Xorg (X11) Issues

- **Screen tearing** — VSync does not function under Xorg
- **VSync non-functional**
- **KDE/KWin driver conflicts** — Known issues with KWin compositor under Xorg

**Recommended:** Use **Wayland** instead of Xorg for optimal experience.

### General Constraints

- Non-conformant (no Khronos certification yet)
- Some rendering glitches in certain applications
- GPU lockups possible (work in progress)

---

## Bug Reporting Protocol

### Diagnosis Tool

```bash
$ asahi-diagnose
```

Generates a diagnostic report for attaching to bug reports.

### Issue Categories

| Issue Type | Reporting Location |
|------------|-------------------|
| App needs newer GL version | Use software rendering fallback (expected behavior) |
| Display/resolution issues | GitHub issue #70 (comment with diagnostics) |
| GPU lockups | New bug report with `asahi-diagnose` output |
| Rendering glitches | GitHub issue #72 (comment with diagnostics) |
| Future regressions | Mesa issue tracker |

---

## Significance

This release represents:

1. The first working open-source GPU driver for Apple Silicon
2. Two years of reverse-engineering work from first ISA analysis to full driver
3. Proof that the AGX GPU architecture is tractable for open-source driver development
4. A working platform for continued development toward ES 3.1, OpenGL 4.x, and Vulkan conformance

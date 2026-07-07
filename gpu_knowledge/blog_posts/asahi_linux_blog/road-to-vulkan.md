# Paving the Road to Vulkan on Asahi Linux

> Source URL: https://asahilinux.org/2023/03/road-to-vulkan/

## Overview

This blog post by Asahi Lina documents major updates to Asahi Linux's open-source GPU drivers for Apple Silicon, focusing on transitioning from synchronous to asynchronous GPU execution through explicit synchronization support.

## Key Technical Achievements

The development team improved performance dramatically—Xonotic now runs at 800+ FPS on M2 hardware, exceeding macOS performance on equivalent systems. The drivers achieve 100% conformance with dEQP-GLES2 and dEQP-EGL tests.

## Understanding the UAPI

A Userspace API (UAPI) represents the communication layer between kernel and userspace GPU drivers. Unlike macOS, where Apple controls both components, Linux maintains strict backward compatibility guarantees. As Lina explains: "newer Linux kernel versions must support the same APIs that older ones do, and older apps and libraries must continue working."

The initial implementation borrowed from Panfrost's design but relied on synchronous execution—GPU work would complete before returning to applications, preventing CPU-GPU parallelism.

## GPU Synchronization Models

**Implicit Sync**: Traditionally, synchronization attached to buffers themselves through DMA fences. The kernel tracked which buffers were read and written, automatically preventing conflicts. This approach is inefficient, requiring kernel monitoring of potentially hundreds of buffers per operation.

**Explicit Sync**: Vulkan introduced explicit synchronization where applications specify dependencies directly using fences and semaphores. This reduces kernel overhead but requires careful application design.

## Bridging Incompatible Worlds

A critical problem emerged: existing window systems (Wayland, X11) assume implicit synchronization, while explicit sync offers better performance. Linux 6.0 (October 2022) provided the solution through new DRM APIs enabling DMA fence import/export between buffers and sync objects.

## OpenGL Complications

OpenGL's design assumes implicit synchronization, creating tensions with explicit sync drivers. The team discovered applications could dynamically share textures after creation:

1. Create texture storage
2. Export as EGL image
3. Export as DMABUF

The driver couldn't anticipate sharing at creation time, requiring buffer reallocation when sharing became necessary.

Additionally, applications could render to buffers before sharing them, potentially losing synchronization information. The solution involved retroactively attaching sync object fences to shared buffers.

## Implementation Details

The Asahi driver employs batch tracking—collecting GPU work into batches rather than submitting immediately. When applications switch framebuffers, new batches form. The system flushes batches when their outputs become dependencies for current work, effectively managing both immediate and deferred execution.

To implement explicit sync, Lina extended batch tracking to monitor submitted-but-incomplete work, using existing reader/writer tracking for dependency management.

## Kernel-Side Developments

Supporting explicit sync required new Rust abstractions for:
- DMA fence mechanisms
- DRM sync objects
- GPU scheduling infrastructure
- Generic kernel data structures (xarray)

Importantly, this work identified memory safety bugs in the shared DRM scheduler component affecting other kernel drivers.

## Additional Features

The update includes support for multiple GPU virtual address spaces, result buffers enabling performance statistics and detailed fault information, compute shader execution, and batch submission with firmware-autonomous dependency resolution.

## Practical Outcomes

For users, performance improvements are substantial. The asynchronous execution model eliminates previous bottlenecks. However, new corner cases emerged—the team identified synchronization issues in certain window manager combinations (particularly Sway), manifesting as temporary graphical artifacts.

The developers acknowledge ongoing work: "there are still bugs to squash" and invite community issue reports on GitHub for reproducible problems.

## Future Direction

The team plans 4K page support (alongside the current 16K implementation) to enable FEX compatibility, potentially allowing Steam/Proton games to run. This bridges x86-64 architecture through emulation.

<!-- Source: https://lwn.net/Articles/995383/ -->
# LWN: Apple M1/M2 GPU Drivers Update (XDC 2024)

*LWN.net — Coverage of Alyssa Rosenzweig's XDC 2024 presentation on Honeykrisp GPU driver*

## Overview

Alyssa Rosenzweig presented updates on the Honeykrisp GPU driver for Apple M1/M2 processors at XDC 2024, covering conformance achievements and gaming support.

## Graphics Standards Conformance

**OpenGL/Vulkan Status:**
- Achieved OpenGL 4.6 conformance (progressed from OpenGL ES 3.1 in previous year)
- Achieved Vulkan 1.3 conformance
- Supports every feature required for multiple DirectX versions

## Tessellation Implementation

**Hardware Limitations:**
The Apple GPU includes a hardware tessellator but cannot be utilized because it lacks critical features required by graphics standards. Missing capabilities include:
- Point mode support
- Isoline support
- Transform feedback support
- Geometry shader support

**Software Tessellation Approach:**
Rather than use hardware tessellation, the driver implements tessellation via software using:
- Microsoft's reference tessellator (circa 2000 lines of C++)
- OpenCL 3.0 support (provided by Karol Herbst, unreleased at talk time)
- Conversion of tessellator code to OpenCL C

**Performance Metrics (terrain tessellation on M2):**
- Software-only: <1 fps
- OpenCL-based: 265 fps
- Hardware-only: 820 fps

## Gaming Support Architecture

**Problem Statement:**
Triple-A game execution requires translation across multiple layers:
- DirectX → Vulkan (via DXVK)
- Windows → Linux (via Wine)
- x86 → Arm64 (via FEX-Emu or Box64)
- 4KB pages → 16KB pages (via virtualization)

**Solution:**
Execution stack deployed within KVM virtual machine using "virtgpu native contexts," enabling GPU work to occur in guest kernel with minimal boundary crossing overhead (>90% native speed).

**Supported Titles:**
Portal, Portal 2, Castle Crashers, The Witcher 3, Fallout 4, Control, Ghostrunner, Cyberpunk 2077

**Performance Results:**
Control ran at 45 fps on M1 MAX system

## Memory Requirements

Minimum 16GB RAM recommended for AAA titles; 8GB systems can run lighter games (Castle Crashers, Portal).

## Release Status

Components made available October 10, 2024 for Fedora Asahi Remix distribution.

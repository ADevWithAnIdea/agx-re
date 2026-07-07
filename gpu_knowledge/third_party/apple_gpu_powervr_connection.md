# Apple AGX GPU and PowerVR: Architecture Connection Analysis

**Sources:**
- https://www.phoronix.com/news/Mesa-AGX-More-PVR-Reference
- https://alyssarosenzweig.ca/blog/asahi-gpu-part-5.html
- https://asahilinux.org/docs/hw/soc/agx/
- https://news.ycombinator.com/item?id=25673631
- https://en.wikipedia.org/wiki/PowerVR
- https://hyeondg.org/gpu/tbr
- https://docs.imgtec.com/starter-guides/powervr-architecture/html/topics/tile-based-deferred-rendering-index.html

---

## Summary

The Apple AGX GPU is described as "heavily PowerVR-inspired (but largely bespoke)" by Asahi Linux developers. Evidence accumulated through reverse engineering suggests significant architectural heritage from Imagination Technologies' PowerVR series.

---

## Evidence of PowerVR Derivation

### 1. Naming Correspondence (Strongest Evidence)
Discovered during reverse engineering of the parameter buffer overflow bug:

> "The Tiled Vertex Buffer is the Parameter Buffer. PB is the PowerVR name, TVB is the public Apple name, and PB is still an **internal Apple name**."

Both architectures use:
- A "Parameter Buffer" / "Tiled Vertex Buffer" to store vertex stage outputs between pipeline stages
- The same two-phase TBDR architecture (tiling → rendering)
- Partial renders when the parameter buffer overflows

### 2. Business Relationship
- Apple maintains a **multi-year license agreement with Imagination Technologies** (announced January 2020)
- All Apple A-series SoCs support **PVRTC (PowerVR Texture Compression)**, indicating continued reliance on Imagination IP

### 3. Mesa Driver Code Similarities
Phoronix reported in 2022-2023 that Mesa AGX driver work revealed additional commonality between PowerVR graphics hardware and Apple AGX:
- Shared memory structure patterns
- Common approach to tiling algorithm implementation
- Source: https://www.phoronix.com/news/Mesa-AGX-More-PVR-Reference

### 4. Shared TBDR Architecture
Both use identical two-phase tile-based deferred rendering:

**Phase 1 - Tiling (Vertex):**
- All vertex shaders run across the entire frame
- Geometry is binned into tiles based on screen position
- Outputs (varyings/interpolants) stored in parameter buffer in main memory

**Phase 2 - Rendering (Fragment):**
- Each tile processed independently
- Tile color/depth/stencil data lives in fast on-chip memory (tile buffer)
- Fragment shaders only run on visible/surviving geometry (hidden surface removal)

### 5. Dual-Dispatch Architecture
From philipturner/metal-benchmarks analysis:
> "Apple's dual-dispatch from 2 simds mode is a remnant of the PowerVR architecture, which could only execute F32 instructions at 2 IPC."

---

## PowerVR TBDR Architecture (Reference)

From Imagination Technologies documentation:

### Core Concept
Rather than immediate rendering (IMR), PowerVR:
> "Captures the whole scene before starting to render, so occluded pixels can be identified and rejected before they are processed."

### Tiling Process
- Screen divided into small rectangular regions (tiles)
- Each tile undergoes independent rasterization
- All data stays in fast on-chip memory during tile processing
- "Perfect tiling" algorithm determines exact triangle coverage (not bounding boxes)

### Deferred Rendering Strategy
- All texturing and shading deferred "until all objects have been tested for visibility"
- **Hidden Surface Removal (HSR):** eliminates overdraw entirely for opaque geometry
- Unlike IMR: only the frontmost fragment per pixel is shaded

### Pipeline Structure
- **Tiler:** Handles vertex processing and tiling operations
- **Renderer:** Manages rasterization and subsequent processing stages

---

## Apple's Divergences from PowerVR

Despite architectural similarities, Apple has made significant proprietary additions:

### 1. Sample Shading Innovation
- Hardware executes shaders once per pixel while allowing instruction-level output to different samples
- Enables compiler optimizations not possible in standard PowerVR designs

### 2. Software Blending
- Blending operations execute in shader code (not fixed-function hardware)
- Enables "sophisticated compiler optimizations" for the blending stage
- Standard PowerVR has fixed-function blending hardware

### 3. Larger Scale
- Apple AGX scaled to desktop/laptop performance levels
- PowerVR primarily targets mobile
- Significantly more shader cores, larger caches, higher bandwidth

### 4. Unified Memory Architecture
- Tight integration with CPU memory subsystem
- Shared LLC (System Level Cache)
- Very high bandwidth: 60 GB/s (M1) to 100+ GB/s (M4)

---

## Degree of Derivation: Uncertain

The community consensus is that:
1. AGX shares significant architectural DNA with PowerVR
2. But has diverged substantially through Apple's own engineering
3. The exact scope of IP licensing vs. independent development remains unclear
4. "It could be a Custom GPU, but it still has plenty of PowerVR tech in it"

---

## TBDR vs. Immediate Mode Rendering (IMR)

For context (both PowerVR and AGX use TBDR):

| Feature | TBDR (PowerVR/AGX) | IMR (NVIDIA/AMD discrete) |
|---------|---------------------|--------------------------|
| Rendering order | Deferred until full frame collected | Immediate per draw call |
| Tile memory | Fast on-chip (~1-5 MB) | N/A (direct framebuffer) |
| Memory bandwidth | Low (tile memory reduces DRAM traffic) | High (constant DRAM access) |
| Overdraw | Eliminated for opaque (HSR) | Full shading per fragment |
| Power efficiency | High (mobile-suitable) | Lower (requires VRAM) |
| Programmable blending | Native (tile memory access) | Complex (framebuffer reads expensive) |

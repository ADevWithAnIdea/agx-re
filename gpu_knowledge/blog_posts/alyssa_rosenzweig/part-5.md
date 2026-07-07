# The Apple GPU and the Impossible Bug (Part V)

**Source URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-5.html  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 13 May 2022  
**Project:** Asahi Linux  

---

## Overview

This post documents the discovery and resolution of a critical GPU rendering bug — partial rendering failures when drawing complex geometry. The investigation revealed a fundamental aspect of the AGX architecture: its behavior as a tile-based deferred renderer with a fixed-size parameter buffer (tiled vertex buffer), and the need for auxiliary GPU programs to handle buffer overflow conditions ("partial renders").

---

## The Bug: Symptoms

The driver failed to correctly render large amounts of geometry. Symptoms:

- Simple scenes rendered correctly
- Complex scenes (many vertices and/or large per-vertex data) rendered incorrectly
- Rendering would partially complete, then produce GPU faults
- The failure was not related to shader complexity alone

**Key observation:** The failure correlated with the **product** of:
```
(number of vertices) × (amount of per-vertex data)
```

---

## Initial Hypothesis: Timing Issue

The author initially suspected a timing/synchronization issue. A test was constructed:

```c
for (int i = 0; i < LARGE_NUMBER; ++i) {
    /* some work to prevent the optimizer from removing the loop */
}
```

This test (burning CPU/GPU time to rule out race conditions) did not reproduce the bug, ruling out timing as the cause.

---

## AGX Architecture: Tile-Based Deferred Rendering

### Background: Immediate Mode vs. Tile-Based

**Immediate mode renderers** (traditional desktop GPUs like Intel/AMD/NVIDIA):
- Process each triangle as it is submitted
- Write directly to main memory framebuffer
- High memory bandwidth consumption

**Tile-based deferred renderers** (mobile/Apple GPUs):
- Collect all geometry for the entire frame
- Divide the screen into small tiles (e.g., 32×32 or 64×64 pixels)
- Process all triangles that overlap each tile
- Use a small, fast "tilebuffer" (on-chip SRAM, a few kilobytes) as a temporary framebuffer
- Only write final tile results to main memory

**Advantage:** Dramatically reduced main memory bandwidth (reads/writes happen on-chip, not to DRAM).

### AGX Rendering Pipeline

```
1. TILING PHASE (vertex shaders + geometry processing)
   - All vertex shaders execute for the entire frame
   - Hardware "tiler" determines which triangles overlap which tiles
   - Results stored in "Parameter Buffer" / "Tiled Vertex Buffer" (TVB)

2. FRAGMENT PHASE (per-tile processing)
   - For each tile:
     a. Load tile data from tilebuffer (or initialize)
     b. Execute fragment shaders for all triangles in this tile
     c. Store tile results back to main memory
```

### The Parameter Buffer (Tiled Vertex Buffer / TVB)

The **Parameter Buffer** (Apple terminology: "Tiled Vertex Buffer") is a region of **system memory** that stores:

- All post-transform vertex outputs from the tiling phase
- Per-triangle metadata for the tiler
- Data needed by the fragment phase to reconstruct interpolated vertex outputs

**Apple WWDC documentation stated:** "The Tiled Vertex Buffer stores tiling phase output" and "causes a Partial Render if full."

**PowerVR documentation** (AGX's rumored historical predecessor) described it as the "Parameter Buffer" and noted: "Each varying [interpolated vertex output] requires additional space in the parameter buffer."

---

## Partial Renders: The Core Mechanism

When the Parameter Buffer fills up, the GPU performs a **Partial Render**:

1. GPU pauses the tiling phase
2. GPU flushes current tile results to main memory (fragment phase runs on what's tiled so far)
3. GPU resets/clears the Parameter Buffer
4. GPU resumes tiling from where it left off
5. Process repeats as needed

This allows rendering scenes with arbitrary geometry complexity at the cost of performance (each partial render requires additional memory bandwidth).

### Dynamic Parameter Buffer Sizing

Apple's implementation uses **adaptive/dynamic sizing**:

- Initially allocates a small Parameter Buffer
- Grows it responsively when overflow occurs
- Balances memory usage against performance

---

## Root Cause: Missing Auxiliary GPU Programs

The driver was missing **auxiliary GPU programs** required by the partial render mechanism.

### The Two Required Programs

#### 1. Tilebuffer Load Program

When a partial render occurs and the GPU needs to restart fragment processing for a tile, it needs to **reload** the current state of the tilebuffer from main memory.

The **load program** is a small GPU shader that:
- Reads the current framebuffer contents from main memory
- Loads them back into the on-chip tilebuffer
- Allows the fragment shader to continue accumulating results correctly

Without this program, the GPU would start each partial render with a cleared tilebuffer, losing previous rendering results.

#### 2. Depth Buffer Management Program

The depth buffer also requires special handling across partial render boundaries:

- The depth buffer must be flushed to main memory before the partial render
- It must be reloaded correctly when resuming
- Without proper depth buffer coordination, depth testing artifacts occur

---

## Debugging: Depth Buffer Artifacts

Even after implementing the tilebuffer load program, depth buffer artifacts persisted. Investigation steps:

1. Confirmed tilebuffer reload was working correctly
2. Observed incorrect depth test results at partial render boundaries
3. Traced Metal driver behavior for specific depth buffer configuration parameters
4. Identified that specific hardware configuration bits control depth buffer flushing/reloading behavior during partial renders

**Resolution:** Matching Metal's configuration exactly for these depth buffer parameters resolved the artifacts.

---

## Validation: Metal Memory Stomping Test

The author used a **"Metal memory stomping"** test to validate hypotheses:

- Write specific values to GPU memory regions
- Observe which values are read/used by Metal's GPU programs
- Confirm which memory regions correspond to which GPU programs
- Verify the structure of auxiliary programs by comparing against Metal-generated programs

---

## Performance Counters

The author used GPU performance counters to:
- Count the number of partial renders occurring
- Measure parameter buffer utilization
- Confirm the parameter buffer overflow was the cause of failures

---

## Resolution Summary

The bug was resolved by:

1. **Implementing the tilebuffer load program:** A GPU shader that reloads framebuffer contents from main memory when resuming after a partial render
2. **Implementing depth buffer coordination:** Proper flush/reload of the depth buffer across partial render boundaries
3. **Matching Metal's configuration:** Using the same hardware parameter settings as Metal for depth buffer behavior during partial renders

---

## Architecture Insight

This bug revealed a fundamental aspect of tile-based deferred rendering that is not obvious from API-level documentation:

> A tile-based GPU driver must provide not just vertex and fragment shaders, but also **auxiliary programs** for managing the tilebuffer and depth buffer across partial render operations.

The API (OpenGL/Vulkan) hides this complexity from applications; the driver must handle it transparently.

---

## References

- WWDC 2020 presentation — Apple's documentation of the Tiled Vertex Buffer
- PowerVR Optimization Guide — Imagination Technologies documentation of the Parameter Buffer
- Asahi Linux project: https://asahilinux.org

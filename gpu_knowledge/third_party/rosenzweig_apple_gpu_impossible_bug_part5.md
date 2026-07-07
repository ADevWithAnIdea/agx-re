# The Apple GPU and the Impossible Bug (Part V)

**Source:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-5.html  
**Also at:** https://rosenzweig.io/blog/asahi-gpu-part-5.html  
**Author:** Alyssa Rosenzweig  
**LWN.net coverage:** https://lwn.net/Articles/916208/

---

## Summary

Part V is a pivotal article documenting the discovery of the **Parameter Buffer (PB)** / **Tiled Vertex Buffer (TVB)** - the critical memory structure in Apple's TBDR GPU that stores intermediate vertex data between shader stages. This article explains the "impossible bug" where complex geometry+shader combinations caused GPU faults.

---

## The Problem

Driver failed to render large amounts of geometry combined with complex shaders:
- Simple geometry: renders fine
- Complex shaders alone: renders fine
- Both together: GPU faults, partial results only

The critical variable was: **vertex count × per-vertex data size** (i.e., total varying/attribute data size).

---

## TBDR Architecture: The Parameter Buffer

AGX operates as a **tile-based deferred renderer (TBDR)** - a mobile GPU architecture:

### Two-Stage Pipeline
1. **Tiling phase (TA - Tiler/Vertex):** All vertex shaders run first, across the entire frame
   - Outputs (varyings/interpolants) are buffered in main memory
   - This buffer is the **Parameter Buffer (PB)**, publicly called the **Tiled Vertex Buffer (TVB)**

2. **Rendering phase (3D - Fragment):** Fragment shaders run, tile by tile
   - Each tile reads its geometry from the PB
   - Tile framebuffer data stays in fast on-chip memory

### The PB Name Discovery
> "The Tiled Vertex Buffer is the Parameter Buffer. PB is the PowerVR name, TVB is the public Apple name, and PB is still an internal Apple name."

This naming correspondence was strong evidence of PowerVR heritage in the AGX design.

---

## The "Impossible Bug" Root Cause

According to Apple's documentation: when the parameter buffer fills, the GPU should execute a **partial render** - flushing completed geometry and restarting vertex processing for remaining geometry.

The driver was **not providing the auxiliary shader programs required for partial render recovery**:

1. No shader to reload framebuffer contents after partial render
2. No depth buffer flush configuration for partial render operations

The kernel/firmware dynamically resizes the parameter buffer in response to overflow, but without the proper auxiliary programs, the recovery path was broken.

---

## Fix Components

1. **Reload shader:** Dedicated shader program to reload framebuffer contents after a partial render
2. **Depth configuration:** Configure depth buffer flushing for partial render operations
3. **Recognition:** Understand that firmware dynamically resizes the TVB/PB heap

After fix: "The bunny now renders correctly."

---

## PowerVR Connection

The use of internal Apple name "PB" matching PowerVR's "Parameter Buffer" terminology is one of the strongest pieces of evidence for AGX being PowerVR-derived. Both architectures:
- Use a parameter buffer to store vertex stage outputs
- Perform tile-based deferred rendering with two phases
- Support partial renders when the parameter buffer overflows

---

## Significance

This article:
1. Documented the TBDR two-pass architecture for the first time in the OSS driver context
2. Identified the TVB/PB naming correspondence with PowerVR
3. Showed that complex inter-shader state management is handled in firmware
4. Explained why a shader complexity + geometry complexity interaction caused failures

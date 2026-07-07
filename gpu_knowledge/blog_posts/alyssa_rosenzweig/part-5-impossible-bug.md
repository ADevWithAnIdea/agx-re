<!-- Source: https://alyssarosenzweig.ca/blog/asahi-gpu-part-5.html -->
# Apple GPU and the Impossible Bug (Part 5)

*By Alyssa Rosenzweig*

## Overview

This post documents debugging a critical GPU rendering failure in Apple's AGX architecture during open-source driver development for Asahi Linux.

## Core Problem Statement

The driver exhibited partial rendering failures when processing large geometry volumes. As described: "The driver fails to render large amounts of geometry. Spinning a cube is fine, low polygon geometry is okay, but detailed models won't render."

## Hardware Architecture Analysis

**GPU Type**: Apple's AGX is classified as a tile-based deferred renderer (TBDR), derived from Imagination's PowerVR series.

**Key Architectural Differences**:

Traditional immediate mode renderers process: vertex shader → fragment shader → framebuffer in sequence.

Tile-based deferred renderers operate in phases:
- All vertex shaders execute for entire frame
- Tiler hardware determines triangle-to-tile assignments
- Per-tile fragment shader execution with tilebuffer caching

The tilebuffer (a few kilobytes) provides fast access compared to main memory, reducing bandwidth for mobile-class GPUs.

## Critical Discovery: Parameter Buffer Overflow

The investigation revealed the failure mechanism: "Because AGX is a tiler, it requires a buffer of _all_ per-vertex data. We fault when we use too _much_ total per-vertex data, overflowing the buffer."

The problematic metric: **vertices × interpolated data per vertex = total per-vertex data volume**

## Supporting Documentation Found

From Apple's WWDC presentation:
- "The Tiled Vertex Buffer stores the Tiling phase output, which includes the post-transform vertex data"
- Mechanism: "A Partial Render is when the GPU splits the render pass in order to flush the contents of that buffer"

PowerVR documentation confirmed this behavior involves system memory allocation for the "parameter buffer."

## Partial Render Handling Requirements

The driver required three auxiliary shader programs:
1. Initial tilebuffer load (with clear or framebuffer preservation)
2. Partial render load (framebuffer reload after overflow flush)
3. Store program for final render completion

## Depth Buffer Complexity

Partial renders introduced a secondary issue: depth buffer state preservation across render splits required additional configuration for proper pixel occlusion testing.

## Resolution

Implementing proper tilebuffer reload shaders and depth buffer flush configuration resolved the rendering artifacts on complex geometry.

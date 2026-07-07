# Harness Apple GPUs with Metal

Source: https://developer.apple.com/videos/play/wwdc2020/10602/
Event: WWDC 2020 (Session 10602)
Speaker: Guillem Vinals, Metal Ecosystem Team, Apple
Fetched: 2026-05-09

## Session Description

Create visually stunning, high-performance apps and games by combining the power of Apple GPUs
with Metal. This session discusses the architecture and capabilities of the Apple GPU and how
Metal harnesses its tile-based deferred rendering (TBDR) architecture to achieve measurable
performance gains.

Prerequisite: Basic knowledge of Metal and graphics rendering.

---

## Part 1: Apple TBDR GPU Fundamentals

### Why Apple GPUs Matter
- Power over 1 billion Apple devices worldwide with integrated GPUs
- Power efficient architecture design
- Unified memory architecture - CPU and GPU share System Memory
- Dedicated on-chip Tile Memory for efficient processing
- No dedicated video memory - requires optimized content to avoid bandwidth issues

### TBDR Architecture Basics

TBDR = Tile Based Deferred Renderer

Two main phases in the rendering pipeline:

```
1. TILING PHASE
   - Split viewport into tiles
   - Shade all vertices
   - Bin transformed primitives into tile lists

2. RENDERING PHASE
   - Process all tiles separately
   - Execute per-tile load actions
   - Rasterize primitives and compute visibility
   - Shade visible pixels
   - Execute per-tile store actions
```

### Tiling Phase Details
- **Tiled Vertex Buffer**: Stores post-transform vertex data and internal structures
- Mostly opaque to applications
- May cause **Partial Renders** if buffer fills up (GPU flushes buffer contents)

### Rendering Phase Details

#### Load and Store Actions
- Executed per-tile at beginning and end of render passes
- Critical for efficiency

Load Action Best Practices:
- Only load data you need
- Use Clear instead of Load when data isn't needed
- Saves memory transfers for color attachments, depth, and stencil buffers

Store Action Best Practices:
- Only store necessary data (e.g., main color attachment)
- Critical for render efficiency
- Avoid storing intermediate targets unnecessarily

#### Hidden Surface Removal (HSR)

Key capability: Minimize overdraw before fragment shading

Characteristics:
- Operates on on-chip depth buffer
- Pixel perfect and submission order independent
- Tracks the frontmost visible layer per pixel
- Defers fragment shader execution until visibility is certain

HSR Process (example: blue opaque, orange opaque, purple translucent, back to front):
1. Blue triangle: Rasterize, populate depth/primitive ID
2. Orange triangle: Update depth/primitive ID (no fragment shader yet)
3. Purple triangle (translucent): HSR flushes opaque pixels first, then processes blended primitive
4. End of pass: Flush remaining visible pixels

Result: Pixels may be shaded once despite multiple overlapping primitives = no overdraw.

Optimal Submission Order for HSR Efficiency:
```
1. All opaque geometry (unsorted is fine)
2. Alpha test / depth feedback meshes
3. Translucent meshes
```

Avoid:
- Interleaving opaque and non-opaque meshes
- Interleaving opaque meshes with different color attachment write masks
- Mixed visibility states in submission order

### Fragment Processing Stage
- Operates on on-chip frame buffer (Tile Memory)
- Alpha Blending always happens in Tile Memory
- No dedicated blending unit
- Render target written only during store actions

Special: Discard or depth update operations loop back to HSR

### Programmable Blending

Problem: Custom blending for effects like global fog or deferred lighting requires multi-pass.
Traditional approach needs to store all attachments between passes.

TBDR Solution:
- Fragment shaders access pixel data directly from Tile Memory
- Merge multiple render passes into one
- Drastically improve memory bandwidth
- No need to load/store intermediate render targets

### Memoryless Render Targets

Problem: Intermediate render targets used only within Tile Memory waste memory footprint.

Solution: Define textures with memoryless storage mode:
- Eliminates unnecessary allocations
- Saves precious memory footprint
- Particularly useful with Programmable Blending

### Multisample Anti-Aliasing (MSAA)

Apple GPU efficiency features:
1. **Edge tracking**: Pixels without edges blend per-pixel; pixels with edges blend per-sample
2. **On-chip storage**: Multiple samples stored in Tile Memory; resolve only when tile flushes
3. **Memoryless support**: Can use memoryless storage for multisample textures

Efficient MSAA Implementation:
- Use efficient Resolve action from Tile Memory
- Make multisample texture fully transient (memoryless)
- Resolve never requires storing samples

---

## Part 2: Modern Apple GPUs (A11+)

Starting with A11 Bionic, major GPU redesign occurred.

### Imageblock

What it is: 2D data structure in Tile Memory
- Has width, height, and pixel depth
- Accessible by fragment or kernel functions

Benefits:
- Single-operation load/store of image data (vs. pixel-by-pixel previously)
- Much more efficient for image-based algorithms
- GPU understands you're operating on image data

### Tile Shaders

What they are: Compute kernels dispatched to access Imageblock mid-render pass

Characteristics:
- Dispatches interleaved with draw calls in API submission order
- Barrier against earlier and later draw calls (automatic synchronization)
- Full tile-level access (vs. single-pixel Programmable Blending)

### Imageblock Sample Coverage Control (MSAA Enhancement)

Provides access to each pixel's sample coverage tracking data.

Use case: Complex scenes with opaque + translucent geometry
- Problem: Many small translucent triangles = high samples/pixel overhead
- Solution: Resolve sample data with tile shader after opaque rendering
- Benefit: All pixels contain single unique color before heavy blending phase

Advanced capability: Custom per-render-target resolve (HDR color, linear depth, etc.)

---

## Metal Integration

Metal is designed for Apple GPUs:

### Exposed Features
- Unified graphics and compute architecture
- TBDR-specific features:
  - Programmable Blending
  - Memoryless Render Targets
  - Tile Shaders
  - Imageblocks
- Explicit submission model
- Explicit multi-threading
- Deep hardware-software integration

### Advanced Technique 1: Tiled Deferred Rendering

Standard deferred rendering flow:
```
G-Buffer Pass -> Light Accumulation Pass
(bandwidth-heavy, large memory footprint)
```

Tiled deferred via Tile Shaders (single pass):
```
G-Buffer Pass -> Tile Shading (Light Cull) -> Single Merged Pass
(G-Buffer stays in tile memory throughout)
```

### Advanced Technique 2: GPU-Driven Rendering

Traditional CPU-driven render loop problems:
- Complex scene traversal on CPU
- Occlusion culling decisions
- LOD selection
- Synchronization points (CPU reads GPU data -> stalls)

Metal Solution - Building blocks:
- **Argument Buffers**: Make scene data available on GPU; describe complex data structures
- **Indirect Command Buffers**: Allow GPU to encode its own draw calls; eliminate CPU-GPU sync

GPU-driven render loop:
```
1. GPU traverses scene, renders occluders
2. GPU traverses scene again, performs culling & LOD selection
3. GPU renders final scene
-> Zero CPU-GPU synchronization points
```

---

## Deferred Rendering Optimization Summary

Traditional approach (bandwidth/memory heavy):
- Pass 1: Render G-Buffer (albedo, normals, roughness) -> store to system memory
- Pass 2: Load from system memory, do lighting

TBDR-optimized with Metal:
- Programmable Blending: Merge passes
- Efficient load/store actions: Minimize transfers
- Memoryless render targets: Eliminate intermediate storage
- Tile Shaders: Keep G-Buffer in tile memory throughout

Result: Efficient in both memory footprint and bandwidth

---

## Resources

Video Downloads:
- HD: https://devstreaming-cdn.apple.com/videos/wwdc/2020/10602/7/7EE751FE-713A-4E04-8780-38491023B7B8/wwdc2020_10602_hd.mp4?dl=1
- SD: https://devstreaming-cdn.apple.com/videos/wwdc/2020/10602/7/7EE751FE-713A-4E04-8780-38491023B7B8/wwdc2020_10602_sd.mp4?dl=1

Sample Code:
- Deferred Lighting: https://developer.apple.com/documentation/Metal/rendering-a-scene-with-deferred-lighting-in-objective-c
- Modern Rendering with Metal: https://developer.apple.com/documentation/Metal/modern-rendering-with-metal

Related Sessions:
- Optimize Metal apps and games with GPU counters (WWDC20): https://developer.apple.com/videos/play/wwdc2020/10603/
- Optimize Metal Performance for Apple silicon Macs (WWDC20): https://developer.apple.com/videos/play/wwdc2020/10632/

---

## Key Takeaways

1. TBDR architecture is foundational to Apple GPU efficiency
2. Optimize load/store actions - only transfer necessary data
3. HSR efficiency maximized by submission order (opaque -> alpha -> translucent)
4. Tile Memory is precious - use memoryless render targets when appropriate
5. Programmable Blending + Imageblocks enable advanced multi-pass merging
6. GPU-driven rendering eliminates CPU-GPU synchronization
7. Metal is specifically designed to expose and optimize for Apple GPU architecture

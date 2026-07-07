# Optimize Metal Apps and Games with GPU Counters

Source: https://developer.apple.com/videos/play/wwdc2020/10603/
Event: WWDC 2020 (Session 10603)
Speaker: Guillem Vinals Gangolells, Metal Ecosystem Team, Apple
Fetched: 2026-05-09

## Session Description

GPU counters can help you precisely measure GPU utilization to pinpoint bottlenecks and
optimize workloads for your Metal apps and games. Covers tools in Metal System Trace
(Instruments) and Metal Debugger (Xcode 12), and how to use collected data to discover
underused and overworked stages of your GPU pipeline.

Prerequisites: Understanding of TBDR architecture of Apple GPUs, familiarity with Metal
best practices.

---

## Apple GPU Architecture Overview

### Key Characteristics
- Part of Apple processors (A13, A12Z, etc.)
- Power efficient with unified memory architecture
- Unified Memory System: CPU and GPU share System Memory
- On-chip Tile Memory for efficient local storage
- No dedicated Video Memory: relies on bandwidth optimization
- TBDR Architecture: Tile Based Deferred Renderer

### GPU Configuration

Each GPU core contains:
- Shader Core
- Texture Unit (TPU)
- Pixel Backend
- Dedicated pool of Tile Memory

Memory hierarchy per GPU core:
- **L1 Caches:** Dedicated to ALU and TPU
- **Shared Last Level Cache (LLC):** Across all GPU cores
- **System Memory:** DRAM with unified memory architecture

---

## GPU Rendering Pipeline

### Two Distinct Phases

**1. Tiling Phase**
- Split viewport into tiles for the entire render pass
- Shade all vertices
- Bin transformed primitives into tiles

**2. Rendering Phase**
- GPU shades tiles separately
- Each GPU core shades at least one tile at a time
- Per-tile execution:
  - Execute load action
  - Rasterize and compute visibility
  - Shade visible pixels
  - Execute store action

Scalability: More GPU cores = more tiles shaded in parallel.

---

## GPU Performance Counters

- **Total Available Counters:** Over 150 GPU counters
- **Access Points:** Metal System Trace (Instruments) and Metal Debugger (Xcode)
- **Granularity:** Per encoder or per draw call

---

## Performance Limiter Counters

The GPU is only as fast as its slowest subsystem. Limiter counters measure activity across
GPU subsystems to identify bottlenecks.

### 1. ALU (Arithmetic Logic Unit) Limiter

Part of the Shader Core. Processes arithmetic, bit-wise, and relational operations.

**Operation Throughput (Relative):**
- **16-bit floating point:** Double rate (PREFERRED)
- **32-bit floating point:** Full rate
- **32-bit integer/complex operations:** Half rate or less (avoid)

**Execution Model:**

Coherent Execution (best case):
```
All threads in SIMD execute same instruction
Total cost: 40 cycles (no penalty)
```

Divergent Execution (inefficient):
```
Threads diverge at branch point
All threads still spend cycles (masked)
Total cost: 70 cycles (30 cycle penalty)
```

**Optimization Strategies:**
- Replace complex calculations with approximations or lookup tables
- Prefer half-precision (F16) over full-precision (F32)
- Avoid implicit type conversions
- Avoid FP32 inputs (textures, buffers)
- Compile with `-ffast-math` flag

**Important:** High ALU limiter != High efficiency. Example: 100% ALU limited but only
50% utilization if using FP32 operations only.

### 2. Texture Read and Write Limiters

**Texture Unit (TPU) - Read Operations:**
- Backed by Device Memory
- Dedicated L1 cache
- Supports multiple filtering and compression modes

**Pixel Format Impact (Sampling Rate):**
- Standard formats: Full rate
- 128-bit formats (RGBA32Float): Quarter rate (avoid for noise textures, etc.)

**Compression Support:**
- Block-compressed formats: PVRTC, ASTC
- Lossless compression of conventional pixel formats
- Example: ASTC HDR reduces 3MB uncompressed cube map significantly

**Optimization for High Texture Sample Limiter:**
- Use mipmaps for likely minification
- Change filtering options (reduce anisotropic sample count)
- Use smaller pixel sizes
- Leverage texture compression (ASTC for assets, lossless for runtime-generated)

**Texture Write Operations:**
Textures written by Pixel Backend when:
- Render pass executes StoreActionStore
- Explicitly writing from shader

Key considerations:
- Avoid divergent writes (different array indices, tiles)
- Keep small pixel sizes
- Watch out for MSAA impact

Note: Pixel Backend and TPU are separate hardware blocks with different throughput.

### 3. Tile Memory Load and Store Limiters

Tile Memory accessed when:
- Reading/writing pixel data from Imageblock (tile shaders)
- Reading/writing Threadgroup Memory (compute dispatches)
- Reading/writing render pass color attachments (programmable blending)

**Optimization:**
- For complex compute shaders with threadgroup memory:
  - Reduce threadgroup atomics
  - Use threadgroup parallel reductions
  - Use SIMD lane operations instead
- Align threadgroup memory to 16-byte boundaries
- Reorder memory access patterns for efficiency

Tool terminology: "Imageblock" and "Threadgroup Memory" in tools and documentation.

### 4. Buffer Read and Write Limiters

**Metal Buffer Characteristics:**
- Backed by Device Memory
- Accessed only by Shader Core
- Dedicated L1 cache
- Support for different address spaces

**Address Space Usage:**
- `device`: Read-write data indexed per fragment/vertex
- `constant`: Read-only data utilized by many vertices/fragments

**Optimization Strategies:**
- Pack data more tightly
- Use smaller data types
- Vectorize load and store operations
- Avoid device atomics
- Avoid register spills
- Consider using textures to balance workload (ALU vs TPU have different caches)

### 5. GPU Last Level Cache (LLC) Limiter

**Characteristics:**
- Shared across all GPU cores
- Caches texture and buffer data
- Stores device atomics
- Optimized for spatial and temporal locality

**Memory Hierarchy Peak Rates (Relative):**
1. Tile Memory (fastest)
2. GPU LLC
3. System Memory (slowest)

**Optimization:**
- Favor Tile Memory over GPU LLC
- Watch for atomic operations (they stress LLC)
- If texture/buffer limiters also high, optimize those first
- Reduce working set sizes
- Refactor device atomics to threadgroup atomics
- Improve spatial and temporal locality

### 6. Fragment Input Interpolation Limiter

- Interpolated during rendering by Shader Core
- Fixed-function dedicated interpolator
- Full precision
- Only mitigation: Remove unnecessary vertex attributes from Fragment Shader

---

## Memory Bandwidth Counter

Measures data transfers from System Memory to GPU.

**Optimization:**
- If texture/buffer limiters high, optimize those first
- Ensure load/store instructions are efficient
- Only load data needed by current render pass
- Only store data needed by future render passes
- Leverage texture compression (major impact)

---

## Occupancy Counter

**Definition:** Percentage of total thread capacity being used by GPU.

- Low occupancy: Only fraction of thread pool executing
- 100% occupancy: GPU runs maximum tasks possible
- GPUs hide latency by switching between available threads

**Composition:** Sum of Compute + Vertex + Fragment Occupancy

**Neither high nor low occupancy inherently indicates problems**

**When to Investigate:**
- Low Vertex Occupancy: Fine if Fragment Occupancy is high
- Low overall occupancy: Can indicate:
  - Shaders exhausted internal resources (tile/threadgroup memory)
  - Threads finish faster than new ones created
  - Small render area or compute grid
  - Limited work to parallelize

**Optimization:**
- Correlate occupancy with other counter data
- High overlap between tiling, rendering, compute increases occupancy
- Query static pipeline properties:
  - Maximum threads per threadgroup
  - SIMD execution width
  - Required threadgroup memory allocation

---

## Hidden Surface Removal (HSR) Efficiency

**HSR Overview:**
- Early visibility pass minimizing overdraw
- Pixel-perfect and submission-order independent for opaque meshes
- Processes pixels in two stages: HSR then Fragment Processing

**Measuring HSR Efficiency:**

Use GPU counters to measure:
- Pixels rasterized
- Fragment Shader invocations
- Pixels stored
- Pre-Z test fails

Overdraw Calculation:
```
Overdraw = Fragment Shader Invocations / Pixels Stored
```

**Optimization Strategies:**

Draw Order (Critical):
1. Opaque meshes (early)
2. Alpha test, discard, depth feedback
3. Translucent meshes (last)

Avoid:
- Interleaving opaque and non-opaque meshes
- Interleaving opaque meshes with different color attachment write masks
- Full-screen passes when possible
- Excessive blending

---

## Development Tools

### Metal System Trace (Instruments)

**Purpose:** Performance overview and GPU profiling

**Features:**
- CPU and GPU timelines
- Game Performance template (pre-configured)
- GPU performance counters for identifying bottlenecks
- Affected by thermals and dynamic system changes

**Configuration:**
1. Select Game Performance template
2. Select device and application
3. Long-press Record, then Recording Options
4. Switch to Metal Application options
5. Select GPU Counter Set (e.g., Performance Limiters)
6. Optional: Enable Shader Timeline

### Metal Debugger (Xcode)

**Purpose:** Deep performance investigation with detailed metrics

**Features:**
- Detailed GPU timeline
- Metal API usage visualization
- All 150+ GPU counters exposed at encoder granularity
- Large subset of counters per draw call
- Unaffected by thermals or dynamic system changes
- Per-draw counter inspection

**Key Improvements:**
- Counters organized into groups (Memory, Performance Limiters, etc.)
- Filter functionality (e.g., "ALU", "Texture", "Buffer")
- Custom group creation for saved filters
- Detail table linked with graph visualization

---

## Practical Case Study: Respawnables Heroes

**Platform:** iPad Pro
**Features:** Reflections, dynamic lighting, shadows, post-processing

**Performance Challenge:** Deferred Phase Encoder taking 1.29ms (50-50 split vertex/fragment)

**Analysis Process:**
1. Capture in Metal System Trace: Record Performance Limiters counter set, enable Shader Timeline
2. Identify Limiter: ALU Limiter highest during deferred phase
3. Deep Dive in Metal Debugger: Switch to Per-Draw Counters mode, sort by memory bandwidth
4. Find Root Cause: RGBA16 floating-point cube map texture with Shared storage mode (prevented compression)

**Optimizations Applied:**
- Change texture storage mode to Private (enables lossless compression)
- Consider block compression (ASTC)
- Increase FP16 utilization (reduce FP32)

**Results:** Steady 120 FPS on iPad Pro

---

## Resources

Video Downloads:
- HD: https://devstreaming-cdn.apple.com/videos/wwdc/2020/10603/10/54C8A5DF-3A48-4879-8368-234E2AF76D3E/wwdc2020_10603_hd.mp4?dl=1
- SD: https://devstreaming-cdn.apple.com/videos/wwdc/2020/10603/10/54C8A5DF-3A48-4879-8368-234E2AF76D3E/wwdc2020_10603_sd.mp4?dl=1

Related Sessions:
- Harness Apple GPUs with Metal (WWDC20): https://developer.apple.com/videos/play/wwdc2020/10602/
- Optimize Metal Performance for Apple silicon Macs (WWDC20): https://developer.apple.com/videos/play/wwdc2020/10632/
- Discover Metal debugging, profiling, and asset creation tools (WWDC21): https://developer.apple.com/videos/play/wwdc2021/10156/
- Optimize high-end games for Apple GPUs (WWDC21): https://developer.apple.com/videos/play/wwdc2021/10150/

---

## Key Takeaways

1. Profile First: Use Metal System Trace and Metal Debugger to identify bottlenecks
2. Focus on Limiters: Start with performance limiter counters
3. Understand Your Pipeline: Know TBDR architecture and GPU memory hierarchy
4. Optimize Data: Texture compression and buffer packing yield major gains
5. Prefer Precision Reduction: F16 over F32 when possible
6. Memory Matters: Bandwidth is critical on unified memory systems
7. Draw Smart: Proper draw ordering for HSR efficiency
8. Iterate: Use tools to measure impact of optimizations

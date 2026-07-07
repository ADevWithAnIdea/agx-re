# GPU Advancements in M3 and A17 Pro
<!-- Source: https://developer.apple.com/videos/play/tech-talks/111375/ -->
<!-- Apple Family 9 GPU (A17 Pro / M3) architecture overview -->

## Overview
Apple Family 9 GPU (A17 Pro / M3) introduces four major advancements:
1. Next-generation shader core with dynamic caching
2. Hardware-accelerated ray tracing
3. Hardware-accelerated mesh shading
4. Significant performance improvements

---

## 1. Shader Core: Dynamic Caching

### Dynamic Shader Core Memory
- Registers are now dynamically allocated/deallocated over a shader's lifetime
- Previously: pre-allocated maximum usage for entire shader lifetime
- Register file now functions as a **cache** rather than permanent storage
- Enables more SIMDgroups to run concurrently on a single shader core
- Improves thread occupancy significantly

### Flexible On-Chip Memory (Unified)
Architecture change: single unified on-chip memory pool serving:
- Registers
- Threadgroup memory
- Tile memory (TBDR tile buffer)
- Stack memory
- Buffer data cache

Benefits:
- Register-heavy shaders: higher occupancy
- Buffer-heavy shaders: better cache hit rates, lower latency
- Function-pointer intensive apps: more on-chip stack space

### High-Performance ALU Pipelines
- FP16, FP32, and Integer operations can execute in parallel
- 2x greater parallel execution degree than prior generations
- FP16 executes at peak throughput, uses fewer registers than FP32
- Free FP16↔FP32 conversion in hardware

---

## 2. Hardware-Accelerated Ray Tracing

### Prior to Family 9
- All ray/BVH intersection computed in shader core
- Execution divergence: threads wait for longest traversal in SIMDgroup
- High idle time in shader cores

### Family 9 Architecture
The `intersector` object now maps to dedicated fixed-function hardware.

**Pipeline stages:**
1. Acceleration structure traversal → **fixed-function hardware** (off-chip)
2. Intersection function execution → shader code on shader cores
3. **Reorder stage** → groups coherent intersection calls from separate SIMDgroups
4. Intersection comparison → closest hit tracking

**Key improvements:**
- Independent traversal per ray via fixed-function hardware
- Reorder stage eliminates execution divergence
- Rays processed off-chip; on-chip memory used for ray/payload communication
- RT scratch performance counters available in Xcode

**API best practices:**
- Use `intersector` API NOT `intersection_query` API
- `intersection_query` disables the reorder stage
- Minimize ray payload structure size
- Use separate intersection functions per logical routine

---

## 3. Hardware-Accelerated Mesh Shading

### Pipeline
Replaces traditional vertex shaders with GPU-driven geometry processing:
- **Object shader stage**: coarse-grain, spawns mesh groups
- **Mesh shader stage**: fine-grain, meshlet-level processing, outputs `metal::mesh` objects

### Hardware Improvements (Family 9 vs prior)
- More efficient object/mesh threadgroup scheduling
- Intermediate meshlet data kept on-chip (reduced memory traffic)
- Threadgroup limit expanded: 1,024 → 1,000,000+ per mesh grid
- Indirect command buffer support for mesh draw commands

### Best Practices
- Keep mesh template parameters minimal
- Don't oversize max primitives/vertices beyond pipeline needs
- Omit vertex position writes for culled primitives
- Skip writing entire primitives early if culled

---

## 4. Real-World Performance

- Baldur's Gate 3 M3 vs M2: significant gains from thread occupancy improvements
- Blender Cycles: significantly faster convergence from RT hardware
- Pixar Hydra Storm: measurable improvement from mesh shading hardware

---

## Related Apple Tech Talks (from session notes)
- "Discover new Metal profiling tools for M3 and A17 Pro" (111374)
- "Learn performance best practices for Metal shaders" (111373)
- "Your guide to Metal ray tracing"
- "Transform your geometry with Metal mesh shaders" (WWDC22 10162)

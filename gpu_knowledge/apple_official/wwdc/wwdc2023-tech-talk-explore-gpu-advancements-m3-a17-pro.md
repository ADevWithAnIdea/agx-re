# Explore GPU Advancements in M3 and A17 Pro

Source: https://developer.apple.com/videos/play/tech-talks/111375/
Event: Tech Talks (2023)
Speaker: Jedd Haberstro, Engineer, Apple GPU, Graphics, and Displays Software Group
Fetched: 2026-05-09

## Session Description

Learn how Dynamic Caching, the next-generation shader core, hardware-accelerated ray tracing,
and hardware-accelerated mesh shading of Apple family 9 GPUs can improve the performance of
your Metal apps and games.

---

## 1. Next-Generation Shader Core Architecture (Apple Family 9)

Three major advancements in the Apple family 9 GPU shader cores:

### 1.1 Dynamic Shader Core Memory (Dynamic Caching)

- Registers are now **dynamically allocated and deallocated** over the lifetime of a shader
- The register file now functions as a **cache** instead of permanent storage
- Allows for much higher thread occupancy by freeing up space previously wasted
- Example: Instead of being limited to 4 concurrent SIMDgroups due to maximum register
  usage, dynamic allocation can support many more concurrent SIMDgroups
- Apps see immediate performance improvements with **no code changes**

### 1.2 Flexible On-Chip Memory

- Register, threadgroup, tile, stack, and buffer data are **all cached on-chip**
- Redesigned on-chip memories into fewer larger caches servicing all memory types
- Benefits:
  - Shaders with heavy register usage: higher occupancy
  - Shaders with large working sets of buffer data: better cache hit rates and lower latency
  - Apps using non-inline functions: more on-chip stack space for faster function calls
- Hardware dynamically monitors shader behavior and adjusts occupancy to prevent memory spill

### 1.3 High-Performance ALU Pipelines

- FP16, FP32, and integer operations can execute **in parallel** to a greater degree
- Up to **2x ALU performance** compared to prior Apple GPUs
- FP16 optimization:
  - Executes at peak throughput
  - Uses fewer registers than FP32 equivalents
  - Reduces memory bandwidth for native FP16 buffer storage
  - Conversion to/from FP16 costs nothing when source/destination isn't already FP16

---

## 2. Hardware-Accelerated Ray Tracing

### Core Architecture Changes

- **Fixed Function Traversal:** Hardware executes each ray traversal independently
  - Removes execution divergence overhead from software traversal
- **Reorder Stage:** Intelligently groups intersection function calls from separate SIMDgroups
  - Reduces execution divergence during intersection function execution
- Rays sent to hardware intersector instead of executing inline with GPU functions
- Communication occurs through on-chip memory
  - Observable via RT scratch performance counters in Xcode

### Performance Characteristics

Traditional (pre-family 9) issues:
- Execution divergence causes threads to wait for longest traversal
- Same overhead compounds for intersection functions
- Threads spend large proportion of runtime idle

Hardware-accelerated benefits:
- Independent ray traversal via fixed-function hardware
- Reorder stage groups coherent intersection function calls
- Dramatically reduced execution divergence overhead

### Best Practices for Ray Tracing

- Use the **intersector object API** whenever possible (not intersection query API)
- Create **separate Metal intersection functions** for each logical routine (avoid "uber functions")
- Minimize **ray payload structure size** to decrease shader latency and increase thread occupancy

---

## 3. Hardware-Accelerated Mesh Shading

### Architecture

Mesh shading replaces traditional vertex shader stage with two compute-like shaders:
- **Object Shader:** First stage, performs coarse-grain processing on app-specific inputs
- **Mesh Shader:** Second stage, processes constituent pieces (meshlets) of parent objects

### Applications

- Fine-grained geometry culling
- Procedural geometry generation
- Custom app-specific geometry representations (compressed formats)
- Porting geometry and tessellation shaders from other graphics APIs

### Hardware Improvements (Family 9 vs prior)

- Much more efficient scheduling of object and mesh threadgroups
- Keeps intermediate meshlet data on-chip, reducing memory traffic
- Significant performance improvements for existing mesh shading code

### New Metal API Enhancements

- Support for encoding draw mesh commands into **indirect command buffers**
  (enables GPU-driven rendering pipelines with mesh shading)
- Expanded maximum threadgroups per mesh grid from **1,024 to over 1 million**

### Best Practices for Mesh Shading

- Keep `metal::mesh` template parameter sizes as small as possible
- Remove unused vertex/primitive attributes
- Set maximum vertex/primitive counts only as large as actually needed
- For per-primitive culling: omit writing vertex positions to mesh object if culled;
  completely omit those primitives to save processing time

---

## Real-World Performance Examples

### Baldur's Gate 3 (Larian Studios)
- Running on MacBook Pro M3 vs M2
- Ultra video quality at 1800p resolution
- M3 delivers significant performance improvements through next-generation shader core's
  higher thread occupancy

### Blender Cycles Path Tracer
- Rendering barbershop scene with Metal Ray Tracing
- M3 Macs converge significantly faster than previous generation

### Toy Story 4 Antiques Mall USD (Pixar Hydra Storm)
- Real-time visualization leveraging Metal mesh shading
- Runs faster with hardware-accelerated mesh shading on M3

---

## Resources

### Video Downloads
- HD: https://devstreaming-cdn.apple.com/videos/tech-talks/111375/3/04B4AAC5-FF8A-4515-976F-81AF68C0CBC0/downloads/tech-talks-111375_hd.mp4?dl=1
- SD: https://devstreaming-cdn.apple.com/videos/tech-talks/111375/3/04B4AAC5-FF8A-4515-976F-81AF68C0CBC0/downloads/tech-talks-111375_sd.mp4?dl=1

### Related Sessions

WWDC 2023:
- Bring your game to Mac, Part 2: Compile your shaders: https://developer.apple.com/videos/play/wwdc2023/10124
- Your guide to Metal ray tracing: https://developer.apple.com/videos/play/wwdc2023/10128

Tech Talks:
- Discover new Metal profiling tools for M3 and A17 Pro: https://developer.apple.com/videos/play/tech-talks/111374
- Learn performance best practices for Metal shaders: https://developer.apple.com/videos/play/tech-talks/111373

WWDC 2022:
- Maximize your Metal ray tracing performance: https://developer.apple.com/videos/play/wwdc2022/10105
- Transform your geometry with Metal mesh shaders: https://developer.apple.com/videos/play/wwdc2022/10162

WWDC 2021:
- Enhance your app with Metal ray tracing: https://developer.apple.com/videos/play/wwdc2021/10149

---

## Key Takeaways

1. **Automatic Benefits:** Apps see immediate performance improvements on Apple family 9 GPUs
   with no code changes, thanks to the new shader core architecture
2. **Profiling Tools:** New suite of profiling tools available in Xcode to diagnose and
   optimize occupancy
3. **Ray Tracing:** Hardware acceleration dramatically improves intersection performance;
   use intersector API for best results
4. **Mesh Shading:** Hardware support enables more flexible geometry processing pipelines
   with improved performance
5. **FP16 Priority:** Maximize use of FP16 data types for optimal performance and efficiency

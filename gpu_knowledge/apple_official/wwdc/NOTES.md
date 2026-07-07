# WWDC Sessions Notes

## Contents

### wwdc2023-tech-talk-explore-gpu-advancements-m3-a17-pro.md
- Source: https://developer.apple.com/videos/play/tech-talks/111375/
- Speaker: Jedd Haberstro, Apple GPU/Graphics/Displays Software
- THE key document for Apple Family 9 GPU architecture (A17 Pro, M3 family)
- Covers: Dynamic Caching (register file as cache), Flexible On-Chip Memory, 2x ALU
  performance, hardware ray tracing with fixed-function traversal and reorder stage,
  hardware mesh shading with better scheduling

### wwdc2020-10602-harness-apple-gpus-with-metal.md
- Source: https://developer.apple.com/videos/play/wwdc2020/10602/
- Speaker: Guillem Vinals, Apple Metal Ecosystem Team
- THE foundational TBDR architecture explainer
- Covers: Tiling phase vs rendering phase, HSR (Hidden Surface Removal), programmable
  blending, memoryless render targets, MSAA on TBDR, imageblocks (A11+), tile shaders,
  GPU-driven rendering with argument buffers + indirect command buffers

### wwdc2020-10603-optimize-metal-apps-gpu-counters.md
- Source: https://developer.apple.com/videos/play/wwdc2020/10603/
- Speaker: Guillem Vinals Gangolells, Apple Metal Ecosystem Team
- Deep dive on GPU profiling tools and the 150+ available GPU counters
- Covers: ALU/Texture/Buffer/TileMemory/LLC limiter counters, occupancy counter,
  HSR efficiency, Metal System Trace vs Metal Debugger workflows

### wwdc2020-10632-optimize-metal-performance-apple-silicon.md
- Source: https://developer.apple.com/videos/play/wwdc2020/10632/
- Presenters: Mike Imbrogno + Dom, Apple GPU Software
- Practical optimization guide for Apple Silicon Macs
- Covers: Workload scheduling and GPU pipeline overlap, minimizing load/store bandwidth,
  HSR draw ordering, tile shader-based deferred shading, shader core optimization
  (address spaces, 16-bit types, memory access patterns)

### tech-talk-111374-discover-metal-profiling-tools-m3-a17.md
- Source: https://developer.apple.com/videos/play/tech-talks/111374/
- Speakers: Ruiwei + Irfan, Apple Metal Developer Tools
- New Xcode 15 profiling tools for Apple Family 9 GPUs
- Covers: Shader Cost Graph, Performance Heat Maps (5 types), Shader Execution History,
  occupancy triaging with new counters (L1 eviction, Occupancy Manager Target, etc.),
  ray tracing counters, Acceleration Structure Viewer

### tech-talk-111373-metal-shader-performance-best-practices.md
- Source: https://developer.apple.com/videos/play/tech-talks/111373/
- Speaker: Srividya Karumuri, Apple GPU Compiler Engineer
- Shader-level optimization best practices for Family 9 GPUs
- Covers: Function constants (vs macros), function groups for indirect calls, address
  space selection, 16-bit data types (half/short/bfloat), ray tracing payload optimization,
  intersector vs intersection query API

---

## Key Architecture Facts Extracted

### Apple GPU Family / Hardware Mapping
- Apple1: A7 (iPhone 5s)
- Apple4: A11 Bionic (first with redesigned GPU: imageblocks, tile shaders)
- Apple7: A15 Bionic, M2
- Apple8: A16 Bionic
- Apple9: A17 Pro, M3 family (Dynamic Caching, HW ray tracing, HW mesh shading)
- Mac1: AMD/Intel (older Intel Macs)
- Mac2: M1 family

### TBDR Unique Features (Apple GPU vs discrete PC GPUs)
- On-chip Tile Memory (SRAM per GPU core)
- Hidden Surface Removal (HSR) - deferred fragment shading
- Programmable Blending (read color/depth attachment directly from tile memory)
- Memoryless Render Targets (no DRAM backing needed for transient attachments)
- Imageblocks (A11+, 2D structured tile memory access)
- Tile Shaders (A11+, compute kernels mid-render-pass accessing imageblock)

### Apple Family 9 GPU New Features (M3/A17 Pro)
- Dynamic Caching: register file is a cache, not static allocation
- Flexible On-Chip Memory: unified L1 for registers, threadgroup, tile, stack, buffers
- High-Performance ALU: FP16/FP32/int execute more in parallel, up to 2x
- Fixed-Function Ray Traversal hardware
- Intersection Reorder Stage (reduces RT divergence)
- Hardware Mesh Shading (improved scheduling, data stays on-chip)

## Additional WWDC Sessions to Consider Fetching
- WWDC21: Optimize high-end games for Apple GPUs: https://developer.apple.com/videos/play/wwdc2021/10150/
- WWDC22: Transform your geometry with Metal mesh shaders: https://developer.apple.com/videos/play/wwdc2022/10162/
- WWDC22: Maximize your Metal ray tracing performance: https://developer.apple.com/videos/play/wwdc2022/10105/
- WWDC23: Your guide to Metal ray tracing: https://developer.apple.com/videos/play/wwdc2023/10128/
- WWDC19: Modern Rendering with Metal: https://developer.apple.com/videos/play/wwdc2019/601/
- Tech Talk: Tailor your Metal apps for Apple M1: https://developer.apple.com/videos/play/tech-talks/10859/

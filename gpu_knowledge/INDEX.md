# Apple GPU (AGX) Knowledge Base

A centralized collection of everything publicly known about the Apple AGX GPU architecture, including reverse engineering methodology, hardware specifications, firmware protocols, shader ISA, and official Apple documentation.

**Goal**: Foundation for building a copyright-clean GPU RE procedure.

**Legal note**: All content here is either (a) open-source material from Asahi Linux / Mesa / Dougall Johnson's work (MIT/Apache/MIT-licensed), (b) publicly available Apple developer documentation, (c) academic papers, or (d) original notes synthesized from public sources. No proprietary Apple code or macOS binaries are included.

---

## Directory Structure

```
gpu_knowledge/
├── INDEX.md                          ← this file
├── asahi_linux/                      ← Asahi Linux RE outputs
│   ├── docs/                         ← git clone of AsahiLinux/docs
│   ├── docs_compiled/                ← compiled notes from online docs
│   ├── gpu_re/                       ← git clone of AsahiLinux/gpu (early RE tools)
│   └── m1n1_agx/                     ← sparse clone of m1n1 AGX Python code
├── isa/
│   └── applegpu/                     ← git clone of dougallj/applegpu (ISA RE)
├── blog_posts/
│   ├── alyssa_rosenzweig/            ← Alyssa's full blog series
│   └── asahi_linux_blog/             ← Asahi Linux official blog GPU posts
├── apple_official/
│   ├── msl_spec/                     ← Metal Shading Language Specification PDF
│   ├── metal_docs/                   ← Metal API docs and feature tables
│   └── wwdc/                         ← WWDC/Tech Talk session notes
├── papers/                           ← academic papers
└── third_party/
    ├── conference_talks/             ← XDC slide PDFs
    └── *.md                          ← other third-party research
```

---

## Primary Resources (Start Here)

### 1. AGX Hardware Architecture

**[asahi_linux/docs/docs/hw/soc/agx.md](asahi_linux/docs/docs/hw/soc/agx.md)**
The definitive Asahi Linux hardware documentation for AGX. Covers UAT (GPU MMU), firmware architecture, communication channels, work submission pipeline, TA/3D rendering flow, micro-sequences, VA address space layout. **This is the best single technical reference.**

**[asahi_linux/docs_compiled/agx-architecture.md](asahi_linux/docs_compiled/agx-architecture.md)**
Compiled synthesis of the AGX architecture from multiple Asahi sources, including the critical shared-page-table insight and TBDR details.

**[asahi_linux/docs/docs/hw/soc/asc.md](asahi_linux/docs/docs/hw/soc/asc.md)**
ASC (Application Specific Coprocessor) and RTKit documentation. The GPU firmware runs on gfx-asc (an ARM64 ASC). Covers mailbox protocol, register layout, RTKit endpoint architecture.

### 2. GPU Firmware Protocol (The Hard Part)

**[asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/initdata.py](asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/initdata.py)** (2148 lines)
Python definitions of the firmware initialization data structures. This is the most complete public documentation of the firmware protocol — structured as Python ctypes-style structs with field names, types, and comments accumulated from RE. Contains 1000+ fields across the initialization message, channel structures, power management tables, DVFS states, UAT layout, and shared memory regions.

**[asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/cmdqueue.py](asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/cmdqueue.py)** (607 lines)
Command queue structures: how TA (Tile Accelerator) and 3D work items are encoded for firmware submission. Includes TA work, 3D work, compute work structures with all fields.

**[asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/microsequence.py](asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/microsequence.py)** (1203 lines)
Micro-sequence opcode definitions. The firmware executes these embedded command scripts as part of work items (Start/WriteTimestamp/WaitForIdle/Finish patterns).

**[asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/channels.py](asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/channels.py)** (565 lines)
Communication channel structures: the ring buffers used for CPU↔firmware messaging. Event channels, device control channels, work submission channels.

**[asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/handoff.py](asahi_linux/m1n1_agx/proxyclient/m1n1/fw/agx/handoff.py)** (120 lines)
The gfx-handoff region: synchronization between CPU and firmware for page table updates and cache flush coordination.

### 3. Shader ISA

**[isa/applegpu/](isa/applegpu/)** — git clone of dougallj/applegpu
The definitive public reference for the Apple G13 (M1) GPU shader ISA, reverse engineered by Dougall Johnson. Contains:
- `applegpu.py` — full instruction set decoder with all instruction encodings
- `disassemble.py` — ISA disassembler
- `assemble.py` — assembler
- `hwtest.py` — hardware validation test runner
- `hwtestbed/` — Metal compute testbed (overwrite shader in metallib, run, compare)
- `docs.html` — rendered ISA reference documentation (readable locally)
- `README.md` — methodology overview

Key ISA facts:
- Scalar architecture (unusual for mobile GPU)
- Variable-length encoding: 4–12 bytes per instruction
- 128 general-purpose 32-bit registers (r0–r127), also accessible as 16-bit halves
- 256 uniform registers (u0–u255) for per-dispatch constants
- Hardware scheduling (compiler doesn't need to worry about instruction scheduling)
- Free modifiers: saturate, negate, abs, FP16↔FP32 conversion on sources/destinations

**[isa/applegpu/docs.html](isa/applegpu/docs.html)** — open locally in a browser for the full ISA reference.

### 4. RE Methodology

**[blog_posts/alyssa_rosenzweig/part-1-introduction.md](blog_posts/alyssa_rosenzweig/part-1-introduction.md)**
"Dissecting the Apple M1 GPU, Part I" (Jan 2021) — the foundational RE methodology post.
- DYLD_INSERT_LIBRARIES interception of IOConnectCallMethod
- How to trace GPU command buffers in macOS
- Iterative binary comparison for command buffer format discovery

**[blog_posts/alyssa_rosenzweig/part-2.md](blog_posts/alyssa_rosenzweig/part-2.md)**
Part II — shader ISA beginnings, how to isolate and study individual instructions.

**[blog_posts/alyssa_rosenzweig/part-3.md](blog_posts/alyssa_rosenzweig/part-3.md)**
Part III — command buffer format, GenXML packet definitions, texture/sampler RE.

**[blog_posts/alyssa_rosenzweig/part-4.md](blog_posts/alyssa_rosenzweig/part-4.md)**
Part IV — hardware guesswork methodology (index buffer sizes, primitive types), blending RE.

**[blog_posts/alyssa_rosenzweig/part-5-impossible-bug.md](blog_posts/alyssa_rosenzweig/part-5-impossible-bug.md)**
Part V — "The Impossible Bug" — how the TBDR vertex buffer overflow was discovered and the partial render mechanism reverse engineered. Key debugging methodology example.

**[blog_posts/asahi_linux_blog/tales-of-the-m1-gpu.md](blog_posts/asahi_linux_blog/tales-of-the-m1-gpu.md)**
"Tales of the M1 GPU" (Nov 2022) — the definitive account of how the Linux kernel driver was developed. Covers:
- The firmware architecture problem (shared page table)
- Python prototyping with m1n1
- The drm-shim embedded Python experiment
- Why Rust was chosen and how it helped
- Multi-version firmware structure management

**[asahi_linux/gpu_re/](asahi_linux/gpu_re/)** — git clone of AsahiLinux/gpu
Early RE tools from 2021. Contains:
- `wrap/wrap.c` — the IOKit DYLD_INSERT_LIBRARIES wrapper for macOS tracing
- `lib/cmdbuf.xml` — early command buffer format XML definitions (GenXML-style)
- `lib/cmdstream.h` — C command stream structures
- `lib/tiling.c` — tile layout computation (swizzle/Morton order)
- `demo/` — minimal demo app that submits GPU work without Metal

### 5. Driver Design and UAPI

**[asahi_linux/docs/docs/sw/agx-driver-notes.md](asahi_linux/docs/docs/sw/agx-driver-notes.md)**
Driver UAPI design: File/VM/Bind/Queue model, GEM object management, queue execution model, explicit sync, result buffers.

**[asahi_linux/docs_compiled/agx-driver-notes.md](asahi_linux/docs_compiled/agx-driver-notes.md)**
Compiled notes on the driver UAPI.

---

## Blog Post Series

### Alyssa Rosenzweig — "Dissecting the Apple M1 GPU"
All at [blog_posts/alyssa_rosenzweig/](blog_posts/alyssa_rosenzweig/):

| File | Date | Topic |
|------|------|-------|
| `part-1-introduction.md` | Jan 2021 | RE methodology: IOKit interception, command buffer tracing |
| `part-2.md` | Jan 2021 | Shader ISA beginnings |
| `part-3.md` | Apr 2021 | Command buffer XML format, texture/sampler RE |
| `part-4.md` | May 2021 | Guesswork methodology, index buffers, primitive types |
| `part-5-impossible-bug.md` | May 2022 | TBDR partial render bug discovery |
| `part-n-end.md` | Aug 2025 | Final retrospective: geometry/tessellation emulation |
| `gpu-drivers-in-asahi.md` | Dec 2022 | Alpha driver launch post |
| `first-conformant-driver.md` | Aug 2023 | First OpenGL ES 3.1 conformant driver |
| `opengl3-on-asahi.md` | Jun 2023 | OpenGL 3.1 / ES 3.0 implementation details |
| `part-6-clip-control.md` | ~2022 | Clip space hardware bit RE |
| `conformant-gl46.md` | ~2024 | OpenGL 4.6 conformance |
| `vulkan13-in-1-month.md` | ~2024 | Vulkan 1.3 in 1 month |
| `vulkan-14.md` | ~2024 | Vulkan 1.4 day-one conformance |
| `aaa-gaming-on-m1.md` | ~2024 | AAA gaming: FEX+Wine+DXVK stack, software tessellation |

### Asahi Linux Blog — GPU Posts
All at [blog_posts/asahi_linux_blog/](blog_posts/asahi_linux_blog/):

| File | Topic |
|------|-------|
| `tales-of-the-m1-gpu.md` | Linux kernel driver story; firmware architecture problem; Python prototyping |
| `gpu-drivers-now-in-asahi.md` | Alpha GPU driver release announcement |
| `road-to-vulkan.md` | Vulkan development roadmap |
| `opengl31-on-asahi.md` | OpenGL 3.1 launch |
| `first-conformant-driver.md` | Conformant ES 3.1 announcement |
| `progress-aug-2021.md` | Early GPU RE progress |
| `progress-sep-2021.md` | GPU RE progress |
| `copyright-re-policy.md` | Asahi's legal framework for RE |

---

## Apple Official Documentation

### Apple Metal Shading Language Specification
**[apple_official/msl_spec/metal-shading-language-spec.pdf](apple_official/msl_spec/metal-shading-language-spec.pdf)** (12 MB)
The complete Metal Shading Language specification. Primary reference for:
- Data types (half, float, vector, matrix types)
- Address spaces (device, threadgroup, constant, thread)
- Built-in functions (all math, texture, atomic operations)
- Vertex/fragment/compute shader semantics
- Attribute qualifiers ([[position]], [[buffer(n)]], [[texture(n)]], etc.)
- Tile shaders and imageblocks (TBDR-specific)

### Metal Feature Set Tables
**[apple_official/metal_docs/Metal-Feature-Set-Tables.pdf](apple_official/metal_docs/Metal-Feature-Set-Tables.pdf)** (3 MB)
Which Metal features are available on which GPU families (Apple1–Apple9, Mac1–Mac2). Essential for understanding what hardware capabilities exist per generation.

### WWDC / Tech Talk Sessions
All at [apple_official/wwdc/](apple_official/wwdc/):

| File | Session | Key Content |
|------|---------|-------------|
| `wwdc2020-10602-harness-apple-gpus-with-metal.md` | WWDC20 10602 | Foundational TBDR architecture: tiling vs rendering phases, HSR (hidden surface removal), programmable blending, imageblocks, tile shaders, GPU-driven rendering |
| `wwdc2020-10603-optimize-metal-apps-gpu-counters.md` | WWDC20 10603 | All 150+ GPU performance counters: ALU/texture/buffer/tile memory/LLC limiters, occupancy |
| `wwdc2020-10632-optimize-metal-performance-apple-silicon.md` | WWDC20 10632 | Apple Silicon optimization: workload scheduling, render pass merging, tile shader deferred shading |
| `gpu-advancements-m3-a17-pro.md` | Tech Talk 111375 | Family 9 (M3/A17 Pro): Dynamic Caching, flexible on-chip unified memory, 2x ALU parallelism, hardware ray tracing with fixed-function traversal + reorder stage, hardware mesh shading |
| `wwdc2023-tech-talk-explore-gpu-advancements-m3-a17-pro.md` | Tech Talk 111375 | Full transcript of above |
| `tech-talk-111374-discover-metal-profiling-tools-m3-a17.md` | Tech Talk 111374 | Xcode profiling: Shader Cost Graph, heat maps, Shader Execution History, occupancy counters |
| `tech-talk-111373-metal-shader-performance-best-practices.md` | Tech Talk 111373 | Compiler optimization, function constants, address spaces, 16-bit types |
| `wwdc22-metal-mesh-shaders.md` | WWDC22 10162 | Mesh shader architecture: object/mesh stages, metal::mesh type, hardware limits |

### Metal API Overview
**[apple_official/metal_docs/metal-overview.md](apple_official/metal_docs/metal-overview.md)**
Metal 4 landing page content, API overview, tool ecosystem.

---

## Conference Slides (XDC)

All at [third_party/conference_talks/](third_party/conference_talks/):

| File | Event | Title | Speaker |
|------|-------|-------|---------|
| `xdc2021-occult-and-apple-gpu.pdf` | XDC 2021 | "The Occult and the Apple GPU" | Alyssa Rosenzweig |
| `xdc2022-tasting-forbidden-apple.pdf` | XDC 2022 | "Tasting the Forbidden Apple" | Alyssa Rosenzweig + Asahi Lina |
| `xdc2023-unleash-graphics-magic.pdf` | XDC 2023 | "Unleash the (graphics) magic" | Asahi Lina + Alyssa Rosenzweig |
| `xdc2024-aaa-witch-slides.pdf` | XDC 2024 | "AAA!! She's a witch!" | Alyssa Rosenzweig |

The XDC series is the best year-by-year account of progress:
- 2021: Initial RE approach, early Mesa driver on macOS
- 2022: Linux kernel driver launch, firmware architecture
- 2023: OpenGL ES 3.1 conformance, hardware incantations
- 2024: Vulkan 1.3 conformance, geometry/tessellation emulation, gaming

YouTube recordings also available (search "XDC [year] Apple GPU").

---

## Third-Party Research

**[third_party/philipturner-metal-benchmarks.md](third_party/philipturner-metal-benchmarks.md)**
Apple GPU microarchitecture details measured via Metal compute benchmarks (Philip Turner). Covers per-core specs, register file sizes, ALU counts, memory hierarchy, sub-core concurrency.
Source: https://github.com/philipturner/metal-benchmarks

**[third_party/lwn-m1-gpu-driver-update-2024.md](third_party/lwn-m1-gpu-driver-update-2024.md)**
LWN article on Apple M1/M2 GPU driver status from 2024. Covers XDC 2024 content: hardware tessellator limitations, software tessellator via OpenCL, virtgpu native contexts for VM GPU access.
Source: https://lwn.net/Articles/995383/

**[third_party/dougallj_applegpu_readme.md](third_party/dougallj_applegpu_readme.md)**
Dougall Johnson's applegpu project README — methodology for hardware instruction testing.

**[third_party/dougallj_applegpu_architecture_reference.md](third_party/dougallj_applegpu_architecture_reference.md)**
Summary of the Apple G13 GPU architecture reference from https://dougallj.github.io/applegpu/docs.html

Additional files created by research agent covering conference talks, blog posts from other angles.

---

## Academic Papers

**[papers/arxiv-2502.05317-apple-silicon-hpc.pdf](papers/arxiv-2502.05317-apple-silicon-hpc.pdf)**
"Apple vs. Oranges: Evaluating the Apple Silicon M-Series SoCs for HPC Performance and Efficiency" (Feb 2025, arXiv:2502.05317). Benchmarks M1–M4 across compute workloads. Measured GPU TFLOPS, memory bandwidth, power efficiency (200+ GFLOPS/W). Notes: M4 reaches 2.9 FP32 TFLOPS, all chips sustain 100 GB/s+ unified memory bandwidth.

**[papers/arxiv-2603.28793-universal-gpu-isa.pdf](papers/arxiv-2603.28793-universal-gpu-isa.pdf)**
"Toward a Universal GPU Instruction Set Architecture: A Cross-Vendor Analysis" (Mar 2026, arXiv:2603.28793). Systematic analysis of NVIDIA, AMD, Intel, and Apple GPU ISAs from official docs + RE sources. Identifies 10 hardware-invariant primitives, 6 parameterizable dialects, 6 true divergences. Proposes a vendor-neutral abstract GPU ISA model. Useful for contextualizing where AGX fits in the GPU landscape.

See also [papers/arxiv_apple_silicon_hpc_2502_05317.md](papers/arxiv_apple_silicon_hpc_2502_05317.md) and [papers/arxiv_universal_gpu_isa_2603_28793.md](papers/arxiv_universal_gpu_isa_2603_28793.md) for markdown summaries.

---

## m1n1 GPU RE Experiment Scripts

At [asahi_linux/m1n1_agx/proxyclient/experiments/](asahi_linux/m1n1_agx/proxyclient/experiments/):

These Python scripts represent the actual RE process — they drove real GPU hardware over USB from a laptop, testing firmware behavior incrementally.

| Script | Purpose |
|--------|---------|
| `agx_boot.py` | Boot the GPU firmware, verify basic communication |
| `agx_1tri.py` | Render a single triangle — the minimal GPU render verification |
| `agx_renderframe.py` | Full frame rendering experiment |
| `agx_parallel.py` | Parallel command submission testing |
| `agx_cancel.py` | Job cancellation testing |
| `agx_deps.py` | Dependency/barrier testing between jobs |
| `agx_tlb.py` | TLB invalidation testing |
| `agx_tracetimings.py` | GPU timing measurement |
| `agx_xtest.py` | X11 rendering test |
| `agx_dumpstructs.py` | Dump firmware data structures for inspection |

---

## Key Technical Facts Summary

### Architecture
- **Type**: Tile-Based Deferred Renderer (TBDR), heavily PowerVR-inspired
- **Codename**: AGX (G13 = M1 generation, G14 = M2, G15 = M3, etc.)
- **Coprocessor**: gfx-asc, ARM64, runs Apple RTKit RTOS
- **Driver model**: ALL GPU communication goes through firmware — the kernel driver never touches GPU hardware registers directly

### UAT (GPU MMU)
- ARM64 page table structure (identical format)
- 40-bit GPU VA, sign-extended to 64 bits
- 16K pages
- Up to 16 GPU contexts
- **Critical**: Firmware uses the same page table → GPU memory = firmware memory

### Shader Cores
- Scalar ISA (unlike most mobile GPUs which are SIMD)
- SIMD-group size: 32 threads
- Hardware scheduling (no software instruction scheduling needed)
- Registers: r0–r127 (32-bit, accessible as 16-bit pairs), u0–u255 (uniforms)
- Free modifiers: saturate/negate/abs on FP ops, free FP16↔FP32 type conversion
- Variable instruction size: 4–12 bytes
- Family 9 (M3/A17): Dynamic Caching — register file as cache, unified on-chip memory

### Communication Protocol
- CPU↔firmware: ASC mailbox (128-bit messages) + shared memory ring buffers
- Channel types: TA work, 3D work, compute, DeviceControl (CPU→GPU); events, faults, stats, syslog (GPU→CPU)
- Firmware init: single large message with 1000+ fields, complex nested structures

### TBDR Rendering Pipeline
- Tiler stage (TA): geometry → tile bins, buffering all per-vertex data
- Fragment stage (3D): per-tile fragment shading
- Vertex buffer overflow → "Partial Render": firmware flushes tile data, continues
- Tiles: typically 32×32 pixels

---

## External Links (Not Downloaded)

- AsahiLinux/linux kernel driver: https://github.com/AsahiLinux/linux/tree/gpu/rust-wip/drivers/gpu/drm/asahi
- Mesa Asahi driver: https://gitlab.freedesktop.org/mesa/mesa (src/asahi/)
- Mesa Asahi docs: https://docs.mesa3d.org/drivers/asahi.html
- Apple GPU ISA docs (rendered): https://dougallj.github.io/applegpu/docs.html
- Apple GPU ISA docs (rendered, alternative): https://dougallj.github.io/applegpu/
- m1n1 full repo: https://github.com/AsahiLinux/m1n1
- Asahi Linux docs (built): https://asahilinux.org/docs/
- Asahi Linux blog: https://asahilinux.org/blog/
- Alyssa Rosenzweig's blog: https://alyssarosenzweig.ca/
- XDC talks (YouTube): https://www.youtube.com/@XOrgFoundation/playlists

# Apple AGX GPU Knowledge Base: Source Index

Compiled: 2026-05-09  
Working directory: /Users/user/asahi_re/gpu_knowledge/

This document indexes all sources collected about Apple AGX GPU architecture, reverse engineering, and driver development.

---

## Directory Structure

```
gpu_knowledge/
├── papers/           # Academic papers and formal analyses
│   ├── SOURCES.md    (this file)
│   ├── arxiv_universal_gpu_isa_2603_28793.md
│   └── arxiv_apple_silicon_hpc_2502_05317.md
└── third_party/      # Blog posts, talks, documentation, community work
    ├── dougallj_applegpu_readme.md
    ├── dougallj_applegpu_architecture_reference.md
    ├── rosenzweig_dissecting_m1_gpu_part1.md
    ├── rosenzweig_dissecting_m1_gpu_part3.md
    ├── rosenzweig_dissecting_m1_gpu_part4.md
    ├── rosenzweig_apple_gpu_impossible_bug_part5.md
    ├── rosenzweig_dissecting_m1_gpu_end.md
    ├── rosenzweig_aaa_gaming_vulkan.md
    ├── asahi_lina_tales_of_m1_gpu.md
    ├── asahi_linux_agx_hardware_docs.md
    ├── asahi_linux_road_to_vulkan.md
    ├── asahi_linux_driver_upstreaming_status.md
    ├── xdc_conference_talks.md
    ├── lwn_apple_agx_driver_articles.md
    ├── hacker_news_discussions.md
    ├── apple_gpu_powervr_connection.md
    └── philipturner_metal_benchmarks.md
```

---

## Academic Papers

### 1. Toward a Universal GPU Instruction Set Architecture
**File:** `papers/arxiv_universal_gpu_isa_2603_28793.md`  
**URL:** https://arxiv.org/abs/2603.28793  
**Authors:** Ojima Abraham, Onyinye Okolie  
**Date:** March 22, 2026  
**Description:** First academic paper to systematically compare Apple G13 GPU against NVIDIA, AMD, and Intel architectures. Analyzes 16 microarchitectures across 5,000+ pages of primary sources. Identifies 10 hardware-invariant computational primitives, 6 parameterizable dialects, and 6 true divergences. Validates abstract execution model on Apple M1 hardware — achieves 97.8-102.1% of native performance (vs. 62.5% on NVIDIA). Uses reverse-engineered Asahi/dougallj documentation as Apple source material. Notable finding: Apple's hardware stack divergence mechanism (r0l register) is architecturally distinct from NVIDIA's per-thread PC approach.

### 2. Apple vs. Oranges: Evaluating Apple Silicon M-Series SoCs for HPC
**File:** `papers/arxiv_apple_silicon_hpc_2502_05317.md`  
**URL:** https://arxiv.org/html/2502.05317v1  
**Date:** February 2025  
**Description:** HPC performance/efficiency analysis of M1-M4. Documents GPU core counts, peak TFLOPS (1.36-2.9 TFLOPS FP32), memory bandwidth (60-100 GB/s), and ~200 GFLOPS/W efficiency. Confirms no native FP64. Useful for establishing baseline performance figures.

---

## Primary Reverse Engineering Documentation

### 3. dougallj/applegpu: README and Methodology
**File:** `third_party/dougallj_applegpu_readme.md`  
**URL:** https://github.com/dougallj/applegpu  
**Author:** Dougall Johnson  
**Description:** README and methodology description for the primary Apple G13 GPU ISA reverse engineering project. Documents the comparative testing approach: inject custom shaders into Metal .metallib archives, execute on real hardware and emulator, compare state. Includes overview of disassembler, assembler, and emulator tools. BSD-3-Clause licensed.

### 4. Apple G13 GPU Architecture Reference
**File:** `third_party/dougallj_applegpu_architecture_reference.md`  
**URL:** https://dougallj.github.io/applegpu/docs.html  
**Author:** Dougall Johnson  
**Description:** The primary technical reference for the Apple G13 GPU ISA. Covers: 32-thread SIMD-groups, 128 GPRs per thread, execution mask mechanism (r0l register), variable-length instructions (2-12 bytes), full instruction set (integer/FP/bitfield/memory/flow control/SIMD ops), free FP modifiers, scalar architecture with superscalar execution. Generated from applegpu.py instruction descriptions. Note: author warns it "likely has mistakes."

---

## Alyssa Rosenzweig Blog Series: "Dissecting the Apple M1 GPU"

### 5. Part I: Methodology and Initial Discoveries
**File:** `third_party/rosenzweig_dissecting_m1_gpu_part1.md`  
**URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-1.html  
**Author:** Alyssa Rosenzweig  
**Date:** January 2021  
**Description:** First installment. Covers reverse engineering methodology (DYLD_INSERT_LIBRARIES hooking, IOConnectCallMethod wrapping, binary differential analysis). Key discoveries: scalar ISA, more 16-bit ALUs than 32-bit, free FP modifiers, hardware scheduling (not compiler-managed).

### 6. Part III: Register File, ISA, and Compiler Design
**File:** `third_party/rosenzweig_dissecting_m1_gpu_part3.md`  
**URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-3.html  
**Author:** Alyssa Rosenzweig  
**Description:** Documents 256 half-word registers per thread, occupancy model (thread count drops in 64-thread increments beyond ~104 registers), 4.875 MiB total register file. Covers AGX2 ISA characteristics and the full Mesa shader compiler pipeline (NIR → SSA → instruction combining → scheduling → RA → post-RA scheduling → binary packing).

### 7. Part IV: Command Stream Analysis
**File:** `third_party/rosenzweig_dissecting_m1_gpu_part4.md`  
**URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-4.html  
**Author:** Alyssa Rosenzweig  
**Description:** Command stream reverse engineering. Covers index buffer format (2-bit field, base-2 log encoding, hidden 8-bit mode), primitive type enumeration (brute force - 4-bit field, 16 possible types but Metal only exposes 5), primitive restart enable bit. Documents kernel interface statefulness (aware of surface dimensions, mipmapping).

### 8. Part V: The Impossible Bug (Parameter Buffer / TVB)
**File:** `third_party/rosenzweig_apple_gpu_impossible_bug_part5.md`  
**URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-5.html  
**Author:** Alyssa Rosenzweig  
**Description:** Critical article. Documents the TBDR two-stage pipeline, discovery of the Parameter Buffer (PB) / Tiled Vertex Buffer (TVB), and the PowerVR naming correspondence. Root cause: driver not providing auxiliary shaders for partial render recovery when TVB overflows. Fix: supply reload shader, configure depth flush, recognize firmware dynamically resizes TVB heap. Critical for understanding Apple TBDR architecture.

### 9. The End: Project Completion and Final Achievements
**File:** `third_party/rosenzweig_dissecting_m1_gpu_end.md`  
**URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-n.html  
**Author:** Alyssa Rosenzweig  
**Description:** Final installment. Documents achievement of OpenGL 4.6, Vulkan 1.3/1.4, OpenCL 3.0 conformance. Novel contributions: geometry shader and tessellation emulation via compute (no open-source prior art in Mesa), software blending optimizations. Performance: 800+ FPS on M2 in Xonotic (exceeds macOS ~600 FPS).

### 10. GPU Driver Launch (Part VII)
**URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-7.html  
**Description:** (Content captured in upstreaming status file) Documents initial OpenGL 2.1/ES 2.0 release, driver architecture (kernel DRM + Mesa Gallium3D + compiler), use of NIR intermediate representation.

---

## Asahi Linux Project Documentation

### 11. Tales of the M1 GPU (Asahi Lina)
**File:** `third_party/asahi_lina_tales_of_m1_gpu.md`  
**URL:** https://asahilinux.org/2022/11/tales-of-the-m1-gpu/  
**Author:** Asahi Lina  
**Date:** November 2022  
**Description:** Comprehensive account of kernel driver implementation. Key content: ASC coprocessor firmware architecture (RTKit RTOS), shared memory communication, 100+ firmware data structures, micro sequence format, UAT (GPU MMU) with 40-bit addresses and 16K pages, 128 event indices. Documents decision to use Rust, Python prototype approach, August-September 2022 implementation timeline.

### 12. AGX Hardware Documentation
**File:** `third_party/asahi_linux_agx_hardware_docs.md`  
**URL:** https://asahilinux.org/docs/hw/soc/agx/  
**Description:** Official Asahi Linux hardware documentation. Covers UAT memory management (40-bit addresses, 16K pages, 16 contexts), communication channels (ring buffers: CPU→GPU TA/3D/CP channels, GPU→CPU event/stats/syslog), micro sequences, 3D pipeline (TVB management, stamp objects, TA/3D stages), hardware status registers (0x11008, 0x1100c, 0x11010, 0x11014), key memory regions.

### 13. Paving the Road to Vulkan
**File:** `third_party/asahi_linux_road_to_vulkan.md`  
**URL:** https://asahilinux.org/2023/03/road-to-vulkan/  
**Description:** UAPI design evolution from synchronous (Panfrost-inherited) to explicit async synchronization with DMA fences. Covers TBDR batching requirements, implicit vs. explicit sync, DMA-BUF fence APIs (Linux 6.0), buffer sharing edge cases, deferred fence attachment. Performance: Xonotic 800+ FPS on M2.

### 14. Driver Upstreaming Status
**File:** `third_party/asahi_linux_driver_upstreaming_status.md`  
**Sources:** Multiple progress reports (6.15 through 6.19)  
**Description:** Timeline of kernel upstreaming: UAPI merged in Linux 6.15 (May 2025), Mesa drivers in 6.16 (August 2025), devicetree bindings in 6.17. Patch count history. Team roles (Dougall/Alyssa/Lina/Ella). Remaining work: display controller, full GPU kernel driver.

### 15a. Asahi Linux Wiki: AGX Hardware and Driver Notes
**File:** `third_party/asahi_wiki_agx_hardware_and_driver.md`  
**Sources:** https://leo3418.github.io/asahi-wiki-build/hwagx/ and https://leo3418.github.io/asahi-wiki-build/swagx-driver-notes/  
**Description:** Asahi Linux wiki pages covering HW:AGX and SW:AGX driver notes. Key content: VA space layout (macOS reference addresses 0x015/0x011/0xf80/0xfa0 ranges), work submission hierarchy (Work Queue → Work Item → Micro Sequence → Stamp Object → Event), typical TA micro sequence format, microPPL security model (magic value 0x4b1d000000000002, flush state at 0x10ffffb4038), GEM VM-private objects, UAPI architecture (Files/VMs/Binds/Queues model inspired by Intel Xe), 64-command job limit, result feedback with TVB statistics and fault info.

### 15b. GPU Resource Descriptors on Apple GPUs
**File:** `third_party/apple_gpu_resource_descriptors.md`  
**URL:** https://techboards.net/threads/gpu-resource-descriptors-on-apple-gpus.4156/  
**Description:** Technical discussion (with Dougall Johnson contributions) on Apple GPU descriptor model. Key details: texture descriptors are 24 bytes (64-bit base address in uniform registers + 32-bit offset in general registers, offset = gpuResourceID × 24); sampler descriptors are 8 bytes (16-bit direct index register, max 1024 unique samplers); Metal argument buffers abstract the table-based hardware model. Comparison with AMD (inline), Intel (table-based similar to Apple), NVIDIA (global tables).

### 15. AAA Gaming on Asahi Linux (Vulkan Technical Details)
**File:** `third_party/rosenzweig_aaa_gaming_vulkan.md`  
**URL:** https://alyssarosenzweig.ca/blog/aaa-gaming-on-m1.html  
**Description:** Honeykrisp Vulkan 1.3 driver technical details. Tessellation emulation (hardware missing point mode/isolines; OpenCL-based software: 265 fps vs hardware 820 fps). Geometry shader emulation via compute. 64GB zero-page trick for robustness. muvm lightweight VM for 4K/16K page size compatibility. Full AAA gaming stack (FEX + Wine + DXVK + Honeykrisp).

---

## Conference Talks

### 16. XDC 2021 - "The Occult and the Apple GPU"
**File:** `third_party/xdc_conference_talks.md` (section 1)  
**URL:** https://www.youtube.com/watch?v=ObS6sdfus2w  
**Indico:** https://indico.freedesktop.org/event/1/contributions/10/  
**Slides:** Available (Slides-Final.pdf on Indico)  
**Speaker:** Alyssa Rosenzweig  
**Date:** September 15, 2021  
**Description:** First major public talk on M1 GPU RE. Covers M1 SoC architecture, RE methodology, early ISA discoveries, Mesa driver development. 45 minutes. Slides available.

### 17. XDC 2022 - "Tasting the Forbidden Apple"
**File:** `third_party/xdc_conference_talks.md` (section 2)  
**URL:** https://www.youtube.com/watch?v=SDJCzJ1ETsM  
**Indico:** https://indico.freedesktop.org/event/2/contributions/66/  
**Speakers:** Alyssa Rosenzweig + Asahi Lina  
**Date:** October 4, 2022  
**Description:** Joint talk covering firmware "magic ring buffers," reverse engineering tricks, Asahi Linux GPU support. Entire talk delivered running on M1 using their own driver (live demo).

### 18. XDC 2023 - "Unleash the (Graphics) Magic"
**File:** `third_party/xdc_conference_talks.md` (section 3)  
**URL:** https://www.youtube.com/watch?v=O36VFNdQHsE  
**Indico:** https://indico.freedesktop.org/event/4/  
**Speakers:** Asahi Lina + Alyssa Rosenzweig  
**Date:** October 17, 2023  
**Description:** Progress from OpenGL 2.1 to OpenGL ES 3.1 conformance on M1/M2. "Truly cursed driver code" required. Hardware details enabling the implementation.

### 19. XDC 2024 - "AAA!! She's a Witch!"
**File:** `third_party/xdc_conference_talks.md` (section 4)  
**URL:** https://www.youtube.com/watch?v=TtLP5sAXYKo  
**Indico:** https://indico.freedesktop.org/event/6/contributions/284/  
**Slides:** Available (slides.pdf on Indico)  
**Speaker:** Alyssa Rosenzweig  
**Date:** October 10, 2024  
**Description:** Vulkan 1.3 on M1 with geometry shaders, tessellation, transform feedback. AAA gaming stack. Live demo. Hardware tessellator limitations and software workarounds documented.

---

## LWN.net Coverage

### 20. LWN: Initial Apple AGX Driver Posting
**File:** `third_party/lwn_apple_agx_driver_articles.md` (section 1)  
**URL:** https://lwn.net/Articles/925503/  
**Description:** Coverage of Asahi Lina's March 2023 first Rust GPU kernel driver submission. Rust safety rationale, fatal firmware crash constraint, community debate on callback implementation.

### 21. LWN: Tales of the M1 GPU
**File:** `third_party/lwn_apple_agx_driver_articles.md` (section 2)  
**URL:** https://lwn.net/Articles/916208/  
**Description:** LWN coverage of the Tales blog post. Python prototype approach, UAPI stability requirements.

### 22. LWN: Whither the Apple AGX Graphics Driver?
**File:** `third_party/lwn_apple_agx_driver_articles.md` (section 3)  
**URL:** https://lwn.net/Articles/988438/  
**Description:** Deep dive into why the driver remained out-of-tree. DRM scheduler API conflicts, Rust vs C philosophy clash, circular ownership (scheduler→fence→driver→scheduler), use-after-free edge cases. Resolution: reimplemented scheduler via workqueues.

### 23. LWN: An Update on Apple M1/M2 GPU Drivers
**File:** `third_party/lwn_apple_agx_driver_articles.md` (section 4)  
**URL:** https://lwn.net/Articles/995383/  
**Description:** OpenGL 4.6 + Vulkan 1.3 conformance status, tessellation implementation details, gaming stack.

### 24. LWN: Dissecting the Apple M1 GPU - The End
**File:** `third_party/lwn_apple_agx_driver_articles.md` (section 5)  
**URL:** https://lwn.net/Articles/1035332/  
**Description:** Project completion coverage, Mesa upstreaming, transition to Intel.

---

## Architecture Analysis

### 25. Apple AGX and PowerVR Connection
**File:** `third_party/apple_gpu_powervr_connection.md`  
**Sources:** Multiple (Phoronix, Rosenzweig blog, Asahi docs, HN, Wikipedia, img.tec)  
**Description:** Synthesis of evidence for PowerVR heritage. Key: internal Apple "PB" name matches PowerVR "Parameter Buffer." Business relationship (Imagination Technologies license, PVRTC support). Dual-dispatch architecture as PowerVR remnant. Mesa code similarities. PowerVR TBDR architecture reference (Imagination Technologies docs). Apple's proprietary innovations over PowerVR (sample shading, software blending, scale).

### 26. Philip Turner - Metal Benchmarks / GPU Microarchitecture
**File:** `third_party/philipturner_metal_benchmarks.md`  
**URL:** https://github.com/philipturner/metal-benchmarks  
**Description:** Empirical microarchitecture documentation. GPU core ~2mm², 512KB registers/L1 cache, L2 32B/cycle. Cache sizes (L1D: 8KB, L1I: 12KB, L2: 256KB-1MB). FP16 FMA: 256 ops/cycle, FP32: 128-256. Instruction latencies (FADD16: 2.16cy, FFMA32: 2.21cy, RECIP32: 6.5cy, RSQRT32: 8.99cy). Register dependency penalties (32b: 0.84cy, 16b: 0.56cy). Dual-dispatch as PowerVR remnant. Hidden ray tracing instruction (M3+). Nanite atomics (M2+). Power: single SIMD 800mW on M1 MAX.

---

## Hacker News Technical Discussions

### 27. HN: Dissecting the Apple M1 GPU Discussion
**File:** `third_party/hacker_news_discussions.md` (section 1)  
**URL:** https://news.ycombinator.com/item?id=25673631  
**Description:** Technical discussion on Part I blog post. PowerVR heritage debate, A14 vs M1 throughput differences (A14: fp16 2× fp32; M1: equal throughput), PVRTC as evidence of continued Imagination IP.

### 28. HN: Asahi Linux Announcement Discussion
**File:** `third_party/hacker_news_discussions.md` (section 2)  
**URL:** https://news.ycombinator.com/item?id=25649999  
**Description:** Early 2021 discussion. Complexity assessment, Neural Engine RE (tinygrad/ane, George Hotz), GPU necessity for usable Linux laptop.

### 29. HN: General Purpose GPU on Apple M* Chips
**File:** `third_party/hacker_news_discussions.md` (section 3)  
**URL:** https://news.ycombinator.com/item?id=42509730  
**Description:** Technical resources discussion. Unified memory bandwidth figures, core heterogeneity, low-level API restrictions, RE cost estimates, practical examples (llama.cpp, EXO clustering).

### 30. HN: Help with Apple Silicon RE
**File:** `third_party/hacker_news_discussions.md` (section 4)  
**URL:** https://news.ycombinator.com/item?id=42509851  
**Description:** Discussion of what RE would unlock. "43 TFLOPS + 8 TB/s" aggregate compute, clustering approaches, cost-competitive NVIDIA alternatives.

---

## Additional Sources (Not Saved as Separate Files)

### FOSDEM 2024: "News from the Hermit Crab"
**URL:** https://archive.fosdem.org/2024/schedule/event/fosdem-2024-3375-news-from-the-hermit-crab-from-soundness-foundations-to-gpu-virtualization/  
**Description:** Hermit OS + GPU virtualization talk (not directly Apple-GPU focused, but covers Rust GPU driver patterns). Martin Kröning. February 3, 2024. GPU virtualization using Cricket.

### FOSDEM 2023: Fedora Asahi Talk
**URL:** https://archive.fosdem.org/2023/schedule/event/fedora_asahi/  
**Description:** Introduction to Fedora Asahi Remix. Not GPU-specific.

### Phoronix: Mesa AGX PowerVR Similarities
**URL:** https://www.phoronix.com/news/Mesa-AGX-More-PVR-Reference  
**Description:** Report on Mesa AGX driver revealing additional PowerVR code commonalities.

### Tile-Based Rendering Technical Analysis
**URL:** https://hyeondg.org/gpu/tbr  
**Description:** In-depth technical comparison of TBDR (PowerVR/AGX) vs IMR architectures. Apple-specific features: sample shading, software blending, Vulkan optimization (45% reduction in memory reads).

### PowerVR TBDR Architecture Reference
**URL:** https://docs.imgtec.com/starter-guides/powervr-architecture/html/topics/tile-based-deferred-rendering-index.html  
**Description:** Official Imagination Technologies documentation on PowerVR TBDR. Two-phase pipeline (tiler + renderer), hidden surface removal, perfect tiling algorithm.

### Rust for Linux: Apple AGX GPU Driver
**URL:** https://rust-for-linux.com/apple-agx-gpu-driver  
**Description:** Summary of Apple AGX GPU driver effort within Rust for Linux project. Team structure, implementation approach.

### Toward a Universal GPU ISA (HTML full text)
**URL:** https://arxiv.org/html/2603.28793v1  
**Description:** Full HTML version of the 2603.28793 paper with detailed Apple G13 analysis.

### Apple Silicon HPC Paper (HTML)
**URL:** https://arxiv.org/html/2502.05317v1  
**Description:** Full HTML version of HPC performance evaluation paper.

---

## Key URLs for Further Investigation

**Not yet fully fetched / additional material:**

- https://alyssarosenzweig.ca/blog/asahi-gpu-part-2.html (Part II of dissecting series)
- https://alyssarosenzweig.ca/blog/asahi-gpu-part-6.html (Part VI)
- https://asahilinux.org/2022/12/gpu-drivers-now-in-asahi-linux/ (Initial GPU driver release)
- https://asahilinux.org/2024/01/fedora-asahi-new/ (Fedora Asahi Remix launch)
- https://asahilinux.org/2026/02/progress-report-6-19/ (Latest progress report)
- https://medium.com/@genelab_999/what-are-the-new-features-of-apple-gpu-ray-tracing-mesh-shading-dynamic-caching-38729caa5f7c (M3+ GPU features)
- https://developer.apple.com/documentation/metal/tailor-your-apps-for-apple-gpus-and-tile-based-deferred-rendering (Apple's official TBDR documentation)
- https://geeks3d.com/newz/item?id=359 (Geeks3D coverage of applegpu project)
- https://www.realworldtech.com/forum/?threadid=200265&curpostid=200324 (Real World Tech forum on Apple GPU RE)

---

## Search Queries That Found No Dedicated Talks

- FOSDEM talks specifically about Apple GPU by Alyssa Rosenzweig: No dedicated talk found (she attended FOSDEM 2026 for strategy discussions on M3/M4 support, but no dedicated GPU talk found in archives)
- Apple AGX shader ISA dedicated academic paper (other than the arXiv papers above): None found
- Apple GPU master's thesis or PhD dissertation: None found publicly

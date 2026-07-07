# Discover New Metal Profiling Tools for M3 and A17 Pro

Source: https://developer.apple.com/videos/play/tech-talks/111374/
Event: Tech Talks (2023)
Speakers: Ruiwei (Software Engineer, Metal Developer Tools), Irfan (Metal Developer Tools)
Fetched: 2026-05-09

## Session Description

Learn how new profiling tools in Xcode 15 can help you achieve the best Metal performance on
Apple family 9 GPUs. Covers shader cost graphs, performance heat maps, and shader execution
history tools. Includes new GPU counters to optimize GPU occupancy and ray-tracing performance.

---

## 1. New Profiling Tools in Xcode 15

### Shader Cost Graph
**Purpose:** Find and triage expensive shaders.

**Features:**
- Flame graph visualization of shader function costs
- Identifies most expensive functions in fragment shaders
- Source code annotations showing per-line performance cost
- Interactive selection to jump to source locations
- Performance popovers with detailed instruction breakdowns

**Use Case:** Identifies which shader functions consume the most GPU resources and provides
line-by-line performance metrics.

**Example Workflow:**
1. Capture GPU frame in Xcode
2. View Shader Cost Graph for expensive encoder
3. Identify expensive shader function (e.g., lighting function)
4. Click to jump to source annotation
5. Investigate per-line cost breakdown

### Performance Heat Maps

Visualizes pixel or compute thread performance metrics:

1. **Shader Execution Cost Heat Map:** Shows execution time and latency hiding by pixel position
2. **Thread Divergence Heat Map:** Visualizes GPU thread divergence in SIMD groups (varies with
   conditional branches)
3. **Overdraw Heat Map:** Shows pixels rendered by multiple GPU threads (overlapping geometry issue)
4. **Instruction Count Heat Map:** Displays exact instruction count per pixel/SIMD group
5. **Draw ID Heat Map:** Color-codes different GPU commands

**Optimization Tip:** Group GPU commands with opaque objects rendered first, then transparent
objects for best Apple GPU performance (HSR efficiency).

### Shader Execution History
**Purpose:** See exactly how SIMD groups execute shaders.

**Features:**
- Timeline visualization showing execution progress
- Full shader call stack at each execution point
- Automatic loop detection and iteration counting
- Thread state tracking
- Unprecedented insight into GPU execution patterns

**Workflow:**
1. Click pixels in performance heat maps
2. Reveal SIMD group execution timeline
3. Correlate with source code

---

## 2. Occupancy Profiling and Management

### Key Concepts

**Apple Family 9 GPU Architecture:**
- Multiple execution pipelines per shader core (FP32, FP16, texture/buffer reads/writes)
- On-chip memory: registers, thread group memory, tile memory, stack
- L1 cache backed by GPU last-level cache and device memory

**Occupancy Relationship to Performance:**
- Occupancy = number of SIMD groups concurrently running on a shader core
- Hides latency of long-memory operations by executing instructions from other SIMD groups
- Goal: Keep ALU and execution pipelines busy by increasing occupancy until memory thrashing occurs

### Memory Management (Family 9)
- Registers, threadgroup, tile, and stack memory dynamically allocated from L1 cache
- Balance between occupancy and cache utilization to prevent memory thrashing
- Occupancy Manager restricts thread occupancy to keep shader data on-chip

### Occupancy Triaging Workflow with New Performance Counters

1. **Check Occupancy Status**
   - View total occupancy in counter track
   - Compare with ALU and pipeline limiters

2. **Shader Launch Limited Counter**
   - Low value (< 0.07%): GPU starved due to small workload
   - High value: Sufficient threads launching or launch stalled by back pressure

3. **Thread Group Memory Check**
   - View memory allocation per dispatch in GPU timeline
   - Rules out threadgroup memory as cause of launch stalls

4. **Occupancy Manager Target Counter**
   - Lower than 100%: GPU balancing occupancy and cache utilization
   - If low, proceed to L1 analysis

5. **L1 Eviction Rate Analysis**
   - High spikes indicate L1 cache thrashing
   - Identify which memory type causes evictions

6. **L1 Load/Store Bandwidth Counter**
   - Shows L1 bandwidth for different on-chip memories
   - Identifies highest-traffic memory types

7. **L1 Residency Counter**
   - Shows L1 cache allocation breakdown
   - Identifies memory with largest working set

**Optimization Strategies:**
- Reduce pixel formats for image block memory
- Reduce MSAA sample count for complex geometry
- Improve spatial and temporal locality
- Reduce incoherent buffer accesses

8. **GPU Last-Level Cache and MMU Analysis**
   - High limiter vs. utilization ratio indicates cache thrashing
   - MMU limiter issues suggest TLB misses
   - Reduce buffer size and memory access incoherence

---

## 3. Ray Tracing Profiling (New Counters)

### New Ray Tracing Counters

1. **Ray Occupancy Track**
   - Shows percentage of active rays
   - GPU automatically optimizes ray occupancy for maximum performance

2. **Ray Activity Breakdown**
   - Percentage of active rays performing specific operations
   - Example: instance transform workload analysis
   - Helps identify optimization opportunities

3. **Intersection Test Tracks**
   - Percentage breakdown of primitive intersection types
   - Tracks opaque triangle tests vs. custom intersections
   - Optimization: Maximize opaque triangle tests, use custom intersections selectively

### Ray Tracing Optimization via Scratch Buffer Management
- Ray tracing unit uses significant L1 cache as scratch buffer
- Reduce by optimizing payload size
- Follow same occupancy triaging process

### Acceleration Structure Viewer
- Visualize acceleration structure breakdown
- Instance traversal highlight mode shows hotspots
- Identify and eliminate instance overlap
- Inspect scene hierarchy for optimization opportunities

**Best Practices:**
- Minimize instance overlap
- Concatenate instances into single primitive acceleration structures
- Review asset pipeline for unnecessary instance duplication

---

## Practical Case Study

**Problem:** GBuffer Pass consuming 50% of total GPU cost

**Investigation:**
1. Used Shader Cost Graph to identify expensive fragment shader
2. Found lighting function with 12 spotlight iterations (79% execution time)
3. Discovered misconfiguration duplicating spotlights

**Solution:** Removed duplicate lights -> significant performance improvement

---

## Resources

Video Downloads:
- HD: https://devstreaming-cdn.apple.com/videos/tech-talks/111374/4/B34C6255-A869-44BE-854B-468DC2871E98/downloads/tech-talks-111374_hd.mp4?dl=1
- SD: https://devstreaming-cdn.apple.com/videos/tech-talks/111374/4/B34C6255-A869-44BE-854B-468DC2871E98/downloads/tech-talks-111374_sd.mp4?dl=1

Related Videos:
- Explore GPU advancements in M3 and A17 Pro: https://developer.apple.com/videos/play/tech-talks/111375
- Learn performance best practices for Metal shaders: https://developer.apple.com/videos/play/tech-talks/111373
- Your guide to Metal ray tracing (WWDC23): https://developer.apple.com/videos/play/wwdc2023/10128
- Maximize your Metal ray tracing performance (WWDC22): https://developer.apple.com/videos/play/wwdc2022/10105

---

## Key Takeaways

1. Xcode 15 introduces state-of-the-art GPU profiling for Apple family 9 GPUs
2. Use Shader Cost Graph, Performance Heat Maps, and Shader Execution History together
3. Systematically triage GPU occupancy using new performance counters
4. L1 cache eviction analysis reveals root causes of occupancy limitations
5. Ray tracing counters and Acceleration Structure Viewer enable targeted RT optimization

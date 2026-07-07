# Toward a Universal GPU Instruction Set Architecture: A Cross-Vendor Analysis of Hardware-Invariant Computational Primitives in Parallel Processors

**Source:** https://arxiv.org/abs/2603.28793  
**PDF:** https://arxiv.org/pdf/2603.28793  
**HTML:** https://arxiv.org/html/2603.28793v1  
**ArXiv ID:** 2603.28793  
**Authors:** Ojima Abraham and Onyinye Okolie  
**Submitted:** March 22, 2026  
**Type:** Academic paper (arXiv preprint)

---

## Abstract

A systematic examination across four major GPU vendors: NVIDIA, AMD, Intel, and Apple. Analysis drew from:
- Official ISA reference manuals
- Architecture whitepapers
- Patent filings
- Community reverse-engineering efforts

Total: **over 5,000 pages of primary sources across 16 distinct microarchitectures**.

**Findings:**
- **10 hardware-invariant computational primitives** that appear across all four architectures
- **6 parameterizable dialects** where vendors implement identical concepts with different parameters
- **6 true architectural divergences**

The paper proposes an abstract execution model for a **vendor-neutral GPU ISA** grounded in the physical constraints of parallel computation.

---

## Apple G13 (AGX) Architecture Details

The Apple G13 GPU (M-series chips) was analyzed from reverse-engineered sources, credited to the Asahi Linux project and Dougall Johnson.

### Thread Model
- SIMD-groups of **32 threads** operating in lockstep
- **128 GPRs per thread** from 208 KB total register file
- **~60 KB threadgroup memory** (scratchpad) for workgroup-level data

### Divergence Mechanism
- Hardware stack maintained in register **r0l** (execution mask stack)
- **Distinct from NVIDIA's per-thread PC approach**
- Stack depth counter allows re-enabling threads at convergence points

### Notable Limitation
- **No native FP64 support** — limits applicability for certain HPC workloads

---

## Ten Hardware-Invariant Computational Primitives

These primitives appear in all four vendors' architectures (NVIDIA, AMD, Intel, Apple G13):

1. **Lockstep Thread Groups** - Required because "instruction fetch costs 100× more energy than single-lane arithmetic at modern nodes"

2. **Mask-Based Divergence** - Required for correctness under lockstep execution; prevents divergent branches from corrupting inactive threads

3. **Register-Occupancy Tradeoff** - Derived from fixed SRAM area constraints; more registers = fewer concurrent threads

4. **Managed Scratchpad Memory** - Enables explicit data placement that caches cannot predict; essential for cooperative algorithms

5. **Zero-Cost Context Switching** - Cheaper than speculation given memory latency dominance; all threads resident simultaneously

6. **Hierarchical Memory** - Register → scratchpad → device memory progression; each level trades latency for capacity

7. **Atomic Read-Modify-Write Operations** - Across all memory scopes; necessary for concurrent data structures

8. **Workgroup-Scope Barriers** - Enabling synchronization without global coordination; scoped to avoid global stalls

9. **Identity Registers** - Thread position and ID information; necessary for data partitioning

10. **Asynchronous Memory + Synchronization** - Decoupled load/store from completion; enables latency hiding

---

## Six Parameterizable Dialects

Where vendors implement identical concepts with different parameters:
(Specific examples for Apple G13 involve the 32-thread SIMD-group size vs. NVIDIA's 32-warp, AMD's 64-wavefront configurations)

---

## Six True Architectural Divergences

Including:
- Apple's hardware-stack divergence mechanism (vs. NVIDIA per-thread PC, AMD implicit reconvergence)
- Absence of native FP64 (Apple only among the four studied)
- Shuffle primitive differences across vendors

---

## Experimental Validation on Apple M1

The abstract execution model was validated on NVIDIA T4 and Apple M1 hardware — described as "the two most architecturally distant platforms in the study."

### Apple M1 Results

| Benchmark | Abstract Model Performance vs Native |
|-----------|--------------------------------------|
| Parallel Reduction | **97.8%** of native |
| GEMM | **101.2%** of native (parity) |
| Histogram (atomic-heavy) | **102.1%** of native |

Compare with NVIDIA T4:
- Parallel reduction: **62.5%** of native (poor - requires vendor shuffle primitives)

### Interpretation
Apple's architectural strengths enable near-native abstract performance:
1. **Higher hardware scheduling flexibility** — tolerates barrier-synchronized shared memory more efficiently
2. **Unified memory architecture** — no discrete VRAM bandwidth cliff
3. **Less dependency on vendor-specific shuffle operations** — reduction can be done efficiently with barriers

This revealed that intra-wave shuffle operations must become mandatory primitives in any universal ISA framework (to serve NVIDIA well).

---

## Significance for Apple GPU RE

This is the first academic paper to:
1. Formally place Apple's G13 GPU in a cross-vendor comparative framework
2. Validate reverse-engineered Apple GPU documentation against hardware benchmarks
3. Identify which Apple GPU architectural choices are truly unique vs. common across vendors
4. Demonstrate that the reverse-engineered applegpu documentation is accurate enough for academic use

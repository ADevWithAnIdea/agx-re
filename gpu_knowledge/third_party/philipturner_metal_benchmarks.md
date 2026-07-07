# Apple GPU Microarchitecture Analysis (philipturner/metal-benchmarks)

**Source:** https://github.com/philipturner/metal-benchmarks  
**GitHub README:** https://github.com/philipturner/metal-benchmarks/blob/main/README.md  
**Author:** Philip Turner

---

## Summary

Comprehensive empirical microarchitecture documentation for Apple GPU (M1, M2, M3, M4). Documents latencies for each ALU assembly instruction, cache sizes, unique instruction pipelines, and power characteristics. Enables evidence-based reasoning about performance bottlenecks.

---

## Core Architecture

### GPU Core Die Area and Composition
- Each GPU core spans approximately **~2mm²**
- Contains approximately **~512KB of registers/L1 cache**
- L2 bandwidth: **32 bytes/cycle per core**
- Single GPU core delivers roughly **2.67× more power than a CPU core** (at 100% ALU utilization)

---

## Cache Hierarchy

| Level | Size | Notes |
|-------|------|-------|
| L1 Data Cache | 8 KB | Smallest among competitors |
| L1 Instruction Cache | 12 KB | |
| L2 Cache | 256 KB – 1 MB | Varies by model; M1 Pro ~512K |
| L3 / SLC | 8 – 96 MB | System Level Cache (shared with CPU) |

> "Apple reduces the amount of static power necessary for operation" by minimizing L1D, L1I, and L2 sizes, compensating through exceptional SLC memory bandwidth and low-latency L2 performance.

---

## Compute Performance

### Per Core-Cycle Throughput
| Operation | Throughput |
|-----------|-----------|
| FP16 FMA | 256 operations/cycle |
| FP32 FMA | 128–256 operations/cycle (generation-dependent) |
| FP64 | Emulated; ≤3.8 cycles effective |

Note: M1 and A15 doubled FP32 performance compared to A14.

---

## Instruction Latencies

| Instruction | Latency |
|-------------|---------|
| FADD16 | 2.16 cycles (adjusted) |
| FFMA32 | 2.21 cycles |
| RECIP32 | 6.5 cycles |
| RSQRT32 | 8.99 cycles |

### Register Dependency Penalties
- 32-bit register dependency: **0.84-cycle penalty**
- 16-bit register dependency: **0.56-cycle penalty**

> "In low-occupancy situations, F16/I16 is significantly faster than F32/I32."

---

## Dual-Dispatch Architecture

A remnant of PowerVR heritage:
- Original PowerVR could only execute F32 instructions at 2 IPC
- Apple GPU retains **"dual-dispatch from 2 SIMDs mode"**
- Preferred at low occupancy and/or low ILP
- Required to fully utilize FP16/I16
- Complex pipeline: runs one 32-wide instruction per SIMD every 4 cycles

---

## Unique Hardware Features

### Nanite Atomics (M2+)
Hardware acceleration for **UInt64 min/max operations**:
- Specifically enables Unreal Engine 5's Nanite rendering on macOS
- "The only 64-bit atomic instruction"
- Despite potential for broader functionality, only exposed for min/max

### Hardware Ray Tracing (M3+)
- "Hardware acceleration for ray-box intersections, hidden in plain sight"
- Implemented within a general-purpose instruction unique to Apple GPUs
- Not a dedicated fixed-function unit (disguised as general instruction)

### Matrix Operations / simdgroup_matrix
- Apple's equivalent of "tensor cores"
- `simdgroup_matrix` instruction decreases register pressure while improving ALU utilization
- Functions within existing FP32 pipelines
- Not a separate hardware unit

---

## Power Efficiency

Extraordinary efficiency characteristics:
- M1 Max: "a single SIMD active consuming 800 mW of power — 1/1000 the power of an RTX 4090 Ti"
- Apple GPU "conserves power at the granularity of individual vector ALUs"
- Sub-core concurrency: **96 simultaneous compute commands across 32 cores**
- Allows fine-grained resource division preventing wasteful core allocation

---

## GPU Generation Compute Performance (Peak TFLOPS FP32)

| Chip | Peak TFLOPS |
|------|-------------|
| M1 | 1.36 |
| M2 | 2.24 |
| M3 | 2.47 |
| M4 | 2.9 |

---

## Memory Bandwidth

| Chip | GPU Memory Bandwidth |
|------|---------------------|
| M1 | 60 GB/s |
| M2 | 91 GB/s |
| M3 | 92 GB/s |
| M4 | 100 GB/s |

Efficiency: 85–90% of theoretical maximum typically achieved.

---

## GPU Generation Naming Map

| GPU Internal Name | Chips |
|-------------------|-------|
| G13G | M1 |
| G13X | M1 Pro, M1 Max, M1 Ultra |
| G14 | A15, A16 (some) |
| G16 (formerly G15) | A17 Pro, M3, M4 |

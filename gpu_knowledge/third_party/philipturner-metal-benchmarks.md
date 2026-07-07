# Apple GPU Microarchitecture Research - Metal Benchmarks
<!-- Source: https://github.com/philipturner/metal-benchmarks -->
<!-- Reverse-engineered Apple GPU microarchitecture via Metal compute benchmarks -->

## Core Architecture (M1 generation, per GPU core)

- Register file: ~208 KB per core
- Shared memory: ~60 KB per core
- Instruction cache: 8 KB per core
- ALUs: 128 per core, sustaining 1 scalar instruction/cycle
- Concurrent threads per core: 384-3072 (register-file limited)

## Compute Performance

M1 Max (32 cores at 1296 MHz): ~10.6 TFLOPS FP32

FP throughput:
- FP16: 1-cycle throughput
- FP32: 2-cycle under optimal conditions
- Significant penalties under register dependencies

## Memory Hierarchy

| Level | Size range | Notes |
|-------|-----------|-------|
| L2 | 256 KB (M1 Pro) – 1 MB (M1 Ultra) | Per GPU cluster |
| L3 | 8–96 MB | Shared system cache |
| Bandwidth to L3 | ~15–22 bytes/cycle | |
| On-core bandwidth | ~32 bytes/cycle | |

## Sub-Core Concurrency

M1 Max supports up to 96 simultaneous compute commands (vs typical GPU limit of 128 max). This enables finer division of work than competing architectures.

## Power Efficiency

Apple uses smaller on-chip caches than AMD/Nvidia but maintains low L2 latency, reducing static power. The register file is the key constraint on thread occupancy.

## A14 vs M1 Comparison

A14 (iPhone) has half the FP32 processing power of M1, suggesting distinct architectural decisions between mobile and Mac GPU cores.

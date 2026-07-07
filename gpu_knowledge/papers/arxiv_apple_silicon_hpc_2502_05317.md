# Apple vs. Oranges: Evaluating the Apple Silicon M-Series SoCs for HPC Performance and Efficiency

**Source:** https://arxiv.org/html/2502.05317v1  
**ArXiv ID:** 2502.05317  
**Published:** February 2025  
**Type:** Academic paper (arXiv preprint)

---

## Summary

Systematic HPC performance and efficiency evaluation of Apple M1–M4 chips. While focused on HPC rather than GPU RE per se, provides useful architectural data for understanding the GPU compute capabilities.

---

## GPU Architecture Overview

All M-series GPUs use **tile-based deferred rendering (TBDR)** architecture:
- Screen divided into tiles, processed sequentially
- Minimizes unnecessary pixel rendering
- Optimizes power consumption

### GPU Core Counts
| Chip | GPU Cores |
|------|-----------|
| M1 | 7-8 |
| M2 | 8-10 |
| M3 | 8-10 |
| M4 | 8-10 |

All generations support: FP32, FP16, INT8 natively.
**Notable absence:** No native FP64 support (limitation for scientific computing).

---

## Peak Compute Performance

| Chip | FP32 TFLOPS |
|------|-------------|
| M1 | 1.36 |
| M2 | 2.24 |
| M3 | 2.47 |
| M4 | 2.9 |

---

## Memory Bandwidth

| Chip | GPU Bandwidth | Theoretical Max |
|------|--------------|-----------------|
| M1 | 60 GB/s | ~85-90% efficiency |
| M2 | 91 GB/s | ~85-90% efficiency |
| M3 | 92 GB/s | ~85-90% efficiency |
| M4 | 100 GB/s | ~85-90% efficiency |

---

## Power Efficiency

GPU implementations achieved: **~200 GFLOPS per Watt** efficiency across all four chips.

Metal Performance Shaders (MPS) implementations delivered **10× higher efficiency** than naive GPU implementations.

---

## Programming Model

- **Metal API**: Low-level GPU access (Apple proprietary)
- **Metal Performance Shaders (MPS)**: High-level abstractions for optimized computations
- No native CUDA/OpenCL (OpenCL support via Rusticl/Honeykrisp on Asahi Linux)

---

## Relevance to GPU RE

This paper provides:
- Validated peak performance numbers to compare against
- Memory bandwidth figures useful for estimating compute-bound vs. bandwidth-bound thresholds
- Power efficiency baseline for GPU workloads

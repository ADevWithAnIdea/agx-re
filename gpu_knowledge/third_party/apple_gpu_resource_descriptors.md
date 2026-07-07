# GPU Resource Descriptors on Apple GPUs

**Source:** https://techboards.net/threads/gpu-resource-descriptors-on-apple-gpus.4156/  
**Context:** Technical discussion with contributions from Dougall Johnson

---

## Overview

A GPU resource descriptor provides the information needed to access data. When fetching texture data, the GPU needs to know: memory location, texture size, pixel data format, and other metadata.

---

## Apple GPU Descriptor Model

Apple GPUs use a **table-based descriptor system**.

### Texture Descriptors
- Each descriptor: **24 bytes**
- Stored in continuous memory arrays
- Accessed via: **64-bit base address** (in uniform registers) + **32-bit dynamic offset** (in general registers)
- The offset corresponds to `gpuResourceID` value, incrementing by 24 bytes per texture

### Sampler Descriptors
- Each descriptor: **8 bytes**
- Maximum: **1,024 unique samplers**
- Indexed via a **16-bit register** (direct index, not offset arithmetic)
- Metal automatically deduplicates identical sampler configurations

---

## Metal Abstraction

Metal wraps hardware descriptor management through **argument buffers**:
- C-style pointer arithmetic abstraction
- Framework handles descriptor table management automatically
- Hides underlying index calculations from programmers

---

## Hardware Comparison

| GPU Vendor | Descriptor Model |
|-----------|-----------------|
| Apple | Table-based; 64-bit base + 32-bit offset; 24B texture, 8B sampler |
| AMD | Inline descriptor values |
| Intel | Table lookups (similar to Apple) |
| NVIDIA | Fixed global descriptor tables |

---

## Relevance for RE

Understanding the descriptor format is essential for:
- Implementing texture sampling in an open-source driver
- Correctly setting up argument buffers for shader inputs
- Understanding how `gpuResourceID` maps to hardware state

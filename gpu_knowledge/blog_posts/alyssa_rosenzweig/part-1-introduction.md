# Dissecting the Apple M1 GPU, Part I

**Source URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-1.html  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 7 January 2021  
**Project:** Asahi Linux  

---

## Overview

This is the first post in the "Dissecting the Apple M1 GPU" series, documenting initial reverse-engineering of Apple's M1 GPU instruction set for the purpose of writing a free, open-source graphics driver for Asahi Linux.

---

## Methodology

The reverse-engineering approach closely paralleled prior work on ARM Mali GPUs (Panfrost/Lima projects). Key techniques:

### macOS System Call Interception

On Linux, `LD_PRELOAD` is used to interpose shared library calls. The macOS equivalent is `DYLD_INSERT_LIBRARIES`. The author used this to wrap `IOConnectCallMethod` calls — the macOS equivalent of `ioctl` for communicating with kernel extensions (kexts).

**Three critical kernel interface calls identified:**
1. Memory allocation
2. Command buffer creation
3. Command buffer submission

### Shader Binary Comparison

The core technique for decoding the instruction set:

1. Write a simple shader in Metal/GLSL
2. Capture the compiled binary output via the intercepted kernel calls
3. Make a minimal change to the shader source
4. Capture the new binary output
5. Compare the two binaries to identify which bits changed and how they correspond to the shader modification

This iterative process was repeated for each instruction/feature to be decoded.

---

## Architectural Findings

### Scalar Architecture

The M1 GPU is **scalar at all bit widths** — both 16-bit and 32-bit operations are scalar. This is in contrast to many embedded GPUs that use vector architectures (e.g., Mali Midgard's vec4 or vec16 design).

However, the hardware appears to be **superscalar**: there are more 16-bit ALUs than 32-bit ALUs, enabling efficient low-precision operations. Evidence for superscalar behavior was found by comparing instruction timing:

- `imad` (integer multiply-add) was avoided by the compiler in favor of repeated `iadd` instructions
- This implies multiple `iadd` units can execute in parallel, making repeated adds faster than a single multiply-add

### Hardware-Based Instruction Scheduling

The M1 GPU implements **hardware-based instruction scheduling**, meaning the hardware reorders and schedules instructions dynamically. This is:

- Common among desktop GPUs (e.g., AMD, NVIDIA)
- Less common in the embedded/mobile GPU space (ARM Mali uses software scheduling in the compiler)

This reduces compiler complexity (no need for software scheduling passes) while increasing hardware complexity.

### Floating-Point Instruction Modifiers

Floating-point operations support **free modifiers** with no additional cost:

- **Clamp**: Clamp result to [0, 1]
- **Negate**: Negate a source operand
- **Absolute value**: Take absolute value of a source operand
- **Type conversion**: Free 16-bit ↔ 32-bit conversion on both sources and destinations

These modifiers are encoded directly in the instruction word and execute without additional cycles.

### Integer Operations

Supported bitwise/integer operations on select instructions:

- Bitwise complement (NOT)
- Shifts

### No Convoluted Optimization Tricks

The author's conclusion: "there are no convoluted optimization tricks" in the instruction set design. The architecture is streamlined and efficient without unnecessary complexity.

---

## Tools Released

The author released initial reverse-engineering tools on GitHub:

- **Repository:** https://github.com/AsahiLinux/gpu

---

## Related Projects Referenced

- **Lima** — Free driver for ARM Mali Utgard GPUs
- **Freedreno** — Free driver for Qualcomm Adreno GPUs
- **Nouveau** — Free driver for NVIDIA GPUs
- **Panfrost** — Free driver for ARM Mali Midgard/Bifrost GPUs (the author's primary prior work)

---

## Context and Next Steps

This post establishes the foundation for the series. The initial work focused on:

1. Setting up the interception infrastructure
2. Decoding the instruction set encoding
3. Characterizing the GPU's architectural properties

Subsequent posts would cover:
- Drawing a triangle (command buffer reverse engineering)
- Writing a shader compiler
- Building a full OpenGL/Vulkan driver

---

## Notes

- The GPU in the Apple M1 is commonly referred to as "AGX" in the open-source community
- The architecture has connections to Imagination Technologies PowerVR (rumored predecessor lineage)
- The work is part of the broader Asahi Linux project to bring Linux to Apple Silicon Macs

# Dissecting the Apple M1 GPU, Part I

**Source:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-1.html  
**Author:** Alyssa Rosenzweig  
**Published:** January 2021  
**Also mirrored at:** https://rosenzweig.io/blog/asahi-gpu-part-1.html

---

## Summary

First in a series documenting the reverse engineering of the Apple M1 GPU. Covers initial methodology, tooling setup, and first architectural observations from analyzing the shader ISA and command stream.

---

## Reverse Engineering Methodology

The approach mirrors techniques used in prior GPU projects (e.g., Panfrost for Mali):

1. **Wrapper library intercept** - On macOS, adapted Linux/Android approaches:
   - Replaced `LD_PRELOAD` with `DYLD_INSERT_LIBRARIES` to hook into applications
   - Wrapped `IOConnectCallMethod` (macOS's equivalent to `ioctl`) instead of standard Linux calls

2. **Critical IOKit calls identified:**
   - Memory allocation
   - Command buffer creation
   - Submission

3. **Shader analysis process:**
   - Dump GPU-visible memory after command buffer submission
   - Iterative comparison: "start with the simplest fragment or compute shader possible, make a small change in the input source code, and compare the output binaries"
   - Differential analysis of binary changes to map source-to-binary relationships

---

## Architectural Discoveries

### Scalar Design
The M1 GPU operates as **scalar across all bit widths**:
- No vector types at the ISA level
- Hardware is superscalar with **more 16-bit ALUs than 32-bit units**
- Enables efficient low-precision operations without explicit vectorization in source

### Hardware Scheduling
Architecture handles scheduling **in hardware** rather than relying on compiler-managed scheduling:
- Reduces compiler complexity
- Increases hardware sophistication
- Compiler does not need to explicitly schedule instructions to hide latency

### Free Modifiers
Floating-point operations support without additional cost:
- Clamping (saturation)
- Negation
- Absolute value
- Type conversion between 16-bit and 32-bit (on sources AND destinations, for free)

### Variable Instruction Timing
Different ALU instructions exhibit varying pipeline lengths:
- Complex operations like `imad` are sometimes avoided in favor of repeated simpler additions
- This confirms **superscalar execution** with multiple independent pipelines

---

## Key Observation: Scalar + Superscalar
The combination of scalar ISA and superscalar execution is distinctive:
- Scalar ISA simplifies the compiler (no vector packing decisions)
- Hardware executes multiple scalar operations in parallel within a single cycle
- More 16-bit than 32-bit ALUs means fp16/int16 ops can be twice as fast

---

## Context
- Researcher purchased a Mac Mini with M1 to study the ISA and command stream
- Reached milestone of understanding enough of the ISA to disassemble simple shaders with FOSS toolchain
- Part of the Asahi Linux project (https://asahilinux.org)

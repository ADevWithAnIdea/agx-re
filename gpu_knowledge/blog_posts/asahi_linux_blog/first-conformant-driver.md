<!-- Source: https://asahilinux.org/2023/08/first-conformant-m1-gpu-driver/ -->
# First Conformant M1 GPU Driver

*Asahi Linux Blog — August 2023*

## Overview

The Asahi Linux project released "the world's **_only_** conformant OpenGL ES 3.1 implementation for M1- and M2-family graphics hardware," representing the first conformant graphics standard implementation for Apple's M-series GPUs.

## Conformance Achievement

To achieve conformance status, implementations must pass official Khronos test suites verifying specification features. "After a 30-day review period, if no issues are found, the implementation becomes conformant." The drivers received listings on the Khronos website for M1, M1 Pro/Max/Ultra, M2, and M2 Pro/Max variants.

## OpenGL ES 3.1 Features

The ES 3.1 standard introduces compute shaders for accelerating general computations within graphics applications. A notable addition is atomic operations on images, enabling flexible image processing algorithms previously constrained by fixed-function pipelines.

Atomics guarantee "consistent, well-defined results for select operations, regardless of the order of the threads," solving race conditions in massively parallel GPU execution.

## Image Atomic Implementation Challenge

The M1 GPU lacks dedicated hardware instructions for image atomics despite supporting non-image atomics and non-atomic images. The solution involved calculating pixel memory addresses and performing standard atomic operations on those addresses.

### Linear Memory Addressing

For linearly-arranged images, the formula is:

```
Address(X, Y) = Address(0, 0) + Y × Stride + X × BytesPerPixel
```

### Interleaved Memory Addressing

Modern graphics hardware uses interleaved coordinate layouts following spiral-like curves rather than linear arrangement. Bit-twiddling algorithms efficiently interleave coordinates by processing bit groups in parallel.

### Vectorized Bit Interleaving Assembly

The initial M1 GPU assembly implementation required 10 instructions:

```assembly
# Inputs x, y in r0l, r0h.
# Output in r1.

add r2, #0, r0, lsl 4
or  r1, r0, r2
and r1, r1, #0xf0f0f0f
add r2, #0, r1, lsl 2
or  r1, r1, r2
and r1, r1, #0x33333333
add r2, #0, r1, lsl 1
or  r1, r1, r2
and r1, r1, #0x55555555
add r1, r1l, r1h, lsl 1
```

## Reverse-Engineering the Interleave Instruction

### Methodological Approach

Rather than discovering the instruction through compiled shader observation, researchers employed systematic hypothesis testing. Dougall Johnson hypothesized based on PowerVR architecture patterns that an undocumented interleave instruction might exist.

### Instruction Encoding Analysis

Known M1 GPU bit-manipulation instructions include:
- Bit reverse (operation code `01`)
- Bit population count (operation code `10`)
- Find first set bit (operation code `11`)
- **Unknown operation code `00`** (hypothesized interleave)

The unobserved two-bit enumeration value suggested the interleave instruction occupies this encoding space.

### Two-Source Hypothesis

Single-source instructions (reverse, count, find) exhibited architectural gaps where a second source could logically reside. Based on "symmetry" and "consistent source encoding across instructions," the second source likely occupies this reserved space.

### Verification Methodology

Rather than handwriting GPU assembly, the team modified their compiler to replace two-source integer operations (multiply instructions) with the hypothesized interleave encoding. A compute shader was written to verify results across approximately "4 billion ($2^{32}$) inputs" representing all possible 16-bit source combinations.

Result: Confirmed functional interleave instruction executing "in under a second."

## Performance Outcome

The documented ten-instruction interleave sequence was replaced with a single dedicated instruction, simplifying code while maintaining performance and conformance test passage.

## Architectural Context

The achievement occurred despite minimal funding and small team size ("Asahi Lina and I are two individuals with minimal funding"), contrasting with manufacturer driver non-conformance across Vulkan and OpenGL standards.

# The First Conformant M1 GPU Driver

**Source URL:** https://alyssarosenzweig.ca/blog/first-conformant-m1-gpu-driver.html  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 22 August 2023  
**Project:** Asahi Linux  

---

## Overview

This post announces the world's first (and at the time, only) conformant OpenGL ES 3.1 implementation for Apple M1 and M2 family GPU hardware. The driver passed tens of thousands of Khronos conformance tests and was officially recognized as conformant by Khronos. The post details the technical work required for ES 3.1 support, particularly the implementation of image atomic operations on hardware that lacks native support for them.

---

## Conformance Achievement

### The Claim

> "The world's **only** conformant OpenGL ES 3.1 implementation for M1- and M2-family graphics hardware."

Apple's own GPU drivers for M1/M2 are **not conformant** to any graphics API standard. The open-source Asahi driver achieved conformance first.

### Supported Hardware

- Apple M1
- Apple M1 Pro / M1 Max / M1 Ultra
- Apple M2
- Apple M2 Pro / M2 Max

### Khronos Submission References

| Hardware | Submission ID |
|----------|--------------|
| M1 | 1007 |
| M1 Pro/Max/Ultra | 1014 |
| M2 | 1016 |
| M2 Pro/Max | 1017 |

### Conformance Process

- Passed tens of thousands of conformance tests
- Submitted to Khronos for official recognition
- **30-day review period** by Khronos before official listing
- Appears on Khronos conformance adopters page: https://www.khronos.org/conformance/adopters/

---

## OpenGL ES 3.1 New Features

ES 3.1 adds significant capabilities over ES 3.0, including:

- **Compute shaders** — General-purpose GPU computations (not just vertex/fragment)
  - Enables parallel image processing algorithms
  - Addresses synchronization stalls in physics simulations
  - Required for many modern rendering techniques
- **Image load/store** — Read and write textures from shaders directly
- **Image atomics** — Atomic read-modify-write operations on image pixels (the main challenge documented in this post)
- **Shader storage buffer objects (SSBOs)**
- **Indirect draw** commands
- **Multi-sample textures**

---

## The Core Challenge: Image Atomics on M1

### Problem Statement

Modern GPUs execute thousands of shader threads in parallel. When multiple threads attempt to write to the **same pixel location** simultaneously, race conditions occur. Without atomic operations, the final pixel value depends on execution order (which is undefined), producing incorrect results.

**Image atomic operations** guarantee correct results regardless of execution order — each atomic is an indivisible read-modify-write.

**The hardware problem:** The M1 GPU lacks native image atomic instructions, unlike competing GPUs (AMD, NVIDIA, Intel, ARM Mali). It has:

- ✓ Non-image atomics (atomic operations on buffer memory addresses)
- ✓ Non-atomic image operations (regular texture reads/writes)
- ✗ Native image atomic instructions

### Solution Architecture

Rather than using non-existent dedicated image atomic instructions, the implementation:

1. **Calculate the pixel's memory address** from its X, Y coordinates
2. **Perform a standard memory atomic** on that calculated address

This converts an image atomic into a regular memory atomic using computed addresses.

---

## Memory Layout Challenge: Linear vs. Tiled

### Linear Memory (simple case)

For a linearly-laid-out image, the address calculation is straightforward:

```
Address(X, Y) = Address(0, 0) + Y × Stride + X × BytesPerPixel
```

This is simple integer arithmetic.

### Tiled Memory (real case)

Modern GPU textures are **not linear in memory**. They use space-filling curves (Morton order / Z-order curve) or other tiling schemes for cache efficiency.

In a Morton-order (bit-interleaved) layout:

```
Address(X, Y) = Address(0, 0) + interleave_bits(X, Y) × BytesPerPixel
```

Where `interleave_bits` interleaves the bits of X and Y coordinates:

```
X = x₆x₅x₄x₃x₂x₁x₀
Y = y₆y₅y₄y₃y₂y₁y₀

interleave(X, Y) = y₆x₆y₅x₅y₄x₄y₃x₃y₂x₂y₁x₁y₀x₀
```

This requires **bit-level manipulation** of the coordinates.

**Constraint:** The bit interleaving is limited to the **lower 7 bits (or fewer)** of each coordinate (i.e., within a 128×128 pixel tile).

---

## The Bit Interleaving Algorithm

### Input/Output

- **Inputs:** X coordinate in low 16 bits of a 32-bit register, Y coordinate in high 16 bits
- **Output:** Interleaved bits in a result register

### Vectorized Implementation: 10-Instruction Sequence

The algorithm uses a well-known bit manipulation technique (from Stanford Bit Twiddling Hacks) adapted for the AGX ISA, processing multiple bits in parallel:

```assembly
# Inputs x, y in r0l (low 16 bits), r0h (high 16 bits).
# Output in r1.

add r2, #0, r0, lsl 4     # r2 = r0 << 4
or  r1, r0, r2             # r1 = r0 | (r0 << 4)
and r1, r1, #0x0f0f0f0f    # mask: keep bits at positions 0-3 and 8-11
add r2, #0, r1, lsl 2      # r2 = r1 << 2
or  r1, r1, r2             # r1 = r1 | (r1 << 2)
and r1, r1, #0x33333333    # mask: keep bits at positions 0-1, 4-5, 8-9, 12-13
add r2, #0, r1, lsl 1      # r2 = r1 << 1
or  r1, r1, r2             # r1 = r1 | (r1 << 1)
and r1, r1, #0x55555555    # mask: keep even-positioned bits
add r1, r1l, r1h, lsl 1    # combine X and Y components: r1 = r1_low + (r1_high << 1)
```

**Reference:** Stanford Bit Twiddling Hacks — https://graphics.stanford.edu/~seander/bithacks.html#InterleaveBMN

### Exhaustive Verification

The 10-instruction implementation was verified by:

- **Input space:** Approximately 2^32 (4 billion) possible (X, Y) input combinations
- **Method:** Test all inputs, compare software reference vs. GPU output
- **Time:** "Under a second" for complete verification

---

## Reverse Engineering: The `interleave` Instruction

### Discovery Methodology

While the 10-instruction sequence worked correctly, **Dougall Johnson** suspected a single dedicated instruction might exist based on instruction encoding analysis:

#### Known Bit Manipulation Instructions

AGX has a class of "unary bit manipulation" instructions. Known members:

| Encoding (2 bits) | Operation |
|-------------------|-----------|
| `01` | Reverse bits (bit reversal) |
| `10` | Count set bits (popcount) |
| `11` | Find first set bit (ctz/clz) |
| `00` | **Unknown / potentially interleave** |

The encoding `00` was conspicuously unused. Based on:
1. The pattern of the other instructions (all are bit manipulation operations)
2. The existence of a need for interleaving in image addressing
3. The PowerVR ISA having an SHFL (shuffle/interleave) instruction (PowerVR reference: https://docs.imgtec.com/reference-manuals/powervr-instruction-set-reference/)

Johnson hypothesized that `00` encoded an **interleave instruction**.

#### Validation Process

1. **Hypothesis:** Encoding `00` = interleave, with second source operand providing Y coordinate
2. **Method:** Modify the compiler to inject the guessed instruction encoding
3. **Test:** Write a shader that uses interleave, compare output against reference
4. **Alternative test:** Replace multiply operations with the guessed interleave instruction and check results
5. **Result:** Confirmed — the instruction exists and performs exactly the expected bit interleaving

#### Final Result

The 10-instruction sequence was replaced by a **single `interleave` instruction**, dramatically reducing instruction count for image address calculation.

---

## Impact on Conformance

The image atomic implementation was the key blocker for OpenGL ES 3.1 conformance. Once implemented:

- All image atomic conformance tests passed
- Full ES 3.1 conformance test suite passed
- Official Khronos submission made

---

## Industry Context

### Why Manufacturer Conformance Matters

Apple's shipped M1 drivers (as of August 2023) are **not conformant** to any graphics API standard. This creates problems for:

- **MoltenVK** — Third-party Vulkan-to-Metal translation layer. Relies on Metal's correctness; Metal bugs become Vulkan bugs. (GitHub: https://github.com/KhronosGroup/MoltenVK)
- **Applications expecting standard behavior** — OpenGL/Vulkan applications assume conformant drivers; non-conformant drivers produce incorrect results

The Asahi open-source driver being conformant while Apple's proprietary driver is not is described as unusual and notable.

---

## Contributors

- **Alyssa Rosenzweig** — Driver and compiler implementation
- **Dougall Johnson** — Reverse-engineering of the `interleave` instruction (Mastodon: @dougall)
- **Asahi Lina** — Kernel driver (Mastodon: @lina@vt.social)
- **Ella Stanforth** — Vulkan driver

---

## Links and References

- Asahi Linux: https://asahilinux.org/
- Fedora Asahi Remix: https://fedora-asahi-remix.org/
- Mesa drivers: https://gitlab.freedesktop.org/asahi/mesa
- Khronos conformance adopters: https://www.khronos.org/conformance/adopters/
- OES shader image atomic extension spec: https://registry.khronos.org/OpenGL/extensions/OES/OES_shader_image_atomic.txt
- PowerVR Instruction Set Reference: https://docs.imgtec.com/reference-manuals/powervr-instruction-set-reference/
- Stanford Bit Twiddling Hacks: https://graphics.stanford.edu/~seander/bithacks.html#InterleaveBMN
- Interleave shader test: /blog/interleave.shader_test
- MoltenVK: https://github.com/KhronosGroup/MoltenVK

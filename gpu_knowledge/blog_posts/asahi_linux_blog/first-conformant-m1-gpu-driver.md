# The first conformant M1 GPU driver

> Source URL: https://asahilinux.org/2023/08/first-conformant-m1-gpu-driver/

Asahi Linux has achieved a significant milestone by releasing "conformant OpenGL® ES 3.1 drivers" for M1 and M2 family GPUs. This represents the industry's only standards-compliant implementation for these chips.

## Conformance Achievement

The drivers underwent rigorous testing through Khronos's official conformance test suite, passing "tens of thousands of tests to demonstrate correctness." After the mandatory 30-day review period, the implementation gained official recognition across multiple GPU variants, including M1, M1 Pro/Max/Ultra, M2, and M2 Pro/Max configurations.

This accomplishment contrasts sharply with Apple's proprietary drivers, which lack conformance certification for any graphics standard. The developers emphasize that their commitment to open standards and cross-vendor collaboration represents the ecosystem's future direction.

## Technical Implementation: Image Atomics

A notable ES 3.1 feature involves atomic operations on images—allowing parallel threads to safely write pixel data simultaneously. The M1 GPU presented a hardware limitation: it lacked dedicated image atomic instructions, though regular atomic operations existed.

The solution involved calculating pixel memory addresses and performing standard atomics on those addresses. While linear memory layouts simplify this calculation, modern GPUs use interleaved coordinate systems for cache efficiency, requiring bit manipulation.

### The Interleave Discovery

Rather than implementing a 10-instruction workaround, the team pursued reverse engineering to locate a potential dedicated instruction. Through systematic analysis of instruction encodings and educated hypothesis testing, they identified an unobserved operation code (`00`) in the GPU's instruction set.

By modifying their compiler to test this theoretical instruction and running comprehensive shader validation, they confirmed its existence and functionality—replacing ten instructions with a single operation that performs the necessary coordinate interleaving for atomic image operations.

This discovery exemplifies how rigorous reverse engineering combined with hardware understanding can unlock optimizations previously considered impossible.

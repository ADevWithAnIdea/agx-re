# Dissecting the Apple M1 GPU, part III

> Source URL: https://rosenzweig.io/blog/asahi-gpu-part-3.html
> Redirect: https://alyssarosenzweig.ca/blog/asahi-gpu-part-3.html

After investigating the Apple M1 GPU, the author successfully developed an open-source shader compiler capable of rendering 3D graphics. The project builds on earlier work that demonstrated drawing a triangle with custom code.

## Compiler Development Context

The compiler was created for Asahi Linux, which aims to run Linux on Apple Silicon hardware. Rather than using LLVM (Apple's preference), the team adopted Mesa's New Intermediate Representation (NIR), following precedent set by Valve's AMD backend rewrite.

## Hardware Architecture Insights

The AGX2 GPU instruction set exhibits distinctive characteristics:

- Scalar arithmetic operations
- Vectorized input/output handling
- 16-bit and 32-bit type support with free conversions
- 256 registers (16-bit each)
- Superscalar execution capabilities

## Compiler Design Pipeline

The implementation follows this sequence: NIR translation to SSA-based intermediate representation, optimization through instruction combining, scheduling to reduce register pressure, register allocation, secondary scheduling for parallelism, and finally binary packing.

## Register File and Thread Occupancy

Analysis of Metal's `maxTotalThreadsPerThreadgroup` property revealed the register pressure tradeoff. Using empirical data, the author determined each threadgroup has approximately 208 KiB of registers. Extrapolating across 24 concurrent threadgroups yields approximately 4.875 MiB total GPU register file.

## Architectural Design Choices

Notably, the GPU lacks dedicated hardware for vertex attributes and uniform buffers common in competing designs. Instead, Metal's compiler-based approach handles these through software, allowing more space for arithmetic units while requiring careful shader specialization during pipeline creation.

The compiler currently supports OpenGL ES 2.0 operations with plans for control flow, textures, and advanced scheduling features.

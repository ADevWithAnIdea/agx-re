<!-- Source: https://alyssarosenzweig.ca/blog/opengl3-on-asahi-linux.html -->
# OpenGL 3.1 on Asahi Linux

*By Alyssa Rosenzweig*

## Overview

This post documents the implementation of OpenGL 3.1 and OpenGL ES 3.0 support for Asahi Linux graphics drivers, representing a significant upgrade from OpenGL 2.1.

## Key Features Added

The release introduces substantial new functionality:

- Multiple render targets
- Multisampling (multisampled anti-aliasing)
- Transform feedback
- Texture buffer objects

## Multisampling Implementation

### Conceptual Foundation

"Multisampling is an efficient implementation" of the supersampling anti-aliasing technique. A multisampled image stores multiple color samples per pixel, which are resolved to a single sample per pixel through averaging.

### Sample Shading Mechanism

The implementation addresses a fundamental architectural difference in Apple's AGX GPU. Unlike typical GPUs that execute fragment shaders per-sample with a hardware flag, AGX executes shaders once per pixel but allows output to different samples via bitmask instructions.

### Shader Transformation

The driver wraps fragment shaders in a loop structure:

```
for (sample = 0; sample < number of samples; ++sample) {
    sample mask = (1 << sample);
    interpolated colour = interpolate at sample(input colour, sample);
    output samples(sample mask, interpolated colour);
}
```

### Optimization Strategy

The compiler applies standard optimization passes (common subexpression elimination and code motion) to hoist sample-independent calculations outside the loop, resulting in performance matching traditional GPU implementations.

## Blending Integration

Software-based blending on AGX requires per-sample execution. The optimizer reorders transformations to place lighting calculations before the sample loop:

```
colour = calculate lighting();
alpha = colour.alpha;
inv_alpha = 1 - alpha;
colour_alpha = alpha * colour;

for (sample = 0; sample < number of samples; ++sample_id) {
    dest = load destination colour at sample (sample);
    blended = colour_alpha + (inv_alpha * dest);
    sample mask = (1 << sample);
    output samples(sample_mask, blended);
}
```

## Future Development

OpenGL ES 3.1 implementation is nearly complete, enabling compute shader support. The Vulkan driver development effort builds upon shared compiler infrastructure from these OpenGL efforts.

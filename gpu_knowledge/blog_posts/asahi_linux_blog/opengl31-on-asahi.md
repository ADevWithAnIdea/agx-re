<!-- Source: https://asahilinux.org/2023/06/opengl-3-1-on-asahi-linux/ -->
# OpenGL 3.1 on Asahi Linux

*Asahi Linux Blog — June 2023*

## Overview

The Asahi Linux project announced a significant GPU driver upgrade, advancing from OpenGL 2.1 to OpenGL 3.1, with OpenGL ES 2.0 bumping to ES 3.0.

## Key Features Added

The release includes:
- Multiple render targets
- Multisampling
- Transform feedback
- Texture buffer objects

## Multisampling Implementation

**Core Concept:** Multisampling implements anti-aliasing by rendering multiple samples per pixel, then resolving to single-sample output through averaging.

**The AGX GPU Challenge:** Unlike typical GPUs, Apple's AGX architecture executes shaders once per pixel rather than per sample. The solution involves wrapping application fragment shaders in a loop structure.

### Original Fragment Shader Pattern

```
interpolated colour = interpolate at current sample(input colour);
output current sample(interpolated colour);
```

### Transformed Pixel Shader Pattern

```
for (sample = 0; sample < number of samples; ++sample) {
    sample mask = (1 << sample);
    interpolated colour = interpolate at sample(input colour, sample);
    output samples(sample mask, interpolated colour);
}
```

## Blending with Multisampling

The driver must handle blending per-sample while optimizing fragment shader execution. Through compiler optimization (common subexpression elimination and code motion), expensive calculations are hoisted outside the per-sample loop.

**Optimized Pattern:**

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

## Future Work

The development roadmap includes OpenGL ES 3.1 and eventual Vulkan 1.0 driver support.

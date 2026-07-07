<!-- Source: https://alyssarosenzweig.ca/blog/asahi-gpu-part-6.html -->
# Clip Control on Apple GPU (Part 6)

*By Alyssa Rosenzweig*

## Overview

The article documents development of an open-source OpenGL driver (Asahi) for Apple's GPU, with focus on implementing clip space control—a critical difference between OpenGL and Metal graphics APIs.

## Key Technical Challenge

**Clip Space Discrepancy:**
- OpenGL uses depth range from -1 to 1
- Metal (and most other APIs) use depth range from 0 to 1
- This requires coordinate transformation in vertex shaders

The author notes: "implementing OpenGL on Metal requires emulating the -1/1 clip space by inserting extra instructions into the vertex shader to transform the Z coordinate."

## Reverse Engineering Approach

**Discovery Method:**
The team identified that Apple's GPU supports both clip spaces but couldn't find documentation. They discovered undocumented Metal API methods by extracting Objective-C symbols from production binaries.

Key finding: A mysterious method called `setOpenGLModeEnabled` appeared in render pipeline and render pass descriptors.

**Testing Process:**
1. Created test benches calling `[MTLRenderPipelineDescriptorInternal setOpenGLModeEnabled: YES]`
2. Compared memory traces between OpenGL mode and standard Metal mode
3. Found relevant state bits in kernel-processed render pass data

## Implementation Trade-offs

Three approaches for `ARB_clip_control` extension support:

1. **Shader Variants:** Recompile shaders for different clip spaces
   - Problem: Causes stuttering from dynamic recompilation

2. **Runtime Uniform:** Always include transformation logic
   - Problem: Constant overhead for all applications
   - Benefit: No shader variants

3. **Hardware Bit with Render Pass Splits:** Use native hardware support
   - Problem: Memory bandwidth waste if clip space changes frequently
   - Benefit: Optimal shader code

## Current Solution

The driver uses the hardware clip space bit unconditionally: "-1/1 unconditionally in OpenGL and 0/1 unconditionally in Vulkan." This approach avoids emulation overhead but prevents advertising the optional `ARB_clip_control` extension.

## Project Status

The Neverball game successfully runs on the driver, though deployment requires X11 on macOS rather than native Cocoa windowing. Future Linux support depends on parallel kernel driver development.

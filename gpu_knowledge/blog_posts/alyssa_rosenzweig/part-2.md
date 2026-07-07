# Dissecting the Apple M1 GPU, Part II

**Source URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-2.html  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 22 January 2021  
**Project:** Asahi Linux  

---

## Overview

This post documents the second major milestone: successfully rendering a triangle using entirely custom open-source code on the Apple M1 GPU. Vertex and fragment shaders were handwritten directly in machine code, and the GPU was driven via IOKit kernel interfaces.

---

## Key Achievement

The author rendered an animated triangle on the M1 GPU using:
- **Shaders:** Handwritten in M1 GPU machine code (no compiler)
- **GPU interface:** IOKit kernel driver (`IOConnectCallMethod`)
- **No proprietary components** in the rendering path

This was a critical milestone establishing that the command buffer structures were sufficiently understood to drive the GPU directly.

---

## Hardware Architecture: Command Buffer Structure

The GPU control system relies on **interconnected command buffers and descriptors** stored in shared CPU/GPU memory. Key principle: "any state accessible from Metal corresponds to bits in these buffers."

### Nested Pointer Structure

The data structures form a deep hierarchy:

```
Main Command Buffer
  └── Shader Description
        └── Internal Tables
              └── Vertex Data Buffer
                    └── (actual vertex data)
```

Each layer contains pointers to the next. The main command buffer is the root that the GPU firmware processes.

---

## Critical Discovery: GPU Memory Allocation Table

The most significant architectural finding was an **auxiliary GPU memory buffer** that tracks all active allocations.

### Structure

The allocation tracking buffer has the following layout:

- **Entry size:** 64 bytes (`0x40` bytes) per entry
- **Entry contents:** Allocation handle (GPU virtual address or handle ID)
- **Handle encoding:** 1-indexed (valid handles start at 1)
- **Sentinel value:** The final entry is always `0` (null/sentinel)
- **Header:** Contains the total entry count

### Critical Requirement

When adding a new GPU allocation, the driver must:

1. Find the sentinel entry (the `0` at the end of the table)
2. **Copy** the sentinel to a new slot (extending the table by one entry)
3. **Replace** the previous sentinel slot with the new allocation handle

This counterintuitive requirement — copying the sentinel rather than simply appending — suggests deeper architectural constraints in the GPU memory management subsystem. Simply writing a new handle without the sentinel copy caused GPU faults.

---

## Framebuffer Format

The M1 uses a **tiled framebuffer format** for memory efficiency:

- **Tile size:** 64×64 pixels
- **Tile layout:** Morton order (Z-order / space-filling curve interleaving)
- **Effect:** Pixels are not laid out linearly in memory; nearby pixels in 2D space are nearby in memory

This required software **detiling** on the CPU side to extract a linear framebuffer for display.

### Morton Order (Z-order curve)

In Morton order, the X and Y coordinate bits are interleaved to form the memory address:
```
Address = interleave_bits(x, y) * bytes_per_pixel
```

This improves cache locality for 2D operations at the cost of linear addressing.

---

## Development Methodology

### Incremental Bring-Up

Rather than attempting to construct all GPU command buffer structures simultaneously, the author used an **incremental approach**:

1. Start with a captured Metal command buffer (from interception)
2. Modify one small part of the buffer
3. Submit to GPU
4. Observe result (correct rendering vs. GPU fault vs. no output)
5. If correct, understand that bit/field; move to next
6. Repeat

This is superior to "replay" approaches (capturing and replaying full GPU command streams) because:
- Errors can be pinpointed immediately
- Each modification tests a specific hypothesis
- No need to understand everything before making progress

---

## Code Statistics

As of this milestone:
- **~1,700 lines** of new code written since the previous post
- Includes: command buffer construction, IOKit interface, software detiling, animation loop

---

## Related Work Referenced

- **GitHub Repository:** https://github.com/AsahiLinux/gpu

---

## Context

At this stage, the driver was still entirely userspace with no kernel components and no compiler. The shaders were handwritten in binary machine code. The next milestones would be:

1. Writing a shader compiler (Part III)
2. Building a proper Gallium/Mesa driver (Part IV)
3. Implementing kernel driver support

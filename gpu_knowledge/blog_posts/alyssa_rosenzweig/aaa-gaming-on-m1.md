<!-- Source: https://alyssarosenzweig.ca/blog/aaa-gaming-on-m1.html -->
# AAA Gaming on M1 (Asahi Linux)

*By Alyssa Rosenzweig*

## Core Architecture Stack

The gaming implementation bridges x86 Windows binaries to ARM Linux through a multi-layer translation system:

- **FEX**: x86 emulation on ARM architecture
- **Wine**: Windows-to-Linux API translation
- **DXVK & vkd3d-proton**: DirectX-to-Vulkan rendering pipeline conversion

## Memory Management Challenge

A critical architectural issue: "x86 expects 4K pages but Apple systems use 16K pages." The solution employs lightweight virtualization:

**muvm** runs games in isolated virtual machines with custom page sizing. This approach allows the host system to maintain 16K pages while guest environments use 4K, with GPU and controller device passthrough enabled.

## Vulkan Driver Implementation

### Tessellation Support

The M1's native tessellation hardware has insufficient capability for standard graphics APIs. The implementation substitutes "arcane compute shaders" to generate geometry dynamically.

### Geometry Shader Emulation

Hardware-absent geometry shader support also uses compute-based emulation, acknowledged as performance-suboptimal but adequate for titles like Ghostrunner.

### Robustness2 Extension

DirectX requires stronger out-of-bounds memory access guarantees than standard Vulkan. The implementation reserves 64GB of zeroed virtual memory space. For any 32-bit index multiplied by 16, this fits within the reserved region, enabling buffer address swapping with just two compare-and-select instructions rather than four.

## Performance Status

"Correctness comes first. Performance improves next." Current AAA titles don't consistently achieve 60fps; lighter titles like Hollow Knight reach full speed.

## Supported APIs

Conformant implementations for OpenGL, OpenCL 3.0, and Vulkan 1.3 on M1/M2 hardware.

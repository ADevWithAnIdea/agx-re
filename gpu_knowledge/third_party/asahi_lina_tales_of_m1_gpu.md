# Tales of the M1 GPU

**Source:** https://asahilinux.org/2022/11/tales-of-the-m1-gpu/  
**Author:** Asahi Lina  
**Published:** November 2022  
**LWN.net coverage:** https://lwn.net/Articles/916208/

---

## Summary

Written by Asahi Lina (the developer of the Rust kernel driver), this article documents the journey of implementing the M1 GPU kernel driver, focusing on the firmware architecture, memory management, and the decision to use Rust.

---

## GPU Architecture Overview

Standard GPU components are present:
- Shader cores (vertex + fragment processing)
- Rasterization units
- Texture samplers
- Render output units
- Command processor

**Key architectural divergence:** Unlike conventional GPUs, the M1 GPU operates through a unique **firmware-based architecture**.

---

## GPU Firmware Architecture

### The ASC Coprocessor
The M1 GPU has an embedded **ASC (ARM64) coprocessor** running Apple's proprietary **RTKit real-time OS**.

The firmware handles:
- Power management
- Command scheduling
- Preemption
- Fault recovery
- Performance counters
- Temperature measurement

> "All communication with the GPU happens via the firmware, using data structures in shared memory."

This is fundamentally different from most GPU architectures where the driver communicates directly with hardware registers.

### Consequences
- The driver cannot talk directly to the GPU hardware
- All work submission goes through firmware IPC
- Firmware crashes are **fatal** - require full system reboot (no restart capability)

---

## Memory Management Architecture

### Unified Address Translation (UAT)
The GPU firmware and MMU share page tables:

> "The firmware literally takes the same page table base pointer used by the GPU MMU, and configures it as its ARM64 page table."

Specifications:
- 40-bit GPU virtual addresses (sign-extended to 64 bits)
- Fixed 16K page sizes
- Up to 16 contexts with separate kernel/user address space splits
- Global page containing context page table base addresses

**Key implication:** The firmware and GPU share the same kernel virtual address space, containing firmware code, data, and communication structures with numerous interconnected pointers.

### Memory Regions
- **gpu-region-base:** Single page containing L0 UAT tables
- **gfx-shared-region-base:** Private firmware pagetables
- **gfx-handoff-base:** Synchronization region with magic values for microPPL validation
  - Includes flush state management
  - GPU VA pointers
  - Size tracking for coordinated page table updates between CPU and firmware

---

## Command Structure Complexity

The firmware manages **over 100 data structures** including:
- Initialization data (~1000 fields)
- Submission pipes
- Device control messages
- Event messages
- Command queues
- Rendering commands

### Micro Sequences
Vertex and fragment rendering commands include **microsequences** - smaller firmware-interpreted commands supporting:
- Timestamping
- Loops
- Arithmetic operations

Typical micro sequence pattern for a draw call:
```
Start (3D/TA/CP operation)
Write timestamp
Wait for idle
Write timestamp
Finish operation
```

### 3D Rendering Pipeline Requirements
Drawing a single frame requires:
- Tiler buffer management (TVB arrays, heap metadata)
- Four stamp objects for event coordination
- Separate TA (vertex) and 3D (pixel) processing stages
- Barrier synchronization between stages
- Event indexing for completion signaling (128 possible event indices)

---

## Communication Channels

**CPU → GPU channels:**
- Four work channel groups (0-3) with TA, 3D, and CP types
- DeviceControl channel for device-wide operations

**GPU → CPU channels:**
- Event notifications (work completion, fault reporting)
- Statistics messages
- Firmware syslogs
- Tracing information

All channels use bidirectional ring buffers with fixed-size messages.

---

## Hardware Registers

Status registers monitored during operation:
- `0x11008`: Work completion counter
- `0x1100c`: Status indicator
- `0x11010`: Secondary work counter
- `0x11014`: Status indicator

---

## Driver Implementation

### Development Approach
1. Python prototype driver using **m1n1** framework for rapid experimentation
2. Production kernel driver written in **Rust** (novel for Linux GPU drivers)

### Why Rust
Lina chose Rust specifically to:
- Model GPU firmware structure lifetimes using Rust's type system
- Prevent use-after-free in complex inter-object references (scheduler→fence→driver→scheduler circular dependencies)
- Use Rust macros to handle firmware ABI multi-versioning
- Provide "partial firmware-ABI safety" - make certain classes of firmware interface bugs impossible

### Key Achievement
> "Going from simple demo apps to a full desktop with multiple GPU-using apps didn't trigger the typical race conditions, memory leaks, or use-after-free issues"

Only a few logic bug fixes were required after the initial implementation - no memory safety bugs.

### Timeline
- August 18, 2022: Started writing Rust driver
- September 24, 2022: Rendered first cube
- Days later: Full GNOME desktop session running

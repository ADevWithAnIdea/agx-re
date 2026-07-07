# Apple GPU (AGX) - Asahi Linux Hardware Documentation

**Source:** https://asahilinux.org/docs/hw/soc/agx/  
**Maintained by:** Asahi Linux project

---

## Overview

AGX is a PowerVR-inspired (but largely bespoke) GPU design used in Apple M-series and A-series chips. Communication with the host OS is brokered almost exclusively via an ASC (ARM64) coprocessor running Apple firmware. All communication occurs via shared memory and a few mailbox doorbell messages.

---

## Memory Management: Unified Address Translator (UAT)

The UAT functions as the GPU's MMU, using page tables identical to ARM64.

**Specifications:**
- 40-bit GPU virtual addresses, sign-extended to 64 bits
- Fixed 16K page sizes
- Up to 16 contexts
- Separate kernel/user address space split per context
- Global page containing context page table base addresses

---

## Firmware Architecture

Initialization occurs via a single message containing a complex nested data structure with pointers to:
- Channel ring buffer controls and memory regions
- Power management and DVFS (Dynamic Voltage/Frequency Scaling) states
- MMIO mapping lists
- UAT layout information
- Colorspace conversion coefficients

The initialization structure has approximately **~1000 fields**.

---

## Communication Channels

Bidirectional ring buffers with fixed-size messages.

### CPU → GPU Channels
- Four work channel groups (groups 0-3), each with three subtypes:
  - TA (Tiler/Vertex)
  - 3D (Fragment/Render)
  - CP (Command Processor)
- DeviceControl channel for device-wide operations

### GPU → CPU Channels
- Event notifications (work completion, fault reporting)
- Statistics messages
- Firmware syslogs
- Tracing information

---

## GPU Work Submission

### Work Queue Structure
- Ring buffers containing pointers to individual work items
- Per-context management structures
- Event indexing for completion signaling: **128 possible event indices**

### Micro Sequences
Firmware-executed command sequences, typically:
```
Start (3D/TA/CP operation)
Write timestamp
Wait for idle
Write timestamp
Finish operation
```

Micro sequences support: timestamping, loops, arithmetic operations.

---

## 3D Rendering Pipeline

Drawing a frame requires coordinating:

1. **TVB (Tiled Vertex Buffer) management:**
   - TVB arrays (storage for vertex stage outputs)
   - Heap metadata for dynamic resizing

2. **Stamp objects (4 per frame)** for event coordination

3. **Two rendering stages:**
   - TA stage: vertex/tiling (runs first, processes all geometry)
   - 3D stage: fragment/rendering (runs per tile)

4. **Barrier synchronization** between TA and 3D stages

---

## Hardware Registers

Status registers polled/monitored during GPU operation:

| Register | Description |
|----------|-------------|
| 0x11008 | Work completion counter |
| 0x1100c | Status indicator |
| 0x11010 | Secondary work counter |
| 0x11014 | Status indicator |

---

## Key Memory Regions (Shared CPU-GPU)

| Region | Description |
|--------|-------------|
| gpu-region-base | Single page containing L0 UAT tables |
| gfx-shared-region-base | Private firmware pagetables |
| gfx-handoff-base | Synchronization region with magic values for microPPL validation |

The handoff region contains:
- Flush state management
- GPU VA pointers
- Size tracking for coordinated page table updates between CPU and firmware

---

## GPU Generation Naming

| GPU Name | Used In |
|----------|---------|
| G13G | M1 |
| G13X | M1 Pro, M1 Max, M1 Ultra |
| G14 | A15, some A16 |
| G16 (formerly G15) | A17 Pro, M3, M4 |

---

## PowerVR Connection

Evidence of PowerVR heritage:
- Internal Apple code still uses PowerVR term "PB" (Parameter Buffer) for what is publicly called TVB (Tiled Vertex Buffer)
- Shared architectural concepts: TBDR two-stage pipeline, partial renders, parameter buffer overflow handling
- Apple's multi-year license agreement with Imagination Technologies (announced January 2020)
- All Apple A-series SoCs support PVRTC (PowerVR Texture Compression)

The degree of actual IP derivation vs. independent development remains uncertain.

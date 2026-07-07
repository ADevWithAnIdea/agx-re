# Apple GPU (AGX) Architecture
<!-- Source: https://asahilinux.org/docs/hw/soc/agx/ -->
<!-- Also: https://leo3418.github.io/asahi-wiki-build/hwagx/ -->

## Overview

AGX is Apple's bespoke GPU architecture, heavily PowerVR-inspired but largely custom. All OS-level communication flows through an ARM64 coprocessor running Apple firmware, operating via shared memory and mailbox messages rather than direct hardware registers.

"AGX is a _heavily_ PowerVR-inspired (but largely bespoke) GPU design."

## Memory Management: UAT (Unified Address Translator)

The UAT functions as AGX's MMU, mirroring ARM64 architecture with identical page table structures.

- **Address space**: 40-bit GPU virtual addresses with sign-extension to 64 bits
- **Page size**: Fixed 16K pages
- **Context limit**: Up to 16 contexts, each with separate kernel/user address spaces
- **Coherency**: Memory appears fully coherent without explicit cache management

A global, fixed memory page stores GPU context page table bases — up to 16 contexts with dual base registers (kernel and user page tables). The kernel half is shared across all contexts; user VA space is unique per context.

**Critical architectural detail**: The firmware literally takes the same page table base pointer used by the GPU MMU, and configures it as its ARM64 TTBR0/1 registers. **GPU memory is firmware memory.** The firmware and the GPU share the same address space.

This means:
- GPU command structures cannot be safely constructed by userspace directly
- One process's GPU memory could corrupt another's, or corrupt firmware itself
- The kernel driver must own and manage all complex nested data structures
- If firmware crashes due to a bad pointer, only a full machine reboot recovers it

## Firmware Architecture

The M1 GPU has an ARM64 coprocessor called **gfx-asc** (also called the AGX ASC) running Apple's proprietary **RTKit** RTOS. All communication with the GPU goes through this firmware — the kernel driver doesn't talk to GPU hardware at all.

The firmware handles:
- Power management and DVFS
- Command scheduling and preemption
- Fault detection and recovery
- Performance counters
- Temperature monitoring

Firmware is loaded by the bootloader (iBoot) and write-protected before the OS runs.

### Initialization

Initialization requires a single complex message containing nested data structures specifying:
- Channel ring buffer control and data pointers
- Power management and DVFS states
- Shared memory regions
- MMIO mapping lists
- UAT layout information
- Color space conversion tables (1000+ fields total)

The initialization data is enormous — over 100 structures with cross-pointers to each other.

## Communication Channels

Communication occurs via fixed-size messages delivered through bidirectional ring buffers (similar to the DCP display coprocessor pattern).

**CPU→GPU Channels:**
- Four work channel groups (0-3) with three channels each:
  - TA (Tile Accelerator) — vertex/primitive processing
  - 3D — pixel/fragment processing
  - Compute (CP)
- DeviceControl — system-wide messages

**GPU→CPU Channels:**
- Event notifications (128-bit arrays indicating firing event indices)
- Fault notifications
- Statistics messages
- Firmware syslogs / crash logs

## GPU VA Address Space Layout (macOS)

- `0x015_00000000` — Primary userspace allocations
- `0x011_00000000` — Secondary userspace allocations
- `0xf80_00000000` — ASC firmware private region (RTKSTACK etc.)
- `0xfa0_00000000` — Kernel allocations and I/O regions
- `0xffffff80_00000000` / `0xffffffa0_00000000` — Sign-extended versions of above

Pointers use 40-bit addressing with sign-extension to 64 bits.

## Work Submission Pipeline

### Tiler Architecture (TBDR)

The GPU is a **Tile-Based Deferred Renderer (TBDR)**:
1. Tiler stage collects all geometry, bins it into tiles
2. Fragment shader runs per-tile, only after all geometry is processed

The tiler requires buffering all per-vertex data (varyings) in fixed-size buffers plus a dynamically-managed heap. **When the buffer overflows, the firmware triggers a "Partial Render"** — it flushes tile data, then continues from where it left off. The firmware manages this autonomously.

### Stamp Objects & Event Management

Four 32-bit stamp objects track work completion. 128 available event indices. Stamps initialize at zero and increment by 0x100 per work item. Event management uses 128-bit bitfield arrays indicating which event indices have fired.

### TA (Tile Accelerator) Work

TA work parameters:
- UAT context ID
- Event management structure pointer
- Heap manager references
- Tiler parameters and work structures
- Command encoder pointers
- Completion stamp values

### Micro Sequences

The firmware's command sequencer executes scripts packed within work items:
1. Start (TA/3D/CP)
2. Write Timestamp
3. Wait For Idle
4. Write Timestamp
5. Finish (TA/3D/CP)

### 3D Work

3D work implements a barrier that blocks until TA is done. The barrier mechanism uses stamp comparison. Partial render behavior during 3D is "unclear what black magic makes partial renders work" (from docs).

## Key Shared Memory Regions

- **gpu-region-base**: L0 UAT page tables, one entry per context
- **gfx-shared-region-base**: Firmware-allocated page tables, mapped at `0xffffffa0_00000000`
- **gfx-handoff-base**: Synchronization and cache flush state management (contains magic value `0x4b1d000000000002`, flush states, page table update coordination addresses)

## RTKit Endpoint Tasks

From firmware syslog: `rtk_ep_work, power, agx_background, agx_recovery, agx_interrupt, agx_power, agx_sampler`

## Hardware Units (Mesa naming)

- **VDM** — Vertex Dispatch Module
- **PPP** — Primitive Processing Pipeline
- **ISP** — Image Stream Processor (rasterization)
- **PBE** — Pixel Back End (output)
- **CDM** — Compute Dispatch Module
- **USC** — Unified Shader Cores

## Multi-Version Support

Apple changes firmware data structure definitions across M1 → M2 → M3 generations. Supporting multiple versions required over 100 structure field changes. The Linux driver uses Rust macros for conditional field definitions based on version numbers.

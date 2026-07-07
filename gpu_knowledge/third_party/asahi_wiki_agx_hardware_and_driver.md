# Asahi Linux Wiki: AGX Hardware and Driver Notes

**Sources:**
- HW:AGX — https://leo3418.github.io/asahi-wiki-build/hwagx/
- SW:AGX driver notes — https://leo3418.github.io/asahi-wiki-build/swagx-driver-notes/
- Also: https://github.com/AsahiLinux/docs (source repository)

---

## AGX Hardware (HW:AGX)

### Core Design
"Heavily PowerVR-inspired (but largely bespoke)" GPU. Communication brokered through ARM64 coprocessor (ASC) running Apple firmware. Full memory coherence across system. Firmware loaded by bootloader and **write-protected**.

### UAT (Unified Address Translator)

ARM64-compatible page tables:
- **40-bit GPU virtual addresses** (top bit sign-extended to 64 bits)
- **16KB fixed page size** (same as Apple Silicon host)
- Kernel/user address space split mirroring ARM64 design
- **16 GPU contexts maximum**, each with separate kernel/user page table bases
- Global fixed memory page with context page table base addresses

VA space:
- Firmware controls its own VA ranges
- Host OS manages GPU control structures in kernel address space half

### Known VA Ranges (macOS Reference)
| Range | Purpose |
|-------|---------|
| `0x015_00000000` | Primary userspace allocations |
| `0x011_00000000` | Secondary userspace allocations |
| `0xf80_00000000` | ASC firmware region |
| `0xf80_10000000` | ASC mailbox IO |
| `0xfa0_00000000` | Kernel allocations and IO regions |

### Firmware Initialization Message

Single complex nested data structure containing:
- Channel ring buffer pointers and control areas
- Power management and DVFS states
- MMIO mapping lists
- UAT layout information
- Colorspace conversion coefficients
- Various shared memory regions

### Channel Architecture

**CPU → GPU channels:**
- 4 work groups (0-3), each with 3 channels:
  - TA (vertex/tiler)
  - 3D (fragment/pixel)
  - CP (compute)
- DeviceControl channel for device-wide operations

**GPU → CPU channels:**
- Event notifications (work completion, faults)
- Statistics messages
- Firmware syslogs
- Tracing channels

### Work Submission Hierarchy

```
Work Queues
  └─ Work Items (large buffers with sub-structures)
       └─ Micro Sequences (firmware command scripts)
            └─ Stamp Objects (32-bit completion tracking, +0x100 per item)
                 └─ Event Management (0-127 event IDs per stamp increment)
```

### Typical TA Micro Sequence
```
Start
Write Timestamp (flag=1)
Wait For Idle
Write Timestamp (flag=0)
Finish
```

### 3D Rendering Sequence
1. TA (vertex) runs first
2. 3D (fragment) waits for TA via **barrier on TA's stamp #2** before executing

### Tiler Buffer (TVB) Management
Components:
- TVB tile array (tile-count dependent)
- TVB list array
- TVB heap metadata block
- Heap manager structure (dynamically-sized heap, minimum 3×128KB blocks)

**Firmware manages overflow/partial store/reload entirely.** macOS allocates in kernel; userspace control over sizing undecided for Linux.

### Status Registers

| Register | Description |
|----------|-------------|
| `0x11008` | Primary work counter (increments per completed work) |
| `0x11010` | Secondary counter (slower increment) |
| `0x4000`-`0x401c` | Version/capability registers (read once during init) |

### Security Model (microPPL)

Firmware runs "microPPL" code with full physical page access. Page table modifications require coordination through handoff region:
- Magic value: `0x4b1d000000000002`
- Flush state offset: `0x10ffffb4038` (synchronization primitive between CPU and firmware)

---

## AGX Software Driver Notes (SW:AGX)

### UAPI Architecture

Hierarchical execution model (inspired by Intel Xe):

| Component | Description |
|-----------|-------------|
| **Files** | DRM device descriptors |
| **VMs** | GPU address spaces |
| **Binds** | GEM object mappings into VMs |
| **Queues** | Logical GPU execution queues backed by firmware queues |

### GEM and Memory Management

VM-private GEM objects:
- Prevent export
- Restrict binding to specific VM
- "Allows the driver to optimize object locking"
- Enforces memory isolation

Bind ioctl:
- Theoretically supports arbitrary range binding/unbinding
- Current implementation requires whole-object binding to contiguous VM space

### Queue Model

Each user queue maintains **two logical queues**: render and compute.

Render queue maps to **two firmware queues** (vertex + fragment) with configurable barriers between them.

Commands support optional dependency specifications via boundary indices:
- "Command dependencies can be optionally added" through render/compute queue indices
- Vertex processing can "run ahead" of fragment processing when barriers permit

### Command Submission

- Jobs contain up to **64 GPU commands**
- Explicit sync via in/out sync object lists
- Jobs submit to firmware immediately upon dependency satisfaction
- "Job boundaries do NOT imply a CPU round trip" between independent submissions
- Queue serialization enforces in-order job submission

### Result Feedback

Driver writes to result buffer BOs with per-command offsets:
- Timing information
- Tiled vertex buffer statistics
- Partial render counts
- Detailed fault information for faulting operations

### Upstreaming Blockers (as of wiki writing)
- Attachment flags resolution
- Compute preemption kernel interactions
- Unknown firmware buffers

### Future Priorities
- Blit command implementation
- RTKit runtime power management
- Arbitrary VM subrange operations
- M2 Pro/Max support

### Microsequence Details

The AGX firmware command sequencer runs "scripts" (microsequences) as part of work commands. These are packed buffers of commands executed as part of work items — functioning like a custom virtual CPU inside the firmware.

Data structures documented in `BufferManager*` in `microsequence.py` (Asahi Linux project).

Normal usage pattern:
1. Set up the rendering pass parameters
2. Wait for rendering to complete
3. Clean up / emit completion events

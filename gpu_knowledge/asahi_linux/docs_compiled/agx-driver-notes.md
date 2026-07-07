# AGX Driver Notes (UAPI Design)
<!-- Source: https://asahilinux.org/docs/sw/agx-driver-notes/ -->

## Core UAPI Abstractions

- **File**: DRM device file descriptor
- **VM**: GPU address space (UAT context)
- **Bind**: Maps GEM objects into a VM at specific GPU virtual addresses
- **Queue**: Logical GPU execution queue

## GEM Objects and Memory Management

The driver supports "private" GEM objects bound exclusively to specific VMs. Current implementation requires the whole object to be bound into free VM space (future: arbitrary range binding).

## Queue Architecture

Each user queue has a parent VM. Jobs are composed of up to 64 GPU commands.

The design implements:
- Explicit synchronization via in/out sync objects
- Render and compute logical queues executing concurrently within user queues
- Render queues backed by vertex and fragment firmware queues with permeable barriers
- Optional per-command dependencies using boundary indices

**Key insight**: vertex processing can "run ahead" of fragment processing absent explicit barriers — the firmware's barrier mechanism handles synchronization.

## Result Buffers

Userspace can request execution feedback:
- Timing information (timestamps)
- Tiled vertex buffer statistics
- Partial render counts (for render commands)
- Fault diagnostics (for faulting commands)

## Outstanding Upstreaming Blockers (as of documentation)

- Attachment flags clarification
- Compute preemption implementation
- Unknown buffer identification
- Future: arbitrary VM subrange operations
- Future: performance counters
- Future: M2 Pro/Max support

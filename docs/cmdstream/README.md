# A18 Pro (G17P) Command Submission & Control Stream

Clean-room documentation of how userspace hands GPU work to the kernel, and the control-stream
structures it builds. Learned by **black-box data tracing** (DATA-TRACE) of our *own* Metal
programs via a DYLD IOKit interposer (`tools/iotrace/`) — command buffers/descriptors are
non-copyrightable hardware data. No Apple binary was disassembled. See `../../CLAUDE.md`.

> **Status: foundation established (EXP-0009).** The submission *mechanism* and the userspace↔kernel
> IOKit interface are mapped; the individual control-stream structures are located and partially
> correlated, with full bit-level decode deferred to follow-up cmdstream experiments.

## Submission model — shared-memory + doorbell (NOT per-call ioctl)
Modern macOS 26 Metal does **not** issue one ioctl per submit (unlike the M1-era 2021
`SUBMIT_COMMAND_BUFFERS` selector). Evidence: the IOKit call count is **invariant** under the
number of submits (compute: 49 calls whether 1/3/5 submits; draw: 58), while each submit
demonstrably ran (correct output each time). Work is encoded into ordinary userspace VM buffers
that are registered into the GPU address space; submission is via a shared-memory ring + doorbell
(ring BO + doorbell write proven to exist, exact location pending — see Open items).

## Userspace↔kernel IOKit interface (G17P)
Userspace opens two user clients: **`IOSurfaceRoot`** and **`AGXAcceleratorG17P`**. All GPU work is
`IOConnectCall*` on the AGX connection. Selectors identified:

| selector | role | notable payload |
|---|---|---|
| `0x8` | create queue | — |
| `0x7` | one-time setup (1040-byte struct in) | candidate for ring/doorbell setup |
| **`9`** | **map resource (register BO into GPU VM)** | in@0x38 = CPU base, in@0x48 = size, **out@0x00 = GPU VA** (HW-confirmed: returned `0x10000030000` = our buffer's `gpuAddress`) |
| `0x11` | completion/notify queue | candidate for doorbell/notify |

A compute dispatch makes ~30 sel-9 maps; a draw ~39 plus a second IOSurface map. No graphics-specific
"submit" selector exists — draw uses the same shape as compute.

## Control-stream structures located (correlated to our own resources)
Captured by snapshotting every registered BO after `waitUntilCompleted` (`tools/iotrace/dumpscan.py`):

- **Argument buffer** (`gpu_va 0x100000e0000`): our three buffer GPU-VAs stored consecutively
  (at +0x14a0) — exact HW match. This is how bound buffers are referenced (Tier-2 argument buffers).
- **Launch/dispatch descriptor** (`gpu_va 0x100000b0000`): grid size `0x40`=64 at +0x10, threadgroup
  `0x20`=32 at +0x1c — our exact dispatch dimensions.
- **Shader-code BO** (`gpu_va 0x10000090000`): the AGX instruction stream (op-groups `09`/`0b`/`67`/`9f`,
  ending in `0e`), i.e. our compiled kernel — identified by structure + location (byte-level match to a
  `shdump` extraction pending).

## Open items (next cmdstream experiments)
- Pinpoint the ring BO + doorbell write (interpose 32-bit `IOConnectMapMemory` /
  `mach_make_memory_entry_64` / `vm_map`; parse the sel-`0x7` and sel-`0x11` structs).
- Byte-validate the shader BO against a `shdump` extraction.
- Change-one-Metal-parameter diffs to decode the launch descriptor, argument buffer, and (for draw)
  the VDM/tiler/fragment control words and pipeline/state packets.

Source: `experiments/EXP-0009-iotrace-bringup/`. Tool: `tools/iotrace/`.

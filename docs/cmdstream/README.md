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

## ✅ Compute launch (CDM) descriptor — decoded (EXP-0011)
BO `gpu_va 0x100000b0000` is a stream of **0x2c-byte records** (one per dispatch) + a
`0x40000000` terminator. Per-record fields (grid/tg HW-validated by single-word diffs):

| offset | field | notes |
|---|---|---|
| `+0x00` | shader config/register word | e.g. `0x00080000`→`0x00880000` for a register-heavy shader ⏳ |
| `+0x08` | **shader-code pointer = shaderVA >> 6** | 64-byte units. HW-confirmed: shaders at 0x90000/0x90100 → `0x2400`/`0x2404` (Δ=4) |
| `+0x10/+0x14/+0x18` | grid x / y / z | **in threads**, not threadgroups (`dispatchThreadgroups(2)×32` ≡ `dispatchThreads(64)`) |
| `+0x1c/+0x20/+0x24` | threadgroup x / y / z | |

The arg-buffer pointer is **not** in this record — binding flows via the argument buffer, whose VA
lives in the uniform/USC BO (`0x10000000000`). ⏳ threadgroup-memory-size field is elsewhere (not here).

## ✅ Argument buffer (Tier-2) — decoded (EXP-0011)
BO `gpu_va 0x100000e0000`, resource table at **+0x14a0**, **8 bytes/slot** in binding order:
- **buffers** = inline 8-byte GPU VA (HW-validated for 1/2/4/8 buffers).
- **textures / samplers** = 8-byte pointer to a descriptor block appended in the same BO. Raw 32-byte
  texture descriptor + sampler descriptor captured for `../descriptors/` (Phase 3 seed).

## Shader BO (EXP-0011)
Captured code BO = `[main][14-byte constant-program stub 03 00 07 00 02 00 00 00 60 00 0e 00 00 00]`,
ending in `0e` stop; no header. Structurally validated against `shdump` (the stub matches
`_agc.main.constant_program`'s head). Note a **codegen difference between API paths**:
`newComputePipelineStateWithFunction:` inlines the arg-load preamble into main (~182 B) while the
binary-archive `_agc.main` that `shdump` extracts is lean (~56 B) — same semantics, different framing.

## Submission ring / doorbell (partial, EXP-0011)
No per-submit mapping syscalls (confirms ring+doorbell). The ring lives in shared memory
(~`gpu_va 0x10000050000`): a **producer index increments by 0x58 bytes/submit** with fixed-size
completion records at the same cadence. The exact CPU→GPU doorbell store is **not** an IOKit/mach-vm
call — likely a store into a firmware-shared page + barrier (invisible to this interposer). sel `0x7`'s
1040-byte struct was reclassified: it is the **executable-path string**, not ring config.

## Open items (next cmdstream experiments)
- Decode the `+0x00` config/register word and remaining launch-record constants; find the
  threadgroup-memory-size field.
- **Graphics/draw command stream** — the big follow-up: VDM / tiler / fragment control words, pipeline
  & fixed-function state packets (via `iohello_draw`).
- Texture/sampler descriptor bit layouts → `../descriptors/`.

Source: `experiments/EXP-0009-iotrace-bringup/`. Tool: `tools/iotrace/`.

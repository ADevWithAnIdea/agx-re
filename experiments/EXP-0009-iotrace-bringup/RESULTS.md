# EXP-0009 Results — submission model + first cmdstream correlation

**TL;DR.** On A18 Pro / G17P / macOS 26.6, GPU work is **submitted through shared
GPU memory + a doorbell, not through a per-submit `IOConnectCallMethod`.** The
whole userspace↔kernel IOKit conversation for a compute dispatch is 49 calls and
for a triangle draw 58 calls, and **that count does not change when the program
submits 1, 3 or 5 command buffers.** The command / control stream is encoded into
ordinary userspace memory that Metal registers into the GPU virtual address space
via one `AGXAcceleratorG17P` selector (9); we located our own shader, argument
buffer and dispatch dimensions inside those buffers. This resolves the ROADMAP
"modern submission path" open question and confirms Phase 2 must decode
**shared-memory command streams**, not per-call ioctl payloads.

All findings below are **DATA-TRACE**: observed bytes crossing the boundary from
our own Metal process. Nothing was learned from Apple code.

---

## 1. Submission mechanism — shared memory + doorbell (per-submit ioctl: NO)

**Decisive evidence — call count is invariant under submit count.** Same process,
same buffers/pipeline, looping `commit` + `waitUntilCompleted`; every submit really
ran on the GPU (`status=4` completed, correct results each iteration):

| program | 1 submit | 3 submits | 5 submits |
|---|---|---|---|
| `iohello_compute` | 49 IOKit calls | **49** | **49** |
| `iohello_draw`    | 58 IOKit calls | **58** | **58** |

(`raw/cmp_iter{1,3,5}.log`, `raw/d{1,3,5}.log`.) If submission were a per-command-
buffer `IOConnectCall*` — as it was on M1 in 2021 (`SUBMIT_COMMAND_BUFFERS=0x1E`,
40-byte struct, once per submit) — the count would grow with the submit count. It
does not move at all. Therefore the per-submit work is a **memory write to a shared
ring + a doorbell**, with completion delivered out-of-band (a notification/data
queue set up once; sel 0x11).

Corroborating: there is **no `SUBMIT_COMMAND_BUFFERS`-shaped call** anywhere in the
trace (no call carries a large per-submit command-buffer struct), and
**`IOConnectMapMemory64` is never called** — client GPU memory is not obtained as
mapped IOKit rings but as regular userspace VM (see §3).

## 2. The IOKit call sequence

Two user clients are opened: `IOSurfaceRoot` and **`AGXAcceleratorG17P`** (the GPU
user client; consistent with EXP-0002). All GPU traffic is `IOConnectCall*` on the
AGX connection. Selector histogram (compute, `raw/compute_trace2.log`):

```
sel 0x0 ×1   0x2 ×1   0x5 ×1   0x6 ×1   0x7 ×1   0x8 ×1   0x9 ×30
0xd ×1   0xe ×2   0xf ×2   0x10 ×1  0x11 ×1  0x1c ×1  0x20 ×1
0x100 ×1 0x102 ×1 0x105 ×1   (0xd/0x20/0x2c on the IOSurface connection)
```

Annotated compute sequence (selector → what the DATA shows; **bold = correlated to
our own resources / high confidence**, others are structural/opaque):

| selector | fn / shape | what the payload shows |
|---|---|---|
| `0x2` | Struct, out 536 | device/global capability table (returned once) |
| `0x0` | Struct, out 64 | device info block |
| `0x5` | Struct, out 32 | returns two 64-bit addresses (a handle + a CPU mapping) |
| `0x102`,`0x100` | Struct | driver version strings ("`Jun  9 2026 22:54:08`", "`release`") |
| **`0x9`** | **Method, in 104 / out 88, ×30** | **resource-map: register a userspace BO into the GPU VM.** in@0x38 = CPU base, in@0x48 = size, **out@0x00 = GPU VA**. Confirmed: a call returned `0x10000030000` = our `bufA`'s `gpuAddress`. |
| `0x105` | Struct, in 72 | per-resource setup (once, early) |
| `0x7` | Method, in 1040 | large one-time setup struct (candidate ring/queue config) |
| `0x10` | Method, in `[0x100,0x28]` | scalar setup |
| `0x1c` | Method, in `[0x1,0x1]` | scalar setup |
| `0xe` | Method, in `[0x4000,0x0]`,`[0x4000,0x1]` | two calls, arg `0x4000` (16 KiB) — region/segment setup |
| `0x8` | Method, in `[0x1]` | **create command queue** |
| `0x11` | Method, in `[0x1]` | **create notification/completion queue** (out-of-band completion path) |
| `0xf` | Scalar, in `[0x2]`,`[0x1]` | small scalar calls near queue creation |

Draw (`raw/draw_trace.log`) is the **same shape** with more resources: 39× sel 9
(vs 30 — the extra BOs are the vertex+fragment shaders, tiler/fragment control
buffers, and the render target) and a second `IOSurface` map for the color target.
Notably, **no new "submit" selector appears for graphics** — draw uses the same
shared-memory + doorbell path as compute.

> Selector *numbers* partially overlap the 2021 M1 table (0x6, 0x8, 0x11) but
> **semantics have shifted** (e.g. 0x9 was `FREE_COMMAND_QUEUE` on M1; here it is the
> resource-map). We map selectors only where the DATA supports it and mark the rest
> opaque — no selector meaning is taken from Apple's headers/code.

## 3. Where the command/control stream lives, and how we captured it

There are **no `IOConnectMapMemory` ring regions** in the client. Instead, client
GPU memory is **ordinary userspace VM registered into the GPU VM** by selector 9,
which returns a GPU VA. The command/control stream is encoded into those BOs by
userspace, then submitted by doorbell (§1). So to capture it we snapshot the BOs.

**Capture method.** The interposer records every BO `(CPU addr, size, GPU VA)` from
selector 9. Because there is no per-submit ioctl to hook, the harness fires
`kill(getpid(), SIGUSR1)` immediately after `waitUntilCompleted`; the interposer
services it on a dedicated `sigwait` thread and `mach_vm_read_overwrite`s each BO's
CPU bytes to a `.hex` file (crash-safe: a torn-down region reads empty, never
faults). We then grep the dumps for our own resource VAs (`dumpscan.py`).

**Correlations found** (compute; our buffers were `bufA=0x10000030000`,
`bufB=0x10000030100`, `bufOut=0x10000030200`, grid=64, threadgroup=32):

1. **Argument buffer** — BO `gpu_va=0x100000e0000`. At offset **0x14a0** our three
   buffer VAs sit consecutively and nowhere else:
   ```
   000014a0: 00000300 00010000  00010300 00010000     ; bufA, bufB
   000014b0: 00020300 00010000  00000000 00000000      ; bufOut
   ```
   This is Metal's bindless argument buffer for the kernel's `[[buffer(0/1/2)]]`.
   **HW-correlated** (exact `gpuAddress` match, `dumpscan.py --u64`).

2. **Launch / dispatch descriptor** — BO `gpu_va=0x100000b0000`, first 0x30 bytes:
   ```
   00000000: 00000800 00000001  00240000 01000040
   00000010: 40000000 01000000  01000000 20000000     ; grid=(64,1,1)  @0x10
   00000020: 01000000 01000000  60010060 00000040     ; localsize.x=32 @0x1c
   ```
   `0x40`=64 (our total grid) at 0x10 and `0x20`=32 (our threadgroup size) at 0x1c;
   the same grid `0x40` also appears in control BO `0x10000080000` @0xa8.
   **HW-correlated** to our exact dispatch dimensions.

3. **Shader machine code** — BO `gpu_va=0x10000090000` holds an AGX instruction
   stream: the op-group bytes we already documented (`0x09`/`0x0b` float-ALU,
   `0x67` load/store, `0x9f` integer-ALU, `0x12` fmin/max) and it **terminates in
   the `0x0e` stop instruction**:
   ```
   ...  2c 09 44 5b 2e 09 04 0b 24 09 04 1b 26 09 04 2b   ; repeated 09 04 xb float-ALU
   ...  09 04 03 00 07 00 02 00 00 00 60 00 0e 00 00 00   ; 0e = stop
   ```
   This is our compute kernel's compiled code loaded into GPU memory. Identified by
   **structure + location** (only user compute kernel in the process). *Not*
   byte-identical to a standalone `shdump` build of the same source — expected,
   because `iohello` builds via `newComputePipelineStateWithFunction:` while
   `shdump` builds via a descriptor + binary archive with fast-math; register
   allocation and the prologue differ. Exact-VA confirmation by byte-diff is a
   Phase-2 follow-up (both are unmistakably AGX code ending in `0e` stop).

The other dense BOs are: a heap holding our buffer *data* (many overlapping 128 KiB
aliases of the same region — that is why selector 9 returns the same base VA
repeatedly, i.e. Metal sub-allocates buffers from a shared heap), a large
uniform/USC BO (`0x10000000000`), and, in the draw, a near-full 0x74000 tiler/
framebuffer BO and additional low-VA (`0x18000`…`0x68000`) firmware-shared regions.

## 4. Obstacles, reliability, recommended next

**Obstacles / honestly-still-opaque.**
- We proved submission is ring+doorbell but have **not yet pinpointed the ring BO
  or the doorbell write**. The ring is *not* an `IOConnectMapMemory64` region and is
  likely established by the one-time sel-0x7 (1040-byte) setup or the notification
  queue (sel 0x11), then written by a plain memory store. Finding it needs the
  follow-ups below.
- Selector semantics beyond sel 9 (and the queue/notify creators) are structural
  guesses; marked opaque.
- The shader-code VA is identified by structure, not yet byte-validated.

**Reliability.** The harness re-captures deterministically: 5 independent runs gave
identical call counts and the same correlations; the crash-safe `mach_vm_read`
dump never faulted; **zero GPU wedges / reboots**. Injection works with no AMFI
change (unsigned harness). The SIGUSR1-after-`waitUntilCompleted` trigger reliably
snapshots BOs while they are still mapped.

**Recommended next (Phase 2 cmdstream decode plan).**
1. **Find the doorbell/ring.** Add interposes for 32-bit `IOConnectMapMemory`,
   `mach_make_memory_entry_64` and `vm_map`; parse the sel-0x11 notification-queue
   and sel-0x7 setup structs. Diff shared memory across submits to catch the
   per-submit ring write.
2. **Decode the CDM launch descriptor** (BO `…b0000`) and **argument buffer** (BO
   `…e0000`) by change-one-parameter diffing: vary grid/threadgroup, buffer count
   and binding index; watch which bytes move. Compare against the public M1
   `cmdbuf.xml` *shapes* (CDM `Launch`, `Bind uniform`) but rebuild the A18 layout
   from our own diffs.
3. **Confirm the shader VA** by byte-diffing BO `…90000` against a `shdump`
   extraction of the same kernel; document any loader fixups.
4. **Repeat for graphics** (VDM/tiler/fragment split) using `iohello_draw`, which
   already captures the richer draw BO set.

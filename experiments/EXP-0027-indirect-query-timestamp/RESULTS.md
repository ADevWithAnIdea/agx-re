# EXP-0027 Results — indirect commands, occlusion queries, GPU timestamps, MSAA

**TL;DR.** On A18 Pro / G17P / macOS 26.6, change-one-Metal-parameter byte-diffing of the
registered GPU BOs (all four clusters, `iotrace` read-only) decodes:

1. **Indirect draw (args-in-buffer)** — the VDM draw opcode changes (`0x61c4→0x6404`
   non-indexed, `0x61f2→0x6432` indexed) and the inline vertex/instance counts are replaced
   by an **8-byte pointer to the indirect-args buffer** (VA low32 HW-correlated to our
   `argBuf`). The GPU reads the standard `MTLDraw[Indexed]PrimitivesIndirectArguments` struct
   at execute time. **Indirect dispatch** injects a **second CDM record + auxiliary
   "grid-setup" shader** (because the CDM grid is in *threads* but the args are *threadgroups*),
   with the args-buffer pointer staged in control BO `0x10000080000+0xb0`. A **full ICB**
   (`executeCommandsInBuffer:`) expands each command into an inline state-block+draw in the
   tiler stream; header word `+0x04` = command count.
2. **Occlusion query** — visibility-result-buffer base pointer at BO `0x10000100000+0x00`;
   per-draw **mode** = bit14 of `0x58000+0x8c` (Boolean=1, Counting=0); per-draw **offset** =
   `0x58000+0xa0 = byteOffset<<14`. Counting writes the **exact passed-sample count**
   (4096 = 64×64), Boolean writes 1 — both 64-bit.
3. **GPU timestamps** — format is **uint64 nanoseconds, period 1.0**; **only stage-boundary
   sampling is supported** (dispatch/draw boundary = **unsupported**). Timestamps land in the
   sample-buffer BO as consecutive uint64 (8-byte stride).
4. **MSAA (stretch)** — HW maintains N independent samples with 1:1 sample-id ordering;
   resolve = arithmetic average; physical interleave is on-chip tile / firmware-side.

All findings are **DATA-TRACE** (bytes our own Metal handed the kernel) unless marked
HW-PROBE. Nothing was learned from Apple code; Metal-generated helper shaders were located,
not disassembled. **Zero GPU wedges / reboots.** Noise floor 0 (draw determinism clean; the
`gpu_va=0x0` sel-5 pseudo-BO pairing artifact is excluded everywhere, as in EXP-0014/-0019).

---

## 1. Indirect (device-generated) commands

VDM (`0x18000`) draw-command layout (LE): primitive-type byte at `+0x65`, **opcode LE16 at
`+0x66/+0x67`** (`docs/cmdstream` convention).

### 1a. Draw with args in a buffer — `drawPrimitives:indirectBuffer:` (HW-correlated)
| case | opcode | inline payload |
|---|---|---|
| direct non-indexed | `0x61c4` | `+0x68` vtxCount, `+0x6c` instCount, `+0x74` term `0xc0000000` |
| **indirect non-indexed** | **`0x6404`** | `+0x68` = argBuf VA **high32** (`0x100`), `+0x6c` = argBuf VA **low32** (`0x1c600`), `+0x70` term |
| direct indexed | `0x61f2` | `+0x64` `0x40000001`, `+0x68` `0xffff` (idx type/restart), `+0x70` idxVA low, `+0x74` indexCount, `+0x78` instCount |
| **indirect indexed** | **`0x6432`** | preamble as direct; `+0x70` idxVA low (inline), `+0x74` = argBuf VA high32, `+0x78` = argBuf VA low32 |

Evidence (`raw/ivar/hex/`, `raw/ivar/ana/diff_draw_indirect*.txt`): non-indexed argBuf VA
`0x1000001c600` → `+0x6c`=`0x1c600`; indexed argBuf VA `0x1000001c700` → `+0x78`=`0x1c700`
(two distinct values, both track = clean HW correlation of the args-pointer low32). The
count fields are gone from the VDM: the GPU reads them from the buffer at execute time. The
struct the GPU consumes is the public `MTLDrawPrimitivesIndirectArguments`
`{vertexCount,instanceCount,vertexStart,baseInstance}` (indexed:
`{indexCount,instanceCount,indexStart,baseVertex,baseInstance}`) — the draw rendered
correctly with the count supplied only in the buffer.

**Args-pointer encoding note:** the inline VDM indirect-args pointer is stored **high32
then low32** (`+0x68`=`0x100`, `+0x6c`=`0x1c600`) — the reverse of a normal LE u64. High32 is
the fixed heap-region selector `0x100` (inferred); low32 is HW-correlated. (The ICB, §1c,
uses normal LE u64 instead.)

### 1b. Dispatch with args in a buffer — `dispatchThreadgroupsWithIndirectBuffer:` (HW-validated)
The CDM (`0x100000b0000`) direct record is the EXP-0011 `0x2c`-byte record (grid in *threads*
`+0x10`=64, tg `+0x1c`=32, terminator `0x40000000` @ `+0x2c`). **Indirect** replaces the
terminator with a **second record** (`raw/ivar/hex/disp_indirect_va100000b0000.hex`):
`+0x2c`=`0x10080000` (2nd record config), `+0x34`=`0x00002404` (**aux shader** @ `0x90100`
= VA>>6), `+0x40`=`0x000e14c0` (ptr into arg-buffer `0x100000e0000+0x14c0`). The indirect-args
buffer VA (`0x1000001c900`) is staged in **control BO `0x10000080000+0xb0`** (dumpscan match).

**Why:** the CDM grid is in *threads* (EXP-0011) but `MTLDispatchThreadgroupsIndirectArguments`
gives *threadgroups*, so a `threadgroups × threadsPerThreadgroup` conversion is required.
Metal injects an auxiliary "grid-setup" compute record that reads the args buffer and patches
the real dispatch's thread-count grid. `threadsPerThreadgroup` stays inline (`+0x1c`=32; it is
**not** indirect). The aux shader is Metal-generated (located, **not** disassembled). A Mesa
driver must replicate this multiply (its own prepare-shader, or a native firmware
indirect-threadgroup path if one exists) — **kernel-interface / driver item.**

### 1c. Full `MTLIndirectCommandBuffer` — `executeCommandsInBuffer:` (HW-validated)
`executeCommandsInBuffer:withRange:` expands each ICB command into an inline
**state-block + draw-primitive** in the tiler stream (`0x18xxx`): the draw uses the **same
`0x61c4` opcode + inline vertexCount** as a direct draw (`+0x1ac`/`+0x1b0` for cmd0). The
**header word `+0x04` = command count** (icbn 1→1, 2→2; HW-clean, `diff_icb_draw_n2.txt`); a
2nd command adds a second draw block (`op 0x61c4`, count, inst) at ~`0x3c` stride. Per-command
bound resources live in the ICB storage region as **normal LE u64** (vtxBuf VA `0x1000001c500`
at `+0x400`: `+0x400`=`0x1c500`, `+0x404`=`0x100`).

**Distinction (as the brief asks):** the *classic* `indirectBuffer` draw carries an opcode +
pointer to a 16/20-byte args struct read at execute; the *full ICB* carries fully **encoded**
commands (opcode + bindings + inline args) that the GPU walks — device-generatable.

---

## 2. Occlusion / visibility queries (HW-validated)

Readback (`qvar`, `raw/qvar/OCCLUSION_FINDINGS.txt`): Boolean → `visBuf[0]`=1; Counting →
`0x1000`=**4096** = 64×64 samples that passed (full-screen triangle, 1 sample/px); two-draw
(count@off0 + count@off8) → `visBuf[0]`=`visBuf[1]`=4096. 64-bit writes (poison
`0xdeadbeef00000000`→`0x00000000000010 00`).

| field | location | evidence |
|---|---|---|
| **visibility-result-buffer base ptr** | BO `0x10000100000 +0x00` = LE u64 visBuf VA | `+0x00`=`0x18800` (visBuf low), `+0x04`=`0x100` (high); visBuf VA=`0x10000018800` (HW-correlated) |
| **per-draw mode** (Boolean vs Counting) | `0x58000 +0x8c` **bit14 (0x4000)** | bool `0x0004c200` / count `0x00048200` (single-bit diff) |
| **per-draw counter offset** | `0x58000 +0xa0` = **byteOffset << 14** | off0→0, off8→`0x20000`, off16→`0x40000` (also mirrored in tiler visibility-ctx `0x10000258000+0x00`) |
| **counter write destination** | our `visBuf` | Counting `+0x00` `1→0x1000`; upper 32 bits of poison cleared ⇒ 64-bit write |

**Counter semantics:** Counting accumulates the exact number of samples passing depth/stencil
per draw into `visBuf[offset]` (64-bit); Boolean writes 1 if any passed. The per-tile → total
summation across the 32×32 tiles is **HW/firmware-managed** — no userspace field (INFERRED).
setVisibilityResultMode is per-draw (two draws → two offsets, each written).

---

## 3. GPU timestamps (HW-validated)

Counter sets: exactly one — name `timestamp`, one counter `GPUTimestamp`.

- **Format / period.** `[dev sampleTimestamps:cpu gpuTimestamp:gpu]` returns **cpu == gpu**
  every call (e.g. `28808777089583 == 28808777089583`); over a 50 ms nanosleep dCPU == dGPU
  ⇒ **`gpu_ticks_per_cpu_ns` = 1.000000**. The counter-sample-buffer `TS[]` values fall in the
  **same nanosecond clock** (pre-commit `sampleTimestamps` `28811037764958`; `TS[0]`
  `28811050096416`, ~12 ms submission latency later). Stage deltas physically sane for a 64×64
  triangle (vertex 10.8 µs, whole 34 µs). ⇒ **GPU timestamp = uint64 nanoseconds,
  timestampPeriod = 1.0 ns/tick.**
- **Supported sampling points** (`supportsCounterSampling:`): dispatchBoundary=**0**,
  drawBoundary=**0**, stageBoundary=**1**. ⇒ timestamps are available **only at render-pass
  stage boundaries** (vertex/fragment start/end via `sampleBufferAttachments`); a compute
  dispatch-boundary sample resolved all-zero. **KEY CAPABILITY FLAG:** compute/blit/per-draw
  timestamp queries (Vulkan `vkCmdWriteTimestamp` in compute, `VK_QUERY_TYPE_TIMESTAMP`) must
  be emulated by a Mesa/Vulkan driver.
- **Sample-buffer layout.** Resolved `TS[0..3]` appear **verbatim** in the sample-buffer BO
  (`0x10000080000` this run) at `+0x00,+0x08,+0x10,+0x18` — an array of uint64 ns, 8-byte
  stride, one per sample index (startVtx, endVtx, startFrag, endFrag). (`raw/tvar/hex/`.)
- **Command-stream encoding.** Enabling stage-boundary sampling grows two state-size words by
  `+0x200`: VDM `0x18000+0x0c` (`0x4800→0x4a00`) and FF-pool `0x58000+0x14` (`0x4c19→0x4e19`).
  The **sample-buffer base address is NOT present** as a plain or `>>6`/low32 pointer in any
  client-registered BO ⇒ the sample-buffer address handoff is **firmware/kernel-managed**
  (kernel-interface item, like the doorbell / sample positions / ZLS). The per-index write is
  emitted by the tiler/3D firmware at each stage boundary.

---

## 4. MSAA sample interleave (stretch, HW-PROBE)

`mvar`: fragment writes `sample_id/255`; `StoreAndMultisampleResolve`; a 2nd compute pass reads
each sample via `texture2d_ms.read(uint2(4,4), s)`.
- **samples=2** → resolve r=1 (avg{0,1}); per-sample s0=0, s1=1.
- **samples=4** → resolve r=2 (avg{0,1,2,3}=1.5→2); per-sample s0=0,s1=1,s2=2,s3=3.

⇒ HW maintains **N independent samples**, each independently written per `sample_id` and
**independently addressable** via `read(coord, sample)`; **sample ordering is 1:1** (value
shaded at `sample_id==s` reads at slot s, no permutation); **resolve = arithmetic average**.
The per-sample data lives in on-chip tile/imageblock SRAM during the pass and in the (private,
tiled) MSAA texture after Store — **not** a client linear BO, so the physical byte interleave
is not byte-diffable here. Under 4× MSAA the color attachment descriptor **relocates** out of
`0x10000110000` into the tiler heap (BO-set restructures m1 vs m4), corroborating EXP-0021,
which owns the sample-count field (`+0x24`) and tile budget.

---

## 5. Userspace-emitted vs firmware/kernel-managed

**Userspace-emitted (a driver must build these):** indirect draw opcode + args pointer (§1a);
the indexed-indirect index-ptr + args-ptr (§1a); the ICB encoded command stream + count word
(§1c); the visibility-buffer base pointer + per-draw mode bit + offset field (§2); the two
state-size words that flag timestamp sampling (§3).

**Firmware / kernel-managed (flag for the kernel team, `docs/kernel-interface.md`):**
- indirect **compute** grid-setup: the aux "grid-setup" dispatch is Metal-injected; a driver
  needs its own threadgroups→threads prepare step (or a native firmware indirect path). §1b.
- occlusion per-tile → total **sample-count summation** (no userspace knob). §2.
- the counter/timestamp **sample-buffer address handoff** (not in any client BO). §3.
- MSAA physical sample interleave lives in on-chip tile SRAM / tiled texture (firmware/HW). §4.

## 6. HW-validated vs inferred
**HW-validated (diff-confirmed or probe-confirmed):** indirect draw opcodes `0x6404`/`0x6432`
+ args-pointer low32 (correlated to two distinct argBuf VAs); indirect-dispatch 2nd
record/aux-shader + args staging BO; ICB command-count word + inline draw expansion + inline
resource ptr; visibility base ptr, mode bit14, offset<<14, and the 4096/1 counter writes;
timestamp ns format+period, supported sampling points, sample-buffer uint64 stride; MSAA N
independent samples + ordering + resolve average.
**Inferred:** the indirect-args-pointer high32 = fixed heap selector `0x100`; the exact
internal fields of the injected grid-setup record; per-tile occlusion summation mechanics;
that the sample-buffer address is firmware-side (negative search, not a positive locate).

## 7. Follow-ups
1. Confirm the indirect-args-pointer high32 by forcing a differently-based argBuf VA.
2. Decode the injected grid-setup record's remaining fields (grid.x placeholder `0x60` at
   `+0x10`; the `0x10080000` config vs normal `0x00080000`).
3. Pin the ICB per-command state-block grammar (the `0x18400+` storage region) and the
   main-stream execute-ICB reference opcode.
4. Kernel-side: sample-buffer address channel; occlusion summation; MSAA tile interleave.
5. Bit-decode the remaining `0x58000` visibility sub-block fields (the block inserted at
   none→bool restructures `0x58000`/VDM heavily).

## Established facts → docs
- §1 indirect draw/dispatch opcodes + args-pointer offsets + ICB framing → `docs/cmdstream/`.
- §2 occlusion base-ptr / mode / offset fields + counter semantics → `docs/cmdstream/`.
- §3 timestamp format/period + sampling-point support + sample-buffer stride → `docs/pipeline/`.
- §4 MSAA per-sample facts → `docs/pipeline/` (extends EXP-0021).
- §5 firmware/kernel bits → `docs/kernel-interface.md`. §3 dispatch/draw-boundary timestamp
  gap + firmware bits → `docs/hypotheses.md`. Orchestrator merges + adds `PROVENANCE.md` rows
  (DATA-TRACE/HW-PROBE, EXP-0027).

## Deliverables
`ivar.m`/`run_ivar.sh`, `qvar.m`/`run_qvar.sh`, `tvar.m`/`run_tvar.sh`, `mvar.m`; `raw/`
(per-cluster `*_FINDINGS.txt`, `ana*/` diffs+lists, curated control-BO `hex/`). Text only.

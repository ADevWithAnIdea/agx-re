# RT-6 RESULTS — falsification of indirect / query / timestamp / geometry-output cmdstream

Device: A18 Pro / G17P, macOS 26.6 (25G5043d). All captures `status=4`; zero faults/reboots.
Method: change-one-Metal-parameter byte-diff of registered GPU BOs under read-only `iotrace`
(arm64e). Raw dumps: `raw/RAW_EVIDENCE.txt` (+ `raw/hex/curated_regions.txt`). Hex is bytes in
address order; `le32` = the little-endian u32.

## TL;DR — verdicts
| # | Claim group | Verdict |
|---|---|---|
| 1 | Indirect draw/dispatch opcodes + args-pointer offsets + indirect-dispatch 2nd-record | **CONFIRMED** (incl. RT-2a cross-check: the shift DOES apply to indirect-indexed) |
| 2 | Full ICB command-count + inline draw + mesh-in-ICB 0x70000600 | **CONFIRMED** (+ mixed draw/mesh ICB accepted; +0x04 = *encoded* count) |
| 3 | Occlusion result-ptr / mode bit14 / offset<<14 | **CONFIRMED exactly** (incl. large offset 4096) |
| 4 | Timestamp u64 ns / period 1.0 / stage-boundary-only | **CONFIRMED** (dispatch-boundary = unsupported, all-zero) |
| 5 | Geometry-output viewport array / clip mask / point_size / vpidx / restart cut | **CONFIRMED exactly** (16 vp, 8 clip, restart strips u16+u32) |

**No discrepancies found.** Finding nothing strengthens the docs.

---

## Claim 1 — Indirect draw/dispatch — CONFIRMED

### 1a. Non-indexed draw (VDM `0x18000`, argBuf=`0x1000001c600`)
| offset | direct | indirect | reading |
|---|---|---|---|
| `+0x64` | `0x61c40600` | **`0x64040600`** | opcode `0x61c4→0x6404` ✓ (LE16 @+0x66) |
| `+0x68` | vtxCount `3` | **`0x00000100`** | args-ptr **high32** = 0x100 ✓ |
| `+0x6c` | instCount `1` | **`0x0001c600`** | args-ptr **low32** = argBuf VA low ✓ |
| `+0x70` | 0 | term `0xc0000000` | counts replaced by 8-byte ptr |

Args pointer is stored **high32-then-low32** (reverse of a normal LE u64): `+0x68`=0x100 (high),
`+0x6c`=0x1c600 (low). The low32 tracks the argBuf VA cleanly (see 1c: 0x18800/0x18900). The high32
is always `0x100` for all reachable buffer VAs → its "true-high32 vs fixed-selector" nature stays
untestable within reachable VA range (EXP-0027 already flags this inferred; **not** a discrepancy).

### 1b. Indexed draw + the RT-2a cross-check (idxBuf=`…1c600`, argBuf=`…1c700`)
Indexed **direct** record (opcode `0x61f2`) is the *shifted* layout RT-2a documented:
`+0x64`=`0x40000001` sub-header, `+0x68`=cut `0x0000ffff`, `+0x6c`=`0x61f20600` (opcode @+0x6e),
`+0x70`=idxVA `0x1c600`, `+0x74`=idxCount `3`, **`+0x78`=instCount `1`**, `+0x7c`=baseVertex `0`.

Indexed **indirect** record (opcode **`0x6432`**):
`+0x64`=`0x40000001`, `+0x68`=cut `0x0000ffff`, `+0x6c`=**`0x64320600`** (opcode `0x61f2→0x6432` ✓),
`+0x70`=idxVA `0x1c600` (**inline, kept** ✓), **`+0x74`=`0x00000100` (args high32)**,
**`+0x78`=`0x0001c700` (args low32 = argBuf VA)** ✓.

> **Cross-check answer: YES — RT-2a's indexed-record shift applies to the indirect-indexed form.**
> The indirect-indexed record IS the shifted indexed record; the args pointer occupies exactly the
> `+0x74`/`+0x78` slots that the *direct* indexed record uses for `indexCount`/`instanceCount`.
> The doc's "indexed keeps idx-buf ptr inline @+0x70, args ptr @+0x74/+0x78 (high32-then-low32)"
> is a direct, correct consequence of that shift. (The u32-indexed opcode base is `0x61f4`;
> restart/strip toggles bit0 — see Claim 5.)

### 1c. Multiple indirect draws in one pass (`midraw`, argBuf0=`…18800`, argBuf1=`…18900`)
Two consecutive **0xc-byte** records, each `{opcode 0x6404, argHi 0x100, argLo}`:
`+0x64`=0x6404, `+0x68`=0x100, `+0x6c`=**0x18800**; `+0x70`=0x6404, `+0x74`=0x100, `+0x78`=**0x18900**;
term `0xc0000000` @+0x7c. Each indirect draw emits its own record with its own args pointer. ✓

### 1d. Indirect dispatch (CDM `0x100000b0000`)
Direct = one `0x2c`-byte record + `0x40000000` terminator @+0x2c. Indirect replaces the terminator
with a **2nd record @+0x2c**: `+0x2c`=`0x10080000` (cfg), `+0x34`=**`0x00002404`** (aux grid-setup
shader @`0x90100`, VA>>6), `+0x3c`=`0x100`, `+0x40`=`0x000e14c0` (ptr into arg-buffer
`0x100000e0000+0x14c0`). The user argBuf VA (`0x1000001c900`) is staged in control BO
**`0x10000080000+0xb0`** (`+0xb0`=0x1c900, `+0xb4`=0x100). ✓ Exactly as documented. (Incidental: the
first record's config word is `0x00880000` for indirect vs `0x00080000` for direct — bit23
register/occupancy tier set; not a documented field, noted only.)

---

## Claim 2 — Full ICB — CONFIRMED (+ extensions)
- **Command-count @`0x18000+0x04`**: icbn 1/2/3 → `+0x04` = 1/2/3; mesh 1/2 → 1/2. ✓
- **Per-command inline draw**: N draw records with opcode `0x61c4` at 0x1aa/0x1ea/0x22a (0x40
  stride); cmd0 has **inline** vtxCount `3` @+0x1ac, instCount `1` @+0x1b0. ✓ (Doc's "+0x1ac/+0x1b0"
  count offsets exact; opcode LE16 sits at +0x1aa.)
- **Mesh-in-ICB → `0x70000600`**: micb1 → one `0x70000600` record @`0x181c4`; micb2 → two
  (0x1c4, 0x22c); rendered green (`bgra=00ff00ff`). ✓
- **Adversarial — execute-range subset** (`enc=3`, execute `(0,2)` vs `(1,2)`): `+0x04` = **3** in
  both, and **all 3** 0x61c4 records are materialized in the tiler stream regardless of range.
  → Clarification (not a contradiction): `+0x04` is the ICB's **encoded/allocated** command count,
  not the `executeCommandsInBuffer:withRange:` length; the range is applied elsewhere.
- **Adversarial — mixed draw+mesh ICB** (`commandTypes = Draw | DrawMeshThreadgroups`, cmd0=draw,
  cmd1=mesh): **ACCEPTED, `status=4`**; `+0x04`=2; the tiler stream carries **one `0x61c4` draw
  record (@0x1c6) + one `0x70000600` mesh record (@0x22c)**. New positive result — a single ICB can
  interleave classic-draw and mesh-dispatch records.

---

## Claim 3 — Occlusion query — CONFIRMED exactly
- **Result-buffer ptr @`0x10000100000+0x00`** = LE u64 visBuf VA: `+0x00`=0x18800, `+0x04`=0x100
  → `0x10000018800` (HW-correlated). ✓
- **Mode bit14 @`0x58000+0x8c`**: none `0x00000000`, **bool `0x0004c200`** (bit14 set),
  **count `0x00048200`** (bit14 clear). Single-bit `0x4000` diff ⇒ Boolean=1/Counting=0. ✓
- **Offset @`0x58000+0xa0` = byteOffset<<14**: off 0/8/16/**4096** → `0`/`0x20000`/`0x40000`/
  **`0x04000000`** (=4096<<14). ✓ including the large offset.
- **Counter semantics (readback)**: bool→visBuf[0]=**1**; count→**4096** (=64×64 passed samples);
  count@off8→visBuf[1]=4096, visBuf[0]=0; two queries (count@0 + count@8)→both 4096. 64-bit writes
  (poison upper word cleared). ✓

---

## Claim 4 — GPU timestamps — CONFIRMED
- **Period / format**: `sampleTimestamps:gpuTimestamp:` returns cpu==gpu every call; over ~60 ms
  dCPU==dGPU ⇒ `gpu_ticks_per_cpu_ns = 1.000000` ⇒ **uint64 nanoseconds, timestampPeriod 1.0**. ✓
- **Sampling-point support**: `dispatchBoundary=0, drawBoundary=0, stageBoundary=1`. ✓
- **Adversarial — compute dispatch-boundary sample**: unsupported (`supportsCounterSampling`=0);
  the sample buffer resolves **all-zero** (`TS[0..3]=0`). ✓
- **Stage-boundary (render) sample**: `TS[0..3]` are real nanoseconds
  (52990250797416…), vertex delta 2875 ns, whole 13500 ns. ✓
  ⇒ Compute/blit/per-draw timestamp queries must be emulated in a Vulkan driver — as documented.

---

## Claim 5 — Geometry-output — CONFIRMED exactly
- **Viewport count word @`0x68000+0x900` = `((count−1)<<12)|0x0C00`**: base `0x0C00`, `--nvp 4`
  `0x3C00`, **`--nvp 16` `0xFC00`** (bits[15:12]=count−1, max 16). ✓
- **Per-viewport 6-float / 0x18-byte stride**: `--nvp 4` vs `--vpmod` (perturb only viewport[1]'s
  height+znear) changes **only floats 3–6 of slot 1** (`+0x948/+0x94c/+0x950/+0x954` = ty,sy,dmin,
  dmax); viewport[0] (@+0x928) and viewport[2] (@+0x958) untouched ⇒ stride `0x18` locked. ✓
- **Clip-distance mask @`0x58000+0x20` bits[7:0]**: base `0x00010000`, `--clipdist 3` `0x00010007`,
  **`--clipdist 8` `0x000100ff`** (exact bit-per-plane, max 8). ✓
- **point_size bit18**: `--prim point` → `0x00050000` (base `0x00010000`; Δ=bit18). ✓
- **viewport_array_index bit19**: `--vpidx 1` → `0x00090000` (Δ=bit19). ✓
- **Primitive-restart cut index @`0x18000+0x68` = all-ones of index width**: list-u16 `0x0000ffff`
  (opcode `0x61f2`), strip-u16-restart `0x0000ffff` (opcode `0x61f3` = strip bit0), strip-u32-restart
  **`0xffffffff`** (opcode `0x61f5` = u32 bit1 | strip bit0). ✓ No separate enable bit; cut written
  for both list and strip.

---

## What a red-team could NOT break
Every documented offset/value reproduced exactly under adversarial multiplicity (multiple indirect
draws, 3-command ICBs, two occlusion queries, 16 viewports, 8 clip planes) and edge values (0-based
+ 4096 occlusion offsets, u16/u32 restart). No field moved unexpectedly; no value contradicted the
doc. The only new facts are additive (mixed draw/mesh ICB works; per-indirect-draw record framing)
or clarifying (ICB `+0x04` = encoded count vs execute-range length).

## Clean-room statement
DATA-TRACE + OWN-SHADER only. Our own MSL, our own harnesses; `iotrace` logs data (BO bytes) at the
userspace↔kernel boundary. No Apple binary disassembled/introspected; Metal-injected helper shaders
(indirect-dispatch grid-setup, blend/a2c microprograms) located but never disassembled. All work on
`~/cleanroom_work/rt6/`; text-only artifacts pulled back. No `docs/`, `tools/agx-isa/`,
`tools/iotrace/`, PROVENANCE, or reviews edited; nothing committed.

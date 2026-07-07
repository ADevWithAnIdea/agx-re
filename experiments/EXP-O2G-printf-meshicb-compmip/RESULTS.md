# EXP-O2G Results — shader printf, mesh-into-ICB, compression × mipmap/NPOT (A18 Pro / G17P)

**TL;DR (all three objective-2 residuals closed).** On A18 Pro / G17P / macOS 26.6:
1. **Shader "printf"** is `os_log` (macOS 26 has no MSL `printf`), gated by
   `MTLCompileOptions.enableLogging=YES`. It emits **self-describing variable-length records**
   (`[len][argblob-size][type][argdesc][inline format string][packed args]`) into a
   **driver-allocated log buffer** (`MTLLogState.bufferSize`, min 1 KB) with a
   `[capacity][flags][write-cursor]` header. The **GPU writes the whole record** (via a shared
   compiler helper `l___air_impl_os_log`, format string in the AGX image's constant data); the
   runtime only allocates + implicitly binds the buffer and **drains/formats it at completion**.
   Record framing **HW-captured mid-flight** and cross-checked against the runtime-decoded strings.
2. **Mesh-into-ICB WORKS** (HW-validated: renders the correct green triangle). Each ICB mesh command
   lowers to the EXP-0030 **mesh-grid-dispatch record `0x70000600`** in the tiler stream (not the
   `0x61c4`/`0x6404` draw records); command count at `0x18000+0x04`. `drawMeshThreads`, `drawMeshThreadgroups`,
   and multi-command ICBs all accepted.
3. **Compression × mipmap:** a mipmapped compressible texture gets **one contiguous aux buffer that
   covers ALL mip levels** (placed after the full chain; size = totalImageBytes/128).
   **NPOT/small threshold:** compression iff **actual W ≥ 16 AND actual H ≥ 16 texels** (per-dimension,
   on unpadded dims, independent of bytes-per-pixel).

All findings are **[HW]** (a dispatch/render confirmed it, or a clean byte-diff/descriptor decode) or
**[inf]** (inferred). **Zero GPU faults / reboots.** No Apple binary disassembled; only our own compiled
shader bytes + our own process's command/log buffers.

---

## PART 1 — Shader printf / os_log lowering

### 1.1 API surface (macOS 26 / Metal 4) — [HW]
- MSL shader logging is **`os_log`**, not C `printf`: `os_log_default.log_info(fmt, args…)` via
  `#include <metal_logging>`. `printf` is an **undeclared identifier** on this toolchain
  (`raw/…`: "use of undeclared identifier 'printf'").
- **`MTLCompileOptions.enableLogging = YES` is REQUIRED** (default NO → `os_log` compiles to a no-op:
  our first run produced correct kernel output but zero records/handler calls).
- Runtime: `MTLLogStateDescriptor{ level, bufferSize (min 1 KB) }` →
  `[dev newLogStateWithDescriptor:]`; bound to the queue via `MTLCommandQueueDescriptor.logState`
  (also settable per `MTLCommandBuffer.logState`). `-[MTLLogState addLogHandler:]` delivers
  `{subSystem, category, MTLLogLevel, message}` at completion.
- **End-to-end HW-validated** (`raw/pf_decoded_strings.txt`): the handler decoded
  `EVEN i=0 m=0x51abcdef g=56576 f=0.250000`, `EVEN i=2 … g=56578 f=2.250000`,
  `ODD i=1 m=0x51abcdef`, `ODD i=3 …` (lvl=2 = `MTLLogLevelInfo`), matching our kernel exactly.

### 1.2 The log buffer — driver-allocated, implicitly bound, NOT a user buffer — [HW]
- `MTLLogState` allocates the log buffer; its captured BO **size tracks `bufferSize`**
  (`bufferSize 0x40000` → BO at `gpu_va 0x10000030000` size `0x40000`; `4096` → the `0x20000` min granule).
- It is **NOT** a user-`setBuffer:` buffer and **NOT** in the Tier-2 argument buffer — the runtime binds
  it implicitly when the queue carries a `logState`. Its bind channel is **not present in any client
  command-stream BO** ⇒ runtime/firmware-managed (like the timestamp sample buffer, EXP-0027 §3). **[inf]**

### 1.3 Buffer header + record format — [HW], captured mid-flight (`raw/pf_logbuffer_records.txt`)
Captured pre-drain by racing the completion drain (kernel logs, then spins, while we SIGUSR1-snapshot).
**Header (0x14 B):** `+0x00` capacity (`0x00040000`) · `+0x04` flags (`0x02`) · **`+0x08` write-cursor /
bytes-used** (`0x90` at snapshot, grows as records land) · `+0x0c/+0x10` = 0.
**Records** are variable-length, densely packed after the header, each:

| field | off | EVEN(`i=0`) | ODD(`i=1`) | meaning |
|---|---|---|---|---|
| length | +0x00 | `0x48` | `0x2c` | total record bytes |
| argblob-size | +0x04 | `0x18` (24) | `0x08` | packed-args byte count |
| type | +0x08 | `0x01` | `0x01` | record type (format-log) |
| argdesc | +0x0c | `0x0101` | `0x0001` | per-arg descriptor/count |
| format string | +0x10 | `"EVEN i=%u m=0x%08x g=%u f=%f\0"` | `"ODD i=%u m=0x%08x\0"` | **inline, NUL-terminated** |
| args | … | i=0(u32), m=`0x51abcdef`(u32), g=`0xdd00`(u32), **f=0.25 as 8-byte double** `0x3FD0000000000000` | i, m | packed |

Key structural facts: **the record embeds the format string verbatim** (not just an id), and **`%f` is
promoted to an 8-byte double** (0.25→`…d0 3f`, 2.25→`0x4002000000000000`) per C varargs. The 4 records
(i=0,2 EVEN; i=1,3 ODD) match the decoded strings 1:1. *(The intra-arg tag/pad micro-encoding is not fully
split — first-pass structural per brief.)*

### 1.4 Shader-emit mechanism — the GPU writes the whole record — [HW] (`raw/part1_shader_lowering.txt`)
- Our own compiled kernel's `_agc.main` (126 B) **calls a shared compiler helper `l___air_impl_os_log`
  (2304 B), present in the AGX/AppleGPU image** (agxparse of *our own* shader).
- The **format string is in the AGX image constant data** (file offset `0x3860`, inside the AppleGPU image
  range `0x1710..0x5490`, **not** the AIR image) → GPU-reachable.
- **Emit code is format-length-INDEPENDENT:** `_agc.main` is byte-identical (252 hexchars) for a 3-char
  vs a 42-char format — because it passes a *pointer* to the format-string constant to the shared helper
  (which copies the string in a loop → constant code size).
- Because the mid-flight capture (§1.3, pre-completion/pre-drain) already shows fully-formed records with
  inline strings + args, the **GPU emits the entire self-describing record**: the helper reserves space
  (atomic bump of the header write-cursor), copies the format string from constant data, and packs the
  args. No dedicated "print" opcode — ordinary atomic + stores (cf. mesh emit, EXP-0030).
- **Runtime/driver-managed:** buffer allocation (`MTLLogState`), implicit bind, the `MTLLogLevel` GPU-side
  gate, and **completion-time drain** (reads the self-describing records → dispatches the handler; the
  handler fires during `waitUntilCompleted`, which is what races our capture).

### 1.5 Driver guidance (Vulkan `debugPrintfEXT` / shader logging)
Allocate a log buffer with a `[capacity][flags][write-cursor]` header; compile shaders that reserve record
space via an **atomic on the write-cursor** and store self-describing `[len][argsize][type][argdesc][format
string][packed args]` records (format string in shader constant data, `%f`→double); CPU-drain + format at
completion. Enable the compiler's logging path (Metal: `enableLogging`).

---

## PART 2 — Mesh draw inside an MTLIndirectCommandBuffer — ACCEPTED / HW-validated

### 2.1 Metal accepts it and it renders — [HW] (`raw/micb_*.out`, `raw/part2_meshicb_records.txt`)
Every step succeeds and the pipeline renders the correct triangle (center `bgra=00ff00ff`, `status=4`):
1. mesh pipeline (`MTLMeshRenderPipelineDescriptor.supportIndirectCommandBuffers = YES`) — created.
2. ICB `commandTypes = MTLIndirectCommandTypeDrawMeshThreadgroups`, `maxMeshBufferBindCount=1` — created.
3. `-[MTLIndirectRenderCommand setRenderPipelineState: / drawMeshThreadgroups:…]` — encoded.
4. `-[MTLRenderCommandEncoder executeCommandsInBuffer:withRange:]` — rendered green.

Also **HW-validated:** `drawMeshThreads` (`MTLIndirectCommandTypeDrawMeshThreads`) and a 2-command ICB.
**No rejects, no faults.** (So mesh-in-ICB is *not* a Metal-rejected case on G17P.)

### 2.2 Combined encoding — the ICB carries the `0x70000600` mesh record — [HW]
The captured tiler/VDM stream (`gpu_va 0x18000`) contains the **EXP-0030 mesh-grid-dispatch record
`0x70000600`** at `0x181c4`, followed by grid-dim words (`…09000000 | 00060070 | 01000000 ×6…`).
It is **NOT** the `0x61c4` draw-primitive record (the EXP-0027 §1c ICB *draw* form) and **NOT** the
`0x6404` indirect-args draw. So `executeCommandsInBuffer:` expands each ICB **mesh** command into an inline
tiler command block terminated by `0x70000600` — the mesh analogue of the ICB-draw expansion.
- **Command count** at `0x18000+0x04` (icbn 1→2, HW-clean byte-diff) — same field as the ICB draw (EXP-0027).
- A 2nd command adds a 2nd `0x70000600` at `0x1822c` (per-command stride ≈ `0x68` in this config).

⇒ Mesh-in-ICB introduces **no new work type and no new record**: it reuses the EXP-0030 mesh path from
inside the ICB command layout. A Mesa driver that already emits the mesh `0x70000600` record and the ICB
command-count/expansion (EXP-0027) gets mesh-in-ICB for free.

---

## PART 3 — Compression × mipmap / NPOT (extends docs/tiling §3+§4)

Word convention: 32-byte texture descriptor, `wordN` = LE32 at byte 4N; `baseVA = (word2 |
(word3&0xfff)<<32)<<4`, `auxVA = (word4 | (word5&0xfff)<<32)<<4`. word1 bit26=mip, bit27=compression-aux,
word3 bit31=aux-metadata (EXP-0015/O2B, `docs/tiling` §4.2). Raw: `raw/part3_*.desc.txt`.

### 3.1 Compression covers ALL mip levels — one contiguous aux after the chain — [HW]
Mipmapped compressible textures set word1 bit26 (mip) **and** bit27 (compression) + word3 bit31, with an
aux VA. The aux is **one contiguous region placed immediately after the full mip chain**:

| texture | auxOff (=auxVA−baseVA) | aux region | BO alloc |
|---|---|---|---|
| 128×128×1 | `0x10000` | `0x200` | `0x10200` |
| 128×128×8 (→1×1, full) | `0x15680` | `0x380` | `0x15a00` |
| **128×128×4 (4 of 8 levels)** | **`0x15680`** | `0x380` | `0x15a00` |
| 64×64×7 (full) | `0x5680` | `0x180` | `0x5800` |
| 256×256×1 | `0x40000` | `0x800` | `0x40800` |

- `auxOff = auxVA − baseVA = Σ_levels paddedLevelBytes over the FULL pyramid (down to 1×1)` — **HW-validated**.
- `aux content = totalImageBytes/128 = Σ_levels ceil(padW/8)·ceil(padH/4)` (1 state byte per 8×4 block,
  summed over levels): 128×128 full → `0x2ad`, 64×64 full → `0xad`, 256×256 → `0x800`; backing BO padded to
  `0x200` (128×128 → `0x15a00`), so the aux *region* is a bit larger than the aux *content*.
- ⇒ **NOT per-level separate aux buffers, NOT level-0-only** — a **single contiguous aux buffer of size
  ≈image/128 covering the whole mip chain**, placed after the last level. (Extends `docs/tiling` §4.3 to mipmaps.)
- **Partial chains reserve the full pyramid — [HW]:** `128×128×4` (only 4 of the 8 possible levels) allocates
  the **identical** footprint + aux as `128×128×8` (auxOff `0x15680`, BO `0x15a00`), *not* the 4-level
  `0x15400`. The allocation + aux placement is sized for the complete pyramid down to 1×1, **independent of
  `mipmapLevelCount`**. (64×64×7 = the full 64×64 chain, so its `0x5680` is already complete.)
- Each level is still the independent pow2-padded Morton plane of §3; compression aux sits after all of them.

### 3.2 NPOT / small-size compression threshold — actual W≥16 ∧ H≥16 texels — [HW]
Compression aux is present **iff both actual (unpadded) dimensions are ≥ 16 texels**, per-dimension:

| result | sizes (rgba8unorm) |
|---|---|
| **compressed** | 16×16, 32×32, 31×31, 17×17, 20×20, 24×24, **17×16, 16×17** |
| **uncompressed** | 4×4, 8×8, 9×9, 10×10, 12×12, 15×15, **16×15, 15×16, 16×12, 12×16, 16×8, 8×16, 32×8, 8×32, 16×4, 4×16** |

- **Actual, not padded, dims:** 15×15 (pads to 16×16) → **NO**; 17×17 (pads to 32×32) → **YES**. Each axis
  must independently reach 16 (16×15 NO, 17×16 YES, 12×16 NO, 31×31 YES).
- **In texels, independent of bytes-per-pixel:** r8unorm 16×16 (256 B) → YES, 8×8 → NO; rgba16f 8×8 (512 B)
  → NO, 16×16 → YES; rgba32f 8×8 → NO, 16×16/17×17 → YES. Confirmed for 1/4/8/16 bpp.
- This precisely pins `docs/tiling` §4.1's "≥ ~one 16×16 tile" to **W≥16 ∧ H≥16 texels**.
- Compressed NPOT aux sits at `base + nextpow2(W)·nextpow2(H)·bpp` (padded image): 17×17/20×20/24×24 →
  auxOff `0x1000` (=32×32×4).

---

## HW-validated vs inferred; Metal-rejected cases
- **[HW]** — printf: os_log end-to-end decode; enableLogging requirement; log-buffer BO size tracks
  bufferSize; header + record framing captured mid-flight; format string in the AGX image + shared
  `l___air_impl_os_log` helper + format-length-independent `_agc.main`. Mesh-in-ICB: renders (green pixel),
  all variants accepted, `0x70000600` in the ICB tiler stream, count word 1→2. Compression: aux-covers-all-mips
  (auxOff = Σ mip bytes; size = img/128); the full 16×16-texel threshold matrix across 4 formats.
- **[inf]** — printf: the intra-arg tag/pad micro-encoding of the arg blob; that the log-buffer bind is
  runtime/firmware-side (negative search — not in any client BO). Compression: that the single aux region is
  internally sub-divided per level (only its total size/placement is proven).
- **Metal-rejected cases: NONE.** Mesh-in-ICB is *accepted* on G17P (a positive result, not a rejection).
  The only "not available" item is MSL C `printf` (superseded by `os_log`), which is a toolchain fact, not
  a HW rejection.

## Recommended next
1. printf: fully split the arg-blob per-arg tag/size encoding (vary arg types: %ld/%p/%s/vector) and confirm
   the write-cursor is bumped by an atomic (splice/agxtest the `l___air_impl_os_log` reserve).
2. printf: pin the log-buffer bind channel from the kernel side (it is firmware/runtime, not a client BO).
3. mesh-in-ICB: decode the inline per-command state-block grammar in the ICB expansion (the ~0x68 stride
   region) and confirm `setMeshBuffer:`/object-payload bindings inside an ICB command.
4. compression: read back a mip level's aux bytes to confirm per-level block ordering within the single aux
   region; probe MSAA×compression×mip.

## Deliverables
`pf.m` (printf harness), `micb.m` (mesh-in-ICB), `cmip.m` (compression), `shdump_log.m` (local shdump +
enableLogging), `texdesc.py`/`pflog.py`/`imgloc.py` (analyzers), `run.sh`, `pf_*.metal`/`pf_len*.metal`;
`raw/` (records, descriptor tables, decoded strings, shader lowering — text only). Reused read-only:
`tools/iotrace/`, `tools/shdump/`. Orchestrator owns `docs/`+`PROVENANCE.md`.

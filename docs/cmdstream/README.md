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
| `+0x00` | config word: bit19 (`0x00080000`) always set + **bit23 = occupancy/register tier** | `0x00080000`↔`0x00880000` — a **2-tier boolean**, not a counter (see the corrected occupancy note below; EXP-M4-09/CMD-8) |
| `+0x08` | **shader-code pointer = shaderVA >> 6** | 64-byte units. HW-confirmed: shaders at 0x90000/0x90100 → `0x2400`/`0x2404` (Δ=4) |
| `+0x10/+0x14/+0x18` | grid x / y / z | **in threads**, not threadgroups (`dispatchThreadgroups(2)×32` ≡ `dispatchThreads(64)`) |
| `+0x1c/+0x20/+0x24` | threadgroup x / y / z = **physical launch threadgroup size, in threads/axis** | **CORRECTED (EXP-M4-09/CMD-8, A18-cross-confirmed):** this is *verbatim* `threadsPerThreadgroup` whenever the group boundaries carry semantics — every **single-group** dispatch and every kernel using a **barrier or threadgroup memory** records the exact request (M4+A18: tgmem kernel 16→16, 48→48, 100→100). The earlier "round up to power of two, product ≥ 32" was a **Metal userspace occupancy *repack*** that only fires for **barrier-free / shared-mem-free** kernels with **>1** group (M4+A18: add3 16→32, 48→64, 100→128) and is **neither next-pow2 nor next-mult-32** (e.g. 34→36, 38→64, 39→39, 80→96, 200→200) — a driver heuristic, **not a hardware rule**. **A conformant driver emits the exact requested workgroup size here (verbatim).** `grid` @+0x10 is verbatim total threads. |

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

## Graphics (draw) command stream — first pass (EXP-0014)
A draw registers ~39 BOs (vs ~13 for compute) via the **same** shared-mem+doorbell path (no
graphics-specific submit selector). Two channel types are involved: **TA** (tiler/vertex) and
**3D** (fragment). Control BOs by GPU VA:

| GPU VA | role |
|---|---|
| `0x18000` (fw ctx) | **VDM / tiler draw stream (TA)** |
| `0x58000` (fw ctx) | **3D fixed-function state pool** (depth/stencil/blend/raster packets) |
| `0x68000` (fw ctx) | **viewport / tiling context** |
| `0x10000000000` | shader code (VS + FS; 6 constant-program stubs) |
| `0x10000100000` | vertex-attribute table |
| `0x10000110000` | **3D attachment (render-target) descriptor** |
| `0x10000130000` | **USC shader-binding program** |

- **TA** binds VDM `0x18000` + viewport `0x68000` + attr table; **3D** binds attachment `0x110000` + FF-state `0x58000`.
- **Shader binding:** unlike compute's single `shaderVA>>6`, graphics uses separable
  selection state. On M4, a VS change emits VDM `(0x500, token)` and the FS uses a
  32-bit code-window-relative selector at `0x58000+0x08` (EXP-0042). The earlier
  “self-describing walk with no selector” interpretation is superseded. Exact mapping
  of the window base to Linux `usc_exec_base` remains open; USC bind grammar was
  partially decoded in EXP-G1a.
- **VDM draw record — full field map (EXP-M4-09/CMD-4; all 5 prims × {non-indexed,u16,u32} RUN):**
  header (state-size @+0x0c) + USC bind-pairs (control-word, addr) + primitive word.
  - **Non-indexed:** opcode **`0x61c4`** (bytes @+0x66/+0x67); **primitive type byte @+0x65** =
    {point `0x00`, line `0x01`, lineStrip `0x03`, tri `0x06`, triStrip `0x09`}; **vertexCount @+0x68**;
    **instanceCount @+0x6c**.
  - **Indexed (record shifts):** opcode word @+0x6c–0x6f = **`0x61f2 | strip | (u32<<1)`** →
    `0x61f2` (u16 list) / `0x61f3` (u16 strip) / **`0x61f4` (u32 list)** / `0x61f5` (u32 strip) —
    **the u32 path `0x61f4` is now HW-RUN, not inferred**; **primitive byte @+0x6d** (same enum as
    non-indexed); **restart comparand @+0x68** (0xffff u16 / 0xffffffff u32); **index-buffer config
    @+0x70**; **indexCount @+0x74**; **instanceCount @+0x78** (moved from +0x6c); **baseVertex @+0x7c**;
    **index-buffer extent-in-dwords−1 @+0x80** = ⌈indexCount·indexSize/4⌉−1 (u16×6=2, u32×6=5,
    u16-strip×8=3); config word @+0x64 = `0x40000001`.
  - **baseInstance** is **not** in the VDM record (both indexed and non-indexed unchanged when set); it
    reaches the shader via the vertex-attribute path (`0x10000100000+0x8c`) only when the shader
    consumes `[[instance_id]]` — elided otherwise.

### M4 repeated-stream framing and rollover (EXP-0043; bounded partial)

Live M4 repetition/threshold probes add framing facts without promoting them to
A18. For the tested direct-dispatch shape, each CDM record is 0x2c bytes. A first
0x8000-byte segment holds 732 records, then `0x40000000`. Adding record 733
replaces that terminal with `[0x20000100, 0x00158000]`, structurally naming the
captured continuation at `0x10000158000`; the continuation terminates normally.

For alternating direct non-indexed draws, the four-dword draw command has a
variable preceding state prefix. A first 0x8000-byte VDM segment holds 328 tested
draw/state groups, then `0xc0000000`. Draw 329 replaces that terminal with
`[0x80000000, 0x00088000]`, structurally naming captured continuation VA
`0x88000`. Runs of 1024 dispatches and 384 draws completed with correct final
readback across two segments.

Adjacent compute encoders coalesced into one terminated CDM stream in the tested
case; separate render passes terminated separately; mixed compute/render
encoders produced separately terminated engine substreams. Treat the link words
and capacities as **STRUCTURAL** for these exact shapes until mutation/replay.
General barriers, calls, indirect packets, pool sizing and A18 transfer remain
open. EXP-0043's verifier restricts evidence to eight explicitly correlated
command/state/resource VAs; generic all-BO analyses are quarantined.

### M4 exact-shape link controls (EXP-0049; commit `84779ec8`)

EXP-0049 repeats the known first-boundary pairs with a stricter four-VA
command-segment allowlist. Across two main runs and fresh boundary repetitions, direct
compute, encoder-per-dispatch compute, and direct compute with seven client
allocations all retain the 732/733 boundary, link offset `0x7dd0`, exact pair
`[0x20000100, 0x00158000]`, and identical complete tested source/target hashes.
Alternating state-every-draw VDM with and without the same padding retains the
328/329 boundary, offset `0x7b18`, pair `[0x80000000, 0x00088000]`, and identical
tested segment hashes. The padding moves authored client resource VAs, but this
single perturbation is not a general relocation proof.

Changed shapes deliberately stop at the clean-room boundary. Indirect CDM first
captures the known second BO at count 512 without the exact source pair.
Stable-state VDM and one-draw-per-pass VDM likewise capture the known second BO without
that pair; recognized source occupancies bound those cases but do not identify
a first link, alternate destination, or execution location. No new target was
searched or inspected. These results therefore preserve the link words as
**STRUCTURAL** for the exact reproduced shapes only. They do not establish a
hardware consumer, legal arbitrary targets, general capacity/packing, Linux
submission semantics, or A18 behavior. See
`../../experiments/EXP-0049-command-link-structure/analysis/{summary.json,report.txt}` and
`../../experiments/EXP-0049-command-link-structure/manifest.json`.

- **Viewport** = 4 transform floats @ `0x68000+0x910` (`{w/2, h/2, w/2, −h/2}` — Y-flip) + depth range
  @+0x920/+0x924; pointed to from the VDM.
- **Attachment descriptor** (`0x10000110000`): **pixel-format code = byte @+0x21** (= sampled byte1; EXP-M4-08 DESC-1 CORRECTS the earlier +0x22, which is the swizzle low byte and only coincided for bgra8). Full format word `(0xf<<28)|(swizzle<<16)|(byte1<<8)|(byte0&~0x20)`, 43/43 formats;
  **clear color** = 4 floats @+0x170, in chained 0x300-byte segments (⏳ load/render/store meaning).
- **Fixed-function state** (`0x58000`): raster line/point @+0x54, depth @+0x38, blend @+0x08 — bound via
  the VDM USC-pairs. ⏳ per-packet bit decode is a follow-up.

## Graphics fixed-function state packets & USC bind grammar (EXP-0019)

### ⚠ Blend is programmable (compiled into the fragment shader), not a fixed-function packet
The single most important structural fact for a Mesa port: **blend factors/ops are lowered into the
fragment shader's blend microprogram in the shader-code BO `0x10000000000`**, not emitted as a
fixed-function LUT (changing a blend factor rewrites ~40 shader words; `0x58000` barely moves). This is
Apple's TBDR programmable-blend model — the driver **must compile blend state into fragment shaders**
(as Asahi does for M1/M2). Dual-source blend and framebuffer logic ops both work through
this shader path (the ISA has the 16-function bitwise LUT, EXP-0013). *(The blend microprogram is
compiler-generated code — located, deliberately NOT disassembled, per CLAUDE.md clean-room rule 5.)*

#### ✅ Blend STATE-POOL side — full field map (EXP-M4-09, all 19 factors × 5 ops × dual-source)
Sweeping **every** blend factor/op on srcRGB/dstRGB/srcAlpha/dstAlpha + write-mask + dual-source and
diffing only the traceable `0x58000` pool proves the **factor/op identity is entirely in the FS
microprogram** — changing a factor/op rewrites the FS blend epilog (typically ~5,600–7,800 code words;
some factors lower to a near-identical program, a handful of word deltas) while **nothing in `0x58000`
selects a factor or op**, and the **five blend ops (add/sub/revsub/min/max) touch `0x58000` not at
all**. So the impl team's blend-lowering compiler owns the equation; `0x58000` carries only these
orthogonal side-flags the driver must emit **alongside** the compiled FS:

| field | offset | meaning |
|---|---|---|
| **Color write mask** | `0x58000+0x5c` bits[3:0] | 4-bit mask, **bit-reversed RGBA**: R→bit3, G→bit2, B→bit1, A→bit0 (full=0xf). Present whether blend is on or off. |
| **Store-epilog engaged** | `0x58000+0x50` bit29 (`0x2000_0000`) | set iff blending enabled **OR** write mask ≠ 0xf (no-blend + full mask = `0x0000_0200`; otherwise `0x2000_0200`). |
| **Blend-constant-color needed** | `0x58000+0x10` bit6 (`0x40`) | set iff any factor ∈ {blendColor, 1−blendColor, blendAlpha, 1−blendAlpha}, on any of the 4 factor slots. |
| **Blend/store program-class** | `0x58000+0x08` bits[10:6] | small enum co-selected by the FS lowering (observed `0x4c0` plain-store / `0x500` default-blend / `0x540` extended). **Not** a driver-independent field — set it as part of blend lowering. |
| **Extended-source / saturate class** | `0x58000+0x18` bit0 | FS-class covariant (observed set by srcAlphaSaturate and several one-minus-dst factors); driver-set as part of lowering, not an orthogonal knob. |

- **Blend-constant color (`setBlendColor`) is a FS UNIFORM, not a fixed-function register:** the 4×f32
  RGBA constant is placed into the uniform/argument BO `0x10000248000` (observed at `+0x620`; the exact
  offset is the driver's own uniform-allocation choice) and read by the FS blend epilog. Driver action:
  set `0x58000+0x10` bit6 and append the RGBA constant to the FS uniform stream.
- **Dual-source blend leaves `0x58000` unchanged** vs single-source (the `src1*` factors change only
  ~27 FS words). Dual-source is realized purely in the FS, which declares `color(0) index(0)` +
  `color(0) index(1)` outputs — **there is no `0x58000` flag distinguishing dual-source**.
- The `0x58000` blend words are all HW-validated on **M4**; the pool layout matches the A18-derived
  offsets used elsewhere in this doc byte-for-byte.

### ✅ Depth/stencil packet (`0x58000`, HW-validated)
Per-face blocks: FRONT depth `+0x38` / stencil `+0x3c`, BACK depth `+0x40` / stencil `+0x44`, flags `+0x34`.
- **Depth word:** stencil-ref[7:0], depth-write-DISABLE bit21, compare[26:24].
- **Stencil word:** write-mask[7:0], read-mask[15:8], pass-op[18:16], zfail-op[21:19], sfail-op[24:22], compare[27:25]; bits[31:28] unused.
- **Compare 0–7** = never/less/equal/lessEqual/greater/notEqual/greaterEqual/always.
- **Stencil-op 0–7** = keep/zero/replace/incrClamp/decrClamp/invert/incrWrap/decrWrap.
- **All three op fields share the identical 0–7 enum — HW-validated 8-of-8 per field** (EXP-M4-09/CMD-2:
  pass, zfail, and sfail each swept through all 8 ops independently). **Back-face** uses the identical
  encoding at the back stencil word `+0x44`, independent of front `+0x3c`.

### ✅ Rasterizer packet (`0x58000+0x70`, HW-validated)
cull[1:0] = none/front/back; winding bit16 = CW/CCW; **depth clip-vs-clamp = native 2-bit field [11:10]**
(depth clamp is HW-supported — good for Vulkan); polygon line-fill = raster nibble `0x5` + flags bit26;
depth bias: enable = flags `+0x34` bit17, constant/slope/clamp = 3 floats in the tiler-param region
(`…+0x2a8000`).

### M4 public scissor/depth-bias behavior (EXP-0054; commit `6c342a06`)

Four fresh-process public-Metal runs retain exact guarded color/depth bytes.
The tested full/asymmetric/edge single scissors cover exactly 256/28/2 pixels;
zero-width and zero-height cases cover none. Two viewport-indexed scissors
write 30 and 40 pixels, and changing only slot 1 writes 15 there while slot 0
remains byte-exact at 30. For Depth32Float, tested flat constant displacements
correlate with `constant * 2^-24` at `-1`, `+/-100`, and `+/-100000`; a sloped
`-1` case shifts by `-0.01875`, while flat slope-only `+/-1` controls do not.

Runs01/02 preserve the H4 negative: magnitude-100 clamped and unclamped bytes
are identical because the approximately `5.96e-6` displacement is below the
`0.001` clamp. Separately preregistered runs03/04 use sign-matched
`+/-100000`; both clamps engage and reduce the displacement to approximately
`+/-0.001`. This is public M4 behavior only. EXP-0054 captures no BO and does
not identify private `isp_scissor_base`/`isp_dbias_base` bytes, integer mode,
native packing, Linux marshaling, or A18 behavior; P0.3 remains open. See
`../../experiments/EXP-0054-m4-scissor-depth-bias/analysis/{summary.json,report.txt}`.

### USC bind grammar + graphics shader binding (EXP-0019/0024, corrected EXP-0042)
The VDM (`0x18000`) holds a **fixed 8-pair template** (control-word, address) into `0x58000`/viewport/
context — invariant under state changes (only the `+0x0c` length word grows, see PPP below).

**PARTIAL — M4 EXP-0042:** no absolute `shaderVA>>N` word was observed, but a draw does carry
explicit separable selectors. When the VS actually changes, the VDM record includes
`(0x500, token)` at `+0x1c/+0x20`; the two tested tokens `0x40/0xc0` follow distinct VS
creation order, not code-record offsets. The FS selector is the 32-bit word at
`0x58000+0x08`. For four tested FS variants:

```text
fs_selector = fs_record_header + record_size + 0x40
```

It addresses the payload of a following `0x80` record. Equal-main/equal-record-size FS
variants select different offsets and produce different colors, disproving the old “FS
size” reading. The consumer and complete token grammar are still unknown.

- In the **code BO `0x10000000000`**, every exact authored stage match is contained by a
  0x40-byte zero-reserved header whose word 0 is the aligned total record size, followed
  by that stage's authored constant program, authored main and padding. This is a live
  record layout, not proof that firmware performs a positional walk. Unknown regions were
  retained but not decoded.
- The **USC program `0x10000130000`** holds three `0x240`-byte per-stage **uniform-preamble programs**
  (block0 ≡ block1 = vertex, block2 = fragment), each led by config `0x008800XX` (XX = stage×0x0c);
  `+0x10/+0x18/+0x250/+0x490` = uniform-data pointers, `+0x14…` = per-shader slot ids.
- **Driver guidance:** maintain a queue-relative executable window and explicit VS/FS
  selection. The observed base stayed at `0x10000000000` under ordinary allocation
  perturbation, but its exact mapping to queue `usc_exec_base` is **INFERRED**, not proven.
  Do not add or assume a per-render code-base submit field.

### ✅ PPP fixed-function header / emission order (EXP-0024) — length word, not a present mask
There is **no present-bit mask**. The 8 VDM bind-pairs and pool layout are **fixed**; presence is a
**monotonic length word**: VDM `0x18000+0x0c` and pool `0x58000+0x14` both grow **+0x400** only when a
depth/stencil block is appended (blend/cull alone → 0 VDM diff). **Per-group presence = enable bits inside
each packet**: depth `+0x34` bit18 / `+0x38`; stencil `+0x34` bits[19:18] / `+0x3c`; blend `+0x18`,`+0x50`;
cull `+0x70`. So a driver assembles state by writing packets + toggling their enable bits, and bumps the
length word when the depth/stencil block is present.

### ✅ Compute config word + threadgroup-memory size (EXP-0024; occupancy tier CORRECTED EXP-M4-09/CMD-8)
- **CDM config word** (`0x100000b0000+0x00`) = `0x00080000` (bit19 always set) + **bit23 = occupancy/register
  tier** (EXP-0020); atomics/barriers/simd/tgmem do **not** touch it.
- **⚠ Occupancy tier bit23 — threshold CORRECTED (A18-cross-confirmed).** bit23 is a **single-bit 2-tier
  boolean** — across ~50 kernels (footprint f0 = 2…96) the word is *only ever* `0x00080000` (clear) or
  `0x00880000` (set); no higher bit ever lights, so it is **not** the LSB of a GPR-count field (the actual
  GPR count lives in the shader BO / USC config, not here). The earlier interpolated **"clear ≤11 / set
  ≥12 GPRs" is FALSE.** The flip is driven by the compiler's **peak register-pressure / occupancy class**,
  *not* the total-GPR (metadata field-0) count, and it happens **far below 12** — A18-measured: an f0=8
  kernel with two loop-carried chains (`N2E0`) is **SET** while other f0=8 kernels (`N1E3`, `N0E7`) are
  **CLEAR**; f0=9 likewise splits (`N1E4`/`N3E0` set, `N0E8` clear); the lowest SET is a half-datapath
  kernel at **f0=5**. (bit23 correlates 1:1 with the presence of our own shader's `__GPU_METADATA`
  field-32 — a compiler-computed occupancy property.) **A Mesa driver must set bit23 from its own register
  allocator's occupancy decision (peak-GPR class), not from a `≥12` test.**
- **Threadgroup (shared) memory size** is in the **shader BO `0x10000090000`**, not the CDM:
  **`field = (tgmem_bytes << 2) | 0x80`** (HW-validated 256→32768 B) — static at `+0x40`, dynamic at
  `+0x4c` bits[31:16].

### Tooling note (macOS 26)
The `iotrace` interposer **must be built `-arch arm64e`** or captures silently fail; shader size-probes
need a non-zero coefficient (≈1e-9) to survive dead-code elimination.

## Completeness: indirect commands, occlusion queries, timestamps (EXP-0027)
- **Indirect draw** (`drawPrimitives…indirectBuffer:`): VDM opcode changes **`0x61c4→0x6404`** (non-indexed) /
  **`0x61f2→0x6432`** (indexed); inline counts are replaced by an 8-byte pointer to the public
  `MTLDraw[Indexed]PrimitivesIndirectArguments` struct — non-indexed ptr at VDM `+0x68`(hi32)/`+0x6c`(lo32)
  (stored **high32-then-low32**); indexed keeps index-buf ptr inline at `+0x70`, args ptr at `+0x74`/`+0x78`.
- **Indirect dispatch:** because the CDM grid is in *threads* but indirect args give *threadgroups*, Metal
  injects a **2nd CDM record + a grid-setup helper shader** to multiply `threadgroups × threadsPerThreadgroup`
  (args VA staged at `0x10000080000+0xb0`). **A Mesa driver must replicate this multiply.**
- **Full ICB** (`executeCommandsInBuffer:`): each command expands to an inline state-block + draw (same
  `0x61c4`, inline vertexCount); header `+0x04` = command count. (Distinct from the args-pointer form above.) *(RT-6: `+0x04` is the **encoded/allocated** command count — `withRange:` still shows the full count with all records materialized, range applied elsewhere. **Mesh and draw commands can coexist in one ICB** — a mixed Draw|DrawMeshThreadgroups ICB produces one `0x61c4` + one `0x70000600` record.)*
- **M4 public-Metal behavior boundary** (EXP-0053, commit `e31dfb46`): canonical
  full-byte runs 05/06 reproduce zero/nonzero indirect compute and draw, a
  CPU-before-commit argument update, a GPU-produced argument from a prior
  encoder, full/prefix/suffix/middle/empty ICB ranges, middle reset plus one-slot
  re-encode, and one optimized-full functional-equivalence case. Hash/aggregate-
  only successes 03/04 are downgraded, while compile/fault histories 01/02 are
  retained. This does not decode or validate private ICB storage/count fields,
  helper programs, writable-command grammar, Linux UAPI mapping, or A18 behavior;
  P1.7 remains open. See
  `../../experiments/EXP-0053-m4-indirect-api-semantics/analysis/{summary.json,report.txt}`.
- **Occlusion query:** result-buffer base pointer at `0x10000100000+0x00`; per-draw **mode = bit14 of
  `0x58000+0x8c`** (Boolean=1 writes 1 / Counting=0 writes exact passed-sample count, both u64); per-draw
  **offset = `0x58000+0xa0` = byteOffset<<14** — HW-validated across offsets 0/8/16/64/256/1024/4096
  (EXP-M4-09/CMD-7); a tiler mirror at `0x10000258000+0x00 = byteOffset>>2` also carries it. Readback
  confirms accumulation (Counting wrote 4096 = 64×64; Boolean wrote 1). Per-tile→total summation is
  firmware-managed.
- **GPU timestamps — public Metal observations, not a native/Linux ABI:** earlier public-API probes returned
  64-bit values in a nanosecond-valued CPU/GPU clock and exposed stage-boundary sampling while tested
  dispatch/draw-boundary requests resolved as zero. EXP-0052 (M4, commit `cad2132b`) strengthens only that
  bounded public path: all 256 CPU/GPU pairs were equal and monotonic, and 28 completed pass ranges obeyed
  `startVertex <= endVertex <= startFragment <= endFragment`. It also **falsified strict cross-pass
  serialization**: pass 2 start-vertex preceded pass 1 end-fragment by 500 ns and 1,000 ns. Pre-commit and
  immediate post-commit/pre-wait resolves were zero; the latter was not status-qualified as actually
  in-flight, so only post-completion resolution is established. Do not infer a private sample-buffer layout,
  native counter availability, Linux `command_timestamp_frequency_hz`/`GET_TIME` conversion, or A18 behavior
  from EXP-0052. See `../../experiments/EXP-0052-m4-timestamp-semantics/analysis/{summary.json,report.txt}`.
- **MSAA** (HW-PROBE): N independent samples with 1:1 sample-id ordering (`read(coord,s)` = sample s);
  resolve = arithmetic average; physical interleave is on-chip tile SRAM (not byte-visible). **Only 2×/4×
  exist — 8× is Metal-rejected** (EXP-M4-09/CMD-7: `supportsTextureSampleCount:` 1/2/4 = YES, 8/16/32 = NO;
  8× fails both texture creation (hard assert) and pipeline creation (nil+NSError)). Sample-count word in
  the RENDER/STORE segment `+0x24`: 1× = `0x0000fc03`, 2× = `0x0800fc03`, 4× = `0x0900fc03` (bit24 = count
  LSB, bit27 = MSAA-store).

## Mesh/object shading submission (EXP-0030)
A mesh draw is **not a new work type** — it reuses the graphics path (same `IOSurfaceRoot` +
`AGXAcceleratorG17P` clients, same selectors, ~39 sel-9 maps; **no CDM launch descriptor** → a single
unified graphics submit, not compute+draw). It builds the same tiler/VDM stream at `0x18000` but replaces
the draw's `0x61c4` primitive record with a **mesh-grid-dispatch record (`0x70000600` + grid dims)**; same
3D state (`0x58000`) + viewport (`0x68000`), plus a **mesh-only dispatch-descriptor BO `0x100000f8000`**.
The mesh-output **UVB buffer** is a driver/firmware-allocated intermediate (tiler-heap + `0x100000f8000`),
reached via USC/uniform binding like the vertex-shader **UVS** varying buffer — **not user-visible**; its
sizing and the UVB→rasterizer wiring are a **kernel-interface** item (see `../kernel-interface.md`).

## Geometry-output pipeline (EXP-O2A; ranges swept to max in EXP-M4-09/CMD-5)
- **Multiple viewports** (`0x68000`): count word `+0x900 = ((count-1)<<12)|0x0C00` — **HW-validated for
  the full range count = 1..16** (`0x0c00, 0x1c00, … 0xfc00`). A per-viewport control-word header; then a
  **6-float / 0x18-byte per-viewport transform array** (the single-viewport block `+0x910`, arrayed).
  Index selected by the VS `[[viewport_array_index]]` output.
- **PPP output-select word `0x58000+0x20`** (which shader outputs are live): **bits[7:0] = clip-distance plane
  mask** — **HW-validated for N = 1..8 planes** (mask = `(1<<N)-1`: `0x01,0x03,…,0xff`); **bit16 = a constant
  "outputs present" flag**; **bit18 = point_size**, **bit19 = viewport_array_index**. Clip-distance = a
  shader-output varying + this mask; point-size *value* is shader-driven (no descriptor field).
- **Primitive restart** (indexed VDM record `0x18000`): **cut/restart comparand at `+0x68`** — a genuine
  **per-draw userspace-written field, always present, with no separate enable bit**. It **tracks the index
  width**: `0x0000ffff` (u16) / `0xffffffff` (u32), HW-confirmed by the u16→u32 diff, and is written on
  **every** indexed draw (restart or not). opcode `+0x6c` bit0=strip / bit1=u32; count `+0x74`,
  extent-dwords-1 `+0x80`, idxBuf VA `+0x70`.
  - **Metal only ever writes the index-type maximum** (`0xffff`/`0xffffffff`) — which is exactly the
    Vulkan/D3D10+ restart-index semantics, so a **Vulkan Mesa driver needs nothing more**. A truly
    *arbitrary* (OpenGL `glPrimitiveRestartIndex`-style) value is **not emittable through Metal**, so its
    HW acceptance is **formally untested**; but since `+0x68` is proven a settable per-draw comparand
    (width-tracking), a GL frontend writing an arbitrary value there is well-founded — HW-plausible,
    unverified. This is the one residual can't-emit-from-Metal item, now precisely located.
- **Alpha-to-coverage** = shader-lowered (FS epilog) + FF bits `0x58000+0x18` bit0 (MSAA-only) and `+0x50`
  bits[30,26]. **Alpha-to-one has no FF field** — realized entirely in the FS epilog (output alpha → 1.0).
- **Kernel-managed:** the multi-scissor rectangle array is in **no** client BO — it routes via the `isp_scissor`
  submit param (see `../kernel-interface.md`); only the scissor *enable* bit (`0x58000+0x34` bit16) + tile-grid
  clamp (`0x68000+0x904/908`) are client-side.
- **Metal-unreachable → emulate:** cull distance (MSL has clip only), polygon-point fill (fill/lines only), a
  *custom* restart index (HW field exists at `+0x68` but Metal always uses all-ones).

## ✅ USC / resource bind grammar — RESOLVED (EXP-G1a)
G17P has **no single tagged USC control-word list** (unlike G13). Binding is split across three structures, each with a
clean, emittable grammar:
- **Textures + samplers → argument buffer `0x10000248000`:** a **2-pointer header** `[texture-array VA][sampler-array VA]`
  (8-byte LE GPU VAs, high32 `0x00000100`), then contiguous **32-byte texture descriptors**, then **0x20-stride sampler
  descriptors** (RT-2a: the sampler entries are **0x20 apart**, not 8), then a `0x60000000` terminator. **The Texture/Sampler count split IS this header:**
  `num_textures = (samp_ptr − tex_ptr)/0x20`, `num_samplers = (terminator − samp_ptr)/0x20` **(RT-2a correction: samplers are 0x20-stride, not 8; the earlier `/8` overcounted 4×)**. The shader's `tex_sample`
  op+4 / op+5 index these two arrays. (HW-clean over tex1/2/3, smp1/2/3, mixed.)
- **Buffers → `0x10000100000+0xa0`:** a flat table of **8-byte LE GPU VAs**, one per bound buffer in index order.
- **Uniform preload → USC program `0x10000130000`** per-stage header tags: `0x0088_00XX` register/shader-config
  (`XX` = stage×0x0c), `0x0042_XXXX` uniform-data pointer, `0x0020_00XX` uniform-slot count/id. The per-resource preload
  is done by the program *body* (`0x67` loads), not a fixed tag list. *(EXP-0042 supersedes the earlier
  positional-walk interpretation: graphics has separate VDM VS-token and pool FS-relative selectors.)*

## ✅ UVS / VS→FS varying linkage — RESOLVED (EXP-G1a)
- **VS UVS output slots:** `[[position]]` = slots 0–3; user varying #k = slots 4+4k..7+4k (one slot/scalar, declaration
  order). The `0x57` varying-store `byte+4 = slot<<5` (EXP-0037).
- **FS `iter`** reads by coefficient index (`0x2f` byte+5 = coef<<1); coef 0 = perspective 1/W. The set is
  **cross-stage-compacted** — only varyings the FS consumes are emitted; a **linker assigns matching VS-slot↔FS-coef**
  (no byte-addressable remap descriptor). **Reorder-proven on hardware** (identical FS reading the middle slot rendered
  0.200 vs 0.302 across two varying orderings).
- **Count descriptor a driver emits:** `0x58000+0x2c = 4 + 4·nvary` (UVS scalar-output count), mirrored at `0x18000+0x10`.
- **Sysvals are NOT in uniform registers** (G1-c negative): `vertex_id`/`instance_id`/`[[position]]`/`front_facing` are
  `get_sr`-on-demand (confirms EXP-0031); the uniform file holds only base pointers + scalar/push uniforms. There is **no
  sysval→uniform table** to build.

## Shader logging (printf/os_log) + mesh-in-ICB (EXP-O2G)
- **Shader logging** (macOS 26 has no MSL `printf`; use `os_log` via `<metal_logging>`, gated by
  `MTLCompileOptions.enableLogging=YES`): the log buffer is **driver-allocated by `MTLLogState`** (min 1 KB, size =
  `bufferSize`; `gpu_va 0x10000030000`), **implicitly bound** (not a user buffer, not in the argument buffer). Record
  format = `[capacity][flags][write-cursor]` header, then dense self-describing records `[u32 len][u32 argblob-size]
  [u32 type][u16 argdesc][inline NUL-terminated format string][packed args]` (`%f`→8-byte double). The shader calls a
  compiler helper `l___air_impl_os_log`; the GPU writes the whole record. Allocation/bind/level-gate/drain are runtime-managed.
- **Mesh-in-ICB is ACCEPTED** (`MTLIndirectCommandTypeDrawMeshThreadgroups`): it lowers to the **same mesh-grid-dispatch
  record `0x70000600`** (EXP-0030) in the tiler stream (`0x181c4`) — no new work type; command-count at `0x18000+0x04`.

## ✅ Tessellation — NATIVE hardware stage (EXP-O2H)
**A18/G17P implements tessellation as a native graphics/tiler-path stage — NOT compute-emulated (unlike M1/M2), NOT
the mesh path.** Decisive evidence: with CPU-written factors (no user compute encoder), `drawPatches` registers the
**same BO set as `drawPrimitives`** — **no CDM launch descriptor, no mesh dispatch record** (single graphics submit).
- `drawPatches` drives a distinct **VDM patch-dispatch record** in the tiler stream `0x18000`: opcode high-byte **`0x40`**
  (vs draw `0x61c4`, mesh `0x70000600`); **patch domain type @+0x8c** (triangle=1 / quad=2); packed config @+0x68
  (control-point count + partition mode — ⏳ sub-bit split); factor pointer ~@+0x74. **Partition mode is NOT in `0x58000`**.
- **Tessellation-factor buffer = IEEE half-float** (`MTLTessellationFactorsHalf`): triangle = edge[3]+inside = 4 halfs (8 B),
  quad = 6 halfs (12 B). HW-validated (levels 1/4/16 → 0x3c00/0x4400/0x4c00).
- The **post-tessellation vertex function is an ordinary `__vertex` shader** (no novel opcode) — structurally like mesh
  (native pipeline, ordinary shader). The **domain-point generator + generated buffers are firmware-managed** (tiler-param
  buffer `0x10000080000`; a kernel-interface item shared with mesh's UVB).
- **Driver options:** (a) **native** — ordinary post-tess VS + half-float factor buffer + the tiler patch-dispatch record
  (no compute pre-pass); or (b) keep `libagx` **compute emulation** as a portable fallback. **Emulation is OPTIONAL on A18.**

## Open items (next cmdstream experiments)
- Compute: decode `+0x00` config/register word; find the threadgroup-memory-size field.
- Graphics: **RESOLVED** — USC grammar + shader-entry (see above), per-packet depth/stencil/raster bit decode
  (RT-2a/RT-11: depth@+0x38/stencil@+0x3c/raster@+0x70 exact), attachment dims/stride + 3-segment load/render/store
  (EXP-G1b), programmable blend (compiled into FS). Remaining firmware-managed (kernel items, not userspace ⏳):
  the **tiler parameter buffer** (`0x10000088000/140000`) overflow→partial-render trigger + ZLS depth-store.
- Texture/sampler descriptor bit layouts → `../descriptors/`.

Source: `experiments/EXP-0009-iotrace-bringup/`. Tool: `tools/iotrace/`.

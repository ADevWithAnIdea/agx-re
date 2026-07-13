# M5 (Apple10 / G17g) command-stream deltas vs A18 (G17P)

Delta-form spec: "same as `cmdstream/README.md` (A18/G17P) except as noted." Source: EXP-M5-06
(own-process iotrace DATA-TRACE on M5 / T8142 / macOS 27.0, 8 GPU cores). HW-validated unless marked ⏳.
Clean-room: own-process IOKit data-trace only; no Apple binary introspected.

## Submission model — SAME
Two user clients: `IOSurfaceRoot` + **`AGXAcceleratorG17G`** (A18: `…G17P`). Shared-memory + doorbell,
no per-submit ioctl (IOKit call count invariant; compute 49 / draw 58, same as A18). Resource-map
selector 9 (in@0x38 CPU base, in@0x48 size, out@0x00 GPU VA) unchanged.

## Compute launch (CDM) descriptor `…b0000` — 0x2c-byte record, `0x40000000` terminator (SAME)
- **SAME:** shader ptr `+0x08 = shaderVA>>6`; grid(threads) `+0x10/+0x14/+0x18`; threadgroup
  `+0x1c/+0x20/+0x24` (incl. the barrier-free Metal occupancy repack, e.g. 48→64).
- **DELTA — config word `+0x00`:** the A18 always-set **bit19 base (`0x00080000`) is GONE** on M5.
  The word is `0x00000000` (clear) / **`0x00800000`** (set) — **bit23 = the same 2-tier occupancy/register
  class** as A18 (driver sets it from its register allocator's peak-GPR occupancy decision, not a `≥N` test).
- **Config constants RESOLVED (EXP-M5-13):** `+0x04=0x01000000`, `+0x0c=0x40000001`, `+0x28=0x60000160`
  are **invariant** across grid (64…1024), threadgroup (1…256), threadgroup-memory (0/256/16384 B) and
  occupancy (`--heavy` flips only `+0x00` bit23) — structural template constants, **not parametric** on
  any dispatch axis. (Earlier `+0x04=0x1` was an LE misread; measured value is `0x01000000`.)

## Threadgroup-memory size — MOVED to shader BO `…90000+0x38`
A18 used `(tgmem<<2)|0x80` at shader-BO **+0x40**; on M5 +0x40 keeps only a 1-bit has-tgmem flag
(`0x40`→`0x48`). The **size is at +0x38**:

    word(+0x38) = 0x0c00000f | (fine<<11) | (coarse<<19)
      fine   = round_up(tgmem & 0x7FF, 64) / 64     (bits [11:15])
      coarse = tgmem >> 11                           (bits [19:...], bits[16:18] reserved)

HW-validated 16 B…32 KiB (sub-64 B rounds up to 64).

## Argument buffer (Tier-2) — SAME
Resource table `+0x14a0`, 8-byte slots: buffers = inline GPU VA; textures/samplers = ptr-to-descriptor
in same BO. Byte-identical to A18.

## Graphics VDM draw record — same layout, OPCODES SHIFTED +0x0800
- **DELTA:** non-indexed opcode **`0x61c4`→`0x69c4`**; indexed **`0x61f2`→`0x69f2`** (`| strip | (u32<<1)`,
  u16=`0x69f2` / u32=`0x69f4`).
- **SAME:** primitive-type byte (point`00`/line`01`/lineStrip`03`/tri`06`/triStrip`09`) at rec+0x01;
  vertexCount rec+0x04 / instanceCount rec+0x08; indexed config word `0x40000001`; restart comparand
  tracks index width (`0xffff`/`0xffffffff`).

## Viewport transform — MOVED to `0x68000+0x9d0` (A18 +0x910)
4 floats `{tx, sx, ty, sy}` with Y-flip in sy (`tx=x+w/2, sx=w/2, ty=y+h/2, sy=-h/2`). Default full-target
`{w/2,h/2,w/2,-h/2}`. Same structure, offset +0xc0.

## Fixed-function state pool `0x58000` — per-bit decode RESOLVED (EXP-M5-10)
Delta vs A18 is **offset-only + one regrouping**: the depth/stencil/raster/blend **bit layouts and
enums are BIT-IDENTICAL to A18** (`cmdstream/README.md` §depth-stencil/§rasterizer/§blend), only the
byte offsets in the pool moved, and the depth/stencil block is **regrouped** (A18 interleaves depth/stencil
per face; M5 puts both depths then both stencils). All HW-validated by change-one-Metal-state + `0x58000` diff.

| field | A18 offset | **M5 offset** | encoding (SAME as A18 unless noted) |
|---|---|---|---|
| depth/stencil-enable flags | `+0x34` | **`+0x134`** | enable cluster (`0x1c4e`→`0x1c52` when depth/stencil engaged) |
| depth-bias **enable** | `+0x34` bit17 | **`+0x16c` bit17** | + bias constant/slope/clamp still in tiler-param region |
| **depth FRONT** word | `+0x38` | **`+0x170`** | stencil-ref[7:0] · depth-write-DISABLE **bit21** · **compare[26:24]** |
| **depth BACK** word | `+0x40` | **`+0x174`** | same layout |
| **stencil FRONT** word | `+0x3c` | **`+0x178`** | wmask[7:0] · rmask[15:8] · **pass[18:16]·zfail[21:19]·sfail[24:22]·compare[27:25]** |
| **stencil BACK** word | `+0x44` | **`+0x17c`** | same layout (back independent of front — HW-validated) |
| **rasterizer** word | `+0x70` | **`+0x1a8`** | **cull[1:0]** none/front/back · **winding bit16** CW/CCW · **depth-clip/clamp[11:10]** |
| color write-mask / store class | `+0x5c` / `+0x50` | `+0x194` / `+0x128` | **RESOLVED (EXP-M5-13):** `+0x194` bits[3:0] = write mask, **STRAIGHT order R=bit0·G=bit1·B=bit2·A=bit3** (**REVERSE of A18**, which was bit-reversed R→bit3…A→bit0). HW-validated all 16 subsets. Bits[16:4]=`0x1fff` engage as a block iff the **alpha** channel is written (FS store-epilog); store-class enum `+0x128` co-varies (`0x4c0` alpha-stored / `0x480` not). |
| **blend-const-color needed** | `+0x10` bit6 | **`+0x130` bit6** | identical `0x40` bit; set by blendColor factors |
| blend/store program-class | `+0x08` | `+0x188` | FS-lowering-covariant enum |
| **occlusion mode** | `+0x8c` bit14 | **`+0x1c4` bit14** | Boolean=1 / Counting=0 |
| **occlusion result offset** | `+0xa0` (`<<14`) | **`+0x1d8`** (`byteOffset<<6`) | HW-validated 64→`0x1000`, 256→`0x4000` |

- **Enums identical to A18:** compare **0–7** = never/less/equal/lessEqual/greater/notEqual/greaterEqual/always
  (HW-validated all 8 on depth `+0x170`); stencil-op **0–7** = keep/zero/replace/incrClamp/decrClamp/invert/
  incrWrap/decrWrap (HW-validated all 8 on **each** of pass/zfail/sfail `+0x178`).
- **Blend is PROGRAMMABLE on M5 (confirmed).** Changing one blend factor (`srcAlpha`↔`srcColor`) rewrites
  **49 words of the fragment-shader BO** `0x10000000000` while the `0x58000` pool shows **0 diffs** — the
  same TBDR compile-blend-into-FS model as A18. `0x58000` carries only the orthogonal side-flags above.
  **Alpha-to-one has NO pool field** (FS-epilog only, as A18). Polygon **line fill** is HW-supported (sets a
  line-mode bit in `+0x16c`/`+0x170`bit18/`+0x188`).
- **Occlusion HW-validated:** Boolean wrote **1**, Counting wrote **4096** (64×64), offset honored.

## Attachment / render-target descriptor (EXP-M5-10) — same 3-segment chain, format word SAME
Primary single-RT attachment descriptor BO **`0x10000118000`** (A18: `0x10000110000`): 3 × **0x300-byte
segments LOAD(+0)/RENDER(+0x300)/STORE(+0x600)**, format word at **seg+0x20**, **format code = byte+0x21**
(= texture `byte1`) — identical formula to A18 (`descriptors/README-M5-deltas.md`). STORE/PBE component byte
+0x22 = r`0x00`/rgba`0xe4`/bgra`0xc6`. Verified bgra8/rgba8/r32f/rgb10a2/rgba32f/rgba16f.
- **Clear color** = float4 RGBA at **`0x10000118000+0x170`** (single RT) / **`0x10000128000+0x170`+k·0x10**
  (MRT). `loadAction≠Clear` zeroes it + clears the clear-enable bit (`+0x14`); `loadAction=Load` injects a
  surface-read; `storeAction=DontCare` poisons the store addr. Same behavior as A18.
- **MRT** ≥2 (or any MSAA) relocates color descriptors into tiler heap **`0x10000018000`** as **0x20-byte
  per-attachment records** (LOAD @`+0x220+k·0x20`, STORE @`+0x420+k·0x20`) — same k-stride as A18.

## Indirect / tessellation records (EXP-M5-10)
- **Indirect dispatch:** injects a **2nd CDM record + a grid-setup multiply helper shader** (grid is in
  threads, indirect args give threadgroups) — the driver must replicate the multiply. Same as A18.
- **Indirect draw opcodes** (VDM record, tiler stream `0x18000`): non-indexed **`0x6c04`** (direct `0x69c4`);
  indexed **`0x6c32`** (direct `0x69f2`). = A18's `0x6404`/`0x6432` shifted by the **same +0x0800** as the
  direct draw opcodes. Args pointer stored inline in the record; indexed keeps `0x40000001` config + `0xffff`
  restart comparand.
- **Tessellation = NATIVE hardware stage on M5** (like A18, NOT compute-emulated): `drawPatches` runs
  (STATUS=Completed) with **no CDM launch descriptor** (single graphics submit) and emits a distinct **VDM
  patch-dispatch record** in the tiler stream `0x18000` (record @~+0x80: config `+0x84`, USC bind addr `+0x88`,
  opcode/domain word `+0x8c`, **half-float factor-buffer pointer `+0x98`/`+0x9c`**). Half-float tessellation
  factor buffer as A18.

## Vertex-output-select (PPP) word — MOVED to `0x58000+0x158` (A18 +0x20), bits identical (EXP-M5-13)
Which VS system outputs are live. **Bit positions bit-identical to A18** (measured absolute LE values,
own MSL emitting each output; HW-validated STATUS=4):

| bit | output | evidence |
|---|---|---|
| bits[7:0] | clip-distance plane mask `(1<<N)-1` | N=1→`0x01` … N=8→`0xff` |
| bit18 | `point_size` | `+0x158`=`0x00040000` |
| bit19 | `viewport_array_index` | `+0x158`=`0x00080000` |
| **bit20** | `render_target_array_index` (**layer**) | `+0x158`=`0x00180000` (co-sets bit19); **NEW — A18 never measured** |

- **Layered-rendering enable = VDM `0x18000+0x20` bit6** (set by `[[render_target_array_index]]`; base
  `0x01000000`→`0x01000040`). **Unblocks OBJ-2 layered rendering.**
- **UVS scalar-output count** relocated **`0x58000+0x2c` (A18) → `0x58000+0x164` (M5)** = `4 + #scalar
  outputs` (position=4; +1 per point_size / vp-index / layer / clip-plane), mirrored at VDM `0x18000+0x28`.

## USC graphics bind grammar — same as A18, relocated (EXP-M5-13)
Fragment argument buffer **`0x10000248000` (A18) → `0x10000250000` (M5)`; grammar byte-identical to
A18/RT-2a. Header of 8-byte LE GPU VAs (high32 = `0x00000100`):

    +0x600  texture-array ptr      (-> first 0x20-byte texture descriptor)
    +0x608  sampler-array ptr      (= tex_ptr + num_textures*0x20)
    +0x610  buffer[0] VA           (each extra bound buffer adds an 8-byte slot: buffer[1]@+0x618)
    ...     0x20-byte texture descriptors, then 0x20-STRIDE sampler descriptors, then 0x60000000 term
    num_textures = (samp_ptr - tex_ptr)/0x20 ; num_samplers = (terminator - samp_ptr)/0x20

HW-clean over tex1/2/3 × samp1/2/3 × buf1/2. Uniform-preamble USC program relocated **`0x10000130000`
→ `0x10000138000`** (adding a resource rewrites the `0x67`-load program body; per-stage headers as A18).
The VS→FS varying-linkage *opcodes* are inherited from the M5 ISA work; only the count field (`+0x164`)
was re-measured here (a dedicated user-varying-reorder render was not re-run — minor residual).

## Mesh grid-dispatch record — RESOLVED (EXP-M5-13)
The EXP-M5-10 "abort" was a **harness bug** (it called the *tile* method
`newRenderPipelineStateWithDescriptor:options:reflection:` with a MESH descriptor; correct call =
`newRenderPipelineStateWithMeshDescriptor:options:reflection:`). Mesh renders correctly on M5 (STATUS=4).
- **Single unified graphics submit** — **no CDM launch BO** (`0x100000b0000` absent), as A18.
- **Mesh-grid-dispatch record** in tiler stream `0x18000`: opcode **`0x70000600`** (**UNSHIFTED** — same
  as A18, *not* +0x0800 like the draw opcodes), then **6 grid-dimension words** (object-grid + mesh-grid),
  then `0xc0000000` terminator — replacing the plain draw's `0x69c4` primitive record. Header length word
  `0x18000+0x18` grows (`0x4000002e`→`0x40000d2c`) for the larger object+mesh state block.
- UVB intermediate in tiler-heap **`0x10000018000`**; **no separate `0x100000f8000` BO on M5** (A18 had
  one) — the minimal mesh carries grid dims inline. (Payload-heavy / vertex-amplification meshes not probed.)

## Open (next cmdstream experiments)
- User-varying reorder HW-proof (A18 EXP-G1a analog) not re-run on M5; vertex-amplification and
  payload-heavy mesh records; `0x100000f8000`'s M5 role for complex meshes; the USC `+0x610`
  buffer-slot's inline-vs-indirect form beyond 2 buffers; sel-2 device-info struct.

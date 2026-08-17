# A18 Pro (G17P) Resource Descriptors

Clean-room documentation of the texture / sampler / buffer descriptor bit layouts a userspace
driver must emit. Learned by **change-one-Metal-parameter data tracing** (DATA-TRACE) of our own
programs' Tier-2 argument buffers + descriptor blocks (`tools/iotrace`), byte-diffing captures. No
Apple binary was disassembled. See `../../CLAUDE.md`. All fields HW-validated (diff-confirmed)
unless marked ⏳.

Binding model (from `../cmdstream/`): the Tier-2 **argument buffer** holds an 8-byte slot per bound
resource (in binding order, table at +0x14a0). **Buffers** store an inline GPU VA; **textures and
samplers** store a pointer to a descriptor block appended in the same BO. Descriptors below.

## Texture descriptor — 32 bytes (EXP-0015)
Little-endian; `wordN` = 32-bit word at byte 4N.

| field | location | encoding |
|---|---|---|
| **type** | byte0 bits[0:2] | 1D=0, 2D=2, 2DArray=3, 2DMS=4, 3D=5, Cube=6 (1D/CubeArray/MSArray ⏳ untested) |
| **channel arrangement** | byte0 hi-nibble | with byte1 forms the format |
| **format numeric type + size** | byte1 = `numtype<<5 \| sizeclass` | numtype: unorm=0, snorm=1, uint=2, sint=3, float=4. (Full 31-format table in EXP-0015 RESULTS.) |
| **swizzle** | word0 bits[16:27] | 4×3-bit destination order R,G,B,A; codes R=0,G=1,B=2,A=3,One=4,Zero=5 |
| **width−1** | word0[28:31] (low 4) ‖ word1[0:9] (high 10) = **14-bit**, max 16384 | RT-3: NOT 12-bit. HW-validated to 16384 on 2D/2DArray/Cube; 3D reaches the 2048 axis limit (EXP-M4-08) |
| **height−1** | word1[10:23] (**14-bit**, max 16384) | RT-3; reached 16384 on 2DArray (EXP-M4-08) |
| **sampleCount** | word1 bits[24:25] | `log2(n)−1` |
| **base VA** | word2 ‖ word3 bits[0:11] | **`VA >> 4`** (16-byte units) — HW-confirmed by VA-offset tracking |
| **sRGB** | word3 bit12 | orthogonal flag (not a format code) |
| **depth / arrayLen − 1** | word3 bits[14:24] (11-bit, max 2048) | shared field, type-dependent; word3 bits[30:31] are layout flags. HW-validated on 2DArray (arrayLen 2048→`0x7ff`) & 3D (depth 2048) — EXP-M4-08 |
| **mipCount − 1** | byte +0x16 | |
| mipmapped | word1 bit26 | set when mipmapped (see `../tiling/`) |
| compression aux present | word1 bit27 | set when the texture has a compression metadata buffer |
| aux layout metadata | word3 bit31 | set by compression **or** mipmaps |
| **secondary VA (aux buffer)** | word4 ‖ word5[0:11] | `(word4 \| word5[0:11]<<32) << 4` — compression metadata; see `../tiling/` §4 |
| linear stride | word3 bits[14:] | buffer-backed only: `bytesPerRow = (word3[14:]+1)×16` (0 for twiddled) |

Independent knobs: `bgra8` = `rgba8` + swizzle; `a8` = `r8` + swizzle; `depth32float` = `r32float`
code. **Format, swizzle, sRGB, and numeric-type are orthogonal** (Vulkan-shaped) — good for a Vulkan
driver.

## Sampler descriptor — 8 bytes (EXP-0015)
64-bit little-endian bitfield. **Note (M1 reconciliation):** the sampler *descriptor content* is **8 bytes**, but in
an argument buffer each sampler occupies a **0x20-byte (32-byte) slot/stride** (the 8-byte descriptor left-packed,
remainder reserved) — so `docs/cmdstream`'s `num_samplers=(term−samp)/0x20` (stride) and this 8-byte descriptor size
are both correct and describe different things (slot stride vs payload size).

| field | bits | encoding |
|---|---|---|
| lodMin | [0:12] | ×64 (6 frac bits); HW-validated 0.25/0.5/1.5/13.9. Metal clamps to lodMax ⇒ saturates 14.0 (EXP-M4-08) |
| lodMax | [13:19] | ×8 (3 frac bits); HW-validated 0.25/1.5/3.0/13.9. **Metal saturates at 14.0** (field is 7-bit ⇒ 15.875 max, but >14.0 Metal-unreachable) |
| maxAnisotropy | [20:22] | `log2`: 1/2/4/**8**/16→0/1/2/3/4 (8× HW-validated). 3-bit field could encode 128× but **Metal clamps >16 → 1×** (not 16×); >16× untested |
| magFilter | 23 | nearest/linear |
| minFilter | 25 | nearest/linear |
| mipFilter | [27:28] | none / nearest / linear |
| addr S / T / R | [29:31] / [32:34] / [35:37] | edge=0, repeat=1, mirror=2, clampZero/clampBorder=3, mirrorClampEdge=5. Codes 4/6/7 Metal-unreachable (untested — DESC-4) |
| unnormalized coords | 38 | |
| compare | sense bit39 + test bits[40:42] | all 8 Metal compare funcs (table in EXP-0015 RESULTS) |
| **border color** | byte7 bits[5:6] | **2-bit preset only** (transparent/black/white) |

## Buffer descriptor (EXP-0015, EXP-M4-08)
A plain `device T*` binding is a bare **inline 8-byte GPU VA** in the argument-buffer slot; **no
length/format word**, hence **no descriptor-level bounds check**. HW-PROBE (EXP-M4-08 DESC-7):
out-of-bounds reads of a 16-element buffer at indices 16 … **268435456 (≈1 GiB past)** all return
**`0.0` with the command buffer completing (no fault)** — OOB device-buffer reads yield zero by GPU-VM
behavior, not by a bound. A Vulkan `robustBufferAccess` implementation gets non-faulting zero-return
for free but cannot rely on a descriptor bound (there is none) for exact semantics.

**Typed / texel buffer (`texture_buffer<T>`)** is the exception: it is a **full 32-byte texture
descriptor**, not a bare VA (EXP-M4-08 DESC-7). It rides the 1D-linear texture path: texture-type
field, format code `byte1`, `width−1 = word0[28:31]‖word1[0:9]`, base **VA>>4**, and **linear stride in
word3[14:]** = `(v+1)×16` = bytesPerRow (e.g. r32float ×256 → word3[14:]=63 → 1024). word0 top nibble
`0xf` + `byte0` bit5 cleared (the same component-explicit form as the PBE / RT-attachment word below).

## Capability notes (extrapolate-and-test → `../hypotheses.md`)
- **Border color is HW-limited to 3 presets** — no arbitrary RGBA in the 8-byte sampler ⇒ Vulkan custom
  border color must be **software-emulated**.
- **`clampToZero` == `clampToBorder(transparent-black)`** — one HW address mode, not two.
- **Anisotropy field is 3-bit log2** (could encode 128×); 8× and 16× HW-validated, but **Metal clamps
  >16 back to 1×** (not 16×), so >16× stays untested — needs descriptor injection, not just a Metal knob
  (EXP-M4-08 DESC-3/DESC-4). Likewise **lodMax > 14.0** is Metal-unreachable though the 7-bit field holds 15.875.
- All 8 compare functions, full channel swizzle, and sRGB/format/numeric-type orthogonality are native.

Source: `experiments/EXP-0015-descriptors/` (`tvar.m`, `descx.py`).

Full tables: [format-table.md](format-table.md)

## Sparse / render-target / float-filtering / bindless samplers (EXP-O2B)
- **Sparse textures:** descriptor carries a **sparse-tier flag** (byte0 hi-nibble: `(byte0 & ~0x20)|0x10`; word1
  bits[28:29] set). **Tile residency is NOT in the descriptor** — it lives in the GPU page table (kernel/firmware-
  managed; `updateTextureMapping` leaves the descriptor byte-identical). Sparse tile = 16 KiB always. Placement/
  automatic **heaps are descriptor-transparent** (only base/aux VA point into the heap).
- **Render-target ("PBE") is NOT a per-texture descriptor bit** — `ShaderRead`/`+RenderTarget`/`+ShaderWrite`/
  `+PixelFormatView` give a byte-identical sampled descriptor; render-target state is structural via the attachment
  path (`../pipeline/`, EXP-0021), whose packed pixel-format word is **derived** from this descriptor's
  `byte0`/`byte1`/`swizzle` (exact formula: "Render-target attachment format word" below). Only side-effect:
  **`ShaderWrite` AND `PixelFormatView` disable lossless compression** (clear word1 bit27/word3 bit31/drop word4);
  RenderTarget stays compressed. (Extends `../tiling/` §4.1.)
- **32-bit float texture filtering is unconditional on Apple9** — no descriptor "filterable" flag; nearest vs linear
  is just the sampler magFilter(bit23)/minFilter(bit25) bits. HW-validated (r32f linear interpolates).
- **Bindless sampler-heap:** a sampler in an argument buffer = an **8-byte little-endian `gpuResourceID`** (a small
  sequential integer = index into a **device-global sampler table**, capacity 500000; stride 8). Distinct from the
  Metal-auto argument buffer's 8-byte pointer-to-descriptor (EXP-0011); shader-computed dynamic index works. Samplers
  are not `MTLResource`s (no residency).

## Storage-image (PBE) descriptor & per-access binding (EXP-G1b)
A texture bound `access::write`/`read_write` uses a **distinct 32-byte "PBE" descriptor** (not the sampled one):
- **Shared with sampled:** byte0/byte1 (texture-type + format numtype/sizeclass, same `format-table` codes); base
  **`VA>>4`** = word2‖word3[0:11].
- **Differs:** **width−1 = word0[24:31]‖word1[0:5]**, **height−1 = word1[6:19]** (a different split than the sampled
  descriptor's); word0[16:27] is a format-derived component field (not the 4×3 swizzle); **no lossless-compression aux**
  (word3 bit31 clear, word4/5 = 0 — ShaderWrite disables compression). Linear stride = `((word3>>12)+1)×16`.
- **Per-access-qualifier binding:** each image access consumes a descriptor slot **+ an 8-byte control-word slot**.
  `access::read` → sampled descriptor + read-control; `access::write` → PBE descriptor + write-control;
  **`access::read_write` binds TWO descriptors** (a compression-disabled read texture desc + a PBE desc). HW-validated.
- **PBE width/height reach the full 14 bits** (EXP-M4-08 DESC-7): width−1 = word0[24:31]‖word1[0:5]
  HW-validated to **16384** (16384×4); height−1 = word1[6:19] to **16384** (4×16384). The width-high
  field (word1[0:5]), previously *inferred* (EXP-G1b tested ≤256), is now HW-validated.
- **MRT live-control cross-check (EXP-0048, M4):** two exact repetitions place
  LOAD records at `0x10000018200+0x20+k·0x20` and STORE/PBE records at
  `+0x220+k·0x20` for RGBA8, BGRA8, sRGB, R32Float, R32Uint and mixed MRT.
  For the tested records, low 40 bits of the qword at `+0x08`, shifted left four,
  reconstruct the exact authored target VA. sRGB retains RGBA8's low-24 format
  value but changes the opaque upper packed control. Load/store action and blend
  controls leave the PBE arena unchanged; these controls do not decode the
  remaining upper field or establish a Linux packing rule.

## Render-target attachment format word (EXP-M4-08 DESC-1) — derived from the sampled codes

The 3-segment RT attachment chain (`../pipeline/`, `../cmdstream/`; LOAD/RENDER/STORE) carries a packed
**format word at seg+0x20** that is fully **derivable from this descriptor's fields** (`byte0`, `byte1`,
`swizzle`). Swept across **all 46 renderable formats** (M4 + A18 identical):

**LOAD / RENDER word (seg+0x20):**
```
word = (0xf << 28) | (swizzle[11:0] << 16) | (byte1 << 8) | (byte0 & ~0x20)
```
| attachment byte | content |
|---|---|
| byte+0x20 | `byte0 & ~0x20` (texture-type + arrangement, bit5 cleared) |
| **byte+0x21** | **`byte1` = the format code** (`numtype<<5 \| sizeclass`) — the real format byte |
| byte+0x22 | `swizzle[0:7]` (low byte of the 12-bit swizzle) |
| byte+0x23 | `0xf0 \| swizzle[8:11]` |

**⚠ Correction:** `../pipeline/README.md` and `../cmdstream/` **previously** stated "byte+0x22 = format" (now corrected to +0x21). That was
**wrong** — the format code is at **byte+0x21**; byte+0x22 is the swizzle low byte. The old claim only
coincided for **bgra8** (whose swizzle-low `0x0a` equals its format code `0x0a`). For rgba8 byte+0x22 =
`0x88` (swizzle), not the format. *(These are not my files to edit — flag for the orchestrator.)*

**STORE word (seg2+0x20)** is a PBE descriptor: `((width−1)&0xff)<<24 | component<<16 | byte1<<8 |
(byte0 & ~0x20)`, with `height−1 << 6` in word1. Format code again at **byte+0x21**; `component` is the
PBE component byte (r=`0x00`, rg=`0x04`, rgba=`0xe4`, bgra=`0xc6`).

**Placement:** ≥64bpp RTs relocate the STORE/RENDER descriptors out of `0x10000110000`, and 128bpp
(rgba32*) relocate the whole attachment to the tiler heap `0x10000018200` / `0x10000120000`, but the
**format-word values are identical** to the formula — so every renderable format's attachment word is
derivable; only the BO it lands in changes with imageblock size.

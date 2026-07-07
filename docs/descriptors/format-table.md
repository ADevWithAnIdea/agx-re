# A18 Pro (G17P) Descriptor Format & Code Tables (self-contained)

Complete, self-contained code tables for the texture and sampler descriptors documented in
`README.md`. **This file defers to no experiment** — every value below is reproduced in full here.
All values are HW-validated (localised by a clean single-Metal-parameter byte-diff and, where noted,
confirmed by splice-and-run) unless explicitly marked **untested** / *inferred*.

Provenance: `experiments/EXP-0015-descriptors/RESULTS.md` (texture/sampler/buffer descriptors) and
`experiments/EXP-0017-tiling/RESULTS.md` (linear stride, secondary/aux VA, compression, block-format
layout). Clean-room category: DATA-TRACE + OWN-SHADER + HW-PROBE. No Apple binary was disassembled.

Byte/word convention: descriptor bytes numbered from the start of the block; `wordN` = 32-bit
little-endian word at byte `4N`; `byteN` = byte at offset N. The 16-bit **format code** = `(byte1<<8) | byte0`.

---

## 1. Texture-type codes (word0 bits[0:2] = byte0 low nibble)

| type | code | status |
|---|---|---|
| 1D | `0` | HW-validated (EXP-0015 `desc_type_1d_fix`) |
| 2D | `2` | HW-validated (`diff_type`) |
| 2DArray | `3` | HW-validated |
| 2DMultisample | `4` | HW-validated (`ms_2`/`ms_4`) |
| 3D | `5` | HW-validated (`d3d_*`) |
| Cube | `6` | HW-validated |
| 1DArray | (likely `1`) | **untested** — extrapolated from the 1D=0/2DArray=3 pattern |
| CubeArray | (likely `7`) | **untested** |
| 2DMultisampleArray | (unassigned) | **untested** |

Codes `1` and `7` are not confirmed; EXP-0015 §5 recommends extrapolating 1DArray=1, CubeArray=7.

---

## 2. Pixel-format → descriptor-code table (31 formats, HW-validated)

Format identity = the 16-bit value `(byte1<<8) | byte0`. `byte0` bits[0:2] carry the **texture type**
(shown as `2` = 2D in these captures); `byte0` high nibble = **channel arrangement**. `byte1 = (numtype<<5) | sizeclass`.

| MTLPixelFormat | byte0 | byte1 | numtype | sizeclass | notes |
|---|---|---|---|---|---|
| r8unorm | `0x22` | `0x00` | unorm | `0x00` | |
| r8snorm | `0x22` | `0x20` | snorm | `0x00` | |
| r8uint | `0x22` | `0x40` | uint | `0x00` | |
| r8sint | `0x22` | `0x60` | sint | `0x00` | |
| a8unorm | `0x22` | `0x00` | unorm | `0x00` | = r8 code + swizzle (000R→A) |
| rg8unorm | `0xa2` | `0x02` | unorm | `0x02` | |
| rg8uint | `0xa2` | `0x42` | uint | `0x02` | |
| r16unorm | `0x62` | `0x02` | unorm | `0x02` | |
| r16uint | `0x62` | `0x42` | uint | `0x02` | |
| r16float | `0x62` | `0x82` | float | `0x02` | |
| rgba8unorm | `0x22` | `0x0a` | unorm | `0x0a` | |
| rgba8snorm | `0x22` | `0x2a` | snorm | `0x0a` | |
| rgba8uint | `0x22` | `0x4a` | uint | `0x0a` | |
| rgba8sint | `0x22` | `0x6a` | sint | `0x0a` | |
| bgra8unorm | `0x22` | `0x0a` | unorm | `0x0a` | = rgba8 code + B↔R swizzle |
| rgba8unorm_srgb | `0x22` | `0x0a` | unorm | `0x0a` | = rgba8 code + sRGB flag (word3 bit12) |
| bgra8unorm_srgb | `0x22` | `0x0a` | unorm | `0x0a` | = rgba8 code + swizzle + sRGB flag |
| rgb10a2unorm | `0xa2` | `0x09` | unorm | `0x09` | packed 10/10/10/2 |
| bgr10a2unorm | `0xa2` | `0x09` | unorm | `0x09` | = rgb10a2 code + swizzle |
| rg11b10float | `0x62` | `0x89` | float | `0x09` | packed 11/11/10 |
| rgb9e5float | `0xe2` | `0x89` | float | `0x09` | packed 9/9/9/5 shared-exp |
| r32uint | `0x62` | `0x48` | uint | `0x08` | |
| r32sint | `0x62` | `0x68` | sint | `0x08` | |
| r32float | `0x62` | `0x88` | float | `0x08` | |
| depth32float | `0x62` | `0x88` | float | `0x08` | = r32float code (depth-ness NOT in format field) |
| rg16float | `0xe2` | `0x88` | float | `0x08` | |
| rg32float | `0x62` | `0x8c` | float | `0x0c` | |
| rgba16unorm | `0xa2` | `0x0c` | unorm | `0x0c` | |
| rgba16uint | `0xa2` | `0x4c` | uint | `0x0c` | |
| rgba16float | `0xa2` | `0x8c` | float | `0x0c` | |
| rgba32uint | `0x22` | `0x4e` | uint | `0x0e` | |
| rgba32float | `0x22` | `0x8e` | float | `0x0e` | |

**31 formats tabulated.** The **numtype** nibble is fully orthogonal — HW-validated across all four
numeric types for r8 / r16 / r32 / rgba8 (unorm/snorm/uint/sint) and float where applicable.

### 2a. Numeric-type field (`byte1` bits[5:7], i.e. the `numtype<<5` term)

| numtype | code (pre-shift) |
|---|---|
| unorm | `0` |
| snorm | `1` |
| uint | `2` |
| sint | `3` |
| float | `4` |

### 2b. Size-class field (`byte1` bits[0:4]) — classifies total pixel width / packing

| sizeclass | meaning |
|---|---|
| `0x00` | 8 bpp |
| `0x02` | 16 bpp |
| `0x08` | 32 bpp, plain (single 32-bit channel, e.g. r32) |
| `0x09` | 32 bpp, packed (10/10/10/2, 11/11/10, 9/9/9/5) |
| `0x0a` | 32 bpp, 4×8 |
| `0x0c` | 64 bpp |
| `0x0e` | 128 bpp |

`byte0` high nibble disambiguates **channel arrangement** at a given size class (e.g. 1×32 `0x6` vs
2×16 `0xe` vs 4×8 `0x2`). Its internal bit-split was not decoded (EXP-0015 §5); the format→code table
is complete without it.

---

## 3. Swizzle codes (word0 bits[16:27] = 4×3-bit, destination order R,G,B,A)

| code | `0` | `1` | `2` | `3` | `4` | `5` |
|---|---|---|---|---|---|---|
| channel | Red | Green | Blue | Alpha | One (1.0) | Zero (0.0) |

Identity (RGBA) = `R,G,B,A` = codes `0,1,2,3`. HW-validated with `bgra`(2,1,0,3), `rrrr`(0,0,0,0),
`aaaa`(3,3,3,3), `000a`(5,5,5,3), `1111`(4,4,4,4), `gbar`(1,2,3,0). Codes 6,7 untested.

**Orthogonality (HW-validated):** format code, swizzle, sRGB flag (word3 bit12), and numeric type are
**independent knobs** (Vulkan-shaped). `bgra8 = rgba8 + swizzle`; `a8 = r8 + swizzle`;
`*_srgb = base + sRGB flag`; `depth32float = r32float` code.

---

## 4. Sampler descriptor — 8-byte field map (EXP-0015)

Entire descriptor is 8 bytes (a hard capacity limit); bit positions are from the block start.
Base (non-comparison) sampler bytes: `00 00 0e 00 80 07 00 00`.

| field | bits | encoding |
|---|---|---|
| lodMinClamp | [0:12] | `round(lodMin × 64)` (6 fractional bits) |
| lodMaxClamp | [13:19] | `round(lodMax × 8)` (3 fractional bits); FLT_MAX/default saturates to 14.0 |
| maxAnisotropy | [20:22] | `log2(maxAnisotropy)`: 1→0, 2→1, 4→2, 16→4 (3-bit field → encodes up to 128×) |
| magFilter | 23 | 0 = nearest, 1 = linear |
| minFilter | 25 | 0 = nearest, 1 = linear |
| mipFilter | [27:28] | 0 = none, 1 = nearest, 2 = linear |
| sAddressMode | [29:31] | see §4a |
| tAddressMode | [32:34] | see §4a |
| rAddressMode | [35:37] | see §4a |
| unnormalizedCoordinates | 38 | 1 = unnormalized coords |
| compareFunc — sense | 39 | invert bit (see §4b) |
| compareFunc — test | [40:42] | see §4b |
| borderColor | [61:62] (byte7 bits5-6) | see §4c |

### 4a. Sampler address-mode codes (3-bit, per axis; HW-validated)

| code | mode |
|---|---|
| `0` | clampToEdge |
| `1` | repeat |
| `2` | mirrorRepeat |
| `3` | clampToZero **and** clampToBorderColor (single HW mode — see note) |
| `5` | mirrorClampToEdge |

Codes `4`, `6`, `7` are **untested** (open probe candidates). **Note:** `clampToZero` and
`clampToBorderColor` both map to code `3`; there is exactly one HW clamp-to-border address mode.
`clampToZero` is the special case where the border color preset is transparent-black (see §4c).

### 4b. Sampler compare-function codes (HW-validated)

Compare = (`sense` = bit39) + (`test` = bits[40:42]). The `test` field groups complementary
predicates; the `sense` bit picks the direction ("predicate + invert" encoding).

| Metal compareFunc | sense | test | Metal compareFunc | sense | test |
|---|---|---|---|---|---|
| never | `1` | `7` | always | `0` | `7` |
| less | `0` | `5` | greater | `1` | `5` |
| lessEqual | `0` | `4` | greaterEqual | `1` | `4` |
| equal | `0` | `6` | notEqual | `1` | `6` |

Default (non-comparison) sampler encodes `never` = (sense `1`, test `7`). All 8 Metal compare
functions are natively expressible → shadow/PCF compare is fully HW-supported.

### 4c. Sampler border-color codes (byte7 bits[5:6]; HW-validated)

| code | preset |
|---|---|
| `0` | transparent-black (0,0,0,0) |
| `1` | opaque-black (0,0,0,1) |
| `2` | opaque-white (1,1,1,1) |

**Only these 3 presets exist** — the 8-byte sampler has **no room for an arbitrary RGBA border
color**. Vulkan `VK_EXT_custom_border_color` is not expressible here and must be software-emulated
(no separate border-color table was seen in these captures). Code `3` untested.

---

## 5. Texture descriptor — 32-byte field map (EXP-0015 + EXP-0017)

Reproduced here so this table file is standalone. Little-endian; `wordN` = word at byte `4N`.

| field | location | encoding |
|---|---|---|
| texture type | word0 bits[0:2] | §1 |
| format channel arrangement | word0 bits[4:7] (byte0 hi nibble) | §2 |
| format code | word0 bits[8:15] (byte1) | `(numtype<<5) \| sizeclass`, §2 |
| swizzle | word0 bits[16:27] | §3 |
| width − 1 | word0 bits[28:31] ‖ word1 bits[0:7] (12 bits) | value = width − 1 |
| height − 1 | word1 bits[10:...] | value = height − 1 |
| sample count (MS) | word1 bits[24:25] | `log2(samples) − 1` (2→0, 4→1) |
| mipmapped flag | word1 bit26 | set when mipmapLevelCount > 1 |
| compression-aux present | word1 bit27 | set when a compression metadata buffer is present (§6) |
| texture base VA | word2 ‖ word3 bits[0:11] | **VA >> 4** (16-byte units); word2 = VA bits[4:35], word3[0:11] = bits[36:47] |
| sRGB flag | word3 bit12 | 1 = sRGB decode (orthogonal to format) |
| depth (3D) / arrayLength − 1 | word3 bits[14:...] | value − 1 (shared field; type-dependent) |
| aux layout metadata flag | word3 bit31 | set by compression **or** mipmaps |
| mipmapLevelCount − 1 | word5 bits[16:19] (byte +0x16) | value = mips − 1 |
| secondary VA (aux buffer) | word4 ‖ word5 bits[0:11] | `(word4 \| (word5[0:11]<<32)) << 4` (16-byte units), §6 |
| linear bytesPerRow | word3 bits[14:...] | **buffer-backed only** — see §7 (context-shares the depth/array field) |

Buffer descriptor: a `device T*` binding is a **bare inline 8-byte little-endian GPU VA** in the
argument-buffer slot — **no length or format word** (EXP-0015 §3).

---

## 6. Compression aux / secondary-VA encoding (EXP-0017)

| descriptor bit/field | meaning |
|---|---|
| word1 bit27 | compression aux present |
| word3 bit31 | texture has auxiliary layout metadata (set by compression **or** mipmaps) |
| word4 ‖ word5[0:11] | secondary (aux) VA, encoded `(word4 \| (word5[0:11]<<32)) << 4` — 16-byte units, exactly like the base VA |

- **Trigger:** compression aux present iff the texture has **no ShaderWrite usage** AND the image is
  ≥ ~one 16×16 tile (16×16 on, 8×8/4×4 off, for rgba8). ShaderWrite (read-write) textures are never
  compressed at any size.
- **Aux placement/size:** immediately after the main image in the same allocation
  (`secondaryVA = baseVA + paddedImageBytes`); `aux_bytes = image_bytes / 128` = 1 state byte per
  8×4-texel block, in Morton-of-blocks order.
- **Per-block state-byte values (observed):** `0x03` = compressed constant, `0x15` = compressed
  smooth gradient, `0x7f` = incompressible / stored raw. The compressed block **codec** and the exact
  numeric meaning of state values are **not decoded** (opaque; documented disable-fallback exists).

---

## 7. Linear (buffer-backed) stride encoding (EXP-0017)

For buffer-backed / linear textures (`newTextureWithDescriptor:offset:bytesPerRow:`):

> **bytesPerRow = (word3[14:] + 1) × 16**  (stride in 16-byte units, minus 1).

HW-validated: bpr 128/256/512/800 ⇒ word3[14:] = 7/15/31/49. Twiddled (optimal-layout) textures leave
word3[14:] = 0 (Morton layout is implicit; no stride stored). This is the **same field** the texture
descriptor otherwise uses for depth/arrayLength − 1 — its meaning is context-dependent per texture kind.

---

## 8. Formats / codes the experiments did NOT test (untested)

Reproduced so an implementer knows the exact boundary of what is validated:

- **Block-compressed formats — BC / ASTC / ETC:** not probed (EXP-0017 §5). By construction they are
  expected to twiddle over *blocks* (the same Morton curve with the block's byte size as the effective
  bpp), but this is a stated extrapolation, **not** HW-validated, and their descriptor format codes
  (byte0/byte1) are **untested**.
- **Depth/stencil-specific formats beyond `depth32float`:** only `depth32float` (= r32float code) is
  confirmed. `depth16unorm`, `stencil8`, `x24_stencil8`, `x32_stencil8` are **untested**.
  (`depth24stencil8` is reported unsupported on this HW — Z/S are separate resources —
  per `../hardware-overview.md` §3.)
- **16-bit normalized variants not in §2:** `r16snorm`, `rg16unorm`, `rg16snorm`, `rgba16snorm` are
  **untested** (only `r16unorm`, `rgba16unorm`, and the 16-float variants were captured).
- **Extended-range / wide-gamut packed formats** (e.g. `bgr10_xr`, `bgra10_xr`, `bgra10_xr_srgb`) and
  **YUV / video formats:** **untested**.
- **Texture types 1DArray / CubeArray / 2DMultisampleArray** (§1) and **address-mode codes 4/6/7**,
  **swizzle codes 6/7**, **border-color code 3** (§3/§4): **untested**.
- **Anisotropy > 16×:** the field is 3-bit `log2` (can encode up to 128×) but Metal caps at 16×;
  values above 16× are **untested** on hardware.

Full tables above are for the **uncompressed color/integer formats actually captured**; anything not
listed in §2 has an untested descriptor code.

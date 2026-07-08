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
| `0x00` | 8 bpp (1×8) |
| `0x02` | 16 bpp (1×16 / 2×8 / packed 3-ch 5/6/5) |
| `0x03` | 16 bpp, **4-channel packed** (4/4/4/4, 5/5/5/1, 1/5/5/5) — *(new, EXP-M4-08)* |
| `0x08` | 32 bpp, plain (single 32-bit channel r32, or 2×16) |
| `0x09` | 32 bpp, packed (10/10/10/2, 11/11/10, 9/9/9/5, bgr10_xr) |
| `0x0a` | 32 bpp, 4×8 |
| `0x0c` | 64 bpp (2×32 / 4×16 / bgra10_xr) |
| `0x0e` | 128 bpp (4×32) |
| `0x10` | **YUV 4:2:2** (gbgr422 / bgrg422) — *(new, EXP-M4-08)* |
| `0x14` | PVRTC (legacy) |
| `0x16` | ETC2 / EAC (RG11 = `0x17`) |
| `0x18`–`0x1b` | ASTC (block-shape grid below) |
| `0x1d` | BC1–BC4 (BC1/BC4 = 8-byte blocks) |
| `0x1e` | BC5 / BC6H / BC7 (16-byte blocks) |

### 2c. Channel-arrangement field (`byte0` bits[4:7]) — **DECODED** (EXP-M4-08)

The `byte0` high nibble is the **channel-arrangement sub-index**. Decode (HW-validated, M4+A18, all 96
formats — `experiments/EXP-M4-08-descriptor-coverage/analysis/format_decode.txt`):

```
byte0 = arrangement[4:7] | texture_type[0:2]
```
- **`byte0` bit4 (0x10) is always 0** in every capture — the arrangement is effectively the **3-bit
  value `byte0[5:7]`** (so the hi-nibble only ever takes `{0,2,4,6,8,a,c,e}`, i.e. even values, and in
  practice `{2,6,a,e}` for color/compressed with bit5 set, `{0,4}` for YUV with bit5 clear).
- It is a **per-sizeclass sub-index**: it disambiguates the distinct channel arrangements that share one
  sizeclass. It is **not** an independent channel-count field (e.g. arr `1` = both r8 at `0x00` and
  rgba8 at `0x0a`; the sizeclass carries the rest of the identity). With the complete table in §2d, no
  format needs guessing — read `byte0[5:7]` + `sizeclass` from the table.

**ASTC block-shape grid** (all 14 LDR shapes decoded — previously 8/14 untested). `arr = byte0[5:7]`:

| sizeclass | arr=1 | arr=3 | arr=5 | arr=7 |
|---|---|---|---|---|
| `0x18` | ASTC 4×4 | 5×4 | 5×5 | 6×5 |
| `0x19` | 6×6 | 8×5 | 8×6 | 8×8 |
| `0x1a` | 10×5 | 10×6 | 10×8 | 10×10 |
| `0x1b` | 12×10 | 12×12 | *(unused)* | *(unused)* |

HDR-ASTC = the same block-shape code with **numtype = float** (e.g. astc_4x4_hdr `byte1 = 0x98`);
sRGB-ASTC = the same code + word3 bit12. BC families likewise use `arr` to pick within a sizeclass
(e.g. `0x1e`: bc5 arr1, bc6h_rgbfloat arr3, bc6h_rgbufloat arr5, bc7 arr7).

### 2d. Complete captured format → code table (96 formats, HW-validated M4 + A18)

Every `MTLPixelFormat` the M4/A18 accept, captured by binding it as a sampled texture and reading the
appended descriptor (`experiments/EXP-M4-08-descriptor-coverage/raw/format_capture.txt`). `byte0[5:7]`
is the arrangement sub-index (§2c). sRGB variants share the base code + word3 bit12 (not shown). This
supersedes the 31-/60-format tables in §2 / "Extended format codes" — it is the authoritative set.

| MTLPixelFormat | byte0 | byte1 | arr[5:7] | numtype | sizeclass |
|---|---|---|---|---|---|
| r8unorm | `0x22` | `0x00` | 1 | unorm | `0x00` |
| r8snorm | `0x22` | `0x20` | 1 | snorm | `0x00` |
| a8unorm | `0x22` | `0x00` | 1 | unorm | `0x00` |
| rg8unorm | `0xa2` | `0x02` | 5 | unorm | `0x02` |
| rg8snorm | `0xa2` | `0x22` | 5 | snorm | `0x02` |
| rgba8unorm | `0x22` | `0x0a` | 1 | unorm | `0x0a` |
| rgba8snorm | `0x22` | `0x2a` | 1 | snorm | `0x0a` |
| bgra8unorm | `0x22` | `0x0a` | 1 | unorm | `0x0a` |
| b5g6r5unorm | `0xe2` | `0x02` | 7 | unorm | `0x02` |
| a1bgr5unorm | `0x62` | `0x03` | 3 | unorm | `0x03` |
| abgr4unorm | `0x22` | `0x03` | 1 | unorm | `0x03` |
| bgr5a1unorm | `0xa2` | `0x03` | 5 | unorm | `0x03` |
| r16unorm | `0x62` | `0x02` | 3 | unorm | `0x02` |
| r16snorm | `0x62` | `0x22` | 3 | snorm | `0x02` |
| rg16unorm | `0xe2` | `0x08` | 7 | unorm | `0x08` |
| rg16snorm | `0xe2` | `0x28` | 7 | snorm | `0x08` |
| rgba16unorm | `0xa2` | `0x0c` | 5 | unorm | `0x0c` |
| rgba16snorm | `0xa2` | `0x2c` | 5 | snorm | `0x0c` |
| r16float | `0x62` | `0x82` | 3 | float | `0x02` |
| rg16float | `0xe2` | `0x88` | 7 | float | `0x08` |
| rgba16float | `0xa2` | `0x8c` | 5 | float | `0x0c` |
| r32float | `0x62` | `0x88` | 3 | float | `0x08` |
| rg32float | `0x62` | `0x8c` | 3 | float | `0x0c` |
| rgba32float | `0x22` | `0x8e` | 1 | float | `0x0e` |
| rgb10a2unorm | `0xa2` | `0x09` | 5 | unorm | `0x09` |
| bgr10a2unorm | `0xa2` | `0x09` | 5 | unorm | `0x09` |
| rgb10a2uint | `0xa2` | `0x49` | 5 | uint | `0x09` |
| rg11b10float | `0x62` | `0x89` | 3 | float | `0x09` |
| rgb9e5float | `0xe2` | `0x89` | 7 | float | `0x09` |
| bgr10_xr | `0xa2` | `0xa9` | 5 | xr | `0x09` |
| bgra10_xr | `0xe2` | `0xac` | 7 | xr | `0x0c` |
| r8uint | `0x22` | `0x40` | 1 | uint | `0x00` |
| rg8uint | `0xa2` | `0x42` | 5 | uint | `0x02` |
| rgba8uint | `0x22` | `0x4a` | 1 | uint | `0x0a` |
| r16uint | `0x62` | `0x42` | 3 | uint | `0x02` |
| rg16uint | `0xe2` | `0x48` | 7 | uint | `0x08` |
| rgba16uint | `0xa2` | `0x4c` | 5 | uint | `0x0c` |
| r32uint | `0x62` | `0x48` | 3 | uint | `0x08` |
| rg32uint | `0x62` | `0x4c` | 3 | uint | `0x0c` |
| rgba32uint | `0x22` | `0x4e` | 1 | uint | `0x0e` |
| r8sint | `0x22` | `0x60` | 1 | sint | `0x00` |
| rg8sint | `0xa2` | `0x62` | 5 | sint | `0x02` |
| rgba8sint | `0x22` | `0x6a` | 1 | sint | `0x0a` |
| r16sint | `0x62` | `0x62` | 3 | sint | `0x02` |
| rg16sint | `0xe2` | `0x68` | 7 | sint | `0x08` |
| rgba16sint | `0xa2` | `0x6c` | 5 | sint | `0x0c` |
| r32sint | `0x62` | `0x68` | 3 | sint | `0x08` |
| rg32sint | `0x62` | `0x6c` | 3 | sint | `0x0c` |
| rgba32sint | `0x22` | `0x6e` | 1 | sint | `0x0e` |
| depth32float | `0x62` | `0x88` | 3 | float | `0x08` |
| depth16unorm | `0x62` | `0x02` | 3 | unorm | `0x02` |
| stencil8 | `0x22` | `0x40` | 1 | uint | `0x00` |
| depth32float_stencil8 (depth aspect) | `0x62` | `0x88` | 3 | float | `0x08` |
| x32_stencil8 (= stencil aspect) | `0x22` | `0x40` | 1 | uint | `0x00` |
| gbgr422 | `0x02` | `0x10` | 0 | unorm | `0x10` |
| bgrg422 | `0x42` | `0x10` | 2 | unorm | `0x10` |
| bc1_rgba | `0x22` | `0x1d` | 1 | unorm | `0x1d` |
| bc2_rgba | `0x62` | `0x1d` | 3 | unorm | `0x1d` |
| bc3_rgba | `0xa2` | `0x1d` | 5 | unorm | `0x1d` |
| bc4_runorm | `0xe2` | `0x1d` | 7 | unorm | `0x1d` |
| bc4_rsnorm | `0xe2` | `0x3d` | 7 | snorm | `0x1d` |
| bc5_rgunorm | `0x22` | `0x1e` | 1 | unorm | `0x1e` |
| bc5_rgsnorm | `0x22` | `0x3e` | 1 | snorm | `0x1e` |
| bc6h_rgbfloat | `0x62` | `0x9e` | 3 | float | `0x1e` |
| bc6h_rgbufloat | `0xa2` | `0x9e` | 5 | float | `0x1e` |
| bc7_rgba | `0xe2` | `0x1e` | 7 | unorm | `0x1e` |
| astc_4x4 | `0x22` | `0x18` | 1 | unorm | `0x18` |
| astc_5x4 | `0x62` | `0x18` | 3 | unorm | `0x18` |
| astc_5x5 | `0xa2` | `0x18` | 5 | unorm | `0x18` |
| astc_6x5 | `0xe2` | `0x18` | 7 | unorm | `0x18` |
| astc_6x6 | `0x22` | `0x19` | 1 | unorm | `0x19` |
| astc_8x5 | `0x62` | `0x19` | 3 | unorm | `0x19` |
| astc_8x6 | `0xa2` | `0x19` | 5 | unorm | `0x19` |
| astc_8x8 | `0xe2` | `0x19` | 7 | unorm | `0x19` |
| astc_10x5 | `0x22` | `0x1a` | 1 | unorm | `0x1a` |
| astc_10x6 | `0x62` | `0x1a` | 3 | unorm | `0x1a` |
| astc_10x8 | `0xa2` | `0x1a` | 5 | unorm | `0x1a` |
| astc_10x10 | `0xe2` | `0x1a` | 7 | unorm | `0x1a` |
| astc_12x10 | `0x22` | `0x1b` | 1 | unorm | `0x1b` |
| astc_12x12 | `0x62` | `0x1b` | 3 | unorm | `0x1b` |
| astc_4x4_hdr | `0x22` | `0x98` | 1 | float | `0x18` |
| astc_8x8_hdr | `0xe2` | `0x99` | 7 | float | `0x19` |
| etc2_rgb8 | `0x22` | `0x16` | 1 | unorm | `0x16` |
| etc2_rgb8a1 | `0xa2` | `0x16` | 5 | unorm | `0x16` |
| eac_rgba8 | `0x62` | `0x16` | 3 | unorm | `0x16` |
| eac_r11unorm | `0xe2` | `0x16` | 7 | unorm | `0x16` |
| eac_r11snorm | `0xe2` | `0x36` | 7 | snorm | `0x16` |
| eac_rg11unorm | `0x22` | `0x17` | 1 | unorm | `0x17` |
| eac_rg11snorm | `0x22` | `0x37` | 1 | snorm | `0x17` |

**numtype orthogonality (DESC-6, HW-validated across 18 multi-numtype families):** `code =
numtype<<5 | sizeclass` holds for **every** family — packed rgb10a2 (unorm/uint/**xr**), 64-bit rg32 &
rgba16, 128-bit rgba32, and compressed BC4/BC5/EAC (unorm↔snorm) / BC6H/ASTC (float). numtype is
independent of arrangement/sizeclass, not just for the 4 base families. **numtype `5` = extended-range
(XR).** **Unsupported on this HW (Metal rejects):** `depth24unorm_stencil8`, `x24_stencil8` — Z/S are
separate resources.

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
| lodMinClamp | [0:12] | `round(lodMin × 64)` (6 fractional bits). HW-validated 0.25/0.5/1.5/13.9 → `0x10`/`0x20`/`0x60`/`0x379`. **Metal clamps the value to lodMax (default 14.0)** so it saturates at `0x380` (EXP-M4-08). |
| lodMaxClamp | [13:19] | `round(lodMax × 8)` (3 fractional bits). HW-validated 0.25/1.5/3.0/13.9 → 2/12/24/111. **Metal saturates it at 14.0** (`112`); the field is 7-bit (could hold 15.875) but >14.0 is **Metal-unreachable** (splice candidate). |
| maxAnisotropy | [20:22] | `log2(maxAnisotropy)`: 1→0, 2→1, 4→2, **8→3**, 16→4 (HW-validated incl. 8× — EXP-M4-08). 3-bit field *could* encode up to 128× but **Metal clamps >16 back to 1× (field 0), not 16×** — >16× needs descriptor injection. |
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

Codes `0,1,2,3,5` HW-validated on all three axes (EXP-M4-08). Codes `4`, `6`, `7` remain **untested and
Metal-unreachable**: they have no `MTLSamplerAddressMode`, and an explicit argument buffer holds the
sampler as an 8-byte **gpuResourceID** (bindless index), not inline descriptor bytes, so their raw code
cannot be injected through a read-only trace pass (EXP-M4-08 §DESC-4). *Vulkan mapping:* map
`VK_SAMPLER_ADDRESS_MODE_*` only onto {0,1,2,3,5}; the behavior of 4/6/7 is unknown. **Note:**
`clampToZero` and `clampToBorderColor` both map to code `3` (HW-validated: both encode `3` on S/T/R) —
exactly one HW clamp-to-border address mode. `clampToZero` = the transparent-black preset special case.

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
| width − 1 | word0[28:31] ‖ word1[0:9] (**14 bits**, max 16384; RT-3, NOT 12) | value = width − 1 |
| height − 1 | word1[10:23] (**14 bits**, max 16384; RT-3) | value = height − 1 |
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

Most of the previously-untested set is now captured in **§2d** (EXP-M4-08 — all BC/ASTC/ETC/EAC format
codes, all 16-bit norm variants, XR, YUV 4:2:2, depth32float_stencil8 aspects, stencil8). What genuinely
remains untested / Metal-unreachable:

- **Block-compressed *tiling*** (byte layout of BC/ASTC/ETC blocks in memory): the format **descriptor
  codes** are now HW-validated (§2d), but the on-disk block twiddle is a separate tiling question —
  see `../tiling/`.
- **PVRTC (`sizeclass 0x14`):** listed from EXP-0028 but **not re-captured** here (PVRTC create may be
  rejected on this HW — verify before use).
- **Texture types 1DArray / CubeArray / 2DMultisampleArray** type-codes (§1) — from EXP-0028's 4-bit
  type field (1DArray=1, CubeArray=7, 2DMSArray=8), orthogonal to format; not re-probed here.
- **Sampler codes 4/6/7 (address), 6/7 (swizzle), 3 (border):** **Metal-unreachable** — no API
  expression, and the explicit arg buffer uses gpuResourceIDs (not inline descriptor bytes), so raw
  injection is beyond a read-only trace pass (EXP-M4-08 §DESC-4). HW behavior unknown.
- **Anisotropy > 16× and lodMax > 14.0:** the 3-bit aniso field could encode 128× and the 7-bit lodMax
  field 15.875, but **Metal clamps** (aniso>16 → 1×; lodMax>14 → 14.0), so the extra range is
  **Metal-unreachable / untested** (splice candidates — §4).

Everything in **§2d** is HW-validated on M4 **and** A18 (byte-identical). Anything not in §2d has an
untested descriptor code.

## Extended format codes (EXP-0028) — 60 formats captured

All reuse `byte1 = numtype<<5 | sizeclass`, `byte0 = type[0:3] | chanArr[4:7]`; sRGB/numtype/swizzle stay orthogonal. New **sizeclass** codes beyond the 31-format table:

| family | sizeclass code | notes |
|---|---|---|
| PVRTC (legacy) | `0x14` | |
| ETC2 | `0x16` | EAC-RG11 = `0x17` |
| ASTC 4×4 / 5×5 | `0x18` | chanArr nibble picks block shape |
| ASTC 6×6 / 8×8 | `0x19` | |
| ASTC 10×10 | `0x1a` | |
| ASTC 12×12 | `0x1b` | |
| BC1–BC4 | `0x1d` | BC1/BC4 = 8-byte blocks |
| BC5 / BC6H / BC7 | `0x1e` | 16-byte blocks |

- **numtype 5 = extended-range (XR)** (`bgr10_xr`, `bgra10_xr`). HDR-ASTC = numtype float; signed BC/EAC = numtype snorm.
- **Depth/stencil reuse color codes** (depth-ness is only in the default swizzle): `depth16unorm`=r16unorm, `depth32float`=r32float, `stencil8`=r8uint.
- **Texture-type field is 4-bit** (byte0 low nibble): 1D=0, 1DArray=1, 2D=2, 2DArray=3, 2DMS=4, 3D=5, Cube=6, CubeArray=7, 2DMSArray=8.
- **Unsupported on A18 Pro** (rejected by Metal): `depth24unorm_stencil8`, `x24_stencil8` — Z/S are separate resources.
- **NOW DECODED (EXP-M4-08, see §2c/§2d):** the `byte0` chanArr field = arrangement sub-index
  `byte0[5:7]` (bit4=0); **all 14 ASTC block-shape codes** (the 4-per-sizeclass grid, §2c);
  **depth32float_stencil8** stencil aspect = X32_Stencil8 = r8uint (`0x22`/`0x40`), depth aspect =
  r32float (`0x62`/`0x88`); new sizeclasses `0x03` (16bpp 4-ch packed) and `0x10` (YUV 4:2:2).
- ⏳ still opaque: MSAA / lossless-compression codec (a tiling concern, `../tiling/`).

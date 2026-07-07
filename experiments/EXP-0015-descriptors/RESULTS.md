# EXP-0015 Results — Texture / Sampler / Buffer descriptor bit layouts (G17P, Apple9)

**TL;DR.** On A18 Pro / G17P / macOS 26.6, the resource descriptors Metal appends into
the Tier-2 argument buffer are now decoded field-by-field by change-one-Metal-parameter
diffing. The **texture descriptor is 32 bytes**; the **sampler descriptor is 8 bytes**;
a **buffer is a bare inline 8-byte GPU VA** (no length/format word). Every field below
was localised by a clean single-parameter byte-diff and is **HW-validated** unless marked
*inferred*. A 31-entry pixel-format→code table, the 3-bit swizzle codes, the texture-type
codes, and the sampler address-mode / compare-func / border-color codes are all pinned.

All findings are **DATA-TRACE** (bytes captured from our own Metal process via the
read-only `tools/iotrace` interposer) + **OWN-SHADER** (our MSL, our resources, whose GPU
VAs we print for correlation). Nothing was learned from Apple code.

Byte/word convention below: descriptor bytes are numbered from the start of the block
(the address the arg-buffer pointer points at). `word0 = bytes[0..3]` little-endian, etc.
"HW-validated" = confirmed by a one-parameter diff in `raw/diffs/`.

---

## 1. Texture descriptor — 32 bytes

Located at the address held in arg-buffer slot0 (`+0x14a0`) — EXP-0011. Canonical layout
(rgba8unorm, 2D, 16×16, 1 mip, identity swizzle; captured `raw/descriptors/`):

```
+0x00  word0 = format + swizzle + type + width(lo)
+0x04  word1 = width(hi) + height + mip/MS/layout flags
+0x08  word2 = texture base GPU VA >> 4  (low 32 bits)
+0x0c  word3 = VA>>4 high bits + sRGB flag + depth/arrayLen + layout flag
+0x10  word4 = secondary VA >> 4  (large/tiled textures only; else 0)   [inferred]
+0x14  word5 = mip-related; mipmapLevelCount-1 at byte +0x16
+0x18..+0x1f  = 0 (for the cases tested)
```

### 1a. Field map

| field | location | encoding | evidence |
|---|---|---|---|
| **texture type** | word0 bits[0:2] (byte0 low nibble) | 1D=0, 2D=2, 2DArray=3, 2DMultisample=4, 3D=5, Cube=6 | HW: `diff_type` + `desc_type_1d_fix` |
| **format – channel class** | word0 bits[4:7] (byte0 high nibble) | per-format (see §1c) | HW: `diff_format` |
| **format – code** | word0 bits[8:15] (byte1) | `numtype<<5 | sizeclass`; numtype: unorm=0,snorm=1,uint=2,sint=3,float=4 | HW: `diff_format` |
| **swizzle (channel map)** | word0 bits[16:27] | 4×3-bit, dst order R,G,B,A. codes: R=0,G=1,B=2,A=3,One=4,Zero=5 | HW: `diff_swizzle` |
| **width − 1** | word0 bits[28:31] ‖ word1 bits[0:7] (12 bits) | value = width−1 | HW: `dim_8x4/256x1/64x32` |
| **height − 1** | word1 bits[10:...] | value = height−1 | HW: `dim_4x8/16x16/64x32` |
| **sample count (MS)** | word1 bits[24:25] (byte7 low 2) | log2(samples)−1: 2→0, 4→1 | HW: `ms_2` vs `ms_4` |
| **mipmapped flag** | word1 bit26 (byte7 0x04) | set when mipmapLevelCount>1 | HW: `mip_1` vs `mip_2` |
| **layout/tiling flag** | word1 bit27 (byte7 0x08) | set for larger textures (16×16 set, 4×4 clear) | inferred (size-correlated) |
| **texture base VA** | word2 (+0x08) ‖ word3 bits[0:11] | **VA >> 4** (16-byte units), low32 in word2 | **HW-validated** (§1b) |
| **sRGB flag** | word3 bit12 (byte13 0x10) | 1 = sRGB decode | HW: `*_srgb` vs base |
| **depth (3D) / arrayLength − 1** | word3 bits[14:...] | value = (depth or arrayLength)−1 | HW: `d3d_d2/d8`, `arr_2/6` |
| **layout flag (large)** | word3 bit31 (byte15 0x80) | set for larger textures | inferred (size-correlated) |
| **mipmapLevelCount − 1** | byte +0x16 (word at +0x14, bits16-19) | value = mips−1 (0,1,3,4 for 1,2,4,5) | HW: `mip_2/4/5` |
| **secondary VA** | word4 (+0x10) | a second `VA>>4` present only for large/tiled textures | inferred |

Notes:
- **Metal-orthogonal facts:** sRGB is a **flag bit**, not a distinct format code —
  `rgba8unorm` and `rgba8unorm_srgb` share the identical 16-bit format code, differing
  only in word3 bit12. `bgra8unorm` = `rgba8unorm` format code + a **swizzle** (B↔R), not
  a distinct format. `a8unorm` = `r8unorm` format code + a swizzle. `depth32float` shares
  the exact format code of `r32float` (0x62,0x88) — "depth-ness" is not in the format
  field.
- The 3D **depth** and 2DArray **arrayLength** share one field (word3 bits14+), as
  expected (mutually exclusive per type).

### 1b. Texture base VA = VA >> 4 (HW-validated)

Buffer-backed 2-D textures (`--texoff`) whose base = printed `gpuAddress + offset`
(`raw/va_correlation.txt`):

| offset | texture base VA | word @ desc+0x08 | check |
|---|---|---|---|
| 0 | `0x10000018000` | `0x00001800` | `0x18000>>4` |
| 0x100 | `0x10000018100` | `0x00001810` | Δ 0x10 = 0x100/16 |
| 0x1000 | `0x10000019000` | `0x00001900` | `0x19000>>4` |
| 0x10000 | `0x10000028000` | `0x00002800` | `0x28000>>4` |

So the base address is stored as **VA≫4 (16-byte granularity)**: word2 = bits[4:35],
word3 bits[0:11] = bits[36:47]. Confirmed to track a 0x100/0x1000/0x10000 byte shift
exactly. (Metal-allocated textures store the same form; e.g. rgba8 16×16 → word2 `0x1c50`,
word3 hi `0x10` = VA `0x1000001c500`.)

### 1c. Pixel-format → code table (31 formats, HW-validated)

Format identity = the 16-bit value `(byte1<<8) | byte0`, with `byte0` bits[0:2] = texture
type (2 for these 2-D captures). `byte1 = numtype<<5 | sizeclass`.

| format | byte0 | byte1 | numtype | sizeclass |
|---|---|---|---|---|
| r8unorm | 0x22 | 0x00 | unorm | 0x00 |
| r8snorm | 0x22 | 0x20 | snorm | 0x00 |
| r8uint | 0x22 | 0x40 | uint | 0x00 |
| r8sint | 0x22 | 0x60 | sint | 0x00 |
| a8unorm | 0x22 | 0x00 | unorm | 0x00 (r8 code + swizzle) |
| rg8unorm | 0xa2 | 0x02 | unorm | 0x02 |
| rg8uint | 0xa2 | 0x42 | uint | 0x02 |
| r16unorm | 0x62 | 0x02 | unorm | 0x02 |
| r16uint | 0x62 | 0x42 | uint | 0x02 |
| r16float | 0x62 | 0x82 | float | 0x02 |
| rgba8unorm | 0x22 | 0x0a | unorm | 0x0a |
| rgba8snorm | 0x22 | 0x2a | snorm | 0x0a |
| rgba8uint | 0x22 | 0x4a | uint | 0x0a |
| rgba8sint | 0x22 | 0x6a | sint | 0x0a |
| bgra8unorm | 0x22 | 0x0a | unorm | 0x0a (rgba8 code + B↔R swizzle) |
| rgba8unorm_srgb | 0x22 | 0x0a | unorm | 0x0a (+ sRGB flag) |
| bgra8unorm_srgb | 0x22 | 0x0a | unorm | 0x0a (+ swizzle + sRGB flag) |
| rgb10a2unorm | 0xa2 | 0x09 | unorm | 0x09 |
| bgr10a2unorm | 0xa2 | 0x09 | unorm | 0x09 (+ swizzle) |
| rg11b10float | 0x62 | 0x89 | float | 0x09 |
| rgb9e5float | 0xe2 | 0x89 | float | 0x09 |
| r32uint | 0x62 | 0x48 | uint | 0x08 |
| r32sint | 0x62 | 0x68 | sint | 0x08 |
| r32float | 0x62 | 0x88 | float | 0x08 |
| depth32float | 0x62 | 0x88 | float | 0x08 (= r32float code) |
| rg16float | 0xe2 | 0x88 | float | 0x08 |
| rg32float | 0x62 | 0x8c | float | 0x0c |
| rgba16unorm | 0xa2 | 0x0c | unorm | 0x0c |
| rgba16uint | 0xa2 | 0x4c | uint | 0x0c |
| rgba16float | 0xa2 | 0x8c | float | 0x0c |
| rgba32uint | 0x22 | 0x4e | uint | 0x0e |
| rgba32float | 0x22 | 0x8e | float | 0x0e |

`sizeclass` low bits classify the packing/total width: 0x00=8bpp, 0x02=16bpp,
0x08=32bpp(plain), 0x09=32bpp(packed 10/10/10/2, 11/11/10, 9/9/9/5), 0x0a=32bpp(4×8),
0x0c=64bpp, 0x0e=128bpp. `byte0` high nibble disambiguates channel arrangement
(1×32 vs 2×16 etc.). The **numtype** nibble (unorm/snorm/uint/sint/float) is fully
orthogonal (HW-validated across all four types for r8/r16/r32/rgba8).

### 1d. Swizzle codes (HW-validated)

word0 bits[16:27] = 4×3-bit components in **destination order R,G,B,A**:

| code | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| channel | Red | Green | Blue | Alpha | One(1.0) | Zero(0.0) |

Identity (RGBA) = `R,G,B,A` = codes `0,1,2,3`. Confirmed with `bgra`(2,1,0,3),
`rrrr`(0,0,0,0), `aaaa`(3,3,3,3), `000a`(5,5,5,3), `1111`(4,4,4,4), `gbar`(1,2,3,0).

---

## 2. Sampler descriptor — 8 bytes

Located at the address in arg-buffer slot1 (`+0x14a8`). The **entire descriptor is 8
bytes** — everything below packs into two 32-bit words (base sampler
`00 00 0e 00 80 07 00 00`). This is a hard capacity limit (see §4).

| field | location (bits from block start) | encoding | evidence |
|---|---|---|---|
| **lodMinClamp** | bits[0:12] | `round(lodMin × 64)` (6 fractional bits) | HW: 0/0.25/0.5/1/1.5/2 → 0/16/32/64/96/128 (`raw/lod_aniso.txt`) |
| **lodMaxClamp** | bits[13:19] | `round(lodMax × 8)` (3 fractional bits); default/FLT_MAX → 14.0 (saturates) | HW: 2/2.5/3/5/10 → 16/20/24/40/80 |
| **maxAnisotropy** | bits[20:22] | `log2(maxAnisotropy)`: 1→0,2→1,4→2,16→4 | HW: `aniso2/4/16`; disjoint from lodMax (`lodmax3_an4`) |
| **magFilter** | bit23 (byte2 0x80) | 0=nearest, 1=linear | HW: `smp_maglin` |
| **minFilter** | bit25 (byte3 0x02) | 0=nearest, 1=linear | HW: `smp_minlin` |
| **mipFilter** | bits[27:28] (byte3 0x08/0x10) | none=0, nearest=1, linear=2 | HW: `smp_mipnear/miplin` |
| **sAddressMode** | bits[29:31] (byte3 bits5-7) | see codes below | HW: `smp_srep/smir/...` |
| **tAddressMode** | bits[32:34] (byte4 bits0-2) | same codes | HW: `smp_trep` |
| **rAddressMode** | bits[35:37] (byte4 bits3-5) | same codes | HW: `smp3_rrep/rmir` (3D) |
| **unnormalizedCoordinates** | bit38 (byte4 0x40) | 1 = unnormalized | HW: `smp_unorm` |
| **compareFunc – sense** | bit39 (byte4 0x80) | invert bit (see table) | HW: `diff_compare` |
| **compareFunc – test** | bits[40:42] (byte5 bits0-2) | see table | HW: `diff_compare` |
| **borderColor** | bits[61:62] (byte7 bits5-6) | 0=transp-black, 1=opaque-black, 2=opaque-white | HW: `smp_bord*` |

### 2a. Address-mode codes (3-bit, per axis; HW-validated)

| code | mode |
|---|---|
| 0 | clampToEdge |
| 1 | repeat |
| 2 | mirrorRepeat |
| 3 | clampToZero **and** clampToBorderColor (see §4) |
| 5 | mirrorClampToEdge |

Codes 4, 6, 7 untested (candidates for probing).

### 2b. Compare-function codes (HW-validated)

Compare = (`sense` = byte4 bit7) + (`test` = byte5 bits[0:2]):

| Metal func | sense | test | Metal func | sense | test |
|---|---|---|---|---|---|
| never | 1 | 7 | always | 0 | 7 |
| less | 0 | 5 | greater | 1 | 5 |
| lessEqual | 0 | 4 | greaterEqual | 1 | 4 |
| equal | 0 | 6 | notEqual | 1 | 6 |

The `test` groups complementary predicates (5=less/greater, 4=lequal/gequal,
6=equal/nequal, 7=always/never) and the `sense` bit picks the direction — a compact
"predicate + invert" encoding. Default (non-comparison) sampler = never (1,7).

---

## 3. Buffer descriptor — inline 8-byte GPU VA

A `device T* [[buffer(i)]]` binding is a **bare 8-byte little-endian GPU VA** inlined in
the arg-buffer slot (`+0x14a0 + i·8`), confirming EXP-0011. In every capture, arg slot2
(`+0x14b0`) held exactly the output buffer's printed `gpuAddress` (e.g. `0x1000001c600`),
with **no accompanying length or format word** — the adjacent slot is the next binding.
The hardware does no descriptor-level bounds/format info for plain device buffers; size
lives only in the shader/args, not in a buffer descriptor.

---

## 4. Capability-probe notes (HW-rich vs Metal-limited)

Candidates for `docs/hypotheses.md` (orchestrator to log):

- **Border color is Metal-limited, HW-limited too.** The sampler is only **8 bytes**;
  border color is a **2-bit preset selector** (byte7 bits5-6) with exactly the 3 Metal
  presets (transparent-black / opaque-black / opaque-white). There is **no room for an
  arbitrary RGBA border color** in the descriptor. Vulkan `VK_EXT_custom_border_color`
  (4 arbitrary floats) is **not** expressible here → must be emulated (e.g. shader-side)
  unless a separate border-color table exists elsewhere (not seen in these captures).
  *Flag: HW-limited.*
- **clampToZero == clampToBorderColor(transparent-black).** Both map to address code 3;
  clampToZero is the border-color-preset-0 special case. So there is a **single
  clamp-to-border address mode** in HW, not two. `clampToBorderColor` with a preset works
  (byte7 selects the color); it faults nothing. *Consistent with a Vulkan clamp-to-border
  as long as the color is one of the 3 presets.*
- **Address modes** cover clampToEdge/repeat/mirrorRepeat/clampToBorder/mirrorClampToEdge
  (codes 0,1,2,3,5). Codes 4,6,7 are unexplored — worth probing for any extra mode
  (e.g. a distinct clamp-to-border-vs-zero, or mirror-once).
- **Anisotropy** is a 3-bit log2 field (bits20-22) → representable up to log2=7 = **128×**,
  though Metal caps at 16× (log2=4). The HW field can encode 32×/64×/128× — a probe
  candidate (does the sampler accept, and does the filter honor, aniso beyond 16?).
- **maxLodClamp** is a 7-bit ×8 field → max ~15.875, and Metal's FLT_MAX default clamps to
  **14.0**. lodMinClamp is finer (×64). So LOD clamp range is limited to ~0..15.9.
- **Compare functions**: all 8 Metal compare funcs are expressible (the predicate+sense
  encoding), so shadow/PCF compare is fully HW-supported.
- **numeric-type / sRGB / swizzle are orthogonal knobs**, not baked per-format: any format
  code can (in principle) be combined with any swizzle and the sRGB flag — richer than a
  flat `MTLPixelFormat` enum. This is exactly the Vulkan model (format + component mapping
  + sRGB) and maps cleanly onto the HW descriptor.

---

## 5. Still opaque / recommended next

- **Large-texture layout bits** (word1 bit27, word3 bit31) and the **secondary VA at
  desc+0x10** appear together above a size threshold (present for 16×16, absent for 4×4).
  These are the entry point to the **tiling/twiddling + compression** story — decode them
  in the Phase-4 `docs/tiling/` experiment (known pattern in, read layout out), not here.
- **word3 bit13** and **byte0 high-nibble** internal structure (channel arrangement) are
  read but not bit-split; the format→code table is complete without it.
- **Extra address-mode codes 4/6/7** and **anisotropy > 16×** are open probe candidates.
- **1DArray / CubeArray / 2DMSArray** type codes untested (extrapolate 1,7,... from the
  1D=0,2DArray=3 pattern).
- The **row stride / bytes-per-row** for non-power-of-two or buffer-backed textures is not
  a separate visible field here (linear buffer-backed textures carried it via the Metal
  API, not the descriptor) — revisit with tiling.

Zero GPU wedges / reboots across the whole matrix (~110 captures). All dispatches
completed `status=4` with correct output.

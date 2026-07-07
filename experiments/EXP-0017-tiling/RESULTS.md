# EXP-0017 Results — Texture tiling/twiddle + lossless compression (G17P, Apple9)

**TL;DR.** On A18 Pro / G17P / macOS 26.6, a 2-D texture in the GPU's optimal (private)
layout is stored in **pure Morton / Z-order twiddle**: byte offset of texel `(x,y)` is
`morton(x,y) · bytesPerPixel`, where `morton` interleaves the bits of x (even positions)
and y (odd positions). There is **no fixed sub-tile** below the whole texture — the
interleave runs across all bits; storage is **padded to the next power of two per axis**.
The twiddle is over **texel coordinates only** (identical for 1/2/4/8/16-byte formats).
Mip levels are packed consecutively, each an independently pow2-padded Morton plane.
**Lossless compression** turns on when the texture has **no ShaderWrite usage** and is at
least one ~16×16 tile in size; it adds an **auxiliary metadata buffer** (the secondary VA
at descriptor+0x10) placed immediately after the image, sized `image_bytes / 128`, holding
one compression-state byte per **8×4-texel block** in Morton-block order. All findings are
**HW-validated** (GPU wrote the pattern, we read the raw backing bytes) unless marked
*inferred*.

Convention: `wordN` = 32-bit LE word at descriptor byte `4N`. "element index" `e` =
`byte_offset / bytesPerPixel` from the texture base. No GPU wedges/reboots across ~50 captures.

---

## 1. Twiddle / tiling order — 2-D optimal layout (HW-validated)

### 1a. The formula
For a 2-D texture, let `Wp = nextpow2(W)`, `Hp = nextpow2(H)` (storage is padded to these),
`kx = log2(Wp)`, `ky = log2(Hp)`, and `n = min(kx,ky)`. Writing `x_i`/`y_i` for bit *i*:

```
element_index(x,y) =  Σ_{i<n} ( x_i << (2i) )  |  ( y_i << (2i+1) )      # interleaved low part
                    +  (high bits of the LARGER dimension, packed linearly above bit 2n):
                         if Wp > Hp:  Σ_{i>=n} x_i << (n + i)
                         if Hp > Wp:  Σ_{i>=n} y_i << (n + i)
byte_offset        =  element_index · bytesPerPixel
```

i.e. **interleave x,y bit-for-bit (x on the lower bit of each pair) up to the smaller
dimension, then append the remaining high bits of the larger dimension linearly**.

### 1b. Evidence (`raw/analysis/`, `raw/twiddle_raw_r32_32.txt`)
GF(2) bit-permutation solves (each **exact**, full coverage):

| case | solved element_index | coverage |
|---|---|---|
| r32uint **16×16** | `x0\|y0<<1\|x1<<2\|y1<<3\|x2<<4\|y2<<5\|x3<<6\|y3<<7` | 256/256 |
| r32uint **32×32** | …`\|x4<<8\|y4<<9` | 1024/1024 |
| r32uint **64×64** | …`\|x5<<10\|y5<<11` | 4096/4096 |
| r32uint **128×128** | …`\|x6<<12\|y6<<13` | 16384/16384 |
| r32uint **256×8** (NPOT-ratio) | `x0\|y0<<1\|x1<<2\|y1<<3\|x2<<4\|y2<<5\|x3<<6\|x4<<7\|x5<<8\|x6<<9\|x7<<10` | 2048/2048 |
| r32uint **48×48** | pure interleave to bit 11 over padded **64×64** | 2304/2304 |
| r32uint **17×9** | interleave over padded **32×16** | 153/153 |

Raw bytes for 32×32 read out in exact Z-order: element 0=(0,0), 1=(1,0), 2=(0,1), 3=(1,1),
4=(2,0), 5=(3,0), 6=(2,1), 7=(3,1), … (`raw/twiddle_raw_r32_32.txt`).

### 1c. Padding = next power of two per axis (HW-validated)
Backing-BO sizes are exactly the pow2-padded Morton area:
- 48×48 → BO `0x4000` = 64×64×4 (padded 48→64).
- 96×96 (mip L0) → `0x10000` = 128×128×4 (padded 96→128).
- 24×24, 12×12 (mip levels) → padded to 32×32, 16×16 respectively.
- 256×8, 64×64, 128×128 (already pow2) → no padding.

### 1d. Scaling with bytes-per-pixel — twiddle is over texels (HW-validated)
At 32×32, **every** format gave the identical `element_index = morton(x,y)`:
`r8uint`(1B), `r16uint`(2B), `r32uint`(4B), `rgba8uint`(4B), `rg32uint`(8B), `rgba16uint`(8B),
`rgba32uint`(16B) (`raw/analysis/B_*.txt`; r8 confirmed clean at 16×16). So the tile is a
fixed number of **texels**; the byte tile scales with bpp: **byte_offset = morton(x,y)·bpp**.

### 1e. Linear control (HW-validated)
A buffer-backed linear r32uint 64×64 solved to **pure row-major**
`element_index = x0..x5 (bits0-5) | y0..y5 (bits6-11)` = `y·64 + x`, and its raw head is
consecutive `00 00 a5 a5 | 01 00 a5 a5 | 02 00 a5 a5 …` (`raw/twiddle_linear_r32_64.txt`,
`raw/linear_bpr.txt`). This confirms the method cleanly separates linear from twiddled, and
that non-buffer-backed `StorageModeShared` textures use the **twiddled** layout.

### 1f. Bonus — linear bytesPerRow encoding (resolves an EXP-0015 unknown)
Linear textures store **bytesPerRow = (word3[14:] + 1) × 16** (stride in 16-byte units − 1):
bpr 128/256/512/800 ⇒ word3[14:] = 7/15/31/49 (`raw/linear_stride_decode.txt`). Twiddled
textures leave word3[14:] = 0 (Morton layout is implicit; no stride stored). This is the
same field EXP-0015 attributed to depth/arrayLength−1 — context-dependent per texture kind.

---

## 2. Mipmap packing (HW-validated — `raw/mip_128.txt`, `raw/mip_96.txt`)

Levels are packed **consecutively after the base**, each an independently pow2-padded
Morton plane. Level *L* occupies `nextpow2(W>>L) · nextpow2(H>>L) · bpp` bytes.

128×128 r32uint, 8 levels:

| L | dims | byte offset | slot size |
|---|---|---|---|
| 0 | 128×128 | `0x00000` | `0x10000` |
| 1 | 64×64 | `0x10000` | `0x4000` |
| 2 | 32×32 | `0x14000` | `0x1000` |
| 3 | 16×16 | `0x15000` | `0x400` |
| 4 | 8×8 | `0x15400` | `0x100` |
| 5 | 4×4 | `0x15500` | `0x80`* |
| 6 | 2×2 | `0x15580` | `0x80`* |
| 7 | 1×1 | `0x15600` | — |

\*Tiny levels (≤4×4) are floored to a **0x80-byte minimum slot** and aligned. 96×96 confirms
pow2 padding per level: L0 (96→128) takes a full `0x10000` slot, L1 (48→64) `0x4000` at
`0x10000`, L2 (24→32) `0x1000`, L3 (12→16) `0x400`. Within every level, the Morton order
holds (`(1,0)→e+1`, `(0,1)→e+2`, HW-checked per level).

Descriptor for mipmapped: **word1 bit26 = 1** (mipmapped), **word3 bit31 = 1**,
**mipCount−1 in word5 bits[16:19]** (byte +0x16). (word1 bit27 / secondary VA stay 0 unless
compression is also active.)

---

## 3. Lossless compression (first pass — HW-validated trigger/placement; codec partial)

### 3a. When it turns on (corrects EXP-0015's "size threshold" guess)
The layout flags **word1 bit27 + word3 bit31 + a non-zero secondary VA** = compression aux,
gated on **usage and size, NOT size alone** (`raw/analysis/F_trigger.txt`):

| usage | 4×4 | 8×8 | 16×16 | 32×32+ | 256/512 |
|---|---|---|---|---|---|
| ShaderRead only (no write) | off | off | **on** | **on** | **on** |
| RenderTarget (no write) | off | — | **on** | **on** | **on** |
| **ShaderRead\|ShaderWrite** | off | off | off | off | **off (512²)** |

So: **compression = (no ShaderWrite usage) AND (image ≥ ~one 16×16 tile)**. ShaderWrite
(read-write image store) **disables** compression at every size — which is why all the §1
tiling captures (usage=rw) showed b27=0 and the plain uncompressed Morton layout. The size
cutoff sits between 8×8 and 16×16 (rgba8), consistent with requiring ≥ 1 compression tile.

### 3b. Where the secondary VA points, and aux size (HW-validated)
The secondary VA is encoded exactly like the base: **`word4 | (word5[0:11] << 32)`, then
`<< 4`** (16-byte units). It points **immediately after the main image, in the same
allocation**: `secondaryVA = baseVA + paddedImageBytes`. Aux size scales linearly:

| size (rgba8 RT) | main image | aux (BO_size − main) | ratio |
|---|---|---|---|
| 64×64 | `0x4000` | `0x80` | main/128 |
| 128×128 | `0x10000` | `0x200` | main/128 |
| 256×256 | `0x40000` | `0x800` | main/128 |
| 512×512 | `0x100000` | `0x2000` | main/128 |
| 1024×1024 | `0x400000` | `0x8000` | main/128 |

**aux_bytes = image_bytes / 128 = 1 byte per 8×4-texel block** (32 texels = 128 rgba8 bytes).
The main image keeps its **full uncompressed footprint** — compression saves bandwidth, not
allocation.

### 3c. Aux = per-block compression-state byte (HW-validated)
`raw/compress_rt64.txt`, `raw/analysis/G_entropy.txt`, `raw/compress_split64.txt`:
- Smooth gradient (compressible) → **all aux bytes `0x15`**.
- High-entropy noise (incompressible) → **all aux bytes `0x7f`**.
- **Split** (left x<32 constant / right x≥32 noise), 64×64 → aux =
  `[0x03 ×32] [0x7f ×32] [0x03 ×32] [0x7f ×32]`.

The split proves the aux array is ordered by **Morton-of-blocks**: the four 32-byte runs are
the four 32×32 super-tiles (Morton order TL,TR,BL,BR), 32 aux bytes each, one byte per 8×4
block within. The byte **value encodes the per-block compression state/mode**: `0x03`/`0x15`
= compressed constant/gradient, `0x7f` = incompressible/stored-raw. (Exact numeric meaning of
the state codes and the internal codec are **not decoded** — see §4.)

### 3d. Main data is genuinely compressed
For a compressed render target the raw main bytes are **not** the Morton pattern (only
1/64 of positions coincidentally re-decode). The readback *through the texture unit* is
correct (HW decompresses transparently), while the raw bytes are a codec stream with a
repeating motif (constant prefix `a5 8c 91 00`, literal constant channels `aa cd`, and
varying gradient bytes; `raw/compress_rt64.txt`). Incompressible noise stores near-verbatim.

---

## 4. What stays unknown (compression is the frontier)
- **Exact codec / bit-layout of a compressed 8×4 block** and the meaning of the state-byte
  values (0x03/0x15/0x7f and others) — not reverse-engineered (would require decoding the
  block stream; out of scope for a first pass, and near the boundary of what's cleanly
  observable without Apple's codec).
- **Block shape 8×4 vs 4×8** is inferred from the proven Morton curve (32 Morton-contiguous
  texels = x:{x0,x1,x2}×y:{y0,y1}), not from an independent fine-grained split.
- **Per-dimension size threshold** (tested square only; 16×16 on, 8×8 off) — the exact rule
  for non-square small textures (e.g. 256×2) is untested.
- **Compression + mipmaps interaction** (aux layout for a compressed mip chain) — untested;
  each mip level presumably gets its own aux slice.
- **Depth/3D, array, cube, MSAA twiddle** — only 2-D single-plane tested. 3D likely extends
  the interleave with z bits; arrays likely concatenate padded planes (both untested).
- **Block-compressed formats (BC/ASTC/ETC)** not probed (see §5).

## 5. Format-specific layouts (brief)
All §1–§3 results are for **uncompressed** color/integer formats; the twiddle is over whole
texels and is bpp-parametric, so it applies to any uncompressed format by its bytesPerPixel
(1/2/4/8/16 all validated). **Block-compressed formats (BC/ASTC/ETC)** were not probed here;
by construction they twiddle over *blocks* (e.g. ASTC/BC 4×4-texel blocks) rather than texels
— i.e. the same Morton curve applied to block coordinates with the block's byte size as the
"bpp". This is a stated extrapolation, **not** HW-validated in this experiment.

---

## Established facts → docs
- Morton twiddle formula + pow2 padding + bpp scaling → `docs/tiling/` §Twiddle. HW-validated.
- Mip packing (consecutive pow2-padded Morton planes, 0x80 min slot) → `docs/tiling/` §Mipmaps.
- Compression trigger / secondary-VA placement / aux size & granularity / per-block state →
  `docs/tiling/` §Compression.
- Linear bytesPerRow = (word3[14:]+1)×16; secondary VA = (word4|word5[0:11]<<32)<<4; word1
  bit26=mip, bit27=compression-aux, word3 bit31=has-aux(mip or compression), word5[16:19]=
  mipCount−1 → `docs/descriptors/` (resolves EXP-0015 open items).

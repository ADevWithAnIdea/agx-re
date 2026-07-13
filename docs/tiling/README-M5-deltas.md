# M5 (Apple10 / G17g) texture-tiling & lossless-compression deltas vs A18 (G17P)

Delta-form: "same as `tiling/README.md` (A18/G17P) except as noted." Source: EXP-M5-10 (own-MSL HW-probe:
Metal-reported `allocatedSize` matrix + descriptor data-trace + GPU-write pattern). Clean-room: own MSL/API,
we read allocation sizes Metal reports for our own textures and bytes our own process registered. No Apple
binary introspected. HW-validated unless marked *inherited* / ⏳.

## Headline — the A18 twiddle + compression MODEL transfers BYTE-FOR-BYTE
The M5 optimal (twiddled) padding rules, the per-bpp Morton tile edge **T**, the page-granule even-column
rule **G**, and the lossless-compression aux rules are **identical to A18**. Established by sweeping
`[tex allocatedSize]` over **6 formats × 8 dimensions** (incl. non-power-of-two 96/192/300) plus the
descriptor compression flags. This closes the tiling/compression open item from EXP-M5-06.

## 1. Twiddled padding — SAME as A18 §1.1/§1.4
`T = largest 2^k with T²·bpp ≤ 16 KiB`; `G = 16KiB/(T²·bpp)`; `cols = round_up(ceil(W/T), G)`;
`padW = cols·T`; `padH = ceil(H/T)·T`; **image bytes = padW·padH·bpp**. Per-bpp table (all HW-validated on M5):

| bpp (fmt) | **T** | **G** (even-col?) | decisive M5 non-pow2 check |
|---|---|---|---|
| 1 (r8) | **128** | 1 | 300→cols 3 (padW 384, 0x24000) — **T=128, not 64** |
| 2 (r16u) | 64 | **2 (even)** | 192→cols **4** (padW 256); 300→cols **6** |
| 4 (rgba8/r32u) | 64 | 1 | 300→cols **5** (padW 320, image 0x64000) — **mult-of-T, not nextpow2 512** |
| 8 (rgba16f) | 32 | **2 (even)** | 96→cols **4**; 300→cols **10** |
| 16 (rgba32f) | 32 | 1 | 96→cols **3** (odd OK, flat G) |

Every one of the 48 (format,dim) cells matches `image_bytes = padW·padH·bpp` exactly. **⚠ M5 allocation
overhead:** Metal's `allocatedSize` for a **writable** (ShaderWrite) 2-D texture is `image_bytes + 0x4000`
(one 16-KiB page of trailing padding; sub-page tiny images add `+0x80`). This overhead is a Metal allocator
detail, not part of the tiled layout — the **twiddle span is the un-padded `image_bytes`** exactly as A18.

## 2. Lossless compression — SAME as A18 §4
Compression-eligible = **no ShaderWrite/PixelFormatView AND W≥16 ∧ H≥16** (HW-validated boundary on M5:
15×15→**no aux**, 16×16→**aux present**, byte-for-byte the A18 threshold). Aux size = **numTexels/32**
(bpp-independent in *texels*): 256² rgba8 / rgba16f / rgba32f each add **0x800** aux over the image, then the
allocation rounds up to a 16-KiB page — identical to A18's `aux = paddedImageBytes/(32·bpp)`. Aux placed
immediately after the image in the same allocation (as A18).

## 3. Intra-tile Morton order — INHERITED from A18 §1.1/§1.6 (not byte-re-solved on M5) ⏳
The within-tile Z-order (`morton_D(x,y)`), 3D/array/cube/MSAA plane stacking, and mip packing are **inherited
from A18**. They are *strongly* corroborated on M5 because the §1 padding rules — which are direct
consequences of the tiled-Morton layout — reproduce byte-for-byte. A direct GPU-write-pattern read-back of the
Morton byte order was **attempted but not captured**: our `iotrace` interposer did not snapshot the
compute-written texture backing BO this run (the pattern-probe backing was absent from the dump). Re-run with a
draw-fill or blit-fill probe (as A18 EXP-0017 did) to byte-verify the curve on M5.

## Open ⏳
Direct Morton byte-order read-back on M5 (method note above); block-compressed (BC/ASTC) tile rule on M5
(inherited — A18 uses 32-block tiles); the compressed block codec + state-byte semantics remain HW-internal
(documented disable-fallback, as A18).

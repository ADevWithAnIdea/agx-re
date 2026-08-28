# M5 (Apple10 / G17g) texture-tiling & lossless-compression deltas vs A18 (G17P)

> [!IMPORTANT]
> **Scope: Apple M5 (Apple10 / G17g / T8142). NOT evidence for Apple9 (A18 Pro / M4).**
> The M5 workstream is **complete and deferred** (`CLAUDE.md`). Nothing in this file may be
> used to support an A18/G17P or M4/G16G claim, and no value here may be emitted by an Apple9
> driver without being independently established on an Apple9 target. M5 is a G17-family
> *sibling*, not the same device: treat every number as M5-only unless an `EXP-M4-*` or
> `EXP-00NN` experiment says otherwise.

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

## 3. Intra-tile Morton order — INHERITED from A18 §1.1/§1.6; direct read-back is CPU-OPAQUE on M5 (EXP-M5-23) ⏳
The within-tile Z-order (`morton_D(x,y)`), 3D/array/cube/MSAA plane stacking, and mip packing are **inherited
from A18**. They are *strongly* corroborated on M5 because the §1 padding rules — direct consequences of the
tiled-Morton layout — reproduce byte-for-byte over 6 formats × 8 dims.

**A direct byte-order read-back is NOT possible on M5** (EXP-M5-23 pinned the root cause, superseding EXP-M5-10's
"interposer didn't snapshot"). We wrote texel(x,y)=`(y<<16)|x` and tried every route to read the raw twiddled
backing; the raw twiddled bytes are **never CPU-observable**:
- **iotrace sel-9 capture:** a standalone uncompressed (ShaderWrite) `StorageModeShared` texture backing is **not
  registered via resource-map selector 9** on M5 (unlike A18/EXP-0017) — the raw value `0x00020003` (texel(3,2))
  appears in **zero** captured BOs, for both a draw-store and a compute image-store.
- **heap-placed texture:** a `StorageModeShared` heap backing IS a sel-9 BO and IS captured, but M5 stores heap
  textures **lossless-compressed even with ShaderWrite** (texSizeInHeap `0x24800` = image `0x24000` + `0x800`
  aux; content is the HW compression codec, e.g. repeating 0x4c-byte blocks, not the raw Morton curve).
- **self-process VM scan** (reading our OWN texture's data — clean-room OK): the full 36864 distinct texel values
  never appear contiguously in any CPU-readable region (best window: RW 383, incl. READ-only 3688, of 36864).
  `getBytes` returns correct texels but de-twiddles on a GPU/driver path — the twiddled bytes never materialise
  in CPU-visible linear memory.

Consequence: the exact intra-tile permutation is **not independently re-derived on M5**; it stays inherited from
A18 (§1.1) and is strongly corroborated by the byte-for-byte allocation model. This read-back opacity is itself a
first-class M5 result (a Mesa driver reading twiddled texels back on the CPU must go through Metal's blit/getBytes
de-twiddle path, not a raw mmap). Tooling: `experiments/EXP-M5-23-cmdstream-opens/scripts/{mortondraw,texscan}.m`.

## Open ⏳
Direct Morton byte-order read-back on M5 is **blocked by design** (§3: texture backing is CPU-opaque —
sel-9-invisible standalone, compressed-in-heap, absent from self-VM); within-tile order stays inherited from A18
and corroborated structurally. Block-compressed (BC/ASTC) tile rule on M5 (inherited — A18 uses 32-block tiles);
the compressed block codec + state-byte semantics remain HW-internal (documented disable-fallback, as A18).

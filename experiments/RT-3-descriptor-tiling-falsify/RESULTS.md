# RT-3 RESULTS — Red-team falsification of `docs/descriptors` + `docs/tiling`

Device: Apple A18 Pro / G17P, macOS 26.6. Method: HW-PROBE + OWN-SHADER + DATA-TRACE via the
read-only `tools/iotrace` interposer (built `-arch arm64e`). Every claim was re-tested against a
**different** set of textures/formats/sizes than the originals, with **independent analyzers**
(`dcheck.py`/`twcheck.py`/`fcheck.py`/`scheck.py`/`pbecheck.py`/`ccheck.py`) that re-derive fields
from raw bytes rather than assuming the documented bit positions. No Apple binary was disassembled.

## Verdict summary

| # | Claim under test | Verdict |
|---|---|---|
| 1 | Texture-descriptor **width/height packing** | **DISCREPANCY** — fields are **14-bit, not 12-bit** |
| 5 | 2D **twiddle formula** ("pure Morton, no sub-tile") | **DISCREPANCY** — it is a **64×64/32×32 Morton tile, row-major tiles** |
| 5 | 2D twiddle **bpp-independence** (`docs/tiling` §1.3) | **DISCREPANCY** — tile *size* depends on bpp |
| 1 | type byte0[0:3], format byte1, swizzle, sRGB, base VA (`VA>>4`), mip/sample counts, depth/arrayLen | **CONFIRMED** |
| 2 | **Sampler** (addr modes, 8 compare funcs, borders, filters, aniso, lod, unnorm) | **CONFIRMED** (all) |
| 3 | **PBE** width/height packing + read_write dual-descriptor | **CONFIRMED** |
| 4 | **Format→code** `byte1 = numtype<<5 \| sizeclass` on 38 obscure formats | **CONFIRMED** (+ 3 gap fills) |
| 5 | NPOT append, 3D/array/cube stacking, MSAA sample-major | **CONFIRMED** |
| 6 | **Compression** ≥16×16 threshold, aux size `image/128`, placement `base+imageBytes`, mip full-pyramid | **CONFIRMED** |

Two real discrepancies were found. Both are cases the originals never exercised (textures wider/taller
than 4096, and textures with **both** dims larger than one tile). Everything the originals *did* test
is upheld.

---

## DISCREPANCY 1 — texture-descriptor width/height are 14-bit, not 12-bit

`docs/descriptors/README.md` and `format-table.md` §5 document:
> width−1 = word0 bits[28:31] ‖ word1 bits[0:7]  (**12 bits**, max 4096)
> height−1 = word1 bits[10:…]

The read-back proves the fields are **14 bits** each (Apple9 max texture dim is 16384, which a 12-bit
field cannot represent). Evidence (`analysis/RT3_evidence.txt`, `raw/desc_w16384.txt`):

```
W=8192  : word1=0x00001dff  bits[8:9]=0b01   -> width-1 = word0[28:31]|word1[0:9] = 8191   (12-bit reading gives 4095, WRONG)
W=16384 : word1=0x00001fff  bits[8:9]=0b11   -> width-1 = 16383                            (12-bit reading gives 4095, WRONG)
H=8192  : word1=0x007ffc00  bits[22:23]=0b01 -> height-1 = word1[10:23] = 8191
H=16384 : word1=0x00fffc00  bits[22:23]=0b11 -> height-1 = 16383
```

**Corrected fields (HW-validated):**
- **width−1  = word0 bits[28:31] ‖ word1 bits[0:9]**  (4+10 = **14 bits**, max width 16384)
- **height−1 = word1 bits[10:23]**  (**14 bits**, max height 16384)
- Full word1 map: `[0:9]`=width-1.hi10, `[10:23]`=height-1, `[24:25]`=sampleCount, `[26]`=mipmapped,
  `[27]`=compression-aux, `[28:29]`=sparse (per EXP-O2B), `[30:31]`=?

**Impact:** a driver following the doc truncates width/height to 12 bits and mis-encodes **any texture
wider or taller than 4096** — i.e. all 4K/8K render targets, large atlases, 1D buffers, etc. The bug is
invisible below 4096, which is why all prior small-texture captures passed. Note the PBE descriptor's
own doc already uses the correct 14-bit split (word0[24:31]‖word1[0:5]); only the *sampled* descriptor
was mis-documented. `tools/iotrace` twiddle helper `find_descriptor` uses the 12-bit `(w1&0xff)<<4`
and shares the bug.

---

## DISCREPANCY 2 — 2D twiddle is a *tiled* Morton (row-major tiles), not a full-address Morton

`docs/tiling/README.md` §1.1–§1.3 claims:
> There is **no fixed sub-tile**: the interleave runs across the full address … For a square
> power-of-two texture this is a full Morton curve over all bits … the twiddle is over texel
> coordinates only — identical for 1/2/4/8/16-byte formats.

**All three of those statements are false for textures whose dimensions exceed one tile.** The
GF(2) bit-permutation solved directly from the raw backing (`raw/map_256x256_r32.txt`):

```
256×256 r32uint (4bpp):  e = x0 y0 x1 y1 x2 y2 x3 y3 x4 y4 x5 y5 | x6 x7 | y6 y7   (bits 0..15)
512×512 r32uint (4bpp):  e = ...x5 y5 | x6 x7 x8 | y6 y7 y8
256×256 rgba16 (8bpp):   e = x0 y0 x1 y1 x2 y2 x3 y3 x4 y4 | x5 x6 x7 | y5 y6 y7
256×256 rgba32 (16bpp):  e = ...x4 y4 | x5 x6 x7 | y5 y6 y7
```

The interleave **stops at a fixed depth D** (bits 0..2D−1 = one Morton tile), then the remaining
**x-high bits come first, then the y-high bits** — i.e. tiles are laid out **row-major (linear)**, not
Morton-interleaved. A *full* Morton (the doc's claim) would interleave x6,y6,x7,y7 — the hardware does
x6,x7,y6,y7. `twcheck.py` (predicted == actual for every texel):

```
256×256 DOC model:   32768 / 65536 texels WRONG      512×512 DOC model:   57344 / 65536 WRONG
256×256 TILED model: 0 MISMATCH (all 65536)          512×512 TILED model: 0 MISMATCH
```

The tiled model also reproduces **every** NPOT/asymmetric capture (48×80, 80×48, 96×160, 33×17,
512×128, 128×512) with 0 mismatch — the doc's "append the larger dim" rule is just the special case
of this model when only one axis exceeds the tile, which is why those passed.

**Tile size depends on bpp** (contradicting §1.3's bpp-independence), measured D(bpp):

| bpp | 2 | 4 | 8 | 16 |
|---|---|---|---|---|
| tile edge (texels) | 64 | 64 | 32 | 32 |
| interleave depth D | 6 | 6 | 5 | 5 |

(1 bpp not directly measurable with a unique-coord pattern; extrapolate 64. Break is between 4 B and 8 B.)

**Corrected formula (HW-validated for 2/4/8/16 bpp):**
```
D    = 6 if bpp <= 4 else 5          # tile edge T = 1<<D  (64×64 for ≤4bpp, 32×32 for ≥8bpp)
Wp   = nextpow2(W);  cols = Wp >> D  # number of tile columns
tx,ty = x>>D, y>>D ;  xl,yl = x&(T-1), y&(T-1)
element_index = (ty*cols + tx) * (T*T) + morton_D(xl, yl)   # 2^D×2^D Morton tiles, ROW-MAJOR
byte_offset   = element_index * bpp
```
Within one tile (all dims ≤ T) this reduces to the plain `morton(x,y)`, so every small-texture result
the originals validated (≤128 at 4bpp) still holds — the divergence appears only once **both** padded
dims exceed T (first falsifying case: 256×256).

---

## CONFIRMED claims (falsification tests upheld the docs)

### Texture descriptor (other fields) — CONFIRMED
- **type** byte0[0:3]: 2D=2, 3D=5, 2DArray=3, 2DMS=4 — match.
- **swizzle** word0[16:27], 4×3-bit R,G,B,A: `ab01` → codes 3,2,5,4 (=0x953), incl. One=4/Zero=5. Match.
- **base VA = word2 ‖ word3[0:11] << 4** (`VA>>4`): exact against 3 buffer-backed known VAs
  (texoff 0x1000/0x5000/0xa000 → base 0x…19000/1d000/22000). Match.
- **sRGB** word3 bit12: set for r8unorm_srgb, bc7_srgb; clear otherwise. Match.
- **mipCount−1** word5[16:19] (byte +0x16): 8 for mips=9, 9 for mips=10. **mipmapped** flag word1 bit26. Match.
- **sampleCount** word1[24:25] = log2(n)−1: ms2→0, ms4→1. Match.
- **3D depth−1 / arrayLen−1** word3[14:]: 3D 32×32×16 → 0xf(=16); 2DArray×6 → 0x5(=6). Match.

### Sampler descriptor (8 B) — CONFIRMED (all fields)
- Address modes S/T/R: edge=0, repeat=1, mirror=2, clampZero=3, **clampBorder=3 (same as clampZero)**,
  mirrorClampEdge=5. Match.
- **All 8 compare funcs** (sense@39 + test[40:42]): never(1,7) always(0,7) less(0,5) greater(1,5)
  lequal(0,4) gequal(1,4) equal(0,6) nequal(1,6). Exact match.
- Border byte7[5:6]: tblack=0 oblack=1 owhite=2. Filters mag@23/min@25/mip[27:28]. Aniso[20:22]=log2
  (2→1,4→2,8→3,16→4). lodMin×64 (1.5→96), lodMax×8 (7.0→56). unnorm@38. All match.

### PBE / storage-image descriptor — CONFIRMED
- width−1 = word0[24:31] ‖ word1[0:5], height−1 = word1[6:19] — exact for 96×48, 100×60, 40×24,
  and **8192×8** (confirms the PBE split is genuinely 14-bit).
- `access::read_write` → **two 32-B descriptors**: desc0 = read texture (sampled split, compression
  disabled `word1.b27=0`), desc1 = PBE (write) descriptor. Confirmed for 64×64 and 48×40.

### Format → code table — CONFIRMED on 38 obscure formats (`analysis/format_table.txt`)
`byte1 = numtype<<5 | sizeclass` (unorm0/snorm1/uint2/sint3/float4/XR5) + orthogonal sRGB (word3.b12)
holds for **every** format tested that the originals skipped: 16-bit snorm/sint/unorm (r16snorm,
rg16*, rgba16*), rgb10a2**uint** (0x49), XR (bgr10_xr 0xa9), 64/128-bit int (rg32u/s 0x4c/0x6c,
rgba32sint 0x6e), depth16unorm (=r16unorm), stencil8 (=r8uint), all BC1–BC7 (0x1d/0x1e ± numtype),
ASTC LDR/HDR/sRGB (0x18/0x19/0x1a), ETC2/EAC.
- **Clarification (not a rule violation):** `bgra10_xr` is a **64-bit** format → `byte1=0xac`
  (XR<<5 | 0x0c), *not* 32-bit packed. My initial expectation (0x09) was wrong; the rule is intact.
- **Gap fills:** depth32float_stencil8 → `0x62/0x88` (= depth32float; stencil aspect is a separate
  resource, not in this field); EAC_R11 → sizeclass `0x16`; ETC2_RGB8A1 → `0x16`.

### Twiddle variants — CONFIRMED
- **NPOT append**: 48×80, 80×48, 96×160, 33×17 all reproduce exactly (special case of the tiled model).
- **3D** = stacked 2D-Morton planes `offset=(z·Wp·Hp + tile_morton(x,y))·bpp` — 16×16×8, 0 mismatch.
- **2DArray/Cube** = linear-stacked pow2 planes (cube = 6-layer array) — 16×16×6, 0 mismatch.
- **MSAA sample-major** `offset=(N·morton+sample)·bpp`: 2×@4×4, 4×@4×4, 2×@8×8 all 0 mismatch;
  **4×@8×8 engages lossless MSAA compression** (raw samples codec-hidden) — matches `docs/tiling` §1.6.

### Compression — CONFIRMED
- **≥16×16 per-dimension threshold**: 15×15 no, 16×16 yes, 17×15 no, 15×17 no, 17×17 yes. Exact.
- **aux size = imageBytes/128**: NPOT 100×100 → aux 0x200 (=0x10000/128); 48×80 → aux 0x100 (=0x8000/128). Exact.
- **placement = baseVA + paddedImageBytes**: secondaryVA = base+0x10000 (100×100), base+0x8000 (48×80). Exact.
- **Mipmapped**: aux is placed after the **full mip pyramid** even when `mipmapLevelCount` is partial:
  128×128 mips=4 → aux @ base+0x15680 (= full 8-level chain), 96×96 mips=4 → base+0x15600 (full 7-level).
  Confirms EXP-O2G ("partial chain reserves full pyramid footprint"). (ccheck's "FAIL" here is a checker
  artifact from computing 4 levels instead of the full chain; the offsets match the full-pyramid sum exactly.)

---

## Reproduce
`sh run.sh <descr|samp|fmt|pbe|twid|comp|all>` builds `tools/iotrace` (arm64e) + the probes and captures;
then the `*check.py` analyzers verify each field/formula. Characterization of Discrepancy 2 used
`twiddle_orig.py` (the EXP-0017 GF(2) solver) on `caps/cx_*` (256/512/asym at 2/4/8/16 bpp). Raw evidence:
`analysis/RT3_evidence.txt`, `analysis/format_table.txt`, `raw/map_256x256_*.txt`, `raw/desc_*16384.txt`.

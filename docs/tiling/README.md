# A18 Pro (G17P) Texture Memory Layout — Twiddle & Lossless Compression

Clean-room documentation of how a userspace driver must lay out texture memory on the
A18 Pro / G17P (Apple9) — 2D, 3D, array, cube, MSAA, mipmapped, block-compressed, and
lossless-compressed. Learned by **hardware probing** — GPU-write a known
`texel(x,y) = encode(x,y)` pattern into a texture in the optimal layout, read the raw backing
bytes via the read-only `tools/iotrace` interposer, and infer the texel→byte map (a GF(2)
bit-permutation solve). No Apple binary was disassembled. Source: `experiments/EXP-0017-tiling/`
(`RESULTS.md` has the full evidence table). All facts **HW-validated** unless marked *inferred*.

Byte/word convention matches `../descriptors/`: `wordN` = 32-bit LE word at descriptor byte `4N`.

---

## 1. Optimal (twiddled) 2-D layout — Morton / Z-order

A 2-D texture created in the GPU's optimal layout (Metal `newTextureWithDescriptor:`, i.e. not
buffer-backed) is stored **twiddled as a ROW-MAJOR GRID OF MORTON TILES** (RT-3 correction — NOT one pure full-texture Morton block; that model is wrong for textures larger than one tile):
the interleave runs across the full address; each axis is **padded to a whole number of tiles**
(a multiple of the tile edge **T**), NOT to the next power of two — see §1.4 (RT-9 correction).

### 1.1 Offset formula (CORRECTED — RT-3 + RT-9, GF(2)-solved, 0 mismatch on non-pow2 widths 192/300/384/448/576)
The texture is a **row-major grid of square Morton tiles** of edge **T** texels. **T = the largest power-of-two square
whose byte size `T²·bpp` is ≤ 16 KiB** (the AGX page). So T is bpp-dependent (⚠ this **corrects** the earlier
"T=64 for bpp≤4 / 32 for bpp≥8" — which was **wrong for bpp1**, HW-shown by EXP-M4-06). Then the **tile-count width**
`cols = ceil(W/T)` is rounded up so the **tile-row stride is a whole number of 16-KiB pages**:

```
T    = largest 2^k with T²·bpp ≤ 0x4000       # 1→128, 2/4→64, 8/16→32 bytes-per-texel
G    = max(1, 0x4000 / (T*T*bpp))             # tiles per 16-KiB page-row granule
cols = round_up( ceil(W/T), G )               # (single-tile W ≤ T excepted)
padW = cols*T ;  padH = ceil(H/T)*T           # padH is NOT granule-rounded (horizontal-only)
```
| bpp | **T** | tile bytes (T²·bpp) | **G** | column rule | status (HW-validated) |
|---|---|---|---|---|---|
| 1 (r8) | **128** | 0x4000 | 1 | `ceil(W/128)` | **A18 (EXP-M4-06)** — 320→cols 3 (odd) proves T=128, refutes G=4 |
| 2 (r16) | 64 | 0x2000 | **2** | `round_up(ceil(W/64),2)` (even) | **A18 (EXP-M4-06)** — 320→cols 6 |
| 4 (r32) | 64 | 0x4000 | 1 | `ceil(W/64)` | A18+M4 (EXP-0017/M4-04) |
| 8 (rg32/rgba16) | 32 | 0x2000 | **2** | `round_up(ceil(W/32),2)` (even) | **A18+M4 (EXP-M4-04/05)** — 96→4,160→6,288→10 |
| 16 (rgba32) | 32 | 0x4000 | 1 | `ceil(W/32)` | A18+M4 (EXP-M4-04/05) |

The `T²·bpp ≤ 16 KiB` + 16-KiB-row-stride rules were **HW-derived on the M4 and cross-confirmed on the real A18** (0
mismatch throughout; flat `ceil(W/T)` mismatches by thousands, and `nextpow2` is refuted — e.g. bpp8 cols 6/10 and
bpp1 cols 3 are non-pow2). This closes two original A18 gaps the earlier corpus never probed (bpp8/bpp2 even-column
padding, and bpp1's T=128). With `tx = x >> log2(T)`, `ty = y >> log2(T)`:

```
element_index(x,y) = (ty · cols + tx) · T²  +  morton_D( x & (T−1), y & (T−1) )
byte_offset(x,y)   = element_index(x,y) · bytesPerPixel
```
where `morton_D(a,b) = Σ_{i<D} (a_i << 2i) | (b_i << 2i+1)`. **Within one tile it is plain Morton**, which is why
all prior ≤128-px validations passed; the tiled structure only appears once **both** dims exceed T.
> ⚠ **RT-9 correction (driver-breaking):** `cols` uses the **multiple-of-T padded width, not nextpow2**. E.g. a
> 1920-wide RT (bpp4, T=64) has `cols = 30`, NOT 32; a 384² texture has `cols = 6`, NOT 8. RT-3's `nextpow2` was
> untested for non-pow2 widths (it only tried 256/512, where mult-of-T and nextpow2 coincide).
*(Supersedes both the "pure full-texture Morton" model AND RT-3's `cols=nextpow2(W)/T`.)*

In words: **interleave the bits of x and y (x on the lower bit of each pair) up to the smaller
padded dimension, then append the remaining high bits of the larger dimension linearly.** For a
square power-of-two texture this is a full Morton curve over all bits.

### 1.2 Tile size / within-tile order
The tile boundary is at **T texels** (bpp1→128, bpp2/4→64, bpp8/16→32 — largest pow2 with T²·bpp≤16KiB, §1.1; the bpp1=128 value HW-shown by EXP-M4-06, per-bpp coverage EXP-M4-07); tiles are laid **row-major**. Within a tile it is Morton. The
"within-tile order" is the Z-order itself. Reference points on the curve:
`e0=(0,0) e1=(1,0) e2=(0,1) e3=(1,1) e4=(2,0) e5=(3,0) e6=(2,1) e7=(3,1) …`.

### 1.3 Bytes-per-pixel
The twiddle within a tile is over texel coordinates, BUT the **tile edge T depends on bpp** (bpp1→128, bpp2/4→64, bpp8/16→32 = largest pow2 with T²·bpp≤16KiB; §1.1) — RT-3 corrected the earlier bpp-independence claim, EXP-M4-06 corrected the bpp1 value. For 1/2/4-byte formats
(r8/r16/r32/rg32/rgba8/rgba16/rgba32 all validated). The byte offset is simply
`morton(x,y) · bytesPerPixel`. Equivalently: the tile is a fixed count of texels; its byte size
scales with bpp.

### 1.4 Allocation size
`paddedImageBytes = padW · padH · bytesPerPixel`, where the per-axis pad is (RT-9):

```
padDim(d, T) = ceil(d / T) · T     if d ≥ T     # round UP to a whole number of tiles (multiple of T)
             = nextpow2(d)         if d < T     # sub-tile dims fall back to the narrow interleave-append model (§1.1)
```
Examples (validated against backing-BO sizes): 48×48 r32 (48<64) → nextpow2 64×64×4 = 0x4000;
96×96 r32 → 128×128×4 = 0x10000; **384×384 rgba8 (bpp4,T64) → 384·384·4 = 0x90000** (RT-9: NOT the
nextpow2 512²·4 = 0x100000 — the tell that padding is multiple-of-T, not nextpow2). Pow2-multiple-of-T
sizes (256/512) are unchanged, which is why RT-3 didn't catch this. **`padW = round_up(ceil(W/T), G)·T`** where
`G = max(1, 0x4000/(T²·bpp))` and **T = largest pow2 with T²·bpp≤16KiB** (§1.1): (bpp1,T128,G1) (bpp2,T64,G2) (bpp4,T64,G1)
(bpp8,T32,G2) (bpp16,T32,G1). `padH = ceil(H/T)·T` (no granule rule on rows). HW-confirmed on A18+M4 (EXP-M4-04/05/06).

### 1.5 Block-compressed formats (BC/ASTC/ETC/EAC) — ✅ CONFIRMED (EXP-0028, **EXP-M4-07** for the block-tile/G rule)
Block-compressed formats apply the **same tiled-Morton curve over BLOCK coordinates**, with the
**identical §1.1 rule applied at block granularity** — substitute `element_bytes = blockBytes`
(the block is the element):

```
element(bx,by) = tiledMorton(bx, by, T_blk, cols_blk) · blockBytes
T_blk    = largest 2^k with T_blk²·blockBytes ≤ 0x4000   #  = 32 blocks for BOTH 8- and 16-byte blocks
G_blk    = 0x4000 / (T_blk²·blockBytes)                  #  = 2 for 8-byte blocks, 1 for 16-byte blocks
cols_blk = round_up( ceil(BW/T_blk), G_blk )             #  BW = blocks-wide = ceil(W/blockWidth)
padBW    = cols_blk·T_blk ; padBH = ceil(BH/T_blk)·T_blk ; BOsize = padBW·padBH·blockBytes
```

| blockBytes | formats (**all HW-validated, EXP-M4-07**) | **T_blk** | tile bytes | **G_blk** | block-column rule |
|---|---|---|---|---|---|
| **8** | BC1, BC4, ETC2_RGB8, EAC_R11 | **32** | 0x2000 (8 KiB) | **2** | `round_up(ceil(BW/32),2)` — **EVEN** |
| **16** | BC2, BC3, BC5, BC6H, BC7, ASTC 4×4…12×12, ETC2_RGBA(EAC), EAC_RG11 | **32** | 0x4000 (16 KiB) | **1** | `ceil(BW/32)` — flat |

- **T_blk = 32 blocks for every block byte-size** (both 8- and 16-byte). The **granule differs**:
  8-byte blocks (tile = 8 KiB) need **even** block-columns (`G_blk=2`), 16-byte blocks (tile = 16 KiB)
  are flat (`G_blk=1`) — exactly the bpp2/bpp8 vs bpp4/bpp16 alternation of §1.1. HW-shown on a 66×66
  block grid (odd tile count): 8-byte → `cols_blk` rounds 3→4 (padBW=128, `0x18000`; flat cols=3
  refuted); 16-byte → `cols_blk=3` survives (padBW=96, `0x24000`; nextpow2=4 refuted).
- ASTC 5×5/6×6/8×8/10×10/12×12 all use the **same 32-block tile** — T_blk depends only on `blockBytes`,
  not the block's texel footprint. A18-confirmed for BC1/BC4/EAC_R11 (padBW=128) and BC7/ASTC-4×4/ASTC-12×12
  (padBW=96). *(Supersedes the earlier "block-grid tile ≈ 32 blocks" approximation with the exact edge +
  the 8-byte-block even-column rule.)*

### 1.6 Texture-type twiddle variants (✅ HW-validated, EXP-0028 + **EXP-M4-07** per-bpp)
- **Texture-type codes** (byte0 low nibble, **4-bit**): 1D=0, 1DArray=1, 2D=2, 2DArray=3, 2DMS=4,
  3D=5, Cube=6, CubeArray=7, 2DMSArray=8. (Corrects EXP-0015's 3-bit reading.)
- **Each plane/layer/face is a full standalone-2D twiddle (§1.1) — NOT nextpow2-padded.** ⚠ **CORRECTION
  (EXP-M4-07, HW-validated at bpp1/2/4/8/16, A18-confirmed):** the per-plane layout uses the **bpp-dependent
  tile edge `T` and the `G` page-granule column rule of §1.1**, and each plane is padded to a **whole number
  of tiles** (`padW = round_up(ceil(W/T),G)·T`, `padH = ceil(H/T)·T`) — **not** to the next power of two.
  The earlier "pow2-padded" wording was a pre-RT-9 artifact (EXP-0028 probed only bpp4 at ≤16-px dims where
  nextpow2 = tile-multiple). Planes are **linear-stacked** with `planeStride = padW·padH·bpp`:
  ```
  offset(x,y,plane) = plane·(padW·padH) · bpp  +  tiledMorton(x,y,T,cols) · bpp    # cols = padW/T
  ```
  - **3D** = stacked 2D-Morton planes (NOT a 3D Morton); depth is linear/unpadded (`plane = z`). Refuted at
    bpp1 320³-plane: padW=**384** (not nextpow2 512); bpp8 160: padW=**192** (not 256).
  - **2DArray** = `plane = layer`. **Cube** = 6-layer array (`plane = face`). **CubeArray** = `6·arrayLength`
    stacked planes (`plane = cubeIndex·6 + face`); no extra per-cube padding.
  - **BO size = numPlanes · padW · padH · bpp** exactly (planes/layers/faces contiguous).
- **1DArray** = linear rows (1D isn't twiddled), stacked with `stride = max(nextpow2(W)·bpp, 128 B)`.
- **MSAA sample interleave (2DMS):** samples are the **lowest** address bits (sample-**minor** per pixel):
  `offset = (N·tiledMorton(x,y,T,cols) + sample)·bpp`, `bpp` = bytes per sample. ⚠ **REFINEMENT (EXP-M4-07):
  the pixel-tile edge `T` follows the PER-PIXEL footprint `bpp·N`, not `bpp`** — i.e. use `T = largest 2^k
  with T²·(bpp·N) ≤ 16 KiB` and `G = 16KiB/(T²·bpp·N)`. So MSAA **shrinks the Morton tile**: r32 (bpp4)
  1×→T=64 but 2× and 4×→**T=32** (HW-decisive: at 192², T=64 mismatches, T=32 is 0-mismatch). BO size
  `= padW·padH·N·bpp + aux` confirmed across bpp1/2/4/8/16. **N ∈ {2,4} only — 8× is Metal-rejected**
  (`supportsTextureSampleCount:8` = 0, device-level; descriptor creation asserts). **Both 2× and 4× engage
  MSAA lossless compression aux** at ≥8×8 (aux grows with N; bpp4 192²: 0x1000 at 2× / 0x2000 at 4× — the
  exact per-sample MSAA aux ratio is not fully pinned). Interleave HW-proven on r32(bpp4), A18-confirmed;
  other bpp are size-consistent (narrow/wide-integer MSAA raw content is capture-limited).

---

## 2. Linear layout (buffer-backed textures)

Buffer-backed textures (`newTextureWithDescriptor:offset:bytesPerRow:`) are **linear / row-major**:
`byte_offset(x,y) = y · bytesPerRow + x · bytesPerPixel`. The descriptor carries the stride:

> **bytesPerRow = (word3[14:] + 1) × 16**  (stride in 16-byte units, minus 1).

(Twiddled textures leave word3[14:] = 0; the Morton layout is implicit.) A driver that needs a
CPU-writable/linear staging image uses this path; the GPU's optimal sampling/render layout is the
twiddled one in §1.

---

## 3. Mipmaps

Mip levels are packed **consecutively after the base**, each an **independent tile-padded Morton
plane** (§1 applied at that level's dimensions, using the same `padDim(d,T)` as §1.4 — multiple-of-T,
NOT `nextpow2`; RT-9). Level *L* slot = `padDim(W>>L) · padDim(H>>L) · bpp`, floored to a
**0x80-byte minimum slot** for tiny levels. **HW-validated at bpp1/2/4/8/16** (EXP-M4-07), incl. the
0x80 floor at bpp16.

⚠ **CORRECTION (EXP-M4-07, A18-confirmed): the small-mip TAIL is 0x8000-aligned.** The naive running
sum below is off by one 16-KiB page for non-power-of-two bases. The exact rule: the **tail** — the run
of levels beginning at the **first level whose slot ≤ 0x8000** (2 pages / 32 KiB) — **starts at an offset
aligned UP to 0x8000**. Levels before the tail are packed tightly from 0; tail levels packed tightly from
the aligned start.

```
slot(L)   = max( padDim(W>>L,T)·padDim(H>>L,T)·bpp , 0x80 )
t         = min L with slot(L) ≤ 0x8000                      # first tail level
offset(L) = Σ_{i<L} slot(i)                        for L < t
          = align_up( Σ_{i<t} slot(i), 0x8000 ) + Σ_{t≤i<L} slot(i)   for L ≥ t
```
- **Pow2-square bases** are already 0x8000-aligned at the tail → no gap. **Non-pow2 bases insert one
  extra 16-KiB page** (zero-filled) at the tail boundary. This is why a **384² r32 chain = 0xcd600** (not
  the `Σ slot` value 0xc9600): the tail (L3, 48²) is aligned from 0xc4000 up to 0xc8000. HW-validated
  0-mismatch at bpp1(320²)/bpp2(320²)/bpp4(192²,384²)/bpp8(160²)/bpp16(96²) and pow2 128²/256²/64².
- **Non-square mip chains** (W≠H): allocation total confirmed, but per-level *addressing* of sub-tile
  levels (padDim<T) follows the §1.1 narrow interleave-append — not separately re-verified here; a driver
  applies §1.1 to each level. Non-square totals may differ by one 0x80 slot.

Validated (128×128 r32uint, pow2, no tail gap): L0@0x0, L1@0x10000, L2@0x14000, L3@0x15000, L4@0x15400,
L5@0x15500, L6@0x15580, L7@0x15600.

**Descriptor bits (mipmapped):** `word1 bit26 = 1` (mipmapped); `word3 bit31 = 1`;
`mipCount−1 = word5 bits[16:19]` (byte +0x16).

---

## 4. Lossless compression

The GPU applies transparent lossless compression to eligible textures, backed by a small
**auxiliary metadata buffer**.

### 4.1 When it is enabled
Compression aux is present iff:

> **the texture has NO ShaderWrite/PixelFormatView usage**
> **AND actual W ≥ 16 AND H ≥ 16 texels** (per-dimension, on *unpadded* dims).

The `W≥16 ∧ H≥16` threshold is **bpp-independent AND format-family-independent** — ✅ **HW-validated
(EXP-M4-07, A18-confirmed)** with the identical boundary (15→no, **16→yes**, 17→yes, 16×15→no, 8×32→no,
8×8→no, 64→yes) for float bpp1/2/8/16 (r8unorm, r16f, rgba16f, rgba32f), integer (r32uint, rgba8uint),
**and** packed (rgb10a2, rg11b10). Compression engages for all these families (unorm/float/uint/packed).
The aux flag/buffer is allocated at texture **creation** (no render required).

A **ShaderWrite** (read-write image) OR **PixelFormatView** texture is **never** compressed (EXP-O2B), at any size — its layout is the
plain uncompressed twiddle of §1. (This is why writable images and staging paths see raw Morton.)

### 4.2 Descriptor flags
| bit | meaning |
|---|---|
| `word1 bit27` | compression aux present |
| `word3 bit31` | texture has auxiliary layout metadata (set by compression **or** mipmaps) |
| `word4 + word5[0:11]` | **secondary VA** (aux buffer), encoded `(word4 \| word5[0:11]<<32) << 4` — 16-byte units, exactly like the base VA |

(`word1 bit26` / `word5[16:19]` remain the mip fields from §3; they coexist with the compression
fields in disjoint bit ranges.)

### 4.3 Aux buffer placement and size — ⚠ CORRECTED (EXP-M4-07, memory-safety)
- **Location:** immediately after the main image, in the **same allocation**:
  `secondaryVA = baseVA + paddedImageBytes` (HW-validated to the byte at bpp4/8/16).
- **Size (THE rule — bpp-independent in *texels*):**
  > **`aux_bytes = numTexels / 32` = 1 state byte per 8×4-texel block**, i.e.
  > **`aux_bytes = paddedImageBytes / (32·bpp)`**.

  ✅ HW-validated (A18-confirmed): `aux/texels = 1/32` **exactly** at rgba8(bpp4)/rgba16f(bpp8)/rgba32f(bpp16),
  256² and 128². In *byte* terms this is `image_bytes/128` at bpp4 but `image_bytes/256` at bpp8 and
  `image_bytes/512` at bpp16.

  ⚠ **The old `aux_bytes = image_bytes / 128` formula is WRONG for bpp≠4** — it over-counts 2× at bpp8
  and 4× at bpp16 (measured aux = 0x800 for a 256² rgba32f, where ÷128 would give 0x2000). Use `numTexels/32`.
  The main image keeps its full uncompressed footprint (compression saves bandwidth, not allocation).
- **Total allocation** for a compressed texture = `paddedImageBytes + paddedImageBytes/(32·bpp)`
  = `paddedImageBytes · (1 + 1/(32·bpp))`. (`numTexels = padW·padH` from §1.4.)

### 4.4 Aux content — per-block compression state
Each aux byte is the compression **state/mode of one 8×4-texel block**. Aux bytes are ordered in
**Morton-of-blocks** order (same curve as §1, at block granularity). Observed state values:
`0x03` (compressed constant), `0x15` (compressed smooth gradient), `0x7f` (incompressible /
stored raw). A block's raw main bytes are a codec stream when its state ≠ raw; the texture unit
decompresses transparently on read.

### 4.5 Unknowns (flagged for downstream)
The **compressed block codec** (the actual bit-layout of an 8×4 block) and the exact numeric
meaning of the state-byte values are **not decoded** — a driver can allocate and wire up
compression (flags + aux placement/size above) but must treat block *contents* as opaque, or
disable compression (omit ShaderWrite-less eligibility / clear the flags) to fall back to the
plain twiddle.

Resolved since EXP-0017 (all EXP-M4-07): compression **aux size at bpp8/16** (§4.3, memory-safety),
**eligibility threshold** bpp/format-family independence (§4.1), **3D/array/cube/MSAA twiddle** per bpp
(§1.6), **block-compressed tiling** across block byte-sizes (§1.5), **mip packing** per bpp + tail align
(§3), and compression×mipmaps (§5). Still open: the block codec bitstream, the exact **per-sample MSAA
aux ratio** (aux exists at 2×/4× and grows with N, but the precise divisor is not pinned), and the
compressed-state-byte numeric semantics.

---

## Provenance
`experiments/EXP-0017-tiling/` — `texprobe.m` (probe harness), `twiddle.py` / `mipmap.py`
(analyzers), `raw/` (hexdumps + inferred maps). Method: HW-PROBE + DATA-TRACE + OWN-SHADER.
Descriptor field cross-references: `../descriptors/README.md` (EXP-0015).

**Coverage across the full bpp / texture-type / block-size space** (§1.5 block-tile+G rule, §1.6
3D/array/cube/MSAA per bpp, §3 mip per bpp + tail align, §4.1 threshold breadth, §4.3 aux size):
`experiments/EXP-M4-07-tiling-coverage/` — `typrobe2.m` (3D/array/cube/MSAA + mip, `--upload`),
`texprobe.m` (2D + compression, extended formats), `bcprobe2.m` (17 block formats); host model-checkers
`solve3d.py` / `solvebc.py` / `solvemip.py` / `cmpx.py` / `b27check.py`. Primary device Apple **M4**;
every **correction** cross-confirmed on the **A18 Pro** (`raw/til_a18_verify.txt` — tiling-identical).
Method: HW-PROBE + OWN-SHADER + DATA-TRACE; no Apple binary disassembled.

## 5. Compression × mipmaps (EXP-O2G)
A mipmapped compressible texture gets **one contiguous aux buffer covering ALL mip levels**, placed after the full mip
chain (`auxOff = Σ padded-level-bytes`, size ≈ **totalTexels/32** = totalImageBytes/128 only at bpp4, see §4.3) — not per-level, not level-0-only. A partial chain
still reserves the full pyramid footprint + aux (independent of `mipmapLevelCount`).


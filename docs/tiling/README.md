# A18 Pro (G17P) Texture Memory Layout — Twiddle & Lossless Compression

Clean-room documentation of how a userspace driver must lay out 2-D texture memory on the
A18 Pro / G17P (Apple9). Learned by **hardware probing** — GPU-write a known
`texel(x,y) = encode(x,y)` pattern into a texture in the optimal layout, read the raw backing
bytes via the read-only `tools/iotrace` interposer, and infer the texel→byte map (a GF(2)
bit-permutation solve). No Apple binary was disassembled. Source: `experiments/EXP-0017-tiling/`
(`RESULTS.md` has the full evidence table). All facts **HW-validated** unless marked *inferred*.

Byte/word convention matches `../descriptors/`: `wordN` = 32-bit LE word at descriptor byte `4N`.

---

## 1. Optimal (twiddled) 2-D layout — Morton / Z-order

A 2-D texture created in the GPU's optimal layout (Metal `newTextureWithDescriptor:`, i.e. not
buffer-backed) is stored **twiddled as a ROW-MAJOR GRID OF MORTON TILES** (RT-3 correction — NOT one pure full-texture Morton block; that model is wrong for textures larger than one tile):
the interleave runs across the full address; storage is **padded to the next power of two in
each axis**.

### 1.1 Offset formula (CORRECTED — RT-3, GF(2)-solved, 0 mismatch on 256²/512²/NPOT)
The texture is a **row-major grid of square Morton tiles** of edge **T** texels, where **T depends on bpp**:
`T = 64 for bpp ≤ 4, T = 32 for bpp ≥ 8` (measured Morton depth D: 2/4 bpp → 6, 8/16 bpp → 5; T = 2^D).
With `tx = x >> log2(T)`, `ty = y >> log2(T)`, `cols = ceil(Wp / T)` (Wp = nextpow2(W)):

```
element_index(x,y) = (ty · cols + tx) · T²  +  morton_D( x & (T−1), y & (T−1) )
byte_offset(x,y)   = element_index(x,y) · bytesPerPixel
```
where `morton_D(a,b) = Σ_{i<D} (a_i << 2i) | (b_i << 2i+1)`. **Within one tile it is plain Morton**, which is why
all prior ≤128-px validations passed; the tiled structure only appears once **both** padded dims exceed T.
*(Superseded the earlier "pure full-texture Morton, no sub-tile, bpp-independent" model — that was wrong above one tile.)*

In words: **interleave the bits of x and y (x on the lower bit of each pair) up to the smaller
padded dimension, then append the remaining high bits of the larger dimension linearly.** For a
square power-of-two texture this is a full Morton curve over all bits.

### 1.2 Tile size / within-tile order
The tile boundary is at **T texels** (64 for bpp≤4, 32 for bpp≥8); tiles are laid **row-major**. Within a tile it is Morton. The
"within-tile order" is the Z-order itself. Reference points on the curve:
`e0=(0,0) e1=(1,0) e2=(0,1) e3=(1,1) e4=(2,0) e5=(3,0) e6=(2,1) e7=(3,1) …`.

### 1.3 Bytes-per-pixel
The twiddle within a tile is over texel coordinates, BUT the **tile size T depends on bpp** (64 for ≤4 B, 32 for ≥8 B) — RT-3 corrects the earlier bpp-independence claim. For 1/2/4-byte formats
(r8/r16/r32/rg32/rgba8/rgba16/rgba32 all validated). The byte offset is simply
`morton(x,y) · bytesPerPixel`. Equivalently: the tile is a fixed count of texels; its byte size
scales with bpp.

### 1.4 Allocation size
`paddedImageBytes = Wp · Hp · bytesPerPixel`. Examples (validated against backing-BO sizes):
48×48 rgba32? no — 48×48 r32 → 64×64×4 = 0x4000; 96×96 → 128×128×4 = 0x10000; already-pow2
sizes are not padded.

### 1.5 Block-compressed formats (BC/ASTC/ETC) — ✅ CONFIRMED (EXP-0028)
Block-compressed formats apply the **same Morton curve over block coordinates**:
`offset = morton(bx, by) · blockBytes` (blockBytes = 8 for BC1/BC4, 16 otherwise). HW-validated for
BC1/BC7/ASTC-4×4/ASTC-8×8; the 8×8 case proves the curve is over the block *index*, independent of
block texel size.

### 1.6 Texture-type twiddle variants (✅ HW-validated, EXP-0028)
- **Texture-type codes** (byte0 low nibble, **4-bit**): 1D=0, 1DArray=1, 2D=2, 2DArray=3, 2DMS=4,
  3D=5, Cube=6, CubeArray=7, 2DMSArray=8. (Corrects EXP-0015's 3-bit reading.)
- **3D** = stacked 2D-Morton planes (NOT a 3D Morton): `offset = (z·Wp·Hp + morton(x,y))·bpp`; only W,H
  are pow2-padded, depth is linear/unpadded.
- **2DArray / Cube / CubeArray** = each layer/face an independent pow2-padded Morton plane, linear-stacked:
  `offset = (layer·Wp·Hp + morton(x,y))·bpp`. Cube ≡ 6-layer array; CubeArray stores arrayLength in cubes.
- **1DArray** = linear rows (1D isn't twiddled), stacked with `stride = max(nextpow2(W)·bpp, 128 B)`.
- **MSAA sample interleave:** samples are the **lowest** address bits (sample-major per pixel):
  `offset = (N·morton(x,y) + sample)·bytesPerSample`. HW-confirmed N=2, N=4 (**8× unsupported**); 4×
  engages MSAA lossless compression at ≥8×8 (aux buffer, like color compression).

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

Mip levels are packed **consecutively after the base**, each an **independent pow2-padded Morton
plane** (§1 applied at that level's dimensions). Level *L* size = `nextpow2(W>>L) · nextpow2(H>>L)
· bytesPerPixel`, floored to a **0x80-byte minimum slot** for tiny levels.

```
offset(L) = Σ_{i < L}  max( nextpow2(W>>i) · nextpow2(H>>i) · bpp , 0x80 )   # aligned; base = level 0
```

Validated (128×128 r32uint): L0@0x0, L1@0x10000, L2@0x14000, L3@0x15000, L4@0x15400, L5@0x15500,
L6@0x15580, L7@0x15600. 96×96 confirms per-level pow2 padding (L0 uses a full 128×128 slot).

**Descriptor bits (mipmapped):** `word1 bit26 = 1` (mipmapped); `word3 bit31 = 1`;
`mipCount−1 = word5 bits[16:19]` (byte +0x16).

---

## 4. Lossless compression

The GPU applies transparent lossless compression to eligible textures, backed by a small
**auxiliary metadata buffer**.

### 4.1 When it is enabled
Compression aux is present iff:

> **the texture has NO ShaderWrite/PixelFormatView usage**
> **AND actual W ≥ 16 AND H ≥ 16 texels** (per-dimension, on *unpadded* dims, in **texels independent of bpp** — EXP-O2G: 15×15 no, 17×17 yes, 16×15/32×8 no; r8 16×16 yes / rgba16f 8×8 no).

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

### 4.3 Aux buffer placement and size
- **Location:** immediately after the main image, in the **same allocation**:
  `secondaryVA = baseVA + paddedImageBytes`.
- **Size:** `aux_bytes = image_bytes / 128` = **1 state byte per 8×4-texel block** (32 texels =
  128 bytes at rgba8). The main image keeps its full uncompressed footprint (compression saves
  bandwidth, not allocation).
- **Total allocation** for a compressed texture = `paddedImageBytes + paddedImageBytes/128`.

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
plain twiddle. Compression×mipmaps interaction, non-square small-size thresholds, and 3D/array/
cube/MSAA twiddle are untested (see `experiments/EXP-0017-tiling/RESULTS.md` §4).

---

## Provenance
`experiments/EXP-0017-tiling/` — `texprobe.m` (probe harness), `twiddle.py` / `mipmap.py`
(analyzers), `raw/` (hexdumps + inferred maps). Method: HW-PROBE + DATA-TRACE + OWN-SHADER.
Descriptor field cross-references: `../descriptors/README.md` (EXP-0015).

## 5. Compression × mipmaps (EXP-O2G)
A mipmapped compressible texture gets **one contiguous aux buffer covering ALL mip levels**, placed after the full mip
chain (`auxOff = Σ padded-level-bytes`, size ≈ totalImageBytes/128) — not per-level, not level-0-only. A partial chain
still reserves the full pyramid footprint + aux (independent of `mipmapLevelCount`).


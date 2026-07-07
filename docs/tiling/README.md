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
buffer-backed) is stored **twiddled in pure Morton / Z-order**. There is **no fixed sub-tile**:
the interleave runs across the full address; storage is **padded to the next power of two in
each axis**.

### 1.1 Offset formula
Let `Wp = nextpow2(W)`, `Hp = nextpow2(H)`, `kx = log2(Wp)`, `ky = log2(Hp)`, `n = min(kx,ky)`.
With `x_i` / `y_i` = bit *i* of the texel coordinates:

```
element_index(x,y) =  Σ_{i < n}  ( x_i << (2·i) ) | ( y_i << (2·i + 1) )       # Z-order low part
                    +  { Σ_{i ≥ n} x_i << (n + i)   if Wp > Hp                   # wider dim, high bits
                         Σ_{i ≥ n} y_i << (n + i)   if Hp > Wp
                         0                          if Wp == Hp }

byte_offset(x,y)   =  element_index(x,y) · bytesPerPixel
```

In words: **interleave the bits of x and y (x on the lower bit of each pair) up to the smaller
padded dimension, then append the remaining high bits of the larger dimension linearly.** For a
square power-of-two texture this is a full Morton curve over all bits.

### 1.2 Tile size / within-tile order
There is **no tile boundary below the whole (padded) texture** — it is one Morton block. The
"within-tile order" is the Z-order itself. Reference points on the curve:
`e0=(0,0) e1=(1,0) e2=(0,1) e3=(1,1) e4=(2,0) e5=(3,0) e6=(2,1) e7=(3,1) …`.

### 1.3 Bytes-per-pixel
The twiddle is over **texel coordinates only** — identical for 1/2/4/8/16-byte formats
(r8/r16/r32/rg32/rgba8/rgba16/rgba32 all validated). The byte offset is simply
`morton(x,y) · bytesPerPixel`. Equivalently: the tile is a fixed count of texels; its byte size
scales with bpp.

### 1.4 Allocation size
`paddedImageBytes = Wp · Hp · bytesPerPixel`. Examples (validated against backing-BO sizes):
48×48 rgba32? no — 48×48 r32 → 64×64×4 = 0x4000; 96×96 → 128×128×4 = 0x10000; already-pow2
sizes are not padded.

### 1.5 Block-compressed formats (BC/ASTC/ETC) — *inferred, not probed*
Uncompressed formats twiddle over texels. Block-compressed formats are expected to apply the
**same Morton curve over block coordinates** (e.g. 4×4-texel blocks), with the block's byte
size as the effective "bytesPerPixel". Not HW-validated in EXP-0017.

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

> **the texture has NO ShaderWrite usage** (render-target or sampled-read-only)
> **AND the image is at least ~one 16×16-texel tile** (16×16 on, 8×8/4×4 off, for rgba8).

A ShaderWrite (read-write image) texture is **never** compressed, at any size — its layout is the
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

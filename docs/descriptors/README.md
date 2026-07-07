# A18 Pro (G17P) Resource Descriptors

Clean-room documentation of the texture / sampler / buffer descriptor bit layouts a userspace
driver must emit. Learned by **change-one-Metal-parameter data tracing** (DATA-TRACE) of our own
programs' Tier-2 argument buffers + descriptor blocks (`tools/iotrace`), byte-diffing captures. No
Apple binary was disassembled. See `../../CLAUDE.md`. All fields HW-validated (diff-confirmed)
unless marked ⏳.

Binding model (from `../cmdstream/`): the Tier-2 **argument buffer** holds an 8-byte slot per bound
resource (in binding order, table at +0x14a0). **Buffers** store an inline GPU VA; **textures and
samplers** store a pointer to a descriptor block appended in the same BO. Descriptors below.

## Texture descriptor — 32 bytes (EXP-0015)
Little-endian; `wordN` = 32-bit word at byte 4N.

| field | location | encoding |
|---|---|---|
| **type** | byte0 bits[0:2] | 1D=0, 2D=2, 2DArray=3, 2DMS=4, 3D=5, Cube=6 (1D/CubeArray/MSArray ⏳ untested) |
| **channel arrangement** | byte0 hi-nibble | with byte1 forms the format |
| **format numeric type + size** | byte1 = `numtype<<5 \| sizeclass` | numtype: unorm=0, snorm=1, uint=2, sint=3, float=4. (Full 31-format table in EXP-0015 RESULTS.) |
| **swizzle** | word0 bits[16:27] | 4×3-bit destination order R,G,B,A; codes R=0,G=1,B=2,A=3,One=4,Zero=5 |
| **width−1** | word0 bits[28:31] ‖ word1 bits[0:7] | |
| **height−1** | word1 bits[10:] | |
| **sampleCount** | word1 bits[24:25] | `log2(n)−1` |
| **base VA** | word2 ‖ word3 bits[0:11] | **`VA >> 4`** (16-byte units) — HW-confirmed by VA-offset tracking |
| **sRGB** | word3 bit12 | orthogonal flag (not a format code) |
| **depth / arrayLen − 1** | word3 bits[14:] | |
| **mipCount − 1** | byte +0x16 | |
| mipmapped | word1 bit26 | set when mipmapped (see `../tiling/`) |
| compression aux present | word1 bit27 | set when the texture has a compression metadata buffer |
| aux layout metadata | word3 bit31 | set by compression **or** mipmaps |
| **secondary VA (aux buffer)** | word4 ‖ word5[0:11] | `(word4 \| word5[0:11]<<32) << 4` — compression metadata; see `../tiling/` §4 |
| linear stride | word3 bits[14:] | buffer-backed only: `bytesPerRow = (word3[14:]+1)×16` (0 for twiddled) |

Independent knobs: `bgra8` = `rgba8` + swizzle; `a8` = `r8` + swizzle; `depth32float` = `r32float`
code. **Format, swizzle, sRGB, and numeric-type are orthogonal** (Vulkan-shaped) — good for a Vulkan
driver.

## Sampler descriptor — 8 bytes (EXP-0015)
64-bit little-endian bitfield:

| field | bits | encoding |
|---|---|---|
| lodMin | [0:12] | ×64 (6 fractional bits) |
| lodMax | [13:19] | ×8 (3 frac; default 14.0) |
| maxAnisotropy | [20:22] | `log2` (3-bit → up to 128×; Metal caps 16×) |
| magFilter | 23 | nearest/linear |
| minFilter | 25 | nearest/linear |
| mipFilter | [27:28] | none / nearest / linear |
| addr S / T / R | [29:31] / [32:34] / [35:37] | edge=0, repeat=1, mirror=2, clampZero/clampBorder=3, mirrorClampEdge=5 (4/6/7 ⏳) |
| unnormalized coords | 38 | |
| compare | sense bit39 + test bits[40:42] | all 8 Metal compare funcs (table in EXP-0015 RESULTS) |
| **border color** | byte7 bits[5:6] | **2-bit preset only** (transparent/black/white) |

## Buffer descriptor (EXP-0015)
Bare **inline 8-byte GPU VA** in the argument-buffer slot; **no length/format word**.

## Capability notes (extrapolate-and-test → `../hypotheses.md`)
- **Border color is HW-limited to 3 presets** — no arbitrary RGBA in the 8-byte sampler ⇒ Vulkan custom
  border color must be **software-emulated**.
- **`clampToZero` == `clampToBorder(transparent-black)`** — one HW address mode, not two.
- **Anisotropy field is 3-bit log2** (can encode 128×) though Metal exposes only 16× — a probe candidate.
- All 8 compare functions, full channel swizzle, and sRGB/format/numeric-type orthogonality are native.

Source: `experiments/EXP-0015-descriptors/` (`tvar.m`, `descx.py`).

Full tables: [format-table.md](format-table.md)

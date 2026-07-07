# EXP-0028 Results — Descriptor format-code + texture-type twiddle completeness (G17P, Apple9)

**TL;DR.** On A18 Pro / G17P / macOS 26.6 we extended the EXP-0015 format-code table and the
EXP-0017 twiddle model to the untested cases. **60 pixel formats** were captured (block-compressed
BC1-7 / ASTC / ETC2 / EAC / PVRTC, depth/stencil, 10/11-bit packed, wide-gamut XR, and the
remaining 16-bit-normalized variants); only **`depth24unorm_stencil8` and `x24_stencil8` are
rejected** by the device (invalid pixelFormat — Z/S are separate resources on Apple Silicon).
All **nine texture-type codes are now HW-validated: 1D=0, 1DArray=1, 2D=2, 2DArray=3, 2DMS=4,
3D=5, Cube=6, CubeArray=7, 2DMSArray=8** — the type field is the full **4-bit** low nibble of
`byte0` (EXP-0015's "bits[0:2]" was too narrow; 2DMSArray=8 needs bit3). The twiddle: **3D =
stacked 2D-Morton planes** (depth linear, NOT a 3D Morton); **2DArray/Cube/CubeArray = each
layer/face an independent pow2-padded 2D-Morton plane, linear-stacked**; **1DArray = linear rows
stacked**; **MSAA interleaves samples as the LOWEST address bits** (sample-major per pixel, then
2D-Morton over pixels). **Block-compressed formats apply the plain 2D-Morton curve over BLOCK
coordinates** (BC1/BC7/ASTC-4x4/ASTC-8x8 all HW-confirmed). Every finding below is **HW-validated**
(GF(2)-exact solve or a diff-confirmed descriptor byte) unless marked *inferred*. Zero GPU wedges
across the whole matrix.

Convention: `wordN` = 32-bit LE word at descriptor byte `4N`; the 16-bit **format code** =
`(byte1<<8)|byte0`; `byte1 = numtype<<5 | sizeclass`; `byte0` = `type[0:3] | chanArr[4:7]`.

---

## 1. Texture-type codes — COMPLETE (HW-validated)

`word0` bits **[0:3]** (full low nibble of `byte0`) = texture type. Captured with rgba8unorm:

| type | code | byte0 | evidence (arr/depth field) |
|---|---|---|---|
| 1D | `0` | `0x20` | HW `type_1d` |
| **1DArray** | `1` | `0x21` | HW `type_1darray` (word3 arr−1 = 5 for 6 layers) |
| 2D | `2` | `0x22` | HW |
| 2DArray | `3` | `0x23` | HW (arr−1 = 5) |
| 2DMS | `4` | `0x24` | HW `type_2dms2/4` (sampCnt2 = log2(N)−1) |
| 3D | `5` | `0x25` | HW (depth−1 = 3 for D=4) |
| Cube | `6` | `0x26` | HW (arr field = 0) |
| **CubeArray** | `7` | `0x27` | HW `type_cubearray` (arr−1 = 1 for 2 cubes) |
| **2DMSArray** | `8` | `0x28` | HW `type_2dmsarray` (arr−1 = 1, sampCnt2 set) |

**Correction to EXP-0015 / `docs/descriptors`:** the type field is **4 bits** (`word0[0:3]`), not 3.
1DArray=1, CubeArray=7 (both previously "extrapolated") are confirmed; **2DMSArray=8** is new.
CubeArray `arrayLength` is stored in **cubes** (arr−1 = numCubes−1), not faces.

---

## 2. Extended pixel-format → descriptor-code table (60 formats, HW-validated)

`byte0` shown with type nibble = `2` (2D capture). `byte1 = numtype<<5 | sizeclass`. sRGB is the
orthogonal `word3` bit12 flag (same code as the non-sRGB variant), swizzle is `word0[16:27]`.

### 2a. Remaining 16-bit-normalized + int variants (uncompressed)
| MTLPixelFormat | byte0 | byte1 | numtype | sizeclass |
|---|---|---|---|---|
| r16snorm | `0x62` | `0x22` | snorm | `0x02` |
| r16sint | `0x62` | `0x62` | sint | `0x02` |
| rg8snorm | `0xa2` | `0x22` | snorm | `0x02` |
| rg8sint | `0xa2` | `0x62` | sint | `0x02` |
| rg16unorm | `0xe2` | `0x08` | unorm | `0x08` |
| rg16snorm | `0xe2` | `0x28` | snorm | `0x08` |
| rg16uint | `0xe2` | `0x48` | uint | `0x08` |
| rg16sint | `0xe2` | `0x68` | sint | `0x08` |
| rgba16snorm | `0xa2` | `0x2c` | snorm | `0x0c` |
| rgba16sint | `0xa2` | `0x6c` | sint | `0x0c` |
| rg32uint | `0x62` | `0x4c` | uint | `0x0c` |
| rg32sint | `0x62` | `0x6c` | sint | `0x0c` |
| rgba32sint | `0x22` | `0x6e` | sint | `0x0e` |

Confirms full numtype orthogonality (unorm/snorm/uint/sint) across the 16- and 32-bit widths.

### 2b. Packed 10/11-bit + wide-gamut extended-range (XR) — **new numtype 5**
| MTLPixelFormat | byte0 | byte1 | numtype | sizeclass | swizzle |
|---|---|---|---|---|---|
| rgb10a2uint | `0xa2` | `0x49` | uint (2) | `0x09` | RGBA |
| bgr10a2unorm | `0xa2` | `0x09` | unorm (0) | `0x09` | BGRA |
| **bgr10_xr** | `0xa2` | `0xa9` | **XR (5)** | `0x09` | BGR1 |
| **bgr10_xr_srgb** | `0xa2` | `0xa9` | XR (5) | `0x09` | BGR1 (+sRGB) |
| **bgra10_xr** | `0xe2` | `0xac` | XR (5) | `0x0c` | BGRA |
| **bgra10_xr_srgb** | `0xe2` | `0xac` | XR (5) | `0x0c` | BGRA (+sRGB) |

`numtype = 5` is an **extended-range** numeric class (distinct from unorm/snorm/uint/sint/float =
0/1/2/3/4). The XR "10" packed uses `sizeclass 0x09` (32-bpp packed) and XR "10_xr_srgb"/`bgra10_xr`
uses `0x0c` (64-bpp) — i.e. the wide 10-bit-per-channel XR container is a 64-bit format.

### 2c. Depth / stencil (only depth32float was previously confirmed)
| MTLPixelFormat | byte0 | byte1 | numtype | sizeclass | note |
|---|---|---|---|---|---|
| depth16unorm | `0x62` | `0x02` | unorm | `0x02` | = **r16unorm** code; swizzle `[R,R,R,1]` (codes 0,0,0,4) |
| depth32float | `0x62` | `0x88` | float | `0x08` | = **r32float** code (re-confirms EXP-0015); swizzle `[R,R,R,1]` |
| stencil8 | `0x22` | `0x40` | uint | `0x00` | = **r8uint** code; swizzle `[R,0,0,1]` (codes 0,5,5,4) |
| x32_stencil8 | `0x22` | `0x40` | uint | `0x00` | = stencil8 (stencil aspect only) |
| depth32float_stencil8 | `0x62` | `0x88` | float | `0x08` | depth aspect = depth32float code |
| **depth24unorm_stencil8** | — | — | — | — | **UNSUPPORTED** (pixelFormat 255 rejected) |
| **x24_stencil8** | — | — | — | — | **UNSUPPORTED** (pixelFormat 262 rejected) |

Depth/stencil "depth-ness" is **not** in the format code (a depth format = the equivalent color
code + a depth default-swizzle); Z and S are separate resources (`depth24unorm_stencil8` /
`x24_stencil8` faulted at descriptor validation — HW does not support combined 24-bit Z/S).
`depth32float_stencil8` here captured only its **depth** aspect (bound as `depth2d<float>`); the
stencil aspect's code was not separately captured.

### 2d. Block-compressed formats — **new sizeclass codes** (HW-validated)
`byte0` chanArr nibble disambiguates codec within a sizeclass; numtype carries unorm/snorm/float;
sRGB = `word3` bit12 (same code).
| family | MTLPixelFormat | byte0 | byte1 | numtype | sizeclass |
|---|---|---|---|---|---|
| PVRTC | pvrtc_rgb/rgba_4bpp | `0x62` | `0x14` | unorm | `0x14` |
| ETC2/EAC | etc2_rgb8 | `0x22` | `0x16` | unorm | `0x16` |
| | etc2_rgb8a1 | `0xa2` | `0x16` | unorm | `0x16` |
| | eac_rgba8 | `0x62` | `0x16` | unorm | `0x16` |
| | eac_r11unorm / eac_r11snorm | `0xe2` | `0x16`/`0x36` | unorm/snorm | `0x16` |
| | eac_rg11unorm / eac_rg11snorm | `0x22` | `0x17`/`0x37` | unorm/snorm | `0x17` |
| ASTC LDR | astc_4x4 | `0x22` | `0x18` | unorm | `0x18` |
| | astc_5x5 | `0xa2` | `0x18` | unorm | `0x18` |
| | astc_6x6 | `0x22` | `0x19` | unorm | `0x19` |
| | astc_8x8 | `0xe2` | `0x19` | unorm | `0x19` |
| | astc_10x10 | `0xe2` | `0x1a` | unorm | `0x1a` |
| | astc_12x12 | `0x62` | `0x1b` | unorm | `0x1b` |
| ASTC HDR | astc_4x4_hdr | `0x22` | `0x98` | **float** | `0x18` |
| | astc_6x6_hdr / astc_8x8_hdr | `0x22`/`0xe2` | `0x99` | float | `0x19` |
| BC (S3TC/RGTC) | bc1_rgba | `0x22` | `0x1d` | unorm | `0x1d` |
| | bc2_rgba | `0x62` | `0x1d` | unorm | `0x1d` |
| | bc3_rgba | `0xa2` | `0x1d` | unorm | `0x1d` |
| | bc4_runorm / bc4_rsnorm | `0xe2` | `0x1d`/`0x3d` | unorm/snorm | `0x1d` |
| BC (BPTC) | bc5_rgunorm / bc5_rgsnorm | `0x22` | `0x1e`/`0x3e` | unorm/snorm | `0x1e` |
| | bc6h_rgbfloat / bc6h_rgbufloat | `0x62`/`0xa2` | `0x9e` | float | `0x1e` |
| | bc7_rgba | `0xe2` | `0x1e` | unorm | `0x1e` |

**sizeclass map extended** (adds to EXP-0015's 0x00/0x02/0x08/0x09/0x0a/0x0c/0x0e):

| sizeclass | meaning |
|---|---|
| `0x14` | PVRTC 4bpp (legacy) |
| `0x16` | ETC2 RGB8/RGB8A1 · EAC RGBA8/R11 |
| `0x17` | EAC RG11 |
| `0x18` | ASTC 4×4 / 5×5 (LDR/HDR/sRGB via numtype+flag) |
| `0x19` | ASTC 6×6 / 8×8 |
| `0x1a` | ASTC 10×10 |
| `0x1b` | ASTC 12×12 |
| `0x1d` | BC1 / BC2 / BC3 / BC4 (S3TC + RGTC-1) |
| `0x1e` | BC5 / BC6H / BC7 (RGTC-2 + BPTC) |

Within a sizeclass the `byte0` **chanArr** nibble (0x2/0x6/0xa/0xe) selects the specific codec /
block shape. sRGB and numtype (unorm/snorm/float for the LDR/signed/HDR variants) remain fully
**orthogonal** — HDR ASTC is just `numtype=float`; signed BC/EAC is `numtype=snorm`.

**HW support (this device):** all 58 above **supported** (texture created + descriptor emitted).
Only `depth24unorm_stencil8` + `x24_stencil8` rejected. (BC full family, ASTC LDR+HDR+sRGB,
ETC2/EAC, and legacy PVRTC are all accepted on A18 Pro / Apple9.)

---

## 3. Texture-type twiddle / memory layout (HW-validated GF(2) solves)

Probe: `value(x,y,slice) = 0xA5A5<<16 | slice<<8 | y<<4 | x` (r32uint), ShaderWrite ⇒ uncompressed
optimal layout; element index `e = byte_offset / bpp`.

### 3a. 3D — **stacked 2D-Morton planes** (depth is NOT interleaved)
16×16×16: `e = [x0|y0<<1|x1<<2|y1<<3|x2<<4|y2<<5|x3<<6|y3<<7]  |  z<<8` (z at bits 8..11);
8×8×8: same with z at bits 6..8. **Slice (z) stride = Wp·Hp elements** (256 / 64), each z-slice an
independent 2D-Morton plane (§EXP-0017 §1). This is **2D-Morton slices, not a 3D Morton interleave.**
- Depth is **not** power-of-two padded: 16×16×**5** → 5 planes (total 1280 = 5·256); 12×12×4 →
  planes padded 12→16 per-plane, 4 planes.
- **`byte_offset(x,y,z) = ( z·nextpow2(W)·nextpow2(H) + morton(x,y) ) · bpp`** ;
  `alloc = D · nextpow2(W) · nextpow2(H) · bpp` (only W,H padded).

### 3b. 2DArray / Cube / CubeArray — **layer/face = one Morton plane, linear-stacked**
- 2DArray 16×16×6: `e = morton(x,y) | layer<<8`, **layer stride = Wp·Hp = 256**. Each layer an
  independent pow2-padded Morton plane.
- Cube 16×16×6: **identical to a 6-layer 2D array** — `e = morton(x,y) | face<<8`, face stride 256.
  Faces stacked in face index order (+X,−X,+Y,−Y,+Z,−Z).
- CubeArray 16×16×(6·2): `e = morton(x,y) | slice<<8`, slice stride 256, 12 planes = 6·numCubes.
- **`byte_offset = ( layer·nextpow2(W)·nextpow2(H) + morton(x,y) ) · bpp`** ; array/face count not
  padded. Cube = array with 6·N faces; the descriptor stores arrayLength in **cubes**.

### 3c. 1DArray — **linear rows, stacked with a fixed min stride**
Within a layer the content is **linear** along x (`e = x0|x1|x2|…`, no y-interleave — 1D textures
are not twiddled). Layer stride was a constant **32 elements (128 bytes) for r32** across
W = 8/16/17/32: **layer stride = max(nextpow2(W)·bpp, 128 bytes)** *(128-B floor inferred from
4 widths)*. `e = x + layer·stride`.

### 3d. MSAA sample interleave — **samples are the LOWEST address bits** (sample-major)
Probe: render r32uint MSAA target, fragment keyed on `[[sample_id]]`, StoreActionStore.
- **2 samples** (8×8): `e = sample<<0 | morton(x,y)<<1` → `e = sample + 2·morton(x,y)`.
- **4 samples** (4×4, uncompressed): `e = sample<<0 (2 bits) | morton(x,y)<<2` →
  `e = sample + 4·morton(x,y)`.
- **General: `byte_offset = ( N·morton(x,y) + sample )·bytesPerSample`** — the N samples of a pixel
  are stored **contiguously** (sample index = the log2(N) lowest bits), then pixels follow the
  standard 2D-Morton curve. Raw evidence (`raw/hex_evidence.txt`): `(0,0)s0,(0,0)s1,(1,0)s0,(1,0)s1,…`.
- **Sample count: only 2× and 4× supported** — `sampleCount=8` rejected ("not supported by device").
- **MSAA lossless compression** engages exactly like color compression (EXP-0017): 4× at ≥8×8 sets
  `word1 bit27` + a secondary/aux VA (raw samples then become a codec stream); 2× at 8×8 and 4× at
  ≤4×4 stay uncompressed (which is how the interleave above was read directly). Aux codec is opaque.

---

## 4. Block-compressed twiddle — **Morton over BLOCK coordinates** (HW-validated)

Upload per-block marker `[bx,by,0x5a,0xa5]` via `-replaceRegion:`, read raw backing:

| format | block | block bytes | solved block-slot map | layout |
|---|---|---|---|---|
| BC1 | 4×4 | 8 | `bx0\|by0<<1\|bx1<<2\|by1<<3\|bx2<<4\|by2<<5\|bx3<<6\|by3<<7` | **Morton-of-blocks** |
| BC7 | 4×4 | 16 | (identical) | Morton-of-blocks |
| ASTC 4×4 | 4×4 | 16 | (identical) | Morton-of-blocks |
| ASTC 8×8 | 8×8 | 16 | (identical) | Morton-of-blocks |

**Confirms `docs/tiling/` §1.5:** a block is the effective "pixel". `byte_offset(bx,by) =
morton(bx,by) · blockBytes`, where `(bx,by) = (⌊x/bw⌋, ⌊y/bh⌋)` over a block grid padded to the
next power of two per block-axis, and `blockBytes` = 8 (BC1/BC4) or 16 (BC2/3/5/6/7, ASTC, EAC).
The 8×8-block ASTC case shows the curve is over the **block index**, independent of block texel size.
Raw evidence: `raw/hex_evidence.txt` (block markers appear in exact Z-order).

---

## 5. Still opaque / recommended next
- **ASTC block-shape enumeration:** 6 of 14 ASTC shapes measured; the `sizeclass`(0x18–0x1b) +
  `chanArr` nibble pattern is shown but the exact nibble for 5×4/6×5/8×5/8×6/10×5/10×6/10×8/12×10
  is untested (extrapolatable, not captured).
- **`byte0` chanArr nibble internal bit-split** — still not decoded (as in EXP-0015); the full
  16-bit `(byte1<<8)|byte0` is a complete format key regardless.
- **depth32float_stencil8 stencil-aspect code** (only depth aspect captured).
- **MSAA / lossless-compression codec** (the aux state bytes and block stream) remains opaque — a
  driver allocates + wires the aux (flags + placement per EXP-0017) but treats contents as opaque
  or disables compression.
- **Non-square small-size compression thresholds for MSAA** (4× flips to compressed between 4×4 and
  8×8; exact rule per sample-count untested).

## Clean-room note
Everything here is our own MSL, our own uploaded bytes, and our own process's descriptor/backing
**data** captured via the read-only interposer, plus hardware layout inferred from known inputs. No
Apple binary was disassembled. Method mirrors EXP-0015 (DATA-TRACE) and EXP-0017 (HW-PROBE).

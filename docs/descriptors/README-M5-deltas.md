# M5 (Apple10 / G17g) resource-descriptor deltas vs A18 (G17P)

> [!IMPORTANT]
> **Scope: Apple M5 (Apple10 / G17g / T8142). NOT evidence for Apple9 (A18 Pro / M4).**
> The M5 workstream is **complete and deferred** (`CLAUDE.md`). Nothing in this file may be
> used to support an A18/G17P or M4/G16G claim, and no value here may be emitted by an Apple9
> driver without being independently established on an Apple9 target. M5 is a G17-family
> *sibling*, not the same device: treat every number as M5-only unless an `EXP-M4-*` or
> `EXP-00NN` experiment says otherwise.

Delta-form: "same as `descriptors/README.md` (A18/G17P) except as noted." Source: EXP-M5-06 (own-process
DATA-TRACE, change-one-parameter). HW-validated unless marked ⏳. No Apple binary introspected.

## Texture descriptor (32 B) — ONE delta: width/height bit split shifted +1 bit
- **DELTA:** **width−1 = word0[28:31] ‖ word1[0:10]**; **height−1 = word1[11:24]**.
  (A18 was width−1 = word0[28:31]‖word1[0:9], height−1 = word1[10:23].) HW-validated across
  64/128/256/512/1024/2048/4096 (e.g. 256×128 → W−1=255, H−1=127).
- **SAME:** type byte0[0:3] (1D=0,2D=2,2DArray=3,… — 4-bit field per A18 EXP-0028, inherited; **not re-probed on M5**); channel-arrangement byte0 hi-nibble; format code
  byte1 = `numtype<<5 | sizeclass` (rgba8=`0x0a`, r8=`0x00`, r32f=`0x88`, rgba16f=`0x8c`, rgba8i=`0x6a`,
  rgb10a2=`0x09`); swizzle word0[16:27] (4×3-bit R0G1B2A3One4Zero5); base **VA>>4** = word2‖word3[0:11];
  sRGB word3[12]; depth/arrayLen−1 word3[14:24]; sampleCount word1[24:25].

## Sampler descriptor (8 B) — BYTE-IDENTICAL to A18
All fields at the same bit positions (address S[29:31]/T[32:34]/R[35:37] edge0/repeat1/mirror2/border3;
maxAniso[20:22] log2; magFilter@23; minFilter@25; mipFilter[27:28]; compare/border as A18). HW-confirmed
by address-mode + filter sweeps.

## Buffer binding — SAME
`device T*` = bare inline 8-byte GPU VA in the arg-buffer slot (no length/format word).

## Storage-image (PBE) descriptor & attachment format word — RESOLVED (EXP-M5-10)
Both transfer from A18 with the format code at **byte+0x21** (= texture `byte1`); HW-validated by
change-one-Metal-parameter data-trace.

- **PBE / storage-image descriptor** (texture bound `access::write`/`read_write`): a **distinct descriptor**
  from the sampled one (as A18). Shared with sampled: **format code byte+0x21** (rgba8=`0x0a`, r32u=`0x48`,
  from the same `format-table` codes), base `VA>>4`. Differs: a **PBE-specific width/height split** (the STORE
  word's byte+0x23 tracks width−1 low byte: 64→`0x3f`, 256→`0xff`; height−1 tracked in the companion word) —
  same shape as A18's PBE split (width−1=word0[24:31]‖word1[0:5], height−1=word1[6:19]); observed bytes are
  consistent with it (exact bit-solve inherited from A18). **`access::read_write` binds TWO descriptors**
  (a read texture-desc + a PBE desc) and adds the read op to the kernel — HW-confirmed (shader BO + descriptor
  heap both grow). Compression disabled on write textures (as A18).
- **Render-target attachment packed-format word** (the LOAD/RENDER segment word at seg+0x20, in the attachment
  BO `0x10000118000` / tiler-heap MRT copies): **byte+0x20 = texture byte0**, **byte+0x21 = format code**,
  byte+0x22/+0x23 = swizzle. **STORE/PBE segment**: byte+0x21 = format code, **byte+0x22 = PBE component byte**
  (r=`0x00`, rgba=`0xe4`, bgra=`0xc6`). HW-validated over bgra8/rgba8/r32f/rgb10a2/rgba32f/rgba16f — identical
  to A18's `(0xf<<28)|(swizzle<<16)|(byte1<<8)|(byte0&~0x20)` formula and DESC-1 correction (format at +0x21,
  not +0x22). See `../cmdstream/README-M5-deltas.md` for the 3-segment chain + clear-color placement.

## Open (not probed on M5 this run) ⏳
Sparse/heap descriptor flags, texel-buffer (`texture_buffer<T>`) path; exact PBE width/height bit-solve on M5
(inherited from A18, byte-consistent). Tiling/twiddle + lossless compression → `../tiling/README-M5-deltas.md`.

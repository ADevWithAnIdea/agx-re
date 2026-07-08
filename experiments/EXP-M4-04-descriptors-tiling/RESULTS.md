# EXP-M4-04 — M4 resource-descriptor + texture-tiling delta vs A18 Pro

**Host:** this machine — Apple **M4** (Mac16,10), 10-core GPU, Metal 4, macOS, SIP disabled.
Everything ran **locally** (no SSH). Baselines confirmed-or-delta'd against
`docs/descriptors/README.md`, `docs/descriptors/format-table.md`, `docs/tiling/README.md`
(all A18 Pro / G17P).

**Clean-room category:** OWN-SHADER + DATA-TRACE + HW-PROBE. Every shader is our own MSL compiled
at runtime; every descriptor/backing byte is captured from **our own** process's GPU buffer
objects via the read-only `tools/iotrace` interposer (built locally, `-arch arm64e`). No Apple
binary was disassembled. Zero GPU wedges/reboots; all dispatches `status=completed (4)`.

**iotrace works on M4.** The IOKit user-client class is **`AGXAcceleratorG16G`** (vs A18's
`AGXAcceleratorG17P`) but the submission path is identical: userspace VM registered into the GPU
VM via selector 9, shared-memory + doorbell submit, BOs snapshot-able on SIGUSR1. The GPU allocator
is deterministic and **matches A18** (arg buffer lands at `0x100000e0000`, textures at
`0x10000080000`, etc.), so the A18 harnesses (`tvar.m`, `texprobe.m`, `svar.m`) and analyzers ran
unmodified except a widened probe encoding (below). Interposition did **not** fail, so the
argument-buffer / BO-readback fallback was not needed — although the tiling twiddle *is* re-derived
by exactly that readback method (write `texel(x,y)=encode(x,y)` → read raw backing → solve).

---

## Bottom line — per item

| # | item | verdict |
|---|---|---|
| 1 | Texture descriptor (32B): type/format/swizzle/14-bit W/H/baseVA/sRGB/mip/sample | **IDENTICAL** |
| 2 | Sampler (8B): addr modes / compare / filter / aniso / border / lod | **IDENTICAL** |
| 3 | PBE / storage-image + read_write two-descriptor | **IDENTICAL** (M4 also *validates* the A18-inferred width-high field) |
| 4 | Format→code table (8-format spot-check) | **IDENTICAL** |
| 5 | Tiling twiddle (T, Morton, cols, padding) | **IDENTICAL for bpp4 & bpp16; one refinement for bpp8** (see §5) |
| 6 | Lossless compression (threshold / aux size / placement / disables) | **IDENTICAL** |
| 7 | Mip packing (consecutive / padDim / 0x80 min slot) | **IDENTICAL** |

The **only** deviation from the documented A18 model is a bpp8-specific column-padding rule (§5.3)
that the A18 doc's flat `cols=ceil(W/T)` does not capture. It is almost certainly a *general* AGX
rule (a 16 KiB tile-row alignment) that A18 also follows but which the A18 tiling experiments never
probed (they used bpp4 non-pow2 widths, where the rule is invisible). Reported as a delta-vs-doc so
the doc can be corrected; not necessarily M4-vs-A18 silicon divergence.

---

## 1. Texture descriptor — IDENTICAL (raw: `raw/texture_descriptors.txt`)

Baseline rgba8unorm 4×4: `word0=0x36880a22 word1=0x00000c00 word2=0x00001c50 word3=0x00000010`
→ byte0=`0x22` (type=2D, chanArr=2), byte1=`0x0a` (unorm, sizeclass 0x0a), swizzle word0[16:27]=`0x688`
= R,G,B,A identity, width−1=height−1=3, base VA = `word2‖word3[0:11] << 4` = `0x1000001c500`. Every
field lands exactly where `format-table.md §5` says.

**8-format spot-check (byte0 / byte1) — all match the A18 table:**
r8unorm `22/00`, rgba8uint `22/4a`, r32float `62/88`, rgba32float `22/8e`, rgb10a2unorm `a2/09`,
rg11b10float `62/89`, rgba16float `a2/8c`, depth32float `62/88` (= r32float code). **swizzle** is an
orthogonal knob (bgra → word0[16:27]=`0x60a`, format byte unchanged). **sRGB** is orthogonal
(rgba8unorm_srgb → word3 bit12=1, format byte unchanged).

**14-bit width/height (the A18 RT-3 fix) — CONFIRMED IDENTICAL.** width−1 = word0[28:31]‖word1[0:9],
height−1 = word1[10:23], both 14-bit (max 16384). Probed **beyond 4096**:

| texture | width−1 | height−1 | note |
|---|---|---|---|
| 8192×16 | `0x1fff` (=8191) | 15 | width needs 13 bits — 12-bit field would truncate |
| 16×8192 | 15 | `0x1fff` (=8191) | height 14-bit via word1[10:23] |
| 16384×8 | `0x3fff` (=16383) | 7 | max 14-bit width |
| 5000×5000 | `0x1387` | `0x1387` | both axes >4096 simultaneously |

**mip / sample:** mips=4 → word1 bit26=1, word3 bit31=1, mipCount−1 = word5[16:19]=3 (byte +0x16).
2DMS samples=4 → byte0=`0x24` (type field=4), sampleCount word1[24:25]=1 (=log2(4)−1). Identical.

## 2. Sampler descriptor — IDENTICAL (raw: `raw/sampler_descriptors.txt`)

Base sampler bytes `00 00 0e 00 80 07 00 00` — **byte-identical to A18**. All field encodings match
`format-table.md §4`:

- **Address modes** (S=word0 bits[29:31], T=word1[0:2], R=word1[3:5]): edge=0, repeat=1, mirror=2,
  **clampToZero=clampToBorder=3** (single HW mode), mirrorClampToEdge=5. Confirmed on all three axes.
- **Filters:** mag bit23, min bit25, mip bits[27:28] (none/nearest/linear = 0/1/2).
- **Anisotropy** bits[20:22] = log2 (2×→1, 16×→4).
- **LOD:** lodMin bits[0:12] ×64 (2.0→`0x080`), lodMax bits[13:19] ×8 (4.0→32; default 14.0→`0x70`).
- **unnormalized** = bit38 (word1 bit6).
- **Border presets** word1 bits[29:30]: transparent-black=0, opaque-black=1, opaque-white=2 (3 presets
  only — no arbitrary RGBA, same HW limit as A18).
- **Compare funcs** (sense=word1 bit7, test=word1 bits[8:10]) — all 8 identical:
  never `s1/t7`, less `s0/t5`, lequal `s0/t4`, greater `s1/t5`, gequal `s1/t4`, equal `s0/t6`,
  nequal `s1/t6`, always `s0/t7`.

## 3. PBE / storage-image descriptor — IDENTICAL (raw: `raw/pbe_descriptors.txt`)

`access::write` binds a distinct **32-byte PBE descriptor** (not the sampled one). rgba8 64×64:
`3fe40a22 00000fc0 00008000 00000010 0…0` — **byte-identical to A18** (`EXP-G1b §1b`). Write-control
word `080e0000 00000300` identical.

- **width−1** = word0[24:31]‖word1[0:5], **height−1** = word1[6:19] (the PBE-specific split, different
  from the sampled descriptor). Confirmed: 256→byte3=`0xff`; 33→`0x20`; height 17→16, 256→255.
- **M4 additionally validates the A18-[inf] width-high field:** 300×200 → width−1=299=`0x12b` split as
  byte3=`0x2b` (low 8) **and word1[0:5]=`0x1`** (high) — A18 only tested ≤256, leaving word1[0:5]
  inferred; M4 proves it. height−1=199=`0xc7` in word1[6:19].
- **base VA** = word2‖word3[0:11] `<<4`; **linear stride** (buffer-backed) = `((word3>>12)+1)×16`
  (bb r32f 64 → word3=`0xf010` → 256 B/row). **No compression aux** (word4/5=0).
- **`access::read_write` binds TWO descriptors** — a compression-disabled **read** texture descriptor
  (`f6880a22 0000fc03 00008000 00000010`) in slot0 **and** the PBE descriptor in slot1 — identical to
  A18. HW-validated: r32f write dispatch read back row0 = `0.00 1.00 2.00 3.00`.

## 4. Format→code table

Covered in §1 (8-format spot-check). byte0 = `type[0:3] | chanArr[4:7]`, byte1 = `numtype<<5 |
sizeclass`; numtype/sizeclass/swizzle/sRGB orthogonal — **every probed value matches the A18 table.**

## 5. Tiling twiddle — the main result (raw: `raw/tiling_verify.txt`, `raw/tiling_width_sweep.txt`)

Re-derived from scratch by writing `texel(x,y)=encode(x,y)` into an optimal (ShaderWrite ⇒
uncompressed) texture, reading the **raw backing** via iotrace, and, for each candidate model,
predicting `element_index(x,y) = (ty·cols + tx)·T² + morton_D(x&(T−1), y&(T−1))`, reading the stored
value at that byte offset, and counting mismatches over the **full W×H grid**. (r32uint probe
encoding widened to 12-bit x/y so W>256 stays uniquely decodable — `work/texprobe.m`.)

### 5.1 CONFIRMED IDENTICAL to A18
- **Tile edge T:** `T=64 for bpp≤4`, `T=32 for bpp≥8` (Morton depth D = log2(T) = 6 / 5). Verified by
  which T gives 0 mismatch: bpp4 needs T=64 (T=32 fails), bpp8/16 need T=32 (T=64 fails).
- **Within-tile order is plain Morton** (0 mismatch on all sizes, including the anchor checks
  (1,0)→+1, (0,1)→+2).
- **cols = ceil(W/T)** and **row-major grid of Morton tiles**, verified on **non-pow2-tile widths that
  distinguish `ceil` from `nextpow2`** — all 0 mismatch, and `nextpow2` explicitly *fails*:

| texture | bpp | T | cols=ceil(W/T) | mismatch @ceil | mismatch @nextpow2 |
|---|---|---|---|---|---|
| r32 **384×384** | 4 | 64 | **6** | **0/147456** | 122880 (cols 8) |
| r32 **448×256** | 4 | 64 | **7** | **0/114688** | 86016 (cols 8) |
| r32 **320×320** | 4 | 64 | **5** | **0/102400** | 81920 (cols 8) |
| rgba32 96×96 | 16 | 32 | **3** | **0/9216** | 6144 (cols 4) |

- **Allocation padded to MULTIPLE-of-T, not nextpow2 (RT-9):** backing-BO sizes are exactly
  `padW·padH·bpp` with per-axis `padDim = ceil(d/T)·T`: **384×384 rgba8/r32 → `0x90000`**
  (= 384·384·4, *not* the nextpow2 512²·4 = `0x100000`); 320² → `0x64000`; 448×256 → `0x70000`;
  rgba32 96² → `0x24000` (= 96²·16, not nextpow2 128²·16). All match A18 RT-9 exactly.

### 5.2 Verdict
For **bpp4 (T=64)** and **bpp16 (T=32)** the documented A18 formula
(`cols=ceil(W/T)`, mult-of-T padding, T=64/32 tiled Morton) reproduces on M4 with **0 mismatch** —
including the RT-9-specific non-pow2 widths. **IDENTICAL.**

### 5.3 Refinement (delta vs the *documented* model) — bpp8 column padding
For **bpp8 (8-byte texels, T=32)** the tile-column count is **padded to an even number of tiles**, so
`cols ≠ ceil(W/T)` at odd tile counts. Width sweep (`raw/tiling_width_sweep.txt`), cols measured from
the tile-row stride:

| W (texels) | 32 | 64 | 96 | 128 | 160 | 192 | 224 | 256 | 288 |
|---|---|---|---|---|---|---|---|---|---|
| **bpp8** cols | 1 | 2 | **4** | 4 | **6** | 6 | **8** | 8 | **10** |
| ceil(W/32) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| **bpp16** cols | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |

So a bpp8 texture with an **odd** number of 32-tiles rounds *up* to even (padW = mult of 64, e.g.
160→192, 96→128, 288→320); a **single**-tile-wide bpp8 texture (W≤32) stays cols=1. bpp16 (and bpp4)
never do this.

**Unifying rule (0 mismatch across the whole set once applied):** the **tile-row stride is aligned to
16 KiB (`0x4000` B)**. A Morton tile is `T²·bpp` bytes = **`0x4000` for bpp4 (64²·4) and bpp16
(32²·16)** but only **`0x2000` for bpp8 (32²·8)** — so bpp8 needs *two* tiles per 16 KiB row granule,
i.e. an even tile count (the lone exception being a single-tile-wide texture, whose row is a half-
granule `0x2000`). Re-running the verifier with `cols = round-up(ceil(W/T) to 0x4000/(T²·bpp) tiles)`
gives **0 mismatch everywhere**, including the previously-failing **rg32 160×96 → cols=6, padW=192,
paddedImageBytes `0x24000`**.

**Interpretation:** this is a `cols`/`padW` rule the A18 tiling doc under-specifies (it says a flat
`cols=ceil(W/T)`). The A18 experiments validated non-pow2 widths only at **bpp4** (rgba8/r32, T=64),
where `T²·bpp = 0x4000` already, so the alignment is a no-op and the even-tile padding never shows.
It is therefore most likely a **general AGX rule A18 shares** — but that cannot be asserted from this
host (M4-only; A18 not re-probed here). Downstream: a driver computing bpp8 texture strides/allocations
with the flat `ceil(W/T)` will get the **wrong stride** for odd-tile widths; use the 16 KiB-row rule.

## 6. Lossless compression — IDENTICAL (raw: `raw/compression.txt`)

- **Enable threshold: per-dimension ≥16 texels.** 15×15 no, **16×16 yes**, 17×17 yes, 16×15 **no**,
  32×8 **no**; format-independent (r8 16×16 yes, rgba16f 8×8 no).
- **Aux placement = base + paddedImageBytes** (secondaryVA − baseVA measured): 16×16 rgba8 → `0x400`
  (=16²·4), 17×17 → `0x1000` (=32²·4 padDim), 64×64 → `0x4000`, r8 16×16 → `0x100`. **Aux size =
  imageBytes/128** (8 / 32 / 128 / 2 bytes respectively).
- **Descriptor flags:** word1 bit27 (aux present), word3 bit31, secondary VA = word4‖word5[0:11] `<<4`.
- **ShaderWrite disables** compression (write descriptor word4/5=0). **PixelFormatView disables** it
  too: ShaderRead 64×64 = compressed (`word1=0800fc03`, `word3=80000010`, `word4=00008400`);
  ShaderRead+PixelFormatView = **not** compressed (`word1=0000fc03`, `word3=00000010`, `word4=0`).

## 7. Mip packing — IDENTICAL (raw: `raw/mip.txt`)

Levels packed **consecutively after base**, each an independent tile-padded Morton plane with per-level
`padDim` (mult-of-T, RT-9), floored to a **0x80-byte minimum slot** for tiny levels.

- **128×128 r32 (T=64): byte-exact A18 match** — L0@`0x0`, L1@`0x10000`, L2@`0x14000`, L3@`0x15000`,
  L4@`0x15400`, L5@`0x15500`, L6@`0x15580`, L7@`0x15600` (the 0x80 min slot visible at L5→L6→L7).
- **384×384 mip chain total = `0xcd600`** — exact A18 match, and the RT-9 tell: impossible under
  `nextpow2` (L0 alone would be 512²·4 = `0x100000`).
- 96×96: L0 uses a full 128×128 slot (`0x10000`) — per-level mult-of-T padding confirmed.
- Descriptor: word1 bit26=1, word3 bit31=1, mipCount−1 = word5[16:19].

---

## Provenance / reproduction

`work/` — harnesses (`iotrace.c`, `tvar.m`, `texprobe.m` [r32uint widened to 12-bit], `svar.m`,
`pfv.m`), analyzers (`descauto.py` [auto-locates the arg BO — large textures shift its VA],
`tvcheck.py` [tiled-Morton offset verifier], `probe_map.py` [row/col-stride inverter], plus the A18
`descx.py`/`twiddle.py`/`mipmap.py`), and `build.sh` (`clang -arch arm64e …`). `raw/` — consolidated
text evidence + representative backing/arg-buffer `.hex` snapshots (our own process's BOs; text
hexdumps, no Apple blobs). To reproduce: `cd work && sh build.sh`, then run any harness under
`DYLD_INSERT_LIBRARIES=./iotrace.dylib … --dump` and feed the dump dir to the matching analyzer.

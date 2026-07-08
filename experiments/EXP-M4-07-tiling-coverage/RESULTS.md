# EXP-M4-07 — Tiling coverage: close TIL-1..TIL-6 across the full bpp / type / block space

**Devices:** primary **Apple M4** (10-core, Metal 4, macOS 26.4.1, local); every **correction**
cross-confirmed on the **Apple A18 Pro** (T8140, 5-core, macOS 26.6, `192.168.170.254`). The two
parts are **tiling-identical** — every A18 re-run matched M4 byte-for-byte (`raw/til_a18_verify.txt`).
**Clean-room:** HW-PROBE (known pattern in, raw layout out) + OWN-SHADER (our MSL, runtime-compiled)
+ DATA-TRACE (our own process's GPU BOs via the read-only `tools/iotrace` interposer). No Apple
binary disassembled. **Zero GPU wedges/reboots.**

Method for each gap: GPU-write/CPU-upload a known `element→encode(coord)` pattern into a texture in
the GPU optimal (twiddled) layout, snapshot the backing BO + descriptor via iotrace, then a host
**model-checker** predicts each element's byte offset for every candidate layout model and counts
mismatches over the **full grid**; the **0-mismatch** model is the true layout, and the backing-BO
size (from the sel-9 registration header, independent of the twiddle solve) is an orthogonal check.

Tooling note (clean, not a HW fact): narrow-format (r8/r16) **compute image-store** to 3D/array
either faults (r8: readback `0xff` — write unsupported) or leaves the shared backing CPU-incoherent
at snapshot; **`replaceRegion` CPU-upload** writes the twiddled backing coherently for all formats,
so all uncompressed probes use `--upload`. Validated: upload reproduces the known 2D r8/r16 twiddles
(`work/typrobe2.m`, `work/wbtest.m` documents the r8-3d-write limitation).

---

## Bottom line per gap

| gap | verdict | doc effect |
|---|---|---|
| **TIL-1** 3D/2DArray/Cube/CubeArray at bpp1/2/4/8/16 | each plane = the standalone-2D twiddle with the **bpp-dependent T + G granule**; planes **linear-stacked** at `planeStride = padW·padH·bpp` (**tile-multiple** padW, **NOT** nextpow2) | **CORRECTS §1.6** ("pow2-padded" → tile-multiple) |
| **TIL-5** compression aux size off bpp4 (memory-safety) | aux = **1 byte / 8×4-texel block = numTexels/32 = paddedImageBytes/(32·bpp)**; formula A (÷128) refuted at bpp8/16; compression engages at bpp8 & bpp16 | **CORRECTS §4.3** (resolves the ÷128 vs per-block contradiction) |
| **TIL-2** block-compressed across block byte-sizes | block grid = tiled-Morton over blocks, **T_blk = 32 blocks for every block byte-size**; **G=2 (even block-cols) for 8-byte blocks**, G=1 (flat) for 16-byte | **COMPLETES §1.5** (adds the G=2 rule for 8-byte blocks; 17 formats) |
| **TIL-3** MSAA interleave/compression | sample-**minor** interleave `morton·N+sample`; tile edge = **T(bpp·N)** (MSAA shrinks the tile); **8× Metal-rejected**; 2× **and** 4× engage compression aux | **REFINES §1.6** (tile edge follows bpp·N; 8× reject proven) |
| **TIL-4** mip-chain packing at bpp1/2/8/16 | per-level `padDim(T)` twiddle + **0x80 min-slot** confirmed all bpp; the small-mip **tail (first level ≤0x8000) starts at an offset aligned up to 0x8000** → non-pow2 bases insert one extra 16 KiB page | **CORRECTS §3** (resolves the 384²=0xcd600 vs formula gap) |
| **TIL-6** compression eligibility threshold | `W≥16 ∧ H≥16` (unpadded texels) is **bpp-independent AND format-family-independent** (float/unorm/uint/packed, bpp1..16) | **STRENGTHENS §4.1** |

---

## TIL-1 — 3D / 2DArray / Cube / CubeArray (raw: `raw/til1_solved.txt`, `raw/til1_console.txt`)

Every capture 0-mismatch under **T = largest pow2 with T²·bpp ≤ 16 KiB** + the G granule cols rule,
plane stride = `padW·padH·bpp`, planes linear-stacked. BO size = numPlanes·padW·padH·bpp exactly.

| type / fmt / dims | bpp | T | cols(rule) | padW×padH | planeStride | BO (=slices·stride) |
|---|---|---|---|---|---|---|
| 3d/2darray r8 320×320×2 | 1 | **128** | 3 (flat, G1) | 384×384 | 0x24000 | 0x48000 |
| 3d/2darray r16 320×320×2 | 2 | 64 | 6 (even, G2) | 384×320 | 0x3c000 | 0x78000 |
| 3d/2darray r32 192×192×2 | 4 | 64 | 3 (flat) | 192×192 | 0x24000 | 0x48000 |
| 3d/2darray rg32 160×160×2 | 8 | 32 | 6 (even, G2) | 192×160 | 0x3c000 | 0x78000 |
| 3d/2darray rgba32 96×96×2 | 16 | 32 | 3 (flat) | 96×96 | 0x24000 | 0x48000 |
| cube r8 320 (6 faces) | 1 | 128 | 3 | 384×384 | 0x24000 | 0xd8000 (=6·stride) |
| cube rgba32 96 (6 faces) | 16 | 32 | 3 | 96×96 | 0x24000 | 0xd8000 |

- **`nextpow2` plane padding is REFUTED**: bpp1 320 → padW **384** (not 512); bpp8 160 → padW **192**
  (not 256). The §1.6 "pow2-padded" wording is a pre-RT-9 artifact (EXP-0028 was bpp4 at ≤16-px
  dims where nextpow2 and tile-multiple coincide).
- **Cube = 6-face array; CubeArray = 6·arrayLength stacked planes** (BO size 0x1b0000 = 12·padW·padH·bpp
  for the 96² rgba32 cubearray; slices 0–6 decode 0-mismatch across the cube0→cube1 boundary,
  proving linear stacking with no per-cube padding). CubeArray slices ≥8 were not uploaded by
  `replaceRegion` (probe artifact, not a layout fact — allocation size already confirms the model).
- **A18:** bpp1 3D 320 and bpp8 array 160 re-run identical (`raw/til_a18_verify.txt`).

## TIL-5 — compression aux SIZE (raw: `raw/til5_console.txt`) — MEMORY-SAFETY

Compression engaged (word1 bit27=1) with aux placed right after the image (`secVA = baseVA + paddedImageBytes`);
`aux = totalBO − paddedImageBytes`:

| fmt | bpp | dims | paddedImageBytes | **aux** | aux/texels | formula A (÷128) | formula B (÷32·bpp) |
|---|---|---|---|---|---|---|---|
| rgba8unorm | 4 | 256² | 0x40000 | 0x800 | **1/32** | 0x800 ✓ | 0x800 ✓ (agree) |
| rgba16f | 8 | 256² | 0x80000 | **0x800** | **1/32** | 0x1000 ✗ | **0x800 ✓** |
| rgba32f | 16 | 256² | 0x100000 | **0x800** | **1/32** | 0x2000 ✗ | **0x800 ✓** |
| rgba32f | 16 | 128² | 0x40000 | **0x200** | **1/32** | 0x800 ✗ | **0x200 ✓** |

- **aux/texels = 1/32 EXACTLY in every case** → aux = **1 state byte per 8×4-texel block (32 texels)**,
  i.e. `aux_bytes = numTexels/32 = paddedImageBytes/(32·bpp)`. Formula A (`image_bytes/128`) is right
  only at bpp4 and **over-counts 2×/4× at bpp8/16**.
- Compression **engages** at bpp8 (rgba16f) and bpp16 (rgba32f). The flag is set at texture
  **creation** (no render needed).
- **A18:** rgba16f/rgba32f 256² → aux 0x800 identical (formula A refuted, B confirmed).

## TIL-2 — block-compressed tiling across block byte-sizes (raw: `raw/til2_console.txt`)

All 17 block formats supported on M4 (none TEX_FAIL). 66×66 block grid (odd block-tile count):

| block bytes | formats | T_blk | G | cols @66 blocks | padBW×padBH | BO |
|---|---|---|---|---|---|---|
| **8** | BC1, BC4, ETC2_RGB8, EAC_R11 | **32** | **2** | 4 (even) | 128×96 | 0x18000 |
| **16** | BC2/3/5/6H/7, ASTC 4/5/6/8/10/12, ETC2_RGBA(EAC), EAC_RG11 | **32** | **1** | 3 (flat) | 96×96 | 0x24000 |

- Block-tile edge **T_blk = 32 blocks for both** byte-sizes (`largest pow2 with T²·bb ≤ 16 KiB` → 32
  for bb=8 and bb=16). The **granule differs**: 8-byte blocks (tile = 8 KiB) → **G=2, block-cols
  padded EVEN**; 16-byte blocks (tile = 16 KiB) → G=1, flat. Exactly mirrors the texel rule with
  `element_bytes = blockBytes`. At 66 blocks: 8-byte → cols round to 4 (0x18000, flat cols=3 refuted);
  16-byte → cols=3 survives (0x24000, nextpow2=4 refuted).
- ASTC 5×5/6×6/10×10/12×12 all use the same 32-block tile (independent of texel footprint per block).
- **A18:** BC1/BC4/EAC_R11 → padBW=128; BC7/ASTC4/ASTC12 → padBW=96. Identical.

## TIL-3 — MSAA interleave / compression (raw: `raw/til3_console.txt`, `raw/til3_analysis.txt`)

- **Sample-minor interleave**: `element(x,y,s) = tiledMorton(x,y)·N + s`, element = bpp (bytes/sample).
  HW-confirmed on r32 at 2× and 4× (0-mismatch).
- **Tile edge follows the per-pixel footprint bpp·N, NOT bpp**: r32 (bpp4) 1×→T=64, but 2×→**T=32**
  and 4×→**T=32** (decisive: at 192², T=64 gives mismatch=200, T=32 gives 0). So MSAA **shrinks the
  Morton tile**. Cross-bpp BO sizes all match `padW(T(bpp·N))·padH·N·bpp + aux`.
- **8× is Metal-rejected**: `supportsTextureSampleCount:8` = 0 (device-level); descriptor creation
  raises a validation assertion. Max 4×.
- **2× and 4× both engage** MSAA lossless compression (aux tail beyond the image), aux grows with N
  (bpp4 192²: 0x1000 at 2× / 0x2000 at 4×). Exact per-sample MSAA aux formula not fully pinned.
- Narrow (r8/r16) and wide-integer (rg32/rgba32) MSAA raw content is **capture-limited** (render-write
  CPU-incoherence / no 64/128-bit integer MSAA render), so the interleave is HW-proven on r32(bpp4)
  and the tile-edge rule is size-consistent across bpp; other bpp are the natural generalization.
- **A18:** r32 4× → T=32 identical.

## TIL-4 — mip-chain packing per bpp (raw: `raw/til4_console.txt`, `raw/til4_verified.txt`)

Per-level twiddle = independent tile-padded Morton plane at `(W>>L,H>>L)` using the bpp-dependent T
+ G granule (`padDim = round_up(ceil(d/T),G)·T` for d≥T, else nextpow2). Level slot = `max(padW·padH·bpp, 0x80)`.

- **New rule (resolves §3):** the small-mip **tail** — the run beginning at the first level whose slot
  `≤ 0x8000` (2 pages / 32 KiB) — **starts at an offset aligned UP to 0x8000**. Pow2-square bases are
  already 0x8000-aligned (no gap); **non-pow2 bases insert one extra 16 KiB page** (zero-filled).
- With this, **0-mismatch at bpp1/2/4/8/16** for pow2 (128,256,64) AND non-pow2 (192,320,160,96,384)
  square bases; BO totals match exactly, including **r32 384² = 0xcd600** (the value the doc §3 already
  cited but whose per-level formula under-counted by 0x4000). **0x80 min-slot confirmed at bpp16.**
- Residual: non-square + non-pow2-**height** mip (e.g. 128×192) — total matches but the model-checker
  can't verify per-level addressing for **sub-tile** levels (padW<T uses §1.1 narrow-interleave, which
  the tiled solver doesn't model); non-square totals can differ by one 0x80 slot. Not a HW surprise —
  a driver uses §1.1 per level. Non-pow2-width square + all square bpp are fully verified.
- **A18:** r32 192²/384²/128² mip totals identical.

## TIL-6 — compression eligibility threshold (raw: `raw/til6_eligibility.txt`)

`compress present ⇔ (no ShaderWrite/PixelFormatView) ∧ (W≥16 ∧ H≥16 unpadded texels)`, **identical
boundary** (15→no, 16→yes, 17→yes, 16×15→no, 8×32→no, 8×8→no, 64→yes) for **every** format tested:
float bpp1/2/8/16 (r8unorm, r16f, rgba16f, rgba32f), integer bpp4 (r32uint, rgba8uint), packed bpp4
(rgb10a2, rg11b10). So the threshold is **bpp- and format-family-independent**. **A18:** r8unorm &
rgba32f → 15 no / 16 yes identical.

---

## Reproduce
`work/` — `typrobe2.m` (3D/array/cube/MSAA + mip + `--upload`), `texprobe.m` (2D + compression,
extended fmts), `bcprobe2.m` (17 block formats); solvers `solve3d.py` `solvebc.py` `solvemip.py`
`cmpx.py` `b27check.py`; sweeps `sweep_til1.sh` `sweep_msaa.sh`; `iotrace.c`. Build with
`clang -arch arm64e ...` (see any sweep header). `wbtest.m`/`mstest.m`/`mssync.m` document the
r8-3d-write and 8×-reject side findings. `raw/` — solver output logs + `til_a18_verify.txt` (A18
cross-confirm) + `backing_head/*.hex` (representative captures).

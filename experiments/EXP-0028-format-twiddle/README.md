# EXP-0028: Descriptor format-code + texture-type twiddle completeness

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + HW-PROBE + OWN-SHADER (no Apple binary disassembled)
- **Phase / question:** Capability backlog #9 — extend the 31-format descriptor table
  (`docs/descriptors/format-table.md`) and the twiddle model (`docs/tiling/README.md`)
  to the cases EXP-0015 / EXP-0017 left **untested**.
- **Device:** `user@192.168.170.254`, Apple A18 Pro / G17P, macOS 26.6, Command Line Tools
  (runtime `newLibraryWithSource:`). Workspace `~/cleanroom_work/exp0028/`.

## Hypothesis
1. The untested pixel formats (BC/ASTC/ETC/EAC, depth/stencil, 10/11-bit packed,
   wide-gamut XR, remaining 16-norm) reuse the same `byte0/byte1` scheme
   (`byte1 = numtype<<5 | sizeclass`; `byte0` = type-nibble | channel-arrangement), with
   new `sizeclass` codes for the block codecs; some are HW-unsupported and rejected by Metal.
2. Texture-type codes fill the EXP-0015 gaps: 1DArray=1, CubeArray=7, and a code for
   2DMSArray, all in `word0` low bits.
3. Arrays/cube = stacked Morton planes; 3D = either a 3D Morton or stacked 2D-Morton slices;
   MSAA interleaves the N samples in memory.
4. Block-compressed formats twiddle over **block** coordinates (Morton-of-blocks), per
   `docs/tiling/` §1.5.

## Method
- **Format & type codes (DATA-TRACE):** `fmtprobe.m` creates a texture of each format/type,
  binds it into the Metal Tier-2 argument buffer via a trivial `t.get_width()` compute kernel
  (works for *any* pixel format of a given data class — no format-specific sample needed), and
  the read-only `tools/iotrace` interposer snapshots the appended 32-byte descriptor. `fmtx.py`
  auto-locates the descriptor (the `+0x14a0` arg-slot self-referential pointer, per EXP-0011) and
  decodes `byte0/byte1/type/swizzle`. Unsupported formats are rejected by Metal and logged.
- **Type twiddle (HW-PROBE):** `typrobe.m` GPU-writes a known `value(x,y,slice) = 0xA5A5<<16 |
  slice<<8 | y<<4 | x` (r32uint) into each texture type in the optimal (ShaderWrite ⇒ no
  compression) layout — arrays/3D by compute image-store, cube through a 2D-array **view**, MSAA
  by **rendering** with a `[[sample_id]]`-keyed fragment shader (StoreActionStore). `tw3.py` reads
  the raw backing bytes and solves the byte→(x,y,slice) map as a GF(2) bit-permutation.
- **Block twiddle (HW-PROBE):** `bcprobe.m` CPU-uploads a per-**block** marker
  (`[bx,by,0x5a,0xa5]`) into a StorageModeShared compressed texture via `-replaceRegion:`; `bcx.py`
  reads the raw backing and solves block-slot → (bx,by).

All clean-room: we log our own process's descriptor/backing **data** and observe hardware layout
from known inputs; no Apple code is inspected.

## Procedure
```sh
# on device, in ~/cleanroom_work/exp0028
sh run_fmt.sh     # format + type descriptor sweep  -> analysis/decoded.txt
sh run_tw.sh      # array/cube/3D/MSAA twiddle       -> tanalysis/twiddle_solved.txt
# block-compressed: build bcprobe, run bc1/bc7/astc4/astc8, solve with bcx.py -> tanalysis/bc_solved.txt
```
Harnesses: `fmtprobe.m` `typrobe.m` `bcprobe.m`; analyzers: `fmtx.py` `tw3.py` `bcx.py`;
interposer: `iotrace.c` (copied read-only from `tools/iotrace/`).

## Raw results
`raw/fmt/decoded_formats_types.txt` (all format + type descriptor decodes),
`raw/twiddle/twiddle_solved.txt` (GF(2) solves for every type incl. MSAA + padding sweeps),
`raw/bc/bc_solved.txt` (block-Morton solves), `raw/hex_evidence.txt` (raw backing byte excerpts).
See `RESULTS.md` for the full analysis.

## Established facts → docs
- Extended format→code table (BC/ASTC/ETC/EAC/depth/stencil/XR/16-norm) → `docs/descriptors/format-table.md`.
- Type codes 1D..2DMSArray = 0..8 (4-bit field) → `docs/descriptors/` §1.
- 3D / array / cube / MSAA / block twiddle → `docs/tiling/`.

## Follow-ups
- ASTC has 14 block shapes; 6 measured — the `sizeclass`+`chanArr` enumeration pattern is shown
  but the remaining shapes' exact nibbles are untested.
- `depth32float_stencil8` stencil-aspect code (only the depth aspect was captured).
- MSAA lossless-compression codec (aux) is opaque, as with color compression (EXP-0017).

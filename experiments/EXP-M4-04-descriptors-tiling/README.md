# EXP-M4-04: M4 resource-descriptor + texture-tiling delta vs A18 Pro

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + DATA-TRACE + HW-PROBE (no Apple binary disassembled)
- **Phase / question:** confirm-or-delta the A18 Pro descriptor + tiling findings on the local **M4**
  (Mac16,10, 10-core, Metal 4). Baselines: `docs/descriptors/README.md`,
  `docs/descriptors/format-table.md`, `docs/tiling/README.md`.
- **Device state:** this host = Apple M4, macOS, SIP disabled. All work **local** (no SSH).

## Hypothesis
The M4 shares the A18 Pro (Apple9) userspace descriptor + tiling formats, so the A18 harnesses
reproduce byte-for-byte. Any deviation is a first-class result.

## Method
Built `tools/iotrace` locally (`-arch arm64e`) + the A18 Metal harnesses (`tvar.m`, `texprobe.m`,
`svar.m`) and a small `pfv.m`. All shaders are our own MSL; all descriptor/backing bytes come from
our own process's GPU BOs via the read-only iotrace interposer (DATA-TRACE). The tiling twiddle is
re-derived by writing `texel(x,y)=encode(x,y)` and reading the raw backing (HW-PROBE), then a GF(2)/
offset solve. Clean-room-legal per `../../CLAUDE.md` (allowed techniques 1–3). iotrace interposition
**works** on the M4 (`AGXAcceleratorG16G`), so the BO-readback fallback was only needed for the
tiling derivation itself.

## Procedure
`cd work && sh build.sh`; run each harness under `DYLD_INSERT_LIBRARIES=./iotrace.dylib … --dump`,
feed the dump dir to the matching analyzer (`descauto.py`, `tvcheck.py`, `probe_map.py`,
`mipmap.py`). Exact invocations are in `RESULTS.md` §Provenance.

## Raw results
`raw/` — consolidated text evidence (`texture_descriptors.txt`, `sampler_descriptors.txt`,
`pbe_descriptors.txt`, `tiling_verify.txt`, `tiling_width_sweep.txt`, `compression.txt`, `mip.txt`)
plus representative `.hex` BO snapshots. See `RESULTS.md` for the full decoded tables.

## Analysis (summary — full detail in `RESULTS.md`)
Descriptors (texture 32B, sampler 8B, PBE 32B, read_write two-descriptor), the format→code table,
14-bit dims (RT-3), compression (threshold/aux/placement/disables), and mip packing are all
**byte-identical to A18**. The tiling twiddle (T=64/32 tiled Morton, cols=ceil(W/T), mult-of-T
padding, RT-9) reproduces with **0 mismatch for bpp4 and bpp16**, including the decisive non-pow2-tile
widths (384²→0x90000, 448×256, 320²). **One refinement:** bpp8 (8-byte) textures pad the tile-column
count to an **even** number of tiles (a 16 KiB tile-row-stride alignment; a bpp8 tile is only 8 KiB),
which the A18 doc's flat `cols=ceil(W/T)` does not capture — likely a general AGX rule the A18
experiments never hit (they used bpp4). M4 also *validates* the PBE width-high field that was
inferred on A18.

## Established facts → docs (for the orchestrator)
- All descriptor/sampler/PBE/format/compression/mip facts → **IDENTICAL**, reconfirms
  `docs/descriptors/*` and `docs/tiling/*` on M4.
- **Tiling `cols`/`padW` correction (bpp8 / 16 KiB tile-row alignment)** → candidate edit to
  `docs/tiling/README.md §1.1/§1.4`. Flagged, not yet applied (orchestrator owns `docs/`).

## Follow-ups
- Re-probe the bpp8 even-tile / 16 KiB-row rule on the **A18 Pro** to decide "general AGX rule" vs
  "M4 divergence" (this experiment is M4-only).
- Sampler address-mode codes 4/6/7, swizzle 6/7, border code 3 remain untested (as on A18).

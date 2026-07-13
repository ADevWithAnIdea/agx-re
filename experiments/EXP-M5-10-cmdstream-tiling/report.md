# EXP-M5-10 — M5 cmdstream / descriptor / tiling / TBDR deltas vs A18

**Device:** Apple M5 (T8142, macOS 27.0, **8 GPU cores**, `AGXAcceleratorG17G`). **Method:** own-process
IOKit DATA-TRACE (`tools/iotrace`, arm64e) + change-one-Metal-parameter diffing + own-MSL HW-probe. No Apple
binary introspected. Every probe hard-timeout-wrapped; all ~90 GPU submits completed (STATUS=4), zero faults.

## Headline
The M5 cmdstream / descriptor / TBDR / tiling model is the **A18 model with offset-only relocations + a few
regroupings** — bit layouts, enums, and allocation math transfer; only byte offsets move. **No missing
hardware functionality found.** (Numeric evidence: `captures/decoded-tables.txt`, `ff_pool_diffs.txt`, etc.)

## Records resolved (same-as-A18 vs delta)
| Subsystem | Verdict | M5 fact |
|---|---|---|
| Depth compare/write/ref | same, relocated | `0x58000+0x170`(front)/`+0x174`(back); compare[26:24], write-disable bit21, ref[7:0]; all 8 compares HW-validated |
| Stencil op/func/mask | **bit-identical**, relocated | `+0x178`/`+0x17c`; pass[18:16]/zfail[21:19]/sfail[24:22]/compare[27:25]; all 8 ops×3 fields + independent back-face |
| Rasterizer cull/wind/fill/clamp | same, relocated | `+0x1a8`: cull[1:0], winding bit16, depth-clip/clamp[11:10]; bias-enable `+0x16c` bit17; line fill supported |
| **Blend** | **PROGRAMMABLE (confirmed)** | factor change rewrites 49 FS-shader words, **0** pool diffs; side-flags: const `+0x130` bit6, store-class `+0x188` |
| Attachment + RT format word | same, relocated | BO `0x10000118000`, 3×0x300 LOAD/RENDER/STORE, format code **byte+0x21**, STORE component byte+0x22; 6 formats |
| PBE / storage-image desc | same-as-A18 | distinct desc, format@+0x21 (rgba8`0x0a`/r32u`0x48`); `read_write`=2 descriptors |
| Clear/load/store/memoryless | same-as-A18 | clear float4 `+0x170`; Load injects read; Store=DontCare poisons; memoryless→poison `0x0eeee000` |
| Indirect dispatch | same-as-A18 | 2nd CDM record + grid-setup multiply helper |
| Indirect draw opcodes | delta (+0x0800) | non-indexed `0x6c04`, indexed `0x6c32` (A18 `0x6404`/`0x6432`) |
| Tessellation | **NATIVE, same as A18** | `drawPatches`→VDM patch-dispatch @`0x18000+0x80`, half-float factors, single graphics submit, no CDM |

## TBDR / tile (Phase 4) — `docs/pipeline/README-M5-deltas.md`
- **Tile size = 32×32, CONFIRMED on the 8-core M5** (headline; unchanged from A18's 5-core). `0x68000+0x9c4 =
  0x80000000|(ceil(W/32)−1)`, `+0x9c8 = ceil(H/32)−1` (moved +0xC0). Decisive: 1920×1080 → 59/33.
- **Programmable sample positions userspace-emittable** (as A18): BO `0x100000d8000+0x40`, N (x,y) f32, 1/16 grid.
- MSAA sample count at attachment-record+0x30; occlusion mode `0x58000+0x1c4` bit14, offset `+0x1d8` (Boolean→1,
  Counting→4096 HW-validated).

## Tiling / compression (Phase 3/4) — `docs/tiling/README-M5-deltas.md`
A18 twiddle + compression allocation model transfers **byte-for-byte**, HW-validated over 6 formats × 8 dims via
Metal `allocatedSize`: per-bpp tile edge T (bpp1→128, bpp2/4→64, bpp8/16→32), even-column page granule for
bpp2/8, mult-of-T padding (300→cols 5/6, not nextpow2), compression threshold 15→no/16→yes, aux = numTexels/32.

## Still open (honest)
- **Mesh grid-dispatch record:** our object+mesh pipeline-create aborts inside AGXMetalG17G (MSL/descriptor
  setup bug, **not** a HW fault — device recovered, tess ran after). Presence confirmed elsewhere; re-probe with
  a corrected mesh pipeline.
- **Intra-tile Morton byte order:** allocation model confirmed (validates the tiled-Morton structure), but the
  interposer didn't snapshot the compute-written texture backing this run — re-run with a draw/blit-fill probe.
- USC graphics 2-pointer-header grammar not re-derived (Tier-2 `+0x14a0` byte-identical per M5-06); FF write-mask
  per-channel packing `+0x194` partial.

## Deliverables
`docs/cmdstream/README-M5-deltas.md` (FF-pool per-bit + attachment + indirect + tessellation + occlusion),
`docs/descriptors/README-M5-deltas.md` (PBE + attachment format word), `docs/tiling/README-M5-deltas.md` (new),
`docs/pipeline/README-M5-deltas.md` (new). Scripts + decoded evidence in `scripts/` + `captures/`; bulk BO
snapshots kept on device (gitignored).

## Clean-room attestation
Own-process data-trace only; interposer wraps the public IOKit C API from our own dylib and logs
non-copyrightable command-buffer/descriptor bytes; tiling used Metal's reported `allocatedSize` for our own
textures. All MSL is ours, runtime-compiled. No Apple binary disassembled/introspected. Every decoded field
traces to observed bytes; unobserved items listed as open.

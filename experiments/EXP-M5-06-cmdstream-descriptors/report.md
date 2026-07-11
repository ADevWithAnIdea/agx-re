# EXP-M5-06 — M5 command-stream + resource-descriptor deltas vs A18/G17P

**Device:** Apple M5, T8142, macOS 27.0, 8 GPU cores, IOKit client `AGXAcceleratorG17G` (Apple10/G17g).
SIP **enabled**. **Method:** own-process IOKit DATA-TRACE via `tools/iotrace` (built `-arch arm64e`) +
change-one-parameter diffing. Clean-room: logs only *data* (selectors, struct payloads, BO bytes our own
process registered) crossing the userspace↔kernel boundary; no Apple binary disassembled/introspected.

## Headline: DYLD injection WORKS under SIP on M5
`DYLD_INSERT_LIBRARIES` into our own freshly-clang-built, non-hardened arm64e binary injects fine with
SIP enabled — SIP restricts injection into Apple/platform binaries, not ours. **Phase 2/3 on M5 needs no
SIP change.** Full `IOConnectCall*` sequence + all 27 BOs captured. Two clients (`IOSurfaceRoot` +
`AGXAcceleratorG17G`); sel-9/sel-5 parsing byte-identical to A18; IOKit call counts **49 compute / 58 draw
— identical to A18** ⇒ same shared-memory + doorbell submission model.

## Deltas found (full tables in `captures/decoded-tables.txt`; specs in `docs/*/README-M5-deltas.md`)
**Compute (CDM):** shader-ptr/grid/tg records SAME; config word `+0x00` — A18 **bit19 base dropped**,
bit23 occupancy tier retained; **tgmem-size MOVED +0x40→+0x38** with a new segmented encoding
`0x0c00000f | (fine<<11) | (coarse<<19)` (HW-validated over 19 sizes, incl. 2 blind cross-checks); arg-buffer
Tier-2 table `+0x14a0` byte-identical.
**Graphics (VDM):** draw opcodes shifted **+0x0800** (`0x61c4→0x69c4`, `0x61f2→0x69f2`); primitive/counts/
restart layout SAME; viewport transform MOVED `+0x910→+0x9d0`; FF-state pool `0x58000` same fields,
reorganized offsets (cull/winding `+0x1a8`) — per-bit enum decode is a follow-up ⏳.
**Descriptors:** texture (32 B) — **one delta:** width/height bit split shifted +1 bit
(width−1 = word0[28:31]‖word1[0:10], height−1 = word1[11:24]); everything else (type/format/swizzle/baseVA/
arrayLen) identical. **Sampler (8 B) byte-identical to A18. Buffer binding identical.**
**8-core vs 5-core:** no core-mask/count field in any client BO — consistent with firmware/kernel-managed
tiler (no userspace delta).

## Interpretation
The M5 cmdstream/descriptor model is the **A18 model with a small set of precise deltas** — same submission
mechanism, same record shapes, a handful of moved offsets / dropped-or-added bits. Confirms the "G17 sibling"
picture extends beyond the ISA. Delta drafts integrated at `docs/cmdstream/README-M5-deltas.md` and
`docs/descriptors/README-M5-deltas.md`.

## Still open (honest)
FF-pool per-bit decode (depth/stencil/blend enums, USC bind-pair grammar); attachment/PBE/storage-image
descriptors + packed format word; CDM `+0x04/+0x0c/+0x28`; sel-2 device-info struct; indirect/mesh/
tessellation records; tiling/twiddle + lossless compression per format.

## Files
`scripts/` (own harnesses cvar_compute.m/dvar_draw.m/dvar_draw2.m/tvar.m + cap*.sh + shex.py/descdump.py/
diff2.py); `captures/cmdstream_samples.txt` + `captures/decoded-tables.txt` (evidence). Bulk BO snapshots
(554 MB) on device at `~/cleanroom_work/EXP-M5-06/` (gitignored/reproducible).

## Clean-room attestation
Own-process data-trace only; interposer wraps the public IOKit C API from our own dylib and logs
non-copyrightable command-buffer/descriptor bytes. All MSL is ours, runtime-compiled. No Apple binary
disassembled or introspected. Every decoded field traces to observed bytes; unobserved items listed as open.

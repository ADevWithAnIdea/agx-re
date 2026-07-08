# EXP-M4-05: A18 Pro confirmation of the bpp-8 even-tile-column / 16-KiB-row-stride rule

- **Date:** 2026-07-07
- **Clean-room category:** HW-PROBE + DATA-TRACE + OWN-SHADER
- **Device:** **A18 Pro** (SoC T8140, 5-core GPU, Metal 4), `user@192.168.170.254`, macOS 26.6. All work on-device under `~/cleanroom_work/exp_bpp8/`.
- **Phase / question:** closes an original-A18 coverage gap surfaced by `EXP-M4-04-descriptors-tiling` (§5.3): the bpp-8 tile-column-padding rule was HW-derived on **M4** but only *inferred* for A18. `docs/tiling/README.md` currently states a flat `cols = ceil(W/T)`.

## Hypothesis
For bpp-8 (8-byte texel) optimal-layout 2D textures (tile edge T=32), the tile-column
count is padded to an **even** number of tiles: `cols = round_up_even(ceil(W/T))`, i.e.
`padW = mult of 64`. The unifying cause is a **16-KiB-aligned tile-row stride**: a Morton
tile is `T²·bpp` bytes = `0x4000` at bpp4 (64²·4) and bpp16 (32²·16) but only `0x2000` at
bpp8 (32²·8), so bpp8 needs two tiles per 16-KiB row granule → an even tile count. The A18
should reproduce the M4 numbers (96→cols 4/padW 128, 160→6/192, 288→10/320) with 0 mismatch,
and bpp4 / bpp16 controls should keep **odd** column counts (rule is bpp8-specific).

## Method
Reuse the `EXP-M4-04`/`EXP-0017` tiling-probe method verbatim (clean-room legal — HW-PROBE +
DATA-TRACE + OWN-SHADER):
1. Create a 2D texture in the GPU's **optimal** (twiddled) layout, `StorageModeShared` so its
   backing BO is CPU-mapped and thus snapshot-able (`work/texprobe.m`, our own MSL compiled at
   runtime).
2. GPU-write a known pattern `texel(x,y) = encode(x,y)` via a compute image-store (our shader).
3. Snapshot every registered BO of **our own process** with the read-only `tools/iotrace`
   interposer (`work/iotrace.c`, `-arch arm64e`), triggered by SIGUSR1 after `waitUntilCompleted`.
4. Host-side: GF(2)/offset twiddle-solve. `work/tvcheck.py` predicts, for each candidate
   `(T, cols-rule)`, `element_index(x,y) = (ty·cols+tx)·T² + morton_D(x&(T−1),y&(T−1))`, reads the
   stored value at that byte offset, and counts mismatches over the full W×H grid — the model with
   0 mismatch is the true layout. `work/probe_map.py` is the model-independent cross-check (inverts
   stored value → (x,y), reports the measured tile-col / tile-row strides). BO size comes from the
   sel-9 registration header (padW·padH·bpp).

No Apple binary was disassembled. Every shader is our own MSL; every byte is from our own
process's GPU buffer objects.

## Procedure
On the device (`~/cleanroom_work/exp_bpp8/`):
```sh
sh build.sh                       # builds iotrace.dylib + texprobe (arm64e)
sh sweep.sh                       # runs all 9 configs, each -> its own maps_<tag>/ BO dump
sh analyze.sh                     # tvcheck twiddle-solve, all configs
sh pmap.sh                        # probe_map stride inverter (bpp8 subset)
sh consolidate.sh                 # writes raw/tvcheck_all.txt, raw/probe_map_all.txt, raw/descriptors_all.txt
# 448x448 backing (0x188000 B) exceeds the default 1-MiB dump cap; recapture full:
IOTRACE_MAX_MAP=0x400000 IOTRACE_DUMP_DIR=maps_b8_448 \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./texprobe --fmt rg32uint --w 448 --h 448 --dump
```

## Raw results
See `raw/`:
- `tvcheck_all.txt` — the twiddle-solve: per-config, per-rule (ceil / nextpow2 / 16KiB-row)
  match/mismatch counts + the confirmed padW/BO-size.
- `probe_map_all.txt` — model-independent measured strides (tile-col=T²=1024, tile-row=cols·T²).
- `descriptors_all.txt` — the captured 32-B texture descriptors (logical W/H encoding; padW is
  **not** stored in the descriptor, it is implicit in the layout).
- `run_status.txt` — every dispatch `status=4` (completed); zero faults, zero reboots.
- `backing_head/*.hex` — text hexdumps of our own process's texture backing BOs (large ones
  head-truncated to 2200 lines; full backings are regenerable by re-running).

## Analysis
**A18 reproduces the M4 rule with 0 mismatch — no M4-vs-A18 delta.** See `RESULTS.md` for the
full side-by-side table. The three M4-probed odd-tile widths (96→4, 160→6, 288→10) reproduce
exactly, with flat `ceil(W/T)` explicitly FAILING (6144 / 20480 / 73728 mismatches) and the
16-KiB-row rule giving 0 mismatch. 160 and 288 also rule out `nextpow2` (cols 6, 10 are even but
non-pow2). New even-tile widths 320→10 and 448→14 confirm the rule is a no-op when the tile count
is already even. bpp4 (160, T=64) and bpp16 (96 & 160, T=32) controls keep **odd** cols → the rule
is bpp8-specific, exactly as the 16-KiB-row-stride unification predicts.

## Established facts → docs
- **bpp-8 optimal 2D textures use `cols = round_up_even(ceil(W/T))`, T=32**, i.e. tile-row stride
  aligned to 16 KiB. Confirmed on A18 (this exp) and M4 (`EXP-M4-04`). → correct the flat
  `cols=ceil(W/T)` in `docs/tiling/README.md`; add `../PROVENANCE.md` row. *(orchestrator owns docs.)*

## Follow-ups
- bpp-8 mip chains at odd-tile level widths (each level should apply the same even-column rule per
  level) were not re-probed here — likely already covered by the general per-level padW rule.

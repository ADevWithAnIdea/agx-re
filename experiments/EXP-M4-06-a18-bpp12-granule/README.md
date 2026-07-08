# EXP-M4-06: A18 bpp1 / bpp2 tile-column-padding granule (the two untested cases)

- **Date:** 2026-07-07
- **Clean-room category:** HW-PROBE + DATA-TRACE + OWN-SHADER
- **Device:** **A18 Pro** (SoC T8140, 5-core GPU, Metal 4), `user@192.168.170.254`, macOS 26.6.
  All work on-device under `~/cleanroom_work/exp_bpp12/`.
- **Phase / question:** closes the last two untested bit-depths of the optimal-layout
  tile-column-padding rule surfaced by `EXP-M4-05` (bpp8) / `EXP-M4-04`. EXP-M4-05 established
  that the tile-row stride is a whole number of 16-KiB pages: `cols = round_up(ceil(W/T), G)`
  with `G = 0x4000/(T²·bpp)`. It was HW-confirmed for bpp8 (G=2) with bpp4/bpp16 controls (G=1),
  but **bpp1 and bpp2 were only inferred**.

## Hypothesis (the prediction under test)
Assuming tile edge **T=64** for bpp≤4 (as bpp4 uses), the granule rule predicts:
- **bpp1 (r8, T=64):** tile = 64²·1 = 0x1000 → `G = 0x4000/0x1000 = 4` → **cols a multiple of 4**
  (predict W 128/192/320 → cols 4/4/8).
- **bpp2 (r16, T=64):** tile = 64²·2 = 0x2000 → `G = 2` → **cols even**
  (predict W 192/320/448 → cols 4/6/8).

Plus: `padH = ceil(H/T)·T` should NOT be granule-rounded (horizontal-only rule).

## Method
Reuse the `EXP-M4-05`/`EXP-M4-04` tiling-probe harness **verbatim** (clean-room legal —
HW-PROBE + DATA-TRACE + OWN-SHADER), only adapting the probe pattern for 1-/2-byte texels:
1. `work/texprobe.m` (our own MSL, compiled at runtime) creates a 2D texture in the GPU's
   **optimal** (twiddled) layout, `StorageModeShared` so its backing BO is CPU-mapped, then
   GPU-writes `texel(x,y)=encode(x,y)` via a compute image-store. Patterns (W-independent so the
   host solver needs no width): **r8** `v=(x*13+y*29)&0xff`; **r16** `v=((y&0xff)<<8)|(x&0xff)`.
2. `tools/iotrace` (our read-only interposer, built on-device `-arch arm64e`) snapshots every
   registered BO of **our own** process on SIGUSR1 after `waitUntilCompleted`, and records each
   BO's GPU VA + size from the sel-9 registration (DATA-TRACE).
3. Host-side `work/tvcheck.py` (twiddle-solve): for each candidate `(T∈{32,64,128}, cols-rule ∈
   {ceil, nextpow2, 16KiB-row/granule})` predict `element(x,y)=(ty·cols+tx)·T²+morton_D(x&(T−1),
   y&(T−1))`, read the stored byte, and count mismatches over the **full W×H grid**. The model
   with 0 mismatch is the true layout. `work/stride.py` is the model-independent cross-check for
   r16 (first-occurrence element index of anchor-texel values → measured tile-col/row strides,
   no assumed cols rule). BO size (padW·padH·bpp) comes straight from the sel-9 header.

No Apple binary was disassembled. Every shader is our own MSL; every byte is from our own
process's GPU buffer objects. See `../CLAUDE.md` / `../SUBAGENT_BRIEF.md`.

## Procedure
On the device (`~/cleanroom_work/exp_bpp12/`):
```sh
sh build.sh      # builds iotrace.dylib + texprobe (arm64e)
sh sweep.sh      # 11 configs (6 bpp1 + 5 bpp2), each -> its own maps_<tag>/ BO dump
sh analyze.sh    # tvcheck twiddle-solve (T=32/64/128 x 3 cols-rules), all configs
sh pmap.sh       # stride.py model-independent tile-stride reading (bpp2 / r16)
```

## Raw results
See `raw/`:
- `tvcheck_all.txt` — full-grid twiddle-solve: per-config, per-(T, cols-rule) match/mismatch +
  confirmed padW/padH/BO-size.
- `stride_all.txt` — model-independent measured strides for r16 (tile-col=T²=4096 ⇒ T=64;
  tile-row=cols·4096 ⇒ cols).
- `descriptors_all.txt` — captured 32-B texture + sampler descriptors (logical W/H; padW is NOT
  stored, it is implicit in the layout).
- `run_status.txt` + `sweep_console.txt` — every WRITE/BIND dispatch `status=4`; zero faults/reboots.
- `backing_head/*.hex` — text head-hexdumps of our own process's texture backing BOs (BO filename
  encodes gpu_va + size, which equals padW·padH·bpp for every dedicated-BO config).

## Analysis
- **bpp2 (r16) CONFIRMS the granule prediction:** tile is **T=64, G=2, `cols = round_up(ceil(W/64),
  2)` (even)**. The key discriminator **320×320 → cols 6** rules out BOTH flat `ceil` (5) and
  `nextpow2` (8) at 0 mismatch; `stride.py` independently reads tile-col stride 4096 (T=64) and
  cols 4/4/6/8/6. All BO sizes = padW·padH·2 exactly.
- **bpp1 (r8) REFUTES the G=4 prediction — the tile edge is 128, not 64.** No T=64 model fits
  192/256/320; only **T=128, `cols = ceil(W/128)` (flat, G=1)** gives 0 mismatch AND matches every
  BO size (192→256², 256→256², 320→384²). At T=128 the Morton tile is 128²·1 = **16384 B = exactly
  one 16-KiB page**, so the granule is **1** and there is NO column padding (cols 1/2/3 for
  128/192/320 — odd counts survive).
- **The EXP-M4-05 unifying principle still holds** — tile-row stride = a whole number of 16-KiB
  pages — once the **correct per-bpp tile size T** is used. The prediction only failed because it
  assumed T=64 for bpp1; the hardware uses T=128 for bpp1 (tile stays ≤16 KiB as a power-of-2
  square).
- **padH is NOT granule-rounded** (both bpp): b1_192×320 → padH=384=3·128 (odd tile count kept);
  b2_320×192 → padH=192=3·64 (odd tile count kept, not evened). Confirms the alignment is a
  horizontal row-stride rule only.

## Established facts → docs (orchestrator owns docs)
- **bpp1 optimal 2D textures use tile edge T=128**, `cols = ceil(W/128)`, `padW=cols·128` (flat, no
  granule padding — G=1). → `docs/tiling/README.md`, `../PROVENANCE.md`.
- **bpp2 optimal 2D textures use tile edge T=64**, `cols = round_up(ceil(W/64), 2)` (even),
  `padW=cols·64`. → same.
- The general rule `cols = round_up(ceil(W/T), 0x4000/(T²·bpp))` is correct **only with the correct
  per-bpp T**; corrected per-bpp T table: bpp1→128, bpp2→64, bpp4→64, bpp8→32, bpp16→32 (tile bytes
  alternate 16384/8192 ⇒ G alternates 1/2). `padH = ceil(H/T)·T`, never granule-rounded.

## Follow-ups
- Whether the T=128 (bpp1) / T=64 (bpp2) tile edge also governs mip-chain per-level padding was not
  re-probed (likely the same per-level padW rule).
- The bpp1 W≤T single-tile case (64×64) landed in a shared heap BO (size 0x20000), so its own
  allocation footprint (128²·1 = 0x4000 tile vs 64²·1 = 0x1000 sub-quadrant) is not isolable from
  BO size; the layout is confirmed single-tile (cols=1) regardless.

# EXP-M4-05 — A18 Pro confirms the bpp-8 even-tile-column / 16-KiB-row-stride rule

**Device:** Apple **A18 Pro** (SoC T8140, 5-core GPU, Metal 4), macOS 26.6, `192.168.170.254`.
Everything ran **on the A18 device** (SSH). **Clean-room:** HW-PROBE + DATA-TRACE + OWN-SHADER —
every shader is our own MSL compiled at runtime; every backing/descriptor byte is captured from
**our own** process's GPU buffer objects via the read-only `tools/iotrace` interposer (built
on-device, `-arch arm64e`). No Apple binary was disassembled. **Zero GPU wedges/reboots; all 9
dispatches `status=4` (completed).**

---

## Bottom line

**The A18 Pro reproduces the M4 bpp-8 rule with 0 mismatch — this is NOT an M4-vs-A18 silicon
delta.** For bpp-8 (8-byte texel) optimal-layout 2D textures (tile edge **T=32**), the tile-column
count is padded to an **even number of tiles**: `cols = round_up_even(ceil(W/T))`, i.e.
`padW = mult-of-64`. The unifying cause — a **16-KiB-aligned tile-row stride** (`0x4000` B) — is
confirmed on A18: it makes bpp-8 pack two `0x2000`-byte Morton tiles per row granule, forcing an
even tile count, while bpp4 (64²·4=`0x4000`) and bpp16 (32²·16=`0x4000`) already fill a granule per
tile and keep **odd** columns.

This means the flat `cols = ceil(W/T)` currently in `docs/tiling/README.md` is **wrong for bpp-8
odd-tile widths on A18** (not just M4), and must be corrected. The A18 tiling experiments never
caught it because they only probed non-pow2 widths at **bpp4** (T=64), where the 16-KiB alignment is
a no-op.

---

## Twiddle-solve evidence (raw: `raw/tvcheck_all.txt`, `raw/probe_map_all.txt`)

Each texture was GPU-written with `texel(x,y)=encode(x,y)` (rg32uint: `(x,y)`; r32uint: tagged
12-bit; rgba32uint: `(x,y,·,·)`), its **raw backing** captured, and each candidate `(T, cols-rule)`
verified by predicting the tiled-Morton byte offset and counting mismatches over the **full W×H
grid**. `probe_map.py` independently measures the tile-col stride (`e(32,0)−e(0,0)` = T² = 1024
elements) and tile-row stride (`e(0,32)−e(0,0)` = cols·T²) with **no assumed model**.

### bpp-8 (rg32uint, T=32) — the even-column probes

| W×H | ceil(W/T) → mismatch | nextpow2/T → mismatch | **16KiB-row → mismatch** | measured tile-row stride | **cols** | **padW** | **BO size** |
|---|---|---|---|---|---|---|---|
| 96×96   | 3 → **6144**  | 4 → 0     | **4 → 0** | 4·1024 | **4**  | **128** | `0x18000`  |
| 160×160 | 5 → **20480** | 8 → 20480 | **6 → 0** | 6·1024 = 6144 | **6**  | **192** | `0x3c000`  |
| 288×288 | 9 → **73728** | 16→ 73728 | **10 → 0**| 10·1024 | **10** | **320** | `0xb4000`  |
| 320×320 | 10 → 0        | 16→ 92160 | **10 → 0**| 10·1024 = 10240 | **10** | **320** | `0xc8000`  |
| 448×448 | 14 → 0        | 16→186368 | **14 → 0**| 14·1024 = 14336 | **14** | **448** | `0x188000` |
| 160×256 | 5 → **35840** | 8 → 35840 | **6 → 0** | 6·1024 | **6**  | **192** | `0x60000`  |

- **Odd-tile widths 96 / 160 / 288 (and 160×256):** flat `ceil(W/T)` FAILS with large mismatch
  counts; the 16-KiB-row rule (round-up-even) is the *only* model at 0 mismatch. **160 & 288 also
  refute `nextpow2`** — cols 6 and 10 are even but **non-power-of-two** (nextpow2 would be 8, 16 and
  fails). The rule is specifically *round to even*.
- **Even-tile widths 320 (10) / 448 (14):** even rule is a no-op (= `ceil`), both at 0 mismatch —
  confirms the padding only bites at odd tile counts. (New on A18; the M4 sweep stopped at 288.)
- **W≠H (160×256):** width drives cols=6 (padW=192), height is un-padded (padH=256) → BO
  `192·256·8 = 0x60000`. padH is **not** even-rounded — the alignment is a horizontal row-stride
  rule only, matching M4's `rg32 160×96 → cols 6 / padW 192`.
- All BO sizes equal `padW · padH · 8` exactly (allocation = mult-of-T padding + even-column padW,
  never nextpow2).

> Note on 448: the default `IOTRACE_MAX_MAP` hexdump cap is 1 MiB; the 448×448 backing is
> `0x188000` (1.57 MiB), so the first capture was **truncated** (coverage 131072/200704, exactly
> 1 MiB / 8 B). Re-captured with `IOTRACE_MAX_MAP=0x400000` → full coverage 200704/200704, 0
> mismatch at cols=14. This was a capture artifact, **not** a layout anomaly.

### Controls — the rule is bpp8-specific

| probe | fmt | bpp | T | ceil(W/T) → mismatch | nextpow2/T → mismatch | **cols** | odd? | padW | BO size |
|---|---|---|---|---|---|---|---|---|---|
| 160×160 | r32uint    | 4  | 64 | 3 → **0** | 4 → 15360 | **3** | **odd, OK** | 192 | `0x24000` |
| 96×96   | rgba32uint | 16 | 32 | 3 → **0** | 4 → 6144  | **3** | **odd, OK** | 96  | `0x24000` |
| 160×160 | rgba32uint | 16 | 32 | 5 → **0** | 8 → 20480 | **5** | **odd, OK** | 160 | `0x64000` |

bpp4 and bpp16 keep **odd** column counts (`cols = ceil(W/T)`, 0 mismatch) — no even-padding. This
is exactly what the 16-KiB-row-stride unification predicts (their `T²·bpp` already = `0x4000`), and
it pins the even-column rule as **bpp-8-specific** on A18, matching M4.

---

## A18 vs M4 — side by side (the three M4-probed bpp8 widths)

| bpp8 width | M4 cols / padW | **A18 cols / padW** | M4 BO | **A18 BO** | verdict |
|---|---|---|---|---|---|
| 96  | 4 / 128 | **4 / 128** | (—) | `0x18000` | **identical** |
| 160 | 6 / 192 | **6 / 192** | `0x3c000` | `0x3c000` | **identical** |
| 288 | 10 / 320 | **10 / 320** | (—) | `0xb4000` | **identical** |
| 160×W (W≠H) | 6 / 192 (160×96 → `0x24000`) | **6 / 192** (160×256 → `0x60000`) | scales w/ padH | scales w/ padH | **identical rule** |

M4 did not probe 320, 448, or 160×256; A18 extends the sweep and they are all consistent with the
same round-up-even / 16-KiB-row rule. **Zero A18-vs-M4 deltas.**

---

## Interpretation for the tiling doc

`docs/tiling/README.md` should replace the flat `cols = ceil(W/T)` with:

```
tile_bytes = T*T*bpp                       # 0x4000 (bpp4,bpp16), 0x2000 (bpp8), T=64(bpp<=4)/32(bpp>=8)
tiles_per_rowgranule = max(1, 0x4000 // tile_bytes)   # 1 for bpp4/bpp16, 2 for bpp8
cols = round_up(ceil(W/T), tiles_per_rowgranule)      # tile-row stride aligned to 16 KiB
padW = cols * T                            # bpp8 odd-tile widths -> mult-of-64
padH = ceil(H/T) * T                       # rows NOT granule-aligned
paddedImageBytes = padW * padH * bpp       # == backing-BO size
```

A driver computing bpp-8 texture strides/allocations with the flat `ceil(W/T)` will emit the
**wrong stride** for odd-tile widths (96→wrong, 160→wrong, 288→wrong, …). HW-validated on A18 here
and on M4 in `EXP-M4-04`.

---

## Provenance / reproduction

`work/` — harness (`texprobe.m` our MSL, `iotrace.c` the read-only interposer) + host-side solvers
(`tvcheck.py` tiled-Morton offset verifier, `probe_map.py` model-independent stride inverter,
`descauto.py` descriptor locator) + `build.sh` and the driver scripts (`sweep.sh`, `analyze.sh`,
`pmap.sh`, `consolidate.sh`). `raw/` — consolidated solver output (`tvcheck_all.txt`,
`probe_map_all.txt`, `descriptors_all.txt`), `run_status.txt` (all `status=4`), and
`backing_head/*.hex` (text hexdumps of our own process's texture backing BOs; large ones
head-truncated to 2200 lines — full backings regenerable by re-running). To reproduce on the A18:
`sh build.sh && sh sweep.sh && sh analyze.sh` (then the 448 full-capture line in README.md).

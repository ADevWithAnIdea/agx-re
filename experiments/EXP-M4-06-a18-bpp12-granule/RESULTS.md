# EXP-M4-06 — A18 bpp1 refutes the G=4 prediction (tile is 128, not 64); bpp2 confirms G=2

**Device:** Apple **A18 Pro** (SoC T8140, 5-core GPU, Metal 4), macOS 26.6, `192.168.170.254`.
Everything ran **on the A18 device** (SSH). **Clean-room:** HW-PROBE + DATA-TRACE + OWN-SHADER —
every shader is our own MSL compiled at runtime; every backing/descriptor byte and every BO size
is captured from **our own** process's GPU buffer objects via the read-only `tools/iotrace`
interposer (built on-device, `-arch arm64e`). No Apple binary was disassembled.
**Zero GPU wedges/reboots; all 22 dispatches (11 WRITE + 11 BIND) `status=4` (completed).**

---

## Bottom line

| bit depth | prediction under test | **A18 verdict** |
|---|---|---|
| **bpp2 (r16)** | T=64, `G=2`, cols even = `round_up(ceil(W/64),2)` | **CONFIRMED, 0 mismatch** (320→cols 6 rules out ceil=5 AND nextpow2=8) |
| **bpp1 (r8)** | T=64, `G=4`, cols mult-of-4 | **REFUTED.** The tile edge is **128, not 64** ⇒ `G=1`, `cols = ceil(W/128)` (flat, odd counts survive). No mult-of-4 padding. |

The bpp1 refutation is **not** a break in the EXP-M4-05 principle ("tile-row stride = a whole
number of 16-KiB pages"); it holds once the **correct per-bpp tile size** is used. The prediction
mis-assumed T=64 for bpp1. The hardware's bpp1 Morton tile is **128×128 = 16384 B = exactly one
16-KiB page**, so its granule is 1 and no column padding is applied.

---

## bpp2 (r16uint) — granule G=2 CONFIRMED (raw: `raw/tvcheck_all.txt`, `raw/stride_all.txt`)

Twiddle-solve counts mismatches over the **full W×H grid** for each `(T, cols-rule)`; the
model-independent `stride.py` reads tile strides with NO assumed cols rule.

| W×H | ceil→miss | nextpow2→miss | **granule(G2)→miss** | measured tile-row stride | **cols** | rule | **padW** | **padH** | **BO size** |
|---|---|---|---|---|---|---|---|---|---|
| 192×192 | 3 → 24576 | 4 → **0** | **4 → 0** | 16384 = 4·4096 | **4** | round_up(3,2)=4 | **256** | 192 | `0x18000` |
| 256×256 (ctrl) | 4 → **0** | 4 → **0** | **4 → 0** | 16384 = 4·4096 | **4** | ceil=granule | 256 | 256 | `0x20000` |
| **320×320** | 5 → 77824 | 8 → 77824 | **6 → 0** | 24576 = 6·4096 | **6** | round_up(5,2)=6 | **384** | 320 | `0x3c000` |
| 448×448 | 7 → 159744 | 8 → **0** | **8 → 0** | 32768 = 8·4096 | **8** | round_up(7,2)=8 | **512** | 448 | `0x70000` |
| 320×192 | 5 → 40960 | 8 → 36864 | **6 → 0** | 24576 = 6·4096 | **6** | width→6, **padH=192** | 384 | **192** | `0x24000` |

- **All at T=64** (tile-col stride = 4096 = T², measured independently). ceil is refuted at every
  odd-tile width; **320×320 is decisive** — cols 6 rules out both ceil (5) and nextpow2 (8).
- **W≠H (320×192):** width drives cols=6 (padW=384); **padH=192 = 3·64 is NOT granule-rounded**
  (an odd tile count survives — if H were evened like W it would be 4·64=256 and BO `0x30000`,
  but it is `0x24000` = 384·192·2). Alignment is a horizontal row-stride rule only.
- Every BO size = padW·padH·2 exactly (from the sel-9 registration header — independent of the
  twiddle-solve).

## bpp1 (r8uint) — G=4 REFUTED; tile edge is 128, flat cols (raw: `raw/tvcheck_all.txt`)

Only **T=128** yields 0 mismatch at the non-single-tile widths (T=64 and T=32 fail at every rule):

| W×H | T=64 best (all fail ≥128) | **T=128 ceil→miss** | T=128 nextpow2→miss | **cols** | **padW** | **padH** | **BO size** | check |
|---|---|---|---|---|---|---|---|---|
| 64×64  | (single tile) | 1 → **0** | — | **1** | 128* | 128* | `0x4000`* | W≤T single tile |
| 128×128 | cols2 → 0 (≡T128 cols1) | 1 → **0** | 1 → 0 | **1** | 128 | 128 | `0x4000` | one 128-tile = 16 KiB |
| 192×192 | **all fail** (≥16351) | 2 → **0** | 2 → 0 | **2** | **256** | 256 | `0x10000` | T=128 only |
| 256×256 (ctrl) | all fail (32768) | 2 → **0** | 2 → 0 | **2** | 256 | 256 | `0x10000` | T=128 only |
| **320×320** | all fail (≥77762) | **3 → 0** | 4 → 57281 | **3** | **384** | 384 | `0x24000` | **odd cols=3 (flat), NOT nextpow2** |
| 192×320 | all fail | 2 → **0** | 2 → 0 | **2** | 256 | **384** | `0x18000` | **padH=384=3·128 not rounded** |

\* `64×64` was heap-suballocated (shared BO `0x20000`); layout is confirmed single-tile (cols=1),
but its own footprint isn't isolable from BO size. `128×128` is the clean single-128-tile datum
(dedicated BO `0x4000` = 16384 = 128²·1).

- **G=4 would predict** padW 256/256/512 for W 128/192/320. **Measured** padW 128/256/384 =
  `ceil(W/128)·128`. The prediction is refuted; there is **no mult-of-4 (or even, or nextpow2)
  column rounding** for bpp1. `320×320 → cols 3` (odd) is the sharpest proof — a granule/pow2 rule
  would force 4/8.
- The reason: bpp1's Morton tile at **T=128** is `128²·1 = 0x4000` = **one full 16-KiB page**, so
  `G = 0x4000/tile_bytes = 1`. The row stride is page-aligned for any cols. Consistent with the
  bpp4/bpp16 controls (also G=1) in EXP-M4-05.

---

## Corrected, unified per-bpp tiling table (all HW-validated)

`tile_bytes = T²·bpp`; `G = 0x4000 / tile_bytes`; `cols = round_up(ceil(W/T), G)`;
`padW = cols·T`; `padH = ceil(H/T)·T` (never granule-rounded); `paddedImageBytes = padW·padH·bpp`.

| bpp | fmt (example) | **T** | tile_bytes | **G** | cols rule | source |
|---|---|---|---|---|---|---|
| 1  | r8      | **128** | 0x4000 (16 KiB) | **1** | `ceil(W/128)` (flat) | **EXP-M4-06 (this)** |
| 2  | r16     | **64**  | 0x2000 (8 KiB)  | **2** | `round_up(ceil(W/64),2)` (even) | **EXP-M4-06 (this)** |
| 4  | r32     | 64  | 0x4000 | 1 | `ceil(W/64)` | EXP-M4-04/05 control |
| 8  | rg32    | 32  | 0x2000 | 2 | `round_up(ceil(W/32),2)` (even) | EXP-M4-05 |
| 16 | rgba32  | 32  | 0x4000 | 1 | `ceil(W/32)` | EXP-M4-05 control |

The single knob is the **tile edge T** = largest power-of-2 square whose byte size ≤ 16 KiB:
`T` = 128/64/64/32/32 for bpp 1/2/4/8/16. `tile_bytes` alternates 16384/8192, so `G` alternates
1/2. Everything reduces to: **the tile-row stride is a whole number of 16-KiB pages.** A driver that
hardcodes `G=4` for bpp1 (or T=64 for bpp1) emits the **wrong stride/allocation** (e.g. 320-wide
r8 would over-allocate 512 vs the correct 384).

---

## Provenance / reproduction

`work/` — harness: `texprobe.m` (our MSL; r8/r16 patterns), `iotrace.c` (read-only interposer),
host-side solvers `tvcheck.py` (full-grid twiddle-solve, T∈{32,64,128}) and `stride.py`
(model-independent r16 tile-stride reader), plus `build.sh`/`sweep.sh`/`analyze.sh`/`pmap.sh`.
`raw/` — `tvcheck_all.txt`, `stride_all.txt`, `descriptors_all.txt`, `run_status.txt`,
`sweep_console.txt` (all `status=4`), and `backing_head/*.hex` (head-hexdumps of our own texture
backing BOs; the BO filename encodes gpu_va + size). Reproduce on the A18:
`sh build.sh && sh sweep.sh && sh analyze.sh && sh pmap.sh`.

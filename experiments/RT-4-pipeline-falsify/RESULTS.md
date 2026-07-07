# RT-4 Results — red-team falsification of the TBDR pipeline facts

Adversarial re-verification of `docs/pipeline/README.md` (EXP-0021). Device: Apple A18 Pro /
G17P, macOS 26.6 (Darwin 25.6.0, T8140). All draws below completed (`status=4`) unless noted.
Method: change-one-Metal-parameter, capture registered GPU BOs under `tools/iotrace`, byte-diff.
**[HW]** = a real hardware dispatch confirmed it; a byte-diff on captured control BOs is the evidence.

## Verdict summary

| # | Claim | Verdict |
|---|---|---|
| 1 | Tile 32×32 fixed, bpp-independent, `+0x904/+0x908` formula | **CONFIRMED** (strengthened) |
| 2a | Per-attachment 0x20-byte record; bgra8 stride 0x1000 | **CONFIRMED** (extended to 8 attach + mixed fmt) |
| 2b | `Σ tile_area×bpp×samples` vs **32 KiB** = imageblock feasibility gate | **DISCREPANCY** |
| 3 | MSAA sample count `+0x24` (2×`0x08`/4×`0x09`); 8× rejected; relocation | **CONFIRMED** |
| 4 | Memoryless: clear bit27 + poison `0x0eeee000` + zero backing + shrink | **CONFIRMED** (color-1×/MSAA/depth) |
| 5 | Load/store 0x300-seg chain; store-program `0x6f`; DontCare poison | **CONFIRMED** |
| 6a | Programmable sample positions **absent** from client BOs | **DISCREPANCY (FALSIFIED)** |
| 6b | Depth/ZLS store **absent** from client BOs | **CONFIRMED** |

Two discrepancies. The headline one (6a) directly reverses a documented "route-to-kernel"
negative: **custom sample positions ARE emitted into a userspace BO.**

---

## Claim 1 — Tile is 32×32 fixed, does not shrink with bpp — **CONFIRMED (strengthened)**

`0x68000 +0x904 = 0x80000000 | (ceil(W/32)−1)`, `+0x908 = ceil(H/32)−1`. Verified across a far
wider adversarial sweep than EXP-0021 (`raw/hex/TILEGRID.txt`, `+0x900` line = words @900/904/908):

| RT | +0x904 (X, bit31 set) | +0x908 (Y) | ceil/32−1 |
|---|---|---|---|
| 1×1 | 0 | 0 | 0/0 ✓ |
| 31×31 | 0 | 0 | 0/0 ✓ |
| 32×32 | 0 | 0 | 0/0 ✓ |
| 33×33 | 1 | 1 | 1/1 ✓ |
| 63×63 | 1 | 1 | 1/1 ✓ |
| 65×65 | 2 | 2 | 2/2 ✓ |
| 512×512 | 15 (0x0f) | 15 | 15/15 ✓ |
| 1024×1024 | 31 (0x1f) | 31 | 31/31 ✓ |
| 2048×2048 | 63 (0x3f) | 63 | 63/63 ✓ |
| 1000×1000 | 31 | 31 | 31/31 ✓ |
| 777×777 | 24 (0x18) | 24 | 24/24 ✓ |
| **2048×32** | 63 | **0** | X,Y independent ✓ |
| **32×2048** | **0** | 63 | X,Y independent ✓ |
| **96×1000** | 2 | **31** | ✓ |
| **1000×96** | 31 | **2** | ✓ |

bit31 (`0x80000000`) is set on `+0x904` in **every** case (incl. count 63) and never on `+0x908`.

**bpp-independence (the load-bearing "do-not-port-shrink-tile" claim):**
- All formats at 64×64 (bgra8/rgba8/r8/r32f/rgb10a2/rgba16f/rgba32f, bpp 1→16) give `+0x904/+0x908 = 1/1`.
- **Full-BO** diff `base_68000` vs `fmt32f_68000` = **0 differing words** (`bodiff` direct file diff) — the
  entire tiling context is byte-identical bgra8 vs rgba32f, not just the two count fields.
- **rgba32f + 4× MSAA** (`m4_32f`, imageblock 16 B×4×1024 = **64 KiB** ≫ 32 KiB SRAM): grid stays 32×32
  (`1/1`) and renders **correctly** — `PIXEL b0..3=0000803e` = R 0.25, the drawn value (`raw/stdout/m4_32f.stdout`).
- Depth+color (`dc`, `dc_512`) leaves the grid identical to color-only.

⇒ tile is 32×32 fixed, bpp/sample/depth-independent. **The G13/G14 shrink-tile logic must not be ported.** No size/format ever produced a sub-32×32 tile (probed to 2048² and 64 KiB imageblocks).

---

## Claim 2 — Imageblock / tile-memory budget

### 2a. Per-attachment 0x20-byte record, bgra8 stride 0x1000 — **CONFIRMED (extended)**
Tiler geometry heap `0x10000018200`. EXP-0021 validated MRT 1→4; RT-4 extends to **8** and to
**mixed formats** (`raw/hex/mrt8_tilerheap.hex`). Per-attachment record `+0x08` (tile-mem offset), bgra8:

`0x8800 0x9800 0xa800 0xb800 0xc800 0xd800 0xe800` → **stride 0x1000** through all 8 attachments ✓.

Each added attachment is a 0x20-byte record: format word `0xf60a0a22` @+0x00, config `0x0800fc03`
@+0x04, tile-mem offset @+0x08, `0x80000010` @+0x0c, secondary offset (`+0x08`+bpp-scaled delta) @+0x10.

**Mixed formats (new):** `mrt4_mix = bgra8,rgba32f,r8,rgba16f` — each record carries **its own**
format word and format-dependent offsets (`raw/hex/mrt4_mix_tilerheap.hex`): att0 `0xf60a0a02` (BGRA8),
att1 `0xf6888e22` (RGBA32F), att2 `0xf9680022` (R8), att3 `0xf6888ca2` (RGBA16F). Confirms attachments
are described independently — a driver may mix formats.

### 2b. "Σ tile_area×bpp×samples vs 32 KiB = imageblock feasibility gate" — **DISCREPANCY**

The doc states the 32 KiB (`maxThreadgroupMemoryLength`) budget "is what a driver checks for imageblock /
programmable-blend feasibility," i.e. reject configs where `Σ tile_area×bpp×samples > 32 KiB`. Falsified:

- **`mrt8_32f`** = 8× RGBA32F, `Σ = 8×1024×16×1 = 128 KiB` (4× the budget): pipeline is **accepted**,
  draw **completes**, and the pixel is **correct** — `PIXEL b0..3=0000803d` = 0.0625 = the shader's
  `col.r*0.25` for attachment 0 (`raw/stdout/mrt8_32f.stdout`). A driver implementing the documented
  gate would wrongly reject this working config.
- **`m4_32f`** = RGBA32F + 4×MSAA, `Σ = 64 KiB` (2× budget): accepted, correct pixel (claim 1).
- Even **`mrt8` bgra8** (`Σ = exactly 32 KiB`) already writes per-attachment tile-mem offsets
  `0x8800..0xe800` (>32 KiB), so the offsets are not into a 32 KiB-capped SRAM window.
- The per-attachment offset **stride does not scale as `tile_area×bpp`**: bgra8 = **0x1000**, but
  rgba32f = **0x1800** (not `1024×16 = 0x4000`) — measured across 7 attachments (`mrt8_32f`). So the
  "Σ tile_area×bpp" arithmetic doesn't describe the actual on-chip layout either.

**Corrected fact:** the fixed-function MRT/MSAA color tile store is **not** capped at 32 KiB and the
driver does **not** reject configs exceeding it (validated to 128 KiB). The 32 KiB
`maxThreadgroupMemoryLength` limit governs **explicit** threadgroup / `[[imageblock]]` memory a
compute/tile shader may declare — a different resource from fixed-function color storage. The doc
conflates the two; a Mesa port must not gate plain MRT/MSAA feasibility on 32 KiB.
*(What the hardware does when a genuine tile/`[[imageblock]]` shader over-declares 32 KiB is out of
scope here — the pipeline-creation limit is the real gate there, not this MRT path.)*

---

## Claim 3 — MSAA sample count, 8× rejection, relocation — **CONFIRMED**

- **Sample count** in the relocated descriptor `0x10000018200 +0x24` (`msaa2_tilerheap` vs `msaa4_tilerheap`):
  `0x0800fc03 → 0x0900fc03`, i.e. bit24 = sample-count LSB (2×→0, 4×→1). ✓ Exactly as documented.
- **8× rejected** — two independent proofs: (a) capability probe `supportsTextureSampleCount:8 = 0`
  (and `16 = 0`); (b) `newRenderPipelineStateWithDescriptor` for `rasterSampleCount=8` fails with
  `PIPELINE_FAIL pso "rasterSampleCount (8) is not supported by device."` (same for 16). Max is 4×.
  (`raw/analysis/status_summary.txt`, `raw/stdout/probe.stdout`.)
- **Relocation:** `base` (1×) keeps the color descriptor at `0x10000110000`; under MSAA there is **no**
  `0x10000110000` BO and the descriptor lives in the tiler heap `0x10000018200`. ✓

---

## Claim 4 — Memoryless encoding — **CONFIRMED (color-1×, MSAA-color, depth)**

Universal signature: replace the surface address with poison **`0x0eeee000`**, zero the backing
size/stride/offset, and (where the record has one) clear the `+0x24` bit27 "has-backing" bit; the
tile-memory reservation shrinks.

- **MSAA color** (`msaa4_col` vs `msaa4_mlcol`, `0x10000018200`) — exact reproduction of the doc table:
  `+0x24 0x0900fc03→0x0100fc03` (bit27 clear), `+0x28 0x8000→0x0eeee000`, `+0x2c 0x80000010→0`,
  `+0x30 0x9000→0`, `+0x34 0x10→0`; tile-mem total `+0x48/+0x248 0x9800→0x8000` (**−0x1800**). ✓
- **Memoryless depth** (`depth_priv` vs `depth_ml`, `0x10000018000`): `+0x244 0x0800fc03→0x0000fc03`,
  `+0x248 0x8800→0x0eeee000`, `+0x24c/+0x250/+0x254 → 0`; VDM `0x18000+0x0c` and FF-state `0x58000+0x14`
  shrink by 0x400. ✓ Same drop-the-backing pattern.
- **Single-sample memoryless color (NEW):** `mlcol1x` has **no** `0x10000110000` BO — single-sample
  memoryless color **also relocates** its descriptor into the tiler heap. Its record
  (`raw/hex/mlcol1x_tilerheap.hex +0x20`) carries poison `+0x28 = 0x0eeee000` and zeroed `+0x2c`,
  vs the private base record `+0x28 = 0x00005800`, `+0x2c = 0x0003c010`. ✓ (Detail to add to the doc:
  relocation is triggered by MRT≥2 **or** MSAA **or** memoryless, not only "MRT≥2 or MSAA".)

---

## Claim 5 — Load/store actions, 0x300-seg chain, store-program 0x6f — **CONFIRMED**

3-segment chain in `0x10000110000` (seg0 `+0x000` load / seg1 `+0x300` render / seg2 `+0x600` store).

- **Store-program `0x6f`** present in the base (Store) attachment: `base_attach_full.hex +0x8c4 = 0x0000006f`,
  with store surface addr `+0x8c8/+0x8cc = 0x00058000` (= our RT). ✓
- **Load=DontCare** (`base` vs `ld_dc`): exactly 3 control words change — `+0x468 0x01000002→0x00000002`
  (clear-enable **bit24** at seg1+0x168 cleared), `+0x17c` & `+0x47c` clear-color `1.0→0.0`. ✓
- **Store=DontCare** (`base` vs `st_dc`): store segment poisoned — `+0x8c4 0x6f→0x100` (store program
  switched), `+0x8c8/+0x8cc/+0x8d0/+0x8d8 0x00058000→0xffffffff` (store addr poisoned). ✓
  (Aside: the RT surface `0x10000058000` also goes non-zero→0 because with DontCare the pixels aren't stored.)
- **Load=Load** (`ld_load`): injects a surface-read descriptor into `0x10000040000` (new `+0x240..+0x29c`
  fields incl. an incrementing offset table) — load reads existing contents. ✓
- **Adversarial combos** (`ld_dc_st_dc`, `ld_load_st_dc`, `ld_load_st_st`) behave as the exact union of the
  single-parameter changes — no interaction surprises.
- **Partial render / Z-prepass** (`nocolor` = `--depth --nocolor`): full 32×32 tiling context built
  (`0x68000 +0x900` = `1/1`) with **no** `0x10000110000` color descriptor. ✓

---

## Claim 6 — the NEGATIVES

### 6a. "Programmable sample positions are NOT in any userspace BO" — **DISCREPANCY (FALSIFIED)** ⚠️

The doc's strongest negative — "msaa4 vs custom-positions capture is byte-identical ... firmware/register-
managed ... a Mesa port must route custom sample positions through the kernel interface, not an attachment
field" — is **wrong**. Custom sample positions **are** written into a client BO.

Change-one-parameter (`msaa4` default vs `msaa4_sp` custom `{0.1,0.1},{0.9,0.3},{0.3,0.9},{0.7,0.7}`),
**direct same-VA file diff** of BO `gpu_va=0x100000e8000` (not the `gpu_va=0x0` dir-mode artifact that
misled EXP-0021) — only 6 words differ, all sample positions (`raw/hex/SAMPOS_EVIDENCE.txt`,
`raw/sampos/`):

```
+0x40..+0x5c, as (x,y) f32 pairs, sample n at +0x40+n*8, snapped to a 1/16 grid:
  default 4x: (0.375,0.125)(0.875,0.375)(0.125,0.625)(0.625,0.875)   = standard D3D/Metal 4x pattern
  custom  4x: (0.125,0.125)(0.875,0.3125)(0.3125,0.875)(0.6875,0.6875) = our input, snapped to 1/16
```

2× confirms it independently: BO `gpu_va=0x100000e0000 +0x40` default `(0.75,0.75)(0.25,0.25)` →
custom `(0.125,0.125)(0.875,0.875)`. Both BOs are `bo_*` (resource-map / sel-9 registered client memory),
present at the same VA in default and custom runs (clean same-VA pairing), and the values decode exactly
to the inputs.

**Corrected fact:** a Mesa driver programs sample positions by writing the per-sample `(x,y)` positions,
each coordinate quantized to a **1/16 grid**, as f32 pairs at **offset +0x40 of the sample-pattern BO**
(observed VA `0x100000e8000` for 4×, `0x100000e0000` for 2×; sample n at `+0x40 + n*8`). This is a
**userspace-emitted** field, **not** a kernel/firmware route. `programmableSamplePositionsSupported = YES`
and the table is fully userspace-visible. *(Why EXP-0021 missed it: it diffed only the `gpu_va=0x0`
pseudo-page and the primary control BOs; the `0x100000e8000` sample-pattern BO was never paired-and-diffed,
so its all-BO "byte-identical" claim was an under-capture, not a true negative.)*

### 6b. "Depth/ZLS store is NOT in any userspace BO" — **CONFIRMED**

`depth_priv` (depth storeAction DontCare) vs `depth_dstore` (Store): across all 38 paired BOs the only
differences are the known `gpu_va=0x0` pseudo-page size-mismatch artifact and the per-run timestamp
(`…0177`). A **direct same-VA diff** of the depth descriptor region `0x10000018000` shows **no** change.
Toggling the depth store action produces no userspace control-BO delta ⇒ depth store / ZLS is
firmware/ZLS-managed, route via kernel. ✓ (This negative is well-tested precisely because the same
capture method *did* catch the sample-position BO in 6a — the capture is comprehensive, so the absence
here is real, not an under-capture.)

---

## Net effect on `docs/pipeline/README.md`
- **Fix (must):** remove/replace the "programmable sample positions are firmware/register-managed, route
  through kernel" claim — document the userspace sample-pattern BO encoding (§6a corrected fact).
- **Fix (must):** stop presenting the 32 KiB `maxThreadgroupMemoryLength` as a fixed-function
  MRT/MSAA imageblock feasibility cap — it is the explicit-`[[imageblock]]`/threadgroup limit; plain MRT
  renders correctly to ≥128 KiB (§2b).
- **Confirmed & safe to keep:** 32×32 fixed tile + bpp-independence + `+0x904/+0x908` formula (now
  validated 1×1→2048² incl. extreme asymmetric and rgba32f+4×MSAA-correct-render); per-attachment
  0x20-byte record & bgra8 stride 0x1000 (now to 8 attach + mixed fmt); MSAA sample count + 8×-rejection +
  relocation; memoryless poison encoding (now color-1×/MSAA/depth); load/store seg chain + store-program
  `0x6f` + DontCare poison; depth-store negative.
- **Add (detail):** descriptor relocation into the tiler heap is triggered by MRT≥2 **or** MSAA **or**
  memoryless (single-sample memoryless color relocates too).

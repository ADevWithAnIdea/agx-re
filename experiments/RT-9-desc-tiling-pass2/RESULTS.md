# RT-9 RESULTS — independent 2nd red-team pass on `docs/descriptors` + `docs/tiling`

Device: Apple A18 Pro / G17P, macOS 26.6. Method: HW-PROBE + OWN-SHADER + DATA-TRACE via the
read-only `tools/iotrace` (arm64e). Every field/formula re-derived from RAW backing bytes with our
own analyzers (`t9tiling.py`/`verify_cols.py`/`t9desc.py`/`t9sampcheck.py`), **different harness and
different sizes than RT-3**. No Apple binary disassembled. Raw: `raw/`, `analysis/RT9_evidence.txt`.

## Verdict summary

| # | Claim under test (as corrected by RT-3, unless noted) | Verdict |
|---|---|---|
| 1 | Tiled-Morton: **row-major grid of Morton tiles**, morton-within-tile | **CONFIRMED** |
| 2 | Tile edge **T=64 (bpp≤4) / T=32 (bpp≥8)** | **CONFIRMED** (bpp 2,4,8,16 all measured) |
| 3 | Tile **column count / allocation padding** (`cols=⌈Wp/T⌉`, "pad to next power of two") | **DISCREPANCY** — it is `cols=⌈W/T⌉` and **tile-multiple** padding, NOT pow2 |
| 4 | Mipmaps §3: per-level `nextpow2(W≫L)·nextpow2(H≫L)·bpp` (pow2 padding) | **DISCREPANCY** — per-level padding is **tile-multiple**, same bug as #3 |
| 5 | Texture width/height **14-bit** packing | **CONFIRMED** (5000/9000/16384; ≤4096 no regression) |
| 6 | Base VA `= word2‖word3[0:11] << 4` (VA≫4) | **CONFIRMED** |
| 7 | Format→code `byte1 = numtype<<5 \| sizeclass` | **CONFIRMED** (8 formats) |
| 8 | PBE two-descriptor + PBE width/height split | **CONFIRMED** |
| 9 | Compression ≥16×16 threshold + aux placement `base+paddedImageBytes` | **CONFIRMED** |
| 10 | Type codes 2D/3D/2DArray/Cube/2DMS + array/cube stacking | **CONFIRMED** |
| 11 | Sampler descriptor (base "never" 8-byte encoding) | **CONFIRMED (partial)** — see note |
| 12 | Block-compressed formats also **tile** (block-grid tile-padded) | **NEW finding** (alloc-size evidence) |

**Two NEW discrepancies found (#3, #4)** — both missed by RT-3 because every width it tested was a
power-of-two multiple of T, where the wrong and right formulas coincide. Everything else RT-3
corrected or confirmed is independently upheld.

---

## HEADLINE DISCREPANCY (#3) — tile column count and allocation padding

`docs/tiling/README.md §1.1` (RT-3-corrected) says:
> `cols = ceil(Wp / T)` (Wp = nextpow2(W)) … storage is **padded to the next power of two in each axis**
and `§1.4`: `paddedImageBytes = Wp · Hp · bytesPerPixel`.

**Both are wrong whenever `⌈W/T⌉` is not a power of two.** The GF(2) solve on textures whose width
is a non-power-of-two number of tiles shows the tile index is `ty·cols+tx` with **`cols = ⌈W/T⌉`**
(actual width in whole tiles), and the backing BO is sized to the **tile-multiple**, not the next
power of two. `verify_cols.py` — CORRECTED model `element=(ty·⌈W/T⌉+tx)·T² + morton_D(xl,yl)`,
allocation `⌈W/T⌉·T · ⌈H/T⌉·T · bpp` — reproduces every case with **0 mismatch**; the doc's
`cols=Wp/T` gives tens of thousands of wrong offsets:

| case | bpp | T | BO size | tile-mult pad | pow2 pad | `cols=⌈W/T⌉` | `cols=Wp/T` (doc) |
|---|---|---|---|---|---|---|---|
| 192×192 r32 | 4 | 64 | `0x24000` | 192×192 (`0x24000`) | 256×256 (`0x40000`) | **3 → 0 mismatch** | 4 → 24576 wrong |
| 300×500 r32 | 4 | 64 | `0xa0000` | 320×512 (`0xa0000`) | 512×512 (`0x100000`) | **5 → 0 mismatch** | 8 → 130800 wrong |
| 384×384 rgba8 | 4 | 64 | `0x90000` | 384×384 (`0x90000`) | 512×512 (`0x100000`) | **6 → 0 mismatch** | 8 → 122880 wrong |
| 448×192 rgba8 | 4 | 64 | `0x54000` | 448×192 (`0x54000`) | 512×256 (`0x80000`) | **7 → 0 mismatch** | 8 → 57344 wrong |
| 576×320 r32 | 4 | 64 | `0xb4000` | 576×320 (`0xb4000`) | 1024×512 (`0x200000`) | **9 → 0 mismatch** | 16 → 147456 wrong |

**Corrected rule (HW-validated):**
```
T          = 64 if bpp<=4 else 32
padDim(d)  = ceil(d/T)*T          if d >= T          # tile-multiple, NOT next power of two
           = nextpow2(d)          if d <  T          # a single clipped tile of pow2 width
cols       = padW / min(T, padW)  = ceil(W/T) when W>=T ; 1 when W<T
element_index(x,y) = (ty*cols + tx) * (T*T) + morton_D(x&(T-1), y&(T-1))   # tx=x>>logT, ty=y>>logT
allocationBytes    = padW * padH * bpp
```
Impact: **driver-breaking**. Any texture whose width is not a power-of-two multiple of T (e.g. a
1920-wide render target: correct `cols=30`, doc says `32`) has every texel past the first tile row
placed at the wrong byte, plus a 30–100 % over-allocation. Invisible below 256 and for pow2 dims,
which is exactly the region RT-3 sampled.

### Sub-tile (W<T) regime — reverts to the *old* interleave-append model (CONFIRMED consistent)
`17×4095` r32 (W=17<64): BO=`0x80000`=32×4096×4 → width padded to `nextpow2(17)=32` (not tile-64).
The GF(2) solve is a **pure bit-permutation**: `x0 y0 x1 y1 x2 y2 x3 y3 x4 y4 | y5 y6 … y11` — i.e.
interleave to the smaller padded dim (5 bits) then append the taller dim linearly = the ORIGINAL
`docs/tiling` interleave-append model, applying inside the clipped tile. Seam check `(0,64)→e=2048`
matches a 32×64 clipped tile. (0 mismatch.)

## DISCREPANCY (#4) — mipmaps inherit the same padding bug

`docs/tiling §3` sizes each level `nextpow2(W≫L)·nextpow2(H≫L)·bpp`. For an NPOT base this is the
same pow2 over-pad. **384×384 mips=4, compression disabled**: BO=`0xcd600`. This is *smaller than*
`0x100000`, so level-0 alone **cannot** be pow2-padded (512²·4=`0x100000`); it is tile-padded
(`0x90000`). Total = tile-multiple mip-chain (`0xc9600`) + one 16 KB page. Control **256×256 all
mips** = `0x55680` = tile-chain = pow2-chain exactly (Δ=0) — the discrepancy is NPOT-specific.
Corrected §3: replace `nextpow2()` per level with `padDim()` (tile-multiple ≥T / nextpow2 <T).

---

## CONFIRMED (independent re-derivation upheld the corrected doc)

**Tiled-Morton + T boundary (the big RT-3 correction) — CONFIRMED.** Independent GF(2) solves,
0-mismatch reconstruction, with T *derived from the data* (interleave-break), not assumed:

| case | bpp | derived T | doc T | notes |
|---|---|---|---|---|
| 256×256 r16 | 2 | **64** | 64 | high bits `xxyy` (row-major tiles) |
| 256×256 r32 | 4 | **64** | 64 | `xxyy` |
| 384×384 rgba8 | 4 | **64** | 64 | cols=6 (disc #3) |
| 300×500 r32 | 4 | **64** | 64 | cols=5 (disc #3) |
| 256×256 rgba16f | 8 | **32** | 32 | `xxxyyy` |
| 256×256 rgba16uint | 8 | **32** | 32 | `xxxyyy` |
| 1024×64 rg32 | 8 | **32** | 32 | `xxxxxy`, 0 mismatch |
| 256×256 rgba32 | 16 | **32** | 32 | `xxxyyy` |

The T=64/32 break sits exactly between **4-byte and 8-byte** elements. Within a tile the order is
plain Morton; tiles are row-major. **Note on discriminating sizes:** 128×128 (only 2×2 tiles) is
degenerate — row-major tile order `(tx,ty)=(x6,y6)` is bit-identical to full Morton there, so ≥256
(≥4 tiles/dim) is required to distinguish T=64. This is *why* EXP-0017's ≤128 validations passed
the (wrong) pure-Morton model.

**14-bit dims — CONFIRMED, no bit off.** width−1 = `word0[28:31]‖word1[0:9]`, height−1 =
`word1[10:23]`, exact at W/H = 5000, 9000, 16384. The 12-bit reading gives 904/808/4096 (wrong).
≤4096 (4096, 2048) packs identically — no regression.

**Base VA — CONFIRMED.** `word2‖word3[0:11] << 4` landed inside the captured backing BO for every
one of the ~30 textures probed.

**Format→code — CONFIRMED (8 formats)** harvested from captured descriptors: r16uint `0x62/0x42`,
r32uint `0x62/0x48`, rg32uint `0x62/0x4c`, rgba16uint `0xa2/0x4c`, rgba16float `0xa2/0x8c`,
rgba32uint `0x22/0x4e`, rgba8uint `0x22/0x4a`, rgba8unorm `0x22/0x0a` — all match
`byte1 = numtype<<5 | sizeclass`, `byte0 = type | chanArr<<4`.

**PBE two-descriptor — CONFIRMED.** A ShaderRead|ShaderWrite 96×48 texture materializes BOTH a
sampled descriptor (split `word0[28:31]‖word1[0:9]` / `word1[10:23]` = 96×48) and a PBE descriptor
(split `word0[24:31]‖word1[0:5]` / `word1[6:19]` = 96×48). Each split decodes correctly only for its
own descriptor. Both have compression disabled (`word1.b27=0`, `word3.b31=0`, `word4=0`) — ShaderWrite
kills compression. `read_write` case shows the two coexisting.

**Compression ≥16×16 threshold + placement — CONFIRMED.** 15×15 / 16×15 / 32×8 → no aux
(`word1.b27=0`, no secondary VA); 16×16 / 17×17 / 64×64 → aux present, `secondaryVA = base +
paddedImageBytes` (16×16→+`0x400`, 17×17→+`0x1000` = 32²·4 nextpow2, 64×64→+`0x4000`). Per-dimension
≥16 texels.

**Type codes + stacking — CONFIRMED.** byte0 low nibble: 2D=2, 3D=5, 2DArray=3, Cube=6, 2DMS=4.
2DArray: `arrayLen−1 = word3[14:] = 5` for 6 layers; planes linear-stacked at a 256-element (16²)
stride. Cube = nibble 6.

**Sampler (partial) — CONFIRMED, no regression seen.** The base "never" sampler independently
decodes to the exact documented bytes `00 00 0e 00 80 07 00 00` = compare(sense=1,test=7)=never,
S/T/R=edge, border=0, lodMax field `0x70` (=14.0×8). *Note:* the modified test samplers
(compare/address/border variants) were **not materialized in the captured BOs** by this binding path
(a harness/capture limitation, not a doc discrepancy); RT-3 already validated all sampler fields with
a working harness, and nothing here contradicts them.

## NEW HOLES probed

- **Block-compressed formats DO tile** (answers item-4). BC/ASTC block grids are **tile-multiple
  padded**, not un-tiled block-Morton. `heapTextureSizeAndAlign`: **BC7** (16 B blocks) 384×384 →
  96×96 blocks (`0x24000`, exact), 320×320 → **96×96** (80 blocks rounded up to mult-32, `0x24000`),
  1024×768 → 256×192 (`0xc0000`, exact) — never pow2 (would be `0x40000`). Tile edge ≈ **32 blocks**
  (matches the ≥8-byte→T=32 rule; a block is ≥8 B). This is allocation-size evidence extending
  EXP-0028's small-size block-Morton into the tiled regime; a raw-layout GF(2) solve at large BC
  sizes remains a residual (BC can't be compute-written).
- **Very-NPOT / narrow (17×4095)** — resolved above (sub-tile regime; old interleave-append model).
- **Mip level>0 with the tiled model** — the allocation proof (#4) shows levels are tile-multiple
  padded; exact per-level offset re-derivation via per-level content is a residual.
- **Sparse / heap** — not re-litigated in RT-9; RT-3/EXP-O2B established sparse-tier flag + 16 KiB
  tiles + residency in the page table (descriptor-transparent). No new evidence here.

## Recommended doc fixes (for the orchestrator)
1. `docs/tiling §1.1`: `cols = ⌈W/T⌉` (not `⌈Wp/T⌉`); tile index `ty·cols+tx`.
2. `docs/tiling §1.1 prose + §1.4`: padding is to a **multiple of T** for dims ≥T (nextpow2 for
   dims <T), NOT "next power of two". `allocationBytes = padW·padH·bpp` with the corrected `padDim`.
3. `docs/tiling §3`: per-level size uses `padDim(W≫L)·padDim(H≫L)·bpp`, not `nextpow2(...)`.
4. `docs/descriptors/format-table.md §5`: same `Wp` → tile-multiple correction if it restates §1.4.

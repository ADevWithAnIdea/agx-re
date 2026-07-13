# M5 (Apple10 / G17g) TBDR pipeline deltas vs A18 (G17P)

Delta-form: "same as `pipeline/README.md` (A18/G17P) except as noted." Source: EXP-M5-10 (own-MSL DATA-TRACE +
HW-PROBE: change-one-Metal-parameter on render-pass state). Clean-room: own MSL/API; no Apple binary
introspected. All HW-validated unless marked *inherited*/⏳.

## Tile size — **32×32, CONFIRMED on the 8-core M5** (headline)
Despite the M5 having **8 GPU cores** (A18 = 5), the fragment tile stays **fixed 32×32** — the A18 "do NOT
port the G13/G14 shrink-tile logic" guidance holds on M5. The tile-grid word **moved +0xC0** vs A18 (same
+0xC0 as the viewport transform's `+0x910→+0x9d0` move, EXP-M5-06):

    0x68000 + 0x9c4 = 0x80000000 | (ceil(W/32) − 1)      # A18: +0x904
    0x68000 + 0x9c8 =              (ceil(H/32) − 1)       # A18: +0x908

HW-validated: 64×64 → `0x80000001`/`0x1`; 128×64 → `0x80000003`/`0x1`; **1920×1080 → `0x8000003b`/`0x21`**
(59 = 1920/32−1, 33 = 1080/32−1 — the ÷32 is decisive). Viewport transform + depth range at `+0x9d0…` (EXP-M5-06).

## MSAA — sample count SAME semantics, encoding relocated
- **Sample count** in the color attachment record at **record+0x30**: 1× = `0x00840000`, 2× = `0x00880000`,
  4× = `0x00900000` (field = `0x80 | (n<<2)`); the texture-type nibble flips to **4** (2DMultisample) and a
  covariant config bit sets at record+0x24. **Only 1×/2×/4×** — 8× is Metal-rejected (`supportsTextureSampleCount`,
  inherited + re-confirmed absent in `capability-completeness-m5.md`). Resolve adds a resolve-target descriptor.
- **Programmable sample positions ARE userspace-emittable on M5** (as A18). Written to client BO
  **`0x100000d8000`** (A18: `0x100000e8000`) at **+0x40**: an array of N `(x,y)` **f32** pairs, sample n @
  `+0x40 + n·8`, each coord snapped to a **1/16 grid**. HW-validated: 4× default = the **D3D pattern**
  `{(.375,.125),(.875,.375),(.125,.625),(.625,.875)}`; custom `{0.1,0.2}…` decoded exactly to the 1/16 snaps
  (0.1→0.125, 0.2→0.1875, 0.9→0.875). NOT kernel-managed.

## Memoryless render targets — SAME
`MTLStorageModeMemoryless` replaces the surface VA with **poison `0x0eeee000`** and **zeroes the backing
size/stride/offset** in the attachment record (`0x10000018000` record +0x28/+0x2c/+0x30/+0x34), and clears the
backing-present bit at record+0x24. Byte-for-byte the A18 memoryless behavior.

## Load / store actions — SAME
Attachment chain = 0x300-byte LOAD/RENDER/STORE segments. **Clear color** = float4 RGBA at
`0x10000118000+0x170` (single RT). `loadAction=Clear` sets the clear-enable byte (record +0x14) + writes the
clear color; `loadAction=DontCare` clears both; `loadAction=Load` injects a surface-read; `storeAction=DontCare`
poisons the store address. Depth store-action / ZLS remains **firmware-managed** (kernel item, as A18).

## Occlusion / visibility query — SAME semantics, relocated
Per-draw **mode** = **`0x58000 + 0x1c4` bit14** (Boolean=1 / Counting=0); per-draw result **offset** =
**`0x58000 + 0x1d8`** = `byteOffset<<6`. HW-validated readback: **Boolean wrote 1**, **Counting wrote 4096**
(64×64 passed samples), offsets 64/256 honored. Per-tile→total summation is firmware-managed (as A18). (A18
had these at `+0x8c`/`+0xa0`; see `../cmdstream/README-M5-deltas.md`.)

## Imageblock / tile memory, tiler-param buffer — inherited
Per-attachment tile-memory records in the tiler geometry heap `0x10000018xxx`; 32 KiB explicit
imageblock/threadgroup-memory budget (device limit re-measured, EXP-M5-04); MRT/MSAA feasibility **not** gated
on 32 KiB. Tiler parameter buffer + partial-render overflow trigger remain **firmware-managed** (kernel items,
as A18). No userspace core-count/core-mask field appears in any client BO on the 8-core part (EXP-M5-06).

## Open ⏳
Depth/ZLS store control (kernel-side, as A18); per-sample MSAA compression-aux ratio; explicit
`[[imageblock]]`/tile-shader dispatch record on M5.

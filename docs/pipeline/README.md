# A18 Pro (G17P) TBDR Pipeline

Clean-room documentation of the Tile-Based Deferred Renderer configuration a userspace driver must
emit/know. Learned by **change-one-Metal-parameter data tracing + hardware probing** (DATA-TRACE +
HW-PROBE) of our own draws; no Apple binary disassembled. See `../../CLAUDE.md`. HW-validated unless
marked ⏳. Source: `experiments/EXP-0021-tbdr-pipeline/`.

## Tile size — fixed 32×32
- The fragment tile is **32×32, fixed** — and **does NOT scale with pixel format / bpp** (rgba32f, and
  even rgba32f+4×MSAA where the imageblock exceeds the 32 KiB tile SRAM, keep 32×32 and still render).
  This is a **driver-relevant delta from the G13/G14 "shrink-tile" model** — do not port that logic.
- Encoded in the tiling context (`0x68000`): `+0x904 = 0x80000000 | (ceil(W/32)−1)`, `+0x908 =
  ceil(H/32)−1` (HW-validated across 11 RT sizes incl. asymmetric and non-multiples). Viewport transform
  + depth range live at `+0x910..+0x924` (see `../cmdstream/`).

## Imageblock / tile memory
- Each color attachment declares a **0x20-byte record in the tiler geometry heap** (`0x10000018xxx`);
  per-attachment tile-memory **stride = 0x1000 = 4096 B = 1024 px × 4 B/px** for bgra8 (records stack;
  HW-validated MRT 1→4). The tile-byte-size field scales ~4× for rgba32f.
- **⚠ Budget — CORRECTED (RT-4):** the **32 KiB `maxThreadgroupMemoryLength`** is for **explicit `[[imageblock]]` /
  threadgroup memory**, and is **NOT a fixed-function MRT/MSAA color-storage feasibility cap** — an 8× rgba32f MRT
  (128 KiB nominal) renders correctly, as does 4× rgba32f. Per-attachment stride is **0x1800 for rgba32f** (not
  `tile_area×bpp`). **Do not gate MRT/MSAA feasibility on 32 KiB.** Use 32 KiB only for explicit imageblock/tile-memory
  declarations.

## MSAA — sample count & positions
- **Sample count** in the attachment descriptor word `+0x24` (msaa2 `0x08…`, msaa4 `0x09…`; bit24 = count
  LSB, bit27 = MSAA-store). The color descriptor relocates from `0x10000110000` into the tiler heap on **MRT≥2 OR MSAA OR memoryless** (RT-4).
- **✅ Programmable sample positions ARE userspace-emittable — CORRECTED by RT-4** (EXP-0021 wrongly said
  "byte-identical" because it diffed the wrong BOs). They are written to a **client BO** (`0x100000e8000` for 4× /
  `0x100000e0000` for 2×) at **+0x40**: an array of N `(x,y)` f32 pairs (sample n @ `+0x40 + n·8`), each coord snapped
  to a **1/16 grid** (default 4× = the D3D pattern; custom positions decode exactly to the inputs). **NOT kernel-managed.**

## Memoryless render targets
`MTLStorageModeMemoryless` (TBDR tile-only, no main-memory backing): clears `+0x24` bit27 (backing bit),
replaces the surface address with poison `0x0eeee000`, zeroes backing size/stride/offset, and shrinks the
tile-memory reservation by 0x1800 (no store/resolve scratch). Memoryless depth omits the depth surface VA
that private depth embeds.

## Load/store actions & partial render
- The attachment descriptor is a chain of **0x300-byte segments = load / render / store**. Seg1 holds
  clear-enable (bit24 at seg+0x168) + clear color; seg2 holds a **store-program id `0x6f`** + store surface
  address. `loadAction=DontCare` flips 3 words / omits the load segment; `storeAction=DontCare` poisons the
  store address. **Depth store-action / ZLS is firmware-managed** (not captured) — route via kernel.
- **Tiler parameter buffer** (`0x10000018xxx` + sparse `0x10000140000`): buffers vertex/primitive data
  between the tiler (TA) and fragment (3D) stages. A depth-only pass still builds the full 32×32 tiling
  context + param heap with no color descriptor (Z-prepass / partial-render path). The **overflow →
  partial-render trigger is firmware-managed** — no userspace knob (kernel/firmware concern).

## Open items
- Depth/ZLS store control (kernel-side). (Sample positions are now known userspace-emittable — RT-4.)
- Full packed pixel-format word decode (→ `../descriptors/`); `+0x24` bits beyond 2×/4×/memoryless.

## Render-target attachment descriptor — full field map (EXP-G1b)
The attachment descriptor (`0x10000110000`) is a chain of three **0x300-byte segments: LOAD (+0x000) / RENDER (+0x300)
/ STORE (+0x600)**.
- **Surface VA** = `((word3 & 0xfff)<<32 | word2) << 4` (same `VA>>4` as textures; HW-correlated to the RT buffer).
- **STORE segment is itself a PBE descriptor:** word0 byte3 = **width−1**, word1>>6 = **height−1**, word2 = surface
  `VA>>4`, word3[12:] = **stride/rowBytes**. HW-validated over 6 sizes (asymmetric 128×64 separates W/H) and 6 formats.
- **LOAD/RENDER:** format word @seg+0x20 (byte+0x22 = format), config/sample @+0x24; **clear-enable = bit24 @
  seg1+0x168**, clear-color floats @+0x17c. `loadAction=Load` injects a surface-read descriptor.
- **Store action:** store-program id `0x6f` + store surface addr (`storeAction=DontCare` poisons the addr). Store-program
  `0x6f` semantics are firmware-managed (kernel item).
- **MSAA:** byte0 low-nibble→4 (2DMultisample), +0x24 sample count (`0x08`=2× / `0x09`=4×); **sample positions are userspace-emittable @+0x40** (1/16-grid f32 pairs; RT-4, corrects EXP-0021).
- **MRT:** N≥2 attachments (or any MSAA) relocate the color descriptor into the tiler geometry heap `0x10000018200`,
  arrayed as **fixed 0x20-byte per-attachment records** (LOAD @`+0x20+k·0x20`, STORE/PBE @`+0x220+k·0x20`, clear-color
  @`+0x500+k·0x18`); per-attachment surfaces at 0x58000/0x60000/… (distinct from the 0x1000 imageblock tile-memory record).


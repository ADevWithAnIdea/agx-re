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
- **Budget:** `Σ_attachments (tile_area × bpp × samples)` against the **32 KiB** tile SRAM ⇒ ~32 B/sample
  on-chip. This is what a driver checks for imageblock / programmable-blend feasibility.

## MSAA — sample count & positions
- **Sample count** in the attachment descriptor word `+0x24` (msaa2 `0x08…`, msaa4 `0x09…`; bit24 = count
  LSB, bit27 = MSAA-store). Under MSAA the color descriptor relocates from `0x10000110000` into the tiler
  heap.
- **⚠ Programmable sample positions are NOT in any userspace BO** (msaa4 vs custom-positions capture is
  byte-identical) — they are **firmware/register-managed**. A Mesa port must route custom sample positions
  through the **kernel interface**, not an attachment field.

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
- Programmable sample-position firmware path (kernel-side); depth/ZLS store control.
- Full packed pixel-format word decode (→ `../descriptors/`); `+0x24` bits beyond 2×/4×/memoryless.

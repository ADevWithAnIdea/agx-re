# EXP-0021 Results — TBDR pipeline specifics (A18 Pro / G17P)

**TL;DR.** The G17P fragment/framebuffer **tile is a fixed 32×32 pixels** — it does *not*
shrink for high-bpp or MSAA formats. The tiling context (`0x68000`) stores the tile grid as
`ceil(dim/32)−1` per axis; the **imageblock** (on-chip tile store) is declared per color
attachment in the **tiler geometry heap** (`0x10000018xxx`) at **tile_area × bpp** bytes each
(bgra8 = 0x1000 B), and scales with attachment count, format and sample count. **Sample count**
is a field in the attachment descriptor (`+0x24`, bits ~[27:24]); **programmable sample
positions are NOT written to any captured userspace BO** (firmware/register-managed).
**Memoryless** clears a "has main-memory backing" bit (`+0x24` bit 27), replaces the surface
address with a poison value (`0x0eeee000`) and zeroes the backing size/stride. The attachment
descriptor is a chain of **0x300-byte segments = load / render / store phases**; load/store
actions flip a clear-enable bit and the store surface address. Everything below marked
**[HW]** is a single-parameter byte-diff on real hardware; **[inf]** is inferred from structure.

Method & determinism: `tvar.m` (own MSL), captured under `tools/iotrace`; `base` vs `base2`
differ in **0 real words** (the only "diff" is the known dual `gpu_va=0x0` pseudo-BO pairing
artifact — see `raw/analysis/diff_base2.txt`). All BO roles inherited from EXP-0014.

---

## 1. Tile size and how it scales — tiling context `0x68000` [HW]

The fragment/framebuffer **binning tile is 32×32 pixels, fixed.** The tiling context BO
`gpu_va 0x68000` holds the tile grid + viewport at `+0x900`:

| offset | field | meaning |
|---|---|---|
| `+0x904` | `0x80000000 \| (ceil(W_px/32) − 1)` | **X tile count − 1** (bit31 flag always set) |
| `+0x908` | `ceil(H_px/32) − 1` | **Y tile count − 1** |
| `+0x910/+0x914` | `f32 W/2`, `f32 H/2` | viewport scale (x,y) |
| `+0x918/+0x91c` | `f32 W/2`, `f32 −H/2` | viewport translate (x, **−y = Y-flip**) |
| `+0x920/+0x924` | `f32 0.0`, `f32 1.0` | depth range near / far |

**RT-size sweep (`+0x904`/`+0x908`), all HW-validated** (`raw/hex/KEY_DIFFS.txt`):

| RT (W×H) | +0x904 (X) | +0x908 (Y) | check |
|---|---|---|---|
| 32×32 | `0x80000000` (0) | 0 | ceil(32/32)−1 = 0 |
| 33×33 | `0x80000001` (1) | 1 | ceil(33/32)−1 = 1 |
| 48×48 | `0x80000001` (1) | 1 | ceil(48/32)−1 = 1 |
| 64×64 (base) | `0x80000001` (1) | 1 | 2−1 = 1 |
| 96×96 | `0x80000002` (2) | 2 | 3−1 = 2 |
| 100×100 | `0x80000003` (3) | 3 | ceil(100/32)−1 = 3 |
| 128×128 | `0x80000003` (3) | 3 | 4−1 = 3 |
| 160×160 | `0x80000004` (4) | 4 | 5−1 = 4 |
| 256×256 | `0x80000007` (7) | 7 | 8−1 = 7 |
| **64×128** | `0x80000001` (1) | **3** | X,Y independent ✓ |
| **128×64** | `0x80000003` (3) | **1** | X,Y independent ✓ |

⇒ **field = number of 32×32 tiles spanning the axis, minus 1** (ceil rounding). Asymmetric RTs
(64×128 / 128×64) prove `+0x904` tracks **width** and `+0x908` tracks **height**.

**Format/bpp does NOT change the tile grid** [HW]: `base` (bgra8, 4 B) vs `fmt_rgba32f`
(16 B) leaves `0x68000` **byte-identical** through `+0x930`. Even **rgba32f + 4× MSAA**
(16 B × 4 samp × 1024 px = 64 KiB imageblock, > the 32 KiB tile SRAM) keeps the grid at 32×32
and **renders successfully** (`m4_32f` status = completed). So the render tile is a fixed
32×32; the byte budget is handled by allocation (§2), not by shrinking tiles. *(This differs
from the G13/G14 model where tile geometry shrinks for wide formats — a driver-relevant delta.)*

Side effects of RT-*size* change (not tile-size but correlated): VDM state-size `0x18000+0x0c`
and FF-state size `0x58000+0x14` grow with RT area.

---

## 2. Imageblock / on-chip tile memory [HW for MRT stride; inf for total budget]

Tile = 32×32 = **1024 pixels/samples**. On-chip budget = **32 KiB** threadgroup/tile SRAM
(`maxThreadgroupMemoryLength`, from hardware-overview) ⇒ **32 bytes per sample** of imageblock.

The imageblock is declared **per color attachment** as a **0x20-byte record** in the tiler
geometry heap (`gpu_va 0x10000018xxx`, the descriptor region the tiler reads). Per record:

| record offset | field | evidence |
|---|---|---|
| `+0x00` | packed pixel-format word (`0xf60a0a22`…; low byte carries attachment index) | MRT [HW] |
| `+0x04` | config/sample word (`0x0800fc03`; `+0x24` analogue) | [HW] |
| `+0x08` | **tile-memory offset for this attachment** | MRT [HW] |
| `+0x0c` | `0x80000010` (flag \| align) | [HW] |
| `+0x10` | secondary offset (`+0x08` value + 0x400) | [HW] |
| `+0x14` | `0x10` | [HW] |

**MRT stride (bgra8), HW-validated** (`base` 1 RT vs `mrt4`; each attachment adds a 0x20-byte
record at `0x10000018200 +0x20/+0x40/+0x60/+0x80`; the tile-memory offset field `+0x08` of the
added records reads **0x8800, 0x9800, 0xa800** for attachments 1/2/3) ⇒ **per-attachment
stride = 0x1000 = 4096 B = 1024 px × 4 B/px** (tile_area × bytes-per-pixel).

**Format scaling** [HW]: `msaa4` bgra8 vs `m4_32f` rgba32f, tiler heap `+0x2c/+0x4c`
tile-byte-size grows `0x3c010 → 0xfc010` (~4×, matching 4 B → 16 B), and the tile-memory
offset `+0x30` grows `0x9000 → 0xc000`. So **imageblock size = Σ over attachments of
(tile_area × bytes_per_pixel × samples)**; the driver must emit these per-attachment offsets.

VDM/FF-state size fields also grow with MRT count (`0x18000+0x0c`: `0x4800→0x5400` for 4 RTs;
`0x58000+0x14`: `0x4c19→0x5819`) [HW].

Relevant to programmable blending (EXP-0019) and `[[imageblock]]`: because the per-attachment
tile store is `tile_area × bpp`, a tile shader's imageblock struct maps onto these same
32×32-px × bpp regions.

---

## 3. Sample count and programmable sample positions [HW count; HW-negative positions]

**Sample count** is encoded in the **attachment descriptor word `+0x24`** (bits ~[27:24]).
Under MSAA the whole color attachment descriptor **relocates** out of `0x10000110000` into the
tiler geometry heap (`0x10000018200`), where `+0x24` reads:

| samples | `+0x24` word | byte[27:24] | notes |
|---|---|---|---|
| 1 (base) | `0x0000fc03` | `0x0` | non-MSAA |
| 2 | `0x0800fc03` | `0x8` | [HW] `msaa2` |
| 4 | `0x0900fc03` | `0x9` | [HW] `msaa4` |

Interpretation [inf]: **bit24 = sample-count LSB** (log2(samples)−1: 2×→0, 4×→1) and
**bit27 = MSAA color stored/resolved to memory** (see §4 — memoryless clears it). Sample-count
also grows the state-size fields (`0x18000+0x0c` `+0x200` for 2→4; `0x58000+0x14` `+0x200`) and
the imageblock/tile-memory offsets (`0x10000018200+0x30`: `0x8800→0x9000`) [HW].

**Programmable sample positions: NO userspace-visible encoding.** `msaa4` (default positions)
vs `msaa4_sp` (custom `{0.1,0.1},{0.9,0.3},{0.3,0.9},{0.7,0.7}`) are **byte-identical across
every captured BO**, including the `gpu_va=0x0` shared pages (direct file diff = 0 words; the
only residual word is a per-run timestamp with the `…aa0177` signature also seen in the format
sweeps). The custom position floats do not appear in any capture. ⇒ **programmable sample
positions are programmed via a firmware/register path the userspace command-stream BOs do not
carry** — a driver must route them through the kernel/firmware, not an attachment field.
`programmableSamplePositionsSupported = YES` (capability), but the *table* is not in userspace
memory we can trace. **[HW-negative]** — flag for kernel-team coordination.

---

## 4. Memoryless attachment encoding [HW]

`MTLStorageModeMemoryless` (tile-only, no main-memory backing). Cleanest isolation is the MSAA
**color** attachment (`msaa4_col` Private vs `msaa4_mlcol` Memoryless — one variable), tiler
heap `0x10000018200`:

| field | Private (`0x09`) | Memoryless (`0x01`) | meaning |
|---|---|---|---|
| `+0x24` word | `0x0900fc03` | `0x0100fc03` | **bit27 (`0x08000000`) = has main-memory backing → CLEARED** |
| `+0x28` surface addr | `0x00008000` | `0x0eeee000` | **poison / "no backing" sentinel** |
| `+0x2c` | `0x80000010` | `0x00000000` | backing stride/size zeroed |
| `+0x30` | `0x00009000` | `0x00000000` | backing tile-mem offset zeroed |
| `+0x34` | `0x00000010` | `0x00000000` | zeroed |
| `+0x48/+0x248` | `0x9800` | `0x8000` | tile-memory total **reduced by 0x1800** (no store/resolve scratch) |

**Memoryless depth** [HW, corroborating]: a Private depth attachment embeds the depth surface
main-memory VAs in its descriptor (e.g. `0x00019a00 / 0x00019900`, seen in
`raw/hex/depth_attach.hex`); a Memoryless depth descriptor has **no depth surface address**
(`raw/hex/depthml_attach.hex`) — same "drop the backing" pattern. (The depth case also
reorders the attachment-descriptor segment chain, so the color diff is allocation-shift noise;
the color-memoryless table above is the clean single-variable result.)

⇒ a driver emits a memoryless attachment by **clearing the backing bit (`+0x24` bit27),
writing the poison surface address, and zeroing the backing size/stride/offset**; the store
action must be DontCare/Resolve (no store phase, §5).

---

## 5. Load/store actions, the 3-segment chain, and the tiler parameter buffer

### 3-segment attachment chain = load / render / store [HW]
The 3D attachment descriptor `0x10000110000` is a chain of **0x300-byte segments**, one phase
each (`raw/hex/base_attach.hex`, base = bgra8 / Clear / Store):

| segment | offset | role | key contents |
|---|---|---|---|
| seg 0 | `+0x000` | **load setup** | self-ptrs `+0x00`; format word `+0x20`=`0xf60a0a02` (byte `+0x22`=`0x0a` BGRA8), RT surface `+0x28`=`0x00058000`; clear-color float `+0x17c` |
| seg 1 | `+0x300` | **render / main** | **clear-enable** at seg`+0x168` (`+0x468`) bit24 (`0x01000000`); clear color `+0x47c` |
| seg 2 | `+0x600` | **store** | store format `+0x620`=`0x3fc60a02`; store program id **`0x6f`** + store surface addr `0x00058000` at `+0x8c0`; `0xffffffff` fill where load addrs would be |

### Load action [HW]
`base` (Clear) vs `ld_dc` (DontCare) — **3 words only** (`raw/hex/KEY_DIFFS.txt`):
- seg1 `+0x468`: `0x01000002 → 0x00000002` — **clear-enable bit24 cleared**.
- `+0x17c`, `+0x47c`: clear color `1.0 → 0.0` — clear color removed.

`ld_load` (Load) instead **adds a load segment** that references the RT surface (the chain
grows), confirming load reads existing tile contents from memory.

### Store action [HW]
`base` (Store) vs `st_dc` (DontCare): the **store segment** (seg 2, `+0x8c0`) changes — the
store surface addresses `0x00058000` become `0xffffffff` (no store) and the tail restructures.
⇒ store surface address + store program id (`0x6f`) live in the store segment.

### Depth store/load [HW-negative]
`depth_priv` (depth storeAction DontCare) vs `depth_dstore` (Store) produced **no captured BO
difference** (only the `gpu_va=0x0` artifact). Depth store/ZLS decisions for a Private depth
attachment are **firmware/ZLS-managed**, not emitted in the userspace stream we capture.

### Tiler parameter buffer & partial render
- **Tiler parameter / geometry heap:** `0x10000018xxx` (per-attachment imageblock + primitive
  descriptors, §2) and the large sparse **`0x10000140000`** (up to ~419 MiB `AGXParameterBufferMaxSize`
  per hardware-overview) hold the **vertex/primitive data buffered between the tiler (TA) and
  fragment (3D) stages**. Present in every draw; grows with geometry.
- **Depth-only / partial render** (`nocolor` = `--depth --nocolor`): builds the **full tiling
  context (`0x68000`, still 32×32) + tiler param heap but NO color attachment descriptor at
  `0x10000110000`** (the depth attachment moves to `0x10000030xxx`). This is the Z-prepass /
  partial-render path — the tiler still bins geometry; only the fragment/store phase differs.
- **Overflow / partial-render trigger config:** no userspace-visible knob found. Parameter-buffer
  overflow → flush/partial-render is **firmware-managed** (consistent with the kernel classes
  `AGXParameterBufferManagement` / `AGXSpillBufferManager`). Flag for the kernel team.

### Userspace vs firmware split (summary)
| Userspace **emits** (in captured BOs) | Firmware / kernel **manages** (not in userspace stream) |
|---|---|
| tile grid `0x68000` (32×32 count) + viewport + depth range | programmable sample-position table |
| attachment descriptor: format, **sample count**, **memoryless bit + poison addr**, load/store (clear-enable, store addr, store program), clear color | depth store / ZLS decision |
| per-attachment imageblock offsets (tiler heap) | parameter-buffer overflow → partial-render trigger |
| tiler parameter/geometry heap allocation (`0x140000`) | ring/doorbell submission (EXP-0009) |

---

## 6. What is opaque / recommended next
1. **Programmable sample-position values** — not in userspace BOs; locate the firmware/register
   path (kernel-team coordination). *(HW-negative established; encoding unknown.)*
2. **Packed pixel-format word** (`+0x20`; `0xf60a0a02` BGRA8, `0xf6888e02` RGBA32F, `0xf9680002`
   R8, `0xf6880982` RGB10A2) — full bit decode belongs to `docs/descriptors/` (EXP-0015).
3. **`+0x24` bits [27:24]** exact semantics beyond the validated points (2×/4×/memoryless);
   probe 8× MSAA and depth-only sample counts.
4. **Depth/ZLS store control** — where the depth store decision is emitted (firmware side).
5. Confirm the tile grid on **very large** RTs and whether any format *ever* triggers a
   sub-32×32 tile (none seen up to 64 KiB imageblock).

## Established facts → docs
Sections 1–5 (tile grid `0x68000`; imageblock per-attachment stride; sample-count `+0x24`;
memoryless bit27+poison; 3-segment load/render/store; tiler-param role; userspace/firmware
split) → `docs/pipeline/` with DATA-TRACE/HW-PROBE provenance (EXP-0021). Orchestrator owns docs.

## Deliverables
`tvar.m` (harness), `run.sh` (capture+diff driver), `raw/hex/` (curated control-BO hexdumps +
`KEY_DIFFS.txt`), `raw/analysis/` (`diff_*`, `focus_*` byte-diffs). Reused read-only:
`tools/iotrace/` (`iotrace.c`, `bodiff.py`, `bograph.py`, `dumpscan.py`), `tools/agxtest/agxrender.m`.

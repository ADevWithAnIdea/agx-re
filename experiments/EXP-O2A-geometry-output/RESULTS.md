# EXP-O2A Results — geometry-output pipeline (multi-viewport/scissor, clip/cull, point_size, primitive restart, alpha-to-coverage/one, fill mode)

**TL;DR.** On A18 Pro / G17P / macOS 26.6, change-one-Metal-parameter byte-diffing of the registered
GPU BOs (39 base captures + 5 alpha follow-ups, `iotrace` read-only, **all `status=4`, zero reboots,
zero Metal rejections**) decodes the whole geometry-output surface:

1. **Multi-viewport** array lives in the tiling context `0x68000`: a **count word** `+0x900 =
   ((count−1)<<12)|0x0C00`, a per-viewport **control-word header** (multi only), then a **6-float /
   `0x18`-byte per-viewport transform array** (the single-viewport block at `+0x910`, arrayed).
   **Multi-scissor is kernel-managed** — the rectangle array is in **no** client BO (only a
   scissor-enable bit `0x58000+0x34` bit16 and the tile-grid bound are visible). Viewport-index
   **selection = the VS `[[viewport_array_index]]` output** (dynamic); declaring it sets output-select
   `0x58000+0x20` **bit19**.
2. **Clip distance** = shader-output varying + a **per-plane mask** in the PPP output-select word
   **`0x58000+0x20` bits[7:0]** (1→0x01, 2→0x03, 4→0x0f, 8→0xff; **max 8 planes**). **Cull distance is
   not exposed by Metal.**
3. **`[[point_size]]`** = shader-output varying, **enabled by the point primitive type** (sets
   `0x58000+0x20` **bit18** + point raster flags); the size **value is 100% shader-driven** (no
   descriptor field). Primitive byte `0x18000+0x65`: point `0x00`, line `0x01`, linestrip `0x03`, tri
   `0x06`, tristrip `0x09`.
4. **Primitive restart** = the indexed-draw VDM record's **cut/restart index at `0x18000+0x68` =
   all-ones of the index width** (`0xffff` u16 / `0xffffffff` u32); restart is tied to the strip
   opcode (`+0x6c` bit0), **no separate enable bit**, and Metal never programs a custom cut value.
5. **Alpha-to-coverage** = shader-lowered (FS grows) **+ FF enable bits** `0x58000+0x18` bit0 (MSAA
   only) & `+0x50` bits[30,26]. **Alpha-to-one has NO fixed-function field** — realized entirely in the
   fragment-shader epilog (output alpha forced to 1.0).
6. **Fill mode**: lines = `0x58000+0x34`/`+0x50` bit26 + nibble `+0x38`/`+0x40` (`0x_20_→0x_24_`) +
   line-width `+0x54`/`+0x58`. **Polygon-point fill is not exposed by Metal** (`MTLTriangleFillMode` =
   fill/lines only) → inferred field, untestable here.

Every field tagged **HW-validated** below is a single/clean multi-word diff from changing exactly one
Metal parameter against a byte-identical baseline (determinism: `base` vs `base2` = 0 words on all
targeted BOs). Raw diffs in `raw/ana/`, curated hexdumps in `raw/hex/`.

Legend: **HW** = diff-confirmed on hardware; **INF** = inferred (structure/architecture, not directly
provoked); **KERN** = kernel/firmware-managed (not a client descriptor).

---

## 1. Multiple viewports / scissor rects

### 1a. Viewport array — tiling context `0x68000` (HW)
Baseline `--nvp 0` (single `setViewport:`) vs `--nvp {1,2,4,8,16}` (`setViewports:count:`), plus
`--vpmod` (perturb only viewport[1]).

| offset | field | encoding |
|---|---|---|
| `+0x900` | **viewport count** | `((count−1) << 12) \| 0x0C00`. HW: 1→`0x0C00`, 2→`0x1C00`, 4→`0x3C00`, 8→`0x7C00`, 16→`0xFC00` (bits[15:12] = count−1). Single `setViewport:` ≡ count 1 = `0x0C00`. |
| `+0x904`/`+0x908` | macro-tile grid extent | `0x80000000\|(ceil(W_eff/32)−1)` / `ceil(H_eff/32)−1` (shared with RT size & scissor bbox; see §1b). Not per-viewport. |
| `+0x90C` (multi only) | **per-viewport control-word header** | `(count−1) × {0x80000001, 0x00000001}` then a trailing `0x00000001`. Header length = `2·count − 1` words. Role **INF** (per-viewport enable/guardband). Absent for single viewport. |
| header end → | **per-viewport transform array** | **6 × float32 per viewport, stride `0x18`**. Single-viewport array is the same 6-float block at `+0x910`. |

**Per-viewport 6-float block** (`{translate_x, scale_x, translate_y, scale_y, depth_min, depth_max}`;
matches the documented single-viewport transform + depth range). HW-validated by `--vpmod`: perturbing
only viewport[1]'s height+znear changed **exactly** floats 3–6 of slot 1 (`ty, sy, dmin, dmax`), leaving
floats 1–2 (`tx, sx`) untouched → stride `0x18` locked. Worked example (`--nvp 4`, hex `raw/hex/vp4_68000.hex`):

```
+0x900: 00003c00  80000001  00000001          <- count word, tile-grid X/Y
+0x90c: 80000001 00000001 80000001 00000001    ┐ 3 pairs {0x80000001,0x00000001}
+0x91c: 80000001 00000001 00000001             ┘ + trailing 0x00000001  (7-word header)
+0x928: 41f00000 41f00000 41c80000 c1c80000 00000000 3f800000   viewport[0]  {30,30,25,-25, 0.0, 1.0}
+0x940: 41f00000 41e80000 41d40000 c1c40000 3ca3d70a 3f75c28f   viewport[1]  {30,29,26.5,-24.5, 0.02, 0.96}
+0x958: …                                                        viewport[2] (stride 0x18) …
```

### 1b. Scissor rects — kernel-managed (HW negative + KERN)
`--nsc {1,2,4,8}` (`setScissorRects:count:`) and `--scmod` (perturb only scissor[1]) produce **identical
client descriptors** — the rectangle coordinates + the multi-rect array are in **no captured BO**. The
only client-visible footprint of a scissor:

| offset | change | meaning |
|---|---|---|
| `0x58000+0x34` bit16 | `0x00040200 → 0x00050200` | **scissor-test enable** (HW) |
| `0x48000+0x04` | `0 → 1` | tiler-context scissor flag (HW) |
| `0x68000+0x904`/`+0x908` | `0x80000001/1 → 0x80000000/0` | macro-tile grid **clamps to the scissor bounding box** (HW; only slot-0 bbox, not the array) |

`sc1`≡`sc2`≡`sc4`≡`sc8` and `sc2`≡`sc2m` on all descriptors (only *output pixels* differ). **The scissor
rectangle array is routed via the kernel submit (`isp_scissor`), consistent with `docs/kernel-interface`
§6.1 — flag for the kernel team.**

### 1c. Viewport-index selection (HW)
The index is the VS **`[[viewport_array_index]]` output** (dynamic, per-primitive). **Declaring** the
output (`--vpidx K`) sets:

| BO+off | change | meaning |
|---|---|---|
| `0x58000+0x20` | `…0000 → …80000` (**bit19**) | output-select: viewport-index present |
| `0x58000+0x2c` | `8 → 9` | total vertex-output count (+1) |
| `0x18000+0x10` | `0x0808 → 0x0909` | VDM output-count word (two bytes, both = count) |
| `0x10000120000+0x34` | `3 → 4` | vertex-output/varying-linkage count (+1) |
| `0x10000000000` | VS code grows | compiler emits the index write (located, not disassembled) |

Changing the **value** (`--vpidx 0/1/3`) touches only the VS code + varying-linkage BO
`0x10000120000` — **no descriptor field carries the index**. Selection is 100% shader-driven.

---

## 2. Clip / cull distances

### 2a. Clip distance = varying + per-plane mask (HW)
`--clipdist N` (VS emits `float cd [[clip_distance]] [N]`). The plane count is a **contiguous bit mask in
the PPP output-select word**:

| N | `0x58000+0x20` | mask [7:0] | `0x58000+0x2c` (out count) | `0x18000+0x10` |
|---|---|---|---|---|
| 0 | `0x00010000` | — | 8 | `0x0808` |
| 1 | `0x00010001` | `0x01` | 9 | `0x0909` |
| 2 | `0x00010003` | `0x03` | 10 | `0x0a0a` |
| 3 | `0x00010007` | `0x07` | 11 | `0x0b0b` |
| 4 | `0x0001000f` | `0x0f` | 12 | `0x0c0c` |
| 8 | `0x000100ff` | `0xff` | 16 | `0x1010` |

**`0x58000+0x20` bits[7:0] = one enable bit per clip plane** (HW-validated, exact bit-per-plane fit;
**max 8 planes**). bit16 = position-present (baseline). Output-count fields grow by the plane count. The
VS machine code emits the clip-distance values (compiler-generated). This is the **PPP vertex
output-select register** — the same word carries clip mask [7:0], point_size (bit18), viewport-index
(bit19).

### 2b. Cull distance — not exposed by Metal (INF / capability-matrix)
MSL has **only `[[clip_distance]]`** (no `[[cull_distance]]`). The 8-bit mask has headroom, but whether
any bit can carry cull (keep-if-any-negative) semantics is **untestable through Metal** → a Vulkan/GL
driver must emulate cull distance (or probe the field via cmdstream injection).

---

## 3. `[[point_size]]` + point primitive path

### 3a. Primitive-type byte `0x18000+0x65` (HW, reconfirms EXP-0014)
point `0x00`, line `0x01`, linestrip `0x03`, tri `0x06`, tristrip `0x09` (opcode `0x61c4` unchanged for
all non-indexed prims; only the prim byte moves).

### 3b. Point-size output (HW)
`--prim point` (vs `tri`) sets:

| BO+off | change | meaning |
|---|---|---|
| `0x18000+0x65` | `0x06 → 0x00` | primitive type = point |
| `0x58000+0x20` | `0x00010000 → 0x00050000` (**bit18**) | **point_size output present** |
| `0x58000+0x2c` | `8 → 9` | output count (+1 for point-size slot) |
| `0x58000+0x34` bit26 / `+0x50` bit26 | set | non-fill (point/line) raster mode |
| `0x58000+0x54`/`+0x58` | `0x07e00000 → 0x47e00000` | point-raster constant (bit30; **fixed**, not the size) |

**The point-size value is 100% shader-driven:** `pt` (default, no `[[point_size]]`) vs `pt_ps`
(writes 8.0) → **0 descriptor diffs** (only VS code); `pt_ps` (8.0) vs `pt_ps16` (16.0) → **0 diffs on
every BO**. The point primitive *reserves the point-size output slot* (bit18 + count) whether or not the
shader writes it; default size = 1.0.

---

## 4. Primitive restart / index type — indexed VDM record `0x18000` (HW)

`drawIndexedPrimitives` builds an **Index-List** VDM command (base `base`→`ix_tri16`):

| offset | field | evidence |
|---|---|---|
| `+0x64` | `0x40000001` index-list marker | — |
| `+0x68` | **cut / restart index = all-ones of index width** | u16→`0x0000ffff`, u32→`0xffffffff` (HW: `ix_tri16`↔`ix_tri32`) |
| `+0x6c` | **opcode `0x61f2` + prim byte** | opcode `0x61f2`base; **bit0 = strip** (list `0x61f2`→strip `0x61f3`), **bit1 = u32** (u16 `0x61f2`→u32 `0x61f4`); prim byte `+0x6d` (`0x06` tri / `0x09` strip) |
| `+0x70` | **index-buffer VA low32** | HW-correlated: idxBuf `0x10000018700` → `0x00018700` |
| `+0x74` | **index count** | HW: 4-index draw `0x04`; 8-index (restart buffer) `0x08` |
| `+0x78` | instance count | `0x01` |
| `+0x80` | **index-buffer extent in dwords − 1** | HW 4-point fit: (u16,4)=1, (u32,4)=3, (u16,8)=3, (u32,8)=7 = `(count·isize/4)−1` |
| `+0x88` | `0xc0000000` terminator | — |

**Restart mechanism (HW):** the cut index (`+0x68`) is populated with the index-type max for **both**
list and strip draws; restart is *applied* by hardware only for strip topologies (opcode `+0x6c` bit0).
**There is no independent restart-enable bit and no user-programmable cut value** — `ix_str16` (strip, no
`0xffff` in the buffer) vs `ix_str16r` (strip, with `0xffff`) differ **only** in index count (`+0x74`)
and extent (`+0x80`); the descriptor is otherwise identical, i.e. the HW compares against the cut index
unconditionally. Metal always writes the type-max cut. **INF:** the `+0x68` field could hold an arbitrary
value (GL/D3D custom restart index) but Metal never exercises it → capability note.

---

## 5. Alpha-to-coverage / alpha-to-one

Tested at `--msaa 4` with a proper **`--calpha 0.5`** follow-up (baseline FS emits α=1.0, which makes
alpha-to-one a no-op by construction; the follow-up drives α<1 so the effect is observable).

### 5a. Alpha-to-coverage — shader-lowered + FF bits (HW)
`--a2c` (vs `--msaa 4` baseline), α=0.5:

| BO+off | change | meaning |
|---|---|---|
| `0x58000+0x08` | `0x4c0 → 0x540` | fragment-shader **code size grows** (+0x80) — a2c lowered into the FS |
| `0x58000+0x18` bit0 | `0 → 1` | **alpha-to-coverage enable** (set **only** at samples>1; msaa1 doesn't set it) |
| `0x58000+0x50` | `0x00000200 → 0x44000200` | bits[30,26] = coverage/sample raster flags |
| `0x10000000000+0x340` | FS block `0x140→0x1c0` | FS machine code changed (compiler-generated) |

So a2c is Apple's programmable-blend-style model: **coverage is computed in the fragment shader** with a
fixed-function enable bit gating it under MSAA.

### 5b. Alpha-to-one — no fixed-function field (HW)
`--a2o` α=0.5, msaa4: **`0x58000` = 0 diffs**; only the **FS code/size** change
(`0x10000000000`, 29 words) and the **output pixel alpha is forced to `0xff`** (`0x...df→0xff` at the
target). msaa1: only `0x58000+0x08` (FS size) differs. **Alpha-to-one has no descriptor bit — it is
realized entirely in the fragment-shader epilog** (the compiler forces the output alpha component to
1.0). Same class as programmable blend / logic-ops (in-shader on this TBDR).

---

## 6. Polygon fill mode

### 6a. Fill = lines (HW, reconfirms EXP-0019)
`--fill lines` (vs `fill`) at `0x58000`:

| offset | change |
|---|---|
| `+0x34` bit26 | `0x00040200 → 0x04040200` |
| `+0x38`/`+0x40` (depth-raster nibble) | `0x07200f00 → 0x07240f00` (nibble `0x_20_→0x_24_`) |
| `+0x50` bit26 | `0x00000200 → 0x04000200` |
| `+0x54`/`+0x58` (line width) | `0x07e00000 → 0x57e40000` |

### 6b. Polygon-point fill — not exposed by Metal (INF / capability-matrix)
`MTLTriangleFillMode` has only `.fill` and `.lines`; there is **no** `.point`. The raster fill field
(`0x58000+0x38/+0x40` nibble: fill `0x_20_`, lines `0x_24_`; flag bit26 at `+0x34`/`+0x50`) plausibly has
a third value for point-fill, but it **cannot be provoked or validated through Metal** — it would require
raw cmdstream injection (out of scope for byte-diff). Point-fill stays **INF/untested**.

---

## HW-validated vs inferred vs kernel-managed

**HW-validated (this experiment):**
- Viewport count `0x68000+0x900 = ((count−1)<<12)|0x0C00`; 6-float/`0x18` per-viewport stride
  (slot-1 isolation); per-viewport control-word header length `2·count−1`.
- Scissor-enable `0x58000+0x34` bit16; scissor bbox → tile-grid clamp `0x68000+0x904/+0x908`; scissor
  tiler flag `0x48000+0x04`.
- Viewport-index/point-size/clip in the **PPP output-select word `0x58000+0x20`**: clip mask [7:0] (1/2/
  3/4/8-plane fit), point_size bit18, viewport-index bit19; output-count fields (`+0x2c`, `0x18000+0x10`,
  `0x10000120000+0x34`).
- Primitive byte `0x18000+0x65` (point/line/strip/tri); point-size value is shader-only.
- Indexed VDM record: cut index `+0x68` = type-max (u16/u32), opcode strip/u32 bits, index count `+0x74`,
  extent `+0x80`, idxBuf VA `+0x70`; restart has no enable bit / no custom cut.
- Alpha-to-coverage FF bits (`0x58000+0x18` bit0, `+0x50`) + shader lowering; alpha-to-one has no FF
  field (in-shader epilog).
- Fill-mode raster field (fill/lines).

**Inferred (structure, not directly provoked):**
- The per-viewport control-word header `{0x80000001,0x00000001}` role (enable/guardband).
- The viewport 6-float scale/translate *naming/order* (semantics match documented single-viewport
  transform; array layout is HW).
- Custom (non-max) primitive-restart index at `+0x68` (field exists; Metal never writes it).

**Metal does NOT expose (→ `docs/capability-matrix`, emulate in Vulkan/GL):**
- **Cull distance** (`[[cull_distance]]`) — MSL has clip only.
- **Polygon-point fill** — `MTLTriangleFillMode` = fill/lines only.
- **Custom primitive-restart index** — Metal fixes it to the index-type max.

**Kernel/firmware-managed (not a client descriptor — coordinate with kernel team):**
- **Multi-scissor rectangle array + per-rect coordinates** (`isp_scissor` submit param). Only the
  scissor-enable bit and the derived tile-grid bound are client-visible.

## Recommended next
1. Confirm the viewport control-word-header role by rendering into distinct per-viewport regions and
   toggling depth clip per viewport (does a header word carry per-viewport depth-clip/guardband?).
2. Kernel-team item: capture the `isp_scissor` submit parameter (scissor rect array) at the
   userspace↔kernel boundary — the only geometry-output state not in a client BO.
3. cmdstream-injection probe (separate splice experiment) for polygon-point fill (raster nibble ≠ 0x20/
   0x24) and a custom restart index at VDM `+0x68` — both HW fields exist but Metal can't reach them.

## Deliverables
`ovar.m` (parametric geometry-output harness), `run.sh` (device driver), `raw/ana/` (byte-diffs),
`raw/hex/` (trimmed control-BO hexdumps), `raw/stdout/` (per-capture logs), `README.md`, `RESULTS.md`.
Clean-room: **DATA-TRACE + OWN-SHADER**; no Apple binary inspected; Metal-generated shader code located,
not disassembled; `.dylib`/binaries stayed on-device under `~/cleanroom_work/exp_o2a/`.

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
  LSB, bit27 = MSAA-store). Full RENDER/STORE-segment `+0x24` words (EXP-M4-09/CMD-7): 1× = `0x0000fc03`,
  2× = `0x0800fc03`, 4× = `0x0900fc03`. **Only 2×/4× exist — 8× is Metal-rejected** (`supportsTextureSampleCount:`
  1/2/4 = YES, 8/16/32 = NO; 8× hard-asserts on texture creation and returns nil+NSError on pipeline creation),
  so no 8× stream is producible. The color descriptor relocates from `0x10000110000` into the tiler heap on
  **MRT≥2 OR MSAA OR memoryless** (RT-4).
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
  clear-enable (bit24 at seg+0x168) + clear color. A prior single-RT layout places value `0x6f` and a
  store surface in seg2; `loadAction=DontCare` changes that layout and `storeAction=DontCare` poisons its
  store address. **This is not a universal MRT rule:** EXP-0048's M4 two-attachment layout leaves the
  complete relocated LOAD/STORE-PBE arena byte-identical across the tested action changes. There,
  drawn Clear/Store and Load/Store correlate with `0x58000+0x14` values `0x19` and `0x10`, while
  Clear/StoreDontCare correlates with `0x20`; empty Clear/Store and Load/Store are identical in all four
  allowlisted state BOs despite distinct live results. `+0x14` is only an action/path-selector candidate.
  Value `0x6f`'s meaning and ownership remain **UNKNOWN**; its prior fixed single-RT slot is zero in the
  relocated MRT arena. **Depth store-action / ZLS is firmware-managed** (not captured) — route via kernel.
- **Tiler parameter buffer** (`0x10000018xxx` + sparse `0x10000140000`): buffers vertex/primitive data
  between the tiler (TA) and fragment (3D) stages. A depth-only pass still builds the full 32×32 tiling
  context + param heap with no color descriptor (Z-prepass / partial-render path). The **overflow →
  partial-render trigger is firmware-managed** — no userspace knob (kernel/firmware concern).

### ✅ The BG/EOT PROGRAM can be constructed and executed (EXP-0130) — `target: G16G`

Evidence label **`HW-PROBE` + `OWN-SHADER` + `PUBLIC`**, `target: G16G` (local Apple M4).
Source: `experiments/EXP-0130-m4-bg-eot-construction/RESULTS.md`, commit `5c677b72`; gates
`--selftest` 14/14, `--seqtest` 6/6, `--captured` 10/10.

**A fragment program that reads the tilebuffer and writes the attachment can be CONSTRUCTED from
our own MSL and executed** — it does not have to be lifted from a capture. `f_eot_combine`
(`dst*2.0 + src`) is **behaviourally exact against a host oracle on 4/4 boundary cases in both
runs** — `3·2+1 = 7`, `−10·2+1 = −19`, `1000000·2+2 = 2000002`, `0.5·2+2 = 3` — and its extracted
**120 bytes contain both `tile_read` and `frag_color_store`**.

- **Paired falsifier:** `f_eot_ctrl` (54 B — `frag_color_store` but **no** `tile_read`) returns a
  constant across all 8 `dst` values including near-`FLT_MAX`, so the oracle match above is not a
  rubber stamp.
- ⛔ **NEGATIVE:** `f_eot_evict` (pure passthrough) is **elided entirely by the compiler** — 16 B,
  **neither** opcode. This independently reproduces EXP-0117's elision from a different code path.
  A driver cannot obtain a passthrough BG/EOT program by writing one in MSL; the compiler deletes
  it.
- The `tile_read` encoding itself is now **emittable with a per-field legal-value set** — and its
  wrong-value failure mode is a **silent zero, i.e. a black tile, not a fault**. See
  `../isa/README.md` → "`tile_read` / `tile_read_mrt` are EMITTABLE" (EXP-0147).

> ⚠️ **BOUNDED NEGATIVE on the UAPI side (P0.4/P0.5 remain OPEN).** `drm_asahi_bg_eot` **cannot be
> populated on this host** — macOS, no `/dev/dri`, no drm/asahi kext — so its `usc` and
> `rsrc_spec` field requirements are **`PUBLIC`-only inference from the pinned MIT header, NOT
> Apple9 hardware facts.** Do not read the program-side success as closing the submission side.

## Open items
- Depth/ZLS store control (kernel-side). (Sample positions are now known userspace-emittable — RT-4.)
- Full packed pixel-format word decode (→ `../descriptors/`); `+0x24` bits beyond 2×/4×/memoryless.
- BG/EOT/partial program tags, resource specs, ABI, and the ownership/meaning of single-RT value `0x6f`.

## Render-target attachment descriptor — full field map (EXP-G1b)
The attachment descriptor (`0x10000110000`) is a chain of three **0x300-byte segments: LOAD (+0x000) / RENDER (+0x300)
/ STORE (+0x600)**.
- **Surface VA** = `((word3 & 0xfff)<<32 | word2) << 4` (same `VA>>4` as textures; HW-correlated to the RT buffer).
- **STORE segment is itself a PBE descriptor:** word0 byte3 = **width−1**, word1>>6 = **height−1**, word2 = surface
  `VA>>4`, word3[12:] = **stride/rowBytes**. HW-validated over 6 sizes (asymmetric 128×64 separates W/H) and 6 formats.
- **LOAD/RENDER:** format word @seg+0x20; **format code = byte+0x21 (= sampled byte1), NOT byte+0x22** (EXP-M4-08 DESC-1: +0x22 is the swizzle low byte; the old '+0x22' only coincided for bgra8 where swizzle-low 0x0a==format 0x0a). Full word = `(0xf<<28)|(swizzle[11:0]<<16)|(byte1<<8)|(byte0&~0x20)`, validated 43/43 formats. config/sample @+0x24; **clear-enable = bit24 @
  seg1+0x168**, clear-color floats @+0x17c. `loadAction=Load` injects a surface-read descriptor.
- **Store action (single-RT layout):** observed value `0x6f` + store surface addr
  (`storeAction=DontCare` poisons that layout's addr). EXP-0048 corrects the earlier
  universalization: its relocated M4 MRT records are unchanged for StoreDontCare,
  with a separate action-correlated byte at `0x58000+0x14`. `0x6f` semantics and
  ownership are unresolved, not established as firmware-managed.
- **MSAA:** byte0 low-nibble→4 (2DMultisample), +0x24 sample count (`0x08`=2× / `0x09`=4×); **sample positions are userspace-emittable @+0x40** (1/16-grid f32 pairs; RT-4, corrects EXP-0021).
- **MRT:** N≥2 attachments (or any MSAA) relocate the color descriptor into the tiler geometry heap `0x10000018200`,
  arrayed as **fixed 0x20-byte per-attachment records** (LOAD @`+0x20+k·0x20`, STORE/PBE @`+0x220+k·0x20`);
  per-attachment surfaces at 0x58000/0x60000/… (distinct from the 0x1000 imageblock tile-memory record). **The
  0x20-byte k-stride is HW-validated to k=7 (all 8 attachments), and each record's format word is genuinely
  per-attachment** (mixed-format MRT: each byte = `numtype<<5|sizeclass` per `../descriptors/format-table.md`) —
  EXP-M4-09/CMD-3.
  - **EXP-0048 M4 action/format control:** the 0x20-byte LOAD records at
    `+0x20+k·0x20` and STORE/PBE records at `+0x220+k·0x20` reproduce exactly
    across two runs for RGBA8, BGRA8, sRGB, R32Float, R32Uint and mixed MRT.
    In both record families the low 40 bits of the qword at record `+0x08`,
    shifted left four, reconstruct the authored surface VA. sRGB retains
    RGBA8's low-24 format value but changes the opaque upper packed control.
  - **⚠ Clear-color CORRECTION (EXP-M4-09/CMD-3, A18-cross-confirmed):** the earlier claim *"clear-color @
    `+0x500+k·0x18` inside `0x10000018200`"* was a **vertex-buffer allocator alias** — `vtxBuf` lands at
    `0x10000018700` = `0x18200+0x500`, so reading there returns the triangle verts (`-1,-1,3,-1,-1,3`; the
    phantom `0x18` stride was the 6-float triangle). The **real** per-attachment clear colors are a **float4
    RGBA array at 0x10 stride** in a **separate tiler BO `0x10000128000`** at **`+0x170 + k·0x10`** (RT0 =
    (0,0,0,1) @ `+0x170`), **mirrored at `+0x470 + k·0x10`** (0x300 apart = the LOAD/RENDER segment spacing).
    Byte-identical on M4 and A18. The `0x18200` k·0x20 records hold LOAD/STORE descriptors only — **not** the
    clear color.

### Depth / stencil reuse the SAME k-indexed attachment array (EXP-0132) — `target: G16G`

Evidence label **`HW-VALIDATED`** (byte-exact across two runs), `target: G16G` (local Apple M4).
Source: `experiments/EXP-0132-m4-pbe-attachment-structures/RESULTS.md`.

- **Depth and stencil populate the same k-indexed `0x20`-byte MRT descriptor array as colour**,
  at **`k = ncolor`** (depth) and **`k = ncolor + 1`** (stencil). The depth prefix
  `628800f8017c0008` reproduces EXP-0108's flagged bytes; stencil is distinct
  (`224068f9017c0008`). The adversarial `ncolor = 2` case places depth at `k = 2` and stencil at
  `k = 3`, exactly as the rule predicts.
- **Memoryless depth still populates its slot**, flipping one unmasked byte `0x08` → `0x00`.
- **MSAA resolve targets take the next free `k` slot in BOTH the LOAD and the STORE arrays.**
- `mipCount > 1` sets word1 **bit 26** — the same "mipmapped" flag bit the sampled-texture
  descriptor uses.
- **NOT REPRODUCED:** `attachment-slot-b` never appeared in 16 cases.
- **Untested combination, stated:** depth/stencil *and* an MSAA resolve present in the same pass.

### ⚠️ Array slice and mip level are NOT in the per-attachment record — and the two boundaries fail DIFFERENTLY (EXP-0132) — `target: G16G`

**NEGATIVE, `HW-VALIDATED`, byte-exact:** the per-attachment `k`-record is **byte-identical**
across slice 0 / 1 / 3 of an `arrayLength = 4` target and across level 0 / 2 of a `mipCount = 3`
target. **Layer/array and mip *selection* are carried somewhere other than this descriptor.**
The only `mipCount`-dependent difference is word1 bit 26, which tracks *whether* the texture is
mipmapped, not *which* level is being rendered.

**The two out-of-range boundaries are both silently accepted, and they do OPPOSITE things:**

| out-of-range input | observed | class |
|---|---|---|
| **`slice = arrayLength`** (first invalid) | **slice 0's existing content is DESTRUCTIVELY ZEROED** — its pre-render canary `a0a0a0a0` is overwritten with `0`, even though slice 0 was never the render target. Slices 1–3 keep their canary untouched. | **destructive, silent** |
| **`level = mipCount`** (first invalid) | **all three levels keep their canary untouched — no observable effect anywhere.** | **pure no-op, silent** |

Note this is **not** a modular `slice % arrayLength` wraparound: a true wraparound would have
produced a *correct* clear/draw at slice 0, not a zero write. Neither case faults, errors, or
sets a status.

> **A driver must validate `slice < arrayLength` and `level < mipCount` itself before emitting a
> render pass. The hardware and the API do neither.** Getting `slice` wrong silently destroys
> unrelated data in the same texture.

## Rasterization rules and hard resource limits (EXP-0123) — `target: G16G`

Evidence label **`HW-PROBE` + `PUBLIC`**, `target: G16G` (local Apple M4, macOS 26.6.2, 16 GB
unified). Source: `experiments/EXP-0123-m4-rasterization-limits/RESULTS.md`, commit `1143ec55`.
This is the **P1.8 / `DRV-RASTER-01`** material: the rasterization behaviour and the finite
resource ceilings a conformant driver must respect.

### Line rasterization — half-open, evaluate-at-pixel-center, exact-integer ties round DOWN

| case | endpoints (8×8 target) | result |
|---|---|---|
| horizontal | (1.0,4.5)–(7.0,4.5) | columns 1..6 lit at row 4; **column 7 (the endpoint) NOT lit** |
| vertical | (4.5,1.0)–(4.5,7.0) | rows 1..6 lit at column 4; **row 7 NOT lit** |
| diagonal 45° | (1.0,1.0)–(7.0,7.0) | single-pixel staircase (1,1)…(6,6); **(7,7) NOT lit** |
| shallow slope 3/7 | (0.5,0.5)–(7.5,3.5) | row0={0,1}, row1={2,3}, row2={4,5}, row3={6} |
| exact-integer y tie | y = 4.0 | resolves to **row 3 — the LOWER row** |
| y = 3.99 / y = 4.01 | | row 3 / row 4 |
| **degenerate** (identical endpoints) | (4.0,4.0)–(4.0,4.0) | **zero pixels lit** — neither a point nor a fault |

**Rule:** half-open interval with the **final vertex excluded** (the convention that avoids
double-drawing a shared vertex in a line strip), with per-column row assignment = evaluate the
line at the **pixel-center x** and floor to the containing row. At the row boundary the interval
behaves as `(r, r+1]`, not `[r, r+1)`. **Driver consequence:** implement evaluate-at-pixel-center
+ floor, exclusive of the final vertex; no diamond-exit-specific tie-break beyond "exact integer
ties round down" was needed. A degenerate line needs **no special case** — it naturally
rasterizes nothing. **Open, narrow:** the exact subpixel snap granularity was **not** bisected
(a `y = 4.001` exploratory probe gave the same row as `y = 4.0`, consistent with snapping coarser
than 0.01 px, but this is not claimed).

### Point rasterization — the size rounding rule

| requested `[[point_size]]` | footprint side | pixels |
|---|---|---|
| 0.5, 0.9, 1.0, 1.1, 1.4, 1.5, 1.6, 1.9 | **1** | 1 |
| **2.0 exactly** | **2** | 4 |
| 2.1, 2.4, 2.5, 2.6, 2.9, 3.0, 3.5 | **3** | 9 |

### Depth clip vs depth clamp — both native, and the interval is CLOSED

| mode | z (all 3 verts) | rendered? | depth written |
|---|---|---|---|
| `.clip` | 1.5 (behind far) | **no** (0/64 px) | clear persists |
| `.clip` | −0.5 (before near) | **no** (0/64 px) | clear persists |
| `.clip` | **1.0 (exactly far)** | **yes** (18/64 px) | **1.0** — the interval is **closed** |
| `.clip` | **0.0 (exactly near)** | **yes** (18/64 px) | **0.0** |
| `.clamp` | 1.5 | **yes** (18/64 px) | **clamped to 1.0** |
| `.clamp` | −0.5 | **yes** (18/64 px) | **clamped to 0.0** |

### ⛔ Clean negatives — what a GL/Vulkan driver must emulate

| capability | native? | required emulation |
|---|---|---|
| **Wide lines** (`wideLines` / `glLineWidth`) | **No** — through the documented public API there is **no line-width, line-rasterization-mode, or conservative-raster control anywhere in the SDK headers**; every line renders at the same fixed narrow band regardless of documented state | Expand each line into a quad/triangle pair in a geometry stage or vertex shader |
| **Polygon mode POINT** (`VK_POLYGON_MODE_POINT` / `GL_POINT`) | **No** — `MTLTriangleFillMode` is a real, functionally distinct **two**-valued enum (`.fill` 72 lit px / `.lines` 38 lit px on the same reference triangle), and there is no third case | Re-emit each triangle's three vertices as a point-topology draw |
| **Conservative rasterization** | **No — clean negative with no API surface at all.** Four tiny triangles each covering ~0.2×0.2 px at a *corner* of pixel (4,4), explicitly not its centre, lit **zero pixels in all four cases, both runs** — exactly what standard centre-sample rasterization predicts | Inflate primitive edges outward by the pixel diagonal in the vertex/geometry stage |
| **Depth clamp / depth clip** | **Yes, both native** (`MTLDepthClipModeClamp` / `…Clip`) | none |

Also recorded: `MTLTriangleFillMode` is **inert for line-topology primitives** — a functioning
no-op, as its name implies.

> **⛔ CLEAN-ROOM RULING, recorded so it is not re-litigated.** During exploration (outside the
> frozen matrix) an **undocumented** `-[MTLRenderCommandEncoder setLineWidth:]` selector was found
> to respond and, invoked through the ObjC runtime, to grow a line's footprint roughly linearly
> (1 px→12, 2→24, 5→60, 10→120 lit pixels, capping near 192). **This was ruled OUT OF BOUNDS:
> probing a guessed private selector is symbol-level introspection of Apple software, not hardware
> observation** (`PROVENANCE.md`, EXP-0123 row). It is excluded from every normative claim and
> from the limit table below. **The negative result above — no wide-line control via the
> documented API — is the one this project stands behind.**

### A2C coverage reaches the occlusion counter (extends EXP-0091)

Full-cover triangle, `Depth32Float`, `depthCompare: Always`, `depthWrite: YES`, no shader depth
write and no `discard_fragment()` — i.e. **early-Z-eligible** per EXP-0091:

| `alphaToCoverageEnabled` | alpha | samples | occlusion count | colour px lit |
|---|---|---|---|---|
| **true** | **0.0** | 4 | **0** | **0/16** |
| true | 1.0 | 1 | 14 | 14/16 |
| false (control) | 0.0 | 1 | 14 | 14/16 |
| false (control) | 1.0 | 1 | 14 | 14/16 |

**A2C-driven coverage suppression reaches the visibility counter** — *not* the 14 that a naive
"early depth test happens before shading, so occlusion is counted regardless" model predicts.
**Driver consequence: a backend must NOT assume A2C is invisible to occlusion/predication
bookkeeping.** A2C coverage participates in whatever gates the visibility counter, alongside
`discard_fragment()`. *(One non-reproducible fault was seen while exploring the adjacent
`A2C = true, alpha = 1.0, samples = 4` case — occlusion + depth + MSAA resolve + an unguarded
point readback together. It re-ran successfully 3/3 afterwards and is recorded as an open,
unresolved, non-reproducible fault, deliberately excluded from the frozen matrix rather than
dropped.)*

### Verified finite-limit table — `target: G16G`

Every boundary below is off-by-one tested (last legal value **and** first invalid value).

| resource | last legal | first invalid | failure mode |
|---|---|---|---|
| Colour render-target attachments | **8** (functional: 8 distinct textures, each correct per-attachment) | 9 | **uncatchable `abort()`** in pipeline-state creation |
| Simultaneously active viewports | **16** (functional: all 16 tile regions render via 16-instance `[[viewport_array_index]]` routing) | 17 | `setViewports:count:` rejection |
| 2D / cube texture width & height | **16384** (both axes) | 16385 | uncatchable `abort()` from texture-descriptor validation |
| 3D texture, per axis | **2048** | 2049 | same `abort()`, isolated per axis |
| 2D texture-array layers | **2048** | 2049 | same `abort()` |
| Mip levels | `floor(log2(max(w,h))) + 1` — confirmed **15** at 16384², **7** at 64² | boundary + 1 | same `abort()` |
| Direct `[[buffer(N)]]` bind index | **30** (31 slots, 0..30) | 31 | **clean MSL frontend `COMPILE_FAIL`** — rejected at compile, not at runtime |
| Direct `[[texture(N)]]` bind index | **127** (128 slots, 0..127) | 128 | same clean `COMPILE_FAIL` (matches EXP-0095's independent figure) |
| Inline constants (`setVertexBytes:` / `setFragmentBytes:`) | **32752 bytes** (functionally verified — both the first and the exact last byte round-trip) | 32753 | — |
| Buffer bind offset alignment | **arbitrary** — 0, 1, 2, 3, 4, 15, 17 bytes all functionally correct, exact byte-for-byte readback | n/a | no misalignment failure exists |
| Threads per threadgroup (compute) | device-reported **1024**, functionally confirmed | 1025 | — |
| Dynamic threadgroup memory | **≥131072 bytes** confirmed at 32768 / 65536 / 131072 | not reached | — |
| SIMD / subgroup width | **32**, via `[[thread_execution_width]]` at threadgroup sizes 32 and 64 | n/a | n/a |
| `simd_shuffle` out-of-range source lane | src ∈ {0,31} exact | src ∈ {32,40,64,100} **wrap as `src % 32`** exactly | — |

> **The `abort()` rows matter more than they look.** Attachment count, texture dimensions, array
> layers and mip levels are enforced by an **uncatchable `abort()`**, so a driver **cannot probe
> them at runtime** — it must carry these as static limits. The two bind-index rows, by contrast,
> fail cleanly at MSL compile time. (Same lesson as the format-eligibility `abort()` in
> `../descriptors/format-table.md` §2e / EXP-0133.)


# RT-2a RESULTS — falsification of the command-stream field maps

Device: A18 Pro / G17P, macOS 26.6 (25G5043d). All draws/dispatches `status=4` (completed);
no faults/reboots. Every field below was localised by change-one-Metal-parameter byte-diff of
registered GPU BOs. **HW-validated** = the dispatch/draw ran and the diff isolates the field;
**inferred** = byte-diff only.

## TL;DR — verdicts
| # | Claim | Verdict |
|---|---|---|
| 1 | CDM shader-ptr @+0x08, grid @+0x10.. in threads, tg @+0x1c.., cfg @+0x00, tgmem not-here | **CONFIRMED** (grid offsets/threads exact) — **1 caveat**: tg field holds the *effective* (driver-chosen) threadgroup, not the verbatim API value |
| 2 | VDM prim @+0x65, vertexCount @+0x68, instanceCount @+0x6c, indexed 0x61c4→0x61f2 + idx VA @+0x70 | **CONFIRMED for non-indexed**; **DISCREPANCY/GAP**: for *indexed* draws the record shifts — instanceCount is @+0x78 (not +0x6c); undocumented vertexStart/baseVertex/baseInstance fields |
| 3 | USC 2-ptr header; num_tex=(samp−tex)/0x20; **num_samp=(term−samp)/8**; buffers @0x10000100000+0xa0 | header + num_tex **CONFIRMED**; **DISCREPANCY**: samplers are **0x20-stride, not 8** → num_samp = (term−samp)/**0x20** |
| 4 | State: depth +0x38, stencil +0x3c, raster +0x70, PPP output-select +0x20, PPP length word | **CONFIRMED exactly** (all bitfields), incl. +0x400 length growth; robust under MRT×8 / 16 viewports |
| 5 | Programmable blend rewrites the FS, not a state packet | **CONFIRMED decisively** (incl. dual-source) |

---

## Claim 1 — CDM compute launch descriptor (0x100000b0000) — CONFIRMED (+1 caveat)
Raw: `raw/analysisA/`, `raw/hexA/`, `raw/raw_summ/cdm_tg_probe.txt`.

- **shader ptr @+0x08 = shaderVA>>6 — CONFIRMED (HW).** base shader @0x10000090000 → `+0x08 = 0x2400`
  (0x90000>>6). Two-pipeline capture: record0 `0x2400`, record1 `0x2404` (0x90100>>6, Δ4). Huge-grid
  capture (shifted VA) → `0x39600`, still VA>>6. Record stride **0x2c**, terminator **0x40000000** — confirmed.
- **grid xyz @+0x10/+0x14/+0x18, in THREADS — CONFIRMED (HW).**
  - Non-cube 3×5×7 → `+0x10=3, +0x14=5, +0x18=7` (each axis isolated). gx 64→65 → `+0x10` only. Huge
    `dispatchThreads(0x123456)` → `+0x10=0x123456` (no truncation).
  - **Threads-not-threadgroups proven by equivalence:** `dispatchThreads(12,5,7) tg(4,5,7)` and
    `dispatchThreadgroups(3,1,1) tg(4,5,7)` produce a **byte-identical** CDM record (both grid=(12,5,7)
    threads, tg=(4,5,7)). Grid can be a non-multiple of tg (e.g. 100 threads / tg 32) — genuinely in threads.
- **threadgroup xyz @+0x1c/+0x20/+0x24 — OFFSET CONFIRMED; VALUE CAVEAT (HW).** The offset is right in
  every case, but the stored value is the **effective/driver-chosen threadgroup**, not the verbatim
  `threadsPerThreadgroup`. Metal normalizes small/awkward requests up to (typically) one SIMD (32) tiling
  the grid: requested→recorded `tg8→16`, `tg10→32`, `tg25→32`, `tg(1,1,1)→(2,4,4)=32`. Requests that are
  already ≥ the chosen partition pass through unchanged (`tg32`, `tg16`, `tg(3,5,7)`). See `cdm_tg_probe.txt`.
  → *A from-scratch Mesa driver emits the launch threadgroup it actually uses, so the offset stands; the
  doc should call the value "effective threadgroup dims", not a copy of the API argument.*
- **config word @+0x00 — CONFIRMED (HW).** base `0x00080000` (bit19), register-heavy kernel `0x00880000`
  (bit23). Matches doc.
- **tgmem NOT in the CDM record — CONFIRMED (HW).** tgmem 256↔32768 leaves the CDM record byte-identical;
  the real field is in the **shader BO 0x10000090000** (`+0x4c` bits[31:16] with carry into `+0x50`:
  256→`+0x4c`=0x0480…, 32768→0x0080…+`+0x50` bit1), i.e. `(bytes<<2)|0x80`. Matches doc.

## Claim 2 — VDM draw record (0x18000) — CONFIRMED (non-indexed); DISCREPANCY for indexed
Raw: `raw/analysisB/`, `raw/hexB/`.

**Non-indexed record (opcode 0x61c4):**
- **primitive @+0x65 — CONFIRMED (HW).** `+0x64` word = `0x61c4_PP00`; byte `+0x65` = prim:
  point `0x00`, line `0x01`, tri `0x06`, tri-strip `0x09` — all as documented. (Additional: **linestrip = 0x03**, not in the doc's enum list.)
- **vertexCount @+0x68 — CONFIRMED (HW).** 3/6/99/`0x123456`, and true 0-vertex (dvar2) → `+0x68=0`. No truncation.
- **instanceCount @+0x6c — CONFIRMED (HW).** 7 / 256 / `0x123456`.
- vertexStart lands at `+0x70` (undocumented; same slot indexed reuses for idx-VA).

**Indexed record (opcode 0x61f2) — the record SHIFTS; doc under-specifies:**
```
+0x64 0x40000001 (indexed sub-header)   +0x74 index count
+0x68 cut/restart index (u16 0xffff)    +0x78 instanceCount   ← NOT +0x6c
+0x6c 0x61f2_PP00 (opcode@+0x6e, prim@+0x6d)  +0x7c baseVertex
+0x70 index-buffer VA (+offset)         +0x80 index extent   +0x88 0xc0000000
```
- **opcode 0x61c4→0x61f2 + idx VA @+0x70 — CONFIRMED (HW).** idxoff 4 → `+0x70` +4 (it's the buffer VA).
  **Refinement: u32 indexed = `0x61f4`** (doc only gives 0x61f2 = the u16 form). cut index `+0x68` = all-ones of the width (0xffff/0xffffffff).
- **⚠ DISCREPANCY:** the doc states "instanceCount @+0x6c" flatly. For **indexed** draws `+0x6c` is the
  opcode word; **instanceCount is @+0x78**. Confirmed on `combo` (indexed, inst 3): `+0x78=3, +0x7c=baseVertex 4, +0x74=indexCount 6`. The doc (EXP-0014 line) omits this shift; EXP-O2A documents cut/opcode/count/idxVA but still omits instanceCount@+0x78 and baseVertex@+0x7c.
- **baseInstance is NOT in the VDM record** (indexed or not) — it is written to **0x10000100000+0x8c**
  (clean isolate bi0→bi9: the only differing word across all BOs is `0x10000100000+0x8c` 0→9). Undocumented.

## Claim 3 — USC bind grammar (arg buffer 0x10000248000) — DISCREPANCY (sampler stride)
Raw: `raw/hexC/`, `raw/raw_summ/usc_stride.txt`, `raw/analysisD/` (blend section unrelated).

- **2-pointer header @+0x480 — CONFIRMED (HW).** `[tex-array VA][sampler-array VA]`, 8-byte LE,
  self-referential (high32 = `0x00000100` = BO's own VA high bits). e.g. 8t4s4b: tex_ptr→+0x4c0, samp_ptr→+0x5c0.
- **Texture stride 0x20, num_tex=(samp−tex)/0x20 — CONFIRMED (HW).** Clean tex sweep 1/2/3/4/8 → tex array
  grows exactly 0x20 per texture; descriptors ordered by binding index (dataVA increments in order),
  consistent with `tex_sample` op+4/op+5 array indexing.
- **⚠ DISCREPANCY — sampler stride is 0x20, NOT 8.** Clean sampler sweep (1 tex fixed):
  1/2/3/4 samplers → `term − samp_ptr` = **0x20 / 0x40 / 0x60 / 0x80**. Each sampler occupies a **0x20-byte
  slot** (8 significant bytes + 0x18 zero pad). The doc's `num_samplers = (term − samp_ptr)/8` **overcounts
  by 4×** (gives 4/8/12/16 for 1/2/3/4 samplers). **Correct: `num_samplers = (term − samp_ptr)/0x20`.**
  Samplers are genuinely distinct per slot (alternating nearest/linear filter bytes at 0x20 stride). Terminator `0x60000000`.
  *(Recommend the orchestrator re-check EXP-G1a's raw — likely the 8 significant bytes/sampler were mistaken for an 8-byte stride.)*
- **Buffers → 0x10000100000+0xa0 — CONFIRMED for VS-stage buffers (HW).** `--vbuf 3` → `+0xa0` table =
  `[vtxBuf][vbuf0][vbuf1][vbuf2]` (8-byte LE VAs in binding-index order). Caveat: this table is
  **vertex-stage** buffers; **FS constant buffers do NOT appear at +0xa0** (they stage at +0x30/+0x38 per
  EXP-G1a). The doc's flat "one per bound buffer" should be qualified as vertex-stage.

## Claim 4 — State packets (0x58000) — CONFIRMED EXACTLY
Raw: `raw/analysisD/depth_*, stencil_*, stencilop_*, ppp_*, o_*, mrt_*`, `raw/hexD/`.

- **Depth @+0x38 — CONFIRMED (HW).** compare **[26:24]** follows enum exactly: never 0 / less 1 / equal 2 /
  lequal 3 / greater 4 / nequal 5 / gequal 6 / always 7 (`0x0X000f00`). Depth-write-**DISABLE bit21**
  (`0x07000f00→0x07200f00`). `+0x40` = back-face depth (mirrors +0x38). stencil-**ref[7:0]** in this word (`+0x38`, sref 0x27→`0x…0f27`).
- **Stencil @+0x3c — CONFIRMED (HW), every bitfield exact.** write-mask **[7:0]** (0x5a), read-mask **[15:8]**
  (0x3c), pass-op **[18:16]**, zfail-op **[21:19]**, sfail-op **[24:22]**, compare **[27:25]**. Op enum 0-7
  = keep/zero/replace/incrClamp/decrClamp/invert/incrWrap/decrWrap (verified across all 8). **`+0x44` = back-face
  stencil** (per-face `--sback` changes `+0x44` only; front `+0x3c` untouched) — fully decoded and matches.
- **Raster @+0x70 — CONFIRMED (HW).** cull **[1:0]** none 0 / front 1 / back 2; winding **bit16** (CCW);
  depth clip-vs-clamp **[11:10]** (clip 01 → clamp 10). Line-fill is separate: `+0x34` bit26 + `+0x54` nibble 0x5 (consistent with doc).
- **PPP output-select @+0x20 — CONFIRMED (HW).** clip-distance plane mask **[7:0]** (1→0x01, 3→0x07, 8→0xff);
  **point_size bit18**; **viewport_array_index bit19**.
- **PPP length word — CONFIRMED EXACTLY (HW).** `0x18000+0x0c` and `0x58000+0x14` both grow **+0x400**
  when the depth/stencil block is appended (0x4800→0x4c00 / 0x4c19→0x5019); **blend alone and cull alone
  produce ZERO 0x18000 diff**. Per-group presence is enable bits inside each packet — matches doc.
- **Robust under large/unorthodox programs.** MRT 1/2/4/8 attachments and 16 viewports leave every
  documented offset (+0x38/+0x3c/+0x70/+0x20) in place; only size/length words grow (`+0x08` FS-code size,
  `+0x14` pool length +0x200/attachment, `+0x18` flag→1 for ≥4 RTs). **No field moved unexpectedly.**
- Bonus: viewport count word **0x68000+0x900 = ((count−1)<<12)|0x0C00** confirmed (1→0xC00, 4→0x3C00, 16→0xFC00).

## Claim 5 — Programmable blend — CONFIRMED DECISIVELY
Raw: `raw/analysisD/bl_*_code.txt` (FS code BO) vs `bl_*_58.txt` (0x58000).

Every blend factor/op change rewrites the **fragment-shader code BO 0x10000000000**, never a
fixed-function blend LUT:

| change | words changed in FS code (0x10000000000) | words changed in 0x58000 |
|---|---|---|
| srcRGB zero | 3581 | 1 (FS code-size mirror @+0x08) |
| srcRGB one | 1610 | 0 |
| dstRGB dstcolor | 37 | 0 |
| op min | 41 | 0 |
| op revsub | 32 | 0 |
| **dual-source** | 1565 | 0 |
| dual-source src1color | 27 | 0 |

`0x58000` keeps only blend-enable (`+0x50` bit29) and the FS code-size mirror (`+0x08`). Dual-source blend
works entirely through the shader path. MRT blend (`mrtvar --blendmask`) is likewise shader-lowered
(`+0x08` FS-code grows). Confirms the doc's key structural claim: **the driver must compile blend into the
fragment shader.**

---

## Discrepancies to fix in docs/cmdstream/README.md (for the orchestrator)
1. **[HIGH] Claim 3 sampler stride.** `num_samplers = (term − samp_ptr)/8` is wrong — samplers are
   **0x20-stride**. Use `/0x20`. A driver using `/8` misparses sampler count 4×. Evidence: `raw/raw_summ/usc_stride.txt`.
2. **[MED] Claim 2 indexed record.** "instanceCount @+0x6c" is non-indexed-only. For indexed draws the
   record shifts: opcode/prim @+0x6c/+0x6d, cut @+0x68, idxVA @+0x70, indexCount @+0x74, **instanceCount @+0x78**,
   baseVertex @+0x7c. Also **u32 indexed opcode = 0x61f4** (doc gives only 0x61f2 = u16). Evidence: `raw/hexB/indexed.hex`, `idx32.hex`, `basevert.hex`, `raw/analysisB/`.
3. **[LOW] Claim 1 tg field** value = effective/driver-chosen threadgroup, not the verbatim API argument
   (offset is correct). Evidence: `raw/raw_summ/cdm_tg_probe.txt`.
4. **[LOW] Additions:** linestrip prim byte 0x03; non-indexed vertexStart @+0x70; baseVertex @+0x7c;
   baseInstance @ **0x10000100000+0x8c** (not in the VDM record); USC `+0xa0` buffer table is vertex-stage only.

Nothing else moved. Depth/stencil/raster/output-select/PPP-length and programmable-blend held up under
every adversarial and large-program case.

# GAP-ANALYSIS-02 — Adversarial acceptance review (objective 1)

**Reviewer role:** final-gate gap-finder. Premise: implement Apple A18 Pro (G17P / Apple9) support in
Mesa's `asahi` **userspace** driver **from scratch**, using **only `docs/`** as the source of
A18-specific hardware truth. `mesa/src/asahi` was read only to know the *shape* of what a userspace
driver must produce; `gpu_knowledge/`, `experiments/*`, `tools/` source, and `PROVENANCE.md` were **not**
used as A18 truth (a fact living only there = a gap).

**Date:** 2026-07-07. Scope reviewed (all of `docs/`): `hardware-overview.md`, `isa/README.md`,
`isa/encoding-tables.md`, `isa/agx3.xml`, `isa/msl-feature-map.md`, `cmdstream/README.md`,
`descriptors/README.md` + `format-table.md`, `tiling/README.md`, `pipeline/README.md`,
`kernel-interface.md`, `capability-matrix.md`, `capability-completeness.md`, `hypotheses.md`,
`porting-guide.md`, `ROADMAP.md`. Prior review `GAP-ANALYSIS-01.md` was skimmed but judged against the
**current** docs, which are far more complete.

---

## Overall verdict: **PASS — a userspace driver is implementable from `docs/` alone.**

Every blocking gap GAP-01 named has been closed, and no core path (compute dispatch, textured &
interpolated draw, indirect/occlusion/timestamp, geometry output, mesh, RT, matrix, function
pointers/dynamic libs, the kernel-boundary contract) is left un-emittable. The remaining deficits are
**acceptable residue**: byte-diff-inferred operand *sub-fields* whose principal encoding is already
HW-validated (with a documented fallback), one honestly-opaque hardware item (the lossless-compression
block codec), and a well-delineated set of firmware/kernel-managed items. There is also a handful of
**internal doc-consistency defects** (stale "unknown"/"open" rows contradicted by later sections) that do
not block implementation but should be reconciled for the deliverable to read as trustworthy.

### How far could you actually get now? (contrast with GAP-01, which stopped before a triangle)
- ✅ **Non-trivial compute kernel** — full scalar/int/float/half/bfloat ISA, 96-GPR machine model + spill,
  uniforms, memory/atomics, **the async model (HW register interlock, no scoreboard — EXP-0025)**, the
  threadgroup barrier scope, subgroup/quad/scan, CDM record, threadgroup-mem size field. Emittable.
- ✅ **Division / sqrt / rsqrt / trig** — SFU single-ops (`0x2f/0xaf`) + the `0x29` NR estimate seed
  (EXP-0026), with the honest large-arg range-reduction caveat. Emittable.
- ✅ **A textured, interpolated, blended triangle** — VDM draw record, USC **sized-block** shader
  binding (EXP-0024, the exact thing GAP-01 called "opaque" three times), PPP length-word header +
  enable bits, depth/stencil/raster packets, **programmable blend via `tile_read`+ALU+`frag_color_pack`+
  `frag_color_store`** (the epilog ABI GAP-01 said was missing), `iter` varying interpolation
  (EXP-0029), the 14-byte texture bundle, the **32-byte texture / 8-byte sampler / inline-VA buffer
  descriptors + the self-contained 31/60-format code table**, Morton twiddle + mip + compression wiring,
  and the fixed-32×32 tile model. Emittable.
- ✅ **RT / mesh / matrix / function-pointers / dylibs** — all now have decoded AGX encodings
  (`0xcf`, `rt_intersect`/`rt_as_load`/`0x5f`, mesh store-emit + `0x70000600` dispatch, `0f 05…8f`
  call/return, `visible_function_table`), not just MSL provocation snippets.

The `isa/README.md` "treat the DB as source of truth (in `tools/`)" structural failure GAP-01 flagged is
**fixed**: `isa/encoding-tables.md` (75 descriptors, byte-0 length rule, per-field bit tables + enums) and
`descriptors/format-table.md` are self-contained and "defer to no experiment." `agx3.xml` renders the same
DB in Mesa's schema for the disassembler. The authoritative encoding now lives **inside `docs/`**.

---

## Per-subsystem PASS / GAP

| # | Subsystem | Verdict | One-line basis |
|---|-----------|---------|----------------|
| 1 | Shader compiler (emit AGX from NIR) | **PASS** | Self-contained encoding tables; length rule; 96-GPR model + spill; async = HW interlock (no scoreboard); CF/calls/frames; memory/atomics; textures; subgroups; transcendental SFU + NR; SR enum + preload ABI + in-shader vertex fetch. Residue = ⏳ operand sub-fields (below), all with principal encoding decoded. |
| 2 | Command stream (compute + draw) | **PASS** | CDM record + tgmem field; USC sized-block bind (no `shaderVA>>N` for draws); PPP length-word header + per-packet enables; indirect/occlusion/timestamp; geometry-output (viewports/clip/restart/A2C); mesh submission; tile-shader inline dispatch. |
| 3 | State (depth/stencil/blend/raster) | **PASS** | Depth/stencil/raster packets HW-decoded (compare/op enums, native depth clamp [11:10]); blend is programmable — the **FS-epilog ABI is now emittable** (`tile_read`/`frag_color_pack`/`frag_color_store`, dual-source, logic-op via `0x0b` LUT). |
| 4 | Descriptors (tex/sampler/buffer + PBE/storage + bindless) | **PASS** | 32B texture, 8B sampler, inline-VA buffer, PBE/storage-image descriptor, sparse-tier flag, bindless sampler-heap; **format-table.md** is complete (31 + 60 formats, swizzle/numtype/sizeclass, BC/ASTC codes, D/S). Untested codes are explicitly bounded (§8). |
| 5 | Tiling (twiddle/mip/compression/MSAA) | **PASS** | Morton twiddle (2D + 3D/array/cube/MSAA all HW-validated EXP-0028), BC/ASTC over block coords, mip packing, compression aux flags/placement/size. Codec bytes honestly opaque with disable-fallback. |
| 6 | TBDR / pipeline | **PASS** | Fixed 32×32 tile, imageblock budget, MSAA count + sample-major interleave, memoryless, load/render/store attachment segments + PBE store descriptor, tiler param buffer. Sample positions/ZLS correctly routed to §6 kernel contract. |
| 7 | Kernel interface | **PASS** | Submission ring+doorbell, sel-9 map→VA, VA-space layout, the G-11 ZLS/sample-position contradiction reconciled (userspace *computes*, kernel *writes register* as submit param), `drm_asahi_cmd_render/compute` field map, firmware-managed item list. Clear enough for the two teams to agree. |
| 8 | Cross-cutting (native-vs-emulate, magic values) | **PASS (with doc-consistency flags)** | `capability-matrix.md` is the decided native/emulate/kernel matrix; most magic values explained (config `0x0088_00XX` = stage×0x0c register word, `0x61c4/0x61f2/0x6404/0x6432` draw opcodes, tgmem `(b<<2)|0x80`, occlusion mode/offset). **SUPERSEDED by EXP-0048:** this review's classification of single-RT value `0x6f` as firmware-owned/kernel-managed was unsupported; its meaning and ownership remain UNKNOWN. `num_gps/num_frags/is_sksm` remain separate firmware-facing unknowns. **See doc-consistency defects D1–D4.** |

No subsystem is a blocking GAP. Every "PARTIAL/GAP" in GAP-01's table has moved to PASS.

---

## Prioritized remaining-gap list

Format: **item — the specific missing fact — severity — classification.** No item is a blocker; the
first cluster is the residue a diligent implementer will actually trip on, ordered by how load-bearing it
is.

### A. Acceptable residue — ⏳ operand sub-fields (principal encoding decoded; fallback documented)

1. **Memory-op index-register bit position — CONTRADICTORY between two docs, and unpinned.**
   **Severity: MEDIUM-HIGH (load-bearing on *every* load/store), acceptable-but-close-this.**
   `isa/README.md` (EXP-0012 table) puts the index GPR in `device_load`/`device_store` **byte+1 upper
   bits** ("higher bits = index GPR", `✅ space / ⏳ reg`). `isa/encoding-tables.md` instead marks
   **byte+6 `addr_lo` / byte+7 `addr_hi` as `raw/unmapped`** and lists byte+1 as `space` only. So the two
   `docs/` files disagree about *where* the index register lives, and neither pins its exact bit layout.
   The addressing *model* (element addressing, `base_slot`@+4, `count`@+5, `elem_size`@+12, dst@+8) is
   fully decoded and HW-validated, and the register convention is `(reg<<1)|size` — so a driver can emit
   by templating the captured 14-byte instruction and varying the known fields. But this is the closest
   thing to a genuine hole in a core path; it deserves one splice experiment to reconcile the two tables.

2. **Float ALU GPR-vs-uniform per-source mode bits — byte-diff-inferred, not splice-validated.**
   Severity: MEDIUM. `isa/README.md` "Machine model": float `0x09` uniform-select ≈ byte+2 bit4 / byte+5
   bit1 (`⏳`). Reading a scalar `constant T&` uniform in a float op depends on these. Integer
   uniform-select (`0x9f` byte+5 bit4 / byte+6) *is* HW-diffed. Fallback (porting §8): the family works;
   validate before shipping heavy uniform-register use.

3. **Integer source-register exact widths / bitwise-shift-compare operand sub-fields — `⏳`.**
   Severity: LOW-MEDIUM. `iadd2`/`imad` srcA/srcB packed in the `b7:b8:b9` tail ("exact widths a
   follow-up"); `ilogic`/`ishift`/`icmpsel` operand bytes typed `raw/unmapped`. dst (`b3`) and the ops
   themselves are HW-validated. Fallback documented.

4. **Texture array/3D/cube/MSAA slice/face/sample/ref index-operand bit positions — `⏳`.**
   Severity: LOW-MEDIUM. `tex_sample` result/coord/tex_slot/samp_slot/variant/mode are decoded; the
   *extra* index operand (slice/face/z/sample/compare-ref) selected via op+3 is byte-diff-inferred.
   Single-resource 2D shaders always encode slot 0 → a first driver runs; multi-dim/bindless needs the
   sub-field validated (porting §8).

5. **`pixel_order` (raster-order-group) acquire/release + tilebuffer fence bytes — inferred.**
   Severity: LOW. `07 14/04 54 … 06 00` acquire/release is byte-diff-inferred, not splice-proven; the
   fragment tilebuffer-ordering analogue to the compute barrier was explicitly a follow-up. ROG-using
   fragment shaders and interlocked blends rely on it.

6. **Control-flow exec-mask sub-ops beyond `jump`/`call`/`ret`/reconverge — partial.**
   Severity: LOW. `0x0f` push(`05`)/else(`01`)/pop-reconverge(`06`) are *noted* but not fully bit-decoded
   (jump/call/ret/indirect-call are). The corpus tokenizes CF to 0 leftover bytes, so structured control
   flow is emittable via predication + backward jump + reconverge; the `else`/`break`/`continue` mask
   sub-op fields would want a decode pass before a complex CF codegen relies on exact bits.

7. **Register-amount shifts + spill/fill scratch-base binding — thin.**
   Severity: LOW. Register-operand shifts/rotates are "multi-instruction lowerings" (structure named, not
   the exact `0x2b/0x3b` prep-stage bits). Spill above 96 GPRs uses ordinary `0x67/0xe7` to scratch, but
   the **scratch-base→shader binding** is only declared kernel-managed (G1-d: userspace writes scratch
   *size* in `__GPU_METADATA`, kernel allocates) — the addressing slot the spill load/store uses isn't
   spelled out. A first driver can cap RA at 96 GPRs (no spill) to sidestep it.

### B. Acceptable residue — honestly-opaque / firmware-owned by design

8. **Lossless-compression 8×4-block codec + state-byte meanings — opaque.** `tiling/README.md` §4.5.
   Correctly documented as HW-internal with a **disable-fallback** (make the image ShaderWrite-eligible /
   clear the flags → plain twiddle). Never blocks correctness. **Acceptable residue.**

9. **RT BVH build + node format — firmware-owned.** `isa` EXP-0023 / `kernel-interface.md` §4.1.
   Userspace supplies vertices + build descriptor + 8-byte AS VA; the *traversal* ISA is native. The
   opaque built structure is by design. **Acceptable residue.**

10. **Kernel/firmware-managed submit items** — sample positions (`ppp_multisamplectl`), ZLS/depth store
    (`zls_ctrl`, depth/stencil buffers), partial-render trigger + `partial_bg/eot`, the CPU→GPU doorbell,
    the graphics **code-BO→firmware shader-entry handoff**, sparse tile residency (page table), the
    timestamp sample-buffer address, mesh **UVB** sizing, and per-core scratch geometry. All are
    enumerated with the userspace-computes/firmware-writes split (`kernel-interface.md` §4/§6.1/§6.2).
    **Acceptable residue** (the boundary is clear enough for the two teams to agree).

### C. Acceptable residue — Metal-unreachable / untested (documented fallback = emulate or probe)

11. **A18-native status of GS / tessellation / transform feedback — assumed emulate, not re-probed.**
    Severity: MEDIUM (scoping, not correctness). `capability-matrix.md` §2/§4 honestly marks these
    "emulate by the M1/M2 default, not independently re-probed on A18." A first driver keeps the compute-
    emulation stack; a probe could retire it (mesh is the plausible native amplification path). Fallback
    documented (porting §8). **Acceptable scoping residue.**

12. **Metal-can't-provoke features:** cull distance, polygon-**point** fill, a *custom* primitive-restart
    index, anisotropy >16×, wide/smooth lines, conditional render. Spare HW encodings sometimes exist
    (restart field @VDM+0x68, 3-bit aniso→128×) but Metal drives the fixed value; classified emulate/probe
    with fallback. **Acceptable residue.**

13. **Untested descriptor codes:** texture types 1DArray(=1)/CubeArray(=7)/2DMSArray(=8) confirmed 4-bit
    but the array/MS-array type codes partly extrapolated; address modes 4/6/7, swizzle 6/7, border code
    3, 16-bit snorm variants, XR/YUV/video formats untested. Boundary is explicitly enumerated in
    `format-table.md` §8. **Acceptable residue** (an implementer knows exactly what is validated).

### D. Doc-consistency defects (NOT gaps in coverage — the fact exists elsewhere in `docs/` — but they
   undercut trust and a final deliverable should reconcile them)

- **D1 — `capability-matrix.md` §4 is stale vs the rest of `docs/`.** It lists **mesh/task shaders** as
  "❓ Unknown … *no AGX encoding exists in `docs/`*" (line 91) — contradicted by `isa/README.md` EXP-0030
  (mesh store-emit + `0x43`), `cmdstream/README.md` EXP-0030 (mesh `0x70000600` submission), and
  `porting-guide.md` §7 which correctly calls mesh **native**. It likewise marks **BC/3D/cube/array/MSAA
  tiling** "❓ Unknown/inferred" (line 95) — contradicted by `tiling/README.md` §1.5/§1.6 (HW-validated,
  EXP-0028). The matrix's summary counts (§5) are also internally out of step with
  `capability-completeness.md`'s later re-syncs. Fix: move mesh + BC/3D/array/MSAA out of "Unknown" into
  "Native," refresh counts.

- **D2 — `cmdstream/README.md` "Open items" (lines 234-239) are resolved earlier in the same file.**
  It still lists "USC bind-pair grammar + graphics shader-entry word" and "per-packet bit decode" as open,
  though EXP-0024 (lines 123-148) and EXP-G1a (lines 208-232) resolve them; line 86's "not yet decoded"
  note is superseded by the line-220 clarification but left in place. Fix: delete/annotate the stale
  open-items list so a reader doesn't conclude draw-shader binding is unsolved (GAP-01's #3 blocker).

- **D3 — `ROADMAP.md` status board lags the work.** Phase 1 "Opcode map"/"Per-instruction spec" and
  Phase 2 VDM/CDM/USC rows still show ◐/☐ and a "64 GPR / register model preliminary" note, though the
  encoding tables, cmdstream, and 96-GPR model are complete. Cosmetic, but a reviewer reading top-down
  gets a misleadingly unfinished picture. The completeness counts are cited three different ways
  (110/160/184 native) across the file.

- **D4 — `isa/README.md` memory table vs `encoding-tables.md`** disagree on the index-register byte (see
  A1). This is both a residue item *and* a consistency defect.

None of D1–D4 removes a fact from `docs/`; they are contradictions/staleness that an adversarial reader
notices and that slightly erode confidence in the "everything is here and settled" claim.

---

## Count of acceptable-residue items

**13 residue items** (A1–A7 operand/ABI sub-fields; B8–B10 opaque/firmware-owned clusters; C11–C13
untested/unreachable clusters), **0 blocking gaps**, plus **4 doc-consistency defects** (D1–D4) to
reconcile. Of the 13, the only one that is load-bearing on a core path is **A1 (memory-op index
register)**, and even that is emittable-by-template today; the rest are multi-dim/bindless/heavy-uniform
refinements, honestly-opaque hardware, or firmware-boundary items.

---

## What is genuinely solid (keep it)

- The whole ISA is now self-contained in `docs/`: `encoding-tables.md` (75 descriptors, byte-0 length
  rule, per-field bit tables + enums) + `agx3.xml` (Mesa schema) + `format-table.md`. The GAP-01
  "authoritative encoding lives in `tools/`" structural failure is gone.
- The five GAP-01 CRITICAL blockers are all closed with HW-validated experiments: async model
  (register interlock, no scoreboard), transcendentals (SFU + NR), graphics shader binding (sized-block
  walk), fragment interpolation (`iter`), SR enum + preload ABI + in-shader vertex fetch.
- The programmable-blend **epilog ABI** (GAP-01 #12) is emittable without transcribing Apple's
  microprogram: `tile_read` (dst color) → float ALU → `frag_color_pack` (format convert) →
  `frag_color_store` (RT index), dual-source + logic-op via the `0x0b` 16-func LUT.
- `kernel-interface.md` reconciles the G-11 ZLS/sample-position contradiction cleanly (compute-value vs
  write-register split as a submit param) and gives a concrete `drm_asahi_cmd_render/compute` field map —
  enough for the userspace and kernel teams to agree.
- The honesty discipline (⏳ markers, negative results in `hypotheses.md`, explicit "untested boundary" in
  `format-table.md` §8, opaque-codec disable-fallback) is exactly right and makes the residue auditable.

## Bottom line

**PASS.** A dedicated implementer restricted to `docs/` could stand up an A18 Pro Mesa userspace driver —
compute kernels and textured/blended draws through to mesh/RT/matrix — without peeking at Apple's stack,
`gpu_knowledge/`, `mesa/`'s M1/M2 code, or the out-of-bounds `tools/`/`experiments/` sources. The gate's
bar ("everything it needs is present and it would not need anything else") is met to the level of
**acceptable residue only**. Recommended before declaring the deliverable final (none block the gate):
(1) reconcile A1/D4 (the memory-op index-register byte) with one splice experiment; (2) fix the D1–D3
stale rows so the docs stop contradicting themselves; (3) optionally close the A2/A4/A5 sub-fields before
shipping bindless/multi-dim/heavy-uniform code paths.

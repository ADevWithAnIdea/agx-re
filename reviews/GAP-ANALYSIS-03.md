# GAP-ANALYSIS-03 — Final adversarial acceptance review (objective 1)

**Reviewer role:** final objective-1 gate. Premise: implement Apple A18 Pro (SoC **T8140**, GPU
**G17P**, Metal feature-family **Apple9**) support in Mesa's `asahi` **userspace** driver **from
scratch**, using **only `docs/`** as the source of A18-specific hardware truth. `mesa/src/asahi` was
consulted only for the *shape* of what a userspace driver must produce; `gpu_knowledge/`,
`experiments/*`, `tools/` source, and `PROVENANCE.md` were **not** used as A18 truth (a fact living
only there = a gap). Read-only; no device; no commit.

**Date:** 2026-07-07. **Scope reviewed (every file in `docs/`):** `hardware-overview.md`,
`isa/README.md` (724 lines), `isa/encoding-tables.md` (1263 lines, 82 descriptors), `isa/agx3.xml`
(125 `<ins>` / 12 groups / 34 enums), `isa/msl-feature-map.md`, `cmdstream/README.md`,
`descriptors/README.md` + `descriptors/format-table.md`, `tiling/README.md`, `pipeline/README.md`,
`kernel-interface.md`, `capability-matrix.md`, `capability-completeness.md` (562 lines / 214 rows),
`hypotheses.md`, `porting-guide.md`, `ROADMAP.md`. Prior reviews `GAP-ANALYSIS-01.md` (FAIL) and
`GAP-ANALYSIS-02.md` (PASS + 4 doc-consistency defects D1–D4) were read and judged against the
**current** docs, which have since been through a full red-team hardening pass (RT-1a … RT-11,
RT-ISA-FIX).

---

## Overall verdict: **PASS — a from-scratch A18 Pro Mesa userspace is implementable from `docs/` alone.**

Every blocking gap the earlier reviews named is closed, every core path is emittable, and — the
specific charge of this final gate — **the red-team corrections are internally consistent across all
spec docs, with no remaining split-brain.** I verified this both by reading each corrected fact in
context and by grepping the whole tree for the *old* (pre-correction) wording; the stale wording
survives only in `ROADMAP.md` (an internal progress tracker, not a spec doc). The four
GAP-ANALYSIS-02 doc-consistency defects (D1–D4) are all reconciled. The remaining deficit is
**acceptable residue only**: ⏳ operand sub-fields whose principal encoding is HW-validated,
two honestly-opaque hardware formats (compression block codec, RT BVH node format), a
cleanly-delineated firmware/kernel-managed set, and an explicitly-bounded list of Metal-unreachable /
untested codes. There are a **small number of cosmetic polish items** (below) that do not block
implementation.

### The red-team corrections — verified applied AND consistent everywhere

| Corrected fact | Where it must agree | Consistency check |
|---|---|---|
| **Memory index reg = byte+5** (was byte+1-upper / byte+6/+7) | `isa/README.md` EXP-0012 table; `encoding-tables.md` `device_load`/`device_store`; length-rule appendix | ✅ All three say **+5 = index GPR, +6 INERT, +1 = address space**. The GAP-02 **D4/A1 contradiction is GONE** — `encoding-tables.md` no longer marks +6/+7 as `addr_lo/addr_hi`. Grep for stale "higher bits = index" finds only the *"NOT the index register"* correction note. |
| **iadd2 polarity: `0x9f`=ADD / `0x1f`=SUB** (was inverted) | `isa/README.md` "Integer ALU"; `encoding-tables.md` `iadd2` (`addsub` enum) + length-rule note | ✅ Consistent; grep for `0x1f`=add finds zero stale hits. |
| **Tiled-Morton `cols = ceil(W/T)` + mult-of-T padding** (was `nextpow2`) | `tiling/README.md` §1.1/§1.4/§1.5/§3; `capability-completeness.md` §14 | ✅ Consistent, with worked non-pow2 examples (1920→cols 30, 384²→0x90000) in both. |
| **14-bit texture dims** (was 12-bit) | `descriptors/README.md`; `format-table.md` §5 | ✅ Both say width/height −1 are 14-bit (max 16384), RT-3-cited. |
| **Sampler arg-buffer stride 0x20** (was /8) | `cmdstream/README.md` EXP-G1a | ✅ `num_samplers=(term−samp_ptr)/0x20`; `/8` survives only in `ROADMAP.md`. *(See minor item M1 on the 8-byte-descriptor vs 0x20-stride wording.)* |
| **Indexed-VDM record shift (instanceCount → +0x78, u32 opcode 0x61f4)** | `cmdstream/README.md` EXP-0014/RT-2a; `capability-completeness.md` §10 | ✅ Consistent. |
| **Sample positions = userspace-emittable @+0x40** (was firmware-managed) | `pipeline/README.md`; `kernel-interface.md` §4.2/§5/§6; `capability-matrix.md` §1/§3/§5; `capability-completeness.md` §12/§17; `porting-guide.md` §5 | ✅ **Six docs agree**; grep for a stale "sample position … kernel/firmware-managed" that is *not* an RT-4 correction note returns nothing. This was the worst split-brain in the RT-8 audit — it is fully propagated. |
| **Native tessellation** (was compute-emulated) | `cmdstream/README.md` EXP-O2H; `capability-matrix.md` §1/§2/§4/§5; `capability-completeness.md` §9/§16; `porting-guide.md` §7/§8 | ✅ Consistent; the compute path is uniformly demoted to an "OPTIONAL fallback." |
| **ballot/shuffle decode** (`simd_ballot` byte+1 low-nib 7; `simd_shuffle` byte+2=0x54 gate) | `isa/README.md` EXP-0018 + RT-ISA-FIX; `encoding-tables.md` `simd_ballot`/`simd_shuffle` | ✅ Consistent, incl. the honest "high-nibble ballot form is a decode label, not a settable field." |
| **`0x0f` exec-mask family fully decoded** (jump/jump_cond/if_push/pop_reconverge/call_indirect/mask_op) | `isa/README.md` "Control flow" + EXP-0035; `encoding-tables.md` + length-rule appendix | ✅ Consistent; all six sub-ops carry a length rule and descriptor. |

**The staged-descriptor merge actually happened.** The `isa/README.md` prose repeatedly says
descriptors are "staged in `experiments/…/new_descriptors.json` for merge," which reads as if the
authoritative tables were incomplete. They are **not**: `encoding-tables.md` (82 descriptors,
2026-07-07) and `agx3.xml` (125 `<ins>`) contain every one of them — `get_sr`, `iadd2` (corrected
polarity), `half_alu`, `bf_alu`, `ibitcount`, `carry_gen`, `half_pack`, `matrix_mac`, `rt_intersect`,
`vary_store`, `frag_color_store`, `tex_sample`, `simd_ballot`, `simd_shuffle`, `call_indirect`,
`if_push`, `jump_cond` all verified present. The "staged for merge" language is stale but the tables
are complete (minor item M3).

---

## Per-subsystem PASS / GAP

| # | Subsystem | Verdict | Basis (can a from-scratch implementer emit it from `docs/` alone?) |
|---|---|---|---|
| 1 | **Compiler / ISA** (emit AGX machine code) | **PASS** | `encoding-tables.md` + `agx3.xml` are self-contained: byte-0 length rule, per-field bit tables, enums. 96-GPR model + 2 halves/GPR + spill + occupancy tier (`isa` EXP-0020). **Async = HW register interlock, NO scoreboard** (EXP-0025) — the single most load-bearing compiler fact, splice-proven. CF incl. the fully-decoded `0x0f` exec-mask family + call/ret/frame ABI. Memory byte+5 index + element addressing. Textures (sample/gather/read/write/compare/LOD + variants). Atomics (native single-RMW). Subgroup/quad incl. ballot/shuffle/prefix-scan. Matrix `0xcf` (full operand decode). RT `rt_intersect`/`rt_as_load`/`0x5f`. Transcendentals (SFU + NR seed) with the large-arg range-reduction caveat. SR enum + in-shader vertex fetch. Residue = ⏳ operand sub-fields (§A), all with the principal encoding HW-validated. |
| 2 | **Command stream** (compute + draw) | **PASS** | CDM 0x2c record (+ threadgroup-mem field `(bytes<<2)\|0x80`); VDM draw record incl. corrected indexed shift; **USC sized-block shader bind + no `shaderVA>>N` for draws** (EXP-0024); PPP length-word header + per-packet enable bits; indirect draw/dispatch (+ the required grid-multiply); occlusion/timestamp; geometry-output (viewports/clip mask/restart/A2C); mesh `0x70000600`; **native tessellation** patch-dispatch `0x40`; tile-shader inline dispatch; USC/resource bind grammar (EXP-G1a) incl. sampler stride 0x20. |
| 3 | **State** (depth/stencil/raster/blend) | **PASS** | Depth `+0x38`/stencil `+0x3c`/raster `+0x70` packets HW-decoded (compare 0–7, stencil-op 0–7, native depth clamp [11:10], cull/winding/line-fill/bias). Blend is **programmable** — the FS-epilog ABI is emittable (`tile_read`→ALU→`frag_color_pack`→`frag_color_store`, dual-source + 16-func logic-op LUT). |
| 4 | **Descriptors** (tex/sampler/buffer + PBE/bindless) | **PASS** | 32B texture (14-bit dims, `VA>>4`, swizzle/numtype/sizeclass), 8B sampler (all 8 compare funcs → native PCF, 3-preset border), inline-VA buffer, distinct 32B PBE/storage descriptor + per-access-qualifier binding (EXP-G1b), sparse-tier flag, bindless sampler-heap `gpuResourceID`. `format-table.md` is self-contained (31 + 60 formats, BC/ASTC sizeclasses, XR, D/S-reuse-color). Untested boundary explicitly enumerated (§8). |
| 5 | **Tiling** (twiddle/mip/compression/MSAA) | **PASS** | Tiled-Morton `cols=ceil(W/T)` + mult-of-T padding (RT-9), T=64(bpp≤4)/32(bpp≥8); mip packing; 3D=stacked planes, array/cube=linear-stacked planes, MSAA sample-major, BC/ASTC over block coords; linear stride; compression aux flags/placement/size. Codec bytes honestly opaque with disable-fallback. |
| 6 | **TBDR / pipeline** | **PASS** | Fixed 32×32 tile (do-not-shrink), imageblock/tile-memory records, MSAA count + **sample positions userspace @+0x40**, memoryless, 3-segment (load/render/store) attachment + STORE-is-a-PBE-descriptor field map (EXP-G1b). ZLS/partial-render correctly routed to §6 kernel contract. |
| 7 | **Kernel interface** | **PASS** | Shared-mem ring + doorbell, sel-9 map→VA, VA-space layout, the G-11 ZLS/sample-position contradiction reconciled (userspace *computes*, kernel *writes register* as a submit param; sample positions struck out and moved to userspace), `drm_asahi_cmd_render/compute` field map, firmware-managed item list. Boundary unambiguous enough for the two teams to agree. |
| 8 | **Cross-cutting** (native-vs-emulate, magic values) | **PASS** | `capability-matrix.md` (15 native / 6 emulate / 4 kernel) and `capability-completeness.md` (189 native / 11 emulate / 5 kernel / 9 NYC = 214) are mutually consistent and reconciled with the RT corrections. Most magic values explained (config `0x0088_00XX`, VDM opcodes, `(b<<2)\|0x80`, occlusion mode/offset). Firmware-owned residuals (`0x6f` store-program, `num_gps/num_frags/is_sksm`) correctly parked as kernel items. |

**No subsystem is a blocking GAP.** Every "PARTIAL/GAP" in GAP-01 and every doc-consistency defect
in GAP-02 has moved to PASS/resolved.

### GAP-02 defects D1–D4 — all reconciled

- **D1 (capability-matrix stale "mesh/BC/3D Unknown")** → **FIXED.** `capability-matrix.md` §4 now lists
  **Mesh = ✅ Native (EXP-0030)** and **BC/ASTC/3D/cube/array/MSAA = ✅ Native (EXP-0028)**; §5 counts refreshed.
- **D2 (cmdstream stale "USC bind grammar open")** → **FIXED.** The "Open items" list is annotated
  "Graphics (RESOLVED: USC grammar + shader-entry)"; the sized-block bind and USC grammar are decoded in-file.
- **D3 (ROADMAP status board lags)** → **PARTIALLY remaining, non-blocking** (see minor item M2). ROADMAP
  is an internal tracker, not a spec doc; its staleness removes **no** A18 fact from the spec.
- **D4 (memory index-register byte disagreement)** → **FIXED** (the headline RT-1a-FIX; see table above).

---

## Acceptable-residue inventory (0 blocking gaps)

Format: item — the specific unclosed fact — classification. None blocks a core path.

### A. ⏳ operand sub-fields (principal encoding HW-validated; documented fallback)

1. **Integer source-register exact widths + bitwise/shift/compare operand sub-fields** — `iadd2`/`imad`
   srcA/srcB packed in the `b7:b8:b9` tail; `ilogic`/`ishift`/`icmpsel` operand bytes typed
   `raw/unmapped`. dst (`b3`) and the ops themselves are HW-validated. *(Acceptable — template from a
   captured instruction.)*
2. **Texture array/3D/cube/MSAA extra-index operand bit positions** (slice/face/z/sample/compare-ref via
   op+3) — byte-diff-inferred; single-resource 2D always encodes slot 0 so a first driver runs.
3. **`pixel_order` (ROG) acquire/release + tilebuffer fence bytes** — byte-diff-inferred (`Provenance:
   inferred` in the table). ROG-using fragment shaders / interlocked blends need it validated.
4. **`rt_intersect` operand sub-fields** — honestly marked ⏳/INERT: RT-5/RT-10 showed the documented
   sub-fields (byte+2 mode, byte+4 AS-type `0x8b`/`0x1b`/`0xbb`) are splice-inert on the single-primitive
   path; the primitive-vs-instance dispatch is **structural** (kernel shape), not a spliceable field. The
   *op* is HW-validated load-bearing; the earlier "EXP-O2C 0x8b→0x1b end-to-end" over-claim is explicitly
   retracted. *(This is exemplary honesty, not a gap.)*
5. **`mask_op` (`0x0f` byte+1=0x04) + `frame`/`spill_frame_marker` semantics** — 1-occurrence inferred /
   "exact role a follow-up." CF still tokenizes to 0 leftover; a first driver emits structured CF via
   predication + jump + reconverge.
6. **Float GPR-vs-uniform per-source mode** — note: this is *no longer* ⏳; RT-7 upgraded it to
   **HW-validated** (both `falu2` srcB and `falu2_uni` srcA encodings documented). Listed only to record
   that the GAP-02 A2 residue item is now closed.

### B. Honestly-opaque / firmware-owned by design

7. **Lossless-compression 8×4-block codec + state-byte meanings** — HW-internal, with a documented
   disable-fallback (ShaderWrite-eligible / clear flags → plain twiddle). Never blocks correctness.
8. **RT BVH build + node format** — firmware-owned; userspace supplies vertices + build descriptor + an
   8-byte AS VA; the *traversal* ISA is native.

### C. Kernel/firmware-managed (enumerated with the userspace-computes/firmware-writes split)

9. ZLS/depth store (`zls_ctrl`), partial-render trigger (`partial_bg/eot`), graphics shader-entry bind
   (code-BO base out-of-band), sparse tile residency (page table), timestamp sample-buffer address, mesh
   **UVB** sizing, per-core scratch geometry + doorbell. All in `kernel-interface.md` §4/§6.2 with an
   unambiguous emit-vs-submit-vs-firmware table.

### D. Metal-unreachable / untested (documented fallback = emulate or probe)

10. GS / transform feedback (assume compute-emulate, not re-probed on A18); cull distance; polygon-point
    fill; custom primitive-restart index; anisotropy >16×; wide/smooth lines; conditional render.
11. Untested descriptor codes: texture types 1DArray(=1)/CubeArray(=7)/2DMSArray(=8) partly extrapolated;
    address modes 4/6/7, swizzle 6/7, border code 3, 16-bit snorm variants, XR/YUV/video formats — the
    exact validated boundary is enumerated in `format-table.md` §8.

**Residue count: 11 clusters, 0 blocking gaps** (A1–A5 operand sub-fields with A6 noting one *closed*;
B7–B8 opaque; C9 firmware; D10–D11 unreachable/untested).

---

## Minor consistency / polish items (do not block the gate; would tighten the deliverable)

- **M1 — sampler "8-byte descriptor" vs arg-buffer "0x20-stride" not reconciled in one sentence.**
  `descriptors/README.md` / `format-table.md` / `porting-guide.md` specify the sampler descriptor as an
  **8-byte** bitfield (fully bit-mapped, HW-validated); `cmdstream/README.md` EXP-G1a specifies the
  contiguous arg-buffer sampler array at **0x20 stride** (`num_samplers=(term−samp_ptr)/0x20`). Both are
  emittable and neither is wrong (the 8-byte bitfield sits at offset 0 of a 0x20-byte slot, matching the
  texture-descriptor stride), but no single sentence says so — a careful reader momentarily wonders
  whether the descriptor is 8 or 32 bytes. One clause ("the 8-byte sampler bitfield occupies a 0x20-byte
  slot in the argument-buffer array") would close it. **Non-blocking.**
- **M2 — `ROADMAP.md` still reads as in-progress.** Phase-1/2 rows show ◐/☐, and the RED-TEAM tracker
  marks several clusters ◐ ("needs a fresh clean 2nd pass", "needs 2nd pass"). This is the residual half
  of GAP-02's D3. ROADMAP is an internal tracker, not an A18-fact source, so it removes nothing from the
  spec — but a reviewer skimming top-down gets a misleadingly unfinished impression, and the tracker's own
  ◐ marks admit a couple of red-team clusters received only one adversarial pass (RT-cmdstream, RT-ISA-1
  before RT-1b). The spec docs themselves present those areas as settled.
- **M3 — `isa/README.md` "staged for merge" language is stale.** The prose says descriptors are staged in
  `experiments/…/new_descriptors.json` "for merge," but the merge is done (`encoding-tables.md` 82 desc /
  `agx3.xml` 125 ins verified complete). Reads as if the tables were incomplete when they are not.
- **M4 — `cmdstream/README.md` "Open items" line still lists "decode `+0x00` config/register word"** as
  open, though it is decoded earlier in the same file (bit19 always set + bit23 occupancy tier). Cosmetic.
- **M5 — code-BO sized-block *header* layout is structural, not exhaustively bit-mapped.** The USC
  sized-block walk gives offsets (`+0x00=0x340`, `+0x340`=FS size, `+0x500`=VS size, order
  `[helpers][FS][VS]`) but not a full bit table of the size-header word. Because the shader-entry handoff
  is firmware-managed (§4.5) this is acceptable residue rather than a blocker, but it is one of the thinner
  spots — flagged for honesty.

None of M1–M5 removes a fact needed to implement a core path.

---

## What is genuinely solid (keep it)

- **The ISA is fully self-contained in `docs/`:** `encoding-tables.md` (byte-0 length rule + per-field bit
  tables + enums) + `agx3.xml` (Mesa GenXML schema, drop-in for `src/asahi/isa/`) + `format-table.md`. The
  GAP-01 "authoritative encoding lives in `tools/`" structural failure is gone.
- **The RT-8 systematic split-brain is fixed.** The two facts most prone to inconsistency after a
  correction — sample-positions (kernel→userspace) and tessellation (emulate→native) — are propagated to
  **every** derived doc (pipeline, kernel-interface, capability-matrix, capability-completeness,
  porting-guide), and the census counts (189/11/5/9) tie out across the summary table, per-section tallies,
  and the "Totals:" line.
- **Honesty discipline is exemplary:** ⏳ markers, retracted over-claims (`rt_intersect` AS-select), the
  64-bit-atomic correction (EXP-O2D corrects EXP-0018), the interpolated-not-measured occupancy-threshold
  caveat (RT-7), and explicit "untested boundary" enumerations make the residue auditable rather than
  hand-waved.
- **The `porting-guide.md` capstone** maps every Mesa `src/asahi` module to the owning `docs/` section and
  states the four framing deltas (new ISA, HW interlock not scoreboard, fixed 32×32 tile, programmable
  blend) — a from-scratch implementer has a navigable path from NIR to submit.

---

## Bottom line

**PASS.** A dedicated implementer restricted to `docs/` could stand up an A18 Pro Mesa userspace driver —
non-trivial compute kernels and textured/interpolated/blended draws through to indirect, geometry-output,
mesh, native tessellation, RT, matrix, and function-pointer/dylib paths — without peeking at Apple's
stack, `gpu_knowledge/`, `mesa/`'s M1/M2 code, or the out-of-bounds `tools/`/`experiments/` sources. The
gate's bar ("everything it needs is present and it would not need anything else") is met to the level of
**acceptable residue only** (11 residue clusters, **0 blocking gaps**). The red-team corrections are
**internally consistent with no remaining split-brain in the spec docs**; the only stale artifact is the
`ROADMAP.md` tracker. Recommended cosmetic polish before the deliverable is declared final (none block
the gate): reconcile the sampler 8-byte-vs-0x20-stride wording (M1), refresh the `ROADMAP.md` board and
the stale "staged-for-merge"/"open-item" notes (M2–M4), and optionally bit-map the code-BO block header
(M5).

# Addendum Triage — OpenGL 4.6 / WineD3D Compiler Questionnaire

Date: 2026-08-28
Author: triage pass (non-device, read-only)
Scope: `APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md` (560 lines, 2026-08-27) cross-referenced against
`APPLE9_RE_IMPLEMENTATION_GAPS.md`, `docs/P0-P1-CLOSURE.md`, `PROVENANCE.md`, and the current
`experiments/` tree. No GPU work was run, no experiment was authored, and no file other than this
one was modified. `docs/`, `PROVENANCE.md`, and `APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md` are read-only
inputs here.

**Stale-filename note.** The addendum's own header (`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md:7`) refers
to `APPLE9_RE_INFORMATION_GAPS.md`. That file does not exist. `CLAUDE.md` and the gaps file's own
header record the actual history: the original file was `AGX_RE_INFORMATION_GAPS.md`, removed and
superseded by `APPLE9_RE_IMPLEMENTATION_GAPS.md` (`APPLE9_RE_IMPLEMENTATION_GAPS.md:3-9`). The
addendum's reference is therefore to a filename that never existed under that exact spelling; treat
every addendum cross-reference to "the primary questionnaire" as pointing at
`APPLE9_RE_IMPLEMENTATION_GAPS.md`. The addendum text is left unedited per instructions.

---

## 1. Complete item inventory

29 numbered items, all under the addendum's own stable IDs (`GL*-A*`). None are summarized away.

| ID | One-line question (addendum's own framing) | Line |
|---|---|---|
| GLIO-A01 | Exact hardware-validated limits of the vertex-output UVS scalar-slot namespace and the fragment coefficient/input-slot namespace, and first-over-limit behavior | 31 |
| GLIO-A02 | Complete `get_sr` operand and result encoding (dest bits, byte-2/3 suffix fields, width, Boolean rep, stage restrictions) | 45 |
| GLIO-A03 | Exact vertex ID / instance ID / base-vertex SR `0x88` / base-instance SR `0x8a` / draw-ID semantics for indexed/instanced/multidraw | 57 |
| GLIO-A04 | Fragment MSAA system-value ABI: sample ID (`0x97` path), sample position, input sample mask, coverage mask, helper status | 71 |
| GLIO-A05 | Exact compute grid-count system-value ABI (`load_num_workgroups`, SRs `0xa8`-`0xaa` + device load + divide) | 85 |
| GLIO-A06 | Finite ranges and overflow behavior of every shader system value exposed to the OpenGL compiler | 98 |
| GLFS-A01 | Exact instruction(s) that kill samples, submit surviving samples to depth/stencil, and finalize tilebuffer-output eligibility; target/live mask model | 125 |
| GLFS-A02 | Exact state transitions for discard, NIR demotion, and true invocation termination | 145 |
| GLFS-A03 | What `get_sr 0x84` (helper status) returns in every fragment execution state | 165 |
| GLFS-A04 | Incoming/current/shader-written sample-mask semantics and combination ordering | 179 |
| GLFS-A05 | Early/late depth-stencil test/update ordering relative to shader execution, demotion, mask output, tilebuffer output, queries, buffer/image effects | 199 |
| GLFS-A06 | Which operations automatically suppress helper/demoted-lane side effects vs. require explicit predication | 219 |
| GLFS-A07 | Sample-shading invocation and liveness model (invocation frequency vs. sample ID/coverage/helpers/demotion) | 236 |
| GLFS-A08 | Do the inferred `0x07` acquire/release forms implement OpenGL fragment-shader-interlock ordering for overlapping fragments? | 253 |
| GLCS-A01 | Complete compute system-value and launch ABI for OpenGL + generated geometry/tessellation helper kernels | 282 |
| GLCS-A02 | Threadgroup/shared-memory addressing (`0x1c` op) and finite allocation semantics (max bytes/workgroup, granularity) | 301 |
| GLPRE-A01 | Can the unchanged Asahi UAPI express a full GPU-driven compute-writes-geometry-and-indirect-draw chain with no CPU round trip? | 322 |
| GLPRE-A02 | Exact records/limits for a shader-produced (not CPU-created) indexed/non-indexed draw | 341 |
| GLPRE-A03 | Pre-raster special-output ABI: position, point size, clip/cull distances, layer, viewport index, primitive ID, edge flag | 360 |
| GLXFB-A01 | Are Apple9's memory/atomic/query/generated-draw primitives sufficient to implement OpenGL transform feedback via Mesa's software `poly` path? | 379 |
| GLIMG-A01 | Complete encoding/behavior of NIR image load/store/size/sample-count for every OpenGL image dimension and format class | 408 |
| GLIMG-A02 | Image selector/descriptor capacity for bindful/dynamic/non-uniform/bindless images, and atomic integration | 427 |
| GLTEX-A01 | Complete encoding/behavior of a dynamic texture bias operand and its interaction with sampler LOD state | 449 |
| GLTEX-A02 | Complete register ABI/encoding for explicit gradients (`txd`), especially cube/cube-array | 468 |
| GLTEX-A03 | Does implicit-LOD sample + `textureQueryLOD` implement exact OpenGL results in a real fragment shader? | 483 |
| GLTEX-A04 | Exact representation/interpretation of the extra coordinate/index for array/cube-array/MSAA forms, incl. float-layer conversion rule | 498 |
| GLTEX-A05 | Do native 1D / 1D-array descriptors work for every OpenGL operation without Mesa's 1D-to-2D lowering? | 513 |
| GLTEX-A06 | Are depth-compare and gather-compare forms executable/exact for 2D-array/cube/cube-array across implicit/explicit LOD, bias, gradient, offset? | 528 |
| GLTEX-A07 | Largest addressable texel buffer per texel size, and how that limit is represented/enforced | 543 |

Count check: GLIO (6) + GLFS (8) + GLCS (2) + GLPRE (3) + GLXFB (1) + GLIMG (2) + GLTEX (7) = **29**.

---

## 2. Cross-reference against existing evidence

Strict grading per dispatch: only promoted, non-quarantined evidence counts. The non-evidence set
(`EXP-0057/0061/0062/0064/0065/0068/0069/0071/0072/0073/0075/0077/0078/0080/0081`, plus `EXP-0086`
run02) was checked and **none of it is cited below** — confirmed by reading each experiment's
`QUARANTINE.md` (all present and dated 2026-08-20/27) and `EXP-0086/RESULTS.md`'s own "Evidence
status" section (run02 explicitly non-gating). A repo-wide grep for the addendum's own ID strings
(`GLIO|GLFS|GLCS|GLPRE|GLXFB|GLIMG|GLTEX`) across `docs/`, `PROVENANCE.md`, and the gaps file returns
**zero hits** — this triage is the first time these questions have been mapped to anything.

**Result: 0 items are ALREADY-ANSWERED to the addendum's own standard (exact width/range/boundary/
overflow behavior, hardware-validated). 17 are PARTIALLY-ANSWERED (a real, cited fact addresses part
of the question). 12 are OPEN (no cited fact addresses any part of it).** This matches the fact that
zero rows in `docs/P0-P1-CLOSURE.md` are `CLOSED` — nothing in this codebase is closed to that bar yet.

| ID | Status | What exists (file:line) / what's missing |
|---|---|---|
| GLIO-A01 | PARTIAL | UVS slot layout is DATA-TRACE structural: VS slots pos 0-3, `varying#k = 4+4k`, count field `0x58000+0x2c = 4+4·nvary` (`PROVENANCE.md` 2026-07-07 EXP-G1a row; `docs/cmdstream/README.md`). No exhaustion sweep (max slots to first failure), no smooth/flat/special-output differential consumption test, no producer-vs-consumer-limit distinction. |
| GLIO-A02 | PARTIAL | `get_sr` SR-number = byte1, splice-proven (`docs/isa/README.md:667-690`; `docs/isa/encoding-tables.md:517`, EXP-0031/RT-7). Dest-register range, byte-2/3 suffix fields, Boolean representation, and first-unencodable-destination are not swept. |
| GLIO-A03 | OPEN | `base_vertex`/`base_instance` are explicitly marked **"(inferred)"** at `docs/isa/README.md:676` — never independently splice-validated with distinguishable nonzero values. `vertex_id`/`instance_id` SR codes are known (`0xdd`/`0xd8`) but raw-vs-base-inclusive behavior, signed base-vertex addition, non-indexed-draw values, and draw-ID source are untested. |
| GLIO-A04 | OPEN | The addendum itself states the `0x97` sample-ID path is "currently unresolved" (line 76). `docs/isa/README.md:681` only records "`sample_id` folds to 0 on a 1-sample target" — a degenerate, non-MSAA observation. Programmable sample *positions* are known userspace-emittable (RT-4, `docs/pipeline/README.md:33`), but that is pipeline input, not the per-invocation SR readback the item asks for. |
| GLIO-A05 | PARTIAL | RT-7 established `threadgroups_per_grid` (`get_sr 0xa8/a9/aa`) is a build-and-divide sequence, not a direct SR (`docs/isa/README.md:682-690`). Asymmetric/non-power-of-two grids, largest legal dims, and malformed-indirect-record behavior are untested. |
| GLIO-A06 | OPEN, non-independent | This is the finite-resource mandate (`APPLE9_RE_IMPLEMENTATION_GAPS.md:85-142`) applied per system value; it has no independent hardware content of its own and closes only as a byproduct of GLIO-A03/A04/A05 and friends closing with a finite-resource-table row each. |
| GLFS-A01 | OPEN | No decode anywhere of a kill/target-mask/live-mask instruction. Grepped `docs/isa/README.md`, `docs/isa/encoding-tables.md` for coverage/kill-adjacent terms — nothing beyond the color-store/discard notes already covered under GLFS-A06. |
| GLFS-A02 | OPEN | Directly restates `OPT-09` (`APPLE9_RE_IMPLEMENTATION_GAPS.md:501-505`), which carries **no** "Answered" annotation — still open. The addendum states this explicitly: "must close the broad `OPT-09` question with executable behavior" (line 161-162). |
| GLFS-A03 | PARTIAL | `get_sr` SR `0x84` = `simd_is_helper_thread`, identified via EXP-O2D (`PROVENANCE.md` 2026-07-07 "O2-D/O2-E" row; `docs/isa/encoding-tables.md:1723`). No before/after-transition read-back matrix (demotion, per-sample kill, final-sample kill) exists. |
| GLFS-A04 | OPEN | No shader-writable sample-mask instruction or incoming/current-mask field is documented anywhere in `docs/isa/`. (An M5-only "native... sample_mask" row exists in `docs/capability-matrix-m5.md:398`, but M5 evidence is explicitly non-promotable to A18/M4 per `CLAUDE.md`.) |
| GLFS-A05 | OPEN | Depth/stencil packet fields exist structurally (`PROVENANCE.md` 2026-07-07 EXP-0019 row: FRONT/BACK depth/stencil words, compare tables), but the *ordering* question — when tests fire relative to shader execution/demotion/mask-output/tilebuffer-output — is untested. |
| GLFS-A06 | OPEN | Addendum explicitly frames this as extending `FS-12` (line 234), which is unanswered in the primary list. `discard_fragment` suppresses the color store (`docs/isa/encoding-tables.md:1182`, "discard_fragment suppresses the store") — that is the only side effect characterized; buffer/image/atomic/depth/stencil/sample-mask suppression is untested. |
| GLFS-A07 | OPEN | No per-sample invocation-frequency model documented. |
| GLFS-A08 | PARTIAL | `pixel_order` = `0x07` fence family, acquire (`07 14 54 50 06 00`) / release (`07 04 54 d0 06 00`) forms located, explicitly flagged "⏳ byte-diff inferred" (`docs/isa/README.md:664`; also `docs/capability-completeness.md:345`, "native-decoded (partial)"). `docs/P0-P1-CLOSURE.md` P1.4 row states `ATOM-07..11` (the fence/barrier family this item depends on) are "explicitly DEFERRED" as of EXP-0085 (`PROVENANCE.md` 2026-08-28 EXP-0085 row). No concurrent same-pixel/same-sample litmus test exists. |
| GLCS-A01 | PARTIAL | Local/global invocation ID, threadgroup position, and workgroup-size SRs are decoded (EXP-0031; `docs/isa/README.md:667-690`); general compute launch is broadly exercised across the M4 corpus (`EXP-M4-*`). Asymmetric/non-power-of-two boundary sweep and the root/parameter-table pointer ABI are not closed. |
| GLCS-A02 | PARTIAL | `tg_addr_compute` opcode structurally located: byte0`==0x1c`, byte+1`==0x02`, byte+2`==0x00`, 6 bytes (`docs/isa/encoding-tables.md:1335-1337`). Source/dest fields, byte-vs-element units, alignment, and unaligned/OOB access are not decoded. The 32 KiB `maxThreadgroupMemoryLength` cap is documented as an **imageblock/tile-SRAM budget, not a compute-shared-memory ceiling** (RT-4; `docs/pipeline/README.md:20-23`) — the addendum's specific ask (max bytes/workgroup for OpenGL `shared`, allocation granularity, static+dynamic combination) has no dedicated boundary test. |
| GLPRE-A01 | OPEN | No experiment demonstrates a full compute-writes-geometry/index/indirect-draw-record chain consumed by a following draw with no CPU round trip on the unchanged UAPI. The nearest building blocks (`DRV-CMD-01`/P0.5 and `DRV-INDIRECT-01`/P1.7) are themselves `OPEN` in `docs/P0-P1-CLOSURE.md`. |
| GLPRE-A02 | PARTIAL | EXP-0053 (`PROVENANCE.md` 2026-08-17 row, commit `e31dfb46`) establishes indirect-argument timing, ICB ranges, CPU-before-commit and prior-encoder **GPU-encoder** argument updates — but not records written by a **compute shader**, which is what this item asks for. `docs/P0-P1-CLOSURE.md` P1.7 explicitly still needs "writable device-generated command grammar" and "no private VDM/CDM/ICB grammar." |
| GLPRE-A03 | PARTIAL | EXP-O2A (`PROVENANCE.md` 2026-07-07 row) established the multi-viewport array (max 16, 0x18B/vp), PPP output-select clip-mask bits`[7:0]` (max 8), point-size enable bit 18, viewport-index enable bit 19 — DATA-TRACE structural, all at `docs/cmdstream/README.md`. Dynamically indexed clip/cull arrays, NaN/Inf/signed-zero positions, layer output, primitive-ID forwarding, and provoking-vertex interaction are untested. |
| GLXFB-A01 | OPEN | No experiment. This is explicitly the highest-order compositional item — it depends on `DRV-QUERY-01` (P1.6, OPEN — EXP-0052 only closes timestamp semantics, not primitives-generated/written counters), `DRV-MEM-01` (P1.4, OPEN), and `GLPRE-A01` (OPEN, above), all cited by the addendum itself (line 399). |
| GLIMG-A01 | PARTIAL | "Texture/image atomics are NATIVE" — `atomic_*` on `texture2d<uint,rw>` lowers to the memory-family device atomic `0x67` (`docs/isa/README.md:735-736`; `PROVENANCE.md` 2026-07-07 "Texture variants (backlog #14)" row, EXP-0034). Ordinary image load/store for 2D is covered by the same sample/read/write op family. The full dimension × format-class × instruction (load/store/size/sample-count) matrix — 1D, 1D-array, 3D, cube, cube-array, buffer, 2DMS, 2DMS-array — is not exhaustively executed. |
| GLIMG-A02 | OPEN | No descriptor-consumption-count or dynamic/non-uniform image-selection capacity test exists. `TEX-14..22` establish the analogous capacity pattern for *sampled* textures/samplers (selector counts, exhaustion behavior) but the addendum is explicit that the image/PBE-entry case is a distinct, unasked question. |
| GLTEX-A01 | PARTIAL | Bias selector located: sample op `op+2 == 0x07` (`docs/isa/README.md:464,732`; `docs/isa/encoding-tables.md:684`). Register packing, bit width, numeric type/precision, signed range, and the operand's interaction with sampler LOD-bias/clamp and base/max mip level are not tested. |
| GLTEX-A02 | PARTIAL | Gradient selector located: `op+2 == 0x04` = `sample_grad` (`docs/isa/encoding-tables.md:684`). No gradient register ABI (component order/count/width/precision), no independent-X/Y test, no cube-face-boundary comparison against a computed reference. |
| GLTEX-A03 | PARTIAL | LOD-query mode located: `op+6 == 0x20` (`docs/isa/README.md:478`; `docs/isa/encoding-tables.md`). Which result component is clamped vs. unclamped, and full implicit-LOD fragment-pipeline correctness (mip transitions, bias/clamp interaction, anisotropy, divergent control flow), are untested. |
| GLTEX-A04 | PARTIAL | The addendum's own text cites this as building on **EXP-0034**, which it says leaves the "extra-coordinate operand encoding noted as partial" (line 511). `TEX-13` (out-of-range integer layers) and `TEX-23` (object-size limit) are themselves `OPEN` in the primary list. Float-layer conversion rule (round-to-nearest vs. other, half-way/negative/signed-zero/Inf/NaN) is untested. |
| GLTEX-A05 | PARTIAL | 1D descriptor type `= 0` HW-validated (`docs/descriptors/format-table.md:21`; `docs/descriptors/README.md:18`, EXP-0028/EXP-0015). The full per-1D-descriptor operation matrix (implicit/bias/gradient/projective sample, fetch, size query, offsets, gather, shadow, image load/store, mipmapped minification) is not executed; the addendum itself accepts a negative answer as valid closure here. |
| GLTEX-A06 | PARTIAL — the strongest partial answer in the set | `sample_compare = op+2 bit5`, reference is a register operand, sampler `compareFunc` drives it; **all 8 compare functions HW-validated with native 2×2 hardware PCF** (`PROVENANCE.md` 2026-07-07 "Texture variants (backlog #14)" row, EXP-0034; `docs/isa/encoding-tables.md:693`). Cube/cube-array face-boundary and array-layer-boundary combinations with compare, and the border-color-emulation cross-check (compare vs. ordinary filtering selecting identical footprint/LOD), are untested. |
| GLTEX-A07 | PARTIAL | `texture_buffer<T>` is confirmed to ride the 1D-linear path as a **full 32-byte texture descriptor**, not a bare VA (`docs/descriptors/README.md:66-67`, EXP-M4-08 DESC-7). Exact max element count per texel size (1/2/4/8/12/16-byte), base-address/range alignment, and last-legal/one-past-end/overflow behavior are untested. |

Summary: **0 ALREADY-ANSWERED / 17 PARTIALLY-ANSWERED / 12 OPEN** (of 29 total).
OPEN set: GLIO-A03, GLIO-A04, GLIO-A06 (non-independent), GLFS-A01, GLFS-A02, GLFS-A04, GLFS-A05,
GLFS-A06, GLFS-A07, GLPRE-A01, GLXFB-A01, GLIMG-A02.

---

## 3. Deduplication against the primary list

The addendum's own text self-cites a primary-list ID for 15 of its 29 items (marked **explicit**
below — these are direct quotes/paraphrases from the addendum, not my inference). I identified a
further 6 thematic overlaps the addendum does not name itself (marked **inferred**). One item
(GLIO-A06) is not an independent hardware question at all — it is the finite-resource mandate
applied per system value, and closes only as those items close. That leaves **7 items with no
primary-list counterpart** — the highest-value new hardware-surface targets.

| Addendum ID | Primary-list counterpart(s) | Cite type |
|---|---|---|
| GLFS-A02 | `OPT-09` | explicit (line 161-162) |
| GLFS-A06 | `FS-12` | explicit (line 234) |
| GLCS-A02 | `ATOM-02`, `ATOM-09`, `DRV-ABI-01`, `DRV-RASTER-01` | explicit (line 319) |
| GLPRE-A01 | `DRV-CMD-01`, `DRV-MEM-01`, `DRV-INDIRECT-01` | explicit (line 338-339) |
| GLPRE-A02 | `DRV-INDIRECT-01` | explicit (line 358) |
| GLXFB-A01 | `DRV-QUERY-01`, `DRV-MEM-01`, `GLPRE-A01` | explicit (line 399) |
| GLIMG-A01 | `DRV-FMT-01`, `DRV-TEX-01`, `DRV-MEM-01`, `DRV-ROBUST-01`, `ATOM-*` | explicit (line 404-405) |
| GLIMG-A02 | `ATOM-01`..`ATOM-11` | explicit (line 443-444) |
| GLTEX-A01 | `TEX-05`, `TEX-24`, `TEX-27` | explicit (line 466) |
| GLTEX-A02 | `TEX-05` | explicit (line 481) |
| GLTEX-A03 | `FS-04`..`FS-06` | explicit (line 494) |
| GLTEX-A04 | `TEX-13`, `TEX-23` | explicit (line 509-511) |
| GLTEX-A05 | `DRV-TEX-01` / `TEX-*` (general) | explicit (line 524) |
| GLTEX-A06 | `TEX-11`, `DRV-TEX-01` | explicit (line 540) |
| GLTEX-A07 | `TEX-09`, `TEX-23` | explicit (line 559) |
| GLIO-A03 | `DRV-ABI-01` (VS fetch/base vertex-instance) | inferred |
| GLFS-A03 | `SIMD-07`, `GLIO-A02` | inferred |
| GLFS-A05 | `DRV-RASTER-01` ("early/late depth and stencil"), `FS-12` | inferred |
| GLFS-A07 | `DRV-RASTER-01` ("centroid/sample interpolation"), `SIMD-07` | inferred |
| GLPRE-A03 | `DRV-ABI-01` (FS/prolog live-outs), `GLIO-A01` | inferred |
| GLCS-A01 | `GLIO-A05` (addendum-internal, not primary-list) | inferred |
| GLIO-A06 | finite-resource mandate applied to every other GLIO/GLFS/GLCS item | not independent |

**Deduplication count: 20 of 29 addendum items (69%) collapse onto an existing, currently-`OPEN`
primary-list row** (15 explicit + 6 inferred, excluding GLIO-A06). Practically, this means one
experiment run against the *deeper* addendum framing typically also closes the corresponding
primary-list item — do not run two experiments for e.g. `OPT-09` and GLFS-A02, or `TEX-05` and
GLTEX-A01/A02.

**Genuinely NEW hardware surface (no primary-list counterpart) — 7 items, highest triage value:**

- **GLFS-A01** — the actual ISA instruction(s) implementing sample kill / depth-stencil submission /
  tilebuffer-eligibility. No opcode anywhere in `docs/isa/` is attributed to this role. This is the
  single most consequential unknown in the fragment cluster: without it, `OPT-09`/GLFS-A02 cannot be
  answered with instruction-level precision either.
- **GLFS-A04** — shader-writable/incoming/current sample-mask representation. No native counterpart
  documented for M4/A18 (an M5-only, non-promotable row exists — see §2).
- **GLIO-A01** — UVS/coefficient namespace capacity and exhaustion. Structural layout is known
  (EXP-G1a) but no primary-list item asks for the *capacity* number the finite-resource mandate
  requires.
- **GLIO-A02** — comprehensive `get_sr` operand/result encoding as its own object. `FS-01` only asks
  about two specific SRs (`0xa0`/`0xa1`); nothing in Part II asks for the general encoding.
- **GLIO-A04** — MSAA system-value ABI including the unresolved `0x97` sample-ID path. Nothing in
  Part II names this instruction.
- **GLIO-A05** — `load_num_workgroups` production sequence as its own question (RT-7 found the
  build-and-divide behavior as a side observation of a different investigation, not a targeted
  closure).
- **GLCS-A02**'s instruction-decode half — `tg_addr_compute` (`0x1c`) itself is undecoded at the
  operand level; only its existence and length are known. (Its capacity/ABI half dedups onto
  `ATOM-02`/`ATOM-09`/`DRV-ABI-01`, hence it is listed once under "explicit" above and once here for
  the opcode-decode residue.)

---

## 4. Prioritized experiment plan

Ordered by how much each bundle blocks a correctness-critical OpenGL 4.6 / WineD3D-class shader path
(basic discard/MSAA/vertex-ID correctness first; broad format/dimension coverage and the
highest-order compositional test last). Each bundle is sized to answer 2-6 related questions.

### Bundle A — Fragment sample/coverage/discard/demote/helper state machine
**Closes:** GLFS-A01, GLFS-A02, GLFS-A03, GLFS-A05, GLFS-A06, GLFS-A07 (6 items; also closes `OPT-09`
and deepens `FS-12`, `SIMD-07`, `DRV-RASTER-01`'s early/late-test clause).
**Probe shape:** OWN-SHADER differential compilation first (isolate the mask/kill instruction the way
EXP-0029/EXP-0034 isolated `frag_color_store`/`sample_compare`: compile matched MSL pairs that differ
only in discard/demote/sample-mask-write presence, byte-diff to find the candidate op), then
splice-and-observe on real M4 hardware with divergent 2×2 quads and MSAA 1×/2×/4× targets carrying
distinguishable per-lane/per-sample values, observed through color **and** depth/stencil/occlusion-
query/buffer-store side channels (per the addendum's own instruction not to use color absence alone).
**Needs the assembler:** yes, once a candidate op is structurally located — this is a splice+field-sweep
job in the EXP-0018/EXP-0025 tradition.
**Key falsifier:** a demoted-but-still-covered lane that continues producing an observable buffer/image
store, or a killed sample that still reaches depth/stencil, would refute the current "suppression is
inherent" assumption embedded in every existing `discard_fragment` note.
**Risk flagged:** `EXP-0086` (`experiments/EXP-0086-m4-register-liveness-bits/RESULTS.md`) showed a
same-instruction-family field in the float-ALU tail-modifier region (`opflags` bit 0) silently
corrupts a *later, separate* instruction's read with no fault. Any candidate field this bundle finds
near that byte region needs the same later-read falsification discipline EXP-0086 introduced, not just
a same-instruction splice check.
**Cost:** medium — several sub-experiments, but the splice-and-render methodology is mature and
fault-contained per the repo's operational history (no wedge in ~1500+ splice dispatches to date).
**Priority: 1** — this is the compiler's basic correctness contract for `discard`/alpha-test emulation
and any MSAA target; WineD3D-class translation depends on both routinely.

### Bundle B — Pixel/sample interlock and device-fence family
**Closes:** GLFS-A08 (1 addendum item) + `ATOM-07`, `ATOM-08`, `ATOM-09`, `ATOM-10`, `ATOM-11` (5
primary-list items explicitly marked deferred as of EXP-0085 — `docs/P0-P1-CLOSURE.md` P1.4 row).
**Probe shape:** own-shader splice of the already-located `0x07` acquire/release forms
(`docs/isa/README.md:664`), then concurrent litmus tests (same-pixel and same-sample read/modify/write
hazards across primitive submission order) — CODEX rule 5 requires concurrent litmus, not
single-thread functional output, for memory-model claims.
**Needs the assembler:** yes.
**Key falsifier:** an unordered-interlock construction that shows a data race under the acquire/release
forms would refute native fragment-shader-interlock support; a race-free result under a
deliberately-wrong-scope control would show the forms are stronger than claimed (a good problem, but
must be documented).
**Cost:** medium-expensive — concurrent litmus tests are inherently harder to make deterministic than
single-thread splices; budget for repeat runs.
**Priority: 2** — blocks `ARB_fragment_shader_interlock`/`GL_ARB_shader_image_load_store` correctness
for overlapping-primitive scenarios WineD3D translation can trigger (order-independent transparency,
etc.), and directly clears a P1.4 row already flagged as the priority-cluster's unfinished tail.

### Bundle C — Vertex/instance/draw-ID and general system-value ABI
**Closes:** GLIO-A02, GLIO-A03, GLIO-A05, GLIO-A06 (4 items; GLIO-A06 closes incrementally as a
byproduct).
**Probe shape:** own-shader splice sweep of the `get_sr` byte1 selector across its full legal range
and boundary destination registers (direct extension of EXP-0031's proven method); public-Metal
differential draws with distinguishable nonzero first-vertex/base-vertex/first-instance/instance-count/
draw-ID values (direct/indexed/instanced/multidraw), plus malformed/overflowing indirect dispatch
records for GLIO-A05.
**Needs the assembler:** yes, for the SR-selector/destination sweep.
**Key falsifier:** a nonzero base-vertex that fails to appear in `load_first_vertex`/`load_base_vertex`
distinctly, or a non-indexed draw that returns a nonzero raw vertex ID, would refute the current
"inferred" `0x88`/`0x8a` mapping outright.
**Cost:** cheap-medium — reuses a well-trodden splice methodology; the multidraw/indirect corner is the
only genuinely new harness work.
**Priority: 3** — `SV_VertexID`/`SV_InstanceID` and D3D base-vertex/base-instance semantics are used in
essentially every WineD3D-translated indexed/instanced draw; a wrong mapping here is a silent
correctness bug, not a crash.

### Bundle D — Texture bias/gradient/implicit-LOD ABI
**Closes:** GLTEX-A01, GLTEX-A02, GLTEX-A03 (3 items; also deepens `TEX-05`, `TEX-24`, `TEX-27`,
`FS-04`..`FS-06`).
**Probe shape:** own-shader differential compilation to isolate the bias-operand and gradient-operand
registers from the already-located `op+2` selectors (`0x07` bias, `0x04` grad); public-Metal behavioral
sweep of bias/gradient/LOD-query values including zero, boundary, very large magnitude, Inf, NaN; cube-
gradient face-boundary renders compared against an independently computed OpenGL reference.
**Needs the assembler:** partially — operand decode needs splice, boundary-value sweeps can stay
public-Metal behavioral.
**Key falsifier:** a cube-gradient result that diverges from the independently computed reference at a
face boundary or major-axis tie would settle whether Mesa's `lower_txd_cube_map` stays mandatory.
**Cost:** medium.
**Priority: 4** — textured-shader correctness is nearly as foundational as Bundle A/C; ranked after
them because the sample/gather/read path itself (without bias/gradient) is already well-decoded
(EXP-0016/EXP-0034), so this bundle is about ABI completeness, not baseline capability.

### Bundle E — Texture/image dimension-and-format operation matrix
**Closes:** GLTEX-A04, GLTEX-A05, GLTEX-A06, GLTEX-A07, GLIMG-A01, GLIMG-A02 (6 items; also deepens
`TEX-09`, `TEX-11`, `TEX-13`, `TEX-23`, `DRV-TEX-01`, `DRV-FMT-01`, `ATOM-*`).
**Probe shape:** public-Metal behavioral execution across an op × dimension × format-class matrix
(1D sample/gather/fetch/image ops; cube/cube-array shadow-compare at face and array-layer boundaries;
texel-buffer element-count sweep to the last-legal/first-overflow boundary; image-descriptor-capacity
census in the EXP-0083 base-slot-census tradition, adapted to image/PBE entries).
**Needs the assembler:** no for the behavioral sweep; yes if a capacity boundary needs raw
descriptor/selector injection (as EXP-0083 did for buffer base slots).
**Key falsifier:** the largest legal texel-buffer element count for a given texel size failing to
match `(range field max + 1) / texel_size`, or an image-selector count exceeding the direct texture
selector ceiling (`TEX-14`..`16`) without a documented bindless fallback, would be a genuine surprise
worth its own follow-up.
**Cost:** medium-expensive — largest bundle by matrix size, but reuses EXP-0034/EXP-M4-08/EXP-0083
groundwork directly rather than starting cold.
**Priority: 5** — broad format/dimension coverage matters for conformance but is lower-urgency than
Bundles A-D, which gate whether *any* textured, discarding, or indexed-draw shader is correct at all.

### Bundle F — Threadgroup addressing and compute launch capacity
**Closes:** GLCS-A01, GLCS-A02 (2 items).
**Probe shape:** splice-decode the `tg_addr_compute` (`0x1c`) operand fields using the exact
methodology EXP-0082 used for `device_load`/`device_store` operand fields (2000+-case splice matrix,
byte-identical two-run gate); public-Metal boundary sweep for max threadgroup-shared bytes, allocation
granularity, and static+dynamic combination.
**Needs the assembler:** yes.
**Key falsifier:** an unaligned or boundary-crossing threadgroup access that silently returns wrong
data (rather than the previously-established device-buffer align-down-and-zero-fill pattern) would mean
the two address spaces need separate compiler lowering rules.
**Cost:** cheap-medium — this is the single cheapest bundle because it reuses EXP-0082's proven
harness pattern almost verbatim.
**Priority: 6.**

### Bundle G — Varying/UVS export capacity and pre-raster special outputs
**Closes:** GLIO-A01, GLPRE-A03 (2 items; deepens `DRV-ABI-01`).
**Probe shape:** own-shader sweep of declared varying/clip-cull-distance count to find the first
rejection/aliasing point (extends EXP-G1a's already-located `0x58000+0x2c = 4+4·nvary` count field);
public-Metal boundary tests for NaN/Inf/signed-zero positions and point sizes, out-of-range layer/
viewport, and provoking-vertex modes.
**Needs the assembler:** no for the capacity sweep (pure MSL source-count variation); optional for
finer field-level validation.
**Cost:** cheap-medium.
**Priority: 7.**

### Bundle H — GPU-driven pre-raster chain: compute-generated draws
**Closes:** GLPRE-A01, GLPRE-A02 (2 items; deepens `DRV-CMD-01`, `DRV-MEM-01`, `DRV-INDIRECT-01`).
**Probe shape:** public-Metal ICB/indirect-argument-buffer chain in which a **compute shader**, not the
CPU or a prior encoder, writes the vertex/index/parameter/indirect-draw records a following draw
consumes; extends EXP-0053's harness by moving the write from GPU-encoder-updated to compute-kernel-
written.
**Needs the assembler:** no (stays on public Metal API surface per the addendum's own instruction not
to build native VDM/CDM grammar here).
**Cost:** expensive — multi-stage pipeline with barrier placement as an independent variable, higher
engineering complexity than any earlier bundle.
**Priority: 8** — necessary groundwork for the software `poly` (GS/tessellation/transform-feedback)
path, but gated behind Bundles A-D producing a correct base rendering pipeline first.

### Bundle I — Compute-emulated transform-feedback litmus
**Closes:** GLXFB-A01 (1 item; the addendum's own explicitly compositional item, self-citing
`DRV-QUERY-01`, `DRV-MEM-01`, `GLPRE-A01`).
**Probe shape:** minimal experimental programs (not production driver code, per the addendum's own
instruction) exercising streamout via global-memory writes, atomics for counters, and a generated
draw, into all four OpenGL transform-feedback buffers/streams.
**Needs the assembler:** no.
**Cost:** expensive — depends on Bundle H's chain and on `DRV-QUERY-01`'s primitives-generated/written
counters, neither of which exists yet.
**Priority: 9 — deliberately last.** Running this before Bundles B/H exist would just re-discover their
missing prerequisites piecemeal instead of composing already-validated pieces.

---

## 5. Honest blockers

- **A18/G17P hands-off status is not a blocker for any addendum item.** Every bundle above is fully
  testable on the local M4 per `CLAUDE.md`'s target discipline (M4 is Apple9-equal for every
  driver-emittable subsystem). The permanent caveat is that no finding here can be promoted to a
  G17P-specific fact without a recorded A18 validation or an explicit `INFERRED` label — this affects
  *labeling*, not *closability*.
- **GLIO-A06 cannot be closed as its own experiment.** It is the finite-resource mandate
  (`APPLE9_RE_IMPLEMENTATION_GAPS.md:85-142`) applied to every system value in GLIO-A01..A05 and the
  compute/fragment items; it needs a finite-resource-table row contributed by each of those bundles as
  they close, not a standalone probe.
- **GLFS-A01 (the kill/mask instruction) carries a real risk of a negative result.** If Apple's
  compiler never emits a shader pattern that isolates a dedicated kill/mask op — because, e.g.,
  coverage submission is folded into the existing `frag_color_store`/tile-access-setup (`0x87`) family
  rather than living in its own instruction — Bundle A may legitimately conclude "no separate
  instruction exists; the mechanism is implicit in ops already decoded." That is an acceptable,
  first-class negative result per `CLAUDE.md`'s methodology section, not a stalled experiment; flagging
  it here so the dispatch brief doesn't over-promise a new opcode.
- **Native geometry-shader/streamout hardware search is explicitly and correctly out of scope.** The
  addendum itself instructs "do NOT spend this assignment... searching for a native Apple9
  geometry-shader/transform-feedback implementation" (lines 275-277), consistent with the existing,
  already-closed finding that GS and transform feedback are Metal-unexposed and must be emulated
  (`docs/capability-matrix.md:58-59`). Bundles H/I correctly target only the compute/memory/
  indirect-draw primitives the software `poly` path depends on, not a native GS/TF search.
- **Vulkan-only exclusions are already respected.** The addendum's own preamble (lines 11-12) excludes
  YCbCr, sparse residency, `samples_identical`, and backend-only prefetch from this triage's scope; no
  bundle above reaches into `TEX-07`/`TEX-10`/`TEX-12`/sparse-residency territory, and none should.
- **Bundle B and Bundle H/I share a hard sequencing dependency, not a technical blocker.** Bundle B
  needs `ATOM-07`/`08` fence semantics decoded before GLFS-A08's interlock-scope claims can be
  falsified meaningfully; Bundle I needs Bundle H's chain and `DRV-QUERY-01`'s counter semantics before
  it can even be attempted without re-discovering both piecemeal. Neither is blocked by anything
  outside this repository's own open work — just sequence Bundle B before any interlock-adjacent claim
  and Bundle I strictly last.
- **No addendum item requires a Linux/UAPI runtime, which we do not have.** All 29 items are testable
  through the public Metal API surface plus our own splice tooling; none requires the kernel driver
  that is explicitly out of scope for this repository (`CLAUDE.md`: "We do NOT depend on a working
  kernel driver").



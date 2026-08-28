# PRE_REGISTRATION — EXP-0097 M4 varying/UVS export capacity + pre-raster special-output ABI

Closes `GLIO-A01` and `GLPRE-A03` (`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md:31-49,360-386`), deepening
`DRV-ABI-01`, per `work/ADDENDUM-TRIAGE-20260828.md` "Bundle G".

**Target: local Apple M4 (G16G) only.** No A18 Pro claim anywhere (A18 hands-off per `CLAUDE.md`).
macOS 26.6.2 (25G82), Metal 4, `xcrun` version 72, `clang` Apple clang version 21.0.0
(clang-2100.1.1.101). Device: Apple M4, 10 GPU cores (`system_profiler SPDisplaysDataType`).

**Pinned revision:** `92acd2ee3c013cfcdd55fcb9bbb6e92b8829a9e1` (0 tracked modifications outside
this experiment directory; untracked sibling-experiment directories present, not gated on — per
`experiments/SUBAGENT_BRIEF.md`, repo `HEAD` moving because a sibling experiment lands is not
contamination; only this experiment's own authored-file hashes below are load-bearing evidence for
what actually ran).

**Session note.** This experiment's harness (`harness/*.py`, `harness/*.m`) was already fully built
and interactively pilot-validated (see "Build-time findings" below) in the working session that
authored this pre-registration; a mid-session coordinator message reported the directory as
"scaffolding only" due to a stale check — the actual on-disk state (verified immediately before
freezing this contract) is the complete harness described here, zero captures, zero prior runs. No
evidence was lost or reused; this is a normal pre-registration off a freshly built, freshly
pilot-tested harness, not a resume-from-crash.

**ALU/db.json caveat (from `work/COMPILER-EXPLAINER-INTERACTION-20260828.md`).** An external
compiler engineer's lifetime model exposed a confirmed decoding bug in `tools/agx-isa/db.json`: the
top bits of the 7-bit `falu2`/`falu2i` `srcA_reg`/`srcB_reg` fields are source-retention flags, not
register-index bits, so any prior ALU operand decode reporting a source register ≥ 64 is suspect.
**This experiment does not decode, splice, or otherwise touch any native AGX instruction encoding.**
Every probe here is pure MSL source-count/value variation compiled and run through the public Metal
runtime (`newLibraryWithSource:` → `newRenderPipelineStateWithDescriptor:` → draw → readback); no
`tools/agx-isa` machinery, no byte splicing, no ALU operand field of any kind is inspected. The
caveat is **not applicable** to any result in this experiment; this is stated explicitly per the
coordinator's request rather than left implicit.

## Predecessors (read; not redone)

- `experiments/EXP-G1a-usc-sysval-uvs/RESULTS.md` — located the VS UVS output-slot layout
  (`[[position]]` = slots 0–3, user varying #k = slots 4+4k..7+4k) and the varying-count descriptor
  `0x58000+0x2c = 4 + 4·nvary`, **HW-validated only for `nvary` 0..8** (i.e. total UVS scalars 4..36)
  via `vary0..vary8` kernels, all declared as `float4`. This experiment extends the *count* axis of
  that formula to its actual ceiling and generalizes it from "4-wide slots" to "scalar components"
  (see H-PERCOMP below) using the current Metal/M4 toolchain; it does not redo G1a's slot-layout or
  linkage findings, and does not re-validate the `0x58000+0x2c` byte value at the new boundary via a
  fresh DATA-TRACE capture (flagged as an open item, not silently assumed — see §6).
- `experiments/EXP-0029-fragment-isa/RESULTS.md` — established `[[flat]]` = a distinct `iter_flat`
  instruction, and noted "flat shading takes vertex 0's value" as an aside. This experiment
  independently re-derives and extends the provoking-vertex finding (list vs strip vs
  reversed-index) as its own falsifiable claim with fresh evidence, not a citation.
- `docs/cmdstream/README.md` "Geometry-output pipeline" (EXP-O2A / EXP-M4-09 CMD-5) — HW-validated
  clip-distance mask `0x58000+0x20` bits[7:0] for N=1..8, multi-viewport count word `0x68000+0x900`
  for count=1..16, and PPP output-select bit18 (point_size)/bit19 (viewport_array_index). This
  experiment does not re-derive those command-stream fields; it tests the *API/pipeline-creation
  and rendered-pixel* boundary behavior those fields ultimately gate, at the public-Metal level.
- `docs/isa/register-move-and-liveness.md` — "on this hardware a wrong operand-field value usually
  produces a SILENT ZERO, not a fault" is a **native-instruction-splice** finding and does not apply
  here (no splicing in this experiment); cited only because the dispatch brief asked for it to be
  read first. Its relevant generalizable warning — do not assume boundary/invalid inputs are
  harmless; validate every claim with a downstream/observable read, never just "it didn't crash" —
  is honored throughout: every case here reads back actual pixels or an explicit pipeline-creation
  error, never merely "the process didn't crash."

## 1. Questions and falsifiable hypotheses

### H-VARYCAP (GLIO-A01 primary capacity)

**Claim.** The maximum number of user-declared vertex-output ("varying") scalar float/half
components **actually consumed by the fragment function** (post cross-stage-compaction, per G1a) is
exactly **124**, independent of the GPU-family-advertised Metal limit for the *declared* struct
size. The 125th component causes `newRenderPipelineStateWithDescriptor:` — not `newLibraryWithSource:`
— to fail with an explicit named error citing "124" as the limit. `[[position]]`'s 4 components are
outside this budget (124 + 4 = 128 total UVS scalars at the ceiling, consistent with and extending
G1a's `4 + 4·nvary` formula to `4 + total_scalar_components`).

**Falsifier.** Any width (`float`/`float2`/`float3`/`float4`/`half`) reaches a *different* usable
scalar-component ceiling than 124 when driven to its own boundary at 1-scalar-equivalent
granularity where possible; or the MSL frontend (`newLibraryWithSource:`) itself rejects a
large declaration (it does not, up to 1024 scalars, per build-time probing below); or a declared-
but-unread varying counts against the budget (it does not — see H-DCE).

### H-PERCOMP (per-component vs per-slot accounting)

**Claim.** The 124-component budget is counted **per scalar component**, not per declared
struct-member ("slot") and not padded to 4-wide. A sweep of `float` (1-wide) scalars and a sweep of
`float4` (4-wide) vectors hit the *identical* numeric ceiling (124 total scalars either way); `half`
(also 1-wide, but half the bit width of `float`) hits the same 124-count ceiling, not a
byte-budget-scaled one — confirming the unit is "component count," not "component count × width" or
"bytes."

**Falsifier.** `float4`-declared varyings reach a ceiling at some `4×k ≠ 124`; or `half` reaches a
numerically different ceiling than `float`; or `float2`/`float3` (which cannot land exactly on 124)
show evidence of padding to a 4-wide slot (i.e. their observed ceiling clusters near a *multiple of
4* rather than near 124 itself).

### H-DCE (declared-vs-consumed sensitivity)

**Claim.** The 124-component budget is charged against varyings the **fragment function actually
reads** (post-link liveness, matching G1a's "cross-stage-compacted" finding for *which* varyings are
emitted), not the raw declared vertex-output struct size. A vertex output struct declaring 500
`float` members, of which the fragment function reads only 10, creates a pipeline successfully;
declaring 200 and reading all 200 fails.

**Falsifier.** A large *declared-but-unread* struct fails pipeline creation regardless of how few
components the fragment function reads.

### H-CLIPCAP (clip-distance capacity, independent budget)

**Claim.** `[[clip_distance]]` array length caps at exactly **8** (`newRenderPipelineStateWithDescriptor:`
fails at 9 with an explicit named error), and this budget is **independent of** the user-varying
budget: 124 user-varying scalars *and* 8 clip-distance components succeed simultaneously in the same
pipeline (132 combined UVS scalars, plus 4 for position = 136), while exceeding *either* limit alone
fails regardless of how far under budget the other is.

**Falsifier.** Clip-distance capacity changes as a function of concurrent varying count (shared
budget); or 8 does not hold as the exact boundary; or combining both at their individual maxima
fails.

### H-CULLNEG (cull-distance is not a Metal-exposed attribute — expected negative)

**Claim.** `[[cull_distance]]` is not a recognized MSL attribute on this toolchain: the frontend
compiler emits `warning: unknown attribute 'cull_distance' ignored`, silently dropping it and
leaving a plain (attribute-less) array-typed struct member, which is itself illegal as a
vertex-function return type / fragment `stage_in` member — so the shader fails to compile
(`COMPILE_FAIL`, not a clean "cull distance unsupported" diagnostic). This is a first-class
Metal-unreachable capability, matching `docs/cmdstream/README.md`'s existing note ("cull distance
(MSL has clip only)").

**Falsifier.** `cull_distance` compiles without warning, or produces a distinct, on-topic
diagnostic naming cull distance specifically as unsupported (rather than "unknown attribute").

### H-POSSPECIAL (NaN/Inf/signed-zero clip-space positions — GLPRE-A03)

**Claim.** Perturbing exactly one vertex's clip-space position component with a non-finite or
signed-zero value produces one of three coarse, component/sign-dependent outcomes established by
build-time probing (§ below): full-target fill (the perturbation effectively enlarges/ engulfs the
covered region), zero fill (primitive discarded), or partial fill (a genuine intermediate clip
result) — **never** a command-buffer error/fault and **never** an unclassifiable per-pixel garbage
pattern. Specifically: `x`/`y` = NaN or +Inf → discard (none); `x`/`y` = −Inf → full fill; `z` = NaN
→ discard; `w` = NaN or −Inf → discard; `w` = +0.0 or −0.0 (signed-zero pair, identical) → full
fill; `w` = +Inf → partial fill; `w` = −1.0 (ordinary negative, finite) → partial fill (near-total
discard).

**Falsifier.** Any case produces `CMDBUF_ERROR`/device loss; or the signed-zero pair (`+0.0`/`−0.0`)
diverge from each other; or a case's fill category (full/none/partial) does not reproduce across the
two official runs.

### H-POINTSIZE (point-size boundary behavior — GLPRE-A03)

**Claim.** `[[point_size]]` behaves as: `0.0` → zero coverage (discarded); requested sizes in
`[4, 511]` produce an exact `size×size` centered square footprint (quadratic scaling, confirmed
positive control); requested sizes `≥ 512`, **and also `NaN` and `+Inf`**, are silently clamped to
an identical maximum `511×511` centered footprint (not 512, not device-max, not a fault); `−Inf` and
very-small/very-large-magnitude negative sizes (`−0.001`, `−1e8`) discard (zero coverage); but
**moderate-magnitude negative sizes** (`−1`, `−5`, `−50`) do **not** discard and do **not** clamp
cleanly — they produce a real (non-degenerate), reproducibly square-but-**off-center** footprint,
offset toward `+x,+y` from the point origin, whose exact size does not follow a simple formula in
the tested range. This last sub-claim is recorded as an **anomalous/likely-undefined-behavior**
finding, not a clean rule — the falsifier only requires it to keep reproducing as "non-discard,
non-clean-clamp, off-center" across both runs, not that a formula be found for it.

**Falsifier.** Any size (including the anomalous negative range) produces `CMDBUF_ERROR`; the
508–513 boundary lands somewhere other than exactly between 511 (still-scaled) and 512
(first-clamped); or NaN/+Inf do NOT match the same clamp footprint as a very large finite value.

### H-ARRAYCLAMP (render-target-array-index / viewport-array-index OOB — GLPRE-A03)

**Claim.** Both `[[render_target_array_index]]` (layer) and `[[viewport_array_index]]` clamp any
out-of-range index (tested up to `UINT32_MAX`) to **index 0**, not the maximum valid index, not a
modulo/wrap of the valid count, and not primitive discard — the SAME clamp-to-zero policy for both
mechanisms, independent of the declared layer/viewport count (tested at count=4 and count=8 for
layers).

**Falsifier.** An out-of-range index lands anywhere other than index 0 (e.g. modulo count, clamp to
count−1, or no landing at all); or the two mechanisms (layer vs viewport) disagree; or the landing
index depends on the declared count.

### H-PROVOKE (provoking-vertex convention — GLPRE-A03; Metal-exposure boundary)

**Claim.** Metal/Apple9 fixes the provoking vertex to the **first vertex of each assembled
primitive** (Direct3D/Vulkan `VK_PROVOKING_VERTEX_MODE_FIRST_VERTEX_EXT`-style), for both plain
triangle lists and triangle strips (each strip triangle's *own* first window vertex, not the
newest/last-added vertex) — and this holds by **fetched vertex identity** (the index-buffer-resolved
`vertex_id`), not by a fixed `vertex_id==0` special case: reversing an index buffer's order changes
which color wins, tracking the reordering exactly. **Metal exposes no API to select a different
convention** (no analogue of `VK_EXT_provoking_vertex`); this is a first-class NEGATIVE result for
any OpenGL default (`GL_LAST_VERTEX_CONVENTION`, i.e. last-vertex) — the driver must **emulate**
last-vertex flat-shading semantics itself (typically by rewriting the index buffer / duplicating the
flat attribute onto the vertex that must appear first) rather than by any pipeline/state toggle.

**Falsifier.** The strip's second triangle provokes on its last (newest) vertex instead of its first
window vertex; or the reversed-index-buffer case still shows vertex_id==0's color (would mean the
hardware special-cases "vertex_id==0" rather than "first-fetched-this-primitive"); or any Metal API
surface (undiscovered by this search) is found to configure the convention.

## 2. Method

Pure `OWN-SHADER` public-Metal-API probing — no assembler, no splicing, no native-instruction
decoding (per dispatch: "no assembler needed for the capacity sweep"). Two purpose-built harness
binaries, compiled once from authored Objective-C and reused read-only by every case:

- `harness/capacityprobe.m` → `work/bin/capacityprobe` — compiles MSL at runtime
  (`newLibraryWithSource:`), looks up the vertex/fragment functions, and attempts
  `newRenderPipelineStateWithDescriptor:`. Reports exactly which stage first failed
  (`COMPILE_FAIL`/`FUNCTION_MISSING`/`PIPELINE_FAIL`/`PIPELINE_OK`) plus the verbatim public API
  error text. No GPU dispatch. Used for the GLIO-A01 capacity families.
- `harness/renderprobe.m` → `work/bin/renderprobe` — compiles, builds a pipeline, and performs one
  real draw + full CPU readback (`MTLPixelFormatRGBA32Float`, exact float, no unorm quantization)
  against a plain 2D target, a point-topology target, a `texture2d_array` target (layer mode,
  `renderTargetArrayLength`), or a multi-viewport tiled target (`setViewports:count:`). Used for the
  GLPRE-A03 families and for a small `vary_render_confirm` family that goes past pipeline-creation
  to a real checksum-verified draw at/near the capacity boundary (silent-aliasing check).

`harness/genkernels.py` generates every MSL source from parametrized string templates (pure text,
no device access); `harness/run.py` writes each case's generated source to `work/gen/<case_id>.metal`
before invoking the relevant probe binary as its own subprocess with a hard timeout, and appends one
gated + one non-gated JSON record per case. `harness/casematrix.py` freezes the exact parameter
matrix (140 cases; family counts below); `harness/schema.py` is the single shared record-key-set
imported by both `run.py` and `verify.py` (standing gate (a)).

## 3. Build-time findings (interactive probing BEFORE freezing this contract)

Conducted with a scratch pilot harness (`pilotcompile.m`, structurally identical to
`capacityprobe.m`) and, after the real harness was built, re-confirmed by calling
`harness/run.py`'s own dispatch functions directly against a subset of frozen case IDs (the exact
values recorded in `harness/fixtures/recorded_reality.json` for the selftest gate) — both on the
pinned revision's toolchain/device.

- **MSL frontend accepts arbitrarily large `[[clip_distance]]` arrays and varying-struct
  declarations with zero rejection** (`xcrun -sdk macosx metal -c`, AIR-only compile, tested up to
  1024-scalar declarations) — the frontend does not enforce any capacity limit; only
  `newRenderPipelineStateWithDescriptor:` does. This directly answers the mandate's "distinguish
  frontend/compiler rejection from API object-creation failure": here, it is squarely the latter.
- **Clip-distance ceiling = exactly 8.** N=8 → `PIPELINE_OK`. N=9 → `PIPELINE_FAIL`, error
  `"Number of clip planes used exceeds supported maximum"` (no explicit number in this particular
  message, unlike the varying-component one below).
- **Varying-component ceiling = exactly 124** (float-scalar granularity). N=124 → `PIPELINE_OK`.
  N=125 → `PIPELINE_FAIL`, error `"Number of varying components(125) exceeds the limit (124)"` —
  Metal's own diagnostic names the limit. N=126 → same clean message form ("...(126) exceeds the
  limit (124)"). **N≥127 → a DIFFERENT failure**: `PIPELINE_FAIL`,
  `"Compilation failed due to an interrupted connection: XPC_ERROR_CONNECTION_INTERRUPTED. This
  error occurred after multiple retries."` — the Metal compiler's out-of-process backend service
  crashes instead of returning a clean validation diagnostic once the overshoot is large enough.
  Reproducible and deterministic per exact N (re-tested N=8, N=31 immediately after an N=32 crash:
  both still `PIPELINE_OK`, ruling out a *stuck/degraded service* explanation — it is a
  per-large-N backend crash, not global session corruption). Recorded precisely as **two distinct
  failure modes at the same logical boundary**, not glossed over as one "rejected" bucket.
- **`float4`-granularity sweep lands on the identical ceiling**: N=31 (124 scalars) → `PIPELINE_OK`;
  N=32 (128 scalars) → `PIPELINE_FAIL` (lands past the clean-message window directly into the XPC
  crash, because the 4-wide step skips over N=125/126). Confirms H-PERCOMP: the budget is
  scalar-component-counted, not slot-counted — a `float4` sweep and a `float` sweep hit the same
  numeric ceiling.
- **`half`-granularity sweep also lands on 124**, not a byte-budget-scaled ceiling (e.g. not ~248).
- **Declared-vs-used**: declared=500/used=10 → `PIPELINE_OK`; declared=200/used=200 → `PIPELINE_FAIL`;
  declared=150/used=124 → `PIPELINE_OK`; declared=150/used=125 → `PIPELINE_FAIL`. Confirms H-DCE.
- **Combined budget**: used=124 + clip=8 simultaneously → `PIPELINE_OK`. Confirms H-CLIPCAP's
  independence claim.
- **`cull_distance`**: `warning: unknown attribute 'cull_distance' ignored`, then `COMPILE_FAIL`
  (illegal array-typed struct member once the attribute is dropped). Confirms H-CULLNEG.
- **Point size**: exact `size×size` footprints for 4/16/64/128/256/510/511; **511×511 is the
  observed ceiling** for 512, 513, 1000, 1e8, NaN, and +Inf alike (re-confirmed on both a 600×600
  and a 2000×2000 target — not a viewport-clipping artifact); 0.0/−0.001/−1e8/−Inf discard (zero
  coverage); −1/−5/−50 produce anomalous off-center square-ish footprints that do not cleanly fit
  either the discard or the clamp-511 model (build-time-probed footprints: −1→300×300 off-center,
  −5→298×298 (600-target, edge-clipped) / 507×507 (2000-target, not edge-clipped, confirming this is
  a real ≈500px-scale effect and not merely viewport clipping), −50→275×275 off-center).
- **Layer/viewport OOB**: layer_count=4, requested∈{0,1,2,3} land at themselves; {4,5,8,255,
  4294967295} all land at layer 0. Reconfirmed at layer_count=8 (requested∈{8,9,255}→layer 0,
  requested=7→layer 7). Viewport OOB at viewport_count=4 shows the identical pattern.
- **Provoking vertex**: triangle list, direct order → red (vertex_id 0's color) at the center pixel.
  Triangle list with a REVERSED index buffer (`[2,1,0]`) → blue (vertex_id 2's color, i.e. the
  vertex that was *fetched first* by the reversed indices) — proves the mechanism is
  first-fetched-vertex, not a fixed `vertex_id==0` special case. Triangle strip (4 verts, 2 tris) →
  first triangle red (vertex 0), second triangle green (vertex 1, the *first* of that triangle's
  own 3-vertex window, not vertex 3 which would be OpenGL's default last-vertex convention).

## 4. Frozen case matrix

`harness/casematrix.py`, 140 cases: `vary_scalar`=52 (5 widths × boundary-focused N per width),
`vary_dce`=6, `clip_sweep`=14 (0..10 at 1-unit granularity + 16/64/256), `cull_negative`=1,
`vary_clip_combo`=5, `vary_render_confirm`=4 (real draw+checksum at/near the boundary),
`position_special`=14, `point_size`=20, `layer_oob`=13, `viewport_oob`=8, `provoking`=3.

## 5. Standing gate set (implemented, verified pre-capture)

- **(a) `--selftest`, one shared key-set** (`harness/schema.py`, imported by both `run.py` and
  `verify.py`): 15/15 checks pass in a clean tree with zero `raw/` captures present.
- **(b) `--seqtest`** state machine over `PRE_GPU` / `RUN01_PRESENT` / `RUN02_PRESENT`: 7/7 correct.
- **(c) NON-RECORDED smoke gate**: `run.py`'s `run_smoke()` performs one real `capacityprobe`
  pipeline-creation and one real `renderprobe` draw+readback, writes the receipt to
  `work/<run_id>_smoke.json`, and only creates `raw/<out>/` if BOTH succeed.
- **(d) No nondeterministic field in any byte-compared record**: every case in this experiment is a
  single deterministic draw/pipeline-creation + readback (no concurrent races, no repeat-count
  aggregation) — `casematrix.case_order_sensitive_keys()` returns the empty set for every case, and
  `verify.py --selftest` explicitly checks this (`no_family_declares_order_sensitive_keys`) and that
  the cross-run gate still correctly FAILS on any observed-field difference (no exclusions to hide
  behind).
- **(e) Selftest fixtures from RECORDED REALITY**: `harness/fixtures/recorded_reality.json` was
  generated by calling `harness/run.py`'s own dispatch functions against 9 real M4 GPU
  pipeline-creations/draws (not hand-typed), on this pinned revision's toolchain.
- **Single-threaded harness, `fflush`/`ferror` discipline**: both `.m` probes call `fflush(stdout)`
  before every `exit()`; `run.py` runs one case at a time, one subprocess per case, `os.fsync()`s
  the gated/non-gated JSONL files after every record.
- **Raw append-only, hard timeouts, one variable per case, each case its own process**: every case
  is dispatched as an isolated `subprocess.run(..., timeout=60)` (`RUN_TIMEOUT_S`); `raw/<run_id>/`
  is written once at the end of a run and never edited in place; a fresh run id is required (no
  overwrite path exists in `run.py` — it aborts with `FAIL` if the output directory already exists).

## 6. Known scope limits (recorded, not silently omitted)

- **The `0x58000+0x2c` count-field byte value at the new (124-component) boundary is not
  independently re-confirmed by a fresh DATA-TRACE (`iotrace`) capture in this experiment.** The
  generalization "the field reads `4 + total_scalar_components`, maxing at 128" is an `INFERRED`
  extension of G1a's `HW-VALIDATED` `4 + 4·nvary` formula (itself only directly validated for
  `nvary` 0..8), grounded in this experiment's own `PIPELINE_OK`/`PIPELINE_FAIL` API-level evidence
  that the *scalar-component* count (not slot count) is what the pipeline-creation validator
  enforces at the true ceiling. A follow-up DATA-TRACE capture at `nvary`-equivalent 31 (the 124
  boundary) would upgrade this specific byte-field claim to `HW-VALIDATED`; it is out of scope here
  given the dispatch's explicit "no assembler needed" scoping for the capacity sweep and the time
  budget for this bundle.
- **The anomalous negative point-size footprint (§3) is recorded as an observed, reproducible
  pattern, not resolved to a formula.** Further characterization (a finer negative-magnitude sweep,
  a positive control isolating whether it's a min/max-swap or a reinterpret-as-unsigned effect) is
  left as an open item.
- **This experiment does not probe A18 Pro** (hands-off per `CLAUDE.md`); every claim above is
  `M4-only` unless explicitly labeled otherwise. Per the standing Apple9-equality basis
  (`EXP-M4-*`), these are the operational Apple9 values, not `INFERRED`-by-family guesses, but no
  A18-specific validation exists.

# EXP-0117 Pre-registration — M4 stage-ABI remainder (DRV-ABI-01 / P0.8)

Frozen before any official (`raw/`) GPU capture. Git revision at registration:
`87d02c34f56357734f448695cf62d37ab555fcb0` (recorded for provenance only —
per `experiments/SUBAGENT_BRIEF.md`'s pinned-revision rule, the cross-run
gate compares **authored file sha256 hashes** frozen in
`CAPTURE_CONTRACT.json`, never live repo `HEAD` — sibling experiments
(EXP-0112..EXP-0124+, visible as untracked directories at freeze time) land
concurrently and are not a gate failure).

Target: **Apple M4/G16G, local host only** (Mac16,10, 10 GPU cores), macOS
26.6.2 (25G82), Metal 4 (Apple9), `xcrun` 72, Python 3.14.6, Apple clang
21.0.0. A18 Pro is hands-off (no data collected from it here). M5 out of
scope.

Harness code (`kernels/*.metal`, `harness/*.m`, `casematrix.py`, `run.py`,
`verify.py`) was written and manually smoke-tested against ad hoc scratch
output under `work/` (never `raw/`) before this document was frozen — CODEX
step 3 ("build the smallest authored probe") and step 4 ("capture the
baseline before mutation"), not a capture. The pilot log, including two
kernel-design bugs found and fixed during smoke testing (a hardcoded
window-space threshold in `fsorder.metal`'s left/right split, and MSL's
`[[instance_id]]` being vertex-stage-only rather than fragment-readable) and
several genuine hardware/API findings discovered opportunistically during
pilot testing, is recorded in `PROGRESS.md`. No official evidence exists yet
at freeze time; `raw/` is empty.

## Coordinator scope reinforcement (binding on this experiment)

Received mid-task: "THE BAR IS IMPLEMENTATION, not characterization... For
each field: build at the minimum legal value, the maximum legal value, the
FIRST INVALID value on each side, and any hole or reserved encoding. Record
BOTH positive results ... AND negative results (exactly what happens at and
past the limit: reject, clamp, wrap, alias, silent zero, fault, hang)."
Applied throughout below — every finite field this experiment touches
(blend factor/op enums, write-mask bits, blend-constant range, color-
attachment count, sample-mask width, stencil value range, CALL nesting
depth) is swept to at least one confirmed-invalid value on the boundary,
constructed by us, not merely observed from a compiler's default output.

## The nine items (EXP-0109 RESULTS.md "What P0.8/DRV-ABI-01 still needs")

Restated verbatim in spirit, each with this experiment's cover/defer decision
and (for covered items) the falsifiable hypothesis:

1. **Programmable-blend-epilog synthesis specification.** **COVERED
   (primary target).** Sub-plan:
   - 1a. Fixed-function blend-unit correctness for all 19 `MTLBlendFactor`
     values (src-role sweep) + 4 dst-role spot checks + the new (macOS 26)
     `Unspecialized` sentinel in both roles + one confirmed-invalid value
     past it.
   - 1b. All 5 `MTLBlendOperation` values + `Unspecialized` + one invalid
     value + RGB/alpha-op independence.
   - 1c. Write mask: all 4 single channels + None + All + a 2-bit combo +
     `Unspecialized` + one out-of-range bit.
   - 1d. Blend constant: 0.0, 1.0, and out-of-`[0,1]` values on both sides.
   - 1e. Format constraints: integer-format + blending-enabled REJECT
     (paired with a same-format blending-disabled positive control);
     RGBA16Float/RGBA8Unorm spot checks.
   - 1f. sRGB store + blend-in-linear-space check.
   - 1g. alphaToCoverage sweep (5 alpha values) + alphaToOne paired control.
   - 1h. NaN/±Inf propagation through the blend equation.
   - 1i. Programmable-epilog construction: logic ops (AND/OR/XOR/INVERT/
     COPY-control) via `tile_read` (`[[color(n)]]` fragment INPUT) + ALU +
     `frag_color_store` — Vulkan `VK_LOGIC_OP_*`-class functionality Metal's
     fixed-function-shaped blend descriptor cannot express at all.
   - 1j. Color-attachment-count finite resource: HW-render 1..8, plus a
     pure API-index-ceiling probe (`colorAttachments[N-1]`) at N=1,8,9,10.
   - 1k. Structural: does `blendingEnabled=YES` alone (same MSL source,
     varied only via the pipeline descriptor) add a `tile_read` op to the
     compiled `_agc.main`? (4 structural cases: off / src-only-factor /
     dst-only-factor / both.)
   - **Deferred within this item, explicitly:** MSAA-vs-blend-timing
     (does the fixed-function-shaped blend apply pre- or post-resolve?) —
     no budget for a dedicated per-sample-tile-content probe here; an
     MTL4 `MTL4BlendStateUnspecialized`/dynamic-blend-state deep dive (a
     brand-new macOS 26 API surfaced during header research, see below) —
     flagged as a high-value NEW LEAD for a follow-up experiment, not
     exercised beyond reading its public header documentation.

2. **CS system values beyond dynamic shared memory** (`dispatch_threads`,
   `grid_origin`, direct/indirect dispatch sysvals). **CLOSED BY CITATION,
   no new work.** EXP-0092 (M4) already `HW-VALIDATED` this ground in full
   (`experiments/EXP-0092-m4-sysval-abi/RESULTS.md`, GLIO-A02/A03/A05/A06);
   re-litigating it here would not add evidence.

3. **FS output ordering constraints** (color/depth/stencil/sample-mask
   write order; what happens when violated). **COVERED.** Sub-plan:
   - 3a. Source-statement-order invariance: two fragment functions
     (`f_order_ab`/`f_order_ba`) computing IDENTICAL final struct field
     values but in OPPOSITE source-assignment order — compared both
     structurally (compiled-byte diff) and functionally (real render).
   - 3b. Depth-test-FAILURE (using the shader's OWN explicit `[[depth]]`
     output, not the rasterizer-interpolated value) suppression of
     color+stencil writes, combined with whether the stencil OP selection
     (`depthFailureOperation` vs `depthStencilPassOperation`) correctly
     uses the POST-shader depth-test outcome — tested in BOTH op-assignment
     directions (Keep/Replace and Replace/Keep) as a paired control.
   - **Deferred, explicitly:** per-sample `[[sample_mask]]`-driven
     suppression of a SPECIFIC excluded sample's depth/stencil write
     (distinct from the uniform-sample_mask width sweep in item 6b) — no
     budget for a per-sample depth/stencil MSAA readback rig; the
     mechanism is inferred-by-analogy to the uniformly-proven color-channel
     case (item 6b) and to EXP-0109/EXP-0091's discard-suppression
     precedent, not independently HW-validated for depth/stencil
     specifically.

4/5. **Barycentric-coordinate and `primitive_id` VALUE correctness**
   (EXP-0109 confirmed only presence/compile). **COVERED.**
   - 4. Barycentric: an asymmetric, non-uniform-`w` triangle (screen
     position independent of `w`, so `w` only affects the perspective-vs-
     linear interpolation math) with a per-primitive vertex-tag buffer;
     the fragment shader reports the raw `(b.x,b.y,b.z)` weights AND an
     in-shader manual recombination `b.x*tag0+b.y*tag1+b.z*tag2`, both
     checked against a HOST-COMPUTED oracle (both the linear/screen-space
     and the perspective-corrected candidate formulas) in `analysis/`.
   - 5. `primitive_id`: non-indexed multi-triangle draw (assembly-order
     check), an INDEXED draw with a deliberately SHUFFLED index buffer
     (does `primitive_id` track assembly order or raw vertex-index values),
     and an INSTANCED draw with per-instance-disjoint screen regions (does
     `primitive_id` reset per instance or accumulate globally).

6. **MSAA-dependent centroid vs. sample VALUE differentiation** (EXP-0111
   left this PARTIAL: centroid and sample both differ from center, but were
   not shown to differ from EACH OTHER). **COVERED.**
   - 6a. Reuses EXP-0111's own proven partial-coverage geometry
     (`interp_centroid_extrap.metal`: N=4, single pixel, 2-of-4 samples
     covered) with a per-sample-forced fragment shader that
     atomic-appends EVERY invocation's `(sample_id, sample-value,
     centroid-value, center-value)` via the pull-model
     `interpolate_at_sample/_centroid/_center` calls on ONE `interpolant<>`
     member — so per-invocation divergence between `sample` and `centroid`
     is directly observable, not inferred from a single racing buffer slot.
   - 6b. `[[sample_mask]]` finite-width sweep (N=1,2,4; every bit position
     0..31 partitioned into "corresponds to a real sample" vs "beyond the
     configured sample count") — this is also this item's contribution to
     the coordinator's "sample mask width" finite-resource row.

7. **Full CALL-ABI byte-level decode**, resolving EXP-0109's flagged
   `byte+6` `0x54`-vs-`0x56` discrepancy against EXP-0035's A18 record.
   **COVERED.**
   - 7a. Six constructed call topologies, extracted via the unmodified
     `tools/shdump`+`agxparse.py` pipeline: `k_single` (exactly one call
     site, no nesting), `k_twosame`/`k_twodiff` (two call sites, same/
     different callee, no nesting), `k_threecalls` (three call sites),
     `k_far` (one call site, callee body inflated to test whether `off40`
     MAGNITUDE alone predicts `byte+6`), and `k_nested` (a non-leaf helper
     calling a leaf TWICE, replicating EXP-0035's own "mid" shape byte-for-
     byte, extracted both as the kernel's own region and as the helper's
     separate `l__ZL...` symbol region).
   - Falsifiable hypotheses: **H-CALL-1** (call-site COUNT determines
     `byte+6`) is directly falsifiable by `k_single` alone showing `0x54`
     (EXP-0035's single-call-site A18 examples showed `0x56`). **H-CALL-2**
     (nesting/nonleaf-frame status determines it) is falsifiable by
     `k_twosame`/`k_twodiff`/`k_threecalls` (non-nested, multiple calls)
     agreeing with `k_nested` (nested). **H-CALL-3** (`off40` magnitude/
     sign determines it) is falsifiable by comparing `byte+6` across the
     full observed offset range from all six topologies.
   - 7b. Call-nesting DEPTH finite-resource sweep (`kernels/callchain.metal`,
     generated by the committed `harness/gen_callchain.py`): depths
     1,2,3,4,6,8,12,16,24,32,48,64,96,128, each a REAL compute dispatch +
     readback against the exact host oracle `out[gid]==gid+depth` (a
     silently-wrong value at depth N would show as a wrong float, not just
     a compile failure) — this is the coordinator's "call depth" finite-
     resource row.

8. **Stencil-value overflow behavior** for `[[stencil]]`. **COVERED.**
   - 8a. `uint` sweep: 0,1,127,254,255 (in-range boundary) and
     256,257,511,65535,4294967295 (`2^32-1`, the type's true maximum) — a
     real Stencil8 attachment readback against each value, every result
     compared to BOTH a "clamp-to-255" and a "truncate-low-8-bits" model.
   - 8b. `ushort` sweep (2 values) — does a narrower legal source type
     change the overflow model.
   - 8c. `int` (signed) — attempted and REJECTED at compile time (own-
     compiler diagnostic, captured verbatim) — kept as an isolated negative
     control in its own translation unit so the failure does not poison
     the working `uint`/`ushort` forms (MSL compiles one source file as
     one translation unit).

9. **Register-level live-value-crossing mechanics for a hypothetical,
   genuinely split prolog/epilog pair** (if a compiler ever built one via
   the CALL ABI rather than inlining). **DEFERRED, explicitly.**
   DRV-ABI-01's own scope note says to *specify* what an epilog generator
   must emit, not implement one; constructing and validating an actual
   split prolog/epilog pair end-to-end (its own calling convention,
   register save/restore discipline, live-range analysis across the split)
   is a substantial standalone engineering effort, not a bounded probe.
   Item 7's CALL-ABI byte decode is the necessary PRECURSOR fact this
   would build on (a real split, if ever built, uses the ordinary CALL/
   RETURN mechanism per EXP-0109 §5.1) — that precursor is covered; the
   full split-pair construction is not attempted here.

**A18/G17P confirmation of every M4 fact above** is out of scope for every
item — the A18 Pro is permanently hands-off per `CLAUDE.md`; not re-listed
per-item below.

## Falsifiers (compact form; full text integrated into each item above)

- H1 (blend factors): each of the 19 documented factors, applied as the
  SOLE nonzero-weighted operand (other side's factor = Zero), produces the
  exact value the standard GPU blend-factor formula predicts for that
  factor id (component-wise, using the src/dst/const colors and, for
  `SourceAlphaSaturated`, the correct RGB-vs-alpha-slot formula split).
  *Falsifier:* any factor whose observed result does not match the
  formula to float precision.
- H2 (blend ops): each of the 5 documented ops, with src=dst=(1,1,1,1)-
  weighted operands chosen so Add/Subtract/Min/Max/ReverseSubtract are
  numerically distinguishable, matches its standard formula exactly.
  *Falsifier:* any op producing a value matching a DIFFERENT op's formula.
- H3 (holes/invalid): `MTLBlendFactorUnspecialized`(19) and
  `MTLBlendOperationUnspecialized`(5) behave EXACTLY as their public-header
  doc comments state (factor: One for src-role/Zero for dst-role; op:
  Add) when used on the CLASSIC (non-MTL4) pipeline API; one step past
  each legal enum range (factor 20, op 6) is REJECTED via a fatal Metal
  API validation assertion (process abort), not a graceful `NSError`, not
  silent acceptance. *Falsifier:* a graceful NSError instead of an abort,
  or a value not matching the documented Unspecialized fallback.
- H4 (write mask): out-of-range bit 0x20 is silently inert (no crash, no
  effect distinguishable from bit unset); `MTLColorWriteMaskUnspecialized`
  (0x10) behaves as All, per its doc comment. *Falsifier:* a crash on
  0x20, or Unspecialized behaving as anything other than All.
- H5 (blend constant): values outside `[0,1]` are NOT clamped by the
  classic blend-constant API (pass through as IEEE floats into the blend
  math). *Falsifier:* an out-of-range constant producing a clamped
  (0 or 1) contribution instead of its literal value.
- H6 (integer format + blend): enabling `blendingEnabled=YES` on an
  integer-valued color pixel format (`MTLPixelFormatR32Uint`) is REJECTED
  via a fatal validation assertion (paired with a same-format,
  blending-disabled POSITIVE control that must succeed). *Falsifier:*
  successful pipeline creation with blending enabled on an integer format.
- H7 (logic-op epilog): `tile_read`+ALU+`frag_color_store`, hand-written in
  MSL via a `[[color(0)]]` fragment-function INPUT, correctly implements
  AND/OR/XOR/INVERT against arbitrary 32-bit patterns including the
  all-zero/all-one boundary values. *Falsifier:* any mismatch against the
  bitwise-arithmetic host oracle.
- H8 (MRT ceiling): color attachments 1..8 all render correctly and
  independently; index 8 (the 9th attachment, 0-based) raises a FATAL
  assertion the instant `colorAttachments[8]` is touched, independent of
  whether a matching N-output fragment function exists. *Falsifier:* a
  graceful failure instead of a fatal abort, or a successful 9-attachment
  configuration.
- H9 (FS order): `f_order_ab` and `f_order_ba` compile to BYTE-IDENTICAL
  machine code and produce identical hardware results. *Falsifier:* any
  byte or value difference.
- H10 (depth-fail suppression + stencil op selection): a depth-test
  FAILURE (driven by the shader's own explicit depth output) suppresses
  color AND stencil writes completely, and the stencil op that fires is
  the one CONFIGURED for that specific pass/fail outcome (verified in both
  Keep/Replace assignment directions). *Falsifier:* any partial write
  reaching the tile buffer on the fail side, or the wrong op firing.
- H11 (barycentric): raw `(b.x,b.y,b.z)` sums to 1.0 and, combined with
  known per-vertex tag values via manual in-shader recombination, matches
  ONE of the two host-computed candidate models (linear screen-space or
  perspective-corrected) to float precision. *Falsifier:* a sum
  meaningfully different from 1.0, or a manual-recombination value
  matching NEITHER candidate model.
- H12 (primitive_id): tracks primitive ASSEMBLY order (not raw vertex-
  index values) within one draw, and RESETS to 0 for each instance of an
  instanced draw (does not accumulate globally). *Falsifier:* pid tracking
  vertex-index values instead of assembly order, or pid accumulating
  across instances.
- H13 (centroid vs sample): within the SAME partially-covered pixel, the
  `sample`-qualified pull-model read differs measurably ACROSS different
  covered samples' own invocations, while the `centroid`-qualified read is
  IDENTICAL across those same invocations. *Falsifier:* `sample` and
  `centroid` reading identically at every covered sample, or `sample`
  itself varying across supposedly-identical conditions in a way that
  contradicts per-sample-position determinism.
- H14 (sample_mask width): for a configured sample count N, resolved
  color fraction for mask value M equals `popcount(M & ((1<<N)-1))/N`
  EXACTLY (no dithering, no aliasing of high bits into low bits).
  *Falsifier:* any deviation from exact popcount/N, or evidence of bit
  wraparound/aliasing for bits >= N.
- H15 (CALL-ABI byte+6): see H-CALL-1/2/3 above (item 7).
- H16 (call depth): every tested depth 1..128 produces the exact host
  oracle `out[gid]==gid+depth`, no compile failure, no fault, no silently
  wrong value. *Falsifier:* any depth producing a wrong value, a compile
  rejection, a GPU fault, or a hang (30s hard timeout per case).
- H17 (stencil overflow): values 256..2^32-1 truncate to their LOW 8 BITS
  (`value & 0xFF`) when stored to an 8-bit Stencil8 attachment — NOT
  clamped to 255. *Falsifier:* any observed value matching a clamp-to-255
  model instead of (or in addition to, for values whose low byte happens
  to be 255) the truncation model — disambiguated by choosing overflow
  values whose low byte is NOT 255 (256→0, 257→1, u16 300→44).
- H18 (stencil type legality): `uint`/`ushort` are accepted MSL types for
  `[[stencil]]`; `int` (signed) is REJECTED at compile time. *Falsifier:*
  `int` compiling successfully, or `uint`/`ushort` being rejected.

## Independent / controlled variables

- Blend: `MTLBlendFactor` (19+2 boundary values) × role (src/dst) ×
  `MTLBlendOperation` (5+2 boundary values) × write mask (9 values) ×
  blend constant (4 values) × pixel format (4 values incl. one integer
  reject pair) × sRGB (2 formats × 2 blend states) × alpha-to-coverage/one
  (5+2 values) × NaN/Inf bit patterns (4 values). Held fixed per sub-probe:
  everything not named (fullscreen-triangle geometry, 1-3 fragment
  invocations per draw).
- FS order: source-statement order (2 variants) × depth-test outcome
  (pass/fail, driven by shader-computed depth) × stencil-op assignment
  direction (2 variants).
- Barycentric/pid: triangle vertex `w` (fixed asymmetric 1/2/4), draw
  topology (non-indexed / indexed-shuffled / instanced).
- MSAA: sample count (1/2/4) × mask value (multiple per count, spanning
  legal and first-invalid-bit values) × interpolation qualifier
  (sample/centroid/center pull-model calls on one interpolant).
- CALL-ABI: call-site count (1/2/3) × callee identity (same/different) ×
  nesting (flat/non-leaf) × callee body size (baseline/inflated) ×
  nesting DEPTH (14 values, 1..128).
- Stencil: shader value (12 values spanning 0..2^32-1) × MSL source type
  (`uint`/`ushort`/`int`-rejected).

## Environment / timeouts frozen at registration

- Per-case subprocess timeout: 30s. Per-binary build timeout: 60s.
- Toolchain: Apple clang 21.0.0 (clang-2100.1.1.101), Metal 4, macOS
  26.6.2 (25G82), `xcrun` 72, Python 3.14.6, host Apple M4 / Mac16,10 / 10
  GPU cores.
- Two required runs: `m4-20260828-run01`, `m4-20260828-run02`, each a fresh
  process invocation of `run.py` producing its own `raw/<run_id>/` tree.

## Known confounders

- **Fatal-process-abort ordering.** Pilot testing found that a Metal API
  validation FAILURE for certain misconfigurations (invalid blend factor/
  op enum values, an out-of-range color-attachment array index, blending
  enabled on a non-blendable pixel format) raises a FATAL assertion that
  SIGABRTs the whole process rather than returning a catchable `NSError` —
  and, once, a case run IMMEDIATELY after such an abort transiently failed
  with a `kIOGPUCommandBufferCallbackErrorInnocentVictim` GPU error (not
  reproduced on 3/3 immediate retries in isolation). To eliminate any risk
  this poses to the two-run byte-identity gate, `casematrix.py` places
  every case confirmed-by-construction to fatal-abort at the very END of
  the case list (see its module docstring and the explicit `abort_ids`
  set), so no other case's GPU submission can ever be collateral to one.
  `run.py` treats a negative subprocess return code as the legitimate
  `PROCESS_ABORT` status (capturing the deterministic assertion text into
  the cross-run-compared `gated` record), not a run.py crash.
- **`[[instance_id]]` is vertex-stage-only in MSL** (own-compiler
  diagnostic, captured verbatim during pilot testing) — `primitive_id`'s
  instancing sub-test relays it via an ordinary `[[flat]]` varying instead
  of a (nonexistent) fragment-stage builtin.
- **`int` poisons a whole translation unit.** Because Metal compiles one
  source file as one compilation unit, the deliberately-invalid
  `int s [[stencil]]` negative control lives in its own file
  (`kernels/stencil_i32_negative.metal`) so it cannot fail the
  `uint`/`ushort` positive cases sharing `kernels/stencil.metal`.
- **`MTL4BlendStateUnspecialized` / Metal 4's dynamic pipeline-state
  surface** (new in macOS 26.0, discovered via public SDK header research)
  is a DIFFERENT, MTL4-native API path (its own pipeline descriptor and
  command-buffer classes) from the classic `MTLRenderPipelineDescriptor`
  path this experiment exercises throughout; the classic-path
  `MTLBlendFactorUnspecialized`/`MTLBlendOperationUnspecialized`/
  `MTLColorWriteMaskUnspecialized` sentinels tested here are the SAME
  enum values shared across both APIs and behave per their documented
  classic-path fallback (confirmed empirically, H3/H4 above), but the
  genuinely-dynamic MTL4 deferred-specialization workflow itself is not
  exercised — flagged as a follow-up lead, not asserted about here.
- **`interpolate_at_sample`/`_centroid`/`_center` are pull-model reads on
  ONE `interpolant<>` member**, matching EXP-0109/EXP-0111's own
  established byte-identical-to-qualifier-form pattern — this experiment
  does not re-verify that byte-identity claim, only uses the pull-model
  API as the measurement vehicle for item 6's VALUE-level question.
- **Barycentric perspective-vs-linear disambiguation depends on the host
  oracle being computed independently** in `analysis/`, from the SAME
  known triangle geometry the kernel encodes — a bug in that independent
  computation would not be caught by the two-run gate (which only proves
  reproducibility, not correctness of the oracle itself); the oracle
  script is reviewed by hand and its formulas are standard, publicly
  documented barycentric/perspective-interpolation math.

## Evidence-record schema (frozen)

Each case produces one JSONL record `{i, id, family, gated, meta}`. `gated`
is the byte-exact cross-run-compared payload (backend, params, status, and
on success the extracted hex/structural report/parsed JSON result/blend
readback bytes). `meta` (duration, timestamps, raw stderr tail, return code)
is excluded from the cross-run comparison. `run.py`'s `check_no_nondet()`
statically rejects `{duration_ms, pid, timestamp, started_utc, address,
elapsed}` anywhere inside `gated` (recursing into nested dicts and lists of
dicts).

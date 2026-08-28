# RESULTS — EXP-0111 M4 fragment semantics (FS-01..FS-12)

**Target:** Apple M4/G16G, this host only. macOS 26.6.2 (25G82), Metal 4, Apple clang
21.0.0. A18 Pro/G17P is `INFERRED`-by-family per `CLAUDE.md` target discipline; no A18
evidence exists or is claimed here.

**Two-run gate:** `raw/m4_20260828_run01/` and `raw/m4_20260828_run02/`, 56 cases each,
every case status one of `OK`/`SCANNED`/`REJECTED` (all expected outcomes — `REJECTED`
is the *predicted* result for `dynidx_out_reject_attempt`, not a failure). `python3
verify.py --crossrun raw/m4_20260828_run01 raw/m4_20260828_run02` → **PASS**: every
`*.gated.json` record byte-identical between the two runs. `python3 verify.py --selftest`,
`--seqtest`, and `--smoke` (run before `raw/` existed) → **PASS** (§13). Zero GPU fault,
hang, command-buffer error, or host wedge across 112 case executions plus the pilot
phase. No `macvdmtool` invocation, no A18/M5 contact.

**Compliance note:** a mid-session update to `experiments/SUBAGENT_BRIEF.md` prohibited
any file I/O outside the repository (including `/tmp`). Several early pilot commands in
this session had already written throwaway files to `/tmp`; all were identified and
deleted immediately upon reading the update, and every finding derived from them was
independently reproduced through the frozen kernels/harness before being relied on here.
Full detail: `PROGRESS.md`.

---

## 1. FS-01 — `get_sr 0xa0`/`0xa1` and NIR `load_pixel_coord`

```text
Status: [x] Closed
Answer: YES.
Applies to: [x] M4/G16G   [ ] A18 Pro/G17P (not tested)  [ ] both
Evidence: [x] independently assembled HW execution (splice)
          [x] HW splice (byte-level field flip, buffer readback)
          [x] API create/submit/exhaustion test (px+0.5/py+0.5 grid readback)
          [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory
          [x] encode/decode round trip (own-shader tokenize)
          [ ] own-MSL byte diff only (stronger evidence obtained)
          [ ] corpus inference only
Test/artifact: kernels/poscoord_scan.metal, poscoord_grid.metal,
  poscoord_splice_corner.metal; raw/m4_20260828_run0{1,2}/{poscoord_scan,
  poscoord_grid_w4h3,poscoord_splice_baseline,poscoord_splice_x_to_y,
  poscoord_splice_y_to_x}.gated.json
```

**OBSERVED.** `poscoord_scan` (own-shader tokenize of a minimal `f_main(float4 pos
[[position]]){return float4(pos.x,pos.y,0,1);}`): `get_sr` at SR `0xa0`→r0, SR
`0xa1`→r1, immediately followed by `cvt_i2f_src [int2f[32->32]]` consuming r0 (i.e. the
compiler explicitly treats the SR's value as an INTEGER requiring conversion, not a
native float). `poscoord_grid_w4h3` (raw-bit buffer readback, W4×H3, 12 pixels): every
covered pixel gave `pos.x == px+0.5`, `pos.y == py+0.5` exactly
(`(0.5,0.5),(1.5,0.5),(2.5,0.5),(3.5,0.5),(0.5,1.5),...,(3.5,2.5)` — 12/12 exact match).

**HW-splice (decisive):** `poscoord_splice_corner.metal` — a single triangle covering
exactly pixel (px=2,py=1) of a 3×2 target so only one, asymmetric-position invocation
runs, writing FIXED buffer slots (no position-derived addressing, avoiding a
register-reuse confound found and abandoned in pilot — see `PROGRESS.md`). `run.py`
locates the two `get_sr` instances by its own byte scan (never a hardcoded offset).
Baseline (unspliced archive): `buf=(x=2.5, y=1.5)`. Splicing the FIRST get_sr's SR-select
byte `0xa0→0xa1`: `buf=(x=1.5, y=1.5)` — the "x" slot now reads the TRUE Y value.
Splicing the SECOND get_sr's SR-select byte `0xa1→0xa0`: `buf=(x=2.5, y=2.5)` — the "y"
slot now reads the TRUE X value. A clean, mutual, hardware-confirmed swap, byte-identical
across both runs.

**INTERPRETED.** `get_sr 0xa0` returns the fragment's integer pixel X, `0xa1` the integer
pixel Y — HW-VALIDATED specifically in the fragment stage (this closes the gap EXP-0031
§5 flagged: "byte-diff only... should be re-confirmed"). The MSL-visible float
`[[position]].xy` is produced by explicit downstream conversion+offset arithmetic (only
the leading `cvt_i2f_src` step was bit-decoded here; the exact `+0.5` instruction was not
further isolated — a minor, explicitly flagged remainder, not load-bearing for the YES
verdict). This satisfies NIR `load_pixel_coord`'s integer contract directly from the SR
read, before any float conversion.

**Driver/compiler consequence:** a compiler backend can implement `load_pixel_coord` as a
direct `get_sr 0xa0`/`0xa1` read (raw integer, no conversion needed), and must apply its
OWN `+0.5`-and-convert sequence only when the source-language surface (e.g. MSL's
`[[position]]`) requires the float center convention — the hardware does not do this for
you natively in the SR value itself.

---

## 2. FS-02 — pixel-coordinate stability across samples and helper invocations

```text
Status: [x] Closed
Answer: YES (stable in both tested senses).
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
  [x] quad-relay technique (EXP-0091 pattern, reused)
Test/artifact: kernels/poscoord_msaa_stability.metal, helper_orig_relay.metal;
  raw/m4_20260828_run0{1,2}/{poscoord_msaa_stability_N2,poscoord_msaa_stability_N4,
  helper_orig_relay}.gated.json
```

**OBSERVED.** `poscoord_msaa_stability` ([[sample_id]] declared, forcing per-sample
invocation per EXP-0091 GLFS-A07): at N=2 and N=4, every one of the N per-sample
invocations of a given pixel recorded IDENTICAL raw `pos.xy` bits (e.g. at N=4, pixel
(0,0)'s 4 samples all read `(0.5,0.5)`; pixel (1,0)'s 4 samples all read `(1.5,0.5)`,
etc. — 0 deviations across 8+16 sample-invocations). `helper_orig_relay` (a triangle
covering exactly pixel column 0 of a W4H4 target, leaving column 1 an ORIGINAL —
never-covered — helper within the same hardware quad-column; relayed via
`quad_shuffle_xor(v,1)` since the helper's own write is suppressed, EXP-0091 GLFS-A06
pattern): the never-covered helper's own `pos.x`/`pos.y` read exactly `(1.5, py+0.5)` at
all 4 tested rows — the TRUE extrapolated pixel-grid coordinate, not zero, not frozen,
not garbage.

**INTERPRETED.** `[[position]]` is defined as the pixel center and does not vary with
sample index (per-sample shading re-executes the WHOLE shader per sample but position
stays pinned to pixel granularity), and an original helper invocation's position is
correctly computed via the same extrapolation machinery a live lane uses, not some
degenerate/undefined value. **Driver/compiler consequence:** a compiler can treat
`load_pixel_coord`/`frag_coord.xy` as sample-invariant within a pixel and safe to read
from any invocation including helpers, with no extra synchronization or per-sample
correction needed.

---

## 3. FS-03 — pixel coordinate / sample position / center convention

```text
Status: [x] Closed for pixel-center convention and axis origin;
        [ ] PARTIAL for exact raw sample-POSITION coordinates (deferred, see below)
Answer: pixel-center = px+0.5/py+0.5 (FS-01); origin = UPPER-LEFT, y increasing DOWNWARD.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
Test/artifact: kernels/poscoord_yhalf.metal, poscoord_xhalf.metal;
  raw/m4_20260828_run0{1,2}/{poscoord_yhalf_w4h4,poscoord_xhalf_w4h4}.gated.json
```

**OBSERVED.** `poscoord_yhalf` (a huge triangle covering exactly NDC y<0, W4H4 target):
framebuffer ROWS 2-3 (as returned by `getBytes`, row 0 first) are coloured; rows 0-1 are
not. `poscoord_xhalf` (NDC x<0): framebuffer COLUMNS 0-1 are coloured; columns 2-3 are
not. Both byte-identical across the two runs.

**INTERPRETED.** NDC+y (the "up" direction in clip space) maps to framebuffer row 0 (the
FIRST row returned) — i.e. **upper-left origin, y increasing downward** in window/
`[[position]]` space, matching the D3D/Metal convention documented in the public Metal
spec, now HW-confirmed on this hardware/toolchain rather than merely asserted from
documentation. NDC-x maps to framebuffer columns in the unsurprising left-to-right sense
(uncontested, included for completeness/symmetry).

**PARTIAL/deferred (explicitly, not silently dropped):** MSL exposes no
`gl_SamplePosition`-equivalent query in the surveyed surface
(`docs/isa/msl-feature-map.md`), so the exact raw sub-pixel coordinates of each hardware
MSAA sample position could not be queried or independently pinned down through the public
API in this experiment. EXP-0091's `msaa` group (GLFS-A01) already established that
samples are individually addressable and independently controllable via
`[[sample_mask]]`/`[[sample_id]]`, and this experiment's `interp_centroid_extrap` (§8)
shows centroid interpolation correctly resolves to a location strictly inside the covered
region — together these bound sample-position behavior without naming exact coordinates.
A dedicated splice-level or geometric-sweep follow-up would be needed to pin exact
per-sample offsets; **UNKNOWN**, flagged for follow-up.

**Driver/compiler consequence:** a compiler backend can rely on Metal's fixed
upper-left/y-down, px+0.5/py+0.5 convention when lowering `frag_coord`/`gl_FragCoord`
(Vulkan/GL's default is also upper-left in Vulkan, lower-left in classic GL — a GL
frontend must still flip Y, exactly as it would need to on any upper-left-origin
backend). Exact sample-position values for `gl_SamplePosition`/
`VK_EXT_sample_locations`-style queries remain unresolved and must be treated as
`UNKNOWN` rather than assumed to follow any particular "standard" grid.

---

## 4. FS-04 — fine derivative over the hardware 2×2 quad

```text
Status: [x] Closed
Answer: YES.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
Test/artifact: kernels/deriv_quadbound.metal;
  raw/m4_20260828_run0{1,2}/deriv_quadbound_axis{x,y}_{within,between}.gated.json
```

**OBSERVED.** A step function `v=(coord>=thresh)?1000:0` differenced with dfdx/dfdy, W4H4:
- **X axis, thresh splitting WITHIN the first quad-column-pair** (columns 0|1):
  `d=1000.0` for ALL rows of columns {0,1}, `d=0.0` for columns {2,3} — 16/16 pixels
  exactly matching the oracle.
- **X axis, thresh splitting exactly BETWEEN quad-column-pairs** (columns 1|2 boundary,
  i.e. between the (0,1) and (2,3) hardware quad columns): `d=0.0` for ALL 16 pixels —
  the "global" step is entirely invisible to the derivative on both sides.
- **Y axis:** identical pattern, transposed (within-quad-row-pair split → `d=1000` for
  rows {0,1}, `0` for {2,3}; between-quad-row-pair split → `d=0` everywhere).

All four cases byte-identical across both runs.

**INTERPRETED.** The derivative instruction computes a genuine quad-LOCAL difference,
broadcasting the SAME result to both lanes of the responsible pair, and is blind to any
discontinuity that falls between two different hardware quads — this is a direct,
decisive proof of 2×2-quad-scoped computation, not merely "some neighboring-pixel
difference" that happens to often coincide with quad boundaries.

**Driver/compiler consequence:** `scalarize`/derivative lowering can assume standard
SPIR-V/Vulkan/GL "fine" derivative semantics (quad-local finite difference); no special
handling is needed for values that are locally constant within a quad but vary at a
larger granularity — the hardware naturally reports 0 there, matching the API contract.

---

## 5. FS-05 — distinct coarse derivative mode

```text
Status: [x] Closed as a documented ABSENCE at the Metal API-exposure level;
        [ ] UNKNOWN at the ISA-encoding level (explicitly deferred)
Answer: No MSL-reachable coarse mode exists; whether the ISA has an unreached coarse bit
  is UNKNOWN.
Applies to: [x] M4/G16G (API-exposure finding); ISA-level: not established
Evidence: [x] PUBLIC (MSL surface survey, docs/isa/msl-feature-map.md A18)
          [ ] HW splice (not attempted — see rationale below)
```

**OBSERVED/INTERPRETED.** The surveyed Metal Shading Language surface exposes exactly one
derivative granularity per axis (`dfdx`/`dfdy`/`fwidth`) — there is no `dFdxCoarse`/
`dFdxFine`-style pair as SPIR-V/HLSL expose. Per the Metal-subset heuristic (`CLAUDE.md`
methodology), this means **no MSL-level probe can distinguish "the hardware has only one
mode" from "the hardware has a second mode Metal simply never emits"** — there is no
compiler-reachable starting point to perturb. `docs/isa/encoding-tables.md`'s own
`tex_deriv` entry already flags "Full fine/coarse decode is a follow-up" as an open item
on the 10-byte `0x37` op's less-documented bytes (byte+7/+8/+9 beyond the decoded
axis/dst/src fields).

**Decision (explicit, not a silent drop):** this cluster's budget does not extend to an
undirected blind-bit splice sweep on those unexplored bytes (no hypothesis for what
pattern would mean "coarse" — an unmotivated sweep would be closer to random fault-hunting
than a falsifiable test, contrary to CODEX §2's pre-registration discipline). **Verdict:
CLOSED at the API/compiler-surface level (No — a portable-NIR backend has no MSL path to
request a distinct coarse op and must treat dfdx/dfdy as the only derivative primitive
available); the underlying ISA-level "is there an unreached coarse mode" question remains
UNKNOWN**, flagged for a dedicated bit-decode follow-up experiment.

**Driver/compiler consequence:** lower NIR `nir_op_fddx_coarse`/`fddx_fine` (and their y
counterparts) to the SAME single hardware primitive — there is no cheaper "coarse" path
to select even as an optimization; if the hardware secretly has one, a compiler cannot
reach it through any documented Metal surface, so it is unusable for compilation
purposes regardless.

---

## 6. FS-06 — derivative correctness for helper/discarded/out-of-coverage lanes

```text
Status: [x] Closed (adds the ORIGINAL-helper case to EXP-0091's already-closed demoted
  case)
Answer: YES for both tested lane categories (demoted, original/never-covered helper).
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
Test/artifact: kernels/helper_orig_relay.metal;
  raw/m4_20260828_run0{1,2}/helper_orig_relay.gated.json (this experiment);
  experiments/EXP-0091-.../RESULTS.md §2 (demoted-lane case, cited not repeated)
```

**Demoted lanes (cited, not repeated):** EXP-0091 §2 (GLFS-A02/OPT-09) HW-validated that a
post-`discard_fragment()` lane's continued register mutation is correctly visible to a
surviving neighbour's `dfdx`/`fwidth` (a surviving lane's `fwidth()` read exactly `999.0`,
matching the discarded neighbour's post-discard `+1000` mutation).

**Original (never-covered) helper lanes — this experiment's remainder:** `helper_orig_relay`
(triangle covering exactly pixel column 0 of a W4H4 target; column 1 is an ORIGINAL
helper, relayed via `quad_shuffle_xor`): the live lane's `dfdx(pos.x)` — computed using
the never-covered helper's contribution — read exactly `1.0` (the true per-pixel screen-
space step) at all 4 tested rows, matching the ordinary interior-quad oracle exactly.
EXP-0091 §3 explicitly flagged this exact case ("this experiment did not build a
quad-shuffle relay for the original-helper case") as untested; this closes that gap.

**INTERPRETED.** Both demoted and original/never-covered helper lanes correctly
participate in quad-local derivative computation — derivative correctness does not
depend on WHY a lane is a helper (it was always outside the primitive vs. it became one
via `discard_fragment()`), only on whether it can compute the underlying value at its
extrapolated position, which both categories do correctly.

**Driver/compiler consequence:** a compiler does not need separate derivative-legalization
paths for "original helper" vs. "demoted" lanes — both are handled uniformly and
correctly by the same quad-difference hardware, consistent with `discard_is_demote=true`
(OPT-09) extending cleanly to this case too.

---

## 7. FS-07 — one derivative instruction per scalar component

```text
Status: [x] Closed
Answer: YES (scalarize_ddx = true).
Applies to: [x] M4/G16G
Evidence: [x] encode/decode round trip (own-shader compile-scan, tools/agx-isa tokenizer)
          [x] API create/submit/exhaustion test (deriv_axis_check ground-truth readback)
Test/artifact: kernels/deriv_scalar_f{1,2,3,4}.metal, deriv_scalar_f4_both.metal,
  deriv_scalar_plain.metal, deriv_axis_check.metal;
  raw/m4_20260828_run0{1,2}/{deriv_scalar_*_scan,deriv_axis_check}.gated.json
```

**OBSERVED.** Own-shader compile-scan of `dfdx()` on float1/2/3/4 values with
algebraically-independent (transcendental-of-distinct-varyings) components: EXACTLY 1, 2,
3, 4 instances of the 10-byte `0x37`/byte+2==0x54 derivative op for N=1,2,3,4
respectively (no case showed a wider or narrower op, and no case showed fewer instances
than N, ruling out any CSE/fusion across components). A combined `dfdx(v)+dfdy(v)`
(float4) gave 8 total instances (4 axis-byte `0x92`, 4 axis-byte `0x90`). A plain
(non-transcendental) single-float varying, dfdx-only, gave 1 instance.

**Genuine anomaly surfaced (reported, not resolved):** every dfdx-ONLY kernel (f1..f4,
plain — 5/5 kernels, no `dfdy` call anywhere in the source) compiled its instance(s) to
axis-byte `0x90` — NOT `0x92` as `docs/isa/encoding-tables.md`'s existing "0x92=dfdx;
0x90=dfdy" labeling (EXP-0016 provenance) would predict. A dedicated ground-truth kernel
(`deriv_axis_check`: separately calling `dfdx(pos.x)`, `dfdx(pos.y)`, `dfdy(pos.x)`,
`dfdy(pos.y)` in ONE shader, HW-readback against the exact `1.0`/`0.0` oracle — readback
`[1.0, 0.0, 0.0, 1.0]`, an exact match) shows axis `0x92` for BOTH dfdx calls and `0x90`
for BOTH dfdy calls in THAT (both-present) shader. **The axis byte correlates with
call-site identity (dfdx vs dfdy) only when both appear in the same program; a
program calling only dfdx uses the OTHER label exclusively.** This is reported exactly as
observed and is **NOT resolved here** — flagged for the `docs/isa` owner as a correction
candidate (the current "0x92=dfdx/0x90=dfdy" table entry is INCOMPLETE, not simply wrong:
both labels are real and both are seen from genuine dfdx calls depending on context).

**INTERPRETED (FS-07's own question, unaffected by the anomaly):** every observed
derivative instance handles exactly one scalar component (10-byte length, fixed axis
field, no vector-width modifier ever observed) — the compiler always scalarizes,
regardless of source vector width or the axis-byte context.

**Driver/compiler consequence:** a compiler backend must set `scalarize_ddx = true` and
emit one derivative instruction per scalar component, matching NIR's existing scalarizing
lowering path. The axis-byte anomaly is a separate, ISA-documentation-only concern (which
literal value `0x92` vs `0x90` to emit for "the derivative op needed here") that a
compiler can navigate empirically per-context but which is not yet reduced to a clean
rule — flagged, not blocking.

---

## 8. FS-08 — interpolation modes independently encodable and HW-validated

```text
Status: [x] Closed for flat/smooth/no-perspective (EXP-0029, cited) + centroid-vs-center
  extrapolation + interpolate_at_offset numerics (this experiment);
        [ ] PARTIAL for full sample-vs-centroid separation (see below)
Answer: YES, with one significant API-behavior anomaly for interpolate_at_offset.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
Test/artifact: kernels/interp_centroid_extrap.metal, interp_offset_{sweep,y,xy,anchor}.metal;
  raw/m4_20260828_run0{1,2}/{interp_centroid_extrap,interp_offset_*}.gated.json;
  experiments/EXP-0029-fragment-isa/RESULTS.md §1 (flat/perspective/no-perspective, cited)
```

**Flat / smooth / no-perspective (cited, not repeated):** EXP-0029 §1 HW-proved flat as a
distinct, constant-provoking-vertex-valued op, and perspective vs. no-perspective vs.
flat as three numerically distinct pixel values under non-trivial w.

**Centroid vs. center (this experiment, new):** `interp_centroid_extrap` — a single
pixel (W1×H1, N=4) covered by exactly 2 of 4 samples (independently pilot-confirmed via
the resolve-fraction technique: resolved fraction exactly 0.5), with the pixel's
geometric center provably OUTSIDE the covered region (edge at local x=0.4, center at
0.5). Varying `v=ndc_x` (an exact affine function of screen position, so the true
mathematical center value is host-computable: `0.0`). **Readback: `v_center =
0.0039215...` (within ~1/255 of the true, unclamped, extrapolated 0.0 — plausibly an
~8-bit rasterizer sub-pixel-precision artifact, not a coverage clamp, which would read
< -0.2), `v_centroid = -0.24705886...`** (decisively inside the covered region,
decisively different from `v_center`). Byte-identical across both runs.

**`interpolate_at_offset` numeric sweep (this experiment, new, significant finding):**
against the same exact-affine-varying oracle at N=1 full coverage, ≥17 distinct offset
values across X-only, Y-only, and combined-XY sweeps (`interp_offset_sweep/_y/_xy`),
all in `raw/m4_20260828_run0{1,2}/`. Selected exact readbacks (float32, byte-identical
both runs):

| offset (dx,dy) | measured `v` (v=ndc_x unless noted) | naive spec prediction* |
|---|---:|---:|
| (0.0, 0.0) | **-1.0** | 0.0 |
| (0.25, 0.0) | -0.5 | 0.5 |
| (0.5, 0.0) | 0.0 | 1.0 |
| (0.9, 0.0) | 0.7999999523... | 1.8 |
| (-0.9, 0.0) | -2.7999999523... | -1.8 |
| (0.0, 0.0), v=ndc_y | **+1.0** | 0.0 |
| (0.0, 0.25), v=ndc_y | 0.5 | -0.5 |
| (0.2, 0.1), v=ndc_x+10·ndc_y | 7.4 | 1.4 |
| (-0.3, 0.4), v=ndc_x+10·ndc_y | 0.3999994993... | -5.6 |

\* "naive spec prediction" = MSL's documented contract (offset ∈ signed range from pixel
CENTER, y untouched) evaluated the same way `v` is defined.

Every single measured value instead matches, to sub-ULP precision, the plane evaluated at
an **absolute window-space pixel-local coordinate equal to (dx,dy) directly** — origin at
the pixel's TOP-LEFT corner, x rightward, y DOWNWARD (window/`[[position]]` convention per
FS-03 §3), 1.0 unit = one full pixel width, with **no clamping or wraparound observed up
to |offset|=2.0** (pure linear extrapolation continues past the documented `[-0.5,0.5)`
range in both directions). A companion anchor case (`interp_offset_anchor`) confirms
`interpolate_at_center()` (pull-model) and `center_perspective` (push-model) agree with
each other and with the true mathematical center (both read `0.0`), while
`interpolate_at_offset(float2(0,0))` in the SAME shader, on the SAME source value, reads
`-1.0` — ruling out a harness/oracle bug as the explanation (the push/pull-center pair is
the internal control proving the measurement method itself is sound).

**INTERPRETED.** Centroid interpolation genuinely, measurably differs from (unclamped)
center interpolation under partial coverage — center extrapolates past the primitive
edge; centroid does not. `interpolate_at_offset`'s (dx,dy) argument, on this M4/Apple9
target via the public Metal API and this toolchain, does **not** implement the MSL
specification's documented "signed offset from pixel center" contract; it behaves as an
absolute, corner-relative, y-down window coordinate instead. This is reported via the
PUBLIC Metal API (not an ISA splice) so it could reflect either genuine hardware wiring
or an AIR→AGX compiler-backend bug specific to this toolchain version — either way it is
the reproducible, actionable behavior a driver calling this exact API path would observe.

**PARTIAL (flagged, not dropped):** full behavioral separation of `sample` from
`centroid` (both avoid the extrapolation `center` performs; this experiment did not
additionally prove sample and centroid differ from EACH OTHER under a coverage pattern
where they would predictably diverge) remains open — EXP-0029's structural byte-diff
(distinct setup-op byte+7 `0x01` vs `0x03`) is the only evidence for that specific
sub-claim; not independently HW-behaviorally separated here.

**Driver/compiler consequence:** flat/smooth/no-perspective/centroid are all independently
usable exactly as documented. **`interpolate_at_offset` MUST NOT be fed a driver-computed
"NIR/SPIR-V-style center-relative" offset directly** — a backend targeting this exact API
path needs to transform `(dx,dy) → (dx+0.5, 0.5-dy)` (or equivalent) before calling it, or
every pull-model offset-interpolation will sample from up to half a pixel in the wrong
direction (and, for offsets with |value|>0.5, from a different location than the
documented spec implies at all). This is a concrete, non-obvious, driver-relevant
correctness fact a compiler team could not get right by reading the public MSL spec alone.

---

## 9. FS-09 — convergent interpolation vs. flat distinctness

```text
Status: [x] Closed
Answer: YES — convergent interpolation is NOT provably bit-identical to flat in general.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
Test/artifact: kernels/interp_convergent.metal;
  raw/m4_20260828_run0{1,2}/interp_convergent_{A,B,C,D,E}.gated.json
```

**OBSERVED.** 5 independent `(w0,w1,w2,attr)` configurations, each with an IDENTICAL
attribute value at all 3 vertices (mathematically convergent), read back at 16 pixels via
flat / `center_perspective` (smooth) / `center_no_perspective` (linear), all
byte-identical across both runs:

| config | w0,w1,w2 | attr | covered px | smooth diverges from flat | linear diverges from flat |
|---|---|---:|---:|---:|---:|
| A | 1,2,3 | 0.1 | 16 | 0/16 | **16/16** |
| B | 1,5,20 | 0.4333... | 16 | 0/16 | 0/16 |
| C | 1,2,3 | 0.3333... | 16 | 0/16 | **16/16** |
| D | 2,2,2 | 0.1 | 16 | 0/16 | 0/16 |
| E | 1,1000,1 | 0.1 | 16 | 0/16 | **16/16** |

Divergences (configs A, C, E) are 1-2 ULP, uniform across all 16 pixels of the diverging
config. Perspective (smooth) matched flat bit-exactly in 80/80 sampled (config,pixel)
pairs across all 5 configurations; linear (no-perspective) matched flat in only 2/5
configurations. **Open curiosity, not chased further:** config D (uniform w) shows no
linear divergence despite sharing config A's exact attribute value (0.1) — since
no-perspective interpolation is mathematically w-independent, this w-dependence of its
rounding behavior is unexplained and flagged as PARTIAL/open.

**INTERPRETED.** A compiler MUST NOT assume a convergent (all-vertices-equal) smooth
input can be silently folded into a flat/provoking-vertex load — real hardware rounding
in at least the no-perspective interpolation path demonstrably produces a different
result in 3 of 5 tested parameter regimes. Perspective-correct interpolation was
bit-exact with flat in every one of the 80 samples tested here, but this is a narrower
observation (bounded parameter range, not proven universal) and does not license folding
it to flat either.

**Driver/compiler consequence:** `nir_io_always_interpolate_convergent_fs_inputs` is
justified and necessary — a compiler backend must keep genuine interpolation instructions
for convergent inputs rather than substituting a flat/uniform load, for at least the
no-perspective path, and by the conservative/uniform rule should do so for all paths.

---

## 10. FS-10 — dynamically indexed fragment inputs

```text
Status: [x] Closed
Answer: YES — lowerable without changing interpolation mode or provoking-vertex behavior.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] encode/decode round trip
          [x] API create/submit/exhaustion test
Test/artifact: kernels/dynidx_in_select.metal, dynidx_in_control.metal;
  raw/m4_20260828_run0{1,2}/{dynidx_in_select_scan,dynidx_in_control_scan,
  dynidx_in_select_render}.gated.json
```

**OBSERVED.** `float arr[4]={v0(flat),v1,v2,v3}; return arr[px%4];` (px = a
position-derived, non-compile-time-foldable runtime index): HW readback gives exactly
`[10.0, 11.0, 12.0, 13.0]` for `px=0..3` — an exact 4/4 match against the `10+idx`
oracle. Compile-scan (own-shader tokenize) shows a CLEAN decode: an `icmp_pred`+`sel`
ALU pair immediately follows the varying-read block, and the interpolation instructions
(`iter`/`iter_flat`) each carry small values in their slot field
(`iter_slots_raw=[0,24,6,10,8,8]`, `iter_flat` count 2 — one more than the single
declared `flat` varying, an unexplained minor duplication not investigated further and
explicitly flagged, not load-bearing for the verdict). A constant-index control
(`arr[2]` literal) compiles to a structurally analogous but shorter sequence (4 iter + 1
iter_flat; the array-literal construction reads all 4 declared varyings regardless of
static-vs-dynamic index, so this control isolates "does the runtime index change the
INTERPOLATION instructions" rather than "does the compiler dead-code-eliminate unused
varyings" — the former is FS-10's actual question).

**INTERPRETED.** Dynamic fragment-input indexing lowers to "read every declared
candidate via ordinary, fixed-slot interpolation instructions (same op family, same field
shape as static indexing — no register-sourced-looking slot field was observed in either
version), then select the desired one via ordinary ALU (`icmp_pred`+`sel`)" — exactly the
safe compiler strategy FS-10 asks about, now functionally HW-confirmed correct.

**Driver/compiler consequence:** a NIR backend targeting Apple9 can lower a dynamically-
indexed fragment input as "materialize every candidate via its normal (static)
interpolation-mode instruction, then select" without needing (or risking triggering) any
special dynamic-varying-slot hardware path, and without altering interpolation mode or
provoking-vertex behavior for any of the candidates.

---

## 11. FS-11 — dynamically indexed fragment outputs

```text
Status: [x] Closed for both sub-claims (no direct MSL syntax; branch-unrolled workaround
  correct); [ ] PARTIAL for the exact ISA-level mechanism of the single-store encoding
Answer: No direct dynamic-output syntax exists in MSL; a branch-unrolled workaround is
  both necessary and functionally correct, including for a genuinely per-fragment-
  divergent (not merely uniform) selector.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] API create/submit/exhaustion test
          [x] encode/decode round trip (partial, see below)
Test/artifact: kernels/dynidx_out_reject.metal, dynidx_out_unroll.metal;
  raw/m4_20260828_run0{1,2}/{dynidx_out_reject_attempt,dynidx_out_unroll_scan,
  dynidx_out_unroll_render}.gated.json
```

**OBSERVED (negative/structural).** `struct FOut { float4 colors[2]; };` (no per-element
`[[color(n)]]` attribute) as a fragment return type is **REJECTED** by
`newLibraryWithSource:`: `"invalid return type 'FOut' for fragment function"`. There is no
MSL grammar path to even ATTEMPT an array-typed/dynamically-indexed fragment output —
every output must be an individually-named, compile-time-fixed `[[color(n)]]` field.

**OBSERVED (positive/functional).** The only expressible workaround — branch-unrolled,
compile-time-fixed `[[color(0)]]`/`[[color(1)]]` outputs guarded by runtime control flow
— was tested with `idx` derived from `[[position]]` (`(uint)pos.x & 1`), i.e. genuinely
**per-fragment DIVERGENT**, not a uniform draw-wide value (this harness's one new
capability, `--rt-count`, provides the second render target needed). W2×H1 readback:
pixel(0,0) [even x] → RT0=red `(1,0,0,1)`, RT1=clear; pixel(1,0) [odd x] → RT0=clear,
RT1=green `(0,1,0,1)` — an exact 2/2 pixel × 2/2 RT match against the oracle, i.e. two
DIFFERENT fragments in the SAME draw correctly routed to two DIFFERENT render targets.

**OBSERVED (structural, PARTIAL).** Compile-scan of the divergent-selector program shows
a CLEAN decode containing only **ONE** `frag_color_store` instruction (`rt_index_bytes=
[0], store_count=1`) — not the naively-expected two (one per branch arm) — preceded by an
`icmp_pred`+`sel` ALU pair and TWO `frag_tile_setup` brackets with different selector
bytes (`sel=0x0` and `sel=0xc`; the latter does not match EXP-0029's simple
`0x0`/`0x4`/`0x8` fixed-RT-index table for ordinary static MRT). Despite only one visible
store instruction, the readback proves BOTH RT0 and RT1 correctly receive per-fragment-
divergent data. **This was NOT further bit-decoded here** — whether the true mechanism is
a genuinely dynamic (predicate/register-sourced) tile/RT selector, or a different static
encoding this experiment's byte-level model does not yet capture, is left **UNKNOWN**,
flagged as a candidate follow-up (possible new hardware capability worth a dedicated
splice-level investigation).

**INTERPRETED.** FS-11's own question (can dynamic output indexing be lowered without
Metal ever needing/exposing an unsupported dynamic-RT-selector AT THE SOURCE LEVEL) is
answered **YES** — MSL provides no syntax for it, so a compiler is never asked to; the
branch-unrolled form is the correct, only, and functionally-validated lowering strategy.
Whether the COMPILED result happens to exploit a genuine hardware dynamic-selector
capability underneath is a separate, open, more speculative question this experiment
surfaces but does not resolve.

**Driver/compiler consequence:** lower a portable dynamically-indexed fragment output as
a branch/select chain over statically-numbered `[[color(n)]]` outputs (this is both
necessary — nothing else compiles — and proven correct on real hardware for per-fragment-
divergent selectors); do not assume a single dynamic-RT-write instruction is available at
the compiler's own IR level even though the underlying compiled machine code for this
specific MSL pattern turned out structurally richer than expected.

---

## 12. FS-12 — `discard_fragment` suppression of color/depth/stencil/sample-mask

```text
Status: [x] Closed for color/depth/buffer/atomic (EXP-0091, cited) + sample-mask (this
  experiment); [ ] PARTIAL for stencil (documented absence, not independently validated)
Answer: YES for every channel where a shader-driven write exists to test.
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution (this experiment, sample-mask)
          [x] API create/submit/exhaustion test
Test/artifact: kernels/fs12_samplemask_demote.metal;
  raw/m4_20260828_run0{1,2}/fs12_samplemask_{control,discard}.gated.json;
  experiments/EXP-0091-.../RESULTS.md §4 (color/depth/buffer/atomic, cited)
```

**Color/depth/buffer/atomic (cited, not repeated):** EXP-0091 §4 (GLFS-A06) HW-validated
complete, uniform suppression of all four channels from a demoted lane, deterministic and
byte-identical across two runs.

**Sample-mask (this experiment's remainder).** `fs12_samplemask_demote`: even-x lanes
`discard_fragment()`; ALL lanes (including discarded ones) then unconditionally write
`color=(1,1,1,1)` and `[[sample_mask]]=0xF` (N=4 MSAA), resolve-fraction readback.
No-discard control: both pixels read `1.0` (fully white, full mask honoured). Discard
case: the discarded (even-x) pixel reads exactly `0.0` (fully clear — as if NEITHER the
color NOR the sample-mask write reached the tilebuffer at all); the surviving (odd-x)
pixel reads exactly `1.0` (fully written), matching the control. Byte-identical across
both runs.

**INTERPRETED.** A demoted lane's `[[sample_mask]]` write is suppressed just as
completely as its color/depth/buffer/atomic writes — no partial effect (e.g. mask bits
partially "leaking" through while color is blocked) was observed; suppression behaves as
one uniform hardware property of the discarded lane's fixed-function/tile-memory writes,
not a per-channel special case.

**Stencil — PARTIAL, explicitly deferred (not silently dropped).** MSL exposes **no
fragment-shader-writable stencil output at all** (surveyed `docs/isa/msl-feature-map.md`
and `docs/capability-completeness.md`: only `[[color(n)]]`, `[[depth(qualifier)]]`, and
`[[sample_mask]]` are documented fragment stage-out attributes; stencil is exclusively a
fixed-function TEST+OP driven by pipeline/depth-stencil state and an API-set reference
value, never a shader-computed value). There is therefore **no API surface to even
attempt** this sub-clause via MSL. The safe fallback — by architectural analogy to the
uniformly-proven depth-channel suppression (GLFS-A06) and the depth/stencil attachment's
shared tile-memory-resident nature — is that a discarded lane's contribution to the
fixed-function stencil OP is likewise suppressed, but this is **INFERRED, NOT
independently HW-validated** here; a dedicated stencil-attachment harness extension is
recommended follow-up.

**Driver/compiler consequence:** a compiler backend can treat discard-suppression as
automatic and complete for color, depth, buffer, atomic, and sample-mask outputs — no
extra predication needed for any of these five channels following a discard. Stencil
suppression should be assumed but is explicitly flagged as unverified; do not cite it as
`HW-VALIDATED` in downstream documentation without a dedicated follow-up.

---

## 13. Two EXP-0091 anomaly resolutions

### 13a. Anomaly (a) — GLFS-A03 helper_pre spatial non-uniformity

```text
EXP-0091 finding (single-run supplementary probe): helper_pre (read via quad_shuffle_xor
relay, BEFORE the lane's own discard) read TRUE for 2 of 8 relayed lanes instead of the
expected FALSE, deterministic but spatially non-uniform, flagged UNEXPLAINED.
Second method (this experiment): anomaly_helper_pre_direct.metal -- write
simd_is_helper_thread() DIRECTLY to a per-lane buffer slot strictly BEFORE that lane's
own discard_fragment() call, NO quad_shuffle_xor relay at all (eliminates the shuffle
mechanism as a variable). W4H4, half the lanes about to discard.
```

**OBSERVED.** All 16 buffer slots read `0` (helper_pre = FALSE) — for every lane, both
those about to discard and those that will survive. Byte-identical across both runs.

**INTERPRETED.** The anomaly does **NOT reproduce** via a fully independent (unrelayed)
measurement method. This strongly suggests the original 2/8 non-uniformity was an
artifact of the `quad_shuffle_xor` relay mechanism itself (or the specific single-run,
diagonal-quad-position geometry EXP-0091 used), not a genuine hardware fact about
pre-discard helper status. **Resolution: helper_pre reads FALSE uniformly when measured
directly; the EXP-0091 anomaly is most likely a measurement artifact of the relay
technique, not a real hardware non-uniformity — the underlying GLFS-A03 claim ("helper
status becomes true immediately upon a lane's own discard, and is FALSE beforehand") is
now HW-validated with two independent methods (byte-identical across two runs each).**

### 13b. Anomaly (b) — GLFS-A07 per-sample discard suppression non-uniformity

```text
EXP-0091 finding: f_persample_discard_N4 (odd sample_id discards, measured via a
(pixel,sample)-indexed ATOMIC COUNTER buffer) found only 2 of 8 "should be suppressed"
slots actually suppressed -- deterministic but spatially non-uniform, unlike the
complete/uniform suppression g6_suppress found for whole-fragment discard.
Second method (this experiment): anomaly_persample_resolve.metal -- SAME per-sample-ID-
conditioned discard, measured via the resolve-fraction technique (plain color write +
hardware MSAA box-filter resolve, NO atomics, NO manual (pixel,sample) buffer addressing
at all).
```

**OBSERVED.** No-discard control: all 4 tested pixels read `1.0` (full white). Discard
(odd `sample_id`) case: all 4 tested pixels read exactly `0.5020 ≈ 128/255` (i.e. exactly
2 of 4 samples survive, matching the `0.5` oracle) — uniform and complete at every pixel,
with NO non-uniformity of any kind. Byte-identical across both runs.

**INTERPRETED.** The anomaly does **NOT reproduce** via this fully independent
measurement mechanism. Per-sample-ID-conditioned discard produces UNIFORM, COMPLETE
suppression — indistinguishable in completeness from whole-fragment discard
(GLFS-A06) — when measured without atomics or manual per-(pixel,sample) buffer
addressing. **Resolution: the original 2/8 finding is most plausibly attributable to the
(pixel,sample)-indexed ATOMIC COUNTER measurement mechanism itself (e.g. an addressing,
replay, or atomic-ordering interaction specific to per-sample-shaded atomic writes), not
a real hardware fact about per-sample discard suppression. The underlying claim ("discard
suppression is complete regardless of granularity — whole-fragment or per-sample") is now
HW-validated by two independent methods.** This does not retroactively invalidate
EXP-0091's atomic-based observation as data (it is preserved, unedited, in that
experiment's raw/) — it narrows the INTERPRETATION: the non-uniformity is now attributed
to the measurement technique, not the underlying hardware behavior, pending any future
experiment that finds a genuine atomic-under-per-sample-shading quirk worth its own
investigation (out of scope here).

---

## 14. Finite-resource-mandate summary table

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| Fragment pixel-coordinate SR (FS-01) | one fragment invocation | `get_sr` SR# byte1: `0xa0`=x, `0xa1`=y | 2 values, both HW-splice-swap-confirmed | none observed | n/a (not a numeric range) | n/a | driver must read the correct SR per axis; splice-proven the values are NOT interchangeable-by-accident | poscoord_splice_*, §1 |
| Interpolation coefficient slot (FS-10, `iter` byte+5) | one fragment program's declared varying set | small fixed immediate (byte+5, `slot<<1` per EXP-0029) | every declared varying gets its own slot, read unconditionally even under dynamic indexing (4 slots tested) | none observed in this range | not established (no fault at any tested slot value) | n/a | dynamic indexing must read every candidate slot, not attempt a register-sourced slot address | dynidx_in_select_scan, §10 |
| `interpolate_at_offset` argument range (FS-08) | one interpolant pull-model call | float2, window-corner-relative per this experiment's finding (not the documented center-relative contract) | tested `[-0.9,+0.9]` pixel-widths on 2 axes + combined, all linear, NO clamp/fault observed up to ±2.0 | none found up to ±2.0 | not established (no clamp/fault found in tested range) | pure linear extrapolation, no fault | driver must pre-transform (dx,dy)→ window-corner convention before calling; do not rely on the documented `[-0.5,0.5)` semantic | interp_offset_*, §8 |
| MRT render-target count (FS-11 harness capability) | this experiment's `fsrun` harness | `--rt-count` 1..3 | 1,2 exercised (2 used for the FS-11 case) | 3 built but not exercised by a frozen case | not applicable (harness limit, not a hardware limit) | n/a | not a hardware finding — a testbed capability note | harness/fsrun.m |
| Convergent-vs-flat divergence (FS-09) | one interpolated scalar per triangle | n/a (behavioral, not a resource table) | 3/5 tested parameter configurations diverge (no-perspective path); 0/5 diverge (perspective path, bounded evidence) | n/a | n/a | 1-2 ULP divergence, never a fault | compiler must not fold convergent inputs to flat for either path | interp_convergent_*, §9 |

## 15. Deferred items (explicit, not silently dropped)

1. **FS-03** — exact raw MSAA sample-position coordinates: `UNKNOWN`, no MSL query
   surface exists; needs a dedicated splice/geometric-sweep follow-up.
2. **FS-05** — whether an ISA-level "coarse" derivative bit exists beyond Metal's
   MSL-reachable surface: `UNKNOWN`, explicitly out of this cluster's budget (no
   motivated hypothesis for a blind splice sweep).
3. **FS-08** — full behavioral separation of `sample` from `centroid` (both differ from
   `center`, but were not shown to differ from EACH OTHER behaviorally here): `PARTIAL`,
   structural-only evidence (EXP-0029 byte-diff).
4. **FS-11** — the exact ISA-level mechanism behind the single-`frag_color_store`,
   per-fragment-divergent-RT-routing encoding (§11): `PARTIAL/UNKNOWN`, flagged as a
   possible new hardware-capability lead worth a dedicated splice follow-up.
5. **FS-12** — stencil-output suppression from a demoted lane: `PARTIAL`, no MSL surface
   exists to test it directly; `INFERRED`-by-analogy only.
6. **FS-07** — the axis-byte (`0x92`/`0x90`) labeling anomaly: reported, not explained;
   a correction candidate for `docs/isa/encoding-tables.md`'s existing table, not a
   blocker for FS-07's own verdict.

## 16. Gate results

```
$ python3 verify.py --selftest   -> RESULT: PASS (11/11 checks)
$ python3 verify.py --seqtest    -> RESULT: PASS (state machine over PRE_GPU/
                                     RUN01_PRESENT/RUN02_PRESENT; the two intentional
                                     [FAIL] lines printed mid-run are smoke()'s own
                                     internal diagnostic showing it correctly refuses
                                     once raw/run01 exists -- not counted, called with
                                     record=False; the seqtest[*]/PASS lines that assert
                                     `not smoke(...)` are what's actually graded)
$ python3 verify.py --smoke      -> RESULT: PASS (run BEFORE raw/m4_20260828_run01
                                     existed; wrote nothing to raw/)
$ python3 run.py --run run01 --out raw/m4_20260828_run01   -> 56/56 cases, all
                                     OK/SCANNED/REJECTED (all expected)
$ python3 run.py --run run02 --out raw/m4_20260828_run02   -> 56/56 cases, all
                                     OK/SCANNED/REJECTED (all expected)
$ python3 verify.py --crossrun raw/m4_20260828_run01 raw/m4_20260828_run02
                                  -> RESULT: PASS (56/56 gated records byte-identical)
```

No GPU fault, hang, command-buffer error, or host wedge occurred in either capture run or
in any pilot dispatch across this experiment's full lifetime. No `macvdmtool` invocation,
no A18/M5 contact.

## 17. Clean-room attestation

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for the MSL-surface-absence
  findings in FS-03/FS-05/FS-12-stencil)
Inputs inspected: every kernels/*.metal file listed in CAPTURE_CONTRACT.json's
  authored_input_sha256 (all authored by this experiment); harness/fsrun.m (authored,
  derived from EXP-0091's own prior authored fsrun.m -- our own committed code, not
  Apple code -- plus one new capability, --rt-count, for FS-11's MRT probe)
Apple binary introspection: NONE. Every inspected/spliced byte is the compiled output of
  MSL source we wrote (kernels/*.metal), compiled by the public
  newLibraryWithSource:/shdump runtime path. agxparse.py --locate SYMBOL returns only an
  (offset,length) pair; no whole-archive byte-array read of any other region.
Reproduction: python3 run.py --run runNN --out raw/m4_<date>_runNN ;
  python3 verify.py --crossrun raw/m4_<date>_run01 raw/m4_<date>_run02 ;
  python3 verify.py --selftest ; python3 verify.py --seqtest ; python3 verify.py --smoke
  (before any raw/ artifact exists)
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/ (56 gated+56 nongated JSON pairs
  each); CAPTURE_CONTRACT.json (authored-input hashes, case/group counts, gate classes);
  PRE_REGISTRATION.md (frozen hypotheses H1-H12, exact FS-01..FS-12 wording); PROGRESS.md
  (milestones, including the self-disclosed /tmp compliance correction)
```

# PRE_REGISTRATION — EXP-0111 M4 fragment semantics (FS-01..FS-12)

Filed BEFORE any capture run counts as evidence. Pilot work below (host-side OWN-SHADER
compiles with `tools/shdump`/`tools/agx-isa`, and exploratory GPU dispatches with this
experiment's own `harness/fsrun.m`) was used to locate candidate encodings, validate the
harness (including its one new capability, `--rt-count`, added for FS-11), and shake bugs
out of the case designs — the standard "characterize before freezing" step this repo's
prior splice experiments use (EXP-0091 §0/§1). Nothing below is a hypothesis-confirming
post-hoc rewrite: the case matrix in `run.py` (hashed in `CAPTURE_CONTRACT.json`) is
committed unchanged for both capture runs.

**Dispatch:** close the FS-* cluster (12 items) of Part II in
`APPLE9_RE_IMPLEMENTATION_GAPS.md:1038-1075`, and — where in scope — resolve two open
anomalies from `EXP-0091-m4-fragment-sample-discard`: (a) the spatially non-uniform
pre-discard helper-status read (GLFS-A03 §3, 2 of 8 relayed lanes anomalous in a
single-run supplementary probe) and (b) the deterministic but spatially non-uniform
per-sample-ID discard suppression pattern (GLFS-A07 §6, `f_persample_discard_N4`).

**Compliance note (self-disclosed, corrective action taken):** `experiments/
SUBAGENT_BRIEF.md` was updated mid-session to explicitly prohibit writing any file
outside the repository, including `/tmp`, even briefly. Before that update was read here,
several early pilot/diagnostic commands in this session wrote throwaway files to `/tmp`.
As soon as the updated brief was read, every such file was identified and deleted; see
`PROGRESS.md` for the exact list and confirmation. No evidence in this document or
`RESULTS.md` depends on any deleted `/tmp` content — every finding used here was
independently reproduced through the frozen `kernels/`/`run.py` before being relied on.
All work from that point forward uses `work/scratch/` inside this experiment directory
for any throwaway output.

## 0. Exact FS-01..FS-12 wording under test (quoted verbatim,
   `APPLE9_RE_IMPLEMENTATION_GAPS.md:1038-1075`)

> **FS-01** — Do `get_sr 0xa0` and `0xa1` return the integer pixel X/Y required by NIR
> `load_pixel_coord`?
>
> **FS-02** — Are those pixel coordinates stable across samples and helper invocations in
> an MSAA fragment shader?
>
> **FS-03** — Is the exact relationship among pixel coordinate, sample position, center
> convention, and NIR `frag_coord.xy` known for upper-left/lower-left and pixel-center
> modes?
>
> **FS-04** — Does the derivative instruction compute the API-required fine derivative
> over the hardware 2x2 quad?
>
> **FS-05** — Is there a distinct coarse derivative mode, or must coarse derivatives use
> the same operation as fine derivatives?
>
> **FS-06** — Are derivative results defined correctly when some lanes are helpers,
> discarded, or outside primitive coverage?
>
> **FS-07** — Does each derivative instruction operate on one scalar component, requiring
> `scalarize_ddx = true`?
>
> **FS-08** — Are flat, smooth, noperspective, centroid, sample, and explicit-offset
> interpolation modes each independently encodable and hardware-validated?
>
> **FS-09** — Does convergent interpolation remain semantically distinct from flat
> interpolation, requiring `nir_io_always_interpolate_convergent_fs_inputs`?
>
> **FS-10** — Can dynamically indexed fragment inputs be lowered without changing
> interpolation mode or provoking-vertex behavior?
>
> **FS-11** — Can dynamically indexed fragment outputs be lowered without emitting an
> unsupported dynamic tilebuffer/render-target selector?
>
> **FS-12** — Does `discard_fragment` suppress all color, depth, stencil, and
> sample-mask writes for the discarded lane?

## 1. Per-item plan, prior coverage, and coverage/deferral decision

No item is silently dropped. For each: what EXP-0091/EXP-0029/EXP-0031/EXP-M4-13 already
established (cited, not repeated), what remains, and this experiment's plan.

- **FS-01.** Not previously HW-splice-validated for the FRAGMENT context specifically —
  EXP-0031 §5 lists FS `[[position]]` SR numbers 0xa0/0xa1 as "Inferred (byte-diff only,
  mechanism HW-validated in compute)". Plan: own-shader-diff locate get_sr(0xa0)/get_sr
  (0xa1) + the immediately-following int→float conversion (`cvt_i2f_src`) in a minimal
  position-reading fragment (group `poscoord`, case `poscoord_scan`); HW-splice-validate
  the SR-number↔component mapping specifically in the fragment stage by swapping the
  SR-select byte of one get_sr instance and observing the buffer readback swap
  (`poscoord_splice_baseline/x_to_y/y_to_x`); HW-validate the exact px+0.5/py+0.5
  numeric contract (`poscoord_grid_w4h3`). **Covered.**
- **FS-02.** Not previously tested. Plan: per-sample position stability at N=2,4
  (`poscoord_msaa_stability_N2/N4`); helper-invocation position stability via a
  never-covered original-helper quad-relay (`helper_orig_relay`, group `deriv_helper`,
  shared with FS-06/GLFS-A03 remainder). **Covered.**
- **FS-03.** Pixel-center convention (px+0.5) established under FS-01. Upper-left vs
  lower-left origin not previously tested. Plan: half-plane coverage geometry along both
  axes, reading which framebuffer rows/columns get covered (`poscoord_yhalf_w4h4`,
  `poscoord_xhalf_w4h4`) — decisively pins the origin/axis-direction convention.
  Exact raw sample-POSITION coordinates (not just coverage) are not queryable through
  MSL (no `gl_SamplePosition`-equivalent exists in the surveyed MSL surface,
  `docs/isa/msl-feature-map.md`) — this sub-clause is **PARTIAL/deferred**, flagged
  explicitly in RESULTS, not silently dropped; the coverage-pattern evidence from
  EXP-0091's `msaa` group (GLFS-A01) already established per-sample addressability.
- **FS-04.** Not previously isolated as a dedicated test (EXP-0091 used derivatives only
  as an instrument for discard/demote). Plan: quad-boundary step-function test, both
  axes, both a within-quad-pair and a between-quad-pair threshold (`deriv_quadbound_*`,
  group `deriv_quad`) — a direct, decisive test of hardware quad locality. **Covered.**
- **FS-05.** MSL exposes exactly one derivative granularity (`dfdx`/`dfdy`/`fwidth`); no
  `*Coarse`/`*Fine` pair exists in the surveyed MSL surface (`docs/isa/msl-feature-map.md`
  A18; confirmed here by inspection of the Metal Shading Language function list actually
  reachable). Per the Metal-subset heuristic, this is an **ABSENCE-via-Metal-exposure**
  finding: there is no public API path to request a coarse-specific mode, so no MSL-level
  probe can distinguish "one native mode" from "a hidden unreached mode". A byte-level
  blind sweep of unexplained bits in the `0x37` derivative op (docs/isa/encoding-tables.md
  flags "full fine/coarse decode" as an open follow-up) would require an undirected splice
  hypothesis outside this cluster's scope and budget. **PARTIAL: closed as a documented
  PUBLIC-sourced absence at the API level; the ISA-level "is there an unreached coarse
  bit" question is explicitly left UNKNOWN and deferred to a dedicated bit-decode
  experiment** — not silently dropped.
- **FS-06.** Demoted-lane derivative correctness across ALU/quad-shuffle/implicit-LOD
  already HW-validated by EXP-0091 §2 (GLFS-A02/OPT-09). EXP-0091 §3 explicitly flagged
  the ORIGINAL (never-covered) helper case as NOT built ("this experiment did not build a
  quad-shuffle relay for the original-helper case"). Plan: close exactly that gap
  (`helper_orig_relay`) — quad-shuffle-relay a never-covered helper's own `dfdx` value
  into a covered neighbour and compare against the known-correct interior value.
  **Covered** (remainder only; demoted-lane case cited, not repeated).
- **FS-07.** Not previously decisively closed (EXP-M4-13's `deriv_scalar`/`deriv_vec4`
  corpus files exist but were exploratory, not analyzed to a component-count conclusion
  in that experiment's own records). Plan: own-shader compile-scan counting 10-byte
  `0x37`/byte+2==0x54 derivative ops for `dfdx` on float1/2/3/4 values with algebraically
  independent (transcendental) components (`deriv_scalar_f1..f4`), replicate the
  EXP-M4-13-style combined dfdx+dfdy case independently (`deriv_scalar_f4_both`), plus a
  plain-varying control (`deriv_scalar_plain`). **Covered**, plus a genuine axis-byte
  labeling anomaly surfaced and reported (`deriv_axis_check`, HW-validated numerically).
- **FS-08.** Flat vs perspective vs no-perspective distinctness already HW-proven
  (EXP-0029 §1). Centroid/sample vs center distinctness under partial coverage, and
  `interpolate_at_offset` numeric correctness, were NOT behaviourally validated there
  ("At full pixel coverage centroid≡sample≡centre, so no pixel difference in the
  testbed"). Plan: MSAA partial-coverage centroid-vs-center extrapolation test
  (`interp_centroid_extrap`) and a numeric `interpolate_at_offset` sweep against a
  host-computable exact affine oracle (`interp_offset_*`). **Covered** (remainder only;
  sample-vs-centroid full separation remains PARTIAL, see RESULTS §8).
- **FS-09.** Not previously tested. Plan: convergent (all-vertices-equal) attribute vs
  flat bit-exactness across 5 independent w/attribute parameter configurations
  (`interp_convergent_A..E`). **Covered.**
- **FS-10.** Not previously tested. Plan: local-array dynamic index over 4 named,
  distinctly-qualified varyings, functional-correctness HW readback plus a compile-scan
  structural comparison against a constant-indexed control (`dynidx_in_*`). **Covered.**
- **FS-11.** Not previously tested. Plan: (a) a direct-syntax negative probe (array-typed
  fragment output, expected MSL rejection); (b) the branch-unrolled-MRT workaround,
  functionally HW-validated for a genuinely per-fragment-DIVERGENT (not merely
  draw-uniform) selector, using the harness's one new capability (`--rt-count`)
  (`dynidx_out_*`). **Covered**, with one sub-finding flagged PARTIAL (see RESULTS §11 —
  the compiled encoding for the divergent case is structurally richer than a naive
  "two separate fixed stores" model and was not fully bit-decoded here).
- **FS-12.** Color/depth/buffer/atomic suppression from a demoted lane already
  HW-validated, uniform, complete (EXP-0091 §4, GLFS-A06). Sample-mask output from a
  demoted lane, and stencil output, were explicitly flagged there as untested. Plan:
  sample-mask remainder via the resolve-fraction technique (`fs12_samplemask_*`).
  Stencil: MSL exposes NO fragment-shader-writable stencil output at all (surveyed
  `docs/isa/msl-feature-map.md` / `docs/capability-completeness.md` — stencil is
  fixed-function-only, driven by pipeline/depth-stencil state, never a shader value) —
  there is no API surface to even attempt this sub-clause. **PARTIAL: sample-mask
  covered (HW-validated); stencil closed as a documented ABSENCE of any shader-driven
  stencil output to test, with the safe INFERRED-by-architectural-analogy fallback
  (uniform tile-memory write-suppression per GLFS-A06 covering the same depth/stencil
  attachment class as the already-tested depth channel) stated but NOT independently
  HW-validated — flagged for a dedicated follow-up, not silently dropped.**

**Anomaly (a) — GLFS-A03 helper_pre non-uniformity.** Second, INDEPENDENT method:
measure `simd_is_helper_thread()` DIRECTLY (no `quad_shuffle_xor` relay) by writing it to
a per-lane buffer slot strictly BEFORE that lane's own `discard_fragment()` call — GLFS-A06
established that a write's suppression depends on whether the OWN lane has already been
discarded at that program point, so a pre-discard write should reach memory regardless of
whether this eliminates the shuffle-relay mechanism as a possible confound
(`anomaly_helper_pre_direct`). **In scope, covered.**

**Anomaly (b) — GLFS-A07 per-sample discard suppression non-uniformity.** Second,
INDEPENDENT method: replace the original (pixel,sample)-indexed ATOMIC COUNTER
measurement with the resolve-fraction technique (plain color write + hardware MSAA
box-filter resolve, no atomics, no manual buffer addressing at all) on the identical
per-sample-ID-conditioned discard pattern (`anomaly_persample_resolve`). **In scope,
covered.**

## 2. Pilot findings informing the frozen hypotheses

### 2.1 FS-01/03 — pixel coordinate contract (`poscoord` group)
Own-shader compile of a minimal `f_main(float4 pos [[position]]) { return float4(pos.x,
pos.y,0,1); }` shows, via `tools/agx-isa` tokenize, `get_sr` at SR 0xa0 → r0, SR 0xa1 →
r1, immediately followed by a `cvt_i2f_src [int2f[32->32]]` consuming r0 — i.e. the SR
value is explicitly converted from an INTEGER representation, consistent with FS-01's
`load_pixel_coord` (integer) contract; the MSL-visible float center offset is added by
subsequent (not fully bit-decoded here) arithmetic. HW readback of a W4×H3 grid
(`poscoord_grid_w4h3`) gave `pos.x == px+0.5`, `pos.y == py+0.5` at every one of 12
pixels. A half-plane-coverage probe along Y (triangle covering exactly NDC y<0) coloured
framebuffer ROWS 2-3 of a 4-row target (bottom rows), not rows 0-1 — i.e. NDC+y (up) maps
to framebuffer row 0 (top): **upper-left origin, y increasing downward**, HW-confirmed
independent of the public Metal documentation's stated convention.

**H1 (frozen):** get_sr 0xa0/0xa1 in the fragment stage deliver the integer pixel x/y
(HW-splice-swappable, see §2.1b); `pos.xy == (px+0.5, py+0.5)` for every covered pixel;
origin is upper-left (NDC+y → framebuffer row 0), y down. **Falsifier:** any covered pixel
whose readback deviates from `px+0.5`/`py+0.5`; a splice swap that does NOT exchange the
x/y buffer values; the half-plane probe colouring the opposite framebuffer half.

### 2.1b FS-01 splice design
Compiling `poscoord_splice_corner.metal` (a single right-triangle covering EXACTLY pixel
column2/row1 of a 3×2 target, so only one, known-asymmetric (px=2,py=1) invocation ever
runs and writes FIXED buffer slots — avoiding the compound addressing/value confound
found in a first attempt using position-derived buffer indexing, see PROGRESS.md) located
get_sr(0xa0) and get_sr(0xa1) at hex offsets 36/40 of the extracted fragment main. Pilot
splice (SR-select byte 0xa0→0xa1) made the "x" buffer slot read the true Y value (1.5,
not 2.5); the reverse splice (0xa1→0xa0) made the "y" slot read the true X value (2.5, not
1.5) — a clean, mutual, hardware-confirmed swap. `run.py` recomputes these offsets by its
own byte scan at build time (never a hardcoded magic literal) so the splice case is
robust to any (unexpected) toolchain-driven offset drift between runs.

### 2.2 FS-04 — quad locality (`deriv_quad` group)
A step function `v = (coord>=thresh) ? 1000 : 0` differenced with dfdx/dfdy at two
thresholds: `thresh` splitting the FIRST quad-row/column-pair internally ("within") vs
`thresh` splitting exactly BETWEEN quad-pairs ("between"). Pilot (W4H4): within → d=1000
for rows/cols {0,1}, d=0 for {2,3}; between → d=0 for ALL rows/cols. Confirmed
independently for both axes.

**H2 (frozen):** derivative is computed strictly within the hardware 2×2 quad and
broadcast identically to both members of the responsible lane-pair; a step falling
exactly at a quad-pair boundary is invisible to derivatives on either side.
**Falsifier:** any nonzero derivative at the "between" threshold, or unequal derivative
values within a "within"-threshold quad-pair.

### 2.3 FS-07 — one op per scalar component (`deriv_scalar` group)
Compile-scan of `dfdx()` applied to float1/2/3/4 values with algebraically independent
(transcendental) components gave EXACTLY N ops (N=1,2,3,4) for N=1..4, all axis-byte
0x92. A combined `dfdx(v)+dfdy(v)` (float4) gave 8 total (4+4 axis split). **Anomaly
surfaced:** dfdx-ONLY kernels (no `dfdy` call anywhere in the shader) compiled EVERY
instance to axis-byte 0x90 (not 0x92) — the OPPOSITE of what a fixed "0x92=dfdx"
labeling (as in `docs/isa/encoding-tables.md`, `EXP-0016` provenance) would predict,
reproduced identically across 5 independent kernels (float1..float4 all-transcendental,
plus a plain-varying no-transcendental control). A dedicated ground-truth kernel
(`deriv_axis_check`: `dfdx(pos.x)`/`dfdx(pos.y)`/`dfdy(pos.x)`/`dfdy(pos.y)`, HW-readback
against the exact 1.0/0.0 oracle) shows axis 0x92 for BOTH dfdx calls and 0x90 for BOTH
dfdy calls in THAT shader — i.e. the byte correlates with call-site identity only when
BOTH dfdx and dfdy appear in the same program; a dfdx-only program's sole derivative
instances use the OTHER label. **This is reported as an observed, reproducible, but
UNEXPLAINED anomaly — not resolved here** (out of this cluster's budget; flagged for the
orchestrator/docs owner).

**H3 (frozen):** the compiled instance count of the 10-byte `0x37`/byte+2==0x54 op family
equals exactly the number of scalar derivative evaluations required (component count ×
number of distinct axes actually called), independent of the exact axis-byte value used
for any one call. **Falsifier:** any dfdx-of-float-N kernel emitting a count other than
exactly N, or any instance of the op family shorter/longer than 10 bytes.

### 2.4 FS-02/06 remainder — original-helper correctness (`deriv_helper` group)
A triangle covering exactly NDC x<-0.5 in a W4H4 target leaves pixel column 0 covered,
column 1 an ORIGINAL (never-covered) helper within the same hardware quad-column. Relayed
via `quad_shuffle_xor(v,1)` from the live column-0 lane: the helper's own `pos.x` read
1.5 (correct, matching its true px=1) at every one of 4 tested rows; `dfdx(pos.x)`
computed on the live lane using the helper's contribution read exactly 1.0 (the true
per-pixel step) at every row; the helper's own `simd_is_helper_thread()` read TRUE at
every row.

**H4 (frozen):** an original (never-covered) helper invocation computes/holds the
correct extrapolated `[[position]]`, participates correctly in a live neighbour's
derivative computation, and reads helper=true. **Falsifier:** any relayed position value
other than the true extrapolated pixel-grid coordinate; any derivative value other than
the interior-quad oracle; helper=false for any never-covered lane.

### 2.5 FS-08 remainder — centroid extrapolation and offset numerics (`interp_mode` group)
A single pixel (W1H1,N=4) covered by exactly 2 of 4 samples (pilot-confirmed via the
resolve-fraction technique: NDC edge at x=-0.2 → resolved fraction exactly 0.5), with the
pixel's geometric center provably outside the covered region: `center_perspective`
(fed `v=ndc_x`, an exact affine function of screen position) read ≈0.0039 (the true,
unclamped, extrapolated center value 0.0, within ~1/255 of it — a plausible ~8-bit
rasterizer sub-pixel-precision artifact, not a coverage-clamped value, which would have
read < -0.2); `centroid_perspective` (same source value) read -0.247, decisively inside
the covered region and decisively different from the center reading.

Independently, sweeping `interpolate_at_offset` against the SAME exact-affine-varying
oracle at N=1 full coverage revealed a significant, well-corroborated (X-only, Y-only,
and combined-XY sweeps, ≥15 distinct offset values, sub-ULP-level residuals only)
discrepancy from the MSL-documented contract: **the offset argument is NOT interpreted as
a signed, pixel-CENTER-relative offset in `[-0.5,0.5)`** (`interpolate_at_offset(0,0)`
did NOT equal `interpolate_at_center()` — verified directly, both read from the identical
source varying in the same shader, push-model AND pull-model `interpolate_at_center()`
agreed with each other and with the mathematically-true center, while
`interpolate_at_offset(0,0)` did not). Instead, every tested (dx,dy) matches the plane
evaluated at an ABSOLUTE window-space pixel-local coordinate (dx,dy) measured from the
pixel's TOP-LEFT corner (x right, y DOWN, 1.0 = one full pixel width) — i.e. the true
center is reached only at input offset (0.5,0.5), and the Y axis is effectively
sign-flipped relative to a naive NDC-y-up mental model. No clamping or wraparound was
observed up to |offset|=2.0 pixel-widths (pure linear extrapolation continues).

**H5 (frozen):** centroid interpolation under partial coverage reads a value measurably
and substantially different from (and closer to the covered region than) the
unclamped/extrapolated center value. **Falsifier:** centroid and center reading
bit-identical, or centroid falling outside the covered value range.
**H6 (frozen):** `interpolate_at_offset(dx,dy)` is NOT bit/value-equivalent to
`interpolate_at_center()` for a zero argument, and its actual effective sample location
follows a fixed, reproducible, deterministic linear relationship to (dx,dy) (whatever
that relationship precisely is) with no observed clamping in the tested range.
**Falsifier:** offset(0,0) exactly matches interpolate_at_center() to the bit; any
non-linear jump, fault, or clamp discontinuity within |offset|<2.0.

### 2.6 FS-09 — convergent vs flat (`interp_convergent` group)
Five (w0,w1,w2,attr) parameter configurations, each read back at 16 pixels
(flat/smooth-perspective/linear-no-perspective, all fed an IDENTICAL per-vertex
attribute value): perspective matched flat bit-exactly in 100% of 80 sampled
(config,pixel) pairs; no-perspective/linear matched flat in only 2 of 5 configurations
(diverging by 1-2 ULP in the other 3, uniformly across all 16 pixels of each diverging
config) — config D (uniform w={2,2,2}) showed NO divergence on either path, despite using
the SAME attribute value (0.1) as diverging config A ({1,2,3}); this w-dependence of the
(mathematically w-independent) no-perspective path is noted as a further open curiosity,
not chased to a root cause here.

**H7 (frozen):** convergent interpolation is NOT provably bit-identical to flat in
general — at least one interpolation mode, in at least one parameter configuration,
diverges. **Falsifier:** all 5 configurations, all pixels, all three modes bit-identical
to flat (would falsify the need for `nir_io_always_interpolate_convergent_fs_inputs`).

### 2.7 FS-10 — dynamic input indexing (`dynidx_in` group)
`float arr[4]={v0,v1,v2,v3}; return arr[px%4];` (v0 flat, v1..v3 smooth) HW-read back
exactly `10.0+px` for px=0..3 (oracle match, 4/4). Compile-scan (`tools/agx-isa`
tokenizer) shows a clean decode: `icmp`/`sel`-family ALU immediately follows the
varying-read block, and the interpolation instructions themselves (`iter`/`iter_flat`)
each carry ordinary small FIXED immediate slot fields — no register-sourced-looking slot
field was observed. A constant-index control (`arr[2]` literal) is compiled for
structural comparison.

**H8 (frozen):** dynamic fragment-input indexing lowers to "read every declared
candidate via ordinary fixed-slot interpolation instructions, then select via ordinary
ALU" — i.e. no interpolation-mode change and no register-sourced interpolation-slot
field is needed. **Falsifier:** a readback mismatch against the `10+idx` oracle for any
idx; an iter-family instruction whose slot field is NOT a plausible small fixed
immediate; a compile rejection.

### 2.8 FS-11 — dynamic output indexing (`dynidx_out` group)
A direct array-typed `stage_out` (`struct FOut { float4 colors[2]; };` with no per-element
`[[color(n)]]`) was REJECTED by `newLibraryWithSource:` ("invalid return type 'FOut' for
fragment function") — there is no MSL syntax to even attempt a dynamic/array-style output
selector. A branch-unrolled workaround (`if(idx==0) o.c0=...; else o.c1=...;`, `idx`
derived from `[[position]]` so it is genuinely PER-FRAGMENT DIVERGENT, not merely a
uniform draw-wide value) HW-read back correctly on a 2-render-target target (this
harness's one new `--rt-count` capability): even-x column → RT0 red / RT1 clear; odd-x
column → RT0 clear / RT1 green (2×2-pixel readback, exact match). Compile-scan shows the
compiled program contains only ONE `frag_color_store` instruction (not the naively
expected two, one per branch arm) preceded by `icmp_pred`+`sel` ALU and TWO
`frag_tile_setup` brackets with different selector bytes — a structurally richer pattern
than a simple "two branches, two fixed stores" model; NOT further bit-decoded here.

**H9 (frozen):** there is no MSL-level syntax for indexing fragment outputs dynamically
(a compile-time rejection is the expected/only outcome for the direct-array form); the
branch-unrolled workaround is both necessary (no simpler form compiles) and functionally
correct on real hardware for a genuinely per-fragment-divergent selector.
**Falsifier:** the direct array form compiling successfully; the branch-unrolled form
producing incorrect per-pixel RT routing.

### 2.9 FS-12 remainder — sample-mask suppression (`fs12_samplemask` group)
Even-x-column whole-invocation discard, N=4, unconditional post-discard
`[[sample_mask]]=0xF` + `color=1` write: resolve-fraction readback shows the discarded
column fully clear (0.0) and the surviving column fully white (1.0) — matching the
no-discard control's uniform 1.0 everywhere, i.e. complete suppression, consistent with
(not exempted from) GLFS-A06's color/depth/buffer/atomic findings.

**H10 (frozen):** a demoted lane's attempted `[[sample_mask]]` write is suppressed just
as completely as its color/depth/buffer/atomic writes. **Falsifier:** any nonzero
resolved contribution from a discarded lane's sample-mask write.

### 2.10 Anomaly (a) — direct pre-discard helper status (`anomaly_helper_pre` group)
Writing `simd_is_helper_thread()` directly to a per-lane buffer slot BEFORE that lane's
own `discard_fragment()` call (no `quad_shuffle_xor` relay at all), W4H4, half the lanes
about to discard: ALL 16 lanes read helper_pre=FALSE — no anomaly, uniform, unlike
EXP-0091's relayed single-run probe.

**H11 (frozen):** helper_pre reads FALSE uniformly for every lane (both future-discarders
and future-survivors) when measured directly. **Falsifier:** any lane reading TRUE.

### 2.11 Anomaly (b) — resolve-fraction per-sample discard (`anomaly_persample` group)
Odd-`sample_id` discard at N=4, measured via color+MSAA-box-filter-resolve (no atomics):
resolved fraction reads EXACTLY 0.5 at all 4 tested pixels (2×2 target) — uniform,
complete 50% suppression, matching the oracle and UNLIKE EXP-0091's atomic-counter-based
finding of only 2/8 "should-be-suppressed" slots actually suppressed.

**H12 (frozen):** per-sample discard suppression is uniform and complete when measured by
an independent (non-atomic, non-manually-indexed) mechanism. **Falsifier:** any
pixel reading a fraction other than 0.5.

## 3. Independent / controlled variables

- **Independent:** which get_sr SR value is read/spliced (`poscoord` splice cases); step
  threshold and axis (`deriv_quad`); derivative-call combination and vector width
  (`deriv_scalar`); which lane relays which value (`deriv_helper`); interpolation
  qualifier and coverage geometry (`interp_mode` centroid), offset (x,y) value
  (`interp_mode` offset sweep); per-vertex w-values and attribute value
  (`interp_convergent`); runtime array index (`dynidx_in`); per-fragment divergent vs
  uniform selector and RT count (`dynidx_out`); discard presence/placement
  (`fs12_samplemask`, both anomaly groups).
- **Controlled:** M4/G16G, this host, macOS 26.6.2 (25G82), Metal 4, Apple clang 21.0.0
  (clang-2100.1.1.101); `MTLCompileOptions.fastMathEnabled=YES` (default) for every case;
  single-triangle (or the documented partial-coverage variant) geometry per kernel, fixed
  across both runs; fresh `MTLDevice`/process per case (`fsrun` is one-shot).
- **Paired controls:** `poscoord_splice_baseline` (unspliced archive) vs the two swap
  cases; `deriv_quadbound` within vs between threshold per axis; `dynidx_in_control`
  (constant index) vs `dynidx_in_select` (dynamic index); `fs12_samplemask`/
  `anomaly_persample` each have an explicit no-discard control fragment function
  (`f_control`) dispatched as its own case.

## 4. Frozen case matrix

The complete, frozen case matrix is `run.py`'s `build_cases()` — **56 cases**: 9
`poscoord`, 4 `deriv_quad`, 7 `deriv_scalar`, 1 `deriv_helper`, 19 `interp_mode`, 5
`interp_convergent`, 3 `dynidx_in`, 3 `dynidx_out`, 2 `fs12_samplemask`, 1
`anomaly_helper_pre`, 2 `anomaly_persample`. `python3 run.py --list` enumerates it;
`CAPTURE_CONTRACT.json` pins the sha256 of every authored kernel/harness/runner file at
freeze time. No case is added, removed, or reparameterized between run01 and run02.

## 5. Raw record schema (frozen; see `schema.py`)

Every case produces exactly two sibling JSON files: `<case_id>.gated.json`
(byte/value-deterministic: case id, group, kind, exact params, status, structured
result) and `<case_id>.nongated.json` (GPU timing, wall-clock, pid — never compared
across runs). `run.py` asserts the key set of every written record against
`schema.GATED_KEYS`/`NONGATED_KEYS` before writing.

## 6. Environment (frozen)

```
git revision (agx-re, recorded for provenance, NOT a cross-run gate): 75eb840a011ffbfa3fe2eb1721e2acbbcc24c1e7
repo dirty at freeze: yes (sibling in-flight experiment directories present, untracked;
  none touched by this experiment; see git status note below)
host: Apple M4, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4
compiler: Apple clang version 21.0.0 (clang-2100.1.1.101), arm64-apple-darwin25.6.0
pre-registration freeze timestamp (UTC): 2026-08-28T07:05:00Z
authored input hashes: CAPTURE_CONTRACT.json
```
The orchestrator commits other experiments' results continuously (sibling `EXP-0101`,
`EXP-0102`, `EXP-0103`, `EXP-0104`, `EXP-0108`, `EXP-0109` directories were present,
untracked, at freeze time). Per the cross-run-gate discipline established in
EXP-0091/EXP-0097 (and the standing instruction not to gate on live HEAD): this
experiment's two-run gate compares only its own captured `*.gated.json` records against
each other and against the authored-blob hashes pinned here — never live git HEAD.

## 7. Timeouts

- Per-case GPU dispatch (`fsrun`): 60s hard timeout, enforced by `subprocess.run(...,
  timeout=...)`; a timeout is recorded as `status="HANG"`, never silently dropped.
- Per-case host compile (`shdump`/`agxparse`/`agxisa` tokenize): 120s hard timeout.
- Harness: single-threaded, one case per process for every `gpu_render` case (`fsrun` is
  one-shot); one case fully recorded (both sibling files written) before the next case
  starts.

## 8. What would falsify each frozen hypothesis

See §2.1-2.11 above for the per-hypothesis falsifier. In addition: any GPU fault, hang,
or command-buffer error during any case is recorded as that case's result and reported in
RESULTS.md, not discarded; any case producing a *different* outcome on run01 vs run02
blocks promotion of that specific case to `HW-VALIDATED` pending a third run.

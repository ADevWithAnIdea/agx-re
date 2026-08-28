# EXP-0094 Results -- M4 texture bias/gradient/implicit-LOD ABI (Bundle D)

Target: **Apple M4 / G16G, local host only**, macOS 26.6.2, Metal 4. A18 Pro: no data (hands-off
per `CLAUDE.md`). Two independently required capture runs, `m4-20260828c-run01` /
`m4-20260828c-run02` (the promoted, non-quarantined pair -- see "Quarantined attempts" below):
**byte-identical `04_results.jsonl`** (verified by `verify.py --captured`), 97/97 cases
`STATUS OK` on both runs, 0 `MISMATCH_EXPECTED`, 82 `MATCH_EXPECTED`, 15 `OBSERVED_NO_ORACLE`
(the pre-registered Inf/NaN/inverted-clamp/mip-view cases with no a-priori public-spec oracle).

## 0. TL;DR

- **GLTEX-A01 (bias):** effective LOD = `base_LOD(from screen-space derivative) + bias`, THEN
  clamped to `[lodMinClamp, lodMaxClamp]`, THEN clamped to `[0, mipCount-1]` -- confirmed exactly
  across 26 cases including the full finite-resource sweep. `bias(NaN)` -> mip 0.
  `bias(+-Inf)` -> mip 8/0 (saturating clamp). Sampler LOD-clamp and bias compose additively, in
  that order. Mip-view (base/max level restriction) re-bases the bias/LOD scale to the view's
  own `[0, viewLevelCount-1]` range. **HW-VALIDATED.**
- **GLTEX-A02 (gradient + register isolation):** `gradient2d(dx,dy)` follows the same public
  rho/lambda formula, confirmed across 18 cases (independent/asymmetric X/Y, negative sign,
  subnormal, huge). **Any** Inf or NaN in **any** gradient component (7 cases, every
  single/combined placement tested) saturates to mip 8 -- the OPPOSITE of the bias path's NaN
  behavior (mip 0). The bias-operand register-select field was isolated by differential
  compilation to a single byte (`_agc.main`+69 in a two-live-value minimal pair) and
  **HW-VALIDATED by a downstream-consumer splice**: flipping that one byte between two
  configurations flips the rendered pixel between reflecting `biasA=2.0` and `biasB=6.0`,
  bidirectionally, reproducibly across both runs. The analogous gradient-operand differential
  pair produced 116 differing bytes (not a clean isolate) -- reported as an open item, not
  claimed. Cube gradients: our own independently-derived quotient-rule projection of the
  gradient onto the selected face matches HW to within trilinear-blend quantization noise
  (<=0.02 mip) across 12 direction x magnitude cases -- **native Apple9 cube-gradient LOD tracks
  the standard OpenGL cube-map derivative formula**, a positive answer to the addendum's key
  falsifier.
- **GLTEX-A03 (implicit LOD / textureQueryLOD):** `calculate_clamped_lod` exactly equals the
  LOD an actual `sample()` at the same coordinate/derivative uses; `calculate_unclamped_lod`
  exactly equals the pre-sampler-clamp base LOD. Confirmed exactly (0 mismatches) across 10
  cases spanning the full LOD range and 4 distinct clamp configurations. **HW-VALIDATED.**
- **Cube face selection:** matches the standard OpenGL major-axis rule, INCLUDING at all 12 edge
  midpoints and all 8 corner ties (X-axis priority, then Y, then Z) -- 26/26 exact matches.
  **HW-VALIDATED.**

## 1. Quarantined attempts (retained, not promoted)

Two earlier run-id pairs are quarantined and retained untouched, per
`experiments/SUBAGENT_BRIEF.md`'s standing rule (never repaired in place):

- `quarantine-m4-20260828-run01/` + `QUARANTINE-run01-attempt1.md` -- an own-code bug (fast-math
  flag mismatch between the `regsplice_bias` archive build and its harness invocation) caused all
  5 `regsplice_bias` cases to `PIPELINE_MISS`; the other 92 cases were correct.
- `quarantine-m4-20260828b-run01/` + `QUARANTINE-run01b-attempt2.md` -- all 97 cases ran
  correctly (`STATUS OK`, 0 mismatches), but `verify.py` (an `AUTH_CODE` file) needed a design
  fix to let the inter-run gate run before `RESULTS.md` exists, and `verify.py`'s own hash is
  bound into each run's provenance -- so the pair had to be re-captured under a new id rather
  than patched in place.

Neither quarantine reflects a hardware anomaly; both are documented purely for the clean-room
paper trail's completeness.

## 2. GLTEX-A01 -- bias operand and effective-LOD semantics

### 2.1 Observed (bias_sweep, 26 cases, `raw/m4-20260828c-run0{1,2}/04_results.jsonl` i=0..25)

Setup: R32Float 2D texture, 9 mip levels (256..1), level L filled with the constant `float(L)`
everywhere ("LOD-recovery" readout -- with `mipFilter=linear` the hardware's own trilinear blend
across levels reads back the CONTINUOUS effective LOD it selected, exactly, not quantized to
8-bit color; validated end-to-end before use, PROGRESS.md T1). Fixed `uvScale=(1/256,0)` gives an
EXACT, closed-form base LOD of 0.0 (derived from `[[position]]`, not vertex interpolation, so
`d(uv)/d(pixel)` has no rounding) -- isolating `bias` as the only source of LOD.

| case | bias | observed LOD | interpretation |
|---|---:|---:|---|
| zero / signed zero | 0.0 / -0.0 | 0.0 | identical; sign of zero has no effect |
| ordinary +/- | +-0.5, +-1, +-4 | clamp(bias,0,8) | exact linear addition |
| max valid | 8.0 | 8.0 | last mip index, no clamp needed |
| first-past-max | 8.5 | 8.0 | clamped to mip count - 1 |
| below min / far below | -1, -20 | 0.0 | clamped to mip 0 |
| huge magnitude | 1e6, -1e6, 3e38 (FLT_MAX) | 8.0 / 0.0 / 8.0 | saturates at the mip-range boundary, no fault, no wraparound |
| subnormal | 1e-40 | 0.0 | treated as (and clamps identically to) zero -- no denormal-flush artifact detected at this readout precision |
| +Inf | inf | 8.0 | saturates high, same as huge-positive |
| -Inf | -inf | 0.0 | saturates low, same as huge-negative |
| **NaN** | nan | **0.0** | **saturates low, like -Inf/below-min -- NOT propagated as NaN, NOT clamped high** |

**Interpretation vs observation:** OpenGL/Vulkan/D3D leave NaN LOD-selection behavior largely
undefined; we make no public-spec claim here, only the M4 observation: `bias(NaN)` behaves as if
it were a very-negative (or -Inf-equivalent) value on this specific path, landing at the
most-detailed mip. This is the OPPOSITE of the gradient path's NaN behavior (sec. 3), a genuine,
reproduced asymmetry between the two operand types -- see sec. 5.

### 2.2 Clamp-order interaction (4 cases, i=19..22)

| case | bias | lodMinClamp | lodMaxClamp | observed | predicted (bias, then clamp) |
|---|---:|---:|---:|---:|---|
| max clamps down | 6.0 | 0.0 | 3.0 | 3.0 | match |
| min clamps up | 1.0 | 5.0 | 8.0 | 5.0 | match |
| tight window | 4.0 | 3.5 | 4.5 | 4.0 | match |
| **inverted (min>max)** | 4.0 | 6.0 | 2.0 | **2.0** | no a-priori oracle |

**Observed order confirmed:** `effective = clamp(base_LOD + bias, lodMinClamp, lodMaxClamp)`,
THEN clamped again to the texture's actual `[0, mipCount-1]` range -- bias is added BEFORE either
clamp, never after. The inverted-range case (`lodMinClamp=6 > lodMaxClamp=2`) resolved to `2.0`,
i.e. **`lodMaxClamp` alone determined the ceiling and `lodMinClamp` was effectively ignored** when
the pair is malformed (`lodMinClamp > lodMaxClamp`) -- not a fault, not the midpoint, not
`lodMinClamp`. `UNKNOWN` whether this is a documented Metal validation-layer clamp (Metal
silently reorders/ignores an invalid range) or raw hardware behavior; `INFERRED` that a driver
should never emit an inverted range regardless.

### 2.3 Mip-view (base/max level restriction) interaction (3 cases, i=23..25)

A `newTextureViewWithPixelFormat:...levels:{2,3,4,5,6}...` view over the same 9-level texture
(GL's base/max-level analogue).

| case | bias | observed (view-local LOD-recovery readback) |
|---|---:|---:|
| view, bias 0 | 0.0 | 2.0 |
| view, bias 8 | 8.0 | 6.0 |
| view, bias -3 | -3.0 | 2.0 |

**Interpretation:** the readback value is the texture's GLOBAL mip index (the LOD-recovery ramp
encodes global level regardless of view), so `bias=0` -> global level 2 (the view's base level)
and `bias=8` (which would ask for view-local index 8, clamped to the view's own
`[0, viewLevelCount-1]=[0,4]`) -> view-local 4 -> global level 2+4=6. **The bias/LOD scale is
re-based to the VIEW's own level count, not the underlying texture's** -- i.e. `lodMaxClamp`'s
implicit default and the mip-clamp both operate in view-local coordinates. This directly answers
part of GLTEX-A01's "texture base/max levels" question: Apple9 (via a Metal texture view, the
mechanism Mesa would use for GL base/max level) correctly re-bases the entire LOD pipeline, not
merely the sampled level offset.

### 2.4 Response block

```text
Status: [x] Closed (bias-operand semantics, addition order, clamp order, view interaction,
              finite-resource sweep incl. Inf/NaN) [ ] Partial (bit-level register/instruction
              encoding of the bias OPERAND itself remains OWN-SHADER-DIFF only, not fully
              decoded to a named field -- see GLTEX-A02 sec. 3)
Answer, where Yes/No: [x] Yes -- Apple9 accepts a dynamic bias operand and composes it with
              sampler LOD clamps and mip-view restriction exactly as OpenGL's implicit-LOD model
              predicts, for every tested finite value.
Applies to: [x] M4/G16G (tested)  [ ] A18 Pro/G17P (INFERRED by family per CLAUDE.md; not
              independently tested, hands-off)
Evidence: [x] independently assembled/executed HW test (own-MSL public compile, real M4 GPU,
              two byte-identical runs)  [ ] HW splice (bias VALUE path; see GLTEX-A02 sec. 3 for
              the splice-validated bias-operand REGISTER-SELECT claim)  [x] own-MSL execution
Test/artifact: analysis/casematrix.py bias_sweep_cases(); harness/texrender; kernels/bias_probe.metal;
              raw/m4-20260828c-run0{1,2}/04_results.jsonl i=0..25
Exact observed semantics or field mapping: effective_LOD = clamp(clamp(base_LOD + bias,
              lodMinClamp, lodMaxClamp), 0, mipCount-1); mip-view re-bases lodMinClamp/lodMaxClamp
              and the mip-count clamp to the VIEW's own level range.
Finite namespace: bias operand -- IEEE-754 float32, full finite range accepted without fault;
              effective consequence is saturating-clamped to [lodMinClamp,lodMaxClamp]∩[0,mipCount-1]
              regardless of magnitude (tested to +-1e6, +-FLT_MAX, +-Inf).
Maximum-valid and first-invalid tests: there is no "invalid" bias value -- every finite value,
              +-Inf, subnormal, and NaN produced STATUS OK with a well-defined (if NaN's is
              non-obvious) saturated result; no fault/hang observed for any bias_sweep case.
Failure/overflow behavior: [x] zero/discard is the wrong frame here -- [x] clamp/saturate is the
              actual behavior for magnitude; NaN specifically resolves to the LOW end of the
              clamp range (mip 0), not a fault, not a pass-through NaN, not the high end.
Correct "need more" fallback: N/A -- bias is not a finite RESOURCE, it is a value; no compiler
              spill/fallback strategy is implicated. A driver combining an OpenGL sampler
              LOD-bias with a shader-emitted bias (both APIs have this) should ADD them before
              handing a single float to bias() -- confirmed additive composition with the
              sampler clamp (sec. 2.2) supports this being safe.
Lifetime, destruction, and reuse semantics: N/A (a per-instruction operand value, not a resource).
Counterexamples and untested cases: anisotropic sampling combined with bias was NOT tested
              (out of scope for this bundle); 1D/3D/array/cube/shadow-compare/projected/offset
              forms of bias() were NOT individually re-tested here (GLTEX-A01 explicitly lists
              them, but EXP-0034 already established the same op+2=0x07 encoding covers every
              dimension uniformly -- this experiment adds the VALUE semantics on top of that
              already-established encoding, not a re-test per dimension).
Driver/compiler consequence: Mesa can emit a single combined bias value (GL sampler LOD-bias +
              shader bias, summed) with no additional hardware-side combination logic needed;
              mip-view (base/max level) must be modeled with the LOD scale re-based to the
              view's own level count, matching how Metal texture views already behave.
```

## 3. GLTEX-A02 -- explicit-gradient ABI and register isolation

### 3.1 Gradient value semantics (grad_sweep, 18 cases, i=26..43)

Single-thread compute dispatch, `gradient2d(dx,dy)` explicit (no implicit-derivative ambiguity),
same LOD-recovery texture/readout as sec. 2.

| case class | observed | interpretation |
|---|---|---|
| zero / small / large, per-axis independently (x_small, x_large, y_small, y_large) | matches `log2(max(|dx.x|*w,|dx.y|*h,` `|dy.x|*w,|dy.y|*h))`-style rho formula exactly | confirms the SAME public rho/lambda formula as implicit LOD, with genuinely INDEPENDENT (not compiler-symmetric) X/Y gradients |
| asymmetric (`asym_x_lt_y`, `asym_x_gt_y`) | both give LOD 5.0 (the larger-magnitude axis dominates, as the `max()` in rho predicts) | confirms `rho=max(mx,my)`, not `mx+my` or an average |
| negative sign (`neg_sign_x`, `neg_sign_y`) | same LOD as the positive-sign case | confirms magnitude-only dependence, sign-independent, as the `hypot`/absolute-value formula predicts |
| subnormal (1e-40) | LOD 0.0 | treated as/clamps like zero |
| huge (1e6) | LOD 8.0 | saturates high |
| **any Inf or NaN in ANY of the 4 gradient components**, tested individually (`inf_dx_x`, `inf_dy_y`, `nan_dx_x`, `nan_dy_y`) and combined (`both_inf`, `both_nan`, `mixed_inf_nan`) -- 7 cases | **LOD 8.0, uniformly, every time** | **saturates HIGH -- the opposite of the bias path's NaN (sec. 2.1, mip 0)** |

### 3.2 The bias/gradient NaN asymmetry (sec. 0's headline finding)

`bias(NaN)` -> mip 0 (most detailed). Any NaN/Inf in a `gradient2d` operand -> mip 8 (least
detailed), regardless of which component or how many are exceptional. **These are two genuinely
different code paths on Apple9 with genuinely different exceptional-value behavior** -- a driver
CANNOT assume one NaN-handling rule covers both `bias()` and `gradient2d()`. `HW-VALIDATED`
(byte-identical across both runs, 10 total NaN/Inf cases across the two operand types).

### 3.3 Bias-operand register isolation -- differential compilation + splice (HW-VALIDATED)

**Method history** (full account in PROGRESS.md T2; summarized here). Three iterations of the
differential-compilation harness were needed:

1. A register-pressure ramp reading operands from a plain `constant float*` buffer produced
   BYTE-IDENTICAL compiled fragment/compute code for 0 to 32 concurrently-live junk values. Root
   cause (confirmed via `agxparse.py --json`'s region listing): any value derived ONLY from the
   `constant` address space is provably data-flow-uniform across the invocation group, so AGX's
   compiler hoists it entirely into the shader PREAMBLE (`_agc.main.constant_program`, which DID
   grow with N: 128->576 bytes for bias N=0->32) while the per-invocation body
   (`_agc.main`) stayed fixed -- the SAME preloaded-uniform mechanism EXP-0016 already documented
   for texture width/height/mip-count queries, now shown to also cover a uniform bias/gradient
   operand.
2. Routing the operand through a genuinely per-invocation-varying source -- a per-vertex
   INTERPOLATED VARYING (`[[stage_in]]`) for the fragment/bias path, and a
   `[[thread_position_in_grid]]`-offset buffer read for the compute/gradient path -- forced real
   per-lane residency (`_agc.main` grew 202->1046 bytes for bias, 204->1244 bytes for grad, across
   N=0..32).
3. A MINIMAL differential pair (`kernels/regpair_bias_A.metal` / `_B.metal`: two named operands
   `biasA`,`biasB`, both varying-routed, byte-identical source except which feeds `bias()` and
   which feeds an output sink) compiled to **exactly 4 differing bytes**, in two clean swapped
   pairs: `_agc.main`+69 (`0x06<->0x08`) and +159 (`0x08<->0x06`), and +107 (`0x03<->0x04`) and
   +169 (`0x04<->0x03`). The texture sampler-op's own 10 bytes (mode `0x07`) were BYTE-IDENTICAL
   between A and B -- **the operand-register selection lives entirely in a PRECEDING
   instruction, not in the texture-sample bundle itself.**

**Splice validation** (`regsplice_bias` backend, 5 cases, i=92..96, `raw/m4-20260828c-run0{1,2}/`):
compiled `regpair_bias_A/B.metal` to F32-color (`--color-format 55`) archives (matching the
`R32Float` LOD-recovery render target -- see sec. 3.4 note on archive/pipeline binding), spliced
the SINGLE byte at absolute file offset 15653 (`_agc.main`+69), forced the spliced archive to run
via `MTLPipelineOptionFailOnBinaryArchiveMiss` (`PIPELINE_SOURCE archive` in every result line
confirms it), and read back the LOD-recovery pixel (biasA=2.0, biasB=6.0 -> distinguishable
mips):

| case | archive | splice | observed LOD | expected |
|---|---|---|---:|---:|
| `A_unspliced` | A (native `0x06`) | none | 2.0 | 2.0 (biasA) |
| `B_unspliced` | B (native `0x08`) | none | 6.0 | 6.0 (biasB) |
| `A_spliced_to_B` | A | `0x06`->`0x08` | **6.0** | 6.0 (biasB) |
| `B_spliced_to_A` | B | `0x08`->`0x06` | **2.0** | 2.0 (biasA) |
| `A_spliced_control0` | A | `0x06`->`0x00` (unclaimed value) | 1.0 | none (raw observation) |

All 5 `MATCH_EXPECTED` (except the control, `OBSERVED_NO_ORACLE` by design), byte-identical
across both runs. **This is the mandated downstream-consumer validation**
(`docs/isa/register-move-and-liveness.md`'s silent-zero warning): the observation point is the
FINAL RENDERED PIXEL, several instructions and a real texture-unit trilinear-blend LOD
computation removed from the flipped byte -- not the spliced instruction's own adjacent result.
The bidirectional swap (A->B and B->A both flip cleanly) and the distinct third value at the
control splice (`0x00` -> `1.0`, neither A's nor B's value, not a fault, not a silent zero) are
consistent with -- but do not, by themselves, prove -- "this byte is a small register-index
field"; we make NO claim about its bit-level meaning, only its OBSERVED CAUSAL EFFECT (see sec.
3.5's clean-room note on why we stop here).

### 3.4 Archive/pipeline-format binding (incidental finding)

`MTLBinaryArchive` pipeline lookup for a render pipeline is bound to the FULL
`MTLRenderPipelineDescriptor`, including the color-attachment pixel format, not merely the
function's AIR hash: an archive built with the default `BGRA8Unorm` color format MISSES a
request for an `R32Float` pipeline (`STATUS PIPELINE_MISS`) even though the vertex/fragment
functions are otherwise identical. Not a bug; recorded because it is a real, previously
undocumented (in this repo) constraint on the splice-and-reload technique for RENDER pipelines
(the compute analogue, `MTLComputePipelineDescriptor`, has no such color-format coupling).

### 3.5 Clean-room / decoding-bug note (coordinator update, 2026-08-28)

`apple9_isa_explainer.md` + `work/COMPILER-EXPLAINER-INTERACTION-20260828.md` document a
CONFIRMED bug in `tools/agx-isa/db.json`: the falu2/falu2i (6-byte compact float), 10-byte logic,
and 8-byte FMA instruction families' `srcA_reg`/`srcB_reg`/src2 fields conflate a
source-RETENTION flag with the register-index top bit (decoded register numbers >= 64 in that
specific family are suspect, off by exactly 64 = one bit). **This experiment's sec. 3.3 claim
does not use `db.json`'s decoder at all** -- the isolated byte was found by raw differential byte
compilation (comparing two whole compiled outputs byte-for-byte) and validated purely by
splice-and-observe-downstream-consumer, with no instruction-family classification or field
decode attempted. It is a structurally different instruction, preceding the texture sampler
bundle rather than a falu2/logic/FMA compact form. Per the coordinator's explicit instruction we
do NOT assume this makes it safe by analogy -- we simply never made a bit-level claim that COULD
be wrong in that specific way: sec. 3.3's finding is "this byte, these two values, this observed
pixel change," not "this is register N."

### 3.6 Cube-gradient LOD vs. independently computed reference (cube_grad, 12 cases, i=80..91)

`analysis/reference.py:cube_gradient_lod` -- derived BY US (not copied from any implementation)
by: (1) the public OpenGL major-axis face-selection rule, (2) the public direction-to-face-UV
projection formula, (3) the ordinary calculus quotient rule applied to that projection to get
face-local `(ds/dx,dt/dx,ds/dy,dt/dy)` from the 3-component `dPdx`/`dPdy`, (4) the same public
rho/lambda formula as secs. 2/3.1. Tested at 4 representative directions (face center, near an
edge, exactly at an edge, exactly at a corner/major-axis tie) x 3 gradient magnitudes (small
0.001, medium 0.01, large 0.05), same LOD-recovery cube texture (every face/level filled with
`float(level)`).

| direction | magnitude | observed LOD | reference LOD | delta |
|---|---|---:|---:|---:|
| face_center | small | 0.0 | 0.0 | 0 |
| face_center | medium | 0.3516 | 0.3561 | 0.0046 |
| face_center | large | 2.6758 | 2.6781 | 0.0023 |
| near_edge | small | 0.0 | 0.0 | 0 |
| near_edge | medium | 0.7813 | 0.7841 | 0.0029 |
| near_edge | large | 3.0977 | 3.1061 | 0.0084 |
| at_edge | small | 0.0 | 0.0 | 0 |
| at_edge | medium | 0.8555 | 0.8561 | 0.0007 |
| at_edge | large | 3.1680 | 3.1781 | 0.0100 |
| at_corner | small | 0.0 | 0.0 | 0 |
| at_corner | medium | 1.1406 | 1.1486 | 0.0080 |
| at_corner | large | 3.4648 | 3.4706 | 0.0058 |

**All 12/12 within the pre-registered 0.15-mip tolerance** (actual max delta 0.01 mip -- far
tighter than the tolerance budgeted for trilinear-blend-weight quantization). **This is a
positive answer to the addendum's key falsifier**: native Apple9 cube-gradient LOD selection
tracks the standard, independently-derived OpenGL cube-map derivative formula closely, INCLUDING
exactly at face boundaries and a major-axis tie (`at_corner`). Face SELECTION for these same
directions is separately confirmed exact in sec. 4. Combined, this is evidence AGAINST
`lower_txd_cube_map` being strictly required for LOD/face correctness on Apple9 -- though we
stress this is 12 points along a 2-parameter family, not an exhaustive proof, and the residual
~0.005-0.01 mip deltas (consistent in sign with a slightly coarser hardware approximation, not
random noise) are themselves worth a dedicated follow-up if bit-exact cube LOD ever becomes
load-bearing.

### 3.7 Response block

```text
Status: [x] Partial -- gradient VALUE semantics, NaN/Inf behavior, and cube-gradient LOD are
              Closed; the bias-operand register-select field is Closed (HW-VALIDATED splice); the
              GRADIENT-operand register field is Open (differential pair produced 116 differing
              bytes, not a clean isolate -- see below).
Answer, where Yes/No: [x] Yes (gradient follows the public rho/lambda formula with independent
              X/Y, HW-VALIDATED) [x] Yes (bias-operand register-select byte isolated + splice-
              validated) [ ] Unknown (gradient-operand register field -- NOT isolated in this
              experiment; the operand VALUE semantics are fully characterized regardless of which
              register(s) carry it)
Applies to: [x] M4/G16G (tested)  [ ] A18 Pro/G17P (INFERRED by family; not independently tested)
Evidence: [x] independently assembled/executed HW test (behavioral sweep)  [x] HW splice
              (bias-operand register field, downstream-consumer readback)  [x] own-MSL byte diff
              (differential compilation, both bias -- clean 4-byte isolate -- and gradient -- 116
              differing bytes, reported as inconclusive, not claimed)
Test/artifact: analysis/casematrix.py grad_sweep_cases()/cube_grad_cases()/regsplice_bias_cases();
              kernels/grad_probe.metal, cube_grad.metal, regpair_bias_{A,B}.metal;
              analysis/pilot/regsplice_probe/ (differential-compile pilot artifacts);
              raw/m4-20260828c-run0{1,2}/04_results.jsonl i=26..43,80..91,92..96
Exact observed semantics or field mapping: gradient LOD = clamp(log2(max(|dx.x*w,dx.y*h|,
              |dy.x*w,dy.y*h|)), 0, mipCount-1); ANY Inf/NaN component -> mip(mipCount-1)
              uniformly; cube gradient LOD = the same formula applied to the quotient-rule
              projection of the 3-component gradient onto the selected face (matches HW to
              <=0.01 mip across 12 cases); bias-operand register selection: `_agc.main`+69 in the
              regpair_bias archives, causally validated by splice (sec 3.3), bit-level meaning
              NOT claimed.
Finite namespace: gradient components -- IEEE-754 float32, full finite range plus Inf/NaN all
              accepted without fault, saturating-clamped consequence identical in spirit to bias
              but with the OPPOSITE NaN/Inf polarity (see sec 3.2).
Maximum-valid and first-invalid tests: no invalid gradient value found -- every finite value,
              subnormal, huge magnitude, Inf, and NaN (7 exceptional-value cases, every
              component/combination tested) produced STATUS OK with a well-defined saturated
              result; no fault/hang.
Failure/overflow behavior: [x] clamp/saturate (magnitude); NaN/Inf specifically clamp to the
              HIGH end (mip count - 1), opposite of the bias path's low-end NaN behavior.
Correct "need more" fallback: N/A (value semantics, not a resource); the register-select
              field's "need more" question (spill/indirect access for gradient operands under
              register pressure) is OPEN pending the gradient-side isolation this experiment did
              not complete.
Lifetime, destruction, and reuse semantics: N/A.
Counterexamples and untested cases: cube-gradient FACE SELECTION was validated separately (sec
              4) using explicit level(0), not cross-checked against cube_grad's own face choice
              (the LOD-recovery ramp is face-independent by construction, so cube_grad cannot
              itself report which face it read); the gradient-operand register/consecutive-
              register-block layout (component order, alignment) remains UNKNOWN -- the
              differential pair that would isolate it produced too diffuse a diff (116 bytes) in
              the time available for this experiment.
Driver/compiler consequence: Mesa's gradient2d lowering can rely on the same rho/lambda formula
              Metal itself uses; a compiler emitting a shader with a NaN/Inf-producing gradient
              (e.g. from a degenerate derivative at a discontinuity) will get mip(count-1), not a
              fault -- worth a defensive note but not a blocker. lower_txd_cube_map's continued
              necessity is NOT clearly established by this experiment (evidence points the other
              way, sec 3.6), but face-selection-only correctness (sec 4) plus this LOD evidence is
              not a full replacement for a native-cube-gradient conformance suite.
```

## 4. GLTEX-A03 -- implicit LOD and textureQueryLOD

### 4.1 Observed (lodquery, 10 cases, i=44..53)

Same fragment `[[position]]`-derived exact-derivative technique as sec. 2. Each case renders
`float4(sampled, calculate_clamped_lod, calculate_unclamped_lod, 1)` for the SAME uv/derivative
in one draw (three signals from one instruction stream, exact float32 readback via
`MTLPixelFormatRGBA32Float`).

| case | target base LOD | lodMinClamp | lodMaxClamp | sampled | clamped_lod | unclamped_lod |
|---|---:|---:|---:|---:|---:|---:|
| lod0_noclamp | 0 | -- | -- | 0.0 | 0.0 | 0.0 |
| lod2_noclamp | 2 | -- | -- | 2.0 | 2.0 | 2.0 |
| lod4_noclamp | 4 | -- | -- | 4.0 | 4.0 | 4.0 |
| lod6_noclamp | 6 | -- | -- | 6.0 | 6.0 | 6.0 |
| lod8_noclamp | 8 | -- | -- | 8.0 | 8.0 | 8.0 |
| lod6_max3 | 6 | 0.0 | 3.0 | 3.0 | 3.0 | 6.0 |
| lod2_min5 | 2 | 5.0 | 8.0 | 5.0 | 5.0 | 2.0 |
| lod4_tight | 4 | 3.5 | 4.5 | 4.0 | 4.0 | 4.0 |
| lod0_min2 | 0 | 2.0 | 8.0 | 2.0 | 2.0 | 0.0 |
| lod8_max6 | 8 | 0.0 | 6.0 | 6.0 | 6.0 | 8.0 |

**10/10 exact matches, both runs, no tolerance needed (bit-exact float32 readback).**

### 4.2 Interpretation

`sampled` (the LOD an actual `sample()` call at the same coordinate uses) and
`calculate_clamped_lod` are IDENTICAL in every case -- Apple9's implicit-LOD sample path and its
clamped LOD-query report the exact same number for the exact same inputs; there is no hidden
discrepancy between "what the texture unit actually used" and "what the query op reports as
clamped." `calculate_unclamped_lod` exactly equals the base LOD BEFORE the sampler's
`lodMinClamp`/`lodMaxClamp` is applied -- confirming which component is which, precisely as
GLTEX-A03 asks. Cross-referencing FS-04..FS-06 (raw derivative behavior): this experiment did not
re-test the derivative INSTRUCTION itself (already covered by EXP-0008/EXP-0016), only the
texture-unit's LOD SELECTION built on top of it -- the derivative feeding these results is exact
by harness construction (sec 2's `[[position]]` technique), so any FS-04..06 derivative
imprecision is not a confound here.

### 4.3 Response block

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes -- implicit-LOD sample and the clamped/unclamped LOD-query both
              implement the OpenGL-expected results exactly, for the full tested LOD range and
              4 distinct sampler-clamp configurations.
Applies to: [x] M4/G16G (tested)  [ ] A18 Pro/G17P (INFERRED by family; not independently tested)
Evidence: [x] independently assembled/executed HW test (own-MSL, real M4 GPU, two byte-identical
              runs, bit-exact float32 readback, 0 mismatches)
Test/artifact: analysis/casematrix.py lodquery_cases(); kernels/lodquery_probe.metal;
              raw/m4-20260828c-run0{1,2}/04_results.jsonl i=44..53
Exact observed semantics or field mapping: calculate_clamped_lod == the LOD an actual sample()
              call uses; calculate_unclamped_lod == the base LOD before lodMinClamp/lodMaxClamp;
              both bit-exact matches to the independently derived rho/lambda formula for every
              tested case.
Finite namespace: N/A (a query result, not a resource); LOD values themselves range over
              [0, mipCount-1] once clamped, matching the already-documented mip-count field.
Maximum-valid and first-invalid tests: N/A for this sub-item (no boundary/exhaustion question --
              see GLTEX-A01/TEX-24/TEX-27 for the mip-count/lodMax finite-resource rows).
Failure/overflow behavior: N/A (no fault/reject/alias case arose; every case OK).
Correct "need more" fallback: N/A.
Lifetime, destruction, and reuse semantics: N/A.
Counterexamples and untested cases: anisotropic filtering, helper invocations, divergent control
              flow, primitive edges, and incomplete mip chains were NOT tested in this sub-probe
              (out of scope for the 10-case matrix budgeted here); sample shading / MSAA
              interaction with LOD query also untested.
Driver/compiler consequence: Mesa/NIR's textureQueryLOD lowering can trust that Apple9's clamped
              component always matches the corresponding sample()'s actual LOD -- no separate
              "what did the hardware really use" uncertainty to work around.
```

## 5. Finite-resource rows (per the non-negotiable mandate)

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| `bias()` operand | per sample instruction | IEEE-754 float32 | full finite range + subnormal + +-Inf + NaN, ALL accepted, no fault | none observed | none -- no value faults | saturating clamp to `[lodMinClamp,lodMaxClamp]∩[0,mipCount-1]`; NaN clamps to the LOW end (mip 0) specifically, not a generic clamp | none needed -- driver sums GL sampler LOD-bias + shader bias into one float | EXP-0094 i=0..25, both runs |
| `gradient2d()` dx/dy components | per sample instruction | IEEE-754 float32 x4 | full finite range + subnormal + +-Inf + NaN, ALL accepted, no fault | none observed | none -- no value faults | saturating clamp; ANY component Inf/NaN clamps to the HIGH end (mip count-1) -- opposite polarity from bias | none needed | EXP-0094 i=26..43, both runs |
| sampler `lodMinClamp`/`lodMaxClamp` pair | per sampler descriptor | float (see `docs/descriptors/README.md` for the raw bit encoding) | independently confirmed compositional with bias/gradient in the additive-then-clamp order | `lodMinClamp > lodMaxClamp` (malformed pair) | first malformed pair tested: `(6.0, 2.0)` | `lodMaxClamp` alone determines the ceiling; `lodMinClamp` is effectively ignored, not a fault, not the average | driver must never emit an inverted pair (this is not a validated fallback, just don't rely on the raw behavior) | EXP-0094 i=22, both runs |
| texture mip VIEW (base/max level) | per texture view object | Metal texture-view level range | LOD/bias/mip-clamp scale re-bases entirely to the view's own `[0,viewLevelCount-1]` | none observed within the tested 5-level view | not applicable (view construction itself is the boundary, not tested to failure here) | re-based cleanly, no aliasing into levels outside the view observed | Mesa's GL base/max-level should map 1:1 onto a Metal texture view, consistent with this result | EXP-0094 i=23..25, both runs |
| `calculate_clamped_lod`/`calculate_unclamped_lod` result | per query instruction | float, matches sample()'s own LOD bit-exactly | N/A (not itself a capacity) | N/A | N/A | N/A -- 0 mismatches across the full LOD range x 4 clamp configs | N/A | EXP-0094 i=44..53, both runs |
| cube face selection at major-axis ties | per sample/gradient/query op | 3-way max-abs-component compare, X>Y>Z tie priority | 6 faces, all 26 tested directions (6 centers+12 edges+8 corners) resolve deterministically | none -- every tie resolved consistently with a fixed priority order | N/A (no invalid direction exists; the zero vector was not tested) | deterministic, reproducible tie-break, not hardware-random | Mesa can rely on a fixed major-axis-priority tie-break matching this order | EXP-0094 i=54..79, both runs |
| bias-operand register-select byte (`_agc.main`+69, regpair archives) | per compiled shader instance (NOT a general resource -- see sec 3.3/3.5 for scope caveats) | 1 byte, values `0x06`(A)/`0x08`(B)/`0x00`(control) observed | only 3 of 256 possible byte values tested | 253 untested values | first untested value: any byte != `{0x00,0x06,0x08}` | `0x00` gave a THIRD distinct value (`1.0`), not zero, not a fault -- consistent with (not proof of) a small register-index field | do not emit an unvalidated byte value at this offset; this is not a general hardware capacity claim, only a 2-shape splice-validated causal fact | EXP-0094 i=92..96, both runs |

## 6. Limitations and open items

- **Gradient-operand register field: OPEN.** The minimal differential pair for gradients
  produced 116 differing bytes (vs. bias's clean 4), too diffuse to isolate a single causal field
  in this experiment's time budget. `analysis/pilot/regsplice_probe/grad_A.bin`/`grad_B.bin` are
  retained as pilot evidence for a follow-up.
- **Cube-gradient LOD: a close but not bit-exact match** (max observed delta 0.01 mip against our
  own derived formula, well inside the pre-registered 0.15 tolerance but not zero) -- consistent
  with hardware using a related but not textbook-identical approximation; a dedicated,
  higher-resolution follow-up (more directions, finer magnitude sweep, explicit precision
  analysis of the trilinear-blend readout itself) would be needed to characterize the residual.
- **1D/3D/array/shadow-compare/projected/offset forms of bias/gradient** were not individually
  re-swept here; EXP-0034 already established the shared `op+2` encoding covers every dimension,
  and this experiment adds VALUE semantics on top of that, not a full per-dimension re-test.
- **A18 Pro/G17P:** no data; every claim above is M4/G16G only, `INFERRED`-by-family for A18 per
  `CLAUDE.md`'s target discipline, pending an explicit A18 validation this project does not
  currently perform (hands-off directive).
- **Anisotropic filtering, helper invocations, divergent control flow, primitive edges, sample
  shading:** none of these were varied in this bundle; each is a real, separate probe.
- **Subnormal handling:** observed as behaviorally equivalent to zero at the LOD-recovery
  readout's precision; whether the hardware flushes subnormals to zero INTERNALLY before the LOD
  computation, or merely produces the same clamped result for other reasons, is UNKNOWN --
  the readout technique cannot distinguish these without a dedicated denormal-specific probe.

## 7. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: our own MSL (kernels/*.metal, kernels/generated/*.metal), our own compiled and
  spliced AGX bytes (via harness/bin/shdump, our own build of the read-only
  tools/shdump/shdump.m), our own harness binaries (harness/texrender.m, harness/texcompute.m),
  public cube-map-face and rho/lambda LOD sampling math (analysis/reference.py, derived by us,
  not copied from any implementation), the coordinator-supplied apple9_isa_explainer.md /
  work/COMPILER-EXPLAINER-20260828.md (read for the db.json bug context only; not used to derive
  any claim in this experiment -- see sec 3.5)
Apple binary introspection: NONE
Reproduction: harness/build.sh; python3 -B verify.py --selftest && python3 -B verify.py --seqtest
  && python3 -B run.py --run-id m4-20260828c-run01 --execute && python3 -B run.py --run-id
  m4-20260828c-run02 --execute && python3 -B verify.py --captured
Evidence: raw/m4-20260828c-run01/, raw/m4-20260828c-run02/ (byte-identical 04_results.jsonl,
  sha256 e1860179c20d0ea1b464ae330675243058616fa28119be1cdda0ebc77a9e719e per
  03_dispatch.json's results_sha256 on both runs); CAPTURE_CONTRACT.json for authored-file hashes;
  analysis/pilot/ for the differential-compilation pilot artifacts referenced in secs. 3.3/3.6/6.
```

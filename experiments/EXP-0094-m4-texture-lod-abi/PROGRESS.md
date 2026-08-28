# EXP-0094 PROGRESS (timestamped milestones)

All times local machine time, 2026-08-28 unless noted. Target: M4/G16G, local host only.

## 2026-08-28 T0 -- setup
- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, work/ADDENDUM-TRIAGE-20260828.md
  (Bundle D spec), APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md (GLTEX-A01/A02/A03 exact wording),
  predecessors EXP-0034/EXP-0016/EXP-0066 RESULTS.md, docs/isa/README.md texture sections,
  docs/isa/register-move-and-liveness.md (silent-zero warning).
- Created experiments/EXP-0094-m4-texture-lod-abi/{harness,kernels,analysis,raw,work}.
- Confirmed local Metal/GPU toolchain works: Apple M4, Metal 4, supports32BitFloatFiltering=1
  (public API query, `[MTLDevice supports32BitFloatFiltering]`).

## 2026-08-28 T1 -- harness design: the "LOD-recovery" technique
- Standalone probe (scratchpad, not committed as evidence): an R32Float 2D texture with 9 mip
  levels, level L filled with the CONSTANT value float(L) everywhere, sampled with
  mipFilter=linear. The hardware's own trilinear blend across mip levels then reads back the
  CONTINUOUS effective LOD it selected, exactly (not quantized to 8-bit color) -- validated:
  uvScale=1/256 (rho=1, base LOD=0) + bias=0/2/8/8.5/-1 -> readback 0/2/8/8(clamped)/0(clamped)
  exactly; uvScale=16/256 (rho=16, base LOD=4) + bias=0 -> readback 4. This became the read-out
  method for bias_sweep/grad_sweep/cube_grad/lodquery.
- Wrote harness/texrender.m (render pipeline: public-Metal source compile OR archive+splice,
  generic 2D texture/sampler/params binding, [[position]]-derived uv so d(uv)/d(pixel) is
  EXACTLY known -- no vertex-interpolation rounding) and harness/texcompute.m (compute pipeline
  sibling for explicit-gradient backends: 2D and CUBE texture, source or archive+splice).
  Built harness/bin/shdump (our own copy, built fresh from tools/shdump/shdump.m, read-only
  source; binary lives in our experiment dir, not in tools/).
- Smoke-tested bias_probe.metal, lodquery_probe.metal (render), grad_probe.metal,
  cube_faceid.metal, cube_grad.metal (compute) -- all functionally correct on first real HW
  dispatch. Notable early observations (informal, superseded by the gated capture matrix below):
  bias=NaN -> mip 0; bias=+Inf -> mip 8 (clamped); grad NaN on one gradient component -> mip 8
  (asymmetric from the bias case -- flagged for the real sweep to characterize properly).

## 2026-08-28 T2 -- register-field isolation: three false starts, then a validated result
- v1 differential-compilation generator (register-pressure ramp via `constant float* params`
  reads + a flat `sink += j[i]*const` reduction): compiled to BYTE-IDENTICAL `_agc.main` for
  N=0..32 junk values, with and without --no-fast-math. Cause: trivial reduction, collapsed by
  the compiler.
- v2 (serially-dependent non-uniform FMA/mul/max chain, same `constant` buffer source): STILL
  byte-identical `_agc.main`. Root cause found via `agxparse.py --json` region listing:
  `_agc.main.constant_program` (the shader PREAMBLE) grew with N (64/128/256/512 bytes for
  N=0/4/16/32) while `_agc.main` (the per-invocation body) stayed fixed. Everything derived
  ONLY from the `constant` address space is provably uniform across the invocation group, so
  AGX's compiler hoists it entirely into the preamble and `main` just consumes an
  already-computed preloaded-uniform result -- the SAME mechanism EXP-0016 already documented
  for texture width/height/mip-count queries, now shown to also apply to a genuinely-uniform
  bias/gradient operand.
- v3 (FINAL): forced genuine per-invocation variance. Compute (grad): buffer reads offset by
  `[[thread_position_in_grid]].x` (`params[tid.x + K]`) -- a per-thread SR is not a
  compile-time constant even though our dispatch is always 1 thread, so the compiler cannot
  hoist it. Fragment (bias): operand values routed through a genuine per-vertex INTERPOLATED
  VARYING (`[[stage_in]]`) instead of a direct `constant` buffer read -- the fragment compiler
  has zero visibility into what the paired vertex stage will output, so a stage_in field is
  always treated as per-fragment-varying by construction (a principled fix, not an
  obfuscation -- an expression like `x*0.0` or `x-x` is ALWAYS uniform regardless of x's
  runtime value, so hoisting it is CORRECT, not a bug to route around). Verified: `main` grew
  68->1244 bytes (grad) / 202->1046 bytes (bias) across N=0..32, confirming real register
  pressure. The sampler-op's OWN 10 bytes stayed structurally recognizable (bias mode `0x07`
  intact) but its surrounding preceding-instruction bytes now visibly move with N.
- Built a MINIMAL differential pair (regpair_bias_A/B.metal, regpair_grad_A/B.metal): two named
  operands (biasA/biasB, or dxA/dyA vs dxB/dyB), both v3-style non-uniform, byte-identical
  source except which one feeds the sample()/gradient2d() and which feeds an output sink.
  - grad pair: 116 differing bytes between A/B compiled output -- too diffuse to isolate a
    single field in the time available; reported as an open item, not a validated claim.
  - **bias pair: exactly 4 differing bytes**, in two clean value-swap pairs:
    `_agc.main`+69 (06<->08) / +159 (08<->06), and +107 (03<->04) / +169 (04<->03). The
    sampler-op's own 10 bytes (mode `0x07`) were IDENTICAL between A and B -- the operand
    selection lives entirely in a PRECEDING instruction, not in the texture-op bundle itself.
- **SPLICE VALIDATION (HW-VALIDATED, real M4 GPU, `PIPELINE_SOURCE archive` proving the spliced
  bytes ran):** compiled regpair_bias_A/B to F32-color archives (`--color-format 55` so the
  archive matches the r32float render target the LOD-recovery readout needs -- BGRA8Unorm
  archives MISS a r32float pipeline request, a real and now-documented finding, not a harness
  bug). biasA=2.0, biasB=6.0 (LOD-recovery readback -> distinguishable mips 2 vs 6).
  - A fresh-compiled: r=2 (biasA). B fresh-compiled: r=6 (biasB). A-as-archive (unspliced): r=2
    (archive path faithful).
  - **Single-byte splice, absolute file offset 15653 (`_agc.main`+69), A's archive, 0x06->0x08
    (B's value): r=6.** The rendered pixel -- several instructions and a real texture-unit LOD
    computation downstream of the flipped byte -- flips from reflecting biasA to reflecting
    biasB. This is the mandated downstream-consumer validation (register-move-and-liveness.md),
    not a same-instruction check.
  - Reverse direction (B's archive, same offset, 0x08->0x06): r=2. Confirms bidirectionality.
  - Control splice to an unused value (0x00, neither A's nor B's): r=1 -- a third, distinct,
    non-zero, non-faulting result (not the "silent zero" pattern seen elsewhere in this repo's
    ISA work) -- consistent with (but not proof of) "this byte selects among several live
    registers," reported as-observed, not over-interpreted.
- **Coordinator update incorporated (2026-08-28, mid-task):** read apple9_isa_explainer.md +
  work/COMPILER-EXPLAINER-INTERACTION-20260828.md. Confirmed db.json bug: falu2/falu2i (6-byte
  compact float), the 10-byte logic form, and the 8-byte FMA form's srcA_reg/srcB_reg/src2
  fields conflate a source-RETENTION flag with the register-index top bit (delta of exactly 64
  = bit 15/31/47). **This bug's scope is that specific ALU instruction family.** This
  experiment's operand-register findings above do NOT go through db.json's decode at all -- the
  isolated byte (`_agc.main`+69) was found by raw differential byte compilation and validated
  by raw splice-and-observe-downstream-consumer, with NO claim about its bit-level meaning
  (register number, retention flag, or otherwise) beyond the OBSERVED causal behavior. Treated
  as a distinct, uninterpreted causal field pending its own decode effort -- explicitly NOT
  assumed unaffected by analogy, per the coordinator's instruction, but also not conflated with
  the falu2 bug since it is a structurally different instruction (preceding the texture sampler
  bundle, not a falu2/logic/FMA compact form).

## Next
- Freeze PRE_REGISTRATION.md + CAPTURE_CONTRACT.json (uses the above as pilot/baseline
  evidence, per the repo's standing pattern of deriving frozen expected values from pilot HW
  compiles/decodes, not inventing constants).
- Build the full gated case matrix (bias_sweep, grad_sweep, lodquery, cube_faceid, cube_grad,
  regsplice_bias) + verify.py five-gate implementation + two capture runs.

## 2026-08-28 T3 -- full case matrix, gates, two capture runs (COMPLETE)

- Built `analysis/reference.py` (independently-derived rho/lambda LOD formula + cube-map
  face/gradient math -- our own derivation, not copied), `analysis/casematrix.py` (97 cases
  across 6 backends: bias_sweep 26, grad_sweep 18, lodquery 10, cube_faceid 26, cube_grad 12,
  regsplice_bias 5).
- Built `run.py` (single-threaded capture runner, gated JSONL record shape,
  smoke-gate-before-raw discipline) and `verify.py` (5 standing gate classes: --selftest,
  --seqtest, non-recorded smoke gate, no-nondeterminism split between 04_results.jsonl and
  04_results_raw.jsonl, selftest fixtures from casematrix's real case identities).
- **Three run-id attempts, two quarantined, one promoted** (see QUARANTINE-*.md for full
  detail): `m4-20260828-run01` (own-code fast-math mismatch in the regsplice_bias harness path,
  5/97 PIPELINE_MISS) -> `m4-20260828b-run01` (all 97 correct, but verify.py itself needed a
  design fix mid-sequence, and verify.py is bound into run provenance) -> **promoted:
  `m4-20260828c-run01`/`m4-20260828c-run02`**, both 97/97 STATUS OK, 82 MATCH_EXPECTED, 15
  OBSERVED_NO_ORACLE (pre-registered no-a-priori-oracle cases), 0 MISMATCH_EXPECTED,
  **byte-identical `04_results.jsonl` across both runs**
  (sha256 `e1860179c20d0ea1b464ae330675243058616fa28119be1cdda0ebc77a9e719e`).
- `verify.py --captured` PASSES on the final tree.
- Headline results (full detail in RESULTS.md): bias/gradient LOD composition confirmed exactly
  against the independently derived formula across the full finite-resource sweep including
  Inf/NaN/subnormal; a genuine bias-vs-gradient NaN-handling ASYMMETRY (mip 0 vs mip
  count-1) reproduced on both runs; the bias-operand register-select byte isolated by
  differential compilation and HW-VALIDATED by a bidirectional downstream-consumer splice;
  cube face selection exact at all 26 tested directions including every edge/corner tie; cube
  gradient LOD matches our own derived reference to within 0.01 mip (well inside the
  pre-registered 0.15 tolerance) across 12 direction x magnitude cases -- a positive answer to
  the addendum's lower_txd_cube_map key-falsifier question; textureQueryLOD's clamped/unclamped
  components match sample()'s own LOD and the pre-clamp base LOD exactly, bit-for-bit, in all 10
  cases. Gradient-operand register isolation remains OPEN (116-byte diff, not a clean isolate --
  reported honestly, not claimed).
- Wrote RESULTS.md (per-item GLTEX-A01/A02/A03 response blocks, finite-resource table, clean-room
  attestation, limitations). Cleaned `analysis/pilot/` to extracted-hex-only per
  `tools/shdump/README.md`'s convention (no committed `.bin` archives).

**Experiment complete.** No git commits made (orchestrator's responsibility per
`experiments/SUBAGENT_BRIEF.md`).

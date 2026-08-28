# EXP-0094 Pre-registration -- M4 texture bias/gradient/implicit-LOD ABI (Bundle D)

Frozen before any capture run under this contract. Git revision at registration:
`b05383c5a40653b1176b0345806af1955bb87659` (recorded for provenance only -- per
`experiments/SUBAGENT_BRIEF.md`'s pinned-revision rule, the cross-run gate in `verify.py`
compares **authored file hashes** recorded in `CAPTURE_CONTRACT.json`, never live repo `HEAD`;
a sibling experiment landing between run01 and run02 is not a gate failure). The repo tree had
uncommitted sibling-experiment files at registration time (pre-existing, unrelated to this
experiment; not part of `CAPTURE_CONTRACT.json`'s authored set).

Target: **Apple M4 / G16G, local host only**, macOS 26.6.2, Metal 4, Apple clang 21.0.0
(`clang-2100.1.1.101`), Python 3 (system `python3`). A18 Pro is hands-off (no data from it in
this experiment). M5 is out of scope.

## Questions under test

- **GLTEX-A01** -- exact bias-operand register packing/width/type/range; interaction among
  shader bias, sampler `lodMinClamp`/`lodMaxClamp`, mip count/base-max-level restriction, and
  implicit fragment LOD; zero/signed-zero/ordinary/endpoint/out-of-range/huge/subnormal/Inf/NaN
  behavior; where addition/clamping/quantization occur.
- **GLTEX-A02** -- complete register ABI for explicit gradients (`gradient2d`); isolate the
  bias-operand and gradient-operand registers from the already-located `op+2` mode selectors;
  independent (asymmetric) X/Y gradient components including zero/subnormal/large/negative/
  Inf/NaN; for cube gradients, compare native results against an independently computed
  reference at face boundaries and major-axis ties, deciding whether Mesa's
  `lower_txd_cube_map` stays mandatory.
- **GLTEX-A03** -- does implicit-LOD sampling and `calculate_clamped_lod`/
  `calculate_unclamped_lod` implement the OpenGL-expected results; which component is
  unclamped and which is implementation-clamped; cross-referenced against `FS-04`..`FS-06`
  (raw derivative behavior) but recorded as texture-unit LOD selection separately.

## Hypotheses and falsifiers

1. **Base-LOD formula.** H: Apple9's implicit/explicit-gradient LOD follows the standard public
   rho/lambda formula (`analysis/reference.py:base_lod_2d`) -- `rho = max(|dudx*w,dvdx*h|,
   |dudy*w,dvdy*h|)`, `lod_base = log2(rho)`. Refuter: an HW-observed LOD (via the LOD-recovery
   readout) that diverges from this formula by more than the stated tolerance (0.15 mip, chosen
   to absorb 8-bit-quantization-free but still filter-hardware-approximate trilinear blending)
   for a case with NO Inf/NaN/clamp involved falsifies exact-formula agreement; the experiment
   still reports the observed value as the fact.
2. **Bias addition order.** H: effective LOD = base_lod + bias, THEN clamp to
   `[lodMinClamp, lodMaxClamp]`, THEN clamp to `[0, mipCount-1]`. Refuter: any case in
   `BIAS_CLAMP_CASES` whose observed LOD does not match `clamp_lod(base+bias, lodMin, lodMax,
   mipCount)` refutes this ordering (e.g. if clamp happens before bias addition, `clamp_max3_bias6`
   would read back 3+6=9-then-clamped-to-8, not 3).
3. **Bias-operand register field.** H (pre-registered from the PROGRESS.md T2 pilot, not
   invented post hoc): a single byte at absolute file offset 15653 (`_agc.main` base 15584 + 69)
   in the F32-color archive of `kernels/regpair_bias_A.metal` / `regpair_bias_B.metal` causally
   selects which live register's value the sample instruction consumes as the bias() operand.
   Refuter: a splice of that byte between A's native value (0x06) and B's native value (0x08)
   that does NOT flip the observed LOD-recovery readback between 2.0 (biasA) and 6.0 (biasB) on
   BOTH runs falsifies the claim. This is the load-bearing HW-VALIDATED claim of the experiment.
4. **Cube face selection.** H: major-axis selection with the OpenGL-standard face-slice order
   (`+X,-X,+Y,-Y,+Z,-Z` -> Metal cube slices 0..5, independently confirmed on hardware before
   this pre-registration -- see PROGRESS.md). Refuter: any `cube_faceid` case whose observed
   face differs from `reference.select_face()` AWAY from an exact major-axis tie falsifies the
   selection rule; a mismatch exactly AT a tie (edge/corner cases) is recorded as an
   implementation-choice difference per the addendum's own framing, not a defect.
5. **Cube gradient LOD.** H: cube gradient LOD follows our own quotient-rule projection of the
   3-component direction gradient onto the selected face's 2D basis
   (`reference.cube_gradient_lod`), then the same rho/lambda formula. This is explicitly a
   **weak, falsifiable** hypothesis -- real hardware may implement a cheaper/different
   approximation, and the addendum anticipates exactly this ("a cube-gradient result that
   diverges from the independently computed reference ... would settle whether Mesa's
   lower_txd_cube_map stays mandatory"). A divergence is a first-class reported result, not
   something to reconcile.
6. **NaN/Inf behavior differs between the bias path and the gradient path.** H (from informal
   pilot observation, PROGRESS.md T1): `bias(NaN)` resolves to mip 0 while a NaN gradient
   component resolves to mip 8 (max) -- i.e. the two operand paths do NOT share identical
   exceptional-value handling. Refuter: the gated `bias_sweep`/`grad_sweep` NaN cases
   disagreeing with this asymmetry (e.g. both landing on the same mip) refutes it; either
   outcome is reported, this is a genuine open question, not assumed true.

## Independent / controlled variables

- `bias` value (`bias_sweep`): the finite-resource sweep in `casematrix.BIAS_CORE` plus the
  clamp-interaction block (`BIAS_CLAMP_CASES`) and the mip-view block (`BIAS_VIEW_CASES`).
  Controlled: fixed `uvScale=(1/256,0)` giving base LOD = 0 exactly, fixed 9-level 256x256
  R32Float LOD-recovery texture, fixed `mipFilter=linear`, `--no-fast-math` (fast-math permits
  reassociation/NaN-unsafe transforms that would confound the Inf/NaN cases).
- `dx`,`dy` gradient components (`grad_sweep`): `casematrix.GRAD_CASES`, independent
  (asymmetric) per-axis values including zero/subnormal/huge/negative/Inf/NaN.
- `uvScale` (-> target base LOD) x sampler `lodMinClamp`/`lodMaxClamp` (`lodquery`):
  `casematrix.LODQUERY_CASES`.
- cube `dir` (`cube_faceid`): 6 face centers + 12 edge midpoints + 8 corners, all normalized.
- cube `dir` x `dPdx`/`dPdy` magnitude (`cube_grad`): 4 representative directions x 3 gradient
  magnitudes.
- splice byte value at the frozen offset (`regsplice_bias`): A-native / B-native / one control
  value (0x00, an unclaimed byte value -- no a-priori oracle, observe raw behavior).
- controlled/held fixed throughout: single M4 device, single-threaded harness, one case per
  process, `--no-fast-math` on every compile, `FLOAT_TOL=1e-3` for non-cube LOD comparisons and
  `0.15` mip for cube-gradient comparisons (stated up front, not tuned post hoc).

## Expected observation if each hypothesis holds

Exact host-computed expected values are in `analysis/casematrix.py` (`bias_sweep_cases`,
`grad_sweep_cases`, `lodquery_cases`, `cube_faceid_cases`, `cube_grad_cases`,
`regsplice_bias_cases`), computed from `analysis/reference.py`'s independently derived formulas
BEFORE any GPU run in this contract, never adjusted to match an observed result. Cases with
Inf/NaN inputs are deliberately marked `expected: None` (`OBSERVED_NO_ORACLE`) -- there is no
a-priori public-spec guarantee for exceptional-value LOD selection; the observed value IS the
result.

## Known confounders

- **Preamble hoisting.** Any operand value derived ONLY from a `constant`-address-space buffer
  read is provably data-flow-uniform and gets compiled into the shader PREAMBLE
  (`_agc.main.constant_program`), not the per-invocation body -- discovered the hard way in this
  experiment's own harness development (PROGRESS.md T2). The `bias_sweep`/`grad_sweep`/
  `lodquery`/`cube_*` behavioral-sweep kernels use a plain `constant float*` params read
  (correctness of the FINAL VALUE is unaffected by which code region computed it -- confirmed
  functionally in PROGRESS.md T1/T1 smoke tests), but the `regsplice_bias` register-isolation
  kernels deliberately route the operand through a genuinely per-invocation-varying source
  (interpolated `[[stage_in]]` varying) specifically so the operand's setup code lands in the
  per-invocation body where the isolated byte lives.
- **`db.json` register/retention conflation bug** (coordinator update, 2026-08-28,
  `apple9_isa_explainer.md` + `work/COMPILER-EXPLAINER-INTERACTION-20260828.md`): confirmed for
  the falu2/falu2i (6-byte compact float), 10-byte logic, and 8-byte FMA families'
  `srcA_reg`/`srcB_reg`/src2 fields. This experiment's `regsplice_bias` claim does not use
  `db.json`'s decoder at all (raw differential byte compilation + raw splice), so it cannot
  inherit that specific bug, but per the coordinator's instruction this is stated explicitly
  rather than assumed by analogy -- the isolated byte's bit-level meaning (register index vs.
  some other encoding) is NOT claimed, only its observed causal effect.
- **Archive/pipeline-format binding.** `MTLBinaryArchive` pipeline lookup is bound to the FULL
  render-pipeline descriptor including color-attachment pixel format, not just the function's
  AIR hash -- an archive built with `shdump`'s default `BGRA8Unorm` MISSES a request for an
  `R32Float` pipeline (`STATUS PIPELINE_MISS`, not a harness bug). `regsplice_bias` archives are
  built with `--color-format 55` (`MTLPixelFormatR32Float`) to match the LOD-recovery readout.
- **Fast-math.** Every compile in this experiment uses `--no-fast-math` throughout (the
  Inf/NaN/subnormal cases are a primary target and fast-math explicitly permits IEEE-unsafe
  reassociation).
- **GPU faults are expected and fault-contained** per `CLAUDE.md`/`CODEX.md`: a
  `CMDBUF_ERROR`/`HANG` on an exceptional-value case is a recorded RESULT (`verdict: FAULT`),
  never retried or suppressed.
- **Cube gradient LOD is a genuinely open formula question** (see Hypothesis 5) -- this
  experiment does not assume its own derived formula is correct; a divergence is data, not
  error.

## Correction (2026-08-28, before any promoted capture)

The originally frozen run ids `m4-20260828-run01`/`m4-20260828-run02` were used for a first
capture attempt that hit an own-code bug (fast-math flag mismatch between the `regsplice_bias`
archive build and its harness invocation -- 5/97 cases, all `regsplice_bias`, failed
`PIPELINE_MISS`; the other 92 cases matched their pre-registered expectation exactly). Per
`experiments/SUBAGENT_BRIEF.md`'s standing rule, that capture is retained untouched and
quarantined (`quarantine-m4-20260828-run01/`, `QUARANTINE-run01-attempt1.md`), not repaired in
place. **The corrected, promoted run ids for this contract are `m4-20260828b-run01` /
`m4-20260828b-run02`** (`run.py` `RUNS`), matching the `...b-run01` convention EXP-0092 used for
the same situation. Every other value in this pre-registration (hypotheses, variables, frozen
case matrix, the frozen splice offset/native bytes in hypothesis 3, timeouts) is UNCHANGED --
only the harness's fast-math flag for the `regsplice_bias` backend needed correcting, not any
pre-registered value.

## Second correction (2026-08-28, same day, before any promoted capture)

`m4-20260828b-run01` also had to be quarantined (`quarantine-m4-20260828b-run01/`,
`QUARANTINE-run01b-attempt2.md`) -- not because its DATA was wrong (all 97 cases ran `STATUS
OK`, 82 matched their pre-registered expectation, 0 mismatched), but because completing the
run02 gate required a `verify.py` fix (`static()`'s `RESULTS.md` requirement needed to apply
only to the FINAL `--captured` gate, not the inter-run `--between-runs` gate), and `verify.py`
is itself an `AUTH_CODE` file bound into the run's own provenance -- changing it after
`m4-20260828b-run01` was captured correctly invalidates that run's cross-run authored-hash
binding. **The final, promoted run ids for this contract are `m4-20260828c-run01` /
`m4-20260828c-run02`.** No hypothesis, variable, case, or frozen value changed between the first
and second correction -- only `verify.py`'s gate-applicability logic.

## Case matrix size (frozen; `analysis/casematrix.full_case_list()`)

97 cases total: `bias_sweep` 26, `grad_sweep` 18, `lodquery` 10, `cube_faceid` 26, `cube_grad`
12, `regsplice_bias` 5. `REPEAT_N=1` per run -- the two independently required capture runs
(`m4-20260828-run01`/`m4-20260828-run02`) are themselves the determinism check via the
byte-exact gated cross-run gate.

## Environment / timeouts (frozen; see `run.py` `TIMEOUTS`)

`env_command=10s`, `host_build=60s`, `archive_build=30s`, `case_process=30s`,
`smoke_process=30s`. Every sub-process is a hard-timeout blocking call in its OWN fresh process;
a timeout is recorded as `STATUS HANG` / `verdict FAULT`, never retried in place.

## Standing gate set implemented (`verify.py`)

(a) `--selftest` -- synthetic, no-Metal, no-device fixtures built from the SAME record shapes
    `run.py` writes (via `casematrix.full_case_list()`'s real case identities/expected values,
    not invented constants), driving `static()`/`captured()`; proves clean shapes pass and each
    broken shape fails for the right reason, including the NO-NONDETERMINISM distinction.
(b) `--seqtest` -- walks `PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT` through synthetic states,
    proving every gate (`--preflight`/`--between-runs`/`--captured`) is satisfiable exactly
    where the contract invokes it and refused everywhere else.
(c) NON-RECORDED smoke gate -- one scratch `bias_sweep` case (`core_zero`), run and discarded
    BEFORE `raw/<run>/` is created; a smoke failure is a pre-capture stop (`sys.exit(3)`), never
    a raw artifact.
(d) NO-NONDETERMINISM -- `04_results.jsonl` (`CASE_KEYS`) never carries a timing/duration/pid/
    address field; only `04_results_raw.jsonl` (`CASE_RAW_KEYS`) does. The cross-run gate
    requires the GATED file byte-identical between run01/run02 while deliberately never
    comparing the raw file.
(e) selftest fixtures from RECORDED REALITY -- the synthetic fixtures encode the SAME case
    identities and `expected`/oracle values `casematrix.py` derives from the pre-registered
    `reference.py` formulas, not ad hoc constants invented in `verify.py`.

Plus: single-threaded harness, `fflush(NULL)`-equivalent (harnesses flush stdout before exit;
`run.py` flushes every JSONL line before the next case starts) and non-zero-exit/`STATUS`
discipline; `raw/` append-only; hard timeouts on every subprocess; one variable per case
(explicitly documented above); each case its own process; faults are RESULTS
(`verdict: FAULT`), never suppressed; run ids `m4-20260828-run01`/`m4-20260828-run02` are never
reused or overwritten (`run.py` refuses if the path already exists); no post-capture repair of
any `raw/` file.

# EXP-0103 pre-registration — M4 FP/transcendental/SFU semantics

**Frozen state: PRE_GPU.** No case in `CAPTURE_CONTRACT.json`'s two contracted runs
(`m4-20260828-run01`, `m4-20260828-run02`) has been dispatched at freeze time. This
registration precedes both capture runs.

**Disclosed pre-freeze engineering (not data capture).** Before this contract was
frozen, two preparatory steps were needed and are disclosed here rather than hidden:

1. **Public MSL API discovery.** `metal::fast`/`metal::precise` do not expose a
   `recip()` function (verified by compiling single-line probe kernels through the
   same runtime `newLibraryWithSource:` API and reading the compiler's own
   diagnostic — an empirical discovery of the *public* API surface, not RE of any
   Apple binary); reciprocal is `fast::divide(1.0f, x)` / `precise::divide(1.0f, x)`.
   `kernels/probe.metal` uses the verified names throughout.
2. **Host-oracle performance debugging.** The first draft of `analysis/exact_ref.py`
   had two correctness-preserving but catastrophically slow paths, found and fixed
   before any corpus was frozen: (a) Machin's-formula π (base-5/base-239 rational
   arctan series) produces a bracket whose denominator bit-length is many times the
   requested precision; repeatedly squaring that in a Taylor series (sin/cos) made a
   single reference call take up to several seconds. Fixed by snapping every
   bracket-producing function's output to a clean power-of-2 denominator
   (`_snap_out`) before it can be repeatedly multiplied. (b) `exp2` of a *huge input*
   (e.g. `x = 2**127`, a legal finite `float`) attempted to build `Fraction(2)**huge`
   — not merely slow but uncomputable. Fixed with an explicit overflow/underflow
   early-exit in `ref_exp2` (`x > max_exponent+64` → `+inf`, `x < min_exponent-64` →
   `+0`) before any bracket is built. Both fixes are committed in
   `analysis/exact_ref.py`; `python3 analysis/exact_ref.py` self-tests pass, and a
   ~7000-sample cross-check against Python's IEEE-754-binary64 `math` module (used
   only as a *sanity check*, never as the reference itself, since float64-then-cast
   double-rounds) found zero disagreements over sqrt/rsqrt/exp2/log2/sin/cos/rcp
   across wide-ranging magnitudes. No hardware was touched during this debugging;
   it is pure host-side Python.
3. One clean-room process violation occurred and was self-corrected during this
   preparatory phase: several throwaway scratch files (MSL function-name probes,
   harness smoke-test JSONL outputs) were briefly written to `/tmp` instead of this
   experiment's `work/` directory, in violation of the (recently tightened)
   `SUBAGENT_BRIEF.md` rule. All were deleted immediately on discovery
   (`rm -f /tmp/check_isqrt.py /tmp/t.metal /tmp/o*.jsonl`) before this contract was
   frozen. Nothing in them was Apple-authored or sensitive (our own MSL snippets and
   JSON scratch), but the rule is absolute and this is disclosed per the brief's own
   precedent (EXP-0098, EXP-0109).

## Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` Part II clusters **FP-\*** (14 items), **TRIG-\***
(10 items), **SFU-\*** (7 items) — 31 items total, enumerated with exact wording and
per-item disposition in the table below. **HIGH VALUE (explicit dispatch priority):**
EXP-0074 showed FP32 division is bit-exact vs. correctly-rounded IEEE-754 *except*
DAZ+FTZ (subnormal operands read as zero, subnormal results flush to zero). Does that
same DAZ+FTZ behavior extend to `rcp`, `rsqrt`, `sqrt`, `exp2`, `log2`? Our own
`docs/isa/encoding-tables.md` (`fspecial_est` note) currently flags this
**UNKNOWN**. This experiment answers it directly with hardware evidence.

## Hypothesis (falsifiable, HIGH VALUE item)

On this machine (Apple M4/G16G, macOS 26.6.2 build 25G82, Metal 4), for each of
`rcp`, `rsqrt`, `sqrt`, `exp2`, `log2` in both `fast::` (single-op SFU estimate) and
`precise::` (estimate + refinement) form, FP32 results are bit-identical to a
correctly-rounded (round-to-nearest-even, gradual underflow, no flushing) IEEE-754
reference for every case **except** cases with a subnormal operand or a subnormal
correctly-rounded result, which follow the **same DAZ+FTZ model EXP-0074 found for
division**: subnormal operands read as signed zero before the op, and a
correctly-rounded subnormal result is flushed to a signed zero.

- Independent variable: input bit pattern (and fast/precise namespace selection).
- Controlled variables: kernel source (`kernels/probe.metal`), compile options
  (`fastMathEnabled=NO`, `mathMode=MTLMathModeSafe` for every case except the one
  explicit FP-07 fastmath-flag probe), dispatch geometry (one thread per case),
  buffer layout with 64-byte guard regions (same design as EXP-0074).
- Expected observation if true: every non-subnormal-involving case matches the exact
  reference bit-for-bit; every subnormal-involving divergence is fully explained by
  the DAZ+FTZ substitution model (flush-input, compute exact, flush-subnormal-output),
  with **zero residual, unexplained divergences**, mirroring EXP-0074 Table structure.
- Refuters: (1) any non-subnormal case whose result bits differ from the exact
  reference; (2) any subnormal-involving divergence the DAZ+FTZ model does NOT
  predict; (3) `fast::` and `precise::` disagreeing on the DAZ+FTZ *model* itself
  (e.g. fast flushes but precise doesn't, or vice versa) — a first-class result either
  way; (4) any NaN-reference case returning non-NaN; (5) non-byte-exact repeat between
  run01/run02; (6) any guard-byte mutation, command-buffer error, or timeout; (7) any
  gate failure before capture.
- Known confounders: the public Metal API exposes no denormal-mode control switch, so
  the GPU-side mode is measured, not set (same caveat as EXP-0074); `fast::` vs.
  `precise::` select different compiled instruction sequences whose exact opcode
  identity this experiment does not independently disassemble (see per-item table —
  the SFU/estimate opcode shapes are already `HW-VALIDATED` on A18 by EXP-0026 and
  are treated as established background, not re-derived here).

## Exact frozen method

1. **Harness** (`harness/probe.m`, public API only): a single generic binary that
   compiles `kernels/probe.metal` at runtime, picks ONE named kernel (`--fn`), loads a
   binary file of fixed 16-byte input records (`{r0,r1,r2,r3}` little-endian `uint32`,
   unused fields zero) into a 64-byte-guarded owned shared buffer, dispatches one
   compute thread per record, waits for completion, verifies all four guard regions,
   and writes one JSONL line per record (`{"i","r0","r1","r2","r3"}`, raw hex) — the
   same guard-byte / single-threaded-synchronous-exit design as
   `experiments/EXP-0074-m4-fp32-division-precision/harness/probe.m`. Internal
   watchdogs: 120 s library+pipeline compile, 300 s dispatch+completion.
2. **Kernels** (`kernels/probe.metal`): one MSL function per (op, fast/precise
   variant, dtype) combination — see the case table below. Every function is our own
   authored source using only the public `fast::`/`precise::` namespaces and standard
   MSL builtins (`fma`, `saturate`, `fmin`/`fmax`, `floor`/`ceil`/`trunc`/`round`,
   relational/`isnan`, explicit `half`/`float` casts).
3. **Host oracle** (`analysis/exact_ref.py`): correctly-rounded binary32/binary16
   references computed from exact `Fraction`/`int` arithmetic only — **never**
   float64-then-cast. Irrational functions (`sqrt`/`rsqrt` via exact integer
   `math.isqrt` bracketing; `exp2`/`log2`/`sin`/`cos` via Taylor/arctan series with an
   explicit, checkable remainder bound) produce a rigorous rational **interval**
   `[lo,hi]`, escalated in precision until it cannot straddle a rounding boundary, then
   rounded once with ordinary exact rational comparison. Self-tests
   (`python3 analysis/exact_ref.py`) check known closed-form values (√2, ln 2, π to
   150 bits) and internal consistency.
4. **Frozen corpora** (`analysis/gen_all.py` → `work/cases/*.bin` +
   `analysis/references.json` + `analysis/corpus_manifest.json`): deterministic,
   seeded (LCG `state=(state*1664525+1013904223) mod 2**32`, seed `0x0103F00D` xored
   per block — see `analysis/corpus.py`), generated **once**, hashed, and frozen into
   `CAPTURE_CONTRACT.json` before any hardware capture. **Finite-resource mandate
   applied**: `rcp`/`rsqrt`/`sqrt` FP16 (`fast`+`precise`, 6 cases) enumerate **all
   65536** FP16 bit patterns exhaustively (isqrt-based references are cheap enough,
   ~20 µs/call). FP16 `exp2`/`log2`/`sin`/`cos` use a large stratified sample (every
   one of the 32 exponent fields represented, ~1500 points) rather than full
   enumeration — the series-based references there cost ~7–14 ms/call, making full
   65536-point enumeration for all four functions impractical within this
   experiment's time budget; this is disclosed as **not exhaustive** for those four
   FP16 cases. FP32 corpora combine: an exponent-sweep directed block (every binade
   from 2⁻¹⁴⁸ to 2¹²⁷, three mantissas, both signs), an explicit special-value block
   (±0, ±∞, canonical/payload/signaling-pattern NaN, min/max subnormal, min/max
   normal, ±1, ±2, ±0.5, ±π, ±π/2), and an LCG-randomized block. `sin`/`cos` add a
   magnitude-binned directed block (2⁻⁴ … 2¹²⁸) for TRIG-05/06 range-reduction
   characterization. **47 cases, 449346 total records, 245139 unique reference
   entries** (deduplicated across fast/precise variants, which share one reference).
5. **Runner** (`run.py --execute --run-id <id>`): refuses without `--execute`;
   requires `verify.py --selftest` and `--seqtest` to pass; builds the harness; runs
   the **non-recorded smoke gate** (3 scratch, non-frozen inputs into `work/`, never
   `raw/`, shape-only assertions); then for **each of the 47 cases, in its own
   subprocess invocation of the compiled harness**, appends one receipt to
   `raw/<run>/receipts.jsonl` (`fflush`+`fsync` immediately) and writes
   `raw/<run>/results/<case>.jsonl` verbatim from the harness's own output. Faults and
   timeouts are recorded (exit code, `timed_out` flag) and do **not** abort the rest
   of the run. `raw/<run>/00_manifest.json` is written **last**, after every case
   completes, and is the sole "this run is closed" signal `verify.run_dir_complete`
   checks for.
6. **Two runs are required**: `m4-20260828-run01`, `m4-20260828-run02`, each a fresh
   process invocation per case (fresh device/library/pipeline/buffers/queue/command
   buffer every time, since every case is its own process). Final promotion requires
   `verify.py --captured`: both runs closed, identical case lists, git revision on
   both runs equal to the value frozen in `CAPTURE_CONTRACT.json` above (not live
   `HEAD` at run02 time — repo `HEAD` moving because a sibling experiment lands is not
   contamination per `SUBAGENT_BRIEF.md`), and **byte-identical `results/<case>.jsonl`
   for every case** (the result record schema
   `{"i","r0","r1","r2","r3"}` carries zero nondeterministic fields, so byte-identity
   is the correct determinism test; timestamps/durations live only in the
   never-byte-compared `receipts.jsonl`).

## The 31 items, exact wording, and disposition

Legend: **HW** = new M4 hardware capture + host-oracle comparison in this experiment
(primary evidence). **PARTIAL** = HW evidence answers the numerically-observable part;
an encoding/instruction-count aspect of the same item is not established here.
**DEFERRED** = not attempted in this experiment; reason given. **CITED** = answered by
a previously committed, already-`HW-VALIDATED` experiment (not re-run; M4≡A18 per
`EXP-M4-*` byte-identity for driver-emittable subsystems), used as background, not
reproduced fresh.

### FP-\* (floating-point ALU semantics)

| item | exact wording | disposition | evidence source |
|---|---|---|---|
| FP-01 | Is FP32 FMA genuinely fused, single final rounding, no intermediate product rounding? | **HW** | `fma_f32` vs. exact fused reference (`ref_fma`), incl. the classic `(1+2⁻²³)²−1` fused-vs-separate divergence vector |
| FP-02 | Is FP16 FMA genuinely fused at FP16 precision, scalar and packed-half? | **HW** | `fma_f16`, `fma_f16x2` |
| FP-03 | Does the FP32 source-negate modifier implement `a−b` for every source class? | **PARTIAL** | `sub_f32`: IEEE-conformance of `a-b` across every operand class (NaN/inf/zero/subnormal/signed-zero-result) is HW-tested; whether this compiles to a *negate-modifier bit on fadd* (vs. a separate negate op) is an encoding question not disassembled here |
| FP-04 | Do FP32 min/max match NIR's required signed-zero choice for +0 vs −0? | **HW** (informational for the true tie) | `minmax_f32`: `SPECIAL_PAIRS_F32` includes `(+0,-0)`/`(-0,+0)`; IEEE minNum/maxNum does not mandate a winner for that exact tie, so the observed choice is recorded, not scored pass/fail (see `ref_fmin`/`ref_fmax` docstring) |
| FP-05 | Do FP32 min/max implement the exact NaN behavior (one-NaN, two-NaN, payload, order) required by NIR? | **HW** | `minmax_f32`: NaN-avoiding rule tested both operand orders, canonical/payload/negative NaN |
| FP-06 | Does Apple9 preserve FP32 input/output subnormals in default graphics compute mode? | **HW + CITED** | Directly re-answered (in the negative, DAZ+FTZ) by every FP32 SFU case's subnormal directed block; **CITED**: EXP-0047 (add/mul), EXP-0074 (division) established the same for the base ALU |
| FP-07 | Can FP32 denormal behavior be selected per shader/instruction rather than a fixed device mode? | **HW** | `rcp_precise_f32_fastmath_on` (global `fastMathEnabled=YES`/`mathMode=Fast`) vs. `rcp_precise_f32` (`NO`/`Safe`), same kernel, same corpus |
| FP-08 | Does Apple9 preserve FP16 input/output subnormals, scalar and packed? | **HW** | `addmul_f16`, `addmul_f16x2`; extended by exhaustive FP16 `rcp`/`rsqrt`/`sqrt` DAZ/FTZ classification (all 65536 patterns) |
| FP-09 | Does saturate exactly implement the NIR/API clamp contract for NaN and signed-zero? | **HW** | `saturate_f32` vs. `ref_saturate_f32` (documented `clamp(x,0,1)` composition; falsifiable prediction: `saturate(NaN)=+0`) |
| FP-10 | Does FP32→FP16 conversion use round-to-nearest-even (the `pack_half_2x16` mode)? | **HW** | `f32_to_f16` vs. `ref_convert_f32_to_f16`, incl. explicit half/whole-ULP tie vectors |
| FP-11 | Does FP32→integer conversion truncate toward zero for every signed/unsigned boundary and exceptional input? | **HW** | `f32_to_int` (`int`/`uint`/`char`/`uchar` truncation) vs. `ref_f32_to_int_trunc`; in-range cases scored strict, out-of-range/NaN/Inf recorded as **observational** (IEEE/C leave this implementation-defined) |
| FP-12 | Does any Apple9 conversion form directly implement NIR saturating float→int conversion? | **PARTIAL** | `f32_to_int8_plain` vs. `f32_to_int8_sat` (`clamp`-then-convert) numeric comparison run; a disassembly instruction-count check (does the compiler fuse clamp+convert into one native op) is a stretch goal attempted only if time remains after capture, not guaranteed |
| FP-13 | Can `fquantize2f16` be implemented by native narrow-then-widen with exact NaN/subnormal/inf behavior? | **HW** | `fquantize_f16` (`float(half(x))`) vs. `ref_widen_f16_to_f32(ref_convert_f32_to_f16(x))` |
| FP-14 | Do FP32 comparisons expose ordered/unordered NaN conditions for `ford`/`funord`/unordered-relational? | **HW** | `compare_nan_f32`: all six relational ops + `isnan` bit-packed, vs. an IEEE-ordered-comparison reference |

### TRIG-\* (trig / range reduction)

| item | exact wording | disposition | evidence source |
|---|---|---|---|
| TRIG-01 | Is the complete operand/modifier encoding of the native trig primitive hardware-validated? | **DEFERRED** | requires instruction-field splice validation beyond black-box MSL execution; out of scope here |
| TRIG-02 | Is the complete operand/modifier encoding of the `0x2b` range-reduction op hardware-validated? | **DEFERRED** | same reason; `docs/isa/encoding-tables.md` already marks this op's internals `INFERRED` |
| TRIG-03 | Does native range reduction expose quadrant info so sin+cos avoid re-reducing? | **PARTIAL** | `sincos_shared_f32` (same SSA `x` feeds both) numeric self-consistency checked; the *instruction-count* proof of sharing needs disassembly — attempted as a stretch goal, not guaranteed |
| TRIG-04 | Can sin and cos of the same SSA input share one native range-reduction result? | **PARTIAL** | same evidence as TRIG-03 |
| TRIG-05 | Finite input interval over which native sin/cos meets the required error bound, with method? | **HW** | `sin_fast_f32`/`cos_fast_f32` (+precise) magnitude-binned sweep (2⁻⁴ … 2¹²⁸, both signs) vs. exact reference; ULP table by magnitude bin in `RESULTS.md` |
| TRIG-06 | Does native range reduction fail the accuracy contract for some finite FP32 inputs? | **HW** | same corpus; **CITED** context: EXP-0026 found `sin(2π)≈5×10⁵` ULP on A18 |
| TRIG-07 | Does the observed polynomial (coefficients + evaluation order) meet the error bound over its reduced interval? | **PARTIAL** | achieved-accuracy-over-reduced-interval is numerically measured (small-\|x\| slice of the same sweep); *exact coefficient bit patterns* require disassembling the fma chain — **DEFERRED**, `docs` already notes this is "not reconstructed" by design (clean-room rule 5 restraint) |
| TRIG-08 | Are sin/cos special cases (+0,−0,∞,NaN,subnormal) fully characterized? | **HW** | directed block in every sin/cos case's corpus |
| TRIG-09 | Can FP16 sin/cos use the FP32 reduction+polynomial plus one native FP16 conversion? | **PARTIAL** | `sin_fast_f16`/`cos_fast_f16` correctness vs. exact FP16 reference is HW-tested; the *mechanism* claim ("reuses the FP32 pipeline internally") is not independently verified without disassembly — **INFERRED** at best |
| TRIG-10 | Do fast and precise Metal output use byte-identical sin/cos arithmetic? | **HW** | `sin_fast_f32` vs. `sin_precise_f32` (and cos) bit-exact comparison across the full corpus; **CITED** context: EXP-0026 found byte-identical compiled code on A18 |

### SFU-\* (special-function unit)

| item | exact wording | disposition | evidence source |
|---|---|---|---|
| SFU-01 | Are rcp/rsqrt/sqrt/exp2/log2/floor/ceil/trunc/round each independently selectable? | **HW** | one dedicated kernel per function; `round_family_f32` for floor/ceil/trunc/round |
| SFU-02 | Are the result semantics and special cases of every SFU selector hardware-validated? | **HW** | directed special-value block embedded in every SFU case |
| SFU-03 | Is the reciprocal/rsqrt estimate seed deterministic for every input bit pattern and FP mode? | **PARTIAL** | black-box determinism evidenced by the required byte-exact run01/run02 repeat across the full `rcp`/`rsqrt` fast+precise corpora (all inputs, both modes); direct estimate-*register* readback (as EXP-0026 did via splice, **CITED**, A18) is not repeated here |
| SFU-04 | Does precise reciprocal require exactly two refinement iterations for its claimed accuracy? | **DEFERRED** | **CITED**: EXP-0026's answer is an *inferred* precision-doubling argument (8→16→≥24 bits), explicitly not a literal instruction count (clean-room rule 5: compiler-generated NR sequences are deliberately not transcribed); not independently re-derived here |
| SFU-05 | Does precise sqrt require a correction distinct from `x * precise_rsqrt(x)`? | **HW** | `sqrt_vs_rsqrt_f32`: both computed from the *same* input in the *same* dispatch, compared bit-exact |
| SFU-06 | Does precise division require a remainder correction distinct from `a * correctly_rounded_rcp(b)`? | **HW** | `div_vs_rcp_f32`: both computed from the same inputs in the same dispatch |
| SFU-07 | Are exp2/log2 error bounds and exceptional-value behavior sufficient without additional software correction? | **HW** | `exp2_fast_f32`/`log2_fast_f32` (+precise) ULP table + special-case block |

**Count check:** HW=20 (FP-01,02,04,05,06,07,08,09,10,11,13,14; TRIG-05,06,08,10;
SFU-01,02,05,06,07), PARTIAL=8 (FP-03,12; TRIG-03,04,07,09; SFU-03), DEFERRED=3
(TRIG-01,02; SFU-04). 20+8+3 = **31/31**, none dropped silently.

## Environment, timeouts, and raw schema (frozen)

See `CAPTURE_CONTRACT.json` (`compile`, `capture`, `timeouts_seconds` blocks) — the
single machine-readable source of truth; this document must not silently disagree
with it.

## Promotion rule and scope

Before any build/capture: `python3 verify.py --selftest`, `python3 verify.py
--seqtest`, `python3 verify.py --preflight` (all three re-run automatically by
`run.py` before it will dispatch). Between run01 and run02: `python3 verify.py
--between-runs`. After both runs: `python3 verify.py --captured`. Until all pass, no
item above is promoted past its listed disposition.

This experiment cannot establish: native instruction encodings beyond what is already
`CITED` from EXP-0026/EXP-0013 (A18); Linux/UAPI behavior; any other macOS/Metal
version; A18 (G17P) hardware directly (hands-off per project directive — M4 evidence
is the operational Apple9 evidence per `EXP-M4-*`, not an A18-specific claim); FP64;
non-default rounding modes (not exposed by the public API); or any claim about
`fast::`/`precise::` selection *inside* a larger expression graph the compiler might
contract differently.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (planned; capture pending)
Inputs inspected: this repository's authored MSL, harness, host oracle, corpus
generator, verifier, and runner; no Apple binary of any kind
Apple binary introspection: NONE
Reproduction: `python3 analysis/exact_ref.py` (oracle self-test) →
`python3 analysis/gen_all.py` (frozen corpora, already generated and hashed above) →
`python3 verify.py --selftest && python3 verify.py --seqtest && python3 verify.py
--preflight` → `python3 run.py --execute --run-id <id>` (both contracted run ids) →
`python3 verify.py --captured`
Evidence: no raw hardware observations exist at freeze; `CAPTURE_CONTRACT.json` and
`analysis/corpus_manifest.json`/`analysis/references.json` are the frozen grammar and
frozen fixtures respectively

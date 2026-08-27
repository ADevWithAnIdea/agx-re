# EXP-0074 results — M4 public-Metal FP32 division precision (OPT-02)

**Verdict for the tested configuration: NO.** Precise FP32 division
(`a / b` on `float`, `MTLCompileOptions.fastMathEnabled = NO`,
`mathMode = MTLMathModeSafe`) on this Apple M4 / G16G does **not** produce the
correctly rounded result for all tested cases: every case with a **subnormal
operand** and every case whose correctly rounded result is a **representable
subnormal** diverges. All 215 divergences are explained by one deterministic
FTZ+DAZ model, which predicts **4171/4171** observed results. Every case whose
operands are non-subnormal and whose exact result is non-subnormal — including
all normal, zero, infinite, NaN, overflow, and underflow-to-zero classes — is
**bit-exact** against the correctly rounded IEEE-754 binary32 reference.

Both contracted capture runs completed with no fault, no timeout, no guard-byte
mutation, no command-buffer error, and byte-identical results
(`repeat_exact: true`).

---

## OBSERVED (directly, from `raw/`, before any interpretation)

Counts (identical in run 01 and run 02; `analysis.json` `verdict_counts`):

| block | total | bit-exact vs reference | divergent |
| --- | ---: | ---: | ---: |
| directed | 75 | 60 | 15 |
| randomized (LCG) | 4096 | 3896 | 200 |
| **all** | **4171** | **3956** | **215** |

NaN policy as pre-registered: cases whose exact IEEE result is NaN were judged
by **is-NaN only**; all of them returned NaN. No case that should not be NaN
was required to be NaN — the seven DAZ-induced NaNs below are counted as
divergences, not passes.

Reference integrity: methods A (exact `Fraction` + exact bracket rounding) and
B (integer long division, 64 guard bits + sticky) agreed on **all 4171 frozen
cases** (0 cross-method disagreements) and reproduced all **27** hand-computed
validation values. No binary64 path exists anywhere in the reference, so no
double rounding is possible.

Class cross-tab (operand classes × correctly rounded reference class), from
`raw/m4-20260827-run01/04_results.jsonl`:

| a | b | ref result | cases | divergent |
| --- | --- | --- | ---: | ---: |
| normal | normal | normal | 3015 + 23 d | 0 |
| normal | normal | inf | 474 + 5 d | 0 |
| normal | normal | zero | 357 + 2 d | 0 |
| normal | normal | subnormal | 181 + 1 d | **181 + 1 d** |
| normal | inf | zero | 3 d | 0 |
| normal | zero | inf | 4 d | 0 |
| normal | subnormal | inf | 2 + 2 d | 0 |
| normal | subnormal | normal | 6 | **6** |
| normal | nan | nan | 25 + 1 d | 0 |
| nan | normal | nan | 15 + 2 d | 0 |
| nan | zero | nan | 1 d | 0 |
| zero | normal | zero | 3 d | 0 |
| zero | inf | zero | 2 d | 0 |
| zero | zero | nan | 4 d | 0 |
| inf | normal | inf | 3 d | 0 |
| inf | inf | nan | 3 d | 0 |
| subnormal | normal | zero | 8 + 2 d | 0 |
| subnormal | normal | normal | 12 | **12** |
| subnormal | normal | subnormal | 1 + 7 d | **1 + 7 d** |
| subnormal | subnormal | normal | 6 d | **6 d** |
| subnormal | zero | inf | 1 d | **1 d** |

(`d` = directed cases; unlabeled = randomized block. The randomized block
contained no pair with both operands subnormal — probability ≈ 1.4e-4 — so that
class is covered only by directed cases 20–25.)

Directed divergences, verbatim (all 15):

| # | name | a | b | reference | observed | Δulp |
| --- | --- | --- | --- | --- | --- | ---: |
| 16 | sd_minsub_div_one | 0x00000001 | 0x3F800000 | 0x00000001 | 0x00000000 | -1 |
| 17 | sd_maxsub_div_one | 0x007FFFFF | 0x3F800000 | 0x007FFFFF | 0x00000000 | -8388607 |
| 20 | sd_minsub_div_minsub | 0x00000001 | 0x00000001 | 0x3F800000 | 0x7FC00000 | NaN |
| 21 | sd_maxsub_div_minsub | 0x007FFFFF | 0x00000001 | 0x4AFFFFFE | 0x7FC00000 | NaN |
| 22 | sd_minsub_div_subthree | 0x00000001 | 0x00000003 | 0x3EAAAAAB | 0x7FC00000 | NaN |
| 23 | sd_two_sub_div_subthree | 0x00000002 | 0x00000003 | 0x3F2AAAAB | 0x7FC00000 | NaN |
| 24 | sd_threesub_div_subtwo | 0x00000003 | 0x00000002 | 0x3FC00000 | 0x7FC00000 | NaN |
| 25 | sd_neg_minsub_div_minsub | 0x80000001 | 0x00000001 | 0xBF800000 | 0x7FC00000 | NaN |
| 27 | sd_twosub_div_three | 0x00000002 | 0x40400000 | 0x00000001 | 0x00000000 | -1 |
| 28 | sd_threesub_div_two | 0x00000003 | 0x40000000 | 0x00000002 | 0x00000000 | -2 |
| 29 | sd_sevensub_div_two | 0x00000007 | 0x40000000 | 0x00000004 | 0x00000000 | -4 |
| 30 | su_minnorm_div_two | 0x00800000 | 0x40000000 | 0x00400000 | 0x00000000 | -4194304 |
| 31 | su_maxsub_div_two | 0x007FFFFF | 0x40000000 | 0x00400000 | 0x00000000 | -4194304 |
| 32 | su_minsub_div_half | 0x00000001 | 0x3F000000 | 0x00000002 | 0x00000000 | -2 |
| 46 | dz_minsub_div_pzero | 0x00000001 | 0x00000000 | 0x7F800000 | 0x7FC00000 | NaN |

Randomized divergences (200): observed values were `0x00000000` (93),
`0x80000000` (101), `0x7F800000` (1), `0xFF800000` (5); i.e. signed zero or
signed infinity, signs consistent with the reference sign in every case. The
full per-case list is in `analysis.json` (`randomized_summary.mismatches`).

NaN payload observations: **58** cases returned NaN — the 51 whose exact IEEE
result is NaN (NaN inputs with payloads `0x7FC12345`, `0x7FC54321`,
`0xFFC12345`; 0/0 and ±0/±0 in all four sign combinations; inf/inf in all three
sign combinations; NaN/0) plus the 7 DAZ-induced 0/0 divergences above.
**Every one of the 58 returned the identical canonical quiet NaN
`0x7FC00000`** (positive sign, quiet bit set, zero payload). Input NaN payloads
were never propagated, and no negative NaN was ever produced — including
`np_negqnan_dividend` (`0xFFC12345 / 3.0`) and `sd_neg_minsub_div_minsub`.

Boundary cases that **did** match exactly (no divergence): overflow threshold
`maxfloat / (1 - 2^-24)` (exact 2^128 tie) → `+inf`; `2^127 / 0.5` (exactly
2^128) → `+inf`; `2^127 / 2.0` → `0x7E800000` (largest finite of that binade);
`maxfloat / (1 + 2^-23)` → finite; `maxfloat / 4` → finite; underflow-to-zero
with normal operands (`357` randomized + `2` directed cases) → the correctly
signed zero; all divide-by-zero sign combinations → correctly signed infinity;
all x/inf and ±0/±inf cases → correctly signed zero.

Environment, exactly as recorded at capture (`raw/*/00_inputs.json`,
`raw/*/03_dispatch.json`): git revision `840ad570ab29de5daa61d6f6133123f2f88937e6`
(identical in both runs, object verified by `git cat-file -e`), repo dirty flag
true, experiment-tree dirty entries 1 (this untracked experiment directory),
python 3.14.6, `sw_vers` macOS 26.6.2 build 25G82, device `Apple M4`,
registryID 4294968259, `fast_math=false`, `math_mode_raw=0` (`MTLMathModeSafe`),
`language_version_raw=262144` (default, not pinned), library+pipeline compile
0.000765 s / 0.000747 s, dispatch 0.001055 s / 0.001403 s, command-buffer
status 4 (completed), all four 64-byte guard regions intact in both runs, 4171
result lines written in both runs.

## INTERPRETED (supported by the observations, not itself observed)

The 215 divergences are fully and exactly explained by denormal flushing on the
divide path — the same behavior EXP-0047 reported for tested fp32 add/multiply
source paths on this machine:

1. **DAZ (denormals are zero):** a subnormal operand is treated as a signed
   zero before the divide. Consequences observed: `subnormal / normal` →
   ±0 (reference: a finite value, sometimes normal); `normal / subnormal` →
   ±inf (reference: a finite value) — and when the true quotient also
   overflows, the result coincidentally agrees; `subnormal / subnormal` →
   canonical qNaN `0x7FC00000` (it is evaluated as 0/0); `subnormal / ±0` →
   canonical qNaN (reference: ±inf).
2. **FTZ (flush to zero):** when the correctly rounded quotient is a
   representable subnormal, the returned value is a **signed zero** with the
   correct sign. This is proven independently of DAZ by `su_minnorm_div_two`
   (`0x00800000 / 0x40000000`, both operands normal, reference `0x00400000`,
   observed `0x00000000`) and by the 181 randomized `normal/normal` cases whose
   reference is subnormal.
3. **Everything else is correctly rounded.** For operands that are both
   non-subnormal and an exact quotient that is not a representable subnormal,
   the hardware/compiler result is bit-identical to single-rounded
   roundTiesToEven binary32 division, including the exact 2^128 overflow tie,
   gradual-underflow-to-zero, signed zeros, signed infinities, and NaN
   generation.

Validation of the interpretation: the model "flush subnormal operands to signed
zero, compute the exact quotient, round once to binary32 roundTiesToEven with
gradual underflow, then replace a subnormal result by a signed zero" reproduces
**4171 / 4171** observed results, with zero exceptions, in both runs. This is a
stronger statement than the mismatch counts alone: there is no residual
divergence left for a second cause (e.g. an off-by-one-ulp quotient) anywhere in
the tested range.

Alternatives not excluded by this experiment: the observations fix the
*userspace-visible behavior* of the Metal-compiled divide on this machine. They
do not locate where flushing happens (hardware divide unit vs. a compiler-lowered
sequence vs. a mode register the compiler sets), and they do not establish any
native encoding. Whether a different compiler driver (e.g. Mesa's own encoder,
or a future compiler version) can select a non-flushing divide is exactly
question OPT-01, which remains open.

## Exact tested range

- Hardware/software: one Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82),
  Metal 4, runtime `newLibraryWithSource:` with `fastMathEnabled = NO` and
  `mathMode = MTLMathModeSafe`; MSL language version left at its default
  (recorded raw value 262144).
- Operation: exactly the MSL source in `kernels/fdiv_precision.metal` —
  `as_type<uint>(as_type<float>(a) / as_type<float>(b))`, one compute thread per
  case, 64-thread groups, one dispatch per run.
- Inputs: the 75 frozen directed pairs and the 4096 frozen LCG pairs (seed
  `0x5A17C0DE`, multiplier 1664525, increment 1013904223, modulus 2^32, two
  draws per pair used directly as bit patterns) — 4171 cases, nothing else.
  Within that set: 47 cases have a subnormal operand (6 with both operands
  subnormal), 190 have a subnormal reference result, 51 have a NaN reference
  result.
- Two runs, fresh process/device/library/pipeline/buffers/queue/command buffer
  each; results byte-identical.

Not tested (explicitly): `fastMathEnabled = YES` (the relaxed arm, OPT-01);
FP16 or FP64 division; `fdiv` reached from any other source language or
compiler version; any other macOS/Metal version; any Linux/UAPI path; any A18
(G17P) hardware; non-default rounding modes (not expressible through the public
API); division embedded in a larger expression graph where the compiler might
contract or reorder it; and any claim about the instruction encoding actually
emitted.

## Target and scope label

**M4 / G16G, local host, public Metal API only — behavioral evidence.**
No native-encoding or ISA claim is made or implied. No Linux/UAPI claim. No
A18 (G17P) inference: the A18 is hands-off for this work, nothing was run on
it, and this result must not be promoted to an A18 fact without its own
recorded experiment. M5 is a separate, deferred workstream and is not touched.

---

## Required response block (format copied from `APPLE9_RE_IMPLEMENTATION_GAPS.md`)

```text
Status: [ ] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [x] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0074-m4-fp32-division-precision/
    raw/m4-20260827-run01/04_results.jsonl, raw/m4-20260827-run02/04_results.jsonl
    (byte-identical), analysis.json, manifest.json; reference in analysis.py;
    gate trail in verify.py (--selftest/--preflight/--between-runs/--captured).
    Evidence qualification: the executed program is our own MSL compiled at
    runtime through the public API (OWN-SHADER / HW-PROBE class); no bytes were
    spliced, no encoding was inspected, and no native instruction is claimed.
Exact observed semantics or field mapping:
    M4/G16G, macOS 26.6.2 (25G82), Metal 4, runtime compile with
    fastMathEnabled=NO and mathMode=MTLMathModeSafe, plain '/' on float:
      * subnormal operands are treated as signed zero before the divide (DAZ);
      * a quotient that rounds to a representable subnormal is returned as a
        signed zero of the correct sign (FTZ);
      * all other cases are bit-exact single-rounded IEEE-754 binary32
        roundTiesToEven division, including the exact 2^128 overflow tie,
        underflow-to-zero, signed zeros/infinities, and NaN generation;
      * every NaN result (58 cases: 51 IEEE-NaN + 7 DAZ-induced 0/0) is the
        identical canonical quiet NaN 0x7FC00000; input NaN payloads are never
        propagated and no negative NaN is ever produced.
    Counts: 3956/4171 bit-exact; 215/4171 divergent (15 directed, 200
    randomized); the DAZ+FTZ model predicts 4171/4171 observations; both
    capture runs byte-identical.
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Not a finite-resource item. The finite namespace actually enumerated is the
    binary32 encoding class lattice: all 8 operand classes (normal, subnormal,
    +0, -0, +inf, -inf, qNaN payload variants, negative qNaN) were exercised on
    at least one side, and all 6 reference result classes (normal, subnormal,
    zero, inf, NaN, and the overflow boundary) were reached.
Maximum-valid and first-invalid tests:
    Overflow boundary probed from both sides and exactly at the tie:
    maxfloat/(1-2^-24) = exactly 2^128 -> +inf, 2^127/0.5 -> +inf,
    2^127/2.0 -> 0x7E800000, maxfloat/(1+2^-23) -> finite, maxfloat/4 -> finite.
    Subnormal boundary probed at the minimum normal dividend (0x00800000/2 ->
    0x00400000 expected, 0x00000000 observed: first case that diverges as the
    quotient sinks below 2^-126) and across the whole subnormal operand lattice.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
    Overflow is CORRECT (to +-inf at the exact RNE threshold; not a failure).
    The only non-conforming behavior observed is zero/discard: subnormal
    results are discarded to a signed zero, and subnormal operands are
    discarded to signed zero before the divide (which additionally yields 0/0
    -> canonical qNaN for subnormal/subnormal). No fault, no device loss, no
    command-buffer error, no guard-byte mutation, no timeout in either run.
Correct behavior when the compiler/driver needs more:
    A driver that must preserve gradual underflow through FP32 division cannot
    rely on this path on M4 in this configuration; it has to lower the divide
    (or the subnormal cases) itself. A driver that is permitted to flush
    denormals (Vulkan/GL both permit FTZ/DAZ) may keep the divide native and
    only needs the NaN policy noted above (canonical qNaN, no payload
    propagation). Deciding which of the two applies requires the OPT-01
    selection-point answer first.
Lifetime, destruction, and reuse semantics:
    Not applicable (stateless per-case arithmetic; no resources with lifetime).
Counterexamples and untested cases:
    15 directed and 200 randomized counterexamples, listed verbatim above and
    in analysis.json. Untested: fastMathEnabled=YES arm; FP16/FP64 division;
    other compiler/OS versions; Linux/UAPI; A18 Pro/G17P (hands-off); any
    native encoding; division inside a larger expression graph; non-default
    rounding modes (not expressible via the public API).
Driver/compiler consequence:
    The premise that "precise" Metal FP32 division is correctly rounded for all
    classes does NOT hold on M4 in the tested configuration, so
    ".lower_fdiv = false is safe because precise division is exact" is not
    available as-is: subnormal operands and subnormal results diverge from
    IEEE. Record the denormal contract explicitly (flush permitted vs. gradual
    underflow required) before deciding where division is lowered. The NaN
    contract is also not NIR-neutral: a single canonical qNaN 0x7FC00000 is
    produced and NaN payloads are not propagated, which a frontend must not
    rely on if it expects payload propagation. OPT-01 (whether two distinct
    hardware sequences are selectable for relaxed vs. precise division) is the
    next required fact and is not answered here.
```

---

## Errata and process notes

- `README.md` (hash-frozen at contract time) lists `verify.py --captured`
  before `analysis.py --write`; the executable order is the reverse, because
  `--captured` requires `analysis.json` to exist. The executed sequence was:
  `--selftest`, `make_manifest.py --check`, `--preflight`, run 01,
  `make_manifest.py --write`, `--between-runs`, run 02, `analysis.py --write`,
  `make_manifest.py --write`, `--captured`, `make_manifest.py --check`. All
  passed.
- The first `--captured` invocation after run 02 failed closed on
  `closed root: ['analysis.json']` — the intended fail-closed behavior, not a
  capture defect; it passed after `analysis.py --write`.
- The contract-named, non-recorded smoke gate passed inside both runs (had it
  failed, the run would have ended with `STOP.json` at phase `smoke_gate`).
- Git HEAD moved from `e90255e5` to `840ad570` (orchestrator commits for
  EXP-0072's quarantine and a governance update) between contract freeze and
  capture; both captures record the same revision `840ad570`, and the authored
  blobs are bound by `CAPTURE_CONTRACT.json` hashes, not by revision.
- EXP-0073's quarantined run-01 capture was not read, reused, cited, or
  compared against at any point. Every number above comes from EXP-0074's own
  two captures.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL (kernels/fdiv_precision.metal), authored harness
  (harness/probe.m), authored runner/verifier/analysis, and the raw bit
  readbacks of our own dispatches. No Apple binary, archive, BO, command
  stream, or compiled-shader byte was inspected.
Apple binary introspection: NONE
Reproduction: python3 -B verify.py --selftest && python3 -B verify.py --captured
  && python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02
  (fresh capture requires python3 -B run.py --execute --run-id <id>)
Evidence: raw/m4-20260827-run01, raw/m4-20260827-run02, analysis.json,
  manifest.json (hashes every artifact except itself)
```

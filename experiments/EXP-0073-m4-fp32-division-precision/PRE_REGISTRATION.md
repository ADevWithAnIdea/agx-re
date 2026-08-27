# EXP-0073 pre-registration — M4 public-Metal FP32 division precision (OPT-02)

**Frozen state: PRE-GPU.** No Metal compilation or execution has occurred for
EXP-0073 at freeze time. This registration precedes the build and the two capture
runs. Anything that could not be frozen before the build is a STOP, not an
improvisation.

## Question

Part-II questionnaire item **OPT-02** (`APPLE9_RE_IMPLEMENTATION_GAPS.md`): does
precise FP32 division produce the correctly rounded result for all tested normal,
subnormal, zero, infinite, NaN, overflow, and underflow cases? Compiler consequence
(recorded, not implemented here): a Yes for the tested configuration supports keeping
NIR `fdiv` un-lowered; anything else requires identifying the actual selection point
(the hardware/compiler point at which approximate division is selected).

## Hypothesis (falsifiable)

On this machine (Apple M4 / G16G, macOS 26.6.2 build 25G82, Metal 4),
`as_float(a) / as_float(b)` — the plain `/` operator on `float`, no fast-path
intrinsics, no `precise` qualifier — compiled at runtime from the authored MSL with
`MTLCompileOptions.fastMathEnabled = NO` (and `mathMode = MTLMathModeSafe`) set
explicitly and recorded, returns results bit-identical to a correctly-rounded
IEEE-754 binary32 division reference (roundTiesToEven, gradual underflow) for every
preregistered directed case and every case of the deterministic randomized block.

- Independent variable: the (a, b) input bit patterns, frozen below.
- Controlled variables: kernel source, compile options (fastMathEnabled=NO,
  mathMode=Safe, languageVersion left at its default and recorded verbatim), dispatch
  geometry (one compute thread per case, 64-thread groups), buffer layout with guard
  bytes, and the reference algorithm.
- Expected observation if true: every non-NaN case matches the reference bits
  exactly; every NaN case returns some NaN.
- Refuters: (1) any non-NaN case whose result bits differ from the reference;
  (2) any NaN-classified case that returns a non-NaN; (3) disagreement between the
  two reference implementations (a STOP, not an observation); (4) non-byte-exact
  repeat between run01 and run02; (5) any guard-byte mutation, command-buffer error,
  or timeout.
- Known confounders and prior evidence: EXP-0047 observed DAZ/FTZ-like flushing of
  subnormal operands and results on this M4 for tested fp32 add/multiply source
  paths (no-fast-math). If that behavior extends to the divide path, the subnormal
  cases below will falsify the hypothesis; that outcome is a first-class result and
  is recorded as such, with NaN payloads kept verbatim. Further confounders: the
  Metal compiler is free to lower `/` to any IEEE-conformant sequence (its choice is
  not observed and not claimed); the runtime compiler version is recorded via
  environment, not introspected; no denormal or rounding control is exposed by the
  public API, so the GPU-side denormal mode is an uncontrolled residual that this
  experiment measures rather than sets.

## Exact frozen method

1. Harness (`harness/probe.m`, public API only) reads a binary file of
   (uint32 a_bits, uint32 b_bits) pairs, places it in an owned shared buffer
   bracketed by 64 `0x5a` prefix and 64 `0xa5` suffix guard bytes, compiles
   `kernels/fdiv_precision.metal` at runtime with the recorded options, dispatches
   one compute thread per pair, waits for completion, verifies guards, and writes one
   JSONL line per case: `{"i", "a", "b", "r"}` with raw hex bit patterns. Result
   bits are never converted to C floats. Internal watchdogs: 120 s for library +
   pipeline compile (exit 97), 300 s for dispatch + completion (exit 98).
2. Runner (`run.py --execute --run-id <id>`) refuses to run without `--execute`,
   passes the preflight/between-runs gate, records git revision, repo dirty flag,
  experiment-tree dirty entry count, `sw_vers`, `xcrun --version`, python version,
   machine, its own argv/cwd, UTC timestamps, all authored SHA-256 values, then
   builds the harness with clang, writes the frozen inputs, dispatches, and retains
   everything append-only under `raw/<run-id>/`. A failure or timeout writes
   `STOP.json`, ends the run, and never retries automatically.
3. Two fresh runs are required: `raw/m4-20260827-run01` and `raw/m4-20260827-run02`,
   each in a fresh process with a fresh device, library, pipeline, buffers, queue, and
   command buffer. Run 02 additionally requires identical revision and authored
   hashes to the closed run 01 record, and final verification requires the two
   results files to be byte-identical.

## Frozen directed case list (75 cases)

| # | name | a bits | b bits | intent |
| --- | --- | --- | --- | --- |
| 0 | nn_one_third | 0x3F800000 | 0x40400000 | awkward repeating quotient 1/3 |
| 1 | nn_two_thirds | 0x40000000 | 0x40400000 | 2/3 |
| 2 | nn_one_tenth | 0x3F800000 | 0x41200000 | 1/10 (classic rounding) |
| 3 | nn_one_seventh | 0x3F800000 | 0x40E00000 | 1/7 |
| 4 | nn_one_plus_eps | 0x3F800001 | 0x3F800000 | (1+2^-23)/1 exact |
| 5 | nn_one_minus_ulp_half | 0x3F7FFFFF | 0x3F800000 | (1-2^-24)/1 exact |
| 6 | nn_eps_over_same | 0x3F800001 | 0x3F800001 | x/x = 1 |
| 7 | nn_pi_over_two | 0x40490FDB | 0x40000000 | exact halving of pi |
| 8 | nn_seven_ninths | 0x40E00000 | 0x41100000 | awkward repeating |
| 9 | nn_1e9_over_three | 0x4E6E6B28 | 0x40400000 | wide exponent gap |
| 10 | nn_one_over_1e9 | 0x3F800000 | 0x4E6E6B28 | wide exponent gap |
| 11 | nn_neg_one_third | 0xBF800000 | 0x40400000 | negative quotient |
| 12 | nn_negneg_one_third | 0xBF800000 | 0xC0400000 | both negative |
| 13 | nn_1e6_over_seven | 0x49742400 | 0x40E00000 | mixed scale |
| 14 | nn_awkward_mantissas | 0x4B3B21AF | 0x3EA9FB62 | arbitrary awkward mantissas |
| 15 | nn_identity | 0x3F800000 | 0x3F800000 | 1/1 |
| 16 | sd_minsub_div_one | 0x00000001 | 0x3F800000 | min subnormal dividend |
| 17 | sd_maxsub_div_one | 0x007FFFFF | 0x3F800000 | max subnormal dividend |
| 18 | sd_minnorm_div_one | 0x00800000 | 0x3F800000 | min normal dividend |
| 19 | sd_one_div_minsub | 0x3F800000 | 0x00000001 | subnormal divisor -> inf |
| 20 | sd_minsub_div_minsub | 0x00000001 | 0x00000001 | subnormal/subnormal exact 1 |
| 21 | sd_maxsub_div_minsub | 0x007FFFFF | 0x00000001 | = 8388607 |
| 22 | sd_minsub_div_subthree | 0x00000001 | 0x00000003 | subnormal/subnormal = exactly 1/3 |
| 23 | sd_two_sub_div_subthree | 0x00000002 | 0x00000003 | subnormal/subnormal = exactly 2/3 |
| 24 | sd_threesub_div_subtwo | 0x00000003 | 0x00000002 | subnormal/subnormal = exactly 3/2 |
| 25 | sd_neg_minsub_div_minsub | 0x80000001 | 0x00000001 | negative subnormal exact -1 |
| 26 | sd_minsub_div_three | 0x00000001 | 0x40400000 | gradual underflow RNE -> +0 |
| 27 | sd_twosub_div_three | 0x00000002 | 0x40400000 | 2/3 ulp rounds up |
| 28 | sd_threesub_div_two | 0x00000003 | 0x40000000 | 1.5 ulp tie to even |
| 29 | sd_sevensub_div_two | 0x00000007 | 0x40000000 | 3.5 ulp tie to even |
| 30 | su_minnorm_div_two | 0x00800000 | 0x40000000 | exact subnormal result 0x00400000 |
| 31 | su_maxsub_div_two | 0x007FFFFF | 0x40000000 | 4194303.5 tie to even rounds up |
| 32 | su_minsub_div_half | 0x00000001 | 0x3F000000 | exact doubling 0x00000002 |
| 33 | su_minnorm_div_2p126 | 0x00800000 | 0x7F000000 | 2^-252 -> +0 |
| 34 | su_minnorm_div_maxfloat | 0x00800000 | 0x7F7FFFFF | underflow to +0 |
| 35 | su_maxsub_div_maxfloat | 0x007FFFFF | 0x7F7FFFFF | underflow to +0 |
| 36 | ez_poszero_div_one | 0x00000000 | 0x3F800000 | +0 dividend |
| 37 | ez_negzero_div_one | 0x80000000 | 0x3F800000 | -0 dividend sign |
| 38 | ez_negzero_div_negone | 0x80000000 | 0xBF800000 | neg/neg zero sign |
| 39 | ez_x_div_negx | 0x40400000 | 0xC0400000 | a = -b exact -1 |
| 40 | ez_negx_div_x | 0xC0400000 | 0x40400000 | -a/b exact -1 |
| 41 | ez_negx_div_negx | 0xC0400000 | 0xC0400000 | neg/neg exact +1 |
| 42 | dz_one_div_pzero | 0x3F800000 | 0x00000000 | x/+0 -> +inf |
| 43 | dz_one_div_nzero | 0x3F800000 | 0x80000000 | x/-0 -> -inf |
| 44 | dz_negone_div_pzero | 0xBF800000 | 0x00000000 | -x/+0 -> -inf |
| 45 | dz_negone_div_nzero | 0xBF800000 | 0x80000000 | -x/-0 -> +inf |
| 46 | dz_minsub_div_pzero | 0x00000001 | 0x00000000 | subnormal/+0 -> +inf |
| 47 | nz_pzero_pzero | 0x00000000 | 0x00000000 | 0/0 NaN |
| 48 | nz_nzero_pzero | 0x80000000 | 0x00000000 | -0/+0 NaN |
| 49 | nz_pzero_nzero | 0x00000000 | 0x80000000 | +0/-0 NaN |
| 50 | nz_nzero_nzero | 0x80000000 | 0x80000000 | -0/-0 NaN |
| 51 | nz_inf_inf | 0x7F800000 | 0x7F800000 | inf/inf NaN |
| 52 | nz_neginf_inf | 0xFF800000 | 0x7F800000 | -inf/inf NaN |
| 53 | nz_neginf_neginf | 0xFF800000 | 0xFF800000 | -inf/-inf NaN |
| 54 | ix_inf_div_three | 0x7F800000 | 0x40400000 | inf/x +inf |
| 55 | ix_neginf_div_three | 0xFF800000 | 0x40400000 | -inf/x -inf |
| 56 | ix_inf_div_negthree | 0x7F800000 | 0xC0400000 | inf/-x -inf |
| 57 | xi_one_div_inf | 0x3F800000 | 0x7F800000 | x/inf +0 |
| 58 | xi_negone_div_inf | 0xBF800000 | 0x7F800000 | -x/inf -0 |
| 59 | xi_pzero_div_inf | 0x00000000 | 0x7F800000 | 0/inf +0 |
| 60 | xi_nzero_div_neginf | 0x80000000 | 0xFF800000 | -0/-inf +0 |
| 61 | xi_maxfloat_div_inf | 0x7F7FFFFF | 0x7F800000 | max/inf +0 |
| 62 | ob_maxfloat_div_minnorm | 0x7F7FFFFF | 0x00800000 | max/tiny -> inf |
| 63 | ob_maxfloat_div_half | 0x7F7FFFFF | 0x3F000000 | just above threshold -> inf |
| 64 | ob_maxfloat_div_four | 0x7F7FFFFF | 0x40800000 | finite near max |
| 65 | ob_2p127_div_half | 0x7F000000 | 0x3F000000 | exactly 2^128 -> inf |
| 66 | ob_2p127_div_two | 0x7F000000 | 0x40000000 | exactly 2^126 finite |
| 67 | ob_maxfloat_div_1plus | 0x7F7FFFFF | 0x3F800001 | largest finite boundary |
| 68 | ob_maxfloat_div_1minus | 0x7F7FFFFF | 0x3F7FFFFF | exactly 2^128 RNE tie -> inf |
| 69 | ob_negmaxfloat_div_1minus | 0xFF7FFFFF | 0x3F7FFFFF | -> -inf |
| 70 | ob_maxfloat_div_maxsub | 0x7F7FFFFF | 0x007FFFFF | max / max subnormal -> inf |
| 71 | np_qnan_dividend | 0x7FC12345 | 0x3F800000 | NaN dividend payload verbatim |
| 72 | np_qnan_divisor | 0x3F800000 | 0x7FC54321 | NaN divisor payload verbatim |
| 73 | np_negqnan_dividend | 0xFFC12345 | 0x40400000 | negative quiet NaN dividend |
| 74 | np_qnan_div_zero | 0x7FC12345 | 0x00000000 | NaN/0 payload verbatim |

## Frozen randomized block (4096 pairs)

- Generator: LCG with seed `0x5A17C0DE` (`1511506142`), recurrence
  `state = (state * 1664525 + 1013904223) mod 2^32`.
- Per pair, two consecutive draws: `a = next()`, `b = next()`; 4096 pairs, 8192
  draws total, indices 75..4170.
- Each draw is used **directly as the binary32 bit pattern** (sign bit 31, exponent
  field bits 30..23, mantissa bits 22..0). Distribution is therefore uniform over
  the LCG stream's representable patterns: exponent field cycles over all 0..255
  (including subnormal, infinity, and NaN encodings at their natural frequency, about
  1.2% of draws), mantissa uniform over 24 bits. No wall-clock or system randomness.
  Known limitation (documented, not corrected): consecutive LCG outputs have lattice
  structure, so the pair (a, b) correlation is weak, not zero.
- Freeze anchors: first pair a=`0x1C2A32A5` b=`0x6CDE43C0`; last pair
  a=`0xED43EABB` b=`0x44AB60DE`.

## Reference algorithm (frozen, two independent methods)

The reference computes correctly-rounded IEEE-754 binary32 division: quotient of
the two exact real values, rounded once with roundTiesToEven, with gradual
underflow onto the 2^-149 subnormal lattice and overflow to infinity at the exact
threshold 2^128 - 2^103. Computing in binary64 and casting is forbidden (double
rounding) and is not used anywhere.

- **Method A**: exact rational arithmetic (`fractions.Fraction`) — decode both
  operands to exact rationals, form the exact quotient, find the two candidate
  binary32 encodings bracketing it, and select by exact comparison with ties to even.
- **Method B**: pure integer long division — normalize significands, divide with 64
  guard bits and a sticky remainder, round once to 24 significant bits (normal range)
  or to the 2^-149 lattice (subnormal range).
- Both methods share only the special-class dispatch table (inf/NaN/zero rules),
  which encodes IEEE 754 section 6 requirements, not an algorithm.
- **Cross-check requirement**: methods A and B must agree on all 4171 frozen cases
  and on the hand set below. Any disagreement is a STOP (the reference itself is
  broken and no verdict is issued).
- **NaN policy**: for cases whose exact IEEE result is NaN (NaN inputs, 0/0,
  inf/inf), the hardware may legitimately return the canonical quiet NaN, a default
  NaN, or a propagated payload. Those cases are compared by **is-NaN only**; the
  observed payload bits are recorded verbatim and never normalized.
- **Hand-computed validation set (27 cases)**, checked against both methods before
  any comparison is issued:

| name | a | b | expected |
| --- | --- | --- | --- |
| 1/3 | 0x3F800000 | 0x40400000 | 0x3EAAAAAB |
| 2/3 | 0x40000000 | 0x40400000 | 0x3F2AAAAB |
| 1/10 | 0x3F800000 | 0x41200000 | 0x3DCCCCCD |
| 1/7 | 0x3F800000 | 0x40E00000 | 0x3E124925 |
| 1/1 | 0x3F800000 | 0x3F800000 | 0x3F800000 |
| (1+eps)/1 | 0x3F800001 | 0x3F800000 | 0x3F800001 |
| (1-ulp/2)/1 | 0x3F7FFFFF | 0x3F800000 | 0x3F7FFFFF |
| minsub/minsub | 0x00000001 | 0x00000001 | 0x3F800000 |
| minsub/sub3 | 0x00000001 | 0x00000003 | 0x3EAAAAAB |
| sub2/sub3 | 0x00000002 | 0x00000003 | 0x3F2AAAAB |
| sub3/sub2 | 0x00000003 | 0x00000002 | 0x3FC00000 |
| maxsub/minsub | 0x007FFFFF | 0x00000001 | 0x4AFFFFFE |
| sub2/minsub | 0x00000002 | 0x00000001 | 0x40000000 |
| minsub/3.0 | 0x00000001 | 0x40400000 | 0x00000000 |
| sub2/3.0 | 0x00000002 | 0x40400000 | 0x00000001 |
| sub3/2.0 | 0x00000003 | 0x40000000 | 0x00000002 |
| sub7/2.0 | 0x00000007 | 0x40000000 | 0x00000004 |
| minnorm/2.0 | 0x00800000 | 0x40000000 | 0x00400000 |
| maxsub/2.0 | 0x007FFFFF | 0x40000000 | 0x00400000 |
| minsub/0.5 | 0x00000001 | 0x3F000000 | 0x00000002 |
| max/(1-2^-24) | 0x7F7FFFFF | 0x3F7FFFFF | 0x7F800000 |
| 2^127/0.5 | 0x7F000000 | 0x3F000000 | 0x7F800000 |
| 2^127/2.0 | 0x7F000000 | 0x40000000 | 0x7E800000 |
| 1/inf | 0x3F800000 | 0x7F800000 | 0x00000000 |
| -1/inf | 0xBF800000 | 0x7F800000 | 0x80000000 |
| 7/9 | 0x40E00000 | 0x41100000 | 0x3F471C72 |
| pi/2 | 0x40490FDB | 0x40000000 | 0x3FC90FDB |

## Environment, timeouts, and raw schema (frozen)

- Target: the local Apple M4 (G16G) through public Metal only; harness built with
  `xcrun clang -fobjc-arc -framework Metal -framework Foundation`.
- Recorded at capture: git revision + dirty flags, `sw_vers`, `xcrun --version`,
  python version, machine, device name and registry ID, OS string, command-buffer
  status, fastMath and mathMode settings as executed, languageVersion default as read
  back, compile and dispatch durations, argv/cwd/UTC timestamps of every step, and
  SHA-256 of every authored blob and raw artifact.
- Hard timeouts: environment commands 10 s; host build 60 s; library+pipeline compile
  120 s (in-process watchdog, exit 97); dispatch+readback 300 s (in-process watchdog,
  exit 98; subprocess timeout 300 s as outer belt).
- Raw schema per run: `00_inputs.json`, `01_cases.json` (complete frozen pair list),
  `02_build.json`, `03_dispatch.json` (receipt + summary + results hash),
  `04_results.jsonl` (one `{"i","a","b","r"}` line per case),
  `05_run_manifest.json`. Raw is append-only, regular files only; `STOP.json` ends a
  run with no automatic retry.

## Promotion rule and scope

Before any build, `python3 -B verify.py --preflight` must pass. Before any
interpretation, `python3 -B verify.py --captured` must pass for exactly the two
contracted runs (closed raw trees, source/revision binding, guard flags, statuses,
echo-checked inputs, byte-exact repeat), and `python3 -B analysis.py --run-a ...
--run-b ... --write` must exit zero (reference self-checks green). Until then OPT-02
remains **Open** for this configuration. This experiment cannot establish native
instruction encodings, ISA-level division semantics, fast-math-arm behavior, behavior
of any other compiler version or OS, Linux/UAPI behavior, or any A18 (G17P) claim;
those require their own experiments. The verdict applies to the exact frozen inputs;
untested inputs are listed as such in RESULTS.md.

## Authored blob hashes at freeze (SHA-256)

- `kernels/fdiv_precision.metal`: `3a6e0033ed6f0bb4804270fecd771033ab481b00bf20db8144246cbf5f0088b8`
- `harness/probe.m`: `80fe4351799fd67ecdd90e4896a676e49f35e275f07fcd1451001f270fb9fe31`
- `run.py`: `f1a0239564cd07e9ff23decc262e1d54efa057deb65aea24d2a221e4c9c1f60a`
- `analysis.py`: `b331edc730f29b174969d3c89a05c66d65a1dfc044371b65a17deacb3dc51102`
- `make_manifest.py`: `343d4f9de53d2e5196f56504ea03bbb4d729d43a6fdfcb8e7dece0a0798ea232`
- `verify.py`: `84939bfe4a9e019d3707d41f0d26bc43d1cfd5c2d640c2ad1ca9c4a58256844d`
- `PRE_REGISTRATION.md`: self (hash frozen in `CAPTURE_CONTRACT.json`)
- `README.md`: `a5beb613dfa8e50a19aa13eb3bce7f026bde88265123cae8bdc0c8bab0d61227`

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (planned only)
Inputs inspected: committed authored MSL, harness, runner, verifier, analysis
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`; capture requires explicit `run.py --execute`
Evidence: no raw observations exist at freeze; `CAPTURE_CONTRACT.json` is the frozen grammar

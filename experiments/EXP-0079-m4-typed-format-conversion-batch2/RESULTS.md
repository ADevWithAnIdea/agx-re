# EXP-0079 results — M4 public typed-format conversion, batch 2

**STATUS: COMPLETE. Both contracted runs captured, byte-exact repeat
verified, all gates PASS. DRV-FMT-01 batch-2 (P1.2) CLOSED for the fourteen
formats/37 cases tested here, M4-target only.** This is the successor to
quarantined EXP-0075, whose run01 captured cleanly but whose frozen
`pre_second_run_gate` sequence was structurally unreachable (see
`../EXP-0075-m4-typed-format-conversion-batch2/QUARANTINE.md`). Both
structural fixes (`verify.py --selftest` made state-agnostic; the new
`verify.py --seqtest` gate-sequence state machine) worked exactly as
designed and the full contracted sequence — `--selftest`, `--seqtest`,
`make_manifest.py --check`, `--preflight`, smoke, run01, [`--selftest`,
`--seqtest`, `make_manifest.py --check`, `--between-runs`, smoke], run02,
[`analysis.py --write`, `make_manifest.py --write`/`--check`,
`--captured`] — completed end to end with zero repairs.

Target: **local Apple M4 (G16G), macOS 26.6.2 (25G82), Metal 4, arm64,
device name "Apple M4", Mac16,10**, public Metal API only. Nothing here is
an A18/G17P, Linux, native-command-stream, or PBE-descriptor result.

## Gate results

| gate | result |
| --- | --- |
| `verify.py --preflight` (PRE_GPU) | **PASS** (first attempt) |
| `verify.py --selftest` (PRE_GPU) | **PASS** |
| `verify.py --seqtest` (PRE_GPU) | **PASS** on the 2nd attempt — 1st attempt caught a real bug (see below); 4/4/5 real subprocess gate checks across the PRE_GPU/RUN01_PRESENT/RUN02_PRESENT fixtures |
| host build (`xcrun clang -fobjc-arc harness/probe.m`) | clean; one public `fastMathEnabled` deprecation warning (expected, harmless) |
| non-recorded smoke invocation | **PASS** inside `run.py --run-id m4-20260828-run01 --execute` (not separately logged; contracted as non-recorded) |
| `raw/m4-20260828-run01` | **CAPTURED** — exactly 40 contracted files, no `STOP.json`, 37/37 case processes exit 0, no timeout, no OS exception, no API rejection |
| `verify.py --selftest` (RUN01_PRESENT) | **PASS** — *the exact invocation EXP-0075 could never satisfy* |
| `verify.py --seqtest` (RUN01_PRESENT) | **PASS** |
| `verify.py --between-runs` | **PASS** (run01 complete, closed, every receipt/payload/guard/provenance binding verified) |
| `raw/m4-20260828-run02` | **CAPTURED** — exactly 40 contracted files, no `STOP.json`, 37/37 case processes exit 0 |
| `analysis.py --run-a run01 --run-b run02 --write` | **PASS** — `repeat_exact: true` |
| `make_manifest.py --write` / `--check` | **PASS** (state=CAPTURED) |
| `verify.py --captured` | **PASS** — final gate |

**`--seqtest`'s first attempt failed, and that failure is itself a result
worth recording.** Its RUN01_PRESENT fixture's `--between-runs` step failed
with `FAIL sw_vers m4-20260828-run01`: the synthetic `00_inputs.json` I
materialized reused `run.py`'s real `env_record()` output verbatim, whose
`sw_vers`/`xcrun_version`/`device_model` receipts carry `cwd` equal to the
**real** experiment directory (because `env_record()` was called once, for
real, against the real `HERE`), while the fixture subprocess's own
`validate_run()` reconstructs `cwd` equal to the **fixture root**. Fixed by
rewriting those three receipts' `cwd` field to the fixture root before
writing them into the synthetic tree (`verify.py`'s `build_fixture()`).
This is exactly the kind of test-harness-only bug `--seqtest` is supposed to
catch fast, safely, with zero GPU cost, before it can hide inside a real
capture attempt.

## OBSERVED (both runs, byte-exact repeat, `raw/m4-20260828-run01` /
`raw/m4-20260828-run02`)

All 37 cases, both runs: runtime library compiled (`library_ok` true), both
compute pipelines created, 1x1 shared-storage buffer-backed texture created
under `MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead`, command buffer
status 4 (completed), `fast_math_enabled` false, `msl_language_version`
262144 (raw public `MTLCompileOptions.languageVersion`, consistent with a
`(major<<16)|minor` encoding at 4.0), device "Apple M4", machine arm64, os
"Version 26.6.2 (Build 25G82)", `sysctl -n hw.model` "Mac16,10". All four
guard regions intact in all 74 case records (37 cases x 2 runs). **No
public-API rejection occurred for any of the 14 formats.** `analysis.json`
confirms `repeat_exact: true` — every one of the 37 payload objects is
byte-identical between run01 and run02, including the two hardware-observed
tie/truncation results below.

## Per-format verdict table

29/37 exact matches against the registered (documented/textbook) expected
value; 8/37 deviations — every one of the 8 is a rule-**c**
(hypothesis-to-falsify) case, and every one of the 8 is the falsification
result that case was designed to produce, not a defect. `rule` legend: **a**
= exact/trivial (not a hypothesis), **b** = documented rule, non-diagnostic
tie/coincidence point, **c** = hypothesis-to-falsify.

| case | format | rule | expected texel | observed texel | verdict |
| --- | --- | --- | --- | --- | --- |
| r8unorm_p100 | R8Unorm | b | ff | ff | match |
| r8unorm_zero | R8Unorm | b | 00 | 00 | match |
| r8unorm_p050 | R8Unorm | c | 80 | 80 | match |
| r8unorm_sep_a | R8Unorm | c | 02 | 02 | match |
| **r8unorm_sep_b** | **R8Unorm** | **c** | **02** | **03** | **deviation — NEW finding, see below** |
| rg8unorm_p100_p050 | RG8Unorm | b | ff80 | ff80 | match |
| rg8unorm_zero_p100 | RG8Unorm | b | 00ff | 00ff | match |
| r8snorm_p100 | R8Snorm | b | 7f | 7f | match |
| r8snorm_zero | R8Snorm | b | 00 | 00 | match |
| r8snorm_p050 | R8Snorm | c | 40 | 40 | match |
| **r8snorm_m100** | **R8Snorm** | **c** | **80** | **81** | **deviation — H1 CONFIRMED** |
| rg8snorm_p100_p050 | RG8Snorm | c | 7f40 | 7f40 | match |
| **rg8snorm_m100_zero** | **RG8Snorm** | **c** | **8000** | **8100** | **deviation — H1 CONFIRMED** |
| **rgba8snorm_pack** | **RGBA8Snorm** | **c** | **8000407f** | **8100407f** | **deviation — H1 CONFIRMED** |
| r16float_exact | R16Float | a | 0038 | 0038 | match |
| **r16float_mid** | **R16Float** | **c** | **0038** | **ff37** | **deviation — H2 CONFIRMED** |
| r16float_third | R16Float | b | 5535 | 5535 | match |
| r16float_pos_trunc | R16Float | c | 0038 | 0038 | match (refutes ceiling/round-away-from-zero) |
| **rg16float_exact_mid** | **RG16Float** | **c** | **00380038** | **0038ff37** | **deviation — H2 CONFIRMED (R exact, G truncates)** |
| rg16float_third_third | RG16Float | b | 55355535 | 55355535 | match |
| r32float_exact | R32Float | a | 0000003f | 0000003f | match (registration slip corrected) |
| r32float_mid | R32Float | a | ffffff3e | ffffff3e | match |
| r32float_third | R32Float | b | abaaaa3e | abaaaa3e | match |
| rg11b10float_exact | RG11B10Float | a | 80031c70 | 80031c70 | match (layout correction confirmed) |
| **rg11b10float_mid** | **RG11B10Float** | **c** | **80031c70** | **7ffbdb6f** | **deviation — H2 CONFIRMED** |
| rgb9e5float_exact | RGB9E5Float | a | 0001027c | 0001027c | match |
| **rgb9e5float_mid** | **RGB9E5Float** | **c** | **0001027c** | **ffffff77** | **deviation — H2 CONFIRMED** |
| r16sint_1/2/3855 | R16Sint | a | 0100/0200/0f0f | 0100/0200/0f0f | match x3 |
| r16uint_1/2/3855 | R16Uint | a | 0100/0200/0f0f | 0100/0200/0f0f | match x3 |
| r32sint_1/2/3855 | R32Sint | a | 01000000/02000000/0f0f0000 | (same) | match x3 |
| rgba16uint_pack | RGBA16Uint | a | 010002000f0f0000 | 010002000f0f0000 | match |

Full per-case expected/observed texel AND read-word hex for all 37 cases:
`analysis.json` (generated, hash-bound in `manifest.json`).

## Hypothesis verdicts

**H1 — snorm8 encode scale: CONFIRMED (symmetric `round(c x 127)`), REFUTES
the `[-1,1] -> [-128,127]` asymmetric-clamp registration.** All three
snorm8-family cases exercising `-1.0` (`r8snorm_m100`, `rg8snorm_m100_zero`,
`rgba8snorm_pack`) independently and consistently encode `-1.0` as physical
byte `0x81` (`-127`), not the registered `0x80` (`-128`), reproduced
byte-exact across both runs. `round(-1.0 x 127) = -127 = 0x81` matches
exactly; the typed read decodes `0x81` back to exactly `-1.0` (`bf800000`)
in every case — read words show **no deviation at all** (the format's own
decode, `max(v/127, -1.0)`, clamps either byte to the same `-1.0`), so the
physical texel byte was the only discriminator, precisely as pre-registered.
**Driver takeaway:** snorm8 (and by the same reasoning, likely snorm16 —
untested here) encodes as `round(clamp(c,-1,1) x (2^(b-1)-1))`, i.e. the
*symmetric* scale, on this hardware; a driver or shader emitting a
`[-1,1]->[-2^(b-1),2^(b-1)-1]` asymmetric encode for the `-1.0` boundary
value would be wrong for the raw stored byte, even though decode is
byte-compatible either way.

**H2 — reduced-float store narrowing rounds toward zero (truncates), not to
nearest-even: CONFIRMED across all three tested destination precisions (fp16
directly, fp11/fp10 via RG11B10Float, and the RGB9E5 shared 9-bit
mantissa), reproduced byte-exact across both runs.**
- `r16float_mid` (fp16): observed `0x37FF` (`0.499755859375`), matching the
  round-toward-zero prediction exactly; RNE (`0x3800`) is refuted.
- `rg16float_exact_mid`: the exact R channel (`0.5`) is unaffected (`0x3800`,
  rule a); the mid G channel independently reproduces the same `0x37FF`
  truncation as `r16float_mid` — a second, independent confirmation of the
  fp16 rule inside a different case.
- `rg11b10float_mid` (fp11/fp10, corrected layout): observed word
  `0x6FDBFB7F` (R=G=`0x37F`, B=`0x1BF`), bit-for-bit identical to the
  independent from-scratch Python reconstruction in `PRE_REGISTRATION.md`
  computed *before* this capture. RNE (`0x701C0380`) is refuted.
- `rgb9e5float_mid` (RGB9E5 shared exponent): observed word `0x77FFFFFF`
  (E=14, M=511 in all three channels — the mantissa overflow at
  511.99999998... is **not** renormalized to E=15/M=256). The canonical
  overflow-renormalization prediction (`0x7C020100`) is refuted.
- `r16float_pos_trunc` (new, positive-direction probe): observed `0x3800`,
  the value **both** round-toward-zero and round-to-nearest-even predict at
  this exact tie point (they coincide here by construction). This does not
  discriminate RNE from truncation (that job belongs to `r16float_mid`, which
  already decided it), but it **does** refute a round-away-from-zero/ceiling
  alternative, which would have predicted `0x3801`. Combined with
  `r16float_mid`, the two probes together pin the direction: the store path
  is consistent with true round-toward-zero truncation from *both* sides of
  `0.5`, not merely "always rounds down within its own exponent bracket
  without regard to sign" (a distinction the negative-side probe alone could
  not make, since floor and round-toward-zero coincide for positive values
  approaching from below).

**Driver takeaway:** a userspace driver relying on Metal-documented
round-to-nearest-even for fp16/fp11/fp10/RGB9E5 texture-store narrowing on
this hardware would be wrong; the observed behavior is consistent with
simple mantissa-bit truncation (no rounding, no renormalization on overflow)
applied uniformly across all four reduced destination precisions tested.

**New finding beyond H1/H2 — R8Unorm tie-breaking is round-half-up, not
round-half-even.** `r8unorm_sep_b` (input `2.5/255.0`, floor=2 **even**) was
specifically designed to discriminate the two rules at an even-floor tie,
where they disagree (round-half-even keeps the even neighbour `2`;
round-half-up always rounds `.5` up to `3`). Observed: `0x03`, i.e.
round-half-up. This is a genuinely new result — `r8unorm_p050`'s existing
tie (`127.5`, floor=127 odd) could not separate the two rules because they
coincide there (both give `128`, the even neighbour), and EXP-0075 explicitly
flagged that limitation. The companion control point `r8unorm_sep_a`
(`1.5/255.0`, floor=1 odd, both rules agree on `2`) matched as designed,
confirming the tie mechanism itself is clean before the discriminating case
is interpreted. **Driver takeaway:** unorm encode ties round half-up
(`round(c x (2^b-1))` with ties away from even, i.e. standard "round half
away from zero" for these non-negative values), consistent across the two
tie points now tested (`127.5->128`, `2.5->3`); this refines EXP-0070's
`RGBA8Unorm`/`R16Unorm` corroboration of the `128/255` and `64/127` decode
values, which those two points alone could not have separated from
round-half-even.

## INTERPRETED

- For all 14 formats on this M4, a 1x1 shared-storage buffer-backed texture
  with `MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead` was created and
  both the store and typed-read pipelines compiled and executed: no
  public-API rejection anywhere in the 37-case matrix, reproduced across two
  independent runs.
- Normalized 8-bit unorm/snorm encode is round-to-nearest with **ties
  breaking away from zero / up** (round-half-up), not round-half-even — a
  refinement over EXP-0070/EXP-0075, which could not separate the two rules.
- The **snorm8 encode scale is symmetric** (`round(c x 127)`, `0x81` for
  `-1.0`), not the asymmetric `[-1,1]->[-128,127]` clamp convention — H1
  resolved.
- **Reduced-precision float store narrowing (fp16, fp11, fp10, and the
  RGB9E5 shared mantissa) truncates toward zero** with no rounding and no
  overflow renormalization — a single consistent rule across four
  destination precisions, and different from the normalized-integer path's
  round-half-up — H2 resolved.
- The typed compute read of every format fills missing channels as
  `(r, 0, 0, 1)` for R/RG formats and returns authored alpha for RGBA;
  integer reads return alpha 1 for R formats (corroborates EXP-0070/
  EXP-0075).
- `128/255` decodes to fp32 `3f008081`, `64/127` to `3f010204`, and `2/255`
  to `3c008081` — all the correctly-rounded fp32 of the exact quotients
  (corroborates EXP-0070/EXP-0075 on the compute path).
- `RG11B10Float` layout is confirmed: R in bits `[10:0]` (e5m6, no sign), G
  in bits `[21:11]` (e5m6), B in bits `[31:22]` (e5m5) — the EXP-0072/
  EXP-0075 layout slip is corrected and independently reproduced.

Alternatives not excluded: the truncation could live in a compiler-emitted
f32->f16/f11/f10/e5m9 convert instruction rather than the store unit itself
(this experiment cannot attribute it to a specific pipeline stage); the
round-half-up finding is established at exactly two tie points per format
family (`127.5`/`2.5` for unorm8, `63.5` for snorm8 — the snorm8 tie point
itself was not re-tested for half-up vs half-even discrimination this round,
only the H1 scale question); NaN/inf/subnormal and out-of-range inputs were
not probed; no filtering, blending, atomics, MSAA, resolve, compressed, or
depth/stencil behavior was probed; only 1x1 in-bounds access was exercised;
16-bit snorm/unorm formats were not tested (only 8-bit).

## DRV-FMT-01 batch-2 answer

**CLOSED for this experiment's scope** (compute-store + typed-read path,
14 named formats, 37 authored cases, M4/G16G, public Metal API only):
complete owned backing bytes and typed-read words are recorded, byte-exact
repeat-verified, for every case; every conversion/rounding/scale question
this batch set out to answer (H1, H2, and the new round-half-up finding) is
resolved with a positive, falsifiable, repeat-confirmed result, not left as
`INFERRED`. This does not close DRV-FMT-01 as a whole — see "What this
experiment does NOT establish" below and `APPLE9_RE_IMPLEMENTATION_GAPS.md`
for the remaining format-capability surface (sampled/filtered read, atomic,
renderable/blendable, MSAA, compressed, 16-bit normalized formats, buffer
textures, and the fragment/PBE store path already covered separately by
EXP-0070).

## What this experiment does NOT establish

No PBE/storage-descriptor behavior (nothing native was emitted or inspected
— public API only); no native command-stream or encoder-level claims; no
Linux/Mesa mapping; no A18/G17P inference (A18 was hands-off; the M4 is the
sole target and M4<->A18 equality for these specific conversion rules is not
re-established here, though `EXP-M4-*` establishes byte-identity for every
driver-emittable subsystem in general); no filtering/blending/MSAA/
compressed/atomic/renderable behavior; no 16-bit normalized formats; no
NaN/infinity/subnormal/out-of-range input behavior; no attribution of the
truncation rule to a specific hardware pipeline stage (store unit vs a
compiler-emitted convert instruction) versus another.

Evidence label: **HW-VALIDATED** for every case's specific texel/read-word
result (independently generated MSL, executed on real hardware, byte-exact
repeat across two independent runs, adversarial hypothesis-to-falsify
framing with a named falsifier per rule-c case) — not merely
`OWN-SHADER-DIFF` or `STRUCTURAL`, per `CODEX.md`'s evidence-strength
ladder, because the expected values were pre-registered as falsifiable
predictions before capture and the hardware's answer (agreeing or
disagreeing) was captured twice, byte-exact, independently of the
pre-registered value.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL (`kernels/format_batch2.metal`), authored harness/runner/verifier/analyzer, public status/error objects, and complete owned buffer readbacks; EXP-0075's disclosed registration-slip prose and candidate-finding prose (read as hypotheses to test, never as evidence)
Apple binary introspection: NONE (no archive, no compiled-shader bytes, no command stream, no pointer, no private interface)
Reproduction: `python3 -B verify.py --captured`; `python3 -B make_manifest.py --check`; full re-capture requires a new successor experiment number per `../CODEX.md` (never repair/rerun in place)
Evidence: `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/` (80 files total, append-only), `analysis.json`, `manifest.json`, `PROGRESS.md`

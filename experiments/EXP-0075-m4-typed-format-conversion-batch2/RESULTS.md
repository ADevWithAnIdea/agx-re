# EXP-0075 results — M4 public typed-format conversion, batch 2

**STOPPED AFTER RUN 01 — the contracted second run is unreachable.** Run 01
captured clean, complete, and fully verified; run 02 could not begin because
EXP-0075's frozen `pre_second_run_gate` sequence
(`verify.py --between-runs`, then `verify.py --selftest`) is self-contradictory:
`--between-runs` requires `raw/` to exist, while `--selftest` is implemented
(and contracted) as a PRE_GPU-only check and fails on the closed-root check the
moment `raw/` exists. Repairing `verify.py` or `run.py` now would break the
capture-time hash binding recorded in `raw/m4-20260827-run01/00_inputs.json`
(the EXP-0064/0073 quarantine class), so per `../CODEX.md` no repair was made.
**The pre-registered promotion rule is therefore unmet and NO DRV-FMT-01 claim
may be promoted from this experiment.** Everything below is a single-run
observation set from one verified run — honest, reproducible from
`raw/m4-20260827-run01`, and repeat-unverified. Successor: the next free experiment
number (EXP-0077 at the time of writing; EXP-0076 is concurrently taken by the
buffer-robustness-matrix experiment) — see the end of this file and
PROGRESS.md.

Target: **local Apple M4 (G16G), macOS 26.6.2 (25G82), Metal 4, arm64,
device name "Apple M4"**, public Metal API only. Nothing here is an A18/G17P,
Linux, native-command-stream, or PBE-descriptor result.

## Gate results

| gate | result |
| --- | --- |
| `verify.py --preflight` | **PASS** (first attempt, PRE_GPU tree) |
| `verify.py --selftest` | **PASS** (schema + smoke-gate + 12 tamper checks, PRE_GPU tree) |
| host build (`xcrun clang -fobjc-arc harness/probe.m`) | clean; one public `fastMathEnabled` deprecation warning |
| non-recorded smoke invocation, attempt 1 | **STOPPED the run pre-capture** — real defect caught: my regenerated kernel header had dropped `#include <metal_stdlib>` / `using namespace metal;` (harness exit 3, `library_failed`, `MTLLibraryErrorDomain|3|... use of undeclared identifier 'access'`). No `raw/` tree was created; repair authorized and made. **The fix-2 gate did its job.** |
| non-recorded smoke invocation, attempt 2 | **PASS** (one complete, self-consistent `r32float_exact` record) |
| `raw/m4-20260827-run01` | **CAPTURED** — exactly the 37 contracted files, no `STOP.json`, 34/34 case processes exit 0, no timeout, no OS exception, no API rejection |
| `verify.py --between-runs` | **PASS** (run01 complete, closed, every receipt/payload/guard/provenance binding verified) |
| `raw/m4-20260827-run02` | **NOT CREATED — blocked** by the self-contradictory frozen gate (see header) |
| `verify.py --captured` / `analysis.py --write` / `make_manifest.py --check` | `--captured` and `analysis.py` require both contracted runs → **not runnable**; `make_manifest.py --check` **PASS** over the retained tree |

## OBSERVED (single run, `raw/m4-20260827-run01`)

All 34 cases: runtime library compiled (`library_ok` true), both compute
pipelines created, 1x1 shared-storage buffer-backed texture created under
`MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead`, command buffer status 4
(completed), `fast_math_enabled` false, `msl_language_version` 262144
(raw public `MTLCompileOptions.languageVersion` on a fresh options object;
consistent with a (major<<16)|minor encoding at 4.0, recorded as a raw value),
device "Apple M4", machine arm64, os "Version 26.6.2 (Build 25G82)". All four
guard regions intact in all 34 records. **No public-API rejection occurred for
any of the 14 formats** — including RG11B10Float and RGB9E5Float on the
compute write+read path.

Complete owned backing bytes and typed-read words per case ("exp" = frozen
pre-registered expectation; "obs" = observed; texel bytes are the physical
little-endian backing bytes at offset 64; words are the four little-endian
uint32s the typed compute read produced):

| case | format | status | exp texel | obs texel | exp words (LE) | obs words (LE) | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r8unorm_p100 | R8Unorm | ok | `ff` | `ff` | 3f800000 00000000 00000000 3f800000 | 3f800000 00000000 00000000 3f800000 | match |
| r8unorm_zero | R8Unorm | ok | `00` | `00` | 00000000 00000000 00000000 3f800000 | 00000000 00000000 00000000 3f800000 | match |
| r8unorm_p050 | R8Unorm | ok | `80` | `80` | 3f008081 00000000 00000000 3f800000 | 3f008081 00000000 00000000 3f800000 | match |
| rg8unorm_p100_p050 | RG8Unorm | ok | `ff80` | `ff80` | 3f800000 3f008081 00000000 3f800000 | 3f800000 3f008081 00000000 3f800000 | match |
| rg8unorm_zero_p100 | RG8Unorm | ok | `00ff` | `00ff` | 00000000 3f800000 00000000 3f800000 | 00000000 3f800000 00000000 3f800000 | match |
| r8snorm_p100 | R8Snorm | ok | `7f` | `7f` | 3f800000 00000000 00000000 3f800000 | 3f800000 00000000 00000000 3f800000 | match |
| r8snorm_zero | R8Snorm | ok | `00` | `00` | 00000000 00000000 00000000 3f800000 | 00000000 00000000 00000000 3f800000 | match |
| r8snorm_p050 | R8Snorm | ok | `40` | `40` | 3f010204 00000000 00000000 3f800000 | 3f010204 00000000 00000000 3f800000 | match |
| r8snorm_m100 | R8Snorm | ok | `80` | `81` | bf800000 00000000 00000000 3f800000 | bf800000 00000000 00000000 3f800000 | deviation: texel |
| rg8snorm_p100_p050 | RG8Snorm | ok | `7f40` | `7f40` | 3f800000 3f010204 00000000 3f800000 | 3f800000 3f010204 00000000 3f800000 | match |
| rg8snorm_m100_zero | RG8Snorm | ok | `8000` | `8100` | bf800000 00000000 00000000 3f800000 | bf800000 00000000 00000000 3f800000 | deviation: texel |
| rgba8snorm_pack | RGBA8Snorm | ok | `8000407f` | `8100407f` | bf800000 00000000 3f010204 3f800000 | bf800000 00000000 3f010204 3f800000 | deviation: texel |
| r16float_exact | R16Float | ok | `0038` | `0038` | 3f000000 00000000 00000000 3f800000 | 3f000000 00000000 00000000 3f800000 | match |
| r16float_mid | R16Float | ok | `0038` | `ff37` | 3f000000 00000000 00000000 3f800000 | 3effe000 00000000 00000000 3f800000 | deviation: texel+words |
| r16float_third | R16Float | ok | `5535` | `5535` | 3eaaa000 00000000 00000000 3f800000 | 3eaaa000 00000000 00000000 3f800000 | match |
| rg16float_exact_mid | RG16Float | ok | `00380038` | `0038ff37` | 3f000000 3f000000 00000000 3f800000 | 3f000000 3effe000 00000000 3f800000 | deviation: texel+words |
| rg16float_third_third | RG16Float | ok | `55355535` | `55355535` | 3eaaa000 3eaaa000 00000000 3f800000 | 3eaaa000 3eaaa000 00000000 3f800000 | match |
| r32float_exact | R32Float | ok | `0000803f` | `0000003f` | 3f000000 00000000 00000000 3f800000 | 3f000000 00000000 00000000 3f800000 | deviation: texel |
| r32float_mid | R32Float | ok | `ffffff3e` | `ffffff3e` | 3effffff 00000000 00000000 3f800000 | 3effffff 00000000 00000000 3f800000 | match |
| r32float_third | R32Float | ok | `abaaaa3e` | `abaaaa3e` | 3eaaaaab 00000000 00000000 3f800000 | 3eaaaaab 00000000 00000000 3f800000 | match |
| rg11b10float_exact | RG11B10Float | ok | `0038c071` | `80031c70` | 3f000000 3f000000 3f000000 3f800000 | 3f000000 3f000000 3f000000 3f800000 | deviation: texel |
| rg11b10float_mid | RG11B10Float | ok | `0038c071` | `7ffbdb6f` | 3f000000 3f000000 3f000000 3f800000 | 3efe0000 3efe0000 3efc0000 3f800000 | deviation: texel+words |
| rgb9e5float_exact | RGB9E5Float | ok | `0001027c` | `0001027c` | 3f000000 3f000000 3f000000 3f800000 | 3f000000 3f000000 3f000000 3f800000 | match |
| rgb9e5float_mid | RGB9E5Float | ok | `0001027c` | `ffffff77` | 3f000000 3f000000 3f000000 3f800000 | 3eff8000 3eff8000 3eff8000 3f800000 | deviation: texel+words |
| r16sint_1 | R16Sint | ok | `0100` | `0100` | 00000001 00000000 00000000 00000001 | 00000001 00000000 00000000 00000001 | match |
| r16sint_2 | R16Sint | ok | `0200` | `0200` | 00000002 00000000 00000000 00000001 | 00000002 00000000 00000000 00000001 | match |
| r16sint_3855 | R16Sint | ok | `0f0f` | `0f0f` | 00000f0f 00000000 00000000 00000001 | 00000f0f 00000000 00000000 00000001 | match |
| r16uint_1 | R16Uint | ok | `0100` | `0100` | 00000001 00000000 00000000 00000001 | 00000001 00000000 00000000 00000001 | match |
| r16uint_2 | R16Uint | ok | `0200` | `0200` | 00000002 00000000 00000000 00000001 | 00000002 00000000 00000000 00000001 | match |
| r16uint_3855 | R16Uint | ok | `0f0f` | `0f0f` | 00000f0f 00000000 00000000 00000001 | 00000f0f 00000000 00000000 00000001 | match |
| r32sint_1 | R32Sint | ok | `01000000` | `01000000` | 00000001 00000000 00000000 00000001 | 00000001 00000000 00000000 00000001 | match |
| r32sint_2 | R32Sint | ok | `02000000` | `02000000` | 00000002 00000000 00000000 00000001 | 00000002 00000000 00000000 00000001 | match |
| r32sint_3855 | R32Sint | ok | `0f0f0000` | `0f0f0000` | 00000f0f 00000000 00000000 00000001 | 00000f0f 00000000 00000000 00000001 | match |
| rgba16uint_pack | RGBA16Uint | ok | `010002000f0f0000` | `010002000f0f0000` | 00000001 00000002 00000f0f 00000000 | 00000001 00000002 00000f0f 00000000 | match |

25/34 exact matches; 9 deviations (5 texel-only, 4 texel+words). Deviations are
results, not surprises; two of them are corrections of my own registration
arithmetic (below).

### Deviation record

1. **snorm8 `-1.0` → `81` (−127), expected `80` (−128)** — `r8snorm_m100`,
   `rg8snorm_m100_zero`, `rgba8snorm_pack`. The typed read still returns exactly
   `bf800000` (−1.0), i.e. the decode of `81` is −127/127 = −1.0. This resolves
   the pre-registered rule-c uncertainty in favour of the **symmetric x127
   scale**: encode = `round(c × 127)`, not the [-1,1]→[-128,127] mapping.
2. **fp32→fp16 narrowing rounds toward zero** — `r16float_mid`, and the G
   channel of `rg16float_exact_mid`. The authored mid literal
   `0.5 − 2^-25` (exact fp32 `0x3EFFFFFF`) is 2.98e-8 below 0.5 but 2.44e-4
   above the next fp16 down, so round-to-nearest-even must give `0x3800` (0.5);
   observed is `0x37FF` = 0.499755859375, read back as `3effe000`
   (= 0.499755859375 exactly). The store path **truncates** the destination
   mantissa. (`r16float_third` = `0x3555` is consistent with truncation as well
   as with RNE; only the mid literal separates them, and it says truncation.)
   This refutes the rule-b hypothesis (documented round-to-nearest-even).
3. **RG11B10Float layout confirmed; registration word was a slip** —
   `rg11b10float_exact` observed `80031c70` (word `0x701C0380`), exactly the
   value pre-derived in PRE_REGISTRATION.md: fp11(0.5) = `0x380` in R[10:0] and
   G[21:11], fp10(0.5) = `0x1c0` in B[31:22]. All three typed reads return
   `3f000000` (0.5). The adopted expectation `0038c071` was an EXP-0072
   derivation slip, as pre-registered.
4. **RG11B10Float narrowing also truncates** — `rg11b10float_mid` observed word
   `0x6FDBFB7F`: R = G = `0x37f` (E=13, M=63), B = `0x1bf` (E=13, M=31), which
   decode to 0.49609375/0.49609375/0.4921875 — exactly the values the typed
   read returned (`3efe0000 3efe0000 3efc0000`). Round-to-nearest would have
   produced 0.5 in all three channels. Field layout, no-sign e5m6/e5m5
   encoding, and truncation are all confirmed by this one case.
5. **RGB9E5Float narrows by mantissa truncation with no overflow
   renormalization** — `rgb9e5float_mid` observed word `0x77FFFFFF`
   (`ffffff77`): E = 14, M = 511 in all three channels, i.e. 511/1024 =
   0.4990234375, read back as `3eff8000` (= 0.4990234375 exactly). The
   pre-registered rule-c hypothesis (mantissa overflow at 511.99999998
   renormalizes to E=15, M=256 → 0.5) is refuted: the mantissa is truncated in
   place. `rgb9e5float_exact` (0.5 → `0001027c`, E=15, M=256) matches.
6. **`r32float_exact` — my registration slip, corrected by hardware** —
   observed texel `0000003f` (word `0x3F000000` = 0.5) with read word
   `3f000000`. The adopted texel expectation `0000803f` (`0x3F800000` = 1.0)
   was arithmetically wrong (the read-word expectation was right); my
   PRE_REGISTRATION re-derivation check repeated the error instead of catching
   it. The observation is internally consistent and the read words match.

Exact tested range: one authored compute `access::write` store to `uint2(0,0)`
of a 1x1 texture per case, and one typed compute `read(uint2(0,0))` in the same
command buffer; inputs limited to the frozen constants (+1.0, 0.0, 0.5, −1.0,
`0.5 − 2^-25`, `1.0/3.0`, and integers 1, 2, 3855); formats limited to the 14
listed; storage mode Shared; usage ShaderWrite|ShaderRead; fast math disabled.

## INTERPRETED (not promotion-ready: single run, repeat-unverified)

- For all 14 formats on this M4, a 1x1 shared-storage buffer-backed texture
  with `MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead` was created and
  both the store and the typed read pipeline compiled and executed: no
  public-API rejection anywhere in the matrix.
- Normalized integer encode is round-to-nearest (ties 127.5 → 128 and 63.5 → 64
  are consistent with both half-even and half-up; these two points do not
  separate them), with the **snorm scale = x127 symmetric** (`-1.0` → `0x81`).
- Reduced-precision float store narrows by **round-toward-zero** (mantissa
  truncation) in fp16, fp11, fp10, and the RGB9E5 shared-exponent mantissa —
  a single consistent rule across four destination precisions, and different
  from the normalized-integer path's round-to-nearest.
- The typed compute read of every format fills missing channels as
  (r, 0, 0, 1) for R/RG formats and returns authored alpha for RGBA; integer
  reads return alpha 1 for R formats (corroborates EXP-0070).
- 128/255 decodes to fp32 `3f008081` and 64/127 to `3f010204`, both the
  correctly-rounded fp32 of the exact quotients (corroborates EXP-0070's
  RGBA8Unorm/R16Unorm observations on the compute path).

Alternatives not excluded: the truncation could live in a compiler-emitted
f32→f16 convert instruction rather than the store unit (this experiment cannot
attribute it); the snorm tie points do not distinguish half-even from half-up;
NaN/inf/subnormal and out-of-range inputs were not probed; no filtering,
blending, atomics, MSAA, resolve, compressed, or depth/stencil behavior was
probed; only 1x1 in-bounds access was exercised.

## What this experiment does NOT establish

No PBE/storage-descriptor behavior (nothing native was emitted or inspected —
public API only); no native command-stream or encoder-level claims; no Linux /
Mesa mapping; no A18/G17P inference (A18 was hands-off; the M4 is the sole
target and M4↔A18 equality for these paths is not re-established here); no
promotion into `docs/` — the contracted two-run byte-exact repeat was never
captured, so every observation above stays single-run evidence pending a
successor that completes the contract.

## Required successor fix (next free number: EXP-0077)

1. `verify.py`: make `--selftest` runnable in the post-run01 state (it is
   read-only and in-memory; the PRE_GPU-only restriction is what contradicts
   the frozen gate order), e.g. allow the tree state "exactly `raw/run01`" for
   the selftest and keep the no-raw requirement only for `--preflight`.
2. Add a self-test that proves **each contracted gate sequence is satisfiable
   in the tree state where it is invoked** (a state-machine check: preflight +
   selftest in the PRE_GPU state; between-runs + selftest in the run01-present
   state; captured in the both-runs state). EXP-0075's self-test proved the
   schema and the smoke gate satisfiable but not the gate graph — that is the
   third contract bug in a row (EXP-0073: unsatisfiable receipt schema;
   EXP-0072: unverifiable payload; EXP-0075: unsatisfiable gate order), and it
   is cheap to kill permanently.
3. Re-register the same 34-case matrix with corrected expected words for the
   three registration slips (`r32float_exact` texel `0000003f`;
   `rg11b10float_exact`/`_mid` texel per layout `0x701C0380`/`80031c70`), and
   with the truncation rule (b/c notes) updated to "truncate" as the new
   hypothesis-to-falsify. Everything else — kernels, harness, buffers, smoke
   gate, runner structure — can be carried over as-is; the harness and both
   dispatched fixes are proven.
4. Optional strengthening while re-registering: add value points that separate
   round-half-even from round-half-up (e.g. unorm8 1.5/255 → 1.5, 2.5/255) and
   a positive-direction truncation probe for fp16 (e.g. 0.5 + 2^-12) so the
   round-toward-zero rule is falsifiable in both directions.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL (`kernels/format_batch2.metal`), authored harness/runner/verifier, public status/error objects, and complete owned buffer readbacks
Apple binary introspection: NONE (no archive, no compiled-shader bytes, no command stream, no pointer, no private interface)
Reproduction: `python3 -B verify.py --between-runs` (run01 verification); `python3 -B make_manifest.py --check`; full re-capture requires the successor
Evidence: `raw/m4-20260827-run01/` (37 files, append-only), `manifest.json`, `PROGRESS.md`

# EXP-0103 — M4 FP32/FP16 arithmetic, transcendental, and SFU semantics

**Question.** Answers the 31-item Part II questionnaire clusters `FP-*` (14),
`TRIG-*` (10), `SFU-*` (7) in `APPLE9_RE_IMPLEMENTATION_GAPS.md`: exact FP32/FP16
arithmetic semantics (rounding, DAZ/FTZ scope, signed zero, NaN propagation/payload,
infinity handling, fused-vs-separate multiply-add), transcendental accuracy and
special-case behavior (`rcp`, `rsqrt`, `sqrt`, `exp2`, `log2`, `sin`/`cos` and their
range reduction), and the SFU's estimate+refine contract. **HIGH VALUE target:**
whether `rcp`/`rsqrt`/`sqrt`/`exp2`/`log2` share EXP-0074's finding that precise FP32
division is DAZ+FTZ (correctly rounded except subnormal operands/results flush to
signed zero) — `docs/isa/encoding-tables.md`'s `fspecial_est` note currently flags
this `UNKNOWN`.

**Method.** Authored MSL (`kernels/probe.metal`) compiled at runtime via the public
`newLibraryWithSource:` API, dispatched by a generic harness
(`harness/probe.m`) against frozen, seeded input corpora
(`analysis/corpus.py` → `analysis/gen_all.py` → `work/cases/*.bin`), compared
bit-exact/ULP against a host oracle computed from exact `Fraction`/`int` arithmetic
(`analysis/exact_ref.py` — never float64-then-cast). Finite-resource mandate applied:
FP16 `rcp`/`rsqrt`/`sqrt` (fast+precise) are tested **exhaustively** over all 65536
bit patterns.

**Target.** Local Apple M4 (G16G) only, public Metal API only. No A18 (hands-off).

**Clean-room category.** HW-PROBE + OWN-SHADER + PUBLIC (MSL Shading Language
Specification function names only — no Apple binary was disassembled, decompiled, or
otherwise introspected; only our own MSL source, compiled through the public runtime
API, and its numeric output were ever inspected).

**Read first:** `PRE_REGISTRATION.md` (full per-item disposition table for all 31
items, exact frozen method, hypothesis, and disclosed pre-freeze engineering including
a self-corrected clean-room process slip) and `CAPTURE_CONTRACT.json` (machine-readable
frozen grammar). `RESULTS.md` is written after both contracted capture runs complete.

## Reproduce

```sh
python3 analysis/exact_ref.py                 # host-oracle self-test
python3 analysis/gen_all.py                    # regenerate frozen corpora (idempotent)
python3 verify.py --selftest && python3 verify.py --seqtest && python3 verify.py --preflight
python3 run.py --execute --run-id m4-20260828-run01
python3 run.py --execute --run-id m4-20260828-run02
python3 verify.py --captured
python3 analysis/score.py                       # ULP tables / per-item verdicts -> RESULTS.md data
```

## Layout

- `kernels/probe.metal` — every authored MSL kernel (one per op/precision/dtype).
- `harness/probe.m` — generic ObjC Metal harness (compiles, dispatches one named
  kernel per process invocation, writes JSONL).
- `analysis/exact_ref.py` — correctly-rounded host oracle (exact rational arithmetic).
- `analysis/corpus.py`, `analysis/gen_all.py` — frozen, seeded input corpora + the
  reference values computed from them (`references.json`, `corpus_manifest.json`).
- `run.py` — gated capture runner (selftest/seqtest/smoke gate/per-case subprocess
  dispatch/append-only receipts).
- `verify.py` — the five standing gates (`--selftest`, `--seqtest`, smoke-gate
  helpers used by `run.py`, `--preflight`, `--between-runs`, `--captured`).
- `raw/<run-id>/` — append-only capture output (receipts + per-case results).
- `PROGRESS.md` — milestone log (crash-safety: a kill costs at most one milestone).

# EXP-0079 progress log (append-only operational record)

Note: this file is an operational log, not capture-bound evidence. The
capture-bound blobs (contract, pre-registration, kernels, harness, and the
four Python tools) are hash-frozen at capture time in `raw/*/00_inputs.json`
and in `CAPTURE_CONTRACT.json`.

## 2026-08-28 (UTC) — successor scaffold authored (PRE_GPU)

- Read in full: `../CLAUDE.md`, `../CODEX.md`, `../experiments/SUBAGENT_BRIEF.md`,
  and every file of `../EXP-0075-m4-typed-format-conversion-batch2/`
  (QUARANTINE, PRE_REGISTRATION, CAPTURE_CONTRACT, kernels, harness, run/
  verify/analysis/make_manifest, RESULTS, README, PROGRESS). EXP-0075's
  run01 tree was read only as disclosed-slip/hypothesis source (its own
  prose), never as raw evidence to copy.
- Confirmed EXP-0079 is the correct, free successor number (orchestrator's
  own EXP-0075 quarantine commit names it explicitly; `experiments/`
  listing confirmed no existing EXP-0079).
- Independently re-derived, in a scratch Python session (not copying
  EXP-0075's stated corrections), all three registration-slip corrections
  (`r32float_exact`, `rg11b10float_exact`, `rg11b10float_mid`) via a
  from-scratch bit-level fp32->eXmM/fp16 converter, and confirmed the
  RG11B10Float truncation-alternative reconstruction (`7ffbdb6f`) matches
  EXP-0075's raw hardware observation bit-for-bit under the corrected
  layout — evidence for the layout correction, not for H2.
- Authored `kernels/format_batch2.metal`: 34 EXP-0075 store-kernel bodies
  carried over byte-identical, plus 3 new kernels
  (`s_r8unorm_sep_a`/`s_r8unorm_sep_b`/`s_r16float_pos_trunc`) and the 3
  unchanged typed-read kernels (40 kernel lines total).
- Copied `harness/probe.m` byte-identical from EXP-0075 (process-exit
  discipline proven on real hardware there: 34/34 untruncated run01
  records); updated only the top-of-file attribution comment.
- Authored `run.py`: same smoke-gate design as EXP-0075 (unchanged), gate
  sequence updated to the corrected contracted order (`--selftest`,
  `--seqtest`, `make_manifest.py --check`, then `--preflight`/
  `--between-runs`), new `GATE_TIMEOUT=900s` ceiling on gate-step
  subprocess calls, run IDs updated to `m4-20260828-run01`/`-run02` (actual
  capture date).
- Authored `verify.py` with the two structural fixes: (1) `--selftest` is
  now state-agnostic (`capture = raw.exists()` passed through to
  `static()`, the old hardcoded `not raw.exists()` requirement removed);
  (2) new `--seqtest` gate-sequence state machine (`build_fixture()` +
  `run_state_gates()` + `seqtest()`) walking PRE_GPU/RUN01_PRESENT/
  RUN02_PRESENT via isolated fixture trees under `work/seqtest/`, each
  proven via real subprocess invocations of the fixture's own copied
  verify.py/make_manifest.py/analysis.py. `CASES` tuple extended to the 37
  frozen case IDs in contract order.
- Authored `analysis.py`/`make_manifest.py` (run-ID constant updated only;
  otherwise unchanged from EXP-0075's proven design).
- Generated `CAPTURE_CONTRACT.json` programmatically (`build_contract.py`,
  scratch, not committed) from a reviewed 37-case Python list, each case's
  `expected_texel_hex`/`expected_read_words_le` computed via `struct.pack`
  (never hand-typed hex), validated for hex-length/format-count invariants
  before writing; blob hashes computed against the final authored files.
- Wrote `PRE_REGISTRATION.md` with the corrections, H1/H2 hypothesis
  framing, new-case rationale, and both independent re-derivation
  transcripts.
- Next action: `make_manifest.py --write`, then
  `verify.py --preflight` / `--selftest` / `--seqtest`; iterate until all
  three pass.

## 2026-08-28 (UTC) — pre-GPU gates green; --seqtest caught a real bug on its first run

- `make_manifest.py --write` then `verify.py --preflight` **PASS** on the
  first attempt.
- Host syntax check (`xcrun clang -fsyntax-only -fobjc-arc harness/probe.m
  -framework Metal -framework Foundation`): clean, one expected
  `fastMathEnabled` deprecation warning.
- `verify.py --selftest` **PASS** on the first attempt (state-agnostic fix
  exercised in the PRE_GPU state here; the post-capture state is exercised
  below).
- `verify.py --seqtest` **FAILED on its first invocation**:
  `FAIL seqtest RUN01_PRESENT: between-runs exited 1: FAIL sw_vers
  m4-20260828-run01`. Root cause: `build_fixture()`'s synthetic
  `00_inputs.json` reused `run.py`'s real `env_record()` output verbatim,
  whose `sw_vers`/`xcrun_version`/`device_model` receipts carry `cwd` equal
  to the *real* experiment directory (captured once, for real, against the
  real `HERE`), while the fixture subprocess's own `validate_run()`
  reconstructs `cwd` equal to the *fixture root*. This is a pre-GPU,
  zero-cost, zero-risk bug catch — exactly what `--seqtest` exists for.
  Fixed by rewriting those three receipts' `cwd` field to the fixture root
  in `build_fixture()` before writing them.
- Regenerated `CAPTURE_CONTRACT.json` blob hashes (verify.py changed) via
  the scratch `build_contract.py` generator, `make_manifest.py --write`,
  then `verify.py --seqtest` **PASS**: 4/4/5 real subprocess gate checks
  across the PRE_GPU/RUN01_PRESENT/RUN02_PRESENT fixtures. Re-ran
  `--preflight` and `--selftest`: both still **PASS**.

## 2026-08-28 (UTC) — run01 captured clean; the previously-unreachable gate sequence now passes

- `python3 -B run.py --run-id m4-20260828-run01 --execute`: internal gate
  sequence (`--selftest`, `--seqtest`, `make_manifest.py --check`,
  `--preflight`) all **PASS**, host build clean, non-recorded smoke
  invocation **PASS**, then `raw/m4-20260828-run01/` created: 40 files (37
  cases + 00_inputs/01_host_build/run_manifest), no `STOP.json`, all 37 case
  processes exit 0.
- `make_manifest.py --write` (now state=CAPTURED), then, in the contracted
  order: `verify.py --selftest` **PASS** — ***this is the exact invocation
  that quarantined EXP-0075***, now running cleanly with `raw/run01`
  present; `verify.py --seqtest` **PASS**; `make_manifest.py --check`
  **PASS**; `verify.py --between-runs` **PASS**. `work/` confirmed empty
  after all of the above (no leftover seqtest fixture artifacts).

## 2026-08-28 (UTC) — run02 captured clean; full contract satisfied end to end

- `python3 -B run.py --run-id m4-20260828-run02 --execute`: same internal
  gate sequence **PASS** (using `--between-runs` in place of `--preflight`
  since `a.run_id == RUNS[1]`), host build clean, smoke **PASS**,
  `raw/m4-20260828-run02/` created: 40 files, no `STOP.json`, all 37 case
  processes exit 0.
- `make_manifest.py --write`, `verify.py --selftest` **PASS**, `verify.py
  --seqtest` **PASS**.
- `python3 -B analysis.py --run-a m4-20260828-run01 --run-b
  m4-20260828-run02 --write`: **PASS**, `repeat_exact: true` — every one of
  the 37 case payloads is byte-identical between run01 and run02, including
  the 8 cases that deviate from the pre-registered expected value.
- `make_manifest.py --write` then `--check` **PASS** (state=CAPTURED),
  `verify.py --captured` **PASS** — the final gate.
- Inspected `analysis.json`: 29/37 match, 8/37 deviation, 0 rejections. All
  8 deviations are rule-c (hypothesis-to-falsify) cases; every one resolves
  cleanly: H1 confirmed (snorm8 symmetric scale, 3/3 cases), H2 confirmed
  (reduced-float truncation, 4/4 cases across fp16/fp11/fp10/RGB9E5), and a
  new finding beyond H1/H2: R8Unorm ties round half-up, not half-even
  (`r8unorm_sep_b` = `0x03`, discriminating; `r8unorm_sep_a` = `0x02`,
  non-discriminating control, as designed).
- Wrote final `RESULTS.md` (OBSERVED/INTERPRETED, full verdict table, H1/H2
  verdicts, gate table, DRV-FMT-01 batch-2 answer, clean-room attestation).
- Next action: `make_manifest.py --write` once more to pick up the final
  `RESULTS.md`/`PROGRESS.md` text, then `make_manifest.py --check` and
  `verify.py --captured` one last time before handing off to the
  orchestrator for docs/provenance promotion and commit.

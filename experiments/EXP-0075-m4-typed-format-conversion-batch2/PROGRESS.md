# EXP-0075 progress log (append-only operational record)

Note: this file is an operational log, not capture-bound evidence. The
capture-bound blobs (contract, pre-registration, kernels, harness, and the four
Python tools) are hash-frozen at capture time in `raw/*/00_inputs.json` and in
`CAPTURE_CONTRACT.json`.

## 2026-08-27 (UTC) — successor scaffold authored (PRE_GPU)

- Read in full: `../CLAUDE.md`, `../CODEX.md`, `../experiments/SUBAGENT_BRIEF.md`,
  and every file of `../EXP-0072-m4-typed-format-conversion-batch2/`
  (PRE_REGISTRATION, CAPTURE_CONTRACT, kernels, harness, run/verify/analysis/
  make_manifest, QUARANTINE, PROGRESS, RESULTS, README). EXP-0072's run-01 tree
  was NOT read as data (non-evidence; truncated records).
- Authored `kernels/format_batch2.metal` (34 store kernels + 3 typed readers,
  body byte-identical to the EXP-0072 registration, new header comment only).
- Authored `harness/probe.m` with fix 1 (single locked print-then-flush-then-exit
  path; `main()` blocks forever after both phase waits; dispatch-phase semaphore
  never signalled) plus the per-case `msl_language_version` public read.
- Authored `run.py` with fix 2 (contract-named pre-capture non-recorded smoke
  invocation into `work/<run-id>/smoke/`, before `raw/` is created; pre-capture
  failures retained in `work/<run-id>/STOP.json`), `verify.py` (fix-1 structural
  checks, smoke-contract checks, smoke-gate self-test, work-clean gate),
  `analysis.py`, `make_manifest.py`.
- Generated `CAPTURE_CONTRACT.json`: 34 frozen cases over 14 formats adopted
  verbatim, fresh blob hashes, run IDs `m4-20260827-run01`/`-run02`,
  `capture.pre_capture_smoke` named as a required pre-capture step.
- Wrote `PRE_REGISTRATION.md` including the independent re-derivation check:
  33/34 adopted expected words reproduce; the RG11B10Float exact/mid texel word
  re-derives to `80031c70` (word `0x701C0380`) under the standard e5m6/e5m5
  layout and the adopted `0038c071` is flagged as a suspected slip and kept as
  the hypothesis of record per the dispatch.
- Next action: write the PRE_GPU manifest, then `verify.py --preflight` and
  `verify.py --selftest`; iterate until both pass.

## 2026-08-27 (UTC) — pre-GPU gates green on the first attempt

- `python3 -B make_manifest.py --write` (PRE_GPU manifest over the 11 authored
  documentation/tool files), then `python3 -B verify.py --preflight` **PASS**
  (closed root, contract case matrix, blob bindings, fix-1 harness discipline
  structure, smoke-contract grammar, no `raw/`, `work/` clean).
- `python3 -B verify.py --selftest` **PASS**: live cross-checks against run.py's
  builders (`rec`, `env_record`, `env_problems`, `run_manifest_record`,
  `case_argv`), harness payload-key extraction == frozen 30-key set, synthetic
  two-run capture (ok + all four rejection statuses) through every schema gate
  and the run-to-run comparison, the smoke validator accepting a complete
  record and rejecting five truncation cut points + eight payload defects +
  four receipt defects, and twelve tamper variants failing closed (including a
  truncated case stdout, the exact EXP-0072 failure class).
- Host-side `xcrun clang -fsyntax-only -fobjc-arc harness/probe.m ...`: clean
  apart from the public `fastMathEnabled` deprecation warning (still functional,
  explicitly NO, recorded per case). No files written; tree has no `__pycache__`
  and no symlinks.
- PRE_GPU manifest regenerated after this entry.
- Next action: `python3 -B run.py --run-id m4-20260827-run01 --execute`, which
  gates itself on preflight+selftest, builds the harness, runs the non-recorded
  smoke invocation, and only then creates the append-only `raw/` tree.

## 2026-08-27 (UTC) — smoke gate fired pre-capture on a real defect; repaired

- First `run.py --run-id m4-20260827-run01 --execute` attempt: preflight and
  selftest gates re-passed inside the runner, host build clean, then the
  non-recorded smoke invocation FAILED and the runner stopped BEFORE creating
  `raw/` (`raw` absent; retained `work/m4-20260827-run01/{STOP.json,
  smoke/smoke.json, probe}`). The gate worked exactly as designed.
- Defect (mine, introduced when regenerating the kernel header): the first nine
  lines of EXP-0072's kernel file contained `#include <metal_stdlib>` and
  `using namespace metal;`; my replacement header kept only the comment block,
  so the MSL failed to compile. Recorded outcome: harness exit 3, status
  `library_failed`, `library_ok=false`,
  `library_error=MTLLibraryErrorDomain|3|program_source:11:45: error: use of
  undeclared identifier 'access'; did you mean 'metal::access'?` (plus
  `no template named 'texture2d'` for every kernel). STOP problems list:
  smoke exit code 3; status outside the contracted set; stage flags all false;
  command buffer status 0.
- Also incidentally validated by this failure: the harness process-exit
  discipline (fix 1) — the full JSON record, including the long error string
  and the complete pristine hex/guard tail, was printed and flushed by the
  worker thread's exit path with no truncation, and the receipt captured it
  whole.
- Environment datum observed in the failed record (re-observed per case in the
  capture): `msl_language_version` = 262144 (0x40000), the raw public
  `MTLCompileOptions.languageVersion` value on a freshly allocated options
  object on this host; consistent with a (major<<16)|minor encoding at 4.0 but
  recorded as the raw public value only.
- Pre-capture repair (authorized; nothing captured): restored
  `#include <metal_stdlib>` + `using namespace metal;` at the head of
  `kernels/format_batch2.metal`; the 37 kernel lines are byte-identical to the
  frozen design (verified by direct comparison). Contract blob hashes and the
  PRE_GPU manifest regenerated; retained scratch work tree removed after its
  content was quoted here (it is the non-recorded smoke location by contract).
- Next action: re-run `verify.py --preflight` + `--selftest`, then
  `run.py --run-id m4-20260827-run01 --execute`.

## 2026-08-27 (UTC) — run01 captured complete and clean

- `run.py --run-id m4-20260827-run01 --execute`: internal preflight + selftest
  re-passed, host build clean, **smoke invocation PASSED** (one complete
  `r32float_exact` record: status ok, cb status 4, guards true, texel/words
  self-consistent), then the append-only `raw/m4-20260827-run01/` was created
  with exactly the 37 contracted files (00_inputs, 01_host_build, 34 case
  receipts, run_manifest). No `STOP.json`. `work/` removed by the runner.
- All 34 case processes: exit 0, no timeout, no OS exception, stdout lengths
  1801–1857 bytes — **no truncation** (the EXP-0072 defect class is gone), all
  four guard regions intact in every record, device "Apple M4", machine arm64,
  OS "Version 26.6.2 (Build 25G82)", `fast_math_enabled` false,
  `msl_language_version` 262144 in every record.
- All 34 cases status `ok`: **no public-API rejection for any of the 14
  formats**, including RG11B10Float and RGB9E5Float under
  `MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead` with shared-storage
  buffer backing — every library, both pipelines, every texture, and every
  command buffer (status 4) succeeded.
- Raw observations versus the frozen expectations (recorded verbatim later by
  `analysis.py`): 25/34 exact matches; 9 deviations, all in the texel word, 4
  of which also in the typed read words. Preliminary reading (to be finalized
  only after run02 and the analysis gates):
  - snorm8 `-1.0` → `81` (−127), not `80`: encode is `round(c × 127)`, the
    symmetric scale; typed read still decodes exactly `-1.0` (`bf800000`).
  - `0.5 − 2^-25` narrows **downward** in every reduced float format: fp16
    `ff37` (0x37FF = 0.499755859375, read `3effe000`), fp11/fp10
    (`0x6FDBFB7F`: R=G=0x37F, B=0x1BF → reads 0.49609375/0.49609375/0.4921875),
    RGB9E5 `ffffff77` (E=14, M=511 → 0.4990234375, read `3eff8000`), i.e.
    round-toward-zero with no mantissa-overflow renormalization — refutes the
    round-to-nearest-even rule-b hypothesis and the renormalization rule-c
    hypothesis.
  - `rg11b10float_exact` observed `80031c70` (word 0x701C0380), exactly the
    value pre-derived in PRE_REGISTRATION.md — confirming the standard
    R[10:0]/G[21:11]/B[31:22] e5m6/e5m5 layout and that the adopted contract
    word `0038c071` was a registration slip.
  - `r32float_exact` observed `0000003f` (0x3F000000 = 0.5) with read word
    `3f000000`: the adopted texel expectation `0000803f` (0x3F800000 = 1.0) was
    a second registration slip that my own re-derivation check missed; the
    observation is internally consistent and matches the read-word expectation.
- Note on runtime: all 34 case processes started within a ~0.35 s window; the
  identical MSL source is compiled once (first in the smoke invocation) and the
  host's Metal library cache serves the rest, so per-case wall time is not a
  compilation-latency measurement.
- Next action: regenerate the PRE_GPU→capture manifest, run
  `verify.py --between-runs`, then `run.py --run-id m4-20260827-run02 --execute`.

## 2026-08-27 (UTC) — run02 BLOCKED by a self-contradictory frozen gate; STOP

- `verify.py --between-runs` **PASS** (run01 complete, closed, all receipts,
  payloads, guards, and provenance bindings verified). Manifest regenerated to
  the CAPTURED state and `make_manifest.py --check` **PASS**.
- `run.py --run-id m4-20260827-run02 --execute` failed at its second internal
  gate: `python3 -B verify.py --selftest` → `FAIL closed root`. Root cause: the
  frozen `pre_second_run_gate` list is
  `["verify.py --between-runs", "verify.py --selftest", smoke]`, but
  `verify.py --selftest` is implemented (and contracted) as a PRE_GPU-only
  check — `static()` in the non-capture branch does not admit `raw` in the root
  name set, and the selftest branch additionally requires
  `not raw.exists()`. Between-runs requires `raw/` to exist. The sequence is
  therefore unsatisfiable in exactly the state where it must run, and run02 can
  never begin. `raw/m4-20260827-run02` was never created; the failure happened
  before any directory was made.
- This is a THIRD contract bug, inherited verbatim from EXP-0072's registration
  (which never reached run02, so it never surfaced there). It is not one of the
  two dispatched fixes; both of those worked (see the entries above).
- No repair made: `verify.py` and `run.py` are capture-bound blobs whose
  SHA-256 is recorded in `raw/m4-20260827-run01/00_inputs.json`, and
  `verify.py --between-runs`/`--captured` fail closed on any post-capture drift.
  Editing them would invalidate the clean run01 capture — the EXP-0064/EXP-0073
  quarantine class. Per `../CODEX.md`, a successor takes a new number and a
  fresh pre-registration.
- Final state: `raw/` holds exactly `m4-20260827-run01` (37 files, append-only,
  verified); `work/` is an empty scratch directory (contract: absent or empty);
  no `analysis.json` (the contracted two-run analysis is impossible, and
  writing a run01-vs-run01 self-comparison would misrepresent a repeat).
- Gate outcomes on the retained tree, for reproduction:
  `--preflight` FAIL closed root; `--selftest` FAIL closed root;
  `--between-runs` PASS; `--captured` FAIL derived analysis;
  `make_manifest.py --check` PASS (state=CAPTURED).
- RESULTS.md finalized with the complete single-run observation table (25/34
  matches, 9 deviations), the deviation analysis, the explicit no-promotion
  statement, and the successor fix list (make `--selftest` runnable in
  the run01-present state; add a gate-sequence state-machine self-test; correct
  the three registration slips; optionally add half-even vs half-up separator
  values and a positive-direction truncation probe).
- Next action: none available inside this experiment. Report to the
  orchestrator: EXP-0075 is complete-as-stopped, nothing promotable, successor
  EXP-0077 should re-register the same matrix with the gate fix and capture
  both runs (~2 minutes of GPU time; the harness, runner structure, smoke gate,
  and verifier schema are all proven and carry over).

## 2026-08-27 (UTC) — correction to an earlier entry (append-only)

- The scaffold entry above records that my independent re-derivation check
  found "33/34 adopted expected words reproduce". That was wrong: it was
  **32/34**. I caught the RG11B10Float slip but repeated EXP-0072's
  `r32float_exact` texel error (`0000803f` = 0x3F800000 = 1.0) instead of
  deriving 0.5 = 0x3F000000 → `0000003f`; the hardware corrected it
  (RESULTS.md deviation record item 6). Documented here rather than edited in
  place so the log stays honest.
- Final tallies for the record: 34 cases captured, 25 exact matches, 9
  deviations (5 texel-only, 4 texel+words); of the 9, two are registration
  arithmetic slips corrected by observation (`r32float_exact`,
  `rg11b10float_exact` — the latter pre-predicted), one carries a slip in its
  texel expectation while its read-word hypothesis was genuinely refuted
  (`rg11b10float_mid`), and six are genuine hardware findings (snorm8 −1.0
  encoding; fp16/fp11/fp10/RGB9E5 round-toward-zero narrowing).
- Manifest regenerated after this entry; final gate state unchanged
  (`--between-runs` PASS, `make_manifest.py --check` PASS, `--preflight`/
  `--selftest`/`--captured` correctly fail on the retained tree).

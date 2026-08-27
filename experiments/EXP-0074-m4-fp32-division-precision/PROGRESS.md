# EXP-0074 progress log (append-only)

Operational note recorded at open (2026-08-27): per coordinator direction the
A18 Pro (192.168.170.254) is **hands-off** — no SSH, no probing, no reference —
and `macvdmtool` is never to be run against any target. All work for this
experiment is **local M4 only**, through the public Metal API, which is exactly
the pre-registered scope. No cross-target inference will be drawn.

## 2026-08-27T15:38:00+00:00 — open

- Milestone: experiment opened as the named successor to the quarantined
  EXP-0073 (see `../EXP-0073-m4-fp32-division-precision/QUARANTINE.md`).
  Question: Part-II item **OPT-02**. Design adopted wholesale from EXP-0073's
  frozen registration (same 75 directed pairs, same 4096-pair LCG block, same
  MSL kernel shape, same two-method exactly-rounded FP32 reference). The single
  substantive change is the fix EXP-0073 was quarantined for: one authoritative
  record schema in `verify.py`, plus a `--selftest` that proves every gate is
  satisfiable and fails correctly, required before any build.
- Files written: `kernels/`, `harness/` (empty dirs), this file.
- Exact next action: author `kernels/fdiv_precision.metal` and
  `harness/probe.m`, then `run.py`, `analysis.py`, `make_manifest.py`,
  `verify.py`; smoke-build the harness in a scratch dir; then freeze
  `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` with freshly derived hashes.

## 2026-08-27T15:55:00+00:00 — contract frozen; self-test 18/18; preflight PASS

- Milestone: all authored blobs final and hash-frozen in
  `CAPTURE_CONTRACT.json` (8 blobs: PRE_REGISTRATION.md, README.md,
  kernels/fdiv_precision.metal, harness/probe.m, run.py, analysis.py,
  make_manifest.py, verify.py). Contract state `PRE_GPU`. No Metal compilation
  or execution has occurred for EXP-0074 (the only host-side build so far was a
  throwaway `clang` compile of the harness in a scratch dir, since deleted, to
  prove it links; its only execution was with no arguments, which exits 2 at
  argument validation before any Metal call).
- The fix this experiment exists to make is in and proven:
  - `verify.py` has ONE execution-record checker (`record(z, keys, ...)`) with
    exact key-set equality against `REC_KEYS` (9) for plain receipts and
    `DISPATCH_KEYS` (12) for the dispatch record. Extra keys and missing keys
    both fail, everywhere.
  - `verify.py --selftest` passes 18/18 synthetic cases with no Metal, no
    device, no Apple binary: the preflight, captured (two-run), and
    between-runs gates are each proven SATISFIABLE on a clean synthetic
    capture, and 15 broken shapes each fail for the right reason — base receipt
    in the dispatch slot (the exact EXP-0073 contradiction shape),
    over-keyed/under-keyed dispatch record, mismatched results hash, tampered
    argv, over-keyed `sw_vers` receipt, over-keyed summary, violated guard,
    broken byte-exact repeat, differing cross-run revision, stray raw file,
    short results file, tampered case echo, authored-hash drift, stale
    manifest.
  - `run.py` refuses to capture unless `--selftest` has just passed.
- EXP-0072 lesson applied before capture (coordinator direction):
  - `harness/probe.m` is single-threaded and synchronous; its only return path
    is after `fflush(stdout)` plus an `ferror` check (exit 5 on flush failure),
    so the process cannot exit mid-record. No worker thread, no semaphore.
  - `run.py` now runs a contract-named NON-RECORDED smoke gate before the real
    dispatch: four frozen directed cases (indices 0, 26, 42, 47) dispatched into
    `work/` (never promoted to `raw/`), requiring the summary to parse with
    every expected field present and every result line to be complete,
    well-formed, and echo-correct. Shape only — no arithmetic expectations.
- Reference pre-validated on CPU before capture: 27/27 hand-computed values
  correct under both methods; 0 cross-method disagreements over all 4171 frozen
  cases; no binary64 path anywhere.
- Files written: kernels/fdiv_precision.metal, harness/probe.m, run.py,
  analysis.py, make_manifest.py, verify.py, PRE_REGISTRATION.md, README.md,
  RESULTS.md (PRE_GPU placeholder), CAPTURE_CONTRACT.json, manifest.json,
  PROGRESS.md (this file).
- Exact next action: `python3 -B run.py --execute --run-id m4-20260827-run01`
  (the runner itself re-runs --selftest and --preflight first), then
  `python3 -B verify.py --between-runs`.

## 2026-08-27T16:05:00+00:00 — both captures written; every gate green; analysis complete

- Milestone: capture complete and verified, end to end, on the first attempt.
  No STOP, no fault, no timeout, no guard mutation, no command-buffer error.
  - run 01: `python3 -B run.py --execute --run-id m4-20260827-run01` — runner
    re-ran `--selftest` (18/18) and `--preflight` itself; the non-recorded
    smoke gate passed; 4171/4171 result lines; command-buffer status 4; device
    `Apple M4`; `fast_math=false`; `math_mode_raw=0`;
    `language_version_raw=262144`.
  - `python3 -B verify.py --between-runs` — PASS (run 01 closed, run 02
    authorized). This is the gate that killed EXP-0073; it passes here.
  - run 02: same path, `--run-id m4-20260827-run02`; cross-run provenance
    matched (same revision `840ad570ab29...`, same authored hashes).
  - `python3 -B analysis.py --run-a ... --run-b ... --write` — reference
    self-check green, 0 cross-method disagreements, `repeat_exact: true`
    (run 01 and run 02 result files are byte-identical, also confirmed with
    `cmp(1)`).
  - `python3 -B verify.py --captured` — PASS. `python3 -B make_manifest.py
    --check` — PASS.
  - Process note: the first `--captured` attempt failed closed on
    `closed root: ['analysis.json']` (the intended order is analysis before
    `--captured`; the hash-frozen README lists them the other way round —
    recorded as an erratum in RESULTS.md). No artifact was edited to get past
    it; `analysis.py --write` was simply run first.
- OBSERVED RESULT (OPT-02, this configuration): **No.** 3956/4171 cases
  bit-exact vs the correctly rounded IEEE-754 binary32 reference; 215/4171
  divergent (15 directed, 200 randomized). Every divergence involves a
  subnormal operand (DAZ) or a subnormal-valued correctly rounded result
  (FTZ); all normal/zero/inf/NaN/overflow/underflow-to-zero classes are
  bit-exact. All 58 observed NaNs are the identical canonical quiet NaN
  `0x7FC00000`; NaN payloads are not propagated. A single DAZ+FTZ model
  predicts 4171/4171 observations (0 residuals).
- Files written: `raw/m4-20260827-run01/{00..05}`, `raw/m4-20260827-run02/{00..05}`,
  `analysis.json`, `RESULTS.md` (final, with the required response block),
  `manifest.json` (CAPTURED).
- Exact next action: regenerate the manifest over the final tree, then re-run
  `verify.py --captured` and `make_manifest.py --check` so the last word on
  disk is a passing gate over the exact final bytes.

## 2026-08-27T16:12:00+00:00 — final gates green over the exact final bytes

- Milestone: experiment complete. After the previous entry the manifest was
  regenerated over the final tree (24 artifacts, every file except
  `manifest.json` itself, zero hash mismatches, no symlinks, no binaries, no
  `work/`, no `selftest/` scratch left behind) and all gates were re-run and
  passed on those exact bytes:
  `verify.py --captured` PASS, `make_manifest.py --check` PASS,
  `verify.py --selftest` 18/18 PASS. Raw trees are untouched since capture.
- Nothing outside `experiments/EXP-0074-m4-fp32-division-precision/` was
  created or modified by this experiment; no `git commit` was made (the
  orchestrator commits). No Apple binary, archive, BO, command stream, or
  compiled-shader byte was inspected at any point; no remote target was
  contacted.
- Verdict recorded in `RESULTS.md`: OPT-02 = **No** for this configuration
  (M4/G16G, public Metal, fastMathEnabled=NO): 3956/4171 bit-exact, 215
  divergent, all explained by DAZ+FTZ; all non-subnormal classes bit-exact;
  every NaN result the canonical quiet NaN 0x7FC00000.
- Exact next action: none for this experiment. Recommended successors (for the
  orchestrator): a `fastMathEnabled = YES` arm of the same frozen matrix (the
  relaxed half of OPT-01); OPT-01 proper (does the compiler select two
  observably distinct division sequences, and where); OPT-03/OPT-01 pow items;
  and an FP16-division variant of this matrix. An A18 replication run is out of
  scope while the A18 is hands-off.

# QUARANTINE — this directory is RETAINED but NOT the promoted run01 evidence

**Reason:** `harness/case_exec.py` at capture time wrote each case's scratch
build/dispatch directory (compiled Metal binary archives, buffer `.bin`
files) under `raw/<run-id>/work/<case-id>/`, i.e. **inside** `raw/`. Per
`SUBAGENT_BRIEF.md`, `raw/` must be text/JSON-only evidence — "never binary
archives, `.metallib`, or Apple blobs". This is a harness path bug, found
immediately after this capture completed (before any result was promoted
to `RESULTS.md`), not a defect in the recorded data itself.

**What is and is not affected:**
- `01_results.jsonl`, `01_timing.jsonl`, `00_env.json`, `02_dispatch.json`,
  and `full/*.json` are exactly what `CAPTURE_CONTRACT.json`'s `raw_schema`
  declares, and were not touched after capture (51/51 cases `status=OK`,
  post-capture `--captured` check PASS). Nothing about the actual
  hardware-observed data is in question.
- The extraneous `work/` subdirectory here (compiled `.bin` archives, input
  buffer files) is scratch build output that should never have been placed
  under `raw/`. It is left in place, untouched, per the standing
  never-repair-in-place rule — this directory is simply not used as the
  contract's `run01`.

**Fix applied for the promoted runs:** `harness/case_exec.py` now takes a
`--work-dir` argument pointing at `work/<run-id>/cases/` (a sibling of
`raw/`, not inside it); `run.py` passes it accordingly. This is a pure
scratch-output-location change — it does not alter any buffer construction,
dispatch parameters, decoding, or oracle comparison, so it changes nothing
about what gets measured.

**Promoted evidence:** the official two-run gated capture uses fresh run
ids generated after this fix, recorded in `CAPTURE_CONTRACT.json` and
`RESULTS.md`. This `run01`-named directory is superseded and must not be
cited as the closure evidence for any item.

Per standing rule, this run id (`m4-20260828T063741Z-run01`) is never
reused for a different capture.

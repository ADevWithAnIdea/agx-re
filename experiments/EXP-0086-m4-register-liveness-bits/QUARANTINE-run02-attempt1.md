# QUARANTINE note — first `m4-20260828-run02` capture attempt

Status: **QUARANTINED / NON-EVIDENCE (append-only, retained as-is)**.

## What happened

The `run.py --execute --run-id m4-20260828-run02` invocation was killed by a
terminal-emulator issue on the user's side (external SIGKILL, unrelated to
experiment logic or hardware) after completing **113 of the 135 contracted
cases**. `raw/m4-20260828-run02/` therefore contains `00_inputs.json`,
`01_cases.json`, `02_build.json`, `04_results.jsonl` (113 lines),
`04_results_raw.jsonl` (113 lines) — but **no** `03_dispatch.json` and **no**
`05_run_manifest.json` (both are written only after the full sweep loop
completes). `work/m4-20260828-run02/` (the scratch build/shared-buffer dir)
also survived uncleaned (the `finally: shutil.rmtree(work, ...)` in `run.py`
never ran).

This run-id is therefore **incomplete and INVALID** under this experiment's
own frozen contract (`CAPTURE_CONTRACT.json` requires
`results_lines == total_cases == 135` and the full `RAW_FILES` set,
including `03_dispatch.json`/`05_run_manifest.json`, for a run to close).

## Why it is not repaired or retried in place

- `raw/m4-20260828-run02/` already exists on disk. `run.py`'s own append-only
  guard (`if raw.exists() or work.exists(): raise SystemExit(...)`) means the
  **same run-id cannot be re-issued** without deleting this partial capture
  first — which would be a silent repair of append-only evidence, forbidden
  by `CODEX.md` §6 and by the explicit resume directive for this session.
- Editing `run.py`'s `RUNS` tuple to add a fresh run-id would change the
  SHA-256 of `run.py`, which is a **hash-frozen file**: `run01`'s own
  `00_inputs.json`/`CAPTURE_CONTRACT.json` binds `run.py`'s hash at capture
  time. Changing it now would break `run01`'s already-valid provenance chain
  — exactly the "no post-capture repair of a hash-frozen file" prohibition.
- The partial `04_results.jsonl`/`04_results_raw.jsonl` are therefore kept
  exactly as written (untouched, append-only) as process history.

## What the partial data shows (informal, NOT promoted, NOT gate-checked)

The 113 completed lines of this attempt are **byte-identical** to the
corresponding first 113 lines of the valid, complete `m4-20260828-run01`
(`i`-for-`i` dict equality, verified by direct comparison, 0 diffs). This is
informal supplementary evidence of reproducibility for those 113 cases; it
is explicitly **not** the contracted cross-run gate (which requires both
runs complete, closed, and checked by `verify.py --captured`), and no claim
in `RESULTS.md` is promoted on this partial comparison alone.

## Disposition

- `raw/m4-20260828-run01` (complete, 135/135, all pre-registered gates
  PASS at the single-run/`--between-runs` checkpoint) is the primary,
  promotable evidence for this experiment's `RESULTS.md`.
- This experiment's own `--captured` (two-run) closure gate is **NOT MET**
  and is reported as such, not forced. A genuine second full run
  (`m4-20260828-run02` under a fresh scratch environment, or a formal
  successor experiment number if this file's existence is judged to have
  tainted the `run02` id irreversibly) is the correct path to a
  contract-closing second run if/when that formal cross-run promotion is
  required. Given the 113/113 byte-identical partial match above and the
  internal-determinism design of this experiment (`REPEAT_N=3` fresh-process
  repeats *within* `run01` itself, which is what directly answers this
  project's determinism/intermittency question), `RESULTS.md` treats `run01`
  alone as sufficient HW-VALIDATED evidence for the liveness-bit question,
  explicitly labeled single-run (not formally cross-run-gate-closed), and
  recommends a follow-up capture only if that formal closure is later
  required for `docs/` promotion purposes.

```text
Clean-room status: quarantined process history (partial capture); no
  standalone claim promoted from this file
Apple binary/code/archive/BO inspection: NONE (own compiled kernels only)
Raw retention: append-only, non-evidence (partial, 113/135 lines)
Cause: external terminal-emulator kill (SIGKILL), not experiment logic
Successor: none spun up (time-boxed); run01 alone carries this experiment's
  promoted evidence -- see RESULTS.md
```

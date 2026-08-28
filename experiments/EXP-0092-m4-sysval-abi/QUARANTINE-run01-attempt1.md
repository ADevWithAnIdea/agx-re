# QUARANTINE note — first `m4-20260828-run01` capture attempt

Status: **QUARANTINED / NON-EVIDENCE (append-only, retained as-is)**.

## What happened

The first `run.py --execute --run-id m4-20260828-run01` invocation ran srsweep (256 cases) and 16 of
23 dstsweep cases (272 cases total, `i=0..271`) successfully, then hit a **harness code defect** (not a
hardware fault) at case `i=272` (`dstsweep reg_096`, the first dst-boundary candidate at/above the
documented 96-GPR physical file size) and stopped cleanly via the pre-registered `STOP.json`
mid-sweep-exception path.

**Root cause**: `run.py`'s `parse_lines()` helper initialized its return dict from the wrong side of
the `{prefix: key}` map (`{k: None for k in prefixes}` iterates the PREFIX strings, not the target
field NAMES), so any stdout that did not emit every expected prefixed line (e.g. no `RESULT 0 ` line,
which `tools/agxtest/agxtest.py` only prints on `STATUS OK`) raised `KeyError: 'result'` instead of
resolving to `None`. This is a bug in the OWN harness code, not a finding about the hardware or a
splice-induced GPU fault.

`raw/m4-20260828-run01/` therefore contains `00_inputs.json`, `01_cases.json`, `02_build.json`,
`04_results.jsonl` (272 lines), `04_results_raw.jsonl` (272 lines), and `STOP.json` — but no
`03_dispatch.json` and no `05_run_manifest.json` (both are written only after the full 300-case sweep
completes). This run-id is therefore **incomplete and INVALID** under the frozen `CAPTURE_CONTRACT.json`
(`total_cases` == 300, and the full `RAW_FILES` set is required for a run to close).

## Why it is not repaired or retried in the same run-id

- `raw/m4-20260828-run01/` already exists. `run.py`'s own append-only guard
  (`if raw.exists() or work.exists(): raise SystemExit(...)`) means the SAME run-id cannot be
  re-issued without deleting this partial capture first — a silent repair of append-only evidence,
  forbidden by `CODEX.md` and `experiments/SUBAGENT_BRIEF.md`'s explicit "never reuse or overwrite a
  run id" rule.
- Unlike EXP-0086's analogous incident (an external SIGKILL mid-sweep), this defect is CHEAP to fully
  redo correctly (the bug is a one-line fix and a full 300-case run completes in well under a minute
  thanks to `tools/agxtest/agxtest.py`'s per-source archive cache), so a formal, fully-closed two-run
  pair is obtained rather than accepting a single-run partial closure.

## Disposition

`run.py`'s `parse_lines()` was fixed (initialize from the target key set, not the prefix-string set).
`RUNS` was changed from `("m4-20260828-run01", "m4-20260828-run02")` to
`("m4-20260828b-run01", "m4-20260828b-run02")` for the real, fully-closed capture pair this
experiment's `RESULTS.md` promotes evidence from. `CAPTURE_CONTRACT.json` was regenerated against the
fixed `run.py` and the new run-id pair before any further capture. This `raw/m4-20260828-run01/`
directory and this note are retained, untouched, as process history.

```text
Clean-room status: quarantined process history (partial capture, harness bug); no standalone claim
  promoted from this file
Apple binary/code/archive/BO inspection: NONE (own compiled kernels only)
Raw retention: append-only, non-evidence (partial, 272/300 lines, no 03_dispatch.json/05_run_manifest.json)
Cause: own-code KeyError in run.py's stdout-line parser, not a hardware fault or GPU wedge
Successor: m4-20260828b-run01 / m4-20260828b-run02 (this experiment's promoted evidence)
```

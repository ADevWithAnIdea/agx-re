# EXP-0072 progress log (append-only operational record)

Note: this file is an operational log, not capture-bound evidence. The
capture-bound blobs (contract, pre-registration, kernels, harness, and the four
Python tools) are hash-frozen at capture time in `raw/*/00_inputs.json`.

## 2026-08-27 (UTC) — initial scaffold authored (pre-quota-interrupt)

- Authored: `kernels/format_batch2.metal` (34 store kernels + 3 typed readers),
  `harness/probe.m` (fresh-process public-Metal probe, 120 s compile / 300 s
  dispatch watchdogs), `run.py`, `verify.py`, `analysis.py`, `make_manifest.py`,
  `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` (34-case frozen matrix,
  14 formats, expected words + a/b/c rules).
- No GPU compilation or execution had occurred. Nothing committed (correct).

## 2026-08-27 (UTC) — resume under new standing instructions

- Coordinator instructions now require: (1) incremental PROGRESS.md writes
  after every milestone (this file), (2) a pre-capture verifier self-test
  (lesson from quarantined EXP-0073), (3) local-M4-only operation.
- Operational notes recorded per coordinator: the A18 Pro at 192.168.170.254 is
  HANDS-OFF (currently unreachable, and permanently out of scope for this
  work); never SSH to it, never run macvdmtool against any target. ALL EXP-0072
  testing stays on the local M4 host, public-API only, no byte splicing.
- Read `experiments/EXP-0073-m4-fp32-division-precision/QUARANTINE.md` in full.
  Root cause there: frozen verifier contained an unsatisfiable receipt schema
  (two checks demanding different key sets on the same record); it surfaced only
  after a clean capture, forcing quarantine.
- Applied the lesson to EXP-0072 BEFORE any GPU work. Found and fixed one real
  EXP-0073-class bug in my own frozen `verify.py`: the `command_buffer_error`
  path required status in (1,2,3), but the public SDK header
  (`MTLCommandBuffer.h`) defines NotEnqueued=0, Enqueued=1, Committed=2,
  Scheduled=3, Completed=4, **Error=5** — a real error case would have failed
  verification after capture. Fixed to accept terminal error statuses
  (1,2,3,5) with the error text carried as data.
- `run.py` refactored: record builders (`env_record`, `run_manifest_record`,
  `case_argv`, `build_argv`) are importable so the self-test can prove the
  capture schema against run.py's own writers; each run now gates on
  `--preflight` + `--selftest` (run01) or `--between-runs` + `--selftest`
  (run02).
- `verify.py` gained `--selftest`: live schema cross-checks against run.py's
  builders, harness payload-key extraction vs the frozen key set, a synthetic
  two-run capture (ok + all four rejection statuses, derived from the contract
  expectations) through every schema gate including the run-to-run comparison,
  and ten tampered variants that must fail closed.
- Next action: regenerate `CAPTURE_CONTRACT.json` with the new blob hashes and
  the `pre_capture_gate`/`pre_second_run_gate` entries, write the PRE_GPU
  manifest, then run `verify.py --preflight` and `verify.py --selftest`.

## 2026-08-27 (UTC) — pre-GPU gates green; entering capture

- Fixed pre-GPU (allowed; nothing captured yet): kernel in-bounds check made
  structural (all `uint2(...)` args == `0, 0`); pre-GPU manifest path list
  aligned with the verifier's expected ordering; self-test argv template and
  cross-run tamper target corrected. A stray `__pycache__` from an ad-hoc debug
  import was removed (lesson: always `python3 -B` here).
- `verify.py --preflight` PASS. `verify.py --selftest` PASS (schema gates
  satisfiable against run.py's own builders + harness payload keys; synthetic
  two-run capture incl. all four rejection statuses validates; ten tampered
  variants fail closed). The self-test caught real bugs pre-capture, including
  a wrong `command_buffer_error` status set (Error=5 per public header) — the
  exact EXP-0073 failure class.
- Host-side `clang -fsyntax-only` of harness/probe.m: clean (one deprecation
  warning for the public `fastMathEnabled`, which we set explicitly to NO and
  record per case). No artifacts written.
- PRE_GPU manifest written. Next action: `run.py --run-id m4-20260827-run01
  --execute` (gated on preflight+selftest), then `verify.py --between-runs`.

## 2026-08-27 (UTC) — run01 captured; harness print-race discovered; QUARANTINED

- run01 executed cleanly at the process level: host build ok, 34/34 case
  processes exit 0, all guards intact, device "Apple M4", cb status 4, no
  API rejection / timeout / fault. Tree has exactly the 37 contracted files,
  no STOP.json.
- Post-run payload scan: 0/34 case stdouts parse as JSON; all truncated at
  varying points (most end right at `"os":`). Root cause: in harness/probe.m
  the worker signals the dispatch semaphore BEFORE printing its record while
  main() returns 0 after the wait, so the process exits mid-print and the
  hex/word data (printed last) is lost. Schema self-test could not express
  this class (thread timing, not schema).
- Repairing the harness post-capture would break the frozen hash binding
  (EXP-0064/0073 class), so EXP-0072 is QUARANTINED / NON-EVIDENCE; see
  QUARANTINE.md. raw/m4-20260827-run01 is retained append-only as process
  history only. Successor: EXP-0075-m4-typed-format-conversion-batch2 with
  (1) the exit race fixed (main must block after waits; only the worker's
  exit() ends the process), and (2) a pre-capture non-recorded probe smoke
  invocation whose stdout must parse before the raw tree is created.
- Next action: add quarantine banners to README/RESULTS, document the
  between-runs gate tripping on the retained tree, refresh the manifest.

## 2026-08-27 (UTC) — quarantine finalized

- `verify.py --between-runs` fails closed on the retained tree ("FAIL closed
  root", due to the quarantine banner itself); `analysis.py` fails at payload
  parsing (JSONDecodeError at the truncation point). Both failures are the
  frozen gates tripping correctly on an unusable capture.
- README.md and RESULTS.md carry quarantine banners; QUARANTINE.md records the
  full analysis, disposal rules, and the two concrete successor fixes.
- Final manifest regenerated over the complete quarantined tree. No further
  changes to this directory.
- Post-finalize tidy-up (no evidentiary change): removed the empty `work/`
  scratch parent left behind by the runner (it contains/contained no files and
  appears in no manifest); the contract allows "absent or empty". Manifest
  regenerated after this line. This is the final entry.

# EXP-0092 Progress Log

- 2026-08-27T00:00:00Z (host-local timestamps below use `date -u`) — experiment directory created;
  pilot compiles of `srprobe.metal`/`dstprobe.metal` on the local M4 (macOS 26.6.2, Metal 4) located
  and froze the anchor bytes now pinned in `casematrix.py`.
- 2026-08-27T19:05Z — `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `README.md`, `RESULTS.md` (stub),
  and the full standing gate set (`verify.py --selftest`/`--seqtest`) written and passing 16/16 and
  14/14 respectively before any GPU capture.
- 2026-08-27T19:09Z — first `run.py --execute --run-id m4-20260828-run01` attempt hit an own-code
  `KeyError` in `parse_lines()` (dict initialized from the wrong side of a `{prefix: key}` map) at case
  272/300 (`dstsweep reg_096`) and stopped cleanly via `STOP.json`. Retained untouched as
  `QUARANTINE-run01-attempt1.md` + `quarantine-m4-20260828-run01/` (moved out of `raw/` so the frozen
  contract's PRE_GPU/CAPTURED state machine stays clean). Bug fixed; `RUNS` changed to
  `("m4-20260828b-run01", "m4-20260828b-run02")` for the real capture pair. `verify.py --selftest`/
  `--seqtest` re-run and still 16/16 and 14/14 after the fix.
- 2026-08-27T19:13Z — `m4-20260828b-run01` executed: 300/300 cases, 293 OK / 7 CMDBUF_ERROR
  (all `dstsweep` register candidates >= 96), 1 MISMATCH_EXPECTED (`numworkgroups indirect_zero_x`,
  a pre-registration oracle gap explained in RESULTS.md, not a hardware surprise). ~24s wall time
  (`tools/agxtest/agxtest.py`'s per-source archive cache makes the 279 splice cases cheap after the
  first compile).
- 2026-08-27T19:14Z — `m4-20260828b-run02` executed: 300/300 cases. `analysis.py` found
  `cross_run_byte_identical=False`: exactly one case (`dstsweep reg_112`) differs between the two runs
  (`CMDBUF_ERROR`/`FAULT` in run01 vs. `OK`/`MISMATCH_EXPECTED`, silent zero, in run02) — genuine
  hardware nondeterminism at an out-of-range register, not a harness defect (all six other tested
  registers >= 96 reproduced `CMDBUF_ERROR` identically in both runs). 8 additional informal
  (non-gated) standalone re-runs of `reg_112` alone: 5 fault-out, 3 silent-zero-success — confirms the
  flakiness is real and roughly split, not a fluke of exactly these two runs.
- 2026-08-27T19:20Z — Analysis complete; `verify.py --captured` formally FAILS on the single byte-exact
  cross-run mismatch (as designed — the gate does not paper over genuine nondeterminism). 299/300 cases
  are byte-identical across two independent runs. `RESULTS.md` written with this explicitly reported,
  not hidden, alongside the required per-item response blocks and the finite-resource table.

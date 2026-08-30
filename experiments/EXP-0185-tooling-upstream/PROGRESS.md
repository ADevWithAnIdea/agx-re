# EXP-0185 PROGRESS (append-only)

## 2026-08-30 — M0: dispatch read, references studied

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md` sections 3 and 7.
- Studied the three reference checks and their gates:
  - `EXP-0178-g17p-sysval-tileread/harness/saferunner.py` (+ `fakerunner.py`, `selftest.py` G9)
  - `EXP-0179-g17p-call/harness/saferunner.py` (+ `fakechild.py`, `selftest.py` G1/G2/G3)
  - `EXP-0178-.../harness/verify_remote.py`, `EXP-0178-.../harness/closure_scan.py` (selftest G10)
  - the promotion-gate arithmetic defect: `EXP-0178-.../analysis/verdicts.py::gate` +
    `EXP-0178-.../PROGRESS.md` M8, and the corrected form already carried by
    `EXP-0184-g17p-onefield-b/analysis/verdicts.py`.
- PURE ANALYSIS run: no device, no SSH, no GPU. `tools/agxtest/persistrun.py` will NOT be
  modified (EXP-0184 may be running against it); the patch is handed over as a diff.

## 2026-08-30 — M1: three modules + stub + gate suite in `tools/agxtest/`, all gates green

- `tools/agxtest/saferunner.py` — `PumpedReader`, `make_safe_runner(base)`,
  `make_safe_render_runner(base)`, `SafePersistRunner`. UPSTREAM NOTES preserved and
  merged from both experiment copies; works over an experiment's PINNED `PersistRunner`
  as well as the shared one.
- `tools/agxtest/verify_remote.py` — generalised (contract/remote/prefix/exclude as args,
  pluggable transport `SshRunner` / `LocalRunner`, batched shasum, exit 0/2/3).
- `tools/agxtest/closure_scan.py` — verbatim algorithm, CLI gains `--allow`/`--ignore`.
- `tools/agxtest/fakepersist.py` — device-free stub (modes good/truncate/hang_first/eof_first),
  merged from EXP-0178 `fakerunner.py` + EXP-0179 `fakechild.py`.
- `tools/agxtest/testdata/closure_shadow_{bad,good}.py` — fixtures reproducing the `nb`
  rebind that lost `raw/g17p_20260830_run01`.
- `tools/agxtest/selftest_tools.py` — 8 offline gates T0..T7. **ALL PASS in 2.6 s, no
  device.** T2 reproduces the shared-runner defect deterministically: the shared
  `PersistRunner` raises `ValueError: not enough values to unpack (expected 3, got 2)`
  while the safe one returns `MALFORMED` with the raw lines kept.
- `tools/agxtest/persistrun.py` NOT touched (EXP-0184 may be running against it).

## 2026-08-30 — M2: persistrun patch generated + gated; README section written

- `analysis/make_persistrun_patch.py` builds `work/persistrun_patched.py` from the committed
  original by exact-anchor replacement (each asserted to hit exactly once, so the diff has no
  accidental drift), and emits `analysis/persistrun-DEF-0178-1.patch`.
  **`git apply --check` passes; `tools/agxtest/persistrun.py` is untouched.**
- `analysis/gate_patched_persistrun.py` — **7/7 PASS, no device**: good path byte-identical on
  every pre-existing key; shared runner RAISES on a truncated OUT while the patched one returns
  MALFORMED; cascade fixed; HANG and broken-pipe error strings unchanged; response keys a strict
  superset (exactly `raw`/`discarded_lines`/`restarts`/`malformed_total` added); `saferunner`
  still works over the patched class.
- Raw evidence: `raw/selftest_tools_run01.txt`, `raw/gate_patched_persistrun_run01.txt`,
  `raw/closure_scan_run01.txt`.
- `raw/closure_scan_run01.txt` also runs the upstreamed scanner against the file the defect was
  found in (`EXP-0178/harness/run.py`) and reproduces that experiment's G10 result exactly:
  the same three allow-listed names (`mnem`, `off`, `runner`) and nothing else.
- `tools/agxtest/README.md`: five new rows in the Pieces table + a "why each one exists" section
  per module, and the width-1 promotion-gate pitfall.

## 2026-08-30 — M3: experiment record complete

- `README.md`, `RESULTS.md`, `manifest.json` (29 hashed artifacts, incl. the source copies the
  three modules were lifted from and the untouched `tools/agxtest/persistrun.py`).
- `drafts/SUBAGENT_BRIEF-addition.md` — the pre-capture sequence as three unchained steps
  (scan your harness / verify remote blobs separately / per-child reader + never score a
  malformed response), plus the width-1 gate trap, with the proposed insertion point and a
  one-line diff for the "Existing tools" bullet. **DRAFT — SUBAGENT_BRIEF.md is NOT edited.**
- Final re-verification, all green: `selftest_tools.py` T0-T7 (run02 raw retained alongside
  run01), `git apply --check` on the patch, `gate_patched_persistrun.py` P1-P7.
- `git diff --stat tools/agxtest/persistrun.py` empty — the shared runner is untouched.
- No `git commit` (per dispatch). No device, no SSH, no GPU at any point.

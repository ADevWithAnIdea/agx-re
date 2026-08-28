# EXP-0122 progress log

- 2026-08-28T00:xx UTC — Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md,
  APPLE9_RE_IMPLEMENTATION_GAPS.md DRV-ROBUST-01, docs/P0-P1-CLOSURE.md P1.5, and prior
  EXP-0076/EXP-0095. Confirmed sparse/VM half of P1.5 has zero prior coverage.
- 2026-08-28T00:xx UTC — Exploratory phase (disclosed in full in `PRE_REGISTRATION.md`):
  built a scratch harness, validated low-risk no-dispatch cases, walked the guard-offset
  ladder to 2^48 with no hangs, bisected and triangulated a `2^43`-byte address wraparound,
  discovered and extensively (unsuccessfully) tried to fix a sparse-write-persistence
  negative. All exploratory artifacts retained under `work/` (never promoted to `raw/`).
- 2026-08-28T00:xx UTC — Froze `harness/probe.m` (12 case classes), `kernels/guard_access.metal`,
  `kernels/sparse_access.metal`, `run.py` (case matrices: 62 align rows, 6x3-pass addrsurvey,
  10 maxlen rows, 74 guard cases, 12 sparse_caps combos, 9 sparse_miptail cases, 4
  sparse_unmapped_read, 2 sparse_partial_map, 1 sparse_remap, 6 timestamp sleeps = 87
  processes/run), `verify.py` (5 standing gates), `analysis.py`, `make_manifest.py`.
- 2026-08-28T00:xx UTC — `verify.py --selftest` and `--seqtest` both pass. Wrote
  `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` (authored SHA-256 frozen, git revision
  `72c2dde8afd896e384afa20050bdd040f657ca78` recorded for provenance, not gated on live HEAD).
  `verify.py --preflight` passes (PRE_GPU, hashes match).
- 2026-08-28T00:xx UTC — MILESTONE: `raw/m4-20260828-run01` captured cleanly, no STOP, ~3.9s
  wall time, all 87 process launches completed (no watchdog/timeout in the guard ladder despite
  offsets to 2^45 and the underflow-direction ladder to `2^64-2^43`).
- 2026-08-28T00:xx UTC — `verify.py --between-runs` passes (RUN01_PRESENT, provenance matches
  frozen contract). Capturing `raw/m4-20260828-run02` next.
- 2026-08-28T00:xx UTC — MILESTONE: `raw/m4-20260828-run02` captured cleanly, no STOP, ~3.8s
  wall time, 0 watchdog/timeout results.
- 2026-08-28T00:xx UTC — `analysis.py --write`: cross-run `gated` comparison clean, **0
  mismatches across all 87 cases in both runs**. `analysis/summary.json` + `report.txt`
  written. `make_manifest.py --write` + `--check`: 9 authored files + 28 raw artifacts hashed,
  consistent. `verify.py --captured`: **OK** (11 domains, gated cross-run comparison clean).
  All five standing gates pass end to end.
- 2026-08-28T00:xx UTC — MILESTONE: `RESULTS.md` written (OBSERVED vs INTERPRETED per finding,
  finite-resource tables for BO alignment/maxBufferLength/guard-zero geometry/sparse tile+
  mip-tail geometry/timestamps, explicit "what P1.5 still needs" section, clean-room
  attestation). Experiment complete for its declared scope; not a P1.5 closure by itself.

# EXP-0073 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** on 2026-08-27.

Pre-registration and `verify.py --preflight` passed cleanly, and one capture run
(`raw/m4-20260827-run01`) completed without fault: 4171/4171 case lines, command
buffer status 4, all four guard regions intact, device "Apple M4",
`fast_math=false`, `math_mode_raw=0` (Safe), `language_version_raw=262144`
(MSL 4.0 per the public header), library compile 0.123 s, dispatch 0.001 s.
No compile rejection, timeout, GPU fault, hang, device loss, or reboot occurred.

The run 02 gate (`verify.py --between-runs`) then failed closed on an
**unsatisfiable check inside the frozen verifier itself**: `one_run()` first
required the dispatch receipt to carry exactly the 9 base receipt keys plus
`results_sha256`, `results_lines`, and `summary`, and then passed that same
record to `receipt()`, which requires exactly the 9 base keys. No possible
capture can satisfy both. The failure is a verifier bug, not an observation.

Repairing `verify.py` after capture is not authorized: the frozen
`CAPTURE_CONTRACT.json` binds the SHA-256 of `verify.py`, and the retained
`raw/m4-20260827-run01/00_inputs.json` records that pre-capture hash. Any
post-hoc fix breaks the no-drift binding (or would require rewriting raw
evidence), which is exactly the capture-time-provenance failure that quarantined
EXP-0064. Per the repository contract, no in-place repair or rerun of EXP-0073
is permitted; a successor must take a new experiment number and a fresh
pre-registration.

Disposal of the retained material:

- `raw/m4-20260827-run01/` is retained **append-only as process history only**.
  Its hardware bits must not be staged as evidence, cited, promoted, or used for
  any OPT-02 claim or implementation decision.
- `CAPTURE_CONTRACT.json`, `PRE_REGISTRATION.md`, `manifest.json`, and the
  authored sources stay as the frozen record of what was registered; nothing is
  edited. `README.md` and `RESULTS.md` carry the quarantine banner only.
- The successor is `EXP-0074-m4-fp32-division-precision` (same frozen design,
  verifier fix, plus a preflight synthetic-receipt self-test so a contradictory
  receipt schema fails before any GPU work).

```text
Clean-room status: quarantined process history; no OPT-02 hardware claim
Apple binary/code/archive/BO/compiled-shader-byte inspection: NONE
Raw retention: append-only, non-evidence
Successor: EXP-0074-m4-fp32-division-precision
```

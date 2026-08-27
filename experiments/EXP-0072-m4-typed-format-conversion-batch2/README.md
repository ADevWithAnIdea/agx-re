# EXP-0072 M4 typed-format conversion, batch 2

> **QUARANTINED / NON-EVIDENCE — see `QUARANTINE.md`.** A harness print-race
> truncated every case payload after the append-only capture run 01; no
> hardware claim may be drawn from this tree. Successor:
> EXP-0075-m4-typed-format-conversion-batch2.

Second bounded increment of DRV-FMT-01 (per-format capability and conversion
table), succeeding EXP-0070 (batch 1, fragment-store path). Authored
public-Metal M4 experiment bundle: an MSL matrix of 34 compute-store kernels
over 14 pixel formats, an owned-buffer in-bounds harness (compute store to a
1x1 texture, then a typed compute read in the same command buffer), a
deterministic analyzer, a complete capture manifest, and a fail-closed verifier
with a pre-capture self-test (lesson from quarantined EXP-0073). API-level
rejections for unsupported format/usage combinations were preregistered as
classification data, not failures.

The frozen audit commands remain in the tree; on this quarantined tree they
fail closed by design (`verify.py --between-runs` at the closed-root check,
`analysis.py` at payload parsing):

```sh
python3 -B verify.py --between-runs
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run01
python3 -B make_manifest.py --check
```

`raw/m4-20260827-run01/` is retained append-only as process history only.
`manifest.json` hashes every authored, raw, and derived artifact (except
itself). The runner is retained for the record and must not be invoked.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (no usable observation retained)
Inputs inspected: authored text sources and public status objects
Apple binary introspection: NONE
Reproduction: not applicable (quarantined); successor: EXP-0075
Evidence: `QUARANTINE.md`, `PROGRESS.md`, `raw/m4-20260827-run01` (process history only)

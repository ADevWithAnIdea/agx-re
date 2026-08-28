# EXP-0081 results — M4 device_load/store memory-offset semantics (MEM-01..MEM-05)

**Status: PRE-GPU (frozen, not yet captured).** Populated only from the two
contracted capture runs after `verify.py --captured` passes.

## OBSERVED

(to be filled from `raw/m4-20260828-run01` + `run02` after the captured gate)

## INTERPRETED

(to be filled after analysis.py)

## Per-item verdict blocks

(MEM-01 … MEM-05, filled after capture)

## Exact tested range

(to be filled)

## Target and scope label

M4 / G16G, local host, public Metal API only — splice evidence on our own
compiled kernels. No A18 (G17P) inference; A18 hands-off. No M5 evidence.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL (kernels/), authored harness/runner/verifier/
  analysis/matrix/baseline, and the compiled bytes of our own kernels only
Apple binary introspection: NONE
Reproduction: see README.md command sequence
Evidence: raw/m4-20260828-run01, raw/m4-20260828-run02, analysis.json, manifest.json
```

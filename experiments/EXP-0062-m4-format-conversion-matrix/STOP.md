# EXP-0062 stop record

Status: **STOPPED / RUN 01 NON-EVIDENCE** on 2026-08-20.

The first six-case M4 run is retained append-only under
`raw/m4_20260820_run01/`, but it is not experiment evidence and must not be
staged, cited, summarized, or used to update any P1.2 or other documentation.
There will be no second run, result interpretation, promotion, or in-place
amendment.

## Process defect

The frozen pre-registration states that the compute backing contains a 64-byte
prefix guard, 16-byte payload, and 64-byte suffix guard. That layout totals
**144 bytes**. Elsewhere, the same frozen record incorrectly calls it an
"80-byte compute backing." The committed public harness implements and retains
the internally consistent 144-byte layout (`compute_hex` is 288 hex
characters). Because the implementation does not satisfy the literal frozen
80-byte statement, the run cannot support a clean-room claim.

The mismatch was detected during the required first-run completeness check,
before the mandatory independent repeat. No second run was started.

## Required next step

A future format conversion probe, if authorized, must use a new experiment
number and fresh preregistration. It must state one unambiguous backing size,
commit/review its complete authored inputs before execution, and retain the same
full bounded readbacks. EXP-0062 cannot be repaired retroactively.

```text
Clean-room status: process stop; no promoted hardware observation
Raw retention: append-only, non-evidence
Apple binary/code/BO inspection: NONE
```

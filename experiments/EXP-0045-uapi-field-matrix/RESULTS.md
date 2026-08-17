# EXP-0045 Results — field-complete UAPI obligation inventory

## Direct observations

The pinned header recursively expands to:

- 1 queue field needed by the graphics-code handoff question;
- 52 leaf fields in `drm_asahi_cmd_render`; and
- 12 leaf fields in `drm_asahi_cmd_compute`.

All 65 paths occur exactly once in `field-matrix.tsv`. The verifier rejects missing,
extra, and duplicate paths. `raw/expected-fields.txt` is the committed expected expansion
and is checked against both the public header and the matrix.

Status count at baseline:

- `OPEN`: 30
- `A18-PARTIAL`: 30
- `PUBLIC-ONLY`: 5
- closed: 0

## Interpretation

P0.2/P0.3 cannot be closed by a subsystem-level statement such as "render fields are
known." Each matrix row needs a generation rule, exact representation and range, a live
Apple9 behavior test, and an unchanged-UAPI mapping. Embedded records are independent
obligations: for example, documenting one helper does not establish all six render-helper
leaves and all three compute-helper leaves.

The matrix is intentionally conservative. `A18-PARTIAL` recognizes useful existing
experiments without claiming that a macOS capture supplies the value required by the Linux
UAPI or that the same behavior has been reproduced on the local M4.

## Limitations and next probes

- This experiment proves inventory completeness only, not hardware semantics.
- Existing evidence citations are subsystem starting points, not closure claims.
- EXP-0041, EXP-0042, and EXP-0043 are the first local-M4 producers for helper, graphics
  selection, and stream-framing rows.
- ZLS, BG/EOT, per-field render control, and timestamp behavior require additional live
  experiments.
- All M4 results remain A18-inferred until replayed on A18 Pro.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC
Inputs inspected: pinned MIT-licensed Mesa UAPI header and repository-authored documentation
Apple binary introspection: NONE
Reproduction: experiments/EXP-0045-uapi-field-matrix/verify.sh
Evidence: field-matrix.tsv and raw/expected-fields.txt
```

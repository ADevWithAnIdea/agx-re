# EXP-0045 — Exhaustive unchanged-UAPI field matrix

## Question

Does the P0 closure campaign have a mechanically checked row for every leaf value that
userspace must provide in queue shader-base setup and render/compute commands?

This experiment converts the public UAPI requirement from EXP-0044 into an exhaustive
field manifest. It does **not** establish an Apple9 hardware value.

## Pre-registered hypothesis and falsifier

Hypothesis: recursively expanding the embedded records in `drm_asahi_cmd_render` and
`drm_asahi_cmd_compute`, plus queue `usc_exec_base`, yields exactly the paths in
`field-matrix.tsv`. Every path will have an explicit evidence status and an outstanding
Apple9 closure obligation.

Falsifiers:

- a leaf field from either command is absent from the matrix;
- the matrix names a field absent from the pinned UAPI; or
- two matrix rows claim the same field.

## Public input

- Mesa revision: `3c4d3e46d19f2f4e951f3ae059543b03592f7944`
- File: `include/drm-uapi/asahi_drm.h`
- SPDX: MIT
- SHA-256: `69fe416b7294dfec4794217bd11379effd53caff4e86010bb803f1b34bdf5e89`

`analysis/verify_matrix.py` removes comments, parses the public C struct declarations,
recursively expands embedded records, and compares the result with the matrix. This is a
requirements audit, not binary inspection.

## Reproduction

```sh
./verify.sh
```

Expected terminal line:

```text
PASS: 65/65 required UAPI leaves have exactly one matrix row
```

## Status vocabulary

- `OPEN`: no sufficient Apple9 synthesis evidence is cited.
- `A18-PARTIAL`: existing A18 work observes part of the behavior, but does not yet prove
  the complete unchanged-UAPI generation rule or local-M4 equivalence.
- `PUBLIC-ONLY`: the field's contractual meaning is known from the UAPI, without an
  Apple9 hardware mapping.

None of these statuses means closed.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC
Inputs inspected: pinned MIT-licensed Mesa UAPI header and this repository's documented experiments
Apple binary introspection: NONE
Reproduction: experiments/EXP-0045-uapi-field-matrix/verify.sh
Evidence: field-matrix.tsv, raw/expected-fields.txt, RESULTS.md
```

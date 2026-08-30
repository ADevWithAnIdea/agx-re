# work/ — regenerated scratch, NOT evidence

`isa_m3/` and `isa_vl/` are throwaway COPIES of `tools/agx-isa/` that
`analysis/gate_sensitivity.py` mutates in order to test what each gate is sensitive to
(M3 swaps two operand field names in a `db.json` copy; V1/V1b/V1c fabricate a promotion in a
`validation.json` copy). They are rebuilt from scratch on every run and duplicate ~900 KB of
tool state each.

**Do not commit them** — see `.gitignore` in this experiment's root. The evidence is
`analysis/gate_sensitivity.json` plus the append-only transcript in `raw/mutation_runs.txt`.
Nothing here was ever written back into `tools/`.

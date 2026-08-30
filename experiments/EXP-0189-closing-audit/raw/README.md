# raw/ — deliberately empty

EXP-0189 is a **pure offline audit**: it captured nothing. No device was contacted
(the A18 Pro was down for the whole run), no shader was compiled, and no byte was
spliced. Every observation it reasons over is another experiment's committed,
append-only `raw/` tree, indexed into `work/raw_index.json.gz` by
`analysis/collect_raw.py`.

The immutable inputs this experiment pinned at pre-registration time are
`work/db.snapshot.json` and `work/validation.snapshot.json`; their sha256 sums are
recorded in `PRE_REGISTRATION.md` and `manifest.json`.

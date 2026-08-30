# EXP-0208 — progress log

All steps are offline analysis of committed artefacts. No device contacted at any point;
nine hardware experiments held the A18 Pro for the whole run.

| # | Milestone | State |
|---|---|---|
| 1 | Read `RE_EXPERIMENT_PROCESS_CORRECTIONS.md`, `docs/evidence-classification.md`, `experiments/FIELD-SWEEP-PROTOCOL.md`, `CODEX.md` | done |
| 2 | Enumerate target rows (label ∈ untested / corpus-correlation / tokenization-only / single-template-inference) | done — **496 rows**, 6 already carrying an `axes` record |
| 3 | Index every `raw/**/*.jsonl` record, superset of EXP-0189/EXP-0194 filters | done — 860 files, 5,251,950 lines, 28,870 groups |
| 4 | Index the non-jsonl committed evidence (`.json`/`.txt`/`.log`/`.md`) | done — 17,087 files scanned |
| 5 | Reconstruct per-row label history from the 52 commits to `validation.json` | done — 1,101 rows with history |
| 6 | Six primary lookups per row (L1–L6) | done — 5 rows with zero hits anywhere |
| 7 | Audit what the six lookups missed; find the remaining keyings | done — **six more found** (dotted names, composite names, byte-position names, record-carried spans, legacy split names, sibling descriptors) |
| 8 | Hand-read the pre-EXP-0138 `.log` era and curate what the index cannot reach | done — 10 rows curated with verbatim quotes |
| 9 | Classify all six axes + frozen_gate + hazard + exact counts | done — `analysis/axes.json` |
| 10 | Instrument test against the four documented hazard walls | done — all four rediscovered from raw |
| 11 | Self-audit: two classifier defects found and fixed (`"hang" in "unchanged"`; promoting EXP-M4-14's own `NOT HW-splice` rows) | done |
| 12 | Reports: hazard inventory, contradictions, no-raw audit, flat TSV | done |
| 13 | README / RESULTS | done |

**Not done, deliberately:** no `label` changed, no `validation.json` / `db.json` / `docs/` /
`PROVENANCE.md` edit, no commit. `analysis/axes.json` is a proposal for the orchestrator to
merge after re-deriving.

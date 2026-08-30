# raw/ — append-only evidence

| tree | status |
|---|---|
| `g17p-20260830-run01/` | **RETAINED, superseded, never re-run.** The capture that exposed the two generator defects recorded in `PRE_REGISTRATION.md` AMENDMENT 1: `device_load.ld_format` writing extra registers, and `iadd2.srcA` not being inert on G17P. It is evidence *for* those findings (75 of 100 MAIN_DAG cases corrupted), not a failed attempt to be hidden. |
| `g17p-20260830-run02/` | never started — the id is retired, not reused. |
| `g17p-20260830-run03/` | the contracted gated pair, first run, corrected generator. |
| `g17p-20260830-run04/` | the contracted gated pair, second run. |

Per-run files: `00_env.json`, `01_results.jsonl` (one gated record per case),
`01_timing.jsonl` (non-gated), `02_dispatch.json`, `03_cascade.jsonl` (the known-good witness
re-run every 40 cases), `04_revalidate.jsonl` (majority-of-3 for every contaminated case).

The section 7A witness-gated 5-repeat re-confirmation lives in `../work/reconfirm/`;
`reconfirm01.jsonl` is retained but **not used as evidence** — it was taken inside a
machine-wide hang cascade (see `RESULTS.md` section 4).

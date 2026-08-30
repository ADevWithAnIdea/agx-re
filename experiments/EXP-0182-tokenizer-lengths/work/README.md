# EXP-0182 `work/` — scratch, all of it regenerable

* `tree_before/` — the **pristine pre-fix `tools/agx-isa`** (isadb.py sha256
  `9cda47a1d4b3857c9…`, the pre-registration freeze). `analysis/apply_fix.py` builds every
  candidate from this, so candidates stay reproducible after the fix was applied in place.
  Keep it.
* `isadb.py.before` / `isadb.py.after` — the edited file either side of the change.
* `candidate_isadb/` — just the `isadb.py` each measured candidate produced (the full trees
  were 1.3 MB each and are regenerable in one command).
* `anchors.json.before`, `diffstat.txt`.
* `docs_regen_effect.diff` — what re-running `gen_agx3_xml.py` / `gen_encoding_tables.py`
  changes in `docs/isa/`. Kept for the orchestrator: those two files are stale relative to
  `db.json` and were **already stale before this experiment** (RESULTS.md §8b). `docs/` was
  reverted and is clean.

Rebuild any candidate tree:

```sh
python3 analysis/apply_fix.py work/cand_full   n1 r9 n2 n2b n2c n0c   # what was applied
python3 analysis/apply_fix.py work/cand_n0m    n0m                    # refused (T2)
python3 analysis/apply_fix.py work/cand_r9g    r9g                    # refused (T2)
python3 analysis/apply_fix.py work/cand_r9s    n1 r9 r9s n2 n2b n2c n0c   # refused (T2)
python3 analysis/demo_cvt_bf16_dbfix.py                               # rebuilds work/demo_dbfix
```

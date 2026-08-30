# EXP-0209 — the promotion checker and the seven dashboards

**Type:** tooling and analysis only. **No device was touched.** Nine hardware experiments
were running on the G17P for the duration of this work; every artifact here is derived
from this repository's own committed files.

**Mandate:** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §8 and §9, which are normative and win
over any conflicting rule.

- **§8** — `validate_labels.py` "must not be used as the evidence-promotion gate by
  itself." Build a checker that **opens the cited raw and derived files** and rejects
  promotion on nine specific conditions, emitting **separate geometry, liveness,
  semantics, recipe, target and audit reports**, and which "must not derive a single
  `N of 166 emittable` headline from field labels."
- **§9** — replace the single headline with **seven monotonic dashboards** that
  **cannot reset themselves**, reporting exact numerators and denominators, and saying
  so explicitly where the data does not exist.

## What was built

| file | role |
|---|---|
| `tools/agx-isa/evidence_index.py` | Re-derives per-(instruction, field) facts **from raw**, in mixed formats, under four independent keyings. Never reads a label. |
| `tools/agx-isa/promotion_check.py` | The §8 promotion gate. Nine rules, three-valued verdicts, six separate reports. |
| `tools/agx-isa/dashboards.py` | The §9 seven dashboards, scored against an append-only high-water ledger. |
| `tools/agx-isa/axes_sidecar.py` | Census and cross-check of the §2 `axes` objects (inline in `validation.json` plus `EXP-0208`'s proposals). |

`validate_labels.py` was **not modified**: §8 says it keeps its schema role, and the
promotion checker is a separate program. No label, `docs/` file, `PROVENANCE.md` entry
or `validation.json` row was edited by this experiment, and nothing was committed.

## Layout

```
EXP-0209-dashboards/
  README.md                  this file
  RESULTS.md                 the seven figures, what the checker rejects, and the limits
  analysis/                  derived comparison tables
    emitter_grade_gap.json           per-rule blocking counts over emitter-grade rows
    emittable_set_under_section8.json  the 32 `emittable` mnemonics vs the nine rules
  ledger/
    dashboard_ledger.jsonl   APPEND-ONLY. One line per (dashboard, key, run).
  reports/                   generated; do not hand-edit
    geometry.md liveness.md semantics.md recipe.md target.md audit.md
    promotion_summary.md     per-AXIS summary (never one number)
    promotion_rows.json      one record per claim row, all nine rule verdicts
    dashboards.md/.json      the seven dashboards
    dashboard_detail.json    per-key status and reason, so any figure can be hand-checked
    axes_crosscheck.md/.json §2 axes census and agreement with this run's re-derivation
  work/
    index/                   the evidence index cache, one JSON per experiment
    monotonicity_demo/       a real-data demonstration that the dashboards cannot reset
```

## Reproducing

```bash
# every gate proves it can return BOTH answers before it is allowed to run
python3 tools/agx-isa/evidence_index.py  --selftest
python3 tools/agx-isa/promotion_check.py --selftest
python3 tools/agx-isa/dashboards.py      --selftest
python3 tools/agx-isa/axes_sidecar.py

# build the evidence index over every experiment (~45 s, 272 dirs, 2.1 GB of records)
python3 tools/agx-isa/evidence_index.py --build

# the §8 promotion gate: six separate reports
python3 tools/agx-isa/promotion_check.py

# the §9 dashboards: score, append to the ledger, report
python3 tools/agx-isa/dashboards.py

# score WITHOUT recording (does not touch the ledger)
python3 tools/agx-isa/dashboards.py --no-append

# one row, all nine rules, with the raw facts behind each
python3 tools/agx-isa/promotion_check.py --row falu2.opsel

# gate a proposed verdict file before it is merged
python3 tools/agx-isa/promotion_check.py --verdicts experiments/EXP-XXXX/analysis/field_verdicts.json
```

The dashboards pin `db.json` and `validation.json` by sha256 in every report, because
other agents write the label sidecar concurrently.

## Why the evidence index is not a `.jsonl` / `instr` / `field` scanner

The corpus is in mixed formats: 1.9 GB of `.jsonl`, 0.17 GB of `.json`, and 5.2 GB of
`.txt`/`.log`/`.hex`. **199 of 272 experiment directories yield zero records** under the
naive "`.jsonl` with `instr` and `field` keys" assumption, because the entire
pre-EXP-0138 era writes text logs and per-case JSON — formats in which "a record keyed
by field name" cannot exist at all. A field-name index over that manufactures a **false
absence**, which is how six `validation.json` notes came to claim evidence did not exist
(EXP-0197). So the indexer uses four keyings, reports each separately, and reports
absence under all of them **as `format-unreadable`, not as zero**:

- **K1 named** — `instr == <mnem>` and `field == <field>`
- **K2 byte-span** — `instr == <mnem>`, `field` null or `__`-prefixed, and a
  `byte_index` inside the field's `db.json` byte span
- **K3 grouping** — an arm/carrier/group/case string naming the field or the mnemonic
- **K4 encodings** — hex blobs harvested from *any* format and tokenized with our own
  disassembler (`--deep`; the promotion checker calls it only where K1–K3 found nothing)

## Clean room

Every input is a file this project authored: `db.json`, `validation.json`, and the
committed contents of `experiments/`. No Apple binary was read, disassembled or
introspected. `isadb.py` (our own disassembler) is used only on hex blobs that came out
of our own committed raw.

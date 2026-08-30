# EXP-0176 — the provenance chain: reverse-direction audit and drafted repair

**PURE ANALYSIS. No device, no SSH, no GPU, no `macvdmtool`.** Nothing outside this experiment
directory was written; `PROVENANCE.md`, `docs/`, `tools/agx-isa/db.json` and
`tools/agx-isa/validation.json` were read only.

## Question

`CODEX.md` §9 requires that no hardware fact enters `docs/` without an auditable `PROVENANCE.md`
row. `EXP-0173` measured the **reverse** direction of that chain — committed experiments that
supply facts to `docs/` but have no row — and found 36 experiments with no row, 11 of them cited
in `docs/`. It also found that `claim_reproduced` is `not-mechanically-checkable` for 162 of 171
rows: **existence of evidence is proven, truth of the claims is not.**

Three questions follow, and this experiment answers all three:

1. **Enumerate precisely.** Which committed `experiments/EXP-*` directories have no `PROVENANCE.md`
   row, and which of those are cited in `docs/`? Re-derive independently; do not trust the count.
2. **Draft the repair.** Write a row per missing experiment, in the existing format, stating what
   was actually learned — including the negative results and the refusals to promote.
3. **Sample the truth question.** Pick 10 rows at random, try to reproduce each claim from its own
   cited artifacts, and report what fraction survives.

## Method

- **Independent re-enumeration** (`analysis/enumerate.py`) over **every** `experiments/EXP-*`
  directory — numeric, `M4`, `M5`, `G1`, `O2` — deliberately *not* reusing `EXP-0173`'s script, so
  the count is a second method rather than a re-run. Commit status from
  `git ls-files --error-unmatch`; `docs/` citation by scanning every file under `docs/`.
- **Claim extraction by reading**, not by heuristic: each missing experiment's own committed
  `RESULTS.md` / `report.md` / `QUARANTINE.md` / `STOP.md` / `SUPERSEDED.md` / `PROGRESS.md`.
  `analysis/build_missing_rows.py` carries the hand-authored claim table and merges it with the
  machine-derived facts into `analysis/missing_rows.json`.
- **Citation verification** (`analysis/cite_paths.py`): every path a drafted row cites was checked
  to exist, and every commit hash resolved with `git log --reverse` over the experiment directory.
- **Table-integrity check** (`analysis/table_integrity.py`): GFM-correct cell splitting on
  unescaped `|`, to find rows whose columns shift when rendered and the point at which the table
  stops being a table.
- **Blind reproduction sample** (`analysis/sample_rows.py`): RNG seeded with the fixed constant
  `20260830`, chosen before any row was opened, so the sample is not the convenient rows. Each
  drawn row's specific numbers, byte strings and arithmetic were then recomputed from its cited
  artifacts.

## Reproduce

```sh
python3 experiments/EXP-0176-provenance-chain/analysis/enumerate.py
python3 experiments/EXP-0176-provenance-chain/analysis/build_missing_rows.py
python3 experiments/EXP-0176-provenance-chain/analysis/cite_paths.py
python3 experiments/EXP-0176-provenance-chain/analysis/table_integrity.py
python3 experiments/EXP-0176-provenance-chain/analysis/sample_rows.py
```

All five are read-only over this repository and take seconds. The per-row reproduction checks are
quoted inline in `analysis/reproduction_sample.md`.

## Deliverables

| file | what it is |
|---|---|
| `analysis/missing_rows.json` | every committed experiment with no row: whether `docs/` takes a **fact** from it, its target, status, evidence label, key claims, and any gap between its own text and its artifacts |
| `analysis/drafted_rows.md` | **67 drafted rows**, ranked by exposure, ready to review and paste |
| `analysis/broken_rows.md` | the four defective rows with corrected drop-in text, plus four further structural defects found while checking them |
| `analysis/reproduction_sample.md` | the blind 10-row sample, with a verdict and the recomputation behind each |
| `analysis/enumerate.json`, `analysis/table_integrity.json` | the machine-derived backing data |
| `RESULTS.md` | observations, interpretation, limits, verdict |

## Scope and limits

- **This experiment establishes no hardware fact.** It audits and drafts.
- **`PROVENANCE.md` was not edited.** The orchestrator owns it; everything here is for review.
- **No hardware was run, so no `HW-VALIDATED` claim can be re-observed.** The reproduction sample
  tests the corpus against its own committed artifacts, which is strictly weaker than re-measuring
  the hardware, and says so in every verdict.
- **Target: none.** The audited evidence spans M4/G16G, A18/G17P and M5/G17g; no row's target was
  changed and no M4 observation was promoted to G17P.

```text
Clean-room provenance: OWN-SHADER + PUBLIC (offline re-reading of this repository's own committed
  markdown, JSON and text artifacts only)
Inputs inspected: PROVENANCE.md, CODEX.md, CLAUDE.md, experiments/SUBAGENT_BRIEF.md, docs/**,
  every experiments/EXP-*/{README.md,RESULTS.md,report.md,QUARANTINE.md,STOP.md,SUPERSEDED.md,
  PROGRESS.md,PRE_REGISTRATION.md}, selected experiments/*/raw/*.jsonl|*.txt|*.hex|*.log written
  by our own harnesses from our own MSL, tools/agx-isa/{db.json,validation.json},
  tools/agxtest/agxrun.m, tools/agx-isa/gen_agx3_xml.py, and git history of this repository
Apple binary introspection: NONE. No device was contacted; no GPU dispatch; no macvdmtool;
  no A18, no M4 GPU, no M5.
Reproduction: the five commands above
Evidence: analysis/{enumerate.json,missing_rows.json,table_integrity.json,drafted_rows.md,
  broken_rows.md,reproduction_sample.md}; hashes in manifest.json
```

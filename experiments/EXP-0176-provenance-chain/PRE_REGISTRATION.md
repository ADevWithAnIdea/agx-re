# EXP-0176 pre-registration — provenance-chain audit and drafted repair

**Registered before any analysis file was written.** Pure analysis; no device work is authorized
under this contract, and none was performed.

## 1. Question

Does the reverse provenance chain required by `CODEX.md` §9 hold, and do the corpus's *claims* —
not merely its citations — survive re-derivation from their own artifacts?

## 2. Falsifiable hypotheses

| id | hypothesis | refuter |
|---|---|---|
| **H1** | The set of committed experiments with no `PROVENANCE.md` row is exactly the 36 `EXP-0173` reported, of which 11 are cited in `docs/`. | An independent enumeration over **all** `experiments/EXP-*` (not just `EXP-[0-9]{4}`) returns a different set. |
| **H2** | Every drafted row can cite at least one artifact that exists and one resolvable commit. | Some experiment's committed tree contains no artifact worth citing. |
| **H3** | The 4 defective rows are defective in their **citations**, not their **claims** — i.e. each claim reproduces once pointed at the right artifact. | A defective row's claim also fails to reproduce, or reproduces only against an artifact that does not exist. |
| **H4** | In a blind 10-row sample, **at least 8 of 10** claims reproduce from their own cited artifacts. | Fewer than 8 reproduce. |
| **H5** | `PROVENANCE.md` is a well-formed GFM table throughout. | Some row does not split into 5 unescaped-pipe cells, or the table is interrupted. |

## 3. Independent and controlled variables

- **Independent:** the experiment directory (for enumeration) and the row (for reproduction).
- **Controlled:** the enumeration is over the committed tree at the session's `HEAD`, recorded in
  `manifest.json`; the reproduction sample is drawn with RNG seed `20260830`, **fixed in this
  pre-registration before any row was opened**, so the sample cannot be chosen after the fact.

## 4. Expected observations

- H1 is expected to be **refuted** in the direction of *more* missing rows, because `EXP-0173`'s
  scan regex matches only `EXP-[0-9]{4}` and there are `EXP-M4-*`, `EXP-M5-*`, `EXP-G1*` and
  `EXP-O2*` directories cited throughout `docs/`.
- H4 is the substantive one. It is set at 8/10 deliberately: below that, the corpus's prose would
  be systematically outrunning its data and the finding would dominate everything else in this
  experiment.

## 5. Known confounders, and how each is handled

| confounder | handling |
|---|---|
| `docs/` may name an experiment only to disclaim it ("IN FLIGHT", "quarantined"), which is not a §9 violation | every citation is classified `fact` / `disclaimer` / `none` by reading the citing sentence, not by grep alone |
| an experiment's own `RESULTS.md` may claim more than its artifacts support | claims are recorded with a `gap` field and the drafted row states what IS supported |
| a row may reproduce against its own prose while failing against its `raw/` | wherever `raw/` exists, the reproduction check recomputes from `raw/`, not from `RESULTS.md` |
| substring matching (`"EXP-M5-1" in prov`) can create false positives | ids are matched with a word boundary and the mention count is reported alongside the boolean |
| a row's claim may have been correct when written and refuted since | rows are checked against the **newest** experiment touching the same field, not only their own |
| the auditor could pick agreeable rows | seed fixed here, before selection |

## 6. Frozen deliverables

`analysis/{enumerate.py,build_missing_rows.py,cite_paths.py,table_integrity.py,sample_rows.py}` and
their outputs; `analysis/{missing_rows.json,drafted_rows.md,broken_rows.md,reproduction_sample.md}`;
`RESULTS.md`; `manifest.json`; `PROGRESS.md` appended after every milestone.

## 7. Standing prohibitions for this experiment

- **Do not edit** `PROVENANCE.md`, `docs/`, `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
  `CLAUDE.md` or `CODEX.md`.
- **Do not `git commit`.**
- **Do not inflate a row.** Where an experiment withdrew its own claim, the row records the
  withdrawal; where an experiment's text outruns its artifacts, the row records what is supported
  and flags the gap.
- **Do not touch a device**, and do not disturb the two live experiments.

## 8. Verdict rule, fixed in advance

- H1 refuted iff the independently derived missing set differs from `EXP-0173`'s.
- H3 confirmed only if **all four** named rows' claims reproduce once re-pointed.
- H4 confirmed iff ≥8 of 10 sampled claims reproduce; a `PARTIAL` counts as **not** reproduced for
  the purpose of the threshold.

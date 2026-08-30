# EXP-0195 — the 132 blocked rows whose raw lives in an experiment their label never cited

**Pure desk analysis. No device work, no SSH, no GPU, no compilation, no Apple binary of
any kind was read.** Every input is already committed in this repository.

```
Clean-room provenance: re-analysis of our own committed capture records
Inputs inspected:      tools/agx-isa/{db,validation}.json                  (read only)
                       experiments/*/raw/**/*.jsonl  and  **/*.json        (our own append-only records)
                       experiments/*/analysis/field_verdicts*.json
                       experiments/*/{RESULTS,PROGRESS}.md
                       experiments/EXP-0194-desk-promotion-audit/analysis/* (its gate, reused unchanged)
Apple binary introspection: NONE.
Target hardware:       OFFLINE and unreachable for the whole of this experiment.
Nothing outside experiments/EXP-0195-uncited-raw-sweep/ was created or modified.
No label, no file in tools/agx-isa/, no doc, no PROVENANCE row was edited.  Nothing committed.
```

## Question

EXP-0194 §2 found a structural blind spot in the corpus's own auditing. `EXP-0164`'s
`analysis/audit.py` `gather()` iterates `for eid in evidence` — it opens only the raw of the
experiments a label **already cites**. It can therefore confirm or refute cited evidence and
can never discover uncited evidence. Chasing exactly one such row recovered
`falu2_ext.srcB_neg`, whose own note asked for "a second, structurally different carrier"
that had been committed in EXP-0138 the whole time.

EXP-0194 stopped after one. This experiment asks the population question:

> Of the blocked field rows that have per-case raw in an experiment their label does **not**
> cite, how many survive EXP-0194's gate chain — and how many of those survive **on the
> uncited evidence alone**?

## Population

From EXP-0194's own snapshot (`blocked_rows.json`, 566 blocked field-labels):

```
566  blocked field-labels holding back the 134 non-emittable instructions
-79  `_instruction` pseudo-fields (not fields; EXP-0194 bucket B)
=487 real field rows
 220 of the 487 have per-case raw anywhere in experiments/**/raw/**.jsonl
 132 of the 487 have per-case raw in an experiment the label does NOT cite   <-- this experiment
  62 of those 132 cite NO experiment that holds any raw at all
```

`analysis/enumerate_uncited.py` reproduces 566 / 79 / 487 / 220 / 132 exactly. Citation
resolution is the same rule `tools/agx-isa/validate_labels.py` uses: an evidence string
names a directory when the directory is `<evidence-id>-<slug>` (or the two are equal).

## Method

The brief was explicit: reuse EXP-0194's committed gate, do not reimplement it, do not relax
it. So the criterion here is **`EXP-0194/analysis/adjudicate2.py`, executed unmodified**, with
its eight gates G1, G2, G2b, G3, G4, G5, G7, G8 as documented in EXP-0194 README. The
decisive one is **G7**: two *matching* cases at *different* encoded values carrying *different*
oracles — a committed prediction that **discriminates between field values**. A constant
oracle while the field varies predicts the instruction's effect, not the field's.

1. `analysis/scan_raw_copy.py` — byte-for-byte copy of EXP-0194's `scan_raw.py`, sole change
   being that the output path is env-driven so nothing is written into EXP-0194. Regenerating
   the index gives **files=727 lines=5 201 306 field_records=1 028 378 groups=9 119** and the
   file is **byte-identical** to EXP-0194's committed `raw_index.jsonl` (`cmp` clean).
2. `analysis/extract_copy.py` — same treatment for `extract_candidates.py`; **263 687 records**,
   matching EXP-0194's count.
3. `analysis/enumerate_uncited.py` — defines the 132-row population → `uncited_rows.json`.
4. `analysis/find_refusals.py` — for each of the 132, is there already a documented refusal,
   in the label's own `validation.json` note or in a committed `RESULTS.md`/`PROGRESS.md`
   line? → `documented_refusals.json`.
5. **Run A** — `EXP-0194/analysis/adjudicate2.py` unchanged over the full record stream.
   Output `verdicts_e0195_rerun.json` reproduces EXP-0194's headline **1 / 46 / 519 with zero
   verdict differences on all 566 rows**, which is the proof that the criterion in this
   experiment is the same object EXP-0194 published.
6. `analysis/filter_uncited_records.py` — restrict the record stream to records from
   **non-cited experiments only** (102 770 of 263 687 records). This narrows the *input*; the
   criterion is untouched. It is needed because Run A cannot distinguish "passes the gate" from
   "passes the gate on evidence its label forgot".
7. **Run B** — the *same unchanged script* over the uncited-only stream →
   `verdicts_uncited_only.json`. **This is the answer to the question.**
8. `analysis/classify.py` — joins both runs onto the 132 rows → `classification.json`,
   `row_table.md`, bucket counts.
9. `analysis/g7_diagnostics.py` — falsifier for the gate's own NO: for every row that reached
   G7, does the raw carry an *alternative* prediction key (`predict`, `predicts`) that would
   have discriminated? A gate that refuses a row because the harness spelled a key differently
   would be a false NO.
10. `analysis/scan_nonjsonl_raw.py` — bounds EXP-0194 limitation §5.5 ("I only read `.jsonl`
    under `raw/`") by walking all 6 499 `experiments/**/raw/**/*.json` for per-case
    `(instr, field, bytes)` records.
11. `analysis/verify_recovery.py` — re-derives every surviving claim straight from the raw
    files, with file:line, byte strings, `db.json` geometry, XOR bit-span proof, both oracles,
    both observations and the cross-run table, trusting no intermediate produced by EXP-0194
    or EXP-0195.
12. Second, independent method, **not** a gate: EXP-0194's committed `verdict_crosscheck.json`
    — does the *uncited* experiment's own `analysis/field_verdicts*.json` already carry an
    emitter-grade verdict for the row? This is exactly the signal by which `falu2_ext.srcB_neg`
    was noticed, so it is the natural way to look for more.

## Answer, in one line

**Zero new recoveries.** The gate passes exactly one of the 132 — `falu2_ext.srcB_neg` — and
that row is the one EXP-0194 already recovered and the orchestrator already promoted
(`validation.json` now reads `hardware-run`/M4, evidence `EXP-0138, EXP-0154, EXP-0194`).
The independent second method nominates **51** of the 132; the gate confirms **1**. See
`RESULTS.md`.

## Reproduction

```
SP=<scratch>
E0195_INDEX_OUT=$SP/raw_index.jsonl            python3 analysis/scan_raw_copy.py
E0195_RECORDS_OUT=$SP/candidate_records.jsonl  python3 analysis/extract_copy.py
python3 analysis/enumerate_uncited.py
python3 analysis/find_refusals.py
# Run A -- EXP-0194's gate, unchanged, full stream (must print 1 / 46 / 519)
E0194_RECORDS=$SP/candidate_records.jsonl \
E0194_OUT=$PWD/analysis/verdicts_e0195_rerun.json \
  python3 ../EXP-0194-desk-promotion-audit/analysis/adjudicate2.py
E0195_RECORDS_IN=$SP/candidate_records.jsonl \
E0195_RECORDS_OUT=$SP/uncited_records.jsonl    python3 analysis/filter_uncited_records.py
# Run B -- the SAME unchanged gate, uncited evidence only
E0194_RECORDS=$SP/uncited_records.jsonl \
E0194_OUT=$PWD/analysis/verdicts_uncited_only.json \
  python3 ../EXP-0194-desk-promotion-audit/analysis/adjudicate2.py
python3 analysis/classify.py
E0195_RECORDS_IN=$SP/uncited_records.jsonl     python3 analysis/g7_diagnostics.py
python3 analysis/scan_nonjsonl_raw.py
python3 analysis/verify_recovery.py
python3 analysis/make_table.py
```

The two intermediates (256 MB and 100 MB) live in scratch and are deliberately not committed,
exactly as EXP-0194 did.

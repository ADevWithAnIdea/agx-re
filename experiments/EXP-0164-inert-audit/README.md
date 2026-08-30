# EXP-0164 — adversarial audit of every emitter-grade field in `validation.json`

**Pure analysis. No device work, no SSH, no GPU, no compilation.** Every input is
already committed in this repository.

```
Clean-room provenance: (re-analysis of committed OWN-SHADER / HW-PROBE evidence)
Inputs inspected: tools/agx-isa/validation.json, tools/agx-isa/db.json,
                  experiments/*/raw/**  (our own append-only capture records),
                  experiments/*/RESULTS.md and analysis/ (schema only)
Apple binary introspection: NONE. No Apple artifact of any kind was read.
Reproduction:  python3 analysis/collect_raw.py
               python3 analysis/audit.py
               python3 analysis/tables.py > work/tables_all.md
Evidence:      work/validation.snapshot.json  sha256 c40195cd9f65d9176c5bc518ede1c171cf3904c26ba81f7b93dc2414b1ad7091
               work/db.snapshot.json          sha256 83b83a350ece33b8fd9e98b773f02be2da89a5f942824896574ff22827042341
               repo revision at snapshot      b7dedbf0ce37c0a95823923bc70f3cab0f733b3c
```

## Question

The user's challenge — *"I really don't buy anything is inert; encoding space is
expensive so it seems like Apple would use it well"* — was confirmed on EXP-0155:
every field there that looked inert turned out to be live on a carrier the analysis
had not picked (`tex_sample.samp_extra` inert on nine arms, 128/256 moved on the
tenth). The orchestrator withheld 15 of that experiment's 105 verdicts as a result.

**This experiment asks the same question of every OTHER already-merged verdict:** of
the 664 fields currently labelled `hardware-run` or `isolated-byte-diff`, how many are
supported by movement that reproduces, how many were declared inert on a single
carrier, and how many cannot be re-derived from `raw/` at all?

## Hypotheses

- **H1** — a material fraction of the 664 was promoted from a sweep in which the field
  never moved anything and only one carrier was tried. *Refuter:* < 5% `INERT-SINGLE`.
- **H2** — the representative-arm defect is not unique to EXP-0155. *Refuter:* zero
  fields outside EXP-0155 with an inert arm and a stable-live arm in the same raw.
- **H3** — every emitter-grade field can be re-derived from append-only raw.
  *Refuter:* any promoted field with no traceable per-value raw record.

Falsifiable thresholds, the decision tree, and four controls were frozen in
`PRE_REGISTRATION.md` before any verdict was computed. Amendments A1–A5 are dated and
each says what gap it filled and which direction it moved the answer.

## Method (summary; the binding version is `PRE_REGISTRATION.md`)

1. Pin `validation.json` and `db.json` to hashed snapshots — the live file changed
   under this session twice (`hardware-run` 548 → 553).
2. Index all 728 387 per-value records under `experiments/*/raw/**`.
3. Attribute each case to db.json **fields** from the `bytes` column, not from the raw
   label: varying bit mask per case group, instruction offset recovered by fitting
   db.json's own `match` constraints, then partition by "the instruction word with
   this field's bits cleared". Only partitions holding ≥ 2 distinct values of the
   field test that field.
4. Score liveness with an **oracle-independent** effect signature (hard-failure class
   + digest of what was read back), so a field whose oracle is a per-value host
   prediction is not miscounted as inert.
5. Bucket into `STABLE-LIVE` / `INERT-MULTI` / `INERT-SINGLE` / `UNSTABLE` /
   `SINGLE-RUN` / `UNVERIFIABLE` by the frozen decision tree.
6. Recompute emittability with `validate_labels.py`'s exact rule over the snapshots.

## Outputs

| file | contents |
|---|---|
| `analysis/audit.json` | one record per emitter-grade field: bucket, arms, per-run counts, cross-run agreement, attribution mode, raw paths |
| `analysis/reclassify.json` | the withhold list in `FIELD-SWEEP-PROTOCOL.md` §5 flat `<mnemonic>.<field>` form, plus why each instruction is lost |
| `analysis/emittability.json` | the emittability ladder and the 95%-agreement sensitivity |
| `analysis/experiment_coverage.json` | per cited experiment: raw parse verdict, runs, gated runs |
| `analysis/mixed_arm_liveness.json` | the H2 defect list |
| `analysis/controls.json` | the four pre-registered controls |
| `work/raw_index.json.gz` | the regenerable per-field index (derived, not evidence) |

## Scope limits

This audit measures **auditability from raw**, not truth. `UNVERIFIABLE` means the
chain `documented fact → RESULTS.md → analysis → immutable raw` cannot be walked for
that field with a machine; several of those fields are backed by real hardware splices
whose evidence is committed as prose (EXP-M4-14's `splice_results.json`). Nothing here
retracts a hardware observation; it bounds what a reviewer can reproduce.

`docs/`, `PROVENANCE.md`, `db.json` and `validation.json` were **not** modified.

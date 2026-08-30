# EXP-0186 — Which of tonight's emitter-facing facts never reached `docs/`

**Type:** PURE ANALYSIS. **No device, no SSH, no GPU.** Promotes nothing on its own; produces
drafted text for the orchestrator to apply.

## Question

`CLAUDE.md` states that the deliverable is `docs/`, and that its reader must be assumed to have
**never seen the hardware and to be unable to run any experiment**. The 2026-08-29/30 G17P wave
produced a large number of emitter-facing hardware facts. An orchestrator audit earlier the same
night found that the most emitter-critical defect of the run — the `fspecial` operand swap — was
**absent from `docs/isa/` entirely**, and fixed that one by hand (commit `a7b0ed97`). Nobody
checked the rest.

**Which facts established since roughly `f517d1e8` have NOT reached `docs/`, and what should the
text say?**

## Method

1. Read `PROVENANCE.md` backwards from its most recent rows (182–200, 210, 219, 246–247,
   265–276) — it is the index, and every row names its experiment and artifacts.
2. **Re-read every load-bearing claim in its own experiment `RESULTS.md`.** No fact is drafted
   from a `PROVENANCE.md` row alone. (This rule earned its place: see `DEF-0186-1` in
   `RESULTS.md`.)
3. Cross-check each claim against `docs/isa/README.md`, `docs/isa/encoding-tables.md`,
   `docs/isa/memory-model.md`, `docs/compiler-readiness.md`, `docs/pipeline/README.md`,
   `docs/descriptors/README.md`, `docs/cmdstream/README.md` and `docs/P0-P1-CLOSURE.md`.
4. Rank by **what an implementer would get wrong without it**: a fact whose absence causes a
   *silent wrong answer* outranks one whose absence causes a *fault*, which outranks a
   *missing capability*. A doc that **asserts a refuted claim** ranks with the silent class,
   because it is worse than absence.
5. Draft the text in the register of the surrounding document, carrying the evidence label, the
   **target it was measured on**, and every bound the source experiment declared.

## Hypothesis (stated before the survey)

*Most of the wave's emitter-facing facts are in experiment `RESULTS.md` only.* **Refuter:** a
survey finding that `docs/` already carries them, or carries them with the same bounds.
**Outcome: not refuted** — 0 of 20 surveyed facts are fully present, and 3 are present in a form
a later experiment refuted.

## Scope limits, applied deliberately

- `EXP-0183`, `EXP-0184`, `EXP-0185` have **no `RESULTS.md`** — they are live. Nothing was
  drafted from them.
- `docs/`, `PROVENANCE.md`, `tools/agx-isa/db.json`, `tools/agx-isa/validation.json` and
  `tools/agxtest/` are owned by others and were **read only**. This experiment edits nothing
  outside its own directory.
- The M5 fork (`docs/isa/encoding-tables-m5.md`, `docs/*-m5.md`, `tools/agx-isa-m5/`) is out of
  scope per `CLAUDE.md`.
- `docs/isa/agx3.xml` is generated from `db.json` and is not hand-edited here — but note that it
  therefore **transmits `db.json`'s defects into the deliverable**, which is why `F01` and `F02`
  matter.

## Deliverables

- `analysis/docs_gap.json` — per fact: claim, experiment, artifacts, evidence label, target,
  whether it appears in `docs/` today and in what form, destination file, rank, rank class, and
  the caveats that must travel with it. Plus `provenance_defects` and `not_a_gap`.
- `analysis/drafted_docs.md` — the actual paste-ready text, grouped by destination file and
  ordered by rank.
- `RESULTS.md` — counts, the single worst omission, and the defects found in the index itself.

## Reproduction

Pure desk work; every input is a committed file at `HEAD`. To re-derive the survey:

```
git log --oneline f517d1e8..HEAD
sed -n '182,200p;210p;219p;246,247p;265,276p' PROVENANCE.md
for e in 0163 0168 0169 0172 0174 0175 0178 0179 0180; do
  sed -n '1,80p' experiments/EXP-$e-*/RESULTS.md; done
grep -rn "<claim keyword>" docs/ --include=*.md
```

## Clean-room provenance

```
Clean-room provenance: PUBLIC (this repository's own committed artifacts only)
Inputs inspected: PROVENANCE.md; experiments/EXP-{0163,0168,0169,0172,0174,0175,0178,0179,
  0180,0181,0182}/RESULTS.md; docs/**.md; git log. No shader bytes were compiled, spliced,
  disassembled or executed by this experiment.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. No device was contacted.
Reproduction: this README, "Reproduction"
Evidence: analysis/docs_gap.json, analysis/drafted_docs.md
```

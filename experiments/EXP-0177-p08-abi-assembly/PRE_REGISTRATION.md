# EXP-0177 pre-registration — P0.8 / DRV-ABI-01 evidence assembly

Frozen before any file under `analysis/` was written. This is a **pure-analysis** experiment
(no device, no SSH, no GPU, no compilation, no splicing), so it has no capture contract, no
run ids and no `raw/` observations; its artifacts are the two re-runnable analysis scripts and
the three derived reports.

## Question

`docs/P0-P1-CLOSURE.md` row **P0.8 — DRV-ABI-01** is `OPEN` with an `Active experiment` cell
reading literally `queued`. It is the only P0/P1 row citing no experiment, a fact EXP-0173
recorded independently under closure rule 2. For each sub-area the row names — inputs,
outputs, sysvals, interpolation, tilebuffer, calls, scratch, linking, sideband, and
independently generated blend/logic/conversion epilogs across advertised formats — what does
the committed evidence actually establish, on which target, at what evidence strength, over
what tested range; and what can an implementer still not do?

## Pre-registered expectations (recorded before the survey, so they can be scored)

- **E1.** A substantial body of P0.8-relevant evidence exists and has never been gathered
  under the row. *Expected outcome if true:* ≥10 non-quarantined experiments bear on it.
- **E2.** The evidence is overwhelmingly **M4/G16G**, so under the current target rule
  (closure measured against full G17P) most of it is supporting, not closure, evidence.
- **E3.** At least one sub-area is genuinely near-empty, and the honest report says so rather
  than padding. *The dispatch explicitly anticipated "the honest answer may be that P0.8 is
  barely started"; if the survey supports that, it must be said plainly.*
- **E4.** The row's own six closure rules are not met even for the sub-areas that look
  complete.

## Falsifiers

- E1 is refuted if fewer than ~5 non-quarantined experiments bear on the row — in which case
  "queued" was approximately right and the report should say so.
- E2 is refuted if a majority of the P0.8 sub-areas have gated G17P evidence.
- E3 is refuted if every sub-area has at least one committed, gated, on-target result.
- E4 is refuted if any sub-area demonstrably satisfies all six rules.

## Method (frozen)

Sources restricted to this repository's own committed artifacts and public reference material:
`experiments/*/RESULTS.md`, `experiments/*/README.md`, `experiments/*/QUARANTINE.md`,
`PROVENANCE.md`, `tools/agx-isa/validation.json`, `docs/`, `APPLE9_RE_IMPLEMENTATION_GAPS.md`.
**Nothing is established; every claim is a citation, attributed to the target it actually ran
on.** Two mechanical checks back the narrative and must be re-runnable:

- `analysis/isa_status.py` → `analysis/isa_status.json`: per sub-area, which stage-ABI
  instruction is `emittable`, which fields block it, at what label and on which target, read
  straight out of `tools/agx-isa/validation.json`.
- `analysis/provenance_check.py` → `analysis/provenance_check.json`: for every cited
  experiment, whether it owns a `PROVENANCE.md` row, is quarantined, and is cited in `docs/`.

## Known confounders, declared in advance

1. **`validation.json` and `db.json` are owned by the live EXP-0175.** Any headline number is
   a snapshot and must be labelled as one. They are read only; neither is edited.
2. **Quarantined experiments are non-evidence** and must be excluded by *name*, not silently
   omitted — particularly `EXP-0050-fragment-output-abi`, whose name is the closest in the tree
   to this row's fragment-output sub-area.
3. **Provenance-row ownership needs a heuristic** (older rows cite differently from newer
   ones). The heuristic must be stated and hand-checked against known rows before it is relied
   on.
4. **Sub-area assignment is a judgement call.** The instruction→sub-area mapping must be
   explicit and editable in the script, not implicit in prose.
5. **Cross-target contamination is the standing risk of this exercise.** Several experiments
   cite an A18/G17P result and an M4 result side by side. Every entry must record its own
   target, and no result may be promoted across targets.

## Scope limits

- Do NOT edit `docs/`, `PROVENANCE.md`, `tools/agx-isa/db.json` or
  `tools/agx-isa/validation.json`. The closure-cell replacement is **drafted for review**, not
  applied.
- Do NOT `git commit`.
- Do NOT contact any device.

## Deliverables

`RESULTS.md` structured by the ten sub-areas; `analysis/p08_evidence.json`;
`analysis/p08_gaps.md` ranked by driver impact, naming instruction and field;
`analysis/p08_closure_cell_draft.md`.

## Clean-room statement

```text
Clean-room provenance: PUBLIC (this repository's own committed clean-room artifacts, read only)
Apple binary introspection: NONE — nothing is disassembled, decompiled, executed or compiled.
```

# EXP-0173 — Acceptance-gate audit (pre-registration)

**Written before any verdict was computed.** Frozen at the revision recorded in
`CAPTURE_CONTRACT.json`. Pure analysis: **no device, no SSH, no GPU**. Three device
experiments (EXP-0168 / EXP-0171 / EXP-0172) are in flight concurrently; this experiment
touches none of their files and does not touch the neo.

## 1. The question

`CLAUDE.md` → *Definition of Done* and `docs/P0-P1-CLOSURE.md` → *Completion gate* both say
closure is decided by a **final audit that positively reproduces the claimed generation paths
and proves that no required field or supported operation depends on captured Apple templates
or on inspection of Apple's implementation.** That audit has never been run. This experiment
runs it, at the revision frozen below, and reports where the work stands **against the gate**
rather than against a field count.

Six sub-questions, each independently falsifiable:

| # | Question | Refuter (what would make me report failure) |
|---|---|---|
| Q1 | For each of the six closure rules in `docs/P0-P1-CLOSURE.md`, is the rule met — with the exact command that establishes it? | Any rule for which no command in this repo produces the claimed artifact. |
| Q2 | Does every `PROVENANCE.md` row's cited evidence **exist** and **contain what the row claims**? | Any row citing a path that is absent, or present but not containing the claimed content. |
| Q3 | For how much of the emittable set can an implementer generate an encoding **without a captured Apple template**, and which instructions need a donor? | An instruction counted emittable whose encoding cannot be produced from documented rules alone. |
| Q4 | What is each tool gate (`roundtrip_test.py`, `validate_labels.py`, `emit_worklist.py`, `match_overlap_report.py`, `work/merge_verdicts.py --dry-run`) actually sensitive to? | A gate that passes on an input it should reject. |
| Q5 | How many "fields" are vacuous (zero free bits, i.e. part of `match`), and what do the emitter counts become with them folded into `match`? | — (this is a measurement, reported both ways) |
| Q6 | Are the four named descriptor defects recorded where an implementer would look, and does the "named operand field that cannot be an operand" class have members not yet found? | Any defect not recorded in `docs/isa/README.md` + the descriptor note; any new member of the class. |

## 2. Hypotheses (stated before measurement)

- **H1.** Closure rules 1 and 6 are met **for a proper subset of the ISA only** — the subset
  EXP-0167 generated — and are **not** met for any of the sixteen P0/P1 rows as a whole. I
  expect **0 of 16 rows CLOSED**, and I expect the gate to be **NOT PASSED**.
- **H2.** At least one `PROVENANCE.md` row cites an artifact that does not exist or does not
  contain the claimed content. (Prior base rate: 125+ fields withdrawn in the last day.)
- **H3.** The headline in `docs/P0-P1-CLOSURE.md` (616/1062, 41/166) is **stale** relative to
  `tools/agx-isa/validation.json` at the frozen revision (dispatch states 588 / 35 of 166).
  Refuter: recomputation reproduces 616/41.
- **H4.** The template-dependency question splits the emittable set three ways:
  (a) generable from documented rules alone; (b) generable only because a *rule the
  experiment did not itself measure* supplies a field value; (c) donor-dependent. I expect
  (b) ∪ (c) to be non-empty and to include all control-flow instructions.
- **H5.** `roundtrip_test.py` is symmetric (tokenizer-vs-itself) and therefore **cannot**
  detect an assembler that fails to clear a bit — already proven by EXP-0170; I will
  re-establish it by construction, not by citation.
- **H6.** The 25 zero-free-bit fields should be folded into `match`. Folding lowers both
  numerator and denominator; the emittable-instruction count can only rise or stay equal
  (removing a field can only remove a blocker), so the *instruction* headline is not
  protected by keeping them.
- **H7.** At least one further instruction exists whose named operand field cannot carry an
  operand (fully match-pinned, or zero free bits, or width too small for the register
  class it names). Found three times by accident ⇒ expect more.

## 3. Method (frozen)

Pure analysis, all under `experiments/EXP-0173-closure-audit/`:

1. `analysis/provenance_audit.py` — parse **every** row of `PROVENANCE.md`, extract every
   path-like and `EXP-NNNN` token, test existence on disk, and for rows whose claim is
   checkable mechanically (a number, a hash, a named field/mnemonic, a JSON key) test
   whether the artifact contains it. Emits `analysis/provenance_audit.json` with
   `artifacts_exist` / `claim_reproduced` / `notes` per row. `claim_reproduced` is
   deliberately three-valued: `true` / `false` / `"not-mechanically-checkable"` — I will not
   record a pass I did not compute.
2. `analysis/template_dependency.py` — for each mnemonic in
   `validation.json.coverage.emittable_mnemonics`, classify every field as
   RULE (a documented rule fixes it), FREE (the implementer chooses; needs an emitter-grade
   label + a range that covers more than one value), or DONOR (only a captured value is
   known). Emits `analysis/template_dependency.json`.
3. `analysis/gate_sensitivity.py` — for each tool gate, run it, record exit status and
   headline, then **mutate an input in a way the gate should catch** and re-run. A gate that
   still passes is reported as insensitive. Mutations are made on **copies** under `work/`;
   no tool file and no `db.json` / `validation.json` is modified.
4. `analysis/vacuous_fields.py` — recompute emitter-grade field count and emittable
   instruction count with and without the zero-free-bit fields folded into `match`.
5. `analysis/operand_sanity.py` — sweep every descriptor for a field whose **name** implies
   an operand (`src*`, `dst*`, `base`, `off*`, `imm*`, `data*`, `coord*`, `sampler`,
   `tex*`, `target`) but which cannot carry one: zero free bits, fully match-pinned, or a
   width narrower than the smallest operand its name implies.
6. `analysis/closure_rules.py` — per P0/P1 row and per closure rule, a verdict plus the
   command that establishes it.

## 4. Controlled / independent variables

Independent: none (observational audit of a frozen tree). Controlled: the git revision, the
sha256 of `db.json` / `validation.json` / `PROVENANCE.md`, and the analysis scripts
themselves — all hashed in `CAPTURE_CONTRACT.json`. Three sibling experiments are writing
under `experiments/EXP-0168*`, `EXP-0171*`, `EXP-0172*`; those trees are **excluded from
mutation** and, where their state is read, the read is timestamped so a later change is
visible rather than silent.

## 5. Confounders I expect and how each is handled

| Confounder | Handling |
|---|---|
| **A green gate mistaken for evidence.** | Every gate is tested for *sensitivity* by mutation, not just run. A gate that cannot fail is reported as proving nothing. |
| **Counting my own re-read of a document as reproduction.** | `claim_reproduced` is only `true` when a command recomputed the claim. Re-reading prose is `not-mechanically-checkable`, never a pass. |
| **`validation.json` moving under me** while three device experiments run. | Hash it at freeze; re-hash at the end; report if it moved and re-run the affected numbers. |
| **Denominator shopping.** | Every count is reported with its denominator and both ways where a choice exists (Q5). |
| **Deadline pressure** (run must end by 10:00 PST). | Findings are appended to `PROGRESS.md` and to partial `RESULTS.md` sections as computed, so an unfinished audit degrades to fewer findings, never to softer ones. |
| **My own optimism.** | H1 is pre-registered as *0 of 16 CLOSED, gate NOT PASSED*. If the measurement disagrees I must report the disagreement; the hypothesis is on record either way. |

## 6. Expected observation vs. refuters

- If H1 holds: `analysis/closure_rules.py` reports no row meeting all six rules, and names
  which rules each row misses. Refuter: a row meeting all six with commands that run.
- If H2 holds: at least one row in `provenance_audit.json` has `artifacts_exist: false`.
  Refuter: all rows' cited paths present.
- If H3 holds: the recomputed headline differs from the board's 616/41. Refuter: it matches.
- If H4 holds: `template_dependency.json` shows a non-empty DONOR/unmeasured-RULE set.
  Refuter: every emittable mnemonic is fully RULE ∪ FREE.
- If H5 holds: a deliberately broken assembler still passes `roundtrip_test.py`.
  Refuter: the suite fails, which would make it a genuine emitter gate.
- If H7 holds: `operand_sanity.py` names at least one instruction beyond the four known.
  Refuter: it names exactly the known set and nothing else.

## 7. Out of scope / what this audit cannot do

- It cannot run hardware, so it cannot *re-observe* any HW-VALIDATED claim. It can only check
  that the raw record exists, is internally consistent, and supports the stated claim. A row
  whose raw evidence is present and self-consistent is reported as
  `claim_reproduced: true` **at the analysis level only**; that is explicitly weaker than a
  re-run on G17P and is labelled as such.
- It does not edit `db.json`, `validation.json`, `docs/`, `PROVENANCE.md`, or
  `docs/P0-P1-CLOSURE.md`. Recommendations are reported, not applied.
- It does not `git commit`.

## 8. Clean-room statement

```
Clean-room provenance: PUBLIC (pure analysis over our own committed artifacts)
Inputs inspected: our own db.json / validation.json / PROVENANCE.md / experiments/**, all authored in this repo
Apple binary introspection: NONE — no Apple binary is opened, read, hashed, or executed
Reproduction: bash experiments/EXP-0173-closure-audit/analysis/run_all.sh
Evidence: experiments/EXP-0173-closure-audit/analysis/*.json + raw/
```

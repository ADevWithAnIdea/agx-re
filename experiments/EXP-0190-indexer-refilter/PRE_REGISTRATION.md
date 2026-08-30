# EXP-0190 — PRE-REGISTRATION: the `_`-prefix discard in the raw indexer

**Frozen before any verdict was computed.** Written 2026-08-30, repo revision
`b98b237b1163b45b00e9c01a6137506c7ad59684`.

**PURE OFFLINE ANALYSIS.** No device is contacted; the A18 Pro is down (powered, not
rejoining the network). No shader is compiled. Nothing outside this experiment
directory is written.

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: tools/agx-isa/{db,validation}.json (snapshotted into work/),
                  experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  experiments/*/{analysis,harness}/*.py (our own code)
Apple binary introspection: NONE
```

---

## 1. The defect

`experiments/EXP-0164-inert-audit/analysis/collect_raw.py:186-188` (copied verbatim
into `EXP-0189-closing-audit/analysis/collect_raw.py`):

```python
if fld.startswith("_"):
    pseudo[exp][arm][runid].add(sig_of(rec))
    continue
```

Every raw record whose `field` begins with `_` is routed to the `pseudo` (baseline
signature) side-channel and **never reaches field attribution**. The filter's purpose
is legitimate — `_baseline`, `_live_control` and friends are scaffolding, and counting
them as field observations would be worse than dropping them. But a harness that names
a genuine per-value field sweep with a leading underscore is silently discarded, and
the field then audits as `UNVERIFIABLE` ("no attributable raw record") for a reason
that is a property of **our indexer**, not of the evidence.

EXP-0189 found one instance by hand (`half_alu_ext8.dst`, swept by EXP-0180 under the
name `__dst_nibble`) and reported it against itself. Both the 41/166 and the 38/166
withdrawals — and therefore today's published **37/166, 554/1040** — were computed
through this filter.

## 2. Questions

- **Q1.** What is the complete set of `_`-prefixed `field` names in
  `experiments/*/raw/**/*.jsonl`, and which of them are scaffolding vs genuine field
  sweeps?
- **Q2.** With the filter corrected (not removed), which currently-withdrawn fields are
  re-derivable from committed raw under the **unchanged** EXP-0164 rule?
- **Q3.** Is there a tenth check in this chain that cannot come out the other way?

## 3. Hypotheses, and what refutes each

**H1 (calibration).** At least one `_`-prefixed name in the corpus is a genuine
per-value field sweep. Already known true for `__dst_nibble`; it is stated so that a
failure to re-detect it is a failure of *this* experiment's tooling.
*Refuter:* the corrected indexer does not attribute EXP-0180's `__dst_nibble` records
to `half_alu_ext8.dst` → the fix is wrong, stop and report.

**H2.** Correcting the filter restores at least one field to emitter-grade under the
unchanged rule, and therefore at least one instruction to emittable.
*Refuter:* after correction, no currently-withdrawn field reaches `STABLE-LIVE`. This
is an **acceptable and publishable outcome**: "the filter was wrong and it changed
nothing." It will be reported as such, without relaxing anything to avoid it.

**H3.** A further check in the audit chain cannot come out the other way (the tenth
instance of the shape found nine times today).
*Refuter:* no such check found; reported as a clean negative.

## 4. Classification rule for `_`-prefixed names — fixed before inspection

Each distinct name is classified **by inspection of the records it labels and of the
harness that emitted them**, never by a name pattern. A name is `FIELD-SWEEP` only if
**both**:

1. **Structural:** its records carry a `bytes` column that *varies* within a
   (experiment, instr, name, arm, run) group, and the varying bits land inside at least
   one `db.json` field of the descriptor the bytes match; **and**
2. **Intentional:** reading the emitting harness and the surrounding records shows the
   name denotes a sweep over an encoding position — i.e. the record's `value` is the
   value written into that position — rather than a baseline, control, detector,
   calibration, latency, power, or health probe.

Anything else is `SCAFFOLDING` and stays in `pseudo`. If (1) and (2) disagree, or the
emitting harness cannot be located, the name is reported `UNCLASSIFIED` and treated as
`SCAFFOLDING` — the conservative direction, because the failure mode being repaired
over-counts `UNVERIFIABLE` and the opposite failure would inflate the headline.

**Every distinct name is reported with its experiments, record count, classification
and reason** in `analysis/underscore_fields.json`. There is no silent bucket. A name I
cannot classify is published as unclassified.

## 5. Frozen thresholds — inherited unchanged from EXP-0164 §5

```
MIN_COMMON            = 2
MIN_AGREE_PCT         = 99.0
MOVED_OVER_DISAGREE   = 2.0
stable_live(c) := c.common >= 2  AND  movedA >= 1  AND  movedB >= 1
                  AND agree_pct >= 99.0
                  AND min(movedA, movedB) >= 2.0 * disagreements
WITHHOLD buckets      = INERT-SINGLE, UNSTABLE, UNVERIFIABLE
NON-withheld buckets  = STABLE-LIVE, INERT-MULTI, SINGLE-RUN
NONGATED run filter   = /(prefreeze|smoke|pilot|quarantine|burned)/i  + PARTIAL.md runs
```

`analysis/audit.py` and `analysis/recount.py` are **copies of EXP-0164's and
EXP-0189's** with the deltas listed in §8; the threshold constants are asserted equal
to the originals at run time and the run aborts if they differ. No threshold, bucket
rule, or gate is changed by this experiment for any purpose, including to recover a
field.

## 6. Restoration policy — frozen

A currently-withdrawn field (label `untested`, note recording an EXP-0164/EXP-0189
withholding) is listed in `analysis/restore.json` **only if** it buckets `STABLE-LIVE`
under §5 with the corrected index. That is exactly the dispatch's bar: ≥99 % per-value
cross-run agreement, `moved >= 2.0 * disagree`, `moved > 0`.

A field that never moves (`INERT-MULTI`) is **not restored** by this experiment. Per
the dispatch it is promotable only if the carriers differ in the dimension the field
controls, which is a per-field semantic argument this experiment does not attempt; such
fields are listed separately under `not_restored_requires_dimension_argument`, and are
**not** counted in the headline.

`restore.json` rows are flat `<mnemonic>.<field>` per FIELD-SWEEP-PROTOCOL §5 and carry
`start`/`width` from `work/db.snapshot.json`, because the merger refuses a row whose
bits moved.

## 7. Controls — declared before running

| id | control | pass condition |
|---|---|---|
| **C1** | Reproduce the published headline with the **defective** indexer, published rule, no withholding | exactly **37 / 166** emittable and **554** emitter-grade fields; otherwise STOP |
| **C2** | Fixed point: strict withholding with the defective indexer over today's `validation.json` | reported; any residual withholding is itself a finding |
| **C3** | No record loss: every (exp, key, arm, run) cell of the defective index is present in the corrected index with `n_cases` ≥ its old value | must hold for 100 % of cells |
| **C4** | H1 calibration: `half_alu_ext8.dst` gains attributable records from EXP-0180's `__dst_nibble` | must hold |
| **C5** | The audit can still say NO: at least one withdrawn field remains withheld after correction | must hold |
| **C6** | EXP-0164's own C2: `iter.dst` buckets `STABLE-LIVE` | must hold |

## 8. Declared deltas from the inherited scripts

1. `analysis/collect_raw.py` — the `_`-prefix branch is replaced by a lookup in an
   explicit, committed name table (`analysis/pseudo_names.py`) produced by §4.
   Names classified `SCAFFOLDING`/`UNCLASSIFIED` behave exactly as before (routed to
   `pseudo`, `continue`). Names classified `FIELD-SWEEP` fall through to the unchanged
   attribution path. **No other line changes.** A `diff` against EXP-0189's copy is
   committed to `analysis/collect_raw.diff`.
2. `analysis/audit.py` — the field-selection loop additionally audits rows whose label
   is `untested` **and** whose note records an EXP-0164/EXP-0189 withholding, tagging
   each row `cohort: "emitter-grade" | "withdrawn"`. Bucket rules, thresholds and
   record construction are untouched. Diff committed to `analysis/audit.diff`.
3. `analysis/recount.py` — gains a scenario that restores the §6 set, and reads this
   experiment's snapshots. The emittable rule is unchanged.

## 9. Confounders

- **The 28 repaired `evidence` citations** already merged into `validation.json` will
  also re-bucket fields, independent of the filter fix. The two causes must be
  separated: every restored field is reported with **which** cause produced it, by
  running the audit in four configurations (defective/corrected × as-cited/as-committed
  evidence is not available — the repaired lists are already committed, so the split is
  instead made per field by recording whether its restoring records came from an
  underscore-named group).
- A `fault` recorded inside a DEF-0178-1 reader-thread cascade is an artefact the
  indexer cannot distinguish from an observation; a field restored on movement that is
  entirely fault-class movement is flagged.
- Underscore groups are `pseudo` today, so reclassifying one **removes** it from the
  baseline-signature channel and can change `noisy_harness_arms` bookkeeping. This is
  reported, not suppressed.
- Non-`.jsonl` raw is out of scope, exactly as in EXP-0164/0189; the indexer only reads
  `*.jsonl`.

## 10. Out of scope

No `git commit`. No edit to `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
`docs/`, `PROVENANCE.md`, or any committed file of EXP-0164 / EXP-0189. This experiment
produces a recommendation and the evidence for it; the orchestrator merges.

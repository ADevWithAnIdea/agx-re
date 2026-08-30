# EXP-0192 — PRE-REGISTRATION: does fault-vs-ok movement meet the emitter bar?

**Frozen at repo revision `8d01daa35a53a478f72fe800dc94d27492c11d77`, working tree clean
(`git status --porcelain` → 0 lines), BEFORE any per-field count was computed.**

**PURE OFFLINE ANALYSIS.** No device is contacted; the A18 Pro is down. Every input is
already-committed append-only evidence captured by earlier experiments.

---

## 1. The question, and why it needs a fresh experiment

`EXP-0190/analysis/collect_raw.py::sig_of` builds a per-case signature as

```python
hard = oc if oc in HARD else "run"      # HARD = {fault, hang, undecodable, killed, ...}
return hard + "|" + sha1(json(observed))[:10]
```

so an `ok` case and a `fault` case **always** carry different signatures. `audit.py`'s
`moved` counts, per `rest` group, the cases whose signature differs from the modal one.
Therefore **a case that merely FAULTED is counted as movement**, and a field whose values
only ever fault — never producing two distinguishable *valid* outputs — can be scored
`STABLE-LIVE` and reach emitter grade.

`EXP-0191` measured the consequence: **7 of 337 STABLE-LIVE arms have fewer than two
distinct valid observation payloads**, and **four currently emitter-grade rows rest
entirely on such an arm**. It found this *after* seeing its own data and therefore
deliberately refused to act on it, filing it under `post_hoc_candidates` in
`EXP-0191/analysis/reclassify.json` rather than in its verdicts. A rule invented to fit the
data is the same error as a check that cannot fail. **This experiment is the
pre-registered successor: the criterion is fixed here, before the counts are computed.**

## 2. What the normative text actually says

`docs/evidence-classification.md` §2 defines `hardware-run` with **two conjuncts**:

> The field was **given arbitrary values** … spliced into a real program, executed, **and the
> output matched prediction**. Faults and silent zeros count as observations.

and, in "The `hardware-run` bar, stated precisely":

> …you must have run values the compiler would not have chosen — boundaries, holes, and
> out-of-range — and recorded what happened, including the silent zeros.

Conjunct **(a)** — arbitrary values ran and what happened was recorded — is satisfied by a
fault sweep; the text says so explicitly ("faults … count as observations"). Conjunct
**(b)** — *the output matched prediction* — is not satisfied by a fault, because a fault
reports that the **encoding is illegal**, not what the field **does**. The `emittable` rule
in the same section is about what an emitter must be able to *choose*.

Both readings are defensible and are argued in §3. The criterion in §4 resolves them by
splitting on a property that is measurable from the committed raw and that neither reading
disputes: **how many values were LEGAL**.

## 3. The two arguments, stated before the split

**For withholding.** A fault is a hazard map, not a semantic. Two of this session's
strongest results — the `frag_color_pack.dst` `0xC0` wall and the `(v & 0x60) == 0x60`
rule — were deliberately recorded as **fault walls** precisely because that is a different
kind of fact from "this field selects X". If every legal value of a field yields an
indistinguishable output, an emitter that must *choose* among them is choosing blind.

**For keeping.** The transition point is real, reproducible information: it bounds the
legal set exactly, and an emitter that stays inside the legal set can emit the
instruction. `call.b5` is `hardware-run` on `(b5 & 0x06) == 0` with 128/128 faults on one
bit, and nobody has disputed that.

**Where they part company.** The keeping argument is strongest when the legal set is
*trivial or singular* — there is nothing to choose, so knowing the boundary is complete
emitter knowledge. It is weakest when **two or more values are legal and produce the same
observation**: that is an **inertness** observation, and audit.py's own rules
(`INERT-SINGLE` ∈ `WITHHOLD`) would have withheld it had `moved` not been inflated by the
faults. In that case the fault-as-movement defect does not merely mislabel the row — it
**converts a withhold-able verdict into a promotable one**.

## 4. The criterion — FROZEN, and it must be able to come out either way

### 4.1 Quantities, per (row `R`, arm `A`)

Computed from `EXP-0190/work/raw_index.json.gz` (the corrected indexer's own attribution;
**no third indexer is written**) and from a record-level pass using
`EXP-0191/analysis/detection_gate.py::payload_of` **imported unmodified** for validity:

- `n_cases(R,A)` — total attributed cases.
- `n_fault(R,A)` — cases whose signature carries a `HARD` class (`fault`, `hang`,
  `undecodable`, `killed`, `not_written`, `no_draw`, `lost_7_of_8`, `nondeterministic`).
- `V(R,A)` — **distinct VALID payloads**: distinct signatures whose hard class is `run`
  and whose observation hash is not `-` (missing `observed`). Cross-checked at record level
  with `payload_of`, which additionally rejects error payloads, `{}`/`[]`/`""`, and
  bookkeeping-only dicts (EXP-0191 §5, inherited verbatim).
- `V_all(R,A)` — distinct signatures **including** the fault classes. This is the quantity
  `moved` is effectively built from.
- `L(R,A)` — **legal-value count**: the number of distinct *field values* for which at
  least one non-HARD, non-CONTAM case was recorded.
- cross-run agreement — reused unchanged from `audit.py::cross_run` on the same arm.

### 4.2 The three cases

For an emitter-grade row `R` (live label `hardware-run` or `isolated-byte-diff`) whose
`STABLE-LIVE` promotion rests on arm set `S(R)`, evaluated over **every** arm in the corpus
that the indexer attributes to `R` — not only `S(R)` — because an independent arm rescues
the row:

- **Case A — `V(R,A) ≥ 2` for some arm `A`.** The row's movement includes two
  distinguishable **valid** outputs. → **STANDS.** No action.
- **Case B — `V(R,A) < 2` for every arm, and `L(R,A) ≤ 1` for every arm.** At most one
  value of the field is legal. There is nothing for an emitter to choose; the legality
  boundary *is* the complete emitter fact. → **STANDS**, flagged
  `legality-only` in the output, with a recommendation (not an edit) that the row's
  `semantics`/`note` be reworded as a legal-set bound rather than a value-selection
  semantic.
- **Case C — `V(R,A) < 2` for every arm, and `L(R,A) ≥ 2` for some arm.** Two or more
  values are legal and every one of them produced the same (or no) observation. This is an
  **inertness** observation that `moved` re-scored as movement. Absent the defect it would
  have been `INERT-SINGLE`/`INERT-MULTI`, and `INERT-SINGLE` is already in audit.py's
  `WITHHOLD` set. → **WITHHOLD**, written to `analysis/reclassify.json`.

**The reclassification trigger fires iff a row lands in Case C.**

### 4.3 What would make me say YES, the row stands

Stated explicitly so this is not a twelfth check that cannot come out the other way. **Any
one** of the following, found in the committed raw, leaves a row emitter-grade:

1. **Two distinct valid payloads on any attributing arm** (Case A) — including an arm
   outside `S(R)`, and including a second experiment's arm on either target.
2. **A legal set of size ≤ 1** (Case B) — the `call.b5` shape taken to its limit: the
   emitter has no choice left to make, so nothing is missing.
3. A distinct-valid-payload count of ≥ 2 recovered at the **record level** by
   `payload_of` even where the index signature collapses them (the index keeps one *modal*
   signature per `rest:fieldvalue` key; a genuinely bimodal cell could be flattened there).
   Record level wins where the two disagree, and the disagreement is reported.

All three directions are reachable from the committed corpus, and I do not know which of
the four rows takes which.

## 5. Pre-registered expected outcome, and the refuters

- **E1 (expectation).** I expect **at least one and at most four** rows to land in Case C —
  most likely `ret.linkmode` and `ret_luse.linkmode`, whose EXP-0191 arm-level tallies show
  667/768 and 658/672 fault cases respectively but also ~96 and ~0…14 non-fault ones. If
  ~96 non-fault cases of an 8-bit field span ≥ 2 distinct values, `L ≥ 2` and the row is
  Case C. **This is a prediction, not a finding**, and it is recorded here so it can be
  wrong.
- **R1 (refuter of the whole experiment).** If **all four** rows land in Case A or Case B,
  the criterion did not fire, and the correct published result is *"the criterion did not
  fire and all four rows stand"*. That outcome is written up with the same weight.
- **R2 (refuter of the criterion's discrimination).** If the criterion assigns **every**
  examined row to the same case, report whether that is a property of the data or of the
  rule: specifically, check the criterion against **`call.b5`** (`hardware-run`, one bit,
  128/128 faults, undisputed) and against at least one uncontested multi-payload
  `hardware-run` row. `call.b5` must **not** be withheld and a healthy row must **not** be
  withheld; if either is, the criterion is broken and this experiment reports *that*.
- **R3.** If a row's `S(R)` arms cannot be located in the pinned index at all, it is
  `UNVERIFIABLE-HERE`, not Case C. An absent record is not evidence of inertness.

## 6. Scope

- The **four rows** named in `EXP-0191/analysis/reclassify.json → post_hoc_candidates`:
  `jump_cond.offset`, `ret.linkmode`, `ret_luse.linkmode`, `n3_sample_read.tail`.
- The **7 arms** listed in `EXP-0191/analysis/gate_results.json →
  `stable_live_arms_with_fewer_than_2_distinct_valid_payloads`, reported in full for
  generality (some carry no emitter-grade row).
- **Controls (R2):** `call.b5`, plus every emitter-grade row the criterion is evaluated on
  as a cohort sanity check.

## 7. Inputs, pinned by hash

| artifact | sha256 |
|---|---|
| `tools/agx-isa/validation.json` | `e1208340f5d8b16e5201c964d1a27fb14ee8214a2be09cbc446d4dd0ebf6d075` |
| `tools/agx-isa/db.json` | `2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4` |
| `EXP-0190/work/raw_index.json.gz` | `b4f13a2f9694d9ffbd9998f2fa9685d2dc034994c7e706364cdc3071b72af756` |
| `EXP-0190/analysis/audit.json` | `caeeafc3760f2683281ad312832f68e9978d3e49747b192898cbb4622c76f86e` |
| `EXP-0191/analysis/detection_gate.py` | `21b9e6bc1b227cc440b8a6df35eeded8c4a071d7f004a93a4e6483f5f39837cf` |
| `EXP-0191/analysis/reclassify.json` | `0ff47d77ee20fb000c83ece3f5eeb5f1e06db79d0e4e6ed704982ddd867fcfe4` |
| corpus | `experiments/*/raw/**/*.jsonl`, append-only |

`EXP-0190/analysis/audit.json` is pinned to a `validation.json` snapshot that predates
later withholdings; as in EXP-0191, **the live `validation.json` supplies the cohort and
`audit.json` supplies the structure**, and any row whose live label is no longer
emitter-grade is reported as already-withheld rather than re-withheld.

## 8. Confounders acknowledged in advance

- **Index modal collapse.** `collect_raw.py` keeps one **modal** signature per
  `rest:fieldvalue` cell, so a cell that was genuinely bimodal contributes one signature.
  This can only *under*-count `V`, i.e. bias toward withholding. Mitigated by the
  record-level `payload_of` pass (§4.3 rule 3), and every disagreement between the two is
  listed by name.
- **`L` is observed legality, not true legality.** A value never dispatched is neither
  legal nor illegal here. `L` is a lower bound; a row cannot be withheld for a value that
  was never run.
- **Contamination outcomes** (`invalid_run`, `victim`, `skipped`) are excluded from both
  `V` and `L` by the indexer's own `live` filter and by `payload_of`. They inflate neither.
- **DEF-0178-1.** A `hang` may be a manufactured artefact of the shared runner's reader
  thread. Hangs therefore count toward `n_fault` (they are not valid observations) but are
  reported separately from genuine `fault`s, and no row is withheld on the strength of
  hang-only evidence without that being stated.
- **Targets are not merged.** Each arm carries the experiment it came from; `EXP-0156` is
  G17P and `EXP-0147` is M4/G16G, and no verdict is promoted across targets.
- This experiment **changes no label**. It writes a recommendation; the orchestrator owns
  `validation.json`, `db.json`, `docs/`, and `PROVENANCE.md`.

## 9. Deliverables

`README.md`, this file, `analysis/valid_payload_audit.py`,
`analysis/valid_payload_audit.json`, `RESULTS.md`, `manifest.json`, `PROGRESS.md`, and —
**only if §4.2 Case C fires** — `analysis/reclassify.json`, flat `<mnemonic>.<field>` with
`start`/`width`.

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json, EXP-0190/analysis+work, EXP-0191/analysis
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/valid_payload_audit.py
Evidence: analysis/valid_payload_audit.json
```

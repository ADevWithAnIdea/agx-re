# EXP-0193 — PRE-REGISTRATION

**Frozen 2026-08-30 at repo revision `7286bf04c500f726fbe3bf096a166e90b6a34e0f` (working tree
clean: `git status --porcelain` returned 0 lines). Nothing below was written after a count
was computed.**

---

## 0. THE ONE THING THAT MATTERS MOST: this experiment applies an UNCHANGED INHERITED CRITERION

**This experiment invents no criterion, tunes no threshold, and adds no case.** It takes the
rule that `EXP-0192-fault-as-movement` froze in its own `PRE_REGISTRATION.md` §4.2 — *before*
EXP-0192 looked at any count — and applies it, verbatim and by direct import of EXP-0192's
committed implementation, to the population EXP-0192 explicitly left unswept.

> EXP-0192 `RESULTS.md` §7, Limitations:
> *"Scope was the four emitter-grade rows named by EXP-0191 plus one control. **The full
> 337-arm `STABLE-LIVE` population was not re-scored under this criterion**; that sweep is
> the obvious successor and is mechanical from `analysis/valid_payload_audit.py`."*

That sentence is the entire mandate of EXP-0193. The scope changes; the rule does not.

**The inherited rule, restated verbatim for the record (EXP-0192 §4.2):**

| case | condition | verdict |
|---|---|---|
| **A** | some attributing arm shows **≥2 distinct VALID payloads** | **STANDS** |
| **B** | no arm shows ≥2 valid payloads **and** ≤1 value is observed legal | **STANDS**, `legality-only` — nothing for an emitter to choose |
| **C** | no arm shows ≥2 valid payloads **and** ≥2 values are observed legal | **WITHHOLD** — an *inertness* observation that `moved` re-scored as movement |

**Binding commitments about the criterion, made now:**

1. **No re-tuning.** `classify_row()`, `arm_stats()`, `index_pass()`, `record_pass()`,
   `payload_of()`, `HARD`, `CONTAM` and `EMIT_OK` are consumed **as imported** from the
   committed files. EXP-0193 writes **no** copy, fork, patch, or reimplementation of any of
   them. `experiments/EXP-0192-fault-as-movement/**` is read-only to this experiment and is
   not executed via its `main()` (which would rewrite EXP-0192's committed outputs).
2. **No new case.** If a row is genuinely ambiguous under A/B/C, EXP-0193 **reports the
   ambiguity and stops there.** It does not resolve it by extending the rule. EXP-0191 earned
   its credibility by refusing exactly this, and an eleventh-hour rule adjustment is the
   failure this experiment chain exists to prevent.
3. **No selective scope.** The population is defined mechanically (below) and every member is
   scored. Rows are not dropped for being inconvenient, and Case A rows are reported with the
   same detail as Case C rows.

## 1. Question

Applying the frozen EXP-0192 criterion to **every field carried by any arm that
`EXP-0190/analysis/audit.py` marked `stable_live`** — the full 337-arm `STABLE-LIVE`
population — does any **further** row fire Case C beyond the three EXP-0192 already withheld?

Why it matters: `collect_raw.py::sig_of` = `"<hardclass>|<sha1(observed)[:10]>"`, so an `ok`
case and a `fault` case **always** differ as signatures and `audit.py`'s `moved` counts a fault
as movement. Any `STABLE-LIVE` promotion in the corpus can in principle be carried entirely by
a fault wall. EXP-0191 measured the exposure (7 of 337 arms have <2 distinct valid payloads)
but refused to act on a post-hoc finding; EXP-0192 acted, on **4 rows**, and left the other
**3 arms and every field attributed to them** unexamined, along with the other 330 arms.

## 2. Population (the independent variable's domain) — mechanical, fixed now

`P` = every `<mnemonic>.<field>` key `k` of `EXP-0190/analysis/audit.json → fields` for which
some `fields[k].per_experiment[eid][armkey].stable_live` is true.

This is byte-for-byte the same enumeration `EXP-0191/analysis/detection_gate.py` performs to
build its `slcheck` dict (lines 417–431), including its `resolver()` mapping of an evidence id
(`EXP-0156`) to an experiment directory (`EXP-0156-g17p-emit-cf-mem`). EXP-0191 committed the
resulting arm count as `n_stable_live_arms_checked = 337` in `analysis/gate_results.json`.

Measured at freeze time (population sizing, not an outcome):

- **337** `STABLE-LIVE` arms — **matches EXP-0191's committed 337 exactly**;
- **503** distinct fields carried by those arms (of 708 keys in `audit.json`, of 1040 in
  `validation.json`);
- **23** experiment directories: EXP-0138, 0139, 0140, 0141, 0144, 0146, 0147, 0153, 0154,
  0155, 0156, 0157, 0160, 0161, 0163, 0168, 0169, 0171, 0172, 0174, 0178, 0179, 0180.

Scope for scoring = `P` ∪ `EXP-0192.CONTROLS`. `EXP-0192.ROWS` (the four already-examined rows)
are re-scored as part of `P` and serve as a re-derivation check (§5).

**Note on `index_pass` breadth.** Per the inherited implementation, a row's Case-A rescue may
come from **any** arm in the whole corpus index, not only from its `STABLE-LIVE` arms. That is
EXP-0192's behaviour (it is how `ret.linkmode` survived) and it is kept unchanged.

## 3. Hypotheses

- **H0 (null, and the outcome I expect to be most likely):** no row in `P` beyond the three
  already withheld fires Case C. The corpus is clean under a rule that has already withdrawn
  three rows.
- **H1:** one or more further rows fire Case C. Emitter-grade members of that set are
  recommended for withholding; non-emitter-grade members cost nothing and are reported only.
- **H2 (Case B):** one or more rows have `V < 2` and `L ≤ 1` — a trivial legal set with nothing
  for an emitter to choose. These **STAND** as `legality-only`. EXP-0192 found none in scope
  and recorded that "its absence is data, not design"; over 503 rows it may well be reachable.

H0 and H1 are both publishable. **H0 is the stronger statement about the corpus** and will be
reported as-is if it holds — it is not a null result to be talked around.

## 4. Method

1. Import `EXP-0192/analysis/valid_payload_audit.py` as a module (its `main()` is behind an
   `if __name__ == "__main__"` guard and is **not** called). This transitively imports
   `EXP-0191/analysis/detection_gate.py::payload_of`, `HARD`, `CONTAM` — also unmodified — and
   re-asserts EXP-0192's `HARD == INDEX_HARD` drift check.
2. Build `P` per §2 from `audit.json`.
3. **Index-level pass:** `V0192.index_pass(idx, row)` for every `row ∈ P ∪ CONTROLS`, over
   `EXP-0190/work/raw_index.json.gz`. This *splits* `sig_of`'s signature into
   `(hardclass, observation-hash)`; it does not recompute it.
4. **Record-level second pass:** `V0192.record_pass(want)` over the append-only
   `experiments/*/raw/**/*.jsonl`, with `want` built exactly as EXP-0192's `main()` builds it —
   `(expdir, armkey)` for every arm the index attributes to any scope row, plus every arm in
   EXP-0191's seven. This is the full unrestricted pass; it is affordable (a timed read of the
   largest single raw tree, EXP-0171 at 97 MB, took 0.37 s).
5. **Classify:** `V0192.classify_row(arms, rec, row)` for every scope row. No wrapper logic
   between the imported function and the recorded case.
6. Emit `analysis/population_audit.json` (all rows, all arms, all cases) and — only if Case C
   fires on an emitter-grade non-control row — `analysis/reclassify.json`.

**Withholding filter (inherited, unchanged).** `reclassify.json` carries exactly EXP-0192's
`withhold` set: `case == "C"` **and** the **live** `validation.json` label ∈
`("hardware-run", "isolated-byte-diff")` **and** the row is not a control. A Case-C row that is
already `untested`/`corpus-correlation` has nothing to withhold; it is reported in
`population_audit.json` and in `RESULTS.md`, and deliberately kept **out** of `reclassify.json`
so the file stays a clean actionable merge input.

## 5. Controls, and their expected results — RECORDED BEFORE RUNNING

### R1 — the positive control: `call.b5` MUST come out Case A

`call.b5` is `hardware-run`, one bit, dense over 256 values, and roughly **half its cases
fault**. It is the row that proves the criterion is not a blanket refusal of fault-bearing
evidence. EXP-0192 measured it on three arms. **Expected here, from EXP-0192's committed
`RESULTS.md` §1 table:**

| arm | cases | fault cells | `V` valid | `V_all` | `L` legal |
|---|---:|---:|---:|---:|---:|
| `EXP-0179-g17p-call\|C1_flat/idx15\|B5` | 768 | 384 | **3** | 4 | 128 |
| `EXP-0179-g17p-call\|C2_nested/idx7\|B5` | 768 | 416 | **4** | 5 | 128 |
| `EXP-0179-g17p-call\|S_kchain_compiled\|S` | 512 | 320 | **2** | 3 | 96 |

→ **case = A, verdict STANDS, `V` = 3, 4, 2 across the three arms.**

**STOP CONDITION.** If the run does not reproduce `call.b5` as Case A with `V` = 3, 4, 2 across
those three arms, **the pipeline is broken and NO verdict of any kind is reported** — not for
`call.b5`, not for any other row. The deliverable in that event is a broken-pipeline report
naming the discrepancy. This is absolute and is not negotiable against the deadline.

### R2 — the re-derivation control: EXP-0192's four rows must land where EXP-0192 put them

| row | expected case | expected verdict |
|---|---|---|
| `ret.linkmode` | **A** | STANDS (rescued by `EXP-0179`'s `L` arms, `V` = 2 and 3) |
| `ret_luse.linkmode` | **C** | (already withheld — live label is now `untested`, so it will NOT re-enter `reclassify.json`) |
| `jump_cond.offset` | **C** | (already withheld — live label now `untested`) |
| `n3_sample_read.tail` | **C** | (already withheld — live label now `untested`) |

Any disagreement here is also a pipeline failure and triggers the same STOP.

### R3 — discrimination

The criterion must be able to come out more than one way over `P`. Case A occurring is
guaranteed by R1; **Case C occurring is guaranteed by R2** (the three re-derived rows). So the
rule demonstrably both promotes and refuses within this very run, independent of whatever the
other 499 rows do. A run in which *every* row came out Case A would still be discriminating,
because R2's three rows are inside `P` and must come out C.

### R4 — attribution

Every row in `P` comes from `audit.json`, which is built from the pinned index, so every row
must be locatable in that index. A row scoring `UNVERIFIABLE-HERE` (no attributing arm) is
recorded as such and **is not** treated as a withholding.

## 6. Refuters — observations that would falsify H0 / the reported verdicts

- **Falsifies H0:** any row in `P` with `bestV < 2` and `L ≥ 2` that is not one of the three
  already-withheld rows.
- **Falsifies a Case-C verdict for a specific row:** any attributing arm anywhere in the corpus
  index — or in the record-level pass — showing ≥2 distinct valid payloads for it. The
  criterion takes `max` over both passes precisely so this refuter is live for every row.
- **Falsifies the run as a whole:** R1 or R2 failing (§5).
- **Falsifies "the population is 337":** an arm count from `audit.json` that differs from
  EXP-0191's committed `n_stable_live_arms_checked`. (Checked at freeze: it does not.)

## 7. Known confounders, stated in advance

- **`L` is *observed* legality, not true legality.** A value never dispatched is neither legal
  nor illegal here, so `L` is a lower bound. This can only make a row *harder* to withhold
  (`L ≤ 1` → Case B → STANDS), never easier. Direction is safe.
- **Index modal collapse.** `collect_raw.py` keeps one modal signature per `rest:fieldvalue`
  cell, so a genuinely bimodal cell contributes one signature — a bias *toward* withholding.
  The record-level pass (§4.4) is the pre-registered cross-check against exactly this, and
  `classify_row` takes the max of the two, so the record level can only rescue a row.
- **A single valid payload can mean the arm lacked detection power rather than that the field
  is inert** (FIELD-SWEEP-PROTOCOL §3(2), §5 / DEF-0190-1). The criterion does not claim to
  distinguish these. **Case C says the promotion is unsupported, not that the field is inert.**
  This limitation is inherited from EXP-0192 verbatim and will be restated in `RESULTS.md`.
- **DEF-0178-1** — hangs may be manufactured by the shared runner's reader-thread defect. Hard
  classes are reported per class per arm (`hard_class_counts`) so no row's withholding can be
  read as resting on hang-only evidence without that being visible.
- **A row can be in `P` via a `STABLE-LIVE` arm while its label came from somewhere else
  entirely.** Case C is a statement about the `STABLE-LIVE` evidence, and the withholding
  filter's live-label conjunct is what keeps that from over-reaching.
- **Widths and multi-value semantics.** `L` counts distinct *field values* observed legal, not
  distinct *bit patterns of the instruction*; a match-pinned "field" whose real encodable range
  is smaller than its modelled width (e.g. DEF-0172-1) will show a small `L`. That is a
  property of the descriptor, not of this rule.

## 8. Frozen inputs and hashes (SHA-256, at freeze)

```
01c7c7c98fb347b76e02e811a5c8d35154c79191ea393d0247c6c3d0fca0d7d8  tools/agx-isa/validation.json
2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4  tools/agx-isa/db.json
b4f13a2f9694d9ffbd9998f2fa9685d2dc034994c7e706364cdc3071b72af756  experiments/EXP-0190-indexer-refilter/work/raw_index.json.gz
caeeafc3760f2683281ad312832f68e9978d3e49747b192898cbb4622c76f86e  experiments/EXP-0190-indexer-refilter/analysis/audit.json
21b9e6bc1b227cc440b8a6df35eeded8c4a071d7f004a93a4e6483f5f39837cf  experiments/EXP-0191-detection-gate/analysis/detection_gate.py
fe290de7ec58a6835dfc2c8f0eb79543dcef899eb912bb7b3bc9e3c9de26f5ba  experiments/EXP-0191-detection-gate/analysis/gate_results.json
204d78feb852934bd4f01013a2cee79a12dde01ea6a558c689427a68202fe027  experiments/EXP-0192-fault-as-movement/analysis/valid_payload_audit.py
9dc1ef7ff42da88f9bdcef4bfbcc9a0093261fce9db8df11479d61215ba4f06a  experiments/EXP-0192-fault-as-movement/analysis/valid_payload_audit.json
e1b06f56bd344de6111c76e97e2636c613b9274f844ea5bbadfcddc75a17959b  experiments/EXP-0192-fault-as-movement/analysis/reclassify.json
```

The script re-hashes these at run time and writes them into `population_audit.json._meta`. A
mismatch against the list above is recorded in `RESULTS.md`, not silently accepted.

Baseline label counts at freeze, from `python3 tools/agx-isa/validate_labels.py` (rc=0):
**483 `hardware-run` + 63 `isolated-byte-diff` = 546 / 1040 emitter-grade fields; 33 / 166
emittable instructions** (172 descriptors − 6 data words).

## 9. Output schema (frozen)

`analysis/population_audit.json`
```
_meta      : experiment, question, criterion provenance, input hashes, HARD/CONTAM sets,
             population sizes, controls, device_contacted:false
population : {n_stable_live_arms, n_fields, n_experiments, arms:{arm -> [fields]}}
summary    : counts per case; case_C_all; case_C_emitter_grade; case_B; unverifiable;
             control checks R1/R2; criterion_fired; projected label counts
verdicts   : per row -> {live_label, live_range, snapshot_label, bucket, moved_total,
             target, evidence, stable_live_arms, n_attributing_arms,
             arms: {arm -> {n_cases, n_keyed_cells, n_fault_cells, hard_class_counts,
                            V_valid_payloads, V_all_signatures, L_legal_values,
                            n_fault_only_values, per_run}},
             record_level, cross_run, case, verdict, reason, geometry, is_control}
```
The per-arm block is `arm_stats()`'s own return value, unmodified, so
"arms / cases / fault cells / distinct valid payloads / distinct legal values / case" are all
present per the deliverable spec.

`analysis/reclassify.json` — flat `<mnemonic>.<field>` with `start`/`width`, written **only**
if the withholding filter is non-empty; same key set as EXP-0192's.

## 10. Scope discipline and prohibitions

- **PURE ANALYSIS.** No device, no SSH, no GPU, no shader compiled. The A18 Pro is DOWN and is
  not contacted. `device_contacted: false` is asserted in `_meta`.
- **No `git commit`.** The orchestrator reviews and commits.
- **No edits** to `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/`,
  `PROVENANCE.md`, or any other experiment's committed files. `reclassify.json` is a
  **recommendation**; EXP-0193 changes no label.
- All EXP-0193 files stay under `experiments/EXP-0193-stable-live-sweep/`. Scratch goes in
  `work/`, never outside the repo.
- Progress is appended to `PROGRESS.md` per milestone and partial `RESULTS.md` sections are
  written as soon as their data exists, so a kill costs at most one milestone.

## 11. Clean-room statement

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json,
                  EXP-0190/analysis+work, EXP-0191/analysis, EXP-0192/analysis
Apple binary introspection: NONE. No shader compiled, no device contacted, no SSH.
Reproduction: python3 analysis/population_audit.py
Evidence: analysis/population_audit.json (+ analysis/reclassify.json if Case C fires)
```

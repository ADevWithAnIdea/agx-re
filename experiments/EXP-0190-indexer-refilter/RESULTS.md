# EXP-0190 — RESULTS: the `_`-prefix discard, corrected

**PURE OFFLINE ANALYSIS. No device was contacted; the A18 Pro was down for the whole
run.** Inputs, thresholds, classification rule and controls were frozen in
`PRE_REGISTRATION.md` at repo revision `b98b237b` **before** any verdict was computed.

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: tools/agx-isa/{db,validation}.json (snapshotted to work/),
                  experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  experiments/*/{harness,analysis}/*.py (our own code)
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/census_underscore.py
           && python3 analysis/classify_underscore.py
           && python3 analysis/collect_raw.py --legacy-underscore
           && python3 analysis/collect_raw.py
           && python3 analysis/verify_inheritance.py
           && python3 analysis/audit.py --index raw_index_legacy.json.gz --suffix _legacy
           && python3 analysis/audit.py
           && python3 analysis/recount.py --audit audit_legacy.json \
                      --index raw_index_legacy.json.gz --suffix _legacy
           && python3 analysis/recount.py
           && python3 analysis/restore.py
           && python3 analysis/blind_arm_scan.py
Evidence: work/{raw_index,raw_index_legacy}.json.gz, work/underscore_census.json,
          analysis/{underscore_fields,restore,audit,audit_legacy,emittability,
          emittability_legacy,blind_arms,controls}.json
```

---

## THE HONEST NUMBER

| | emittable of 166 | emitter-grade fields of 1040 |
|---|---|---|
| **published today** | **37** | **554** |
| re-derived with the **defective** indexer, strict | **35** | 552 |
| **re-derived with the corrected indexer, strict** | **37** | **554** |
| after the one defensible restoration (§5) | **37** | **555** |

**The filter was wrong. It changed the headline by zero, and it was protecting two
instructions rather than hiding any.**

The correction moves exactly **two** fields, `half_alu.dst` and `half_alu_ext8.dst`,
from `UNVERIFIABLE` to `STABLE-LIVE`. Both were already published as emitter-grade, so
nothing is *added* — but under the defective indexer a strict re-derivation of today's
number withdraws them and takes `half_alu` and `half_alu_ext8` with them. With the
filter corrected, **today's 37/166 is a fixed point**: strict withholding removes
nothing.

**Nothing comes back from the filter fix.** Of the 154 rows this repo has withdrawn to
`untested` on an EXP-0164/EXP-0189 re-derivation, the corrected and the defective
indexes bucket **all 154 identically**. One field comes back by the *other* route the
dispatch named — the already-committed evidence-citation repairs — and is reported in
§5.

---

## 1. Every `_`-prefixed field name in the corpus

`analysis/census_underscore.py` → **96 distinct names, 28,736 records**, across
`experiments/*/raw/**/*.jsonl`. Each was classified by hand from the harness line that
emits it and from the records themselves; the table is in
`analysis/classify_underscore.py` and the joined result, with per-name record counts,
experiments, outcomes, and the db fields the varying bits land in, is
`analysis/underscore_fields.json`. **There is no default bucket** — the script asserts
its key set equals the corpus's, so a name in a future capture fails loudly.

```
FIELD-SWEEP     14      CONTROL-SHAPED   1      SCAFFOLDING    81
```

**Only 18 of the 96 have any group that varies its `bytes` at all.** For the other 78
the classification cannot change any number in either direction; that is stated per
name in `effect_of_classification`.

### The 14 genuine field sweeps that were being discarded

| name | experiment | records | what it actually is | db fields the bits hit |
|---|---|---:|---|---|
| `__dst_nibble` | EXP-0180 | 128 | 16-value sweep of byte0's high nibble, H0/DEF-0180-1 | `half_alu_ext8.dst` |
| `__len_b2` | EXP-0180 | 4608 | 256-value sweep of byte+2 at six byte+4 settings | `half_alu_ext8.{opsel,opflags,b4}` |
| `__len_b4` | EXP-0180 | 1536 | 256-value sweep of byte+4 at two byte+2 settings | `half_alu_ext8.{opsel,b4}` |
| `__raw_b0` | EXP-0161 | 4399 | raw whole-byte sweep at byte 0, `byte_index` recorded | `mov_zext16.src_reg`, `carry_gen.dst`, `fspecial_est.dst`, `fspecial.fn_hi` |
| `__raw_b2` | EXP-0161 | 1024 | same generator at byte 2 | (match bits only) |
| `__lut2d` | EXP-0154 | 1024 | 2-D `ilogic` op_base × lut_a_sel × lut_b sweep | `ilogic.{op_base,lut_a_sel,lut_a_free,lut_b}` |
| `__2d_desc_lo` | EXP-0160 | 528 | 12 `srcC_desc` × 11 `srcC_lo` points | `imad.{srcB,srcC_desc}` |
| `__2d_desc_mul` | EXP-0160 | 384 | 12 `srcC_desc` × 8 `mulsel` points | `imad.{srcC_desc,mulsel}` |
| `_byte0_hi` | EXP-0138 | 48 | 16-value sweep of `half_alu` byte0 high nibble, with a host oracle | **`half_alu.dst`** |
| `_match_b1`, `_match_b2` | EXP-0138 | 768+768 | 256-value sweeps of `copysign` byte+1 / byte+2 | (match bits only) |
| `_b1_match`, `_b2_match` | EXP-0184, EXP-0187 | 1040+672 | 256-value sweeps of the same bytes on G17P | (match bits only) |
| `_b3_match` | EXP-0187 | 160 | 16-value sweep of `n4_rt_word` byte+3 | (match bits only) |

Every one of these names exists because **`db.json` models those bits as a fixed match
constant, so the harness had no field name to use** — and then the indexer discarded the
record for having no field name. That is the whole defect, stated as a sentence.

Six of the fourteen credit no db field (the bits really are match constants), so
admitting them changes nothing. Two of them change a verdict. The rest were already
attributable by other groups.

### The one CONTROL-SHAPED name — reported, not counted

**`_detect`** (EXP-0163, EXP-0172; 3,536 records; 265 of 271 groups vary their bytes and
land in real db fields) is the only name where structure and intent disagree. It writes
two values into every db field of the anchor's descriptor — the complement of the current
value, and 0 — and records whether the observation changed. Structurally that is a
per-field hardware sweep with bytes and observations. But both experiments consume it
**only** as `arms_with_proven_detection_power`, i.e. as the instrument check that
licences their inert verdicts, and two values chosen to maximise the chance of a change
is not the dense sweep FIELD-SWEEP-PROTOCOL §3 requires. Per the frozen rule it stays
discarded, and it is named here rather than dropped silently. §7 argues it should be
consumed — as a **gate**, not as a measurement.

### The two names that prove the classification cannot be structural

`_ANCHOR_VERDICT` (EXP-0157, 541 records) records a **boolean verdict** — "LIVE iff L1 or
L2 moved the output off baseline" — as its `value`. It never writes anything into the
encoding. Yet 50 of its 94 groups "vary their bytes", because one group spans several
anchors, and the varying bits land squarely in `n2_op6.{dst,opA,opB,opsel,imm_sel,
src_desc}`. A purely structural rule would have promoted a bookkeeping record into six
field observations. `_L1_opcode_group` (45 of 83 groups, same six fields) is the same
shape: one fixed mutation per anchor, used only to decide whether the anchor is live.
Both are classified `SCAFFOLDING` on intent.

## 2. The corrected indexer

`analysis/collect_raw.py` is EXP-0189's file with **one test changed**
(`analysis/collect_raw.diff`, 91 lines including the new docstring and the
`--legacy-underscore` plumbing):

```python
-                    if fld.startswith("_"):
+                    if fld.startswith("_") and (LEGACY or fld not in FIELD_SWEEP):
```

`FIELD_SWEEP` is the committed table of §1. `--legacy-underscore` restores the old
behaviour verbatim, and **the legacy run reproduces EXP-0189's counts to the digit —
6,592 groups → 5,910 attributed cells, 0 unparseable lines.** The corrected run:
6,674 groups → 5,937 cells.

`analysis/verify_inheritance.py` compares the AST of every verdict-producing function
and every frozen constant against the committed originals — `cross_run`, `stable_live`,
`classify`, `build_record`, `moved_of`, `resolver`, `sig_of`, `fit_offset`, `identify`,
`resolve_label`, `emittable_current`, `instr_dispatch_audit`, plus `MIN_COMMON`,
`MIN_AGREE_PCT`, `MOVED_OVER_DISAGREE`, `THIN_COMMON`, `WITHHOLD`, `EMIT_OK`, `HARD`,
`CONTAM`, `NONGATED`, `NOTES` — and **PASSES**. No threshold, bucket rule or gate was
touched, for any purpose.

## 3. Controls

| id | control | result |
|---|---|---|
| **C1** | reproduce the published headline before withholding anything | **PASS — 37/166 exactly**, on both indexes |
| **C2** | fixed point under strict withholding | legacy **35**, corrected **37** — the residual withholding is entirely the filter defect |
| **C3** | no record loss: every legacy cell present in the corrected index with `n_cases` ≥ | **PASS — 0 lost**, 23 grew, 27 new |
| **C4** | H1 calibration: `half_alu_ext8.dst` recovers EXP-0180's `__dst_nibble` | **PASS** — `UNVERIFIABLE` → `STABLE-LIVE`, 16 values × 2 carriers × 2 gated runs, 100.00 % agreement |
| **C5** | the audit can still say NO | **PASS — 151 of 154 withdrawn rows stay withheld** |
| **C6** | EXP-0164's own C2, `iter.dst` = `STABLE-LIVE` | **PASS** (and C1-of-EXP-0164, all 15 EXP-0155 orchestrator withholds reproduced, also passes) |

Extra, unplanned: **the unresolved-group count is identical under both indexes**
(8,877 in 152 kinds), so admitting the 14 names produced no second-order loss in the
label-level fallback path — worth checking, because `resolve_label`'s `BYTELABEL` regex
cannot parse any of the newly-admitted names, and a group that reached the fallback
would have been discarded a second time. None did.

## 4. What the correction actually moves

Emitter-grade cohort (the 554), legacy → corrected:

```
STABLE-LIVE  499 -> 501      UNVERIFIABLE  14 -> 12      INERT-MULTI 27      SINGLE-RUN 14
```

Exactly two bucket changes, both `UNVERIFIABLE` → `STABLE-LIVE`:

| field | evidence that was being discarded | cross-run |
|---|---|---|
| **`half_alu_ext8.dst`** | EXP-0180 `__dst_nibble`, arms `C_HI\|DSTNIB` and `C_LO\|DSTNIB` | 16 values, 2 gated runs, moved 15/15 and 13/13, **100.00 %** agreement, 0 disagreements |
| **`half_alu.dst`** | EXP-0138 `_byte0_hi`, arm `half_alu` | 16 values, 3 gated runs, moved 2/2, **100.00 %** agreement, 0 disagreements |

`half_alu_ext8.dst` is the instance EXP-0189 found by hand and repaired with
`rescue.py`. **`half_alu.dst` is new — EXP-0189's R1 named only `half_alu_ext8`**, and
`half_alu.dst`'s own history shows why it was missed: EXP-0164 scored it `STABLE-LIVE`
citing `EXP-0138`; by EXP-0189 its evidence list had been rewritten to
`["EXP-0180","EXP-0183"]`, whose only `dst` sweep is the discarded `__dst_nibble`, and it
fell to `UNVERIFIABLE`. Today's committed row cites `EXP-0138-m4-emit-falu` again, and
the corrected indexer re-derives it mechanically. The correction is therefore worth
**+2 instructions of withdrawal risk removed**, not +2 instructions of headline.

## 5. What legitimately comes back — `analysis/restore.json`

Of the **154** withdrawn rows audited:

| | |
|---|---|
| **restored** | **1** — `falu2i.imm_flag` |
| blocked by a prior ruling this gate cannot see | 1 — `get_sr.form` |
| never moved; needs a carrier-dimension argument | 1 — `call.tail` |
| remain withheld (UNVERIFIABLE 65, INERT-SINGLE 51, UNSTABLE 35) | 151 |

**`falu2i.imm_flag` — restore.** `[8:1]`, target G17P, evidence `EXP-0169`, arm
`C1_alu|FALU2I`, two gated runs `g17p_20260830_run01/02`: **512 common per-value keys,
100.00 % agreement, 0 disagreements, moved 7 in each run**, bit-exact attribution, every
signature in the `run` (non-fault) class — so the movement is observation movement, not a
DEF-0178-1 fault artefact. It clears the gate the dispatch names with room to spare.

Two things must be said with it. First, **this is not the filter fix** — it buckets
`STABLE-LIVE` under the *defective* index too. It comes back through the
evidence-citation repairs already committed to `validation.json`: EXP-0164 withdrew it as
`INERT-SINGLE` when the row cited `EXP-0138` alone, where the group is two cases that
never move; the row now cites `EXP-0169`, whose re-record sweeps `imm_flag` against a
second varying position and finds it live at 14 of ~48 settings. Second, **the row's own
`note` is now false**: it still reads *"inert on the ONE carrier that had detection
power"*, and the raw it cites refutes that. Restoring the label without rewriting that
sentence would leave a text-contradicts-evidence row of exactly the kind EXP-0189 swept
for.

Restoring it yields **555/1040** and leaves the instruction count at **37** —
`falu2i.srcA_reg_top` is still `INERT-SINGLE` on one carrier, so `falu2i` does not become
emittable.

**`get_sr.form` — NOT restored, and this is the deliberate one.** It buckets
`STABLE-LIVE` here (2 values, three stage carriers, two gated runs, 100.00 % agreement).
But EXP-0189 §8a did not withdraw it for lack of movement — it withdrew it because all 12
records carry `oracle: null`, `match: false`, `outcome: "wrong_value"` *including cases
whose bytes equal the arm's own unmutated anchor*, because EXP-0178 filed no verdict for
it at all, and because EXP-0172 spanned the datapath-width dimension in both directions
and concluded *not* emitter-grade. This experiment's gate measures baseline-hash
**movement**, which EXP-0181 classifies as *"the BYTES are live — nothing about
semantics"*. Movement was never the objection. Passing a gate that does not ask the
question is not an answer to it, so it stays withheld with the reasoning recorded in
`restore.json → blocked_by_prior_ruling`.

**`call.tail` — NOT restored.** `INERT-MULTI`, moved 0 on all three arms. Per the
dispatch a never-moving field is promotable only if the carriers differ in the dimension
the field controls; that is a per-field semantic argument this experiment does not make,
and EXP-0189 showed the gate that originally promoted it could not fail. Listed in
`not_restored_requires_dimension_argument`, not counted.

## 6. Where the remaining 151 live

```
UNVERIFIABLE 65      INERT-SINGLE 51      UNSTABLE 35
```

Unchanged by the filter, row for row, under both indexes. The corrected indexer says
nothing new about any of them: their gaps are the ones EXP-0189 already characterised —
`EXP-M4-14-a18-splice` having no `raw/` directory, single-carrier inertness, and cross-run
instability that may itself be a DEF-0178-1 artefact.

## 7. The tenth check that cannot come out the other way — DEF-0190-1

**`audit.py`'s inert buckets have no detection-power conjunct, and 128 arms in the corpus
could not have returned anything but "inert".**

`moved` is derived from the hash of each record's `observed`. An arm whose observable
never varies — for any field, at any value — returns `moved = 0` **by construction**, and
`classify()` reads that as *"the field is inert"* rather than *"the instrument could not
answer"*. `INERT-MULTI` is a **non-withheld** bucket, so such a field keeps its
emitter-grade label without any hardware demonstration that it can be seen at all.

Measured (`analysis/blind_arm_scan.py` → `analysis/blind_arms.json`):

- **8** (experiment, arm) groups of field records where `observed` is **empty on every
  record** (1,103 records);
- **128** groups with ≥ 8 records and **exactly one distinct `observed` payload** across
  every case (80,138 records);
- **21** `INERT-*` fields all of whose tested arms are in that set — **5 of them
  currently emitter-grade**, and all three of their instructions are in the published 37:

| field | bucket | arms |
|---|---|---|
| `atomic_mem.amode` | INERT-MULTI | EXP-0141 `atdevimm`, `atdev` |
| `atomic_mem.base_slot` | INERT-MULTI | EXP-0141 `atdevimm`, `atdev` |
| `atomic_mem.rsv3` | INERT-MULTI | EXP-0141 `atdevimm`, `atdev` |
| `pop_reconverge.reserved` | INERT-MULTI | EXP-0156 `cfN` ×2 |
| `stop.reserved` | INERT-MULTI | EXP-0168 `STOP/midprogram`, `STOP/terminal` |

This is the same shape as the eighth instance (EXP-0179's promotion gate with no
`moved >= 1` conjunct), inverted: there a *promotion* gate could not fail, here an
*inertness* gate cannot fail. It is the shape FIELD-SWEEP-PROTOCOL §3(a) already names
one level down — *"the oracle could not express the field"* — applied to a whole arm.

**One distinct observation is not proof of no detection power.** The hardware may
genuinely be inert for everything those arms tried. That is precisely the ambiguity:
nothing inside an arm's own field records distinguishes the two, and the audit asks no
other question. What makes it a defect rather than a limitation is that **the corpus
already contains the positive controls that would settle it** — `_detect` (3,536
records), `__ladder_L_*` (an explicit pre-registered liveness ladder), `_live_control`
(305) — and the audit chain **discards every one of them through the same `_` filter this
experiment was dispatched to repair.**

**Recommendation:** consume the `CONTROL-SHAPED` and ladder names as a *gate* rather than
as measurements — require, for any `INERT-*` verdict, that the arm produced at least one
recorded change on some control — and re-derive the 21. That is a strictly better use of
`_detect` than admitting it as a field sweep, and it needs no hardware.

## 8. Checked, and clean — reported because a clean negative is a result

- **DEF-0190-2 (latent, no consequence today).** `audit.py`'s `gather()` silently
  disables its own gated-run filter: `if not gruns: gruns, fb = dict(runs), True`. A
  field whose *only* records are in a `prefreeze`/`smoke`/`pilot`/`quarantine`/`burned`
  run is scored anyway, flagged `gating_fallback`, and **nothing downstream consumes that
  flag**. The gate is bypassed exactly in the case where it would bite. Blast radius
  today: **2 rows, neither `STABLE-LIVE`, neither emitter-grade** — so it changes no
  number, but it is one quarantined capture away from doing so. Fix: treat
  `gating_fallback` as `UNVERIFIABLE`, or at least withhold on it.
- **EXP-0164's C1 control is not circular**, which I checked because it looked like it
  might be. The 15 EXP-0155 orchestrator withholds bucket `INERT-SINGLE` (10) and
  `UNSTABLE` (5) — not `UNVERIFIABLE` — with 13 of 15 having a tested arm. The control
  genuinely could have failed.
- **No second-order discard.** Unresolved groups are identical under both indexes
  (8,877 in 152 kinds), so no newly-admitted group fell through to the label-level path,
  whose `BYTELABEL` regex could not parse any of these names.
- **`_detect`'s exclusion does not hide a promotion.** It is reported as a declared
  sensitivity rather than folded in; the fields it would touch are `simd_shuffle.*`,
  `falu2i.*`, `iter_at.*` — the same descriptors already covered by dense non-underscore
  sweeps.

## 9. Limitations

- **Every number here is a re-derivation from records other experiments captured**, on
  the targets they name (M4/G16G for EXP-0138/0141/0146/0147, G17P for EXP-0154 and
  above). Nothing was measured on hardware; the A18 Pro was down.
- **`UNVERIFIABLE` remains an auditability verdict, not a refutation.** 65 rows still
  cannot be re-derived from committed raw; that is not a claim the hardware disagrees.
- **The classification of `_detect` is a judgement, and it is the one place where a
  different reading would change a number.** It is stated as such, with the record counts
  needed to overturn it, in `analysis/underscore_fields.json`.
- **`half_alu.dst`'s recovery depends on `EXP-0138-m4-emit-falu` being in its evidence
  list**, which it is today and was not at EXP-0189. A future evidence-list rewrite that
  drops it re-breaks the chain — the failure mode is the citation list, not the indexer.
- A `fault` recorded inside a DEF-0178-1 reader-thread cascade is still an artefact the
  indexer cannot tell from an observation. The one field restored here moves entirely
  within the non-fault signature class, so it is not exposed to that; the 35 `UNSTABLE`
  rows still are.

## 10. Verdict

**Publish 37/166 and 554/1040 — unchanged — and 555/1040 if `falu2i.imm_flag` is
restored with its note rewritten.**

The indexer defect was real, it was over-counting `UNVERIFIABLE` exactly as EXP-0189
suspected, and it had **two** instances rather than one. Neither was hiding a field: both
were already published, and the correction's value is that a strict re-derivation of
today's number now returns 37 instead of 35. *The filter was wrong and it changed
nothing* is the honest headline, and it is worth publishing precisely because the
opposite was plausible before it was measured.

The more valuable output is §7. A tenth check that cannot come out the other way is
worth more than a recovered field, and this one currently underwrites five emitter-grade
fields across three of the published 37 instructions — with its own remedy already sitting
in the corpus, discarded by the same filter.

# EXP-0189 — RESULTS: the closing audit of 55/166 and 638/1040

**PURE OFFLINE ANALYSIS. No device was contacted; the A18 Pro was down for the whole
run.** Pinned inputs and thresholds are in `PRE_REGISTRATION.md`, frozen at repo
revision `0de24f4f` **before** any verdict was computed.

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: tools/agx-isa/{db,validation}.json (snapshotted to work/),
                  experiments/*/raw/** (our own append-only capture records),
                  experiments/*/analysis/*.py and harness/*.py (our own code)
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/collect_raw.py && python3 analysis/audit.py \
           && python3 analysis/recount.py && python3 analysis/rescue.py \
           && python3 analysis/finalize.py
Evidence: work/raw_index.json.gz, analysis/{audit,reclassify,emittability,rescue,
          controls}.json
```

---

## THE HONEST NUMBER

| | emitter-relevant instructions emittable | emitter-grade fields |
|---|---|---|
| **published today** | **55 / 166** | **638 / 1040** |
| **re-derived, generous reading** (§3) | **38 / 166** | **556 / 1040** |
| **re-derived, as the evidence lists literally stand** (§3) | **33 / 166** | **527 / 1040** |

**55 does not survive.** The defensible number is **38 of 166** — 17 fewer — and it
is 38 only if you accept 29 fields whose evidence lists point at the wrong
experiment and are repaired rather than withdrawn (§4). Read strictly from
`validation.json` as committed, an auditor reproduces **33**.

**638/1040 does not survive either.** 82 of the 638 fail re-derivation under the
same frozen rule that produced the 41/166 withdrawal this morning; 111 fail it as
cited.

**But the merges are not worse than what preceded them.** The post-`459bb8bd`
cohort withholds at **18.31 %** (39 of 213 fields) against **16.94 %** (72 of 425)
for the pre-existing corpus. H2's refuter does not fire: this session's merges are
of *the same grade* as the corpus they joined. The shortfall is an inherited debt
that the new work did not clear, not new damage the new work caused.

### Two different questions, two different numbers — read both

This report contains two audits and they do not disagree.

- **The field re-derivation (§2–§6)** asks *"can every emitter-grade field be
  re-derived from committed raw under EXP-0164's frozen rule?"* Answer: **no, 82 of
  638 cannot**, so **55 → 38**.
- **The hand-ruling audit (§8a)** asks *"of the four rulings the orchestrator made
  personally, which the evidence does not support?"* Answer: **one**, `get_sr.form`,
  so **55 → 54** on that axis alone.

`get_sr` appears in both lists, by two independent routes. The 17-instruction
shortfall is dominated by inherited chain gaps, not by this session's rulings — which
is the fairest thing that can be said about the merges, and it is said on the numbers.

---

## 1. What was run

`analysis/{collect_raw.py,audit.py}` are **verbatim copies** of EXP-0164's (only
`_meta` strings differ — full diff in §9). The indexer produced 6,592 groups →
5,910 attributed cells over the whole `experiments/*/raw/**` tree with **0
unparseable lines**.

Controls, all declared in `PRE_REGISTRATION.md` §6 before running:

| control | result |
|---|---|
| **C1** reproduce EXP-0155's 15 orchestrator withholds | **PASS** — all 15 withheld |
| **C2** `iter.dst` must be `STABLE-LIVE` | **PASS** |
| **C3** ≥1 `STABLE-LIVE` field whose movement is a fault/hang class change | **PASS** — 134 fields |
| **C4** exactly 638 emitter-grade fields audited, every cited experiment accounted | **PASS** |
| **C5** the audit can still say NO | **PASS** — 111 withheld as cited |
| **C6** the gate can promote a width-1 field | **PASS** — 48 width-1 fields reach `STABLE-LIVE` |

## 2. Bucket census of the 638

```
STABLE-LIVE   486      INERT-MULTI    27      SINGLE-RUN     14
UNSTABLE       15      INERT-SINGLE    2      UNVERIFIABLE   94
                       (no-field-records 56 | no-raw 29 | named-but-unstructured 9)
```

`INERT-MULTI` and `SINGLE-RUN` are **not** withheld — the same choice EXP-0164 made,
so this audit cannot be accused of raising the bar after the fact.

**UNVERIFIABLE fell from EXP-0164's 144 to 94, and to 57 after the repairs in §4.**
That is real progress and it should be said plainly.

## 3. Recomputing the headline

`analysis/recount.py` reimplements `tools/agx-isa/validate_labels.py`'s rule as it
now stands — including the DEF-0173-1 `_instruction` gate — and **reproduces the
published 55 exactly** before any withholding. The scenarios:

| scenario | emittable of 166 |
|---|---|
| published rule, no withholding | **55** |
| strict withholding, evidence lists as cited | **33** |
| lenient (give unstructured splice evidence the benefit of the doubt) | 37 |
| **strict, after the citation/underscore repairs of §4** | **38** |
| `_instruction` gate alone, nothing else withheld | 51 |

## 4. Two mechanical causes of a FALSE `UNVERIFIABLE` — found, and repaired not withdrawn

Both were found by hand and then tested at scale (`analysis/rescue.py`). Neither
changes a threshold; both re-run the frozen rule over a corrected input.

**R1 — the indexer discards any raw record whose `field` name starts with `_`.**
That rule exists to skip `__baseline` / `__ladder_*` / `__falsifier_*`. But EXP-0180
records the **only** sweep of `half_alu_ext8.dst` — byte0's high nibble, 16 values ×
2 carriers × 2 gated runs — under `field: "__dst_nibble"`. So the field read
`UNVERIFIABLE` because of a *name*. This is a defect in **EXP-0164's own tooling**,
which I inherited, and it means EXP-0164's 144 was itself somewhat overstated.

**R2 — `audit.py` only looks in the experiments a field's `evidence` list cites.**
`call.offset` cites `EXP-0035` alone, while `EXP-0179` holds fully attributable
per-value records for that exact key (8 arms, 48 distinct offsets, 46 moved,
`STABLE-LIVE`). The evidence list was never updated when EXP-0179 landed.

Widening the evidence set for the 94 unverifiable rows and re-running the **frozen**
rule: 40 rows gained records, **29 cleared the rule** (25 `STABLE-LIVE`, 4
`INERT-MULTI`), 7 became `UNSTABLE`, 1 `INERT-SINGLE`, 3 stayed `UNVERIFIABLE`.
**57 remain genuinely unverifiable.**

> These 29 are a **citation repair**, not a promotion. They are listed in
> `analysis/reclassify.json` → `citation_repairs_not_withdrawals` with the exact
> directories whose raw actually carries them. Fixing the `evidence` lists is
> cheap, is required by CODEX §9, and buys back 5 instructions.

## 5. Where the remaining 57 unverifiable rows live

| citing experiment | fields still unverifiable |
|---|---|
| **EXP-M4-14** | **26** |
| EXP-0171 | 12 |
| EXP-O2C | 10 |
| EXP-0018 | 3 |
| EXP-0115, EXP-O2D | 2 each |
| EXP-0180, RT-ISA-FIX | 1 each |

**`EXP-M4-14-a18-splice` has no `raw/` directory at all** — its evidence is a single
narrative `splice_results.json` of prose strings at the experiment root. All 29
emitter-grade fields citing it are `UNVERIFIABLE`, and **7 of the 17 instructions
that lose emittable status rest entirely on it**: `tex_addr_setup` (11 fields),
`frame_prologue`, `link_save_restore`, `spill_frame_marker` (3 each),
`frag_color_pack`, `iunary`, `rt_query_traverse` (2–4 each). This is the single
largest structural hole in the headline, it is inherited from the A18 phase, and it
is a **CODEX §6 chain break** (`raw` observations are append-only evidence), not a
statement that the hardware behaves otherwise.

## 5a. Direct answer: do emittable instructions still depend on an UNVERIFIABLE field?

**Yes — 8 of the published 55.** After the §4 repairs, 57 emitter-grade fields still
have no attributable per-value raw record anywhere in the repository, and these eight
currently-emittable instructions each rest on at least one of them:

| instruction | still-unverifiable fields it needs |
|---|---|
| `tex_addr_setup` | `form`, `cache`, `op_reg`, `op_hi`, `op_reg2`, `rsv6`, `op_mode`, `src_desc`, `op_desc9`, `op_cnt`, `rsv11` (11 of 11) |
| `spill_frame_marker` | `b1`, `b2`, `b3` |
| `link_save_restore` | `b3`, `dir_offset`, `reserved7` |
| `frame_prologue` | `subop`, `marker`, `frame_size` |
| `frag_color_pack` | `src_gate_select`, `conv_scale` |
| `iunary` | `b1`, `opsel` |
| `simd_reduce` | `op`, `dtype` |
| `rt_query_traverse` | `opA`, `sel` |

Seven of the eight trace to `EXP-M4-14-a18-splice`, the experiment with no `raw/`
directory. `simd_reduce` is the exception (EXP-0018 / EXP-O2D / RT-ISA-FIX, whose raw
predates the per-field record schema entirely).

## 6. Ranked list — which instructions lose status (generous reading, 55 → 38)

Ordered by how cheap the repair is. The first eight are one field away.

| # | instruction | blocking fields | why |
|---|---|---|---|
| 1 | `get_sr` | `dst_hi[29:3]` | INERT-SINGLE, 8 values, **one** carrier (EXP-0168) |
| 2 | `shift_amt_move` | `src_flag[15:1]` | INERT-SINGLE, 2 values, **one** carrier (EXP-0168) |
| 3 | `falu3` | `op[16:8]` | UNSTABLE — 256 values, 428 moved, cross-run agreement < 99 % (EXP-0160) |
| 4 | `falu3_ext` | `op[16:8]` | UNSTABLE — 256 values, 450 moved (EXP-0160) |
| 5 | `irotate` | `operands[24:40]` | UNSTABLE — 1276 values, 2365 moved (EXP-0146/0166) |
| 6 | `tex_deriv` | `dstsrc[16:24]` | UNSTABLE — 65 values over 4 arms (EXP-0172) |
| 7 | `tex_sample` | `mode[80:8]` | no per-value record (RT-5, EXP-0016) |
| 8 | `fspecial_est` | `srcA[8:8]` | no per-value record (EXP-0171) |
| 9 | `simd_reduce` | `op`, `dtype` | no per-value records (EXP-0018/O2D/RT-ISA-FIX) |
| 10 | `iunary` | `b1`, `opsel` | **EXP-M4-14, no raw** |
| 11 | `frag_color_pack` | `src_gate_select`, `conv_scale` | **EXP-M4-14, no raw** |
| 12 | `h_coord_hi_ext` | `srcB`, `ext`, `tail` | all three UNSTABLE (EXP-0157) |
| 13 | `frame_prologue` | `subop`, `marker`, `frame_size` | **EXP-M4-14, no raw** |
| 14 | `link_save_restore` | `b3`, `dir_offset`, `reserved7` | **EXP-M4-14, no raw** |
| 15 | `spill_frame_marker` | `b1`, `b2`, `b3` | **EXP-M4-14, no raw** |
| 16 | `rt_query_traverse` | `dst` + `opA`, `sel`, `opB` | `dst` UNSTABLE over 70 arms; rest **EXP-M4-14** |
| 17 | `tex_addr_setup` | 11 of 11 fields | **EXP-M4-14, no raw** — nothing about this descriptor is reproducible from `raw/` |

The five instructions bought back by the §4 citation repair — i.e. present at 38 but
absent at 33 — are `call`, `half_alu`, `half_alu_ext8`, `mov_zext16`, `stop`.

## 7. The eighth check that cannot come out the other way

**`experiments/EXP-0179-g17p-call/analysis/analyze.py:140-142` — the promotion gate
has no movement requirement.**

```python
promotable = (compared > 0 and agreement >= AGREEMENT_MIN
              and (disagreements == 0
                   or len(moved) >= MOVEMENT_RATIO_MIN * disagreements))
```

`len(moved)` appears only in the right arm of an `or` whose left arm is
`disagreements == 0`. When the two runs agree perfectly the movement clause is
short-circuited away entirely and `promotable` reduces to *"the two runs agreed"* —
and even if the short circuit were removed, the surviving test is
`len(moved) >= 2.0 * 0`, true for every input. **A field that never moves anything,
in a carrier where the instruction is dead code, passes.** Every sibling experiment
carries the missing conjunct (EXP-0169:202, 0171:334, 0172:607, 0178:97, 0180:184,
0184:191, 0187:212); EXP-0179 is the only one that dropped it.

Verified constructively, not argued: a synthetic carrier with 256 byte-distinct
encodings and a bit-identical observation for every value in both runs, fed to the
experiment's own unmodified pipeline, yields
`{"label": "hardware-run", "movement": 0, "gate_pass": true, "range": "0..255 dense
(all 256 values), 2 carriers"}` — **byte-for-byte the string published for
`call.tail` today**. Reproduction in `work/cannotfail-0179/`.

Three fields rode the vacuous branch (`moved=0, disagree=0, agreement=1.0`):
`ret.scoreboard` (hand-declined — correctly), **`call.b6`** (later overturned by the
experiment's own arm S: bit 1 is load-bearing, encodable range 128 not 256), and
**`call.tail`, which was never revisited**. `call.b6` is direct proof that this gate
already shipped a wrong emitter constraint that hardware later refuted; `call.tail`
has the identical evidence shape and the same blind generated leaf callee.

Two aggravating facts: EXP-0179's `PRE_REGISTRATION.md` §11 clause 4 (*"every
falsifier in §7 fired in both runs"*) **is never implemented** — the falsifier
records are collected, written to `report["falsifiers"]`, and read by nothing; and
arm `F` produced **zero records in the gated pair**, running only in a
`MAPPING_…_hangtolerant` run the same pre-registration excludes from the verdict.

**Independent cross-check from this audit's own pipeline:** under the frozen rule
`call.tail` is `INERT-MULTI` — moved 0 on **all three** arms, including the
compiled-splice arm S that overturned `call.b6`. So this audit does not withdraw
`call.tail` (INERT-MULTI is not a withheld bucket), and the headline stays 38. But
its `hardware-run` label rests on a gate that cannot fail, and the honest label for
a field that is inert on every arm tried is an inertness claim, not an emitter
claim. **Recommend: re-derive `call.tail` under a gate with the `moved >= 1`
conjunct, or demote it to `corpus-correlation` as EXP-0179's own sibling
experiments would have.**

## 8. Things checked that came out CLEAN — reported because a clean negative is a result

- **The `moved >= 2.0 * max(disagree, 1)` bug is NOT committed.** It appears
  textually at `EXP-0180/analysis/verdicts.py:184`, but the whole expression is the
  true-arm of `… if disagree else moved > 0`, so `max(disagree,1)` is only evaluated
  when `disagree >= 1`, where it equals `disagree`. Verified by enumeration over
  `(disagree, moved)`; the effective rule is exactly `moved > 0 and moved >= 2*disagree`.
  Every other merged gate uses the correct form. **Cosmetic only — but rewrite the
  line, because the next auditor will read it as a live defect, as I did.**
- **No emitter-grade row's normative `range` text contradicts its own raw.** The
  regex sweep over `range` for inertness/absence claims cross-checked against
  `moved_total` returns **0 rows**. 35 rows match on `note` prose, and every one is a
  *narrated superseded claim* ("first reported INERT … CORRECTED BY THE EXPERIMENT
  ITSELF", "RANGE TEXT WITHDRAWN AND REPLACED") — i.e. CODEX §8 being obeyed, not
  violated. The two the user found today (`half_alu_ext8.rsv6`, `n4_rt_word.dst`)
  are fixed in the pinned snapshot. **H4's refuter does not fire.**
- **`call.b6`'s correction is sound.** Independently re-derived: `STABLE-LIVE`, 256
  values, arm `S_kchain_compiled` moves 128 in each of two gated runs, 99.22 %
  agreement, 2 disagreements. The two generated carriers are inert on it, exactly as
  the note says. The correction was right and the reasoning for it was right.
- **`get_sr.form` → `isolated-byte-diff` survives.** It classifies `STABLE-LIVE`
  under the frozen rule: width 1, both values, three stage carriers, two gated runs,
  100.00 % agreement, 0 disagreements. It is also one of the 48 width-1 fields that
  prove the gate is not silently refusing width-1 promotions (C6).
- **The `_instruction` gate is nearly clean.** Of the 92 emitter-grade `_instruction`
  entries, **85 have per-value hardware dispatch records** attributable to that exact
  descriptor; 2 are bytes-seen-only (`call_indirect`, `spill_frame_marker`) and 5
  have no per-value record at all (`frame_prologue`, `imageblock_load`,
  `link_save_restore`, `rt_intersect`, `tex_addr_setup`). Withholding those 7 costs
  **4** of the published 55 on its own — and all 4 are already lost for field
  reasons, so the gate adds nothing to the shortfall. Applying it was correct.

## 8a. The four ungated hand-rulings, checked one at a time

An independent second pass re-derived each from raw. Two survive, one is over-labelled
but not fatal, one does not survive.

**`call.b6` — SOUND, the cleanest of the four.** Arm S (mutating the compiler-emitted
call inside our own `c_frame.metal`, host oracle `k_chain(3,5) = 23.0f`, poisoned
buffer): `splice01` 128/128 `ok` with bit 1 SET and **0/128** with it clear;
`splice02` identical. Perfect separation on the bit-1 predicate in both runs, zero
exceptions. This audit's own pipeline agrees independently: `STABLE-LIVE`, 99.22 %
agreement, arm S moves 128 in each gated run while both generated carriers are inert
— exactly as the note says. The correction also *restricts* emitter freedom
(`encodable_range` 256 → 128), which is the safe direction. **Keep.**

**EXP-0181's `_instruction` refresh — SOUND, and the strongest work in the batch.**
All **30** refreshed rows have raw records whose `bytes` satisfy that mnemonic's own
`db.json` `match` constraints (bit-exact attribution, not the harness's `instr`
label), ranging from 532 to 29,225 cases. **Zero rest on decode/corpus/round-trip
evidence.** The "230,804 cases across 18 experiments" and the "costs 5, not 30" gate
arithmetic both reproduce to the digit at that commit. And the promote/hold split
tracks host-oracle coverage almost perfectly: the nine promoted to `hardware-run` at
100 % oracle coverage, against **five held at `isolated-byte-diff` with 0.0 %**
(`h_coord_hi`, `h_coord_hi_ext`, `iter_flat`, `rtq_state_move`, `sr_read_wide`).
That is the rule being applied, not retrofitted. **Keep. H5 confirmed.**

**`iter_at._instruction` → `hardware-run` — OVER-LABELLED, count unaffected.**
Dispatch is genuine (10,398 bit-exactly attributed records over 14 arms, three
experiments, G17P). But **10 of those 10,398 carry a host oracle (0.1 %)** — by two
orders of magnitude the weakest of any `hardware-run` `_instruction` among the 55 —
every arm is a one-byte mutation of a compiler-emitted instruction with **no generated
encoding anywhere**, and the stated rationale ("all six field rows are emitter-grade,
so this label was the only remaining blocker") is the inference EXP-0181's own R5 was
frozen to forbid. The unmutated program *did* reproduce its host oracle exactly across
four gated runs with a falsifier that held, which is `isolated-byte-diff` verbatim.
**Correct it to `isolated-byte-diff` — still emitter-grade, so `iter_at` keeps its
status and the headline does not move.**

**`get_sr.form` → `isolated-byte-diff` — DOES NOT SURVIVE.** The observation is real
and reproducible (this audit buckets it `STABLE-LIVE`: 2 of 2 values, three stage
carriers, two gated runs, 100.00 % agreement, 0 disagreements — and it is one of the
48 width-1 fields that prove the gate is not silently refusing width-1 promotions).
**The label is the problem, not the movement.** `docs/evidence-classification.md` §35
defines `isolated-byte-diff` as an isolated reproducible byte change *"**and** the
resulting program ran with the predicted effect"*. Four facts against it:

1. all 12 records carry `oracle: null`, `foreign: true`, `match: false`,
   `outcome: "wrong_value"` — **including cases whose bytes are identical to the arm's
   own unmutated anchor.** A regime that scores the baseline `wrong_value` is not an
   oracle, and only the baseline-hash movement flag is usable — which EXP-0181 itself
   classifies as *"the BYTES are live — nothing about semantics"*;
2. **EXP-0178 filed no verdict for it.** Its `field_verdicts.json` has exactly three
   keys (`sr_sel`, `dp_width`, `dp_marker`) and its RESULTS says `form` was *"swept and
   recorded but not ruled on"* — `validation.json` cites it as evidence for a row that
   experiment declined to produce;
3. the "the eight declining arms cannot express the field" rebuttal is **factually
   wrong about EXP-0172**, whose `field_verdicts.json` records
   `rule2_dimension.dimension = "special-register DATAPATH WIDTH"`, `spanned: true`,
   4 arms at form=0 and 4 at form=1 — it spanned the dimension `db.json` says the bit
   controls, in both flip directions, and concluded *"NOT emitter-grade (rule 8)"*.
   The counter-claim that the controlling dimension is *shader stage* is a new
   hypothesis borrowed from a different field (`sr_sel`);
4. no effect was predicted — the ruling's own text concedes *"it did not identify what
   form=0 does"*, and the vertex form=0 output is a ramp of large floats where the
   shader returns a constant 7, as consistent with corruption as with a feature.

`validation.json`'s own `_conventions` block already names this case: a field exercised
on hardware whose semantics remain unexplained is **`untested`, with the observation
recorded in `note`**. **The demotion from `single-template-inference` was right; the
destination was not.** This audit independently drops `get_sr` anyway, for a different
field (`dst_hi`, INERT-SINGLE on one carrier) — two independent routes to the same
withdrawal.

## 8b. The number is also too LOW on one axis: six stale `_instruction` labels

The DEF-0173-1 gate costs six instructions whose fields are all emitter-grade but whose
`_instruction` label is stale — and **all six have per-value hardware dispatch records
in this audit's index**:

| mnemonic | `_instruction` label | dispatch records in |
|---|---|---|
| `copysign` | `corpus-correlation` | EXP-0138, EXP-0168, EXP-0184 (4,891 host-oracle-scored) |
| `n2_op6` | `corpus-correlation` | EXP-0146, EXP-0157 |
| `frag_depth_store` | `corpus-correlation` | EXP-0155 |
| `vary_slot` | `corpus-correlation` | EXP-0155, EXP-0172 |
| `frame_marker_compact` | `tokenization-only` | EXP-0172 |
| `sfu_marker` | `tokenization-only` | EXP-0146, EXP-0157 |

`copysign` became field-emittable only after EXP-0184, *after* EXP-0181's sweep, so the
gate's cost silently grew 5 → 6. These are stale in exactly the way EXP-0181 diagnosed.
**Recommendation: re-run EXP-0181's script over these six rather than ruling by hand** —
and note that whatever it returns should be applied *before* the headline is published,
because it moves the number in the opposite direction from everything else in this
report.

## 9. Deviations from the pre-registration

- `analysis/collect_raw.py` and `analysis/audit.py` differ from EXP-0164's only in
  the `_meta` `experiment` / `generated_by` strings and the pinned snapshot hash
  (3 hunks, verified by `diff` against `git show HEAD:…`). No threshold, bucket rule
  or gate was changed.
- `analysis/{recount,rescue,finalize}.py` are new and produce **new outputs only**.
  `recount.py` reimplements the *current* `validate_labels.py` emittable rule, which
  audit.py (written before the `_instruction` gate existed) does not implement; that
  is why audit.py prints 61 where validation.json publishes 55. `rescue.py` asserts
  the frozen thresholds are unchanged before it will run.
- The §7.4 contradiction sweep was run twice: once over `range`+`note`+`semantics`
  (35 hits, all note-prose narrating superseded claims) and once over the normative
  `range` alone (0 hits). Both are reported; the `range`-only result is the verdict.
  A third, unplanned sweep for **coverage overclaims** (a `range` claiming more
  values than the raw dispatched, capped at 2^width) found **44 rows**, 26 of them
  already `UNVERIFIABLE`; it is reported in
  `analysis/reclassify.json → coverage_overclaims` as an advisory, not folded into
  the headline, because it was not pre-registered.

## 10. Limitations — read these before acting on the number

- **`UNVERIFIABLE` is an auditability verdict, not a refutation.** 57 rows cannot be
  re-derived from committed raw; that does not mean the hardware disagrees. The right
  response to the EXP-M4-14 block is a re-record on G17P, not a claim that
  `tex_addr_setup` is wrong.
- **This audit inherits EXP-0164's attribution and its blind spots**, one of which
  (the `_`-prefix rule) I found and had to repair mid-run. There may be others of the
  same shape, and each one *over*-counts `UNVERIFIABLE`.
- **A `fault` recorded inside a DEF-0178-1 reader-thread cascade is an artefact and
  the indexer cannot tell it from an observation.** Several `UNSTABLE` verdicts
  (notably `falu3.op`, `falu3_ext.op` from EXP-0160, which itself documented
  busy-machine manufactured faults) may be artefacts of that defect rather than real
  instability. They are withheld here because they *do not reproduce*, which is the
  correct conservative call either way, but a quiet-machine re-run could recover
  them.
- Nothing here was measured on hardware. Every number is a re-derivation from
  records other experiments captured, on the targets they name (M4/G16G for the
  EXP-01xx sweeps below 0154, G17P above).

## 11. Verdict

**55/166 is inflated by 17. Publish 38/166, or 33/166 if you will not repair the
evidence citations first. Fields: publish 556/1040, not 638/1040.**

The number is not inflated because the merges were careless — the post-`459bb8bd`
cohort is statistically indistinguishable in grade from the corpus it joined. It is
inflated because **the pre-existing A18-phase debt was never re-measured**, and
`EXP-M4-14`, an experiment with no `raw/` directory at all, is still load-bearing for
seven instructions and 29 fields.

Cheapest paths back up, in order:

1. **repair the 29 stale `evidence` citations** — +5 instructions, zero new hardware,
   and it is required by CODEX §9 anyway;
2. **re-run EXP-0181's `_instruction` script over the six stale rows of §8b** — up to
   +6, again with no new hardware;
3. a second, structurally different carrier for `get_sr.dst_hi` and
   `shift_amt_move.src_flag` — +2, one short sweep each;
4. a **quiet-machine** re-run of `falu3.op`, `falu3_ext.op`, `irotate.operands`,
   `tex_deriv.dstsrc` — +4, and it also tests whether their instability is the
   DEF-0178-1 artefact;
5. re-record `EXP-M4-14`'s seven descriptors on G17P — +7, the largest and slowest, and
   the only one that closes the actual chain break.

Two corrections that do not move the number but should land anyway: relabel
`iter_at._instruction` `hardware-run` → `isolated-byte-diff`, and rewrite
`EXP-0180/analysis/verdicts.py:184` so it stops reading like the width-1 gate bug.

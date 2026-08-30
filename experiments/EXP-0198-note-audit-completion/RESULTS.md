# EXP-0198 — RESULTS

## 0. Headline

**Ten more notes in `tools/agx-isa/validation.json` state an observation that committed
evidence contradicts. All ten are on emitter-grade fields, and all ten fail in the same
sentence: `"the original arm showed it inert."`** Six sit on `tex_sample`, three on
`iter_flat` — which is one of the 32 mnemonics in `coverage.emittable_mnemonics` — and one
on `iter`.

The defect is a per-instruction sentence pasted onto per-field rows. Twelve rows carry the
re-pointing clause; the clause's *positive* half (the new arm is live, with these numbers)
is exact in all twelve, and its *negative* half ("the original arm showed it inert") is
true in exactly **two** of them and false in **ten** — against the arm the note itself
names, in EXP-0155's own committed `cross_run` block, inside the same JSON object.

**Denominator actually tested: 164 of the 167.** All 113 emitter-grade *field* rows were
tested; the three I could build no instrument for are two emitter-grade `_instruction`
rows and one `corpus-correlation` row, reported as `INSTRUMENT-LIMITED` rather than filed
under `UNCHECKABLE` — a distinction EXP-0196 insisted on and this experiment keeps.

**Part 2 is settled: the `note` is right and the `range` is stale.** The 12 `b_alu10_*`
rows are not a contradiction inside one measurement; they are two statements about two
different descriptor identities, separated by the `ilogic` re-span in commit `74f6af25`
(EXP-0174/0175). Evidence in §5.

---

## 1. Buckets over the 167

| bucket | all 167 | emitter-grade fields (113) | emitter-grade `_instruction` (9) | other (45) |
|---|---:|---:|---:|---:|
| **SUPPORTED** | **154** | **103** | 7 | 44 |
| **OVERSTATED** | **10** | **10** | 0 | 0 |
| **UNCHECKABLE** | 0 | 0 | 0 | 0 |
| **CITES-MISSING-FILE** | **0** | 0 | 0 | 0 |
| *INSTRUMENT-LIMITED* | 3 | 0 | 2 | 1 |

`analysis/classification.tsv` has the per-row detail. Every SUPPORTED row was regrounded
from committed raw or from the producing experiment's own structured output; none is
"supported" merely because a search came back empty, except `funary.mod`, whose claim
*is* a negative existential (§4.3).

### 1.1 What was regrounded, and from what

| family | notes | what was re-derived from raw | result |
|---|---:|---|---|
| EXP-0139 (ialu) | 38 | reconcile gate re-implemented from `verdicts.py:11-27,58-72`; unstable/fault/silent-zero/works counts **and the exact value-range strings** | 38/38 |
| EXP-0157 (misc) | 25 | 59 `outcomes` segments + 29 `accepted set:` masks, over **11 112 gated cases**, under the RSH/B2 gate | 25/25 |
| EXP-0162 (pack) | 12 | per-field outcome histograms + the arm-level "detection power" figures (71/1816, 86/1304 & 115, 212/1304) | 12/12 |
| EXP-0189 withheld, N>0 | 25 | transcription against `withhold_flat.json`'s own `max_values_dispatched`/`n_arms`/`moved_total`, plus a raw floor on distinct values | 25/25 |
| EXP-0155 (tex/frag) | 19 | movement/agreement metric **validated against all 227 committed `cross_run` triples before use** | **9/19** |
| EXP-0141 (mem) | 10 | 15 005 addendum cases; the four operand-register indices; the acceptance-disagreement count | 10/10 |
| EXP-0140 (mov/cf) | 8 | comparable/stable gate + **both documented repairs** (`repair_signed_compare`, `reclassify_no_store`) | 8/8 |
| EXP-0147 (pipeline) | 6 | accepted-set rules, outcome histograms, per-byte inertness, intra-run stability | 6/6 |
| EXP-0138 (falu) | 4 | prediction-refutation counts under the victim gate | 4/4 |
| EXP-0161/0165 (fspecial) | 4 + `carry_gen.srcB` | destination/source register maps from the 16-GPR dump, the roundmode NaN result, the danger sweep | 5/5 |
| EXP-0191/2/3 "Case C" clauses | 4 | against those experiments' own structured outputs | 4/4 |
| the rest | 16 | anchors decoded with our own disassembler; census figures against their sources | 13/16 |

---

## 2. The ten OVERSTATED notes

All ten are the same sentence. Quoted below: the note verbatim from
`tools/agx-isa/validation.json`, then the line of EXP-0155's own
`analysis/field_verdicts_flat.json` that contradicts it — **the `cross_run` entry for the
very arm the note names, inside the same JSON object as the note**.

### 2.1 `tex_sample` — six rows, all `hardware-run`

> `tools/agx-isa/validation.json:3704` (`tex_sample.chain`)
> `"[orchestrator: representative arm re-pointed from tex_sample@t1_0 to tex_sample@lo_1, where the field is demonstrably live (15/15 of 16 moved, 100.0% cross-run agreement); `**`the original arm showed it inert.`**`]"`

> `experiments/EXP-0155-g17p-emit-tex-frag/analysis/field_verdicts_flat.json:2925`
> `"tex_sample@t1_0": { "agree": 100.0, "common": 16, "disagreements": 0, `**`"moved03": 15, "moved04": 15`**`, "stable_live": true },`

| row | validation.json | note says the original arm | `field_verdicts_flat.json` says that arm | raw (run03 ∩ run04) |
|---|---|---|---|---|
| `tex_sample.chain` | :3704 | inert | :2925 `moved03 15 / moved04 15 of 16` | 15/15 of 16 |
| `tex_sample.kind` | :3695 | inert | :3234 `moved03 15 / moved04 15 of 16` | 15/15 of 16 |
| `tex_sample.comp_flags` | :3713 | inert | :3035 `moved03 14 / moved04 14 of 16` | 14/14 of 16 |
| `tex_sample.result_sel` | :3732 | inert | :3462 `moved03 248 / moved04 248 of 256` | 248/248 of 256 |
| `tex_sample.lod_present` | :3811 | inert | :3344 `moved03 128 / moved04 128 of 256` | 128/128 of 256 |
| `tex_sample.tex_type` | :3820 | inert | :3698 `moved03 254 / moved04 254 of 256` | 254/254 of 256 |

A per-case witness, straight out of the append-only raw:

```
experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run03/sweep.jsonl:1055
{"carrier": "tex_sample@t1_0", "field": "chain", "value": 1, "outcome": "wrong_value",
 "bytes": "15800c2090000000000110000100"}

experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run03/sweep.jsonl:2116
{"carrier": "tex_sample@t1_0", "field": "tex_type", "value": 2, "outcome": "wrong_value",
 "bytes": "05800c2090000000000110000200"}
```

**The seventh `tex_sample` row is the control.** `tex_sample.samp_extra`
(`validation.json:3829`) carries the identical sentence and it is **true**: `t1_0` gives
`moved03 0 / moved04 0 of 256`. That is the one field of the seven for which `t1_0` really
was inert — and it is almost certainly why the sentence was written at all.

### 2.2 `iter_flat` — three rows, on one of the 32 mnemonics in `coverage.emittable_mnemonics`

> `tools/agx-isa/validation.json:5791` (`iter_flat.b4`, `hardware-run`)
> `"[orchestrator: representative arm re-pointed from iter_flat@flat1 to iter_flat@flat0, where the field is demonstrably live (254/254 of 256 moved, 100.0% cross-run agreement); `**`the original arm showed it inert.`**`]"`

> `experiments/EXP-0155-g17p-emit-tex-frag/analysis/field_verdicts_flat.json:1749`
> `"iter_flat@flat1": { "agree": 100.0, "common": 256, "disagreements": 0, `**`"moved03": 254, "moved04": 254`**`, "stable_live": true }`

| row | validation.json | flat file | raw |
|---|---|---|---|
| `iter_flat.b4` | :5791 | :1749 `254/254 of 256` | 254/254 of 256 |
| `iter_flat.b5` | :5800 | :1795 `191/192 of 256` | 191/192 of 256 |
| `iter_flat.sel` | :5782 | :1841 `124/124 of 126` | 124/124 of 126 |

`raw/g17p_20260829_run03/sweep.jsonl:36081` —
`{"carrier": "iter_flat@flat1", "field": "b4", "value": 0, "outcome": "wrong_value", "bytes": "1f0354060005"}`

### 2.3 `iter.grp` — one row, `hardware-run`

> `tools/agx-isa/validation.json:5612`
> `"[orchestrator: representative arm re-pointed from iter@frag0W to iter@frag1, where the field is demonstrably live (255/255 of 256 moved, 100.0% cross-run agreement); `**`the original arm showed it inert.`**`]"`

> `experiments/EXP-0155-g17p-emit-tex-frag/analysis/field_verdicts_flat.json:1255`
> `"iter@frag0W": { "agree": 100.0, "common": 256, "disagreements": 0, `**`"moved03": 254, "moved04": 254`**`, "stable_live": true },`

`raw/g17p_20260829_run03/sweep.jsonl:31149` —
`{"carrier": "iter@frag0W", "field": "grp", "value": 0, "outcome": "fault", "bytes": "000d5400030004021000"}`
— 238 of the 256 values FAULT on that arm. Whatever else it is, it is not inert.

### 2.4 What "inert" means here, so the finding cannot be read loosely

The vocabulary is EXP-0155's own. `analysis/withheld_by_orchestrator.json` withholds rows
with the reason string `"never-moved; single carrier only"`, and every row it so withholds
has `moved03 == 0 and moved04 == 0`. The ten rows above have `moved03/moved04` between 14
and 254. The metric was **validated before use**: recomputing `moved_r` = |{v present in
both run03 and run04 : outcome_r(v) != "ok"}| and `agree` = agreement on the boolean
"moved" reproduces **all 227** committed `cross_run` triples in
`field_verdicts_flat.json` **exactly, 227/227** (`analysis/check_0155.py`).

### 2.5 What is NOT wrong

* **The re-pointing itself is right.** The new arm's figures (`15/15 of 16`,
  `254/254 of 256`, `126/126 of 126`, …) are exact in all twelve rows, from raw.
* **The labels are not touched by this.** Each field is live on the arm the row now cites;
  a stale justification for choosing that arm is not a claim that the field moved.
* **The other clause in the same notes is fine.** `iter_flat.sel`'s
  "swept 127/256 of the frozen value set in both runs" and `iter_flat.b5`'s
  "1/256 values disagree" both reproduce exactly — once the clause is attributed to the
  arm it was written for (the *original* arm) and counted under `verdicts.py`'s own
  convention, which does not drop the `value = -1` sentinel record. Getting either of
  those two details wrong reads every such note as off-by-one (§6.2).

---

## 3. INSTRUMENT-LIMITED: three claims I could not test

Reported, not counted. **The raw for these may well exist; what is established is that
*I* could not build a check that could have returned "no".**

1. **`half_alu_fma12._instruction`** (`hardware-run`, emitter-grade instruction) —
   *"121/126 corpus instances embed a real op-leader byte (0x9f iadd, 0xa8, 0x54, 0xe7)
   inside `ext`"*. The figure is carried from a committed artifact —
   `tools/agx-isa/db.json`'s `half_alu_fma12.provenance`, which attributes it to
   *"census EXP-M4-13 R8/R10 (own-MSL half corpus)"* — but the census is not reproducible
   at desk: `EXP-M4-14-a18-splice/corpus/` holds `.metal` **sources** only, and the
   descriptor has been re-spanned since R8 (EXP-0183). Recounting over
   `EXP-M4-13-full-corpus/hex/*.hex` under **today's** db.json gives 7 instances, 2 with an
   op-leader byte — a different population under a different descriptor, so it is not a
   refutation and is not reported as one.
2. **`frag_depth_store._instruction`** — *"its baselines are ok 11/11"*. Under the exact
   convention that makes `iter_flat._instruction`'s *"baselines on G17P 23/23"* come out
   exact (every underscore-prefixed control record for the instruction across the two
   gated runs, all `ok`), `frag_depth_store` gives **12/12**, not 11/11 — one more, all
   `ok`. The claim is an **undercount**, i.e. conservative, and I cannot exclude that the
   author used a slightly different control set. Recorded as an imprecision on the
   precedent EXP-0196 set for `sr_read_wide`'s "3 ray-query carriers" vs five.
   (`All three of its declared fields are hardware-run` is exact; so is the db.json quote.)
3. **`mov_imm._instruction`** — *"196,114 assembler-GENERATED mov_imm instances inside 233
   zero-copied programs whose 01_results.jsonl was BYTE-IDENTICAL across two isolated gated
   runs"*. 196 114 is exact
   (`EXP-0167/analysis/assemble_defect_check.json` → `mnemonics_used.mov_imm`), and the two
   `01_results.jsonl` files are byte-identical (verified by hash). **233** is EXP-0167's
   `zero_copied_and_matched`; the zero-copied population is **237**
   (`EXP-0167/RESULTS.md:11`, *"233 of 237 zero-copied programs matched"*). The note
   attaches the instance count to the smaller number, which understates the population —
   conservative, so not a finding.

---

## 4. Notable SUPPORTED results

### 4.1 The two largest families are clean, and were regrounded from raw

* **EXP-0139, 38/38.** `analysis/check_0139.py` re-implements the reconciliation gate from
  the docstring (`verdicts.py:11-27`) rather than importing it, then reproduces every
  `N/M values excluded as not reproducible`, every `reproducibly FAULT … at N values: <ranges>`,
  every `N values return a silent zero` and every
  `TESTED-BUT-UNEXPLAINED: K of N … (<ranges>)` — **including the literal value-range
  strings**, e.g. `isel10.selFalse_file`'s `64-78,80,82-95,192-211,213-223`.
* **EXP-0157, 25/25 over 59 segments and 11 112 gated cases**, including all 29
  `accepted set: (value & 0xMM) == 0xVV` masks, re-derived with an independent
  implementation of the unique-mask search.

### 4.2 The sharpest single claims in the 167, all exact

* **`fspecial.dst`**: *"45 of those 64 values gave a genuine
  `kIOGPUCommandBufferCallbackErrorHang`, 19 were only ever observed as innocent victims,
  and none ever worked"* → `raw/g17p_20260830_danger01/sweep.jsonl`: 64 cases, 45 hangs, 19
  victim-only, 0 worked. Exact.
* **`fspecial.roundmode`**: *"128/128 odd values all-NaN and 128/128 even values
  bit-matching the baseline, in two carriers × two gated runs, with no exceptions"* →
  exact in all four (run, carrier) combinations.
* **`fspecial.dst`/`.src` register maps**: 28/28 and 60/60 fits, 0 misfits, in both gated
  runs, re-derived from the 16-register architectural dump with an independently written
  `rsqrt` matcher; `v = 12/13` are indeed the invisible seed-alias pair.
* **`atomic_rmw.oper_reg_hi`**: *"byte+6 values 0x30 and 0x31 … are the only two addendum
  cases whose acceptance disagreed between run21 and run22"* → over **15 005** common
  addendum cases, exactly two acceptance disagreements, at exactly 0x30 and 0x31, and the
  model `(byte+5>>7) | ((byte+6 & 0x3F)<<1)` puts them at indices 97 and 99 as stated.
* **`carry_gen.srcB`**: accepted set is exactly `{3, 131}` = `(v & 0x7F) == 0x03`, 2 of 256,
  on both arms in both gated runs; the released-register map `reg=(v>>1)&0x3F` fits 22/22.
* **`falu2_ext.srcB_neg`**: `6901040501000080` vs `6901040501080080` differ in exactly one
  bit — **bit 43**, popcount 1 — which is db.json's `srcB_neg` (start 43, width 1); `w0`
  goes 8.0 → 2.0 with both sentinels (`w4 = 26.0`, `w8 = 5.0`) unchanged; the oracle
  predicted 8.0 and 2.0 *separately* and matched both; identical in run01, run05 and run06.
* **`iter_at._instruction`**: *"0/256 at one sample, 128/256 at four"* → EXP-0163's
  `cent1` occurrences move 0 of 256 and its `cent4` occurrences move 128 of 256, in both
  gated runs; the moved set is exactly `{v : bit1 set}`. And
  *"10,398 dispatch records but only 10 carry an oracle (0.1%)"* → summing
  `EXP-0189/work/oracle_scan.json` over `iter_at` gives **n = 10 398, oracle = 10**.
* **`if_push.scope`**: EXP-0184's 10 arms all move 0 of 256, on 2 carriers, with 1 distinct
  baseline value (0x54), every control fired; EXP-0188's six loop carriers, the 0x54/0x56
  span, the four `0x1a` occurrences and the un-completed gated pair are all verbatim in
  `EXP-0188/analysis/field_verdicts_flat.json`.
* **Three anchors decoded with our own disassembler**: `09011e0581080200` → `falu3`,
  `09011e05820802000080` → `falu3_ext` at length 10, `2701560002006c00f0150900` → `irotate`.

### 4.3 The one negative existential

`funary.mod`: *"Own-shader byte-diff; no synthesized value was executed."* Scanning every
`experiments/*/raw/**/*.jsonl` for a per-value record with `instr == "funary"` returns
**zero**. This is the one row whose SUPPORTED verdict rests on an absence, and the
asymmetry cuts the dangerous way here (a false absence would wrongly *support* the note),
so it is flagged in §6.

---

## 5. PART 2 — the twelve `b_alu10_*` rows: the note is right, the range is stale

**Verdict: they are not two readings of one measurement. They are two statements about two
different descriptor identities, and the identity changed between them.**

The 12 rows are `b_alu10_loe` and `b_alu10_lof` × `{modA, modB, outmod, srcA, src_flag,
src_reg}`, all `untested`, all cited to `EXP-0171`.
*(Small correction to `EXP-0196` §3.5, which quotes all twelve ranges as "256 of 256": four
are not — `src_flag` is `"2 of 2 sub-values, DENSE"` and `src_reg` is `"128 of 128"`. Both
match EXP-0171's own per-key `values_dispatched` of 2 and 128.)*

**B1.** All 12 carry both strings. **B2.** No raw record anywhere in
`experiments/*/raw/**/*.jsonl` has `instr` starting `b_alu10` — **0 of them**, which is
what EXP-0196 found and is the reason it could not go further.

**B3 — the records exist, under `ilogic`.** `EXP-0171/analysis/field_verdicts.json`
carries **18** `b_alu10_*` keys, and **every carrier of every one of them is an `ilogic`
anchor**: `FRAME:k_and@ilogic+32`, `NAT:k_and@ilogic+32`, `SYNTH:k_and@ilogic+32`,
`NAT:k_andn@ilogic+32`, `NAT:k_nand@ilogic+32`, `NAT:k_or@ilogic+32`,
`NAT:k_xor@ilogic+32`. Their `values_dispatched` / `distinct_bytes` are 256 (and 2 for
`src_flag`, 128 for `src_reg`) — **exactly the numbers the `range` strings state.** So the
`range` is a faithful transcription of a real, dense, two-run measurement.

**B4 — the descriptor was re-spanned, by `74f6af25` (`exp(0174,0175)`).**

| | `ilogic.match` | `b_alu10_loe.match` | `b_alu10_lof.match` |
|---|---|---|---|
| before `74f6af25` | `[[0, 8, 11], [17, 7, 15]]` | `[[0,4,11],[16,4,14]]` | `[[0,4,11],[16,4,15]]` |
| after `74f6af25` | `[[0, `**`4`**`, 11], [17, 7, 15]]` | *unchanged* | *unchanged* |

`ilogic`'s byte0 constraint went from the **whole byte** `0x0b` (destination r0 only) to the
**low nibble** `0x0b` (any destination). The `b_alu10_*` descriptors did not move at all.

**B5 — and that flips the tokenization of the exact bytes EXP-0171 dispatched.** Its
anchors are `2b 03 1f 01 …` and `2b 03 1e 01 …` — byte0 `0x2b`, i.e. destination **r2**:

| bytes | tokenizes as, before `74f6af25` | tokenizes as, after |
|---|---|---|
| `2b031f01000000000000` | **`b_alu10_lof`** (8 bits constrained) | **`ilogic`** (11 bits) |
| `2b031e01000000000000` | **`b_alu10_loe`** (8) | **`ilogic`** (11) |
| `2b011e01000000000000` | **`b_alu10_loe`** (8) | **`ilogic`** (11) |

(most-specific match wins, db.json's own rule; `analysis/check_b_alu10.py` computes both.)

**B6 — db.json already says so, in a sentence addressed to exactly this question.**
`tools/agx-isa/db.json`, `b_alu10_loe.semantics`:

> **"NOTE FOR LABEL AUDITORS: EXP-0171 swept only opsel_hi == 1 and reported the same cases
> under both key sets, so this descriptor's `hardware-run` rows are ALIASES of the ilogic
> sweep and no evidence in that experiment exercises opsel_hi in {2,3,4,6,8,12}."**

### 5.1 The ruling

* **The `note` is correct.** Under the current descriptor set, nothing that was ever
  dispatched is an instance of `b_alu10_loe` or `b_alu10_lof`. `0 values dispatched over 0
  arm(s), 0 observations moved — Reason: no-field-records` is an accurate statement about
  this descriptor as it now stands. EXP-0189 was measuring the right thing.
* **The `range` is stale, not false.** It accurately reports EXP-0171's dense sweep, but
  that sweep is an alias of the `ilogic` sweep at `opsel_hi == 1`, and since `74f6af25`
  those bytes are `ilogic`. As a description of *this* descriptor it survives only under
  the pre-repair identity.
* **They do not refer to the same descriptor identity**, which is why they can both be
  honest and still contradict each other. The gap is the `ilogic` re-span, and the rows
  were never re-derived across it.
* **The `untested` labels are right** and nothing here argues for changing them; the risk
  the pair creates is a *reader* taking `"256 of 256 sub-values, DENSE"` as coverage
  evidence for a descriptor whose defining byte+2 high nibble — db.json's own lists are
  `0x2e/0x3e/0x6e` for `loe` and `0x3f/0x4f/0x6f/0x8f/0xcf` for `lof` once `0x1f` goes to
  `ilogic` — has never been dispatched. **Reported; the orchestrator rules.**

---

## 6. How this method could have failed to say "no"

Stated so the next reader can attack it. Four of these fired during the audit, and one of
them fired against this audit's own instruments.

1. **My first EXP-0155 pass produced 16 false findings, and the cause was the gate.**
   EXP-0155's gated pair is **run03 + run04**, not the directories named run01/run02:
   `EXP-0155/analysis/field_verdicts.json["_runs"]` says so, and
   `raw/g17p_20260829_run01/PARTIAL.md` says run01 is *"PARTIAL, RETAINED, NOT REUSED, NOT
   USED FOR PROMOTION"*. Pairing run01 with run02 made almost every EXP-0155 note read
   CONTRADICTED. **Had I stopped there I would have published 16 findings, 6 of them
   fabricated.** The first pass is described here rather than hidden.
2. **A second false-finding wave came from two conventions inside one experiment.**
   `verdicts.py`'s `swept N/M` counts the `value = -1` sentinel record; the flat file's
   `cross_run` block does not. And a swept/disagree clause on a *re-pointed* row was
   written for the **original** arm, not the new one. Getting either wrong turns every such
   note into an off-by-one "finding". Both are now explicit in `check_0155.py`.
3. **EXP-0140 nearly cost me two more.** Its analysis applies two documented repairs
   before the gate — `repair_signed_compare` (a signed/unsigned oracle-comparison bug that
   mis-scored the bound constant `0xA1B2C3D4`) and `reclassify_no_store` (an
   `invalid_run` in both runs with every trial `STATUS OK` is a real encoding effect, not
   contamination). Omitting them made `uniform_mov.usrc`'s "8/8" read as 6/8 and
   `if_push.scope_kind`'s "242 comparable" read as 192. Re-implementing both reproduces
   EXP-0140's own `repaired_signed_compare = 4` and `reclassified_no_store = 65` exactly,
   and all eight rows are SUPPORTED. Same shape as EXP-0141, where counting `match`-flag
   disagreements instead of the documented **acceptance** disagreements (`ok` vs not-`ok`,
   `verdicts.py:19-26`) gives 3 where the note says 2.
4. **My own instruments failed a falsifiability control on the first attempt — 4 of 11.**
   `analysis/negative_control.py` perturbs one number in one note per family by +1 and
   requires the row to flip to CONTRADICTED. Four checks did not flip, because they
   compared raw against a constant *I* had transcribed from the note rather than against
   the note itself — a check that cannot come out the other way. All four were rewritten to
   parse the claimed number out of the note text. **The control now passes 11/11.** It is
   committed and re-runnable; it is the part of this experiment most worth attacking next.
5. **The audit is asymmetric, on purpose, and one row depends on the weak direction.**
   It can prove a negative existential wrong (a record exists) but not right (an absence in
   my index is not an absence in the corpus). Nine of the ten findings are of the strong
   kind — a positive assertion of inertness contradicted by present, counted records.
   `funary.mod` (§4.3) is the exception: its SUPPORTED verdict rests on a search returning
   nothing, and a field-name-keyed miss there would wrongly support the note. I keyed on
   `instr` rather than `field` to widen it, but that is a mitigation, not a proof.
   Six of the 25 EXP-0189 rows are likewise reported `INSTRUMENT-LIMITED` on their raw
   floor rather than counted either way.
6. **I checked notes against raw and against producing artifacts, not raw against reality.**
   Where a producing experiment's structured output and its raw agree, I mark SUPPORTED. If
   a harness wrote a wrong `outcome` into the raw in the first place, this audit reproduces
   the error and calls it support. Three rows are supported *only* by transcription
   fidelity against the producing experiment's own JSON (§3), and 25 more — the EXP-0189
   withheld family — are supported by transcription plus a raw *floor*, not by re-deriving
   EXP-0189's byte-attribution collector, which I did not reimplement.
7. **Ten findings, one sentence, one experiment.** All ten sit in orchestrator-authored
   text appended at merge time to rows from a single experiment, and
   `EXP-0155/analysis/field_verdicts_flat.json` has **no committed generator script** in the
   tree — so that file's `cross_run` block, which is what refutes the sentence, is itself
   an artifact whose production I cannot re-run. I therefore re-derived its metric from raw
   and required it to reproduce all 227 committed triples before using it. That is the
   strongest check available at desk; it is not the same as having the generator.
8. **Three claims went untested (§3) and are not in any bucket that implies a verdict.**
   Counting them as UNCHECKABLE would be exactly the cannot-fail bookkeeping this corpus
   keeps catching, so they are separated. At the 10/164 ≈ 6 % rate measured here, the
   expected number of further findings hiding in three rows is small — but that is an
   argument about arithmetic, not about those three rows.

---

## 7. Files

`analysis/classification.{json,tsv}` — the buckets, per note, with which checks ran.
`analysis/check_*.json` — per-check evidence, including the raw statistics behind every
verdict. `analysis/negative_control.json` — the falsifiability control, 11/11.
`analysis/check_b_alu10.json` — Part 2. `analysis/run_all.sh` — regenerates all of it.

**Nothing in `tools/agx-isa/`, `docs/`, or `PROVENANCE.md` was modified. No label was
changed. No label change is proposed. Nothing was committed.**

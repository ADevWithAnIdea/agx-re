# EXP-0195 — RESULTS

## 0. Headline

**132 rows evaluated. Zero new recoveries.**

| | count | share |
|---|---:|---:|
| **RECOVERED** (DESK-PROMOTABLE on uncited evidence alone) | **1** | 0.8 % |
| — of which *new* (not already promoted by EXP-0194) | **0** | 0 % |
| **AMBIGUOUS** (reaches G7, no discriminating oracle) | **26** | 19.7 % |
| **HARDWARE-BLOCKED** | **105** | 79.5 % |

The single pass is `falu2_ext.srcB_neg` — the row EXP-0194 recovered. It is no longer blocked:
`tools/agx-isa/validation.json` now carries `hardware-run` / target M4 / evidence
`["EXP-0138","EXP-0154","EXP-0194"]`. A diff of EXP-0194's snapshot against the live
`validation.json` shows **exactly one label changed since, and it is that one** — so the
population is otherwise unmoved, and this experiment's net contribution to the field count is
**zero**: the one-field move EXP-0194 earned stands, and nothing is added to it. **The
emittable-instruction headline does not move either** — `falu2_ext` is still blocked on
`srcA_size`, `ctrl` and `srcB_imm`.

---

## 1. The criterion, and the proof it is the same object

`EXP-0194/analysis/adjudicate2.py` was executed **unmodified**, twice, differing only in which
records it was fed. No second implementation of the gate exists in this experiment.

Run A, full record stream, all 566 blocked field-labels:

```
TOTAL blocked field-labels: 566
  DESK-PROMOTABLE    1
  AMBIGUOUS          46
  HARDWARE-BLOCKED   519
verdict differences vs EXP-0194's committed verdicts_final.json: 0   (all 566 rows)
```

The regenerated index is byte-identical to EXP-0194's (`cmp` clean; 727 files, 5 201 306 lines,
1 028 378 field-tagged records, 9 119 carrier groups) and the regenerated record stream carries
the same 263 687 records. **The criterion was not relaxed, tightened, or re-derived.**

### Why Run A is not the answer

Run A cannot distinguish "this row passes the gate" from "this row passes the gate *on the
evidence its label forgot to cite*" — the passing group could be a cited one. Run B feeds the
same unchanged script a stream restricted to records from non-cited experiments
(102 770 of 263 687 records, 132 rows). Restricting the input is not relaxing the criterion; it
is strictly less evidence, and it is the only way to answer the question that was asked.

Run A vs Run B over the 132: six rows are AMBIGUOUS only because of *cited* evidence
(`ibfins.b6hi`, `ibfins.b7`, `ibfins.b10`, `vtx_out_pos.dst`, `copysign.operands`,
`falu3_srcmod12.opsel`), which is why AMBIGUOUS falls 32 → 26 and BLOCKED rises 99 → 105.
No row moves the other way.

---

## 2. The one row that passes — full evidence

### `falu2_ext.srcB_neg` — *already recovered by EXP-0194; reproduced here independently*

`db.json` geometry: **`start = 43`, `width = 1`** → bit span 43..43.
Label at EXP-0194 snapshot time: `untested` / target G17P / evidence `["EXP-0154"]`, note
*"…2 values dispatched, 1 carrier(s) tested, 0 observations moved… Needs a second,
structurally different carrier."*
Uncited experiment holding the raw: **`EXP-0138-m4-emit-falu`**.

`python3 analysis/verify_recovery.py`, straight from raw, trusting no intermediate:

| raw file | line | bytes | bit 43 | outcome | match | expect_match | observed | oracle |
|---|---:|---|---:|---|---|---|---|---|
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run01/sweep.jsonl` | 1282 | `6901040501000080` | 0 | ok | True | True | `{w0:8.0, w4:26.0, w8:5.0}` | `{w0:8.0}` |
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run01/sweep.jsonl` | 1283 | `6901040501080080` | 1 | ok | True | True | `{w0:2.0, w4:26.0, w8:5.0}` | `{w0:2.0}` |
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run05/sweep.jsonl` | 1282 | `6901040501000080` | 0 | ok | True | True | `{w0:8.0, w4:26.0, w8:5.0}` | `{w0:8.0}` |
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run05/sweep.jsonl` | 1283 | `6901040501080080` | 1 | ok | True | True | `{w0:2.0, w4:26.0, w8:5.0}` | `{w0:2.0}` |
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run06/sweep.jsonl` | 1282 | `6901040501000080` | 0 | ok | True | True | `{w0:8.0, w4:26.0, w8:5.0}` | `{w0:8.0}` |
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run06/sweep.jsonl` | 1283 | `6901040501080080` | 1 | ok | True | True | `{w0:2.0, w4:26.0, w8:5.0}` | `{w0:2.0}` |

**Isolation proof.** `0x6901040501000080 XOR 0x6901040501080080` = one set bit, at **index 43**,
and the field's span is exactly `[43]`. `verify_recovery.py` prints
`distinct-outside-span = 1`, i.e. the two 8-byte strings are identical everywhere except that
one bit. Both encoded values 0 and 1 occur, so this is the **complete encodable range of a
1-bit field**, not a sample.

**Discriminating oracle (G7).** The host oracle predicted **8.0 for bit 43 = 0** and **2.0 for
bit 43 = 1**, *separately*, and hardware matched **both** — the semantics are the obvious one
(`5.0 + 3.0 = 8.0` vs `5.0 − 3.0 = 2.0`; the field negates srcB). Both cases carry
`expect_match: true`, which in EXP-0138's pre-registered oracle policy
(`harness/families.py` lines 21–30) means *a real pre-registered prediction*, not the
null-hypothesis "this field does not change the result" stand-in used for exploratory cases.
That distinction is the exact hazard that killed `tile_read.b7` in EXP-0194 §4, and it is
cleared here.

**Detection power.** The two sentinel words held in every case (`w4 = 26.0`, the untouched
control register; `w8 = 5.0`, a source register), so the arm could have seen a co-varying
artefact and did not.

**Cross-run (G8).** Identical value→payload map in **three** independent raw run directories
(`m4_20260828_run01`, `run05`, `run06`), zero faults, hangs, victims or sentinel trips.

**The cited arm, for contrast.** `EXP-0154-g17p-emit-alu` (`raw/g17p_20260829_run02` L16244–5,
`run03` L7188–9, `run04` L7188–9) runs the *same* one-bit diff — `09011c0501000082` vs
`09011c0501080082`, XOR = bit 43 only — on a G17P carrier, and the observed digest is
**bit-identical for both values**. That carrier cannot express the field. This is the
"0 observations moved" the label's note recorded, and it is why the honest reading is
**target M4, G17P still open** — which is what the merged label says.

**Worth, restated:** `falu2_ext` has four blocked fields (`srcA_size`, `ctrl`, `srcB_imm`,
`srcB_neg`); three remain blocked, so the instruction is still not emittable.

---

## 3. The 26 AMBIGUOUS rows — all stop at G7, and the NO is evidential, not clerical

Every one of the 26 has, in uncited committed raw, an isolated, injective, in-run-deterministic
per-value sweep. What none has is a **committed prediction that discriminates between field
values**.

`analysis/g7_diagnostics.py` measures this directly, per best carrier group
(`n_oracles` = distinct oracle payloads among *matching* cases):

| instruction | field | label | uncited exps | clean | enc vals | payloads | matching cases | distinct matched oracles | refusal on record |
|---|---|---|---|--:|--:|--:|--:|--:|---|
| `falu2i` | `ctrl_lo` | untested | EXP-0138, EXP-0160 | 192 | 64 | 3 | 12 | **1** | yes |
| `falu2i` | `mods` | untested | EXP-0138 | 768 | 256 | 4 | 48 | **1** | yes |
| `falu3` | `op` | untested | EXP-0138, EXP-0154 | 660 | 224 | 20 | 11 | **1** | yes |
| `falu3_ext` | `op` | untested | EXP-0138, EXP-0154 | 667 | 236 | 26 | 11 | **1** | yes |
| `falu2_ext` | `srcA_size` | untested | EXP-0138 | 6 | 2 | 2 | 3 | **1** | yes |
| `falu2_ext` | `ctrl` | untested | EXP-0138, EXP-0154 | 93 | 32 | 2 | 24 | **1** | yes |
| `falu2_ext` | `srcB_imm` | untested | EXP-0138 | 6 | 2 | 2 | 3 | **1** | yes |
| `iadd2` | `addsub` | untested | EXP-0139, EXP-0153, EXP-0154 | 6 | 2 | 2 | 3 | **1** | yes |
| `iadd2` | `srcB_imm` | untested | EXP-0139, EXP-0154 | 314 | 256 | 16 | 8 | **1** | yes |
| `imad` | `srcC_desc` | corpus-correlation | EXP-0139, EXP-0154, EXP-0160 | 376 | 192 | 14 | 8 | **1** | yes |
| `tex_deriv` | `dstsrc` | untested | EXP-0155 | 186 | 56 | 3 | 4 | **1** | yes |
| `ret` | `scoreboard` | corpus-correlation | EXP-0140, EXP-0156, EXP-0172 | 9 | 9 | 2 | **0** | **0** | yes |
| `unpack_convert` | `src` | untested | EXP-0168 | 32 | 16 | 8 | 8 | **1** | yes |
| `rt_query_traverse` | `opB` | untested | EXP-0184, EXP-0187 | 30 | 15 | 3 | 26 | **1** | yes |
| `atomic_tg` | `op_desc` | untested | EXP-0141 | 380 | 252 | 4 | 8 | **1** | yes |
| `mesh_out_src` | `sel` | tokenization-only | EXP-0157 | 256 | 256 | 2 | 256 | **1** | yes |
| `scoreboard_fence` | `scope` | tokenization-only | EXP-0147, EXP-0157 | 254 | 127 | 3 | **0** | **0** | yes |
| `scoreboard_fence` | `kind` | corpus-correlation | EXP-0147, EXP-0157 | 530 | 255 | 5 | **0** | **0** | — |
| `scoreboard_fence` | `mask` | tokenization-only | EXP-0147, EXP-0157 | 576 | 255 | 132 | **0** | **0** | — |
| `ibfins` | `srcdesc` | corpus-correlation | EXP-0139, EXP-0154 | 494 | 256 | 8 | 61 | **1** | — |
| `if_push_pred` | `level` | tokenization-only | EXP-0140, EXP-0156 | 124 | 92 | 2 | 16 | **1** | — |
| `falu2_srcmod10` | `opsel` | corpus-correlation | EXP-0138, EXP-0154 | 21 | 7 | 5 | 6 | **1** | — |
| `falu2_srcmod10` | `ctrl` | untested | EXP-0138 | 285 | 96 | 2 | 46 | **1** | — |
| `falu3_srcmod12` | `ctrl` | untested | EXP-0138 | 287 | 96 | 4 | 36 | **1** | — |
| `falu_srcmod12b` | `ext_srcmod` | tokenization-only | EXP-0138 | 3631 | 1208 | 16 | 3622 | **1** | — |
| `op04_len8` | `body` | tokenization-only | EXP-0157 | 142 | 142 | 4 | **0** | **0** | — |

**17 of the 26 already carry an explicit documented refusal** (in the label's own
`validation.json` note or in a committed `RESULTS.md`/`PROGRESS.md` line). Re-promoting those
would undo a considered ruling with strictly less analysis. The remaining 9 have no refusal on
record, and they are still refused here, on the same ground: no discriminating prediction.

### Falsifying the gate's own NO

A gate that says NO because a harness spelled its prediction key `predict` instead of `oracle`
would be broken in the direction that matters least to this brief but matters to the corpus.
`g7_diagnostics.py` re-ran G7's arithmetic against every alternative prediction key the raw
actually carries (`predict`, `predicts`) as well as the pre-registration flag `expect_match`:

```
AMBIGUOUS rows that WOULD pass G7 under some ALTERNATIVE prediction key: 0
```

In every case the alternative key is *also* constant across encoded values. Four of the 26 —
`scoreboard_fence.{kind,scope,mask}` and `op04_len8.body` — carry **no per-case oracle at all**
in their best carrier group, and those four plus `ret.scoreboard` (which does carry one) record
**zero matching cases**: their committed raw contains no successful prediction of any kind.

One row deserves separate mention. **`falu2_ext.srcA_size`** is the only AMBIGUOUS row whose
committed prediction *did* vary with the encoded value (2 distinct oracles across all clean
cases) — but it matched at **only one** of the two values. A prediction that discriminated and
was then contradicted by the hardware at the other value is a **refutation of the model**, not
evidence for it. It is correctly refused, and it is a caution against reading "the oracle
varies" as "the field is characterised".

Note also the shape of `EXP-0138`'s pre-registered oracle policy
(`harness/families.py` L21–30): for exploratory values the recorded prediction is deliberately
*the null hypothesis "this field does not change the result"*. Counting agreement with that as
"ran with the predicted effect" is precisely the did-nothing-reference trap
(EXP-0194 §4, `tile_read.b7`). Any future attempt to promote from these 26 must read
`expect_match`, not just `match`.

---

## 4. The 105 HARDWARE-BLOCKED rows

| stop gate | meaning | count |
|---|---|---:|
| **G4** | isolated per-value sweep exists, but the observable **never moved** | 51 |
| **G1** | fewer than 2 clean *executed* cases in any one uncited carrier group | 30 |
| **G5** | movement not reproducible per encoded value **within** the run | 17 |
| **G2b** | the harness's value→encoding map is **non-injective** (DEF-0166-1 aliasing) | 4 |
| **G2** | fewer than 2 distinct **encoded** values in any group | 3 |
| | **total** | **105** |

52 of the 105 additionally carry a documented refusal. By current label: 59 `untested`,
21 `single-template-inference`, 14 `tokenization-only`, 11 `corpus-correlation`.

The full 132-row table with per-row numbers is `analysis/row_table.md`; the machine-readable
form is `analysis/classification.json`.

---

## 5. The second method nominates 51 and the gate confirms 1 — this is the real finding

EXP-0194's `verdict_crosscheck.json` answers an independent question: does the **uncited**
experiment's own committed `analysis/field_verdicts*.json` already carry an emitter-grade
verdict (`hardware-run` or `isolated-byte-diff`) for this row? That signal is exactly how
`falu2_ext.srcB_neg` came to light, so it is the obvious place to look for more.

**It fires on 51 of the 132.** The gate passes **1**:

| gate verdict for the 51 nominated rows | count |
|---|---:|
| DESK-PROMOTABLE | 1 |
| AMBIGUOUS (stop G7) | 7 |
| HARDWARE-BLOCKED | 43 |

and of the 43 blocked, **29 stop at G4 — "the observable never moved"** (7 more stop at G5,
6 at G1, 1 at G2).

That is not a coincidence, and it is the most useful thing this experiment learned. Those 29
are **inert / reserved-bit claims**. **20 of the 29 say `inert` in their own committed
semantics**; the other 9 record only a dense `0..255` sweep in which every value came back `ok`
with a single observed result — the same inertness observation, unlabelled. Verbatim, from the
uncited experiments' own `analysis/field_verdicts.json`:

```
EXP-0154  "imad.b11"  : label isolated-byte-diff / G17P
                        semantics "inert ..."
                        range     "29 values tested (sampled over 8-bit domain)"
                        note      "carrier SYNTH+LIFTED:k_imad@imad[32:44]; outcomes {'ok': 29}"
EXP-0154  "ilogic.z6" : label isolated-byte-diff / G17P     (nominated too; stops at G5, not G4)
                        semantics "inert across the 254 SAMPLED values only; the full
                                   256-value range was NOT swept"
EXP-0141  "tg_addr_compute.b3" : label hardware-run / M4    -> gate stop G4,
                        "observable never moved across 256 encoded values"
EXP-0138  "copysign.operands"  : label hardware-run / M4,  semantics "ok@-5.0: 256 values (0..255)"
                        -> one observed result for the whole 8-bit field
```

The full G4 set of 29: `copysign.operands`, `cvt_f2i.b9`, `frag_color_store.store_mode`,
`frag_tile_setup.{sel,access,b5}`, `iadd2.srcB_reg_hi`, `ibfe.{b2_bit0,sign_ext}`,
`imad.{b1hi,b2_fmt,b11}`, `imageblock_store.b4`, `ishift.{src_cache,pad9}`, `iter.b9`,
`ray_move.{dst,src,b3}`, `ray_move_copy6.{dst,src}`, `ray_move_zero6.{dst,src,b3}`,
`tex_write.{amode,rsv11}`, `tg_addr_compute.{b3,b4,b5}`.

**This is where the corpus's own promotion rule and EXP-0194's gate genuinely part company, and
I am flagging it rather than acting on it.** For a bit that is *supposed* to be inert, "the
observable did not move" **is** the predicted effect, so a constant oracle is the correct
oracle and G4/G7 can never be satisfied by any amount of good data. EXP-0194's chain is
structurally incapable of passing an inert field. Its positive control already showed the
consequence — the chain refuses 95.4 % of the 543 fields already at emitter grade.

I was told to apply the criterion unchanged and to say so if I thought it was wrong. I do not
think it is wrong for *active* fields; I think it is **category-mismatched for inert ones** —
and `docs/isa/emit-worklist.md` line 7 agrees, since the project's own rule explicitly
contemplates promoting a never-moving field: *"a field that never moves is only promotable if
the carriers differ **in the dimension the field controls**. Two carriers identical in that
dimension are one carrier (EXP-0164; `iter_at.loc` read inert only because every carrier was
`samples=1`)."* That is the missing conjunct for all 29, and it is not a thing EXP-0194's chain
measures.

I am still not promoting any of the 29, because an inert-field promotion needs its own
criterion with its own falsifier that this experiment did not pre-register and cannot supply
from the desk. Minimally that criterion would have to demand, per row: a carrier proven **live**
in the dimension the field would control (a positive control that *does* move the observable),
a **swept** rather than sampled range, and cross-run agreement. On the corpus's own admission
several of the 29 already fail the second — `imad.b11` reports 29 of 256 values, and the
nominated-but-G5 `ilogic.z6` states outright that "the full 256-value range was NOT swept".
Two more cautions before anyone treats the 29 as low-hanging fruit: six of them
(`ray_move.{dst,src}`, `ray_move_copy6.{dst,src}`, `ray_move_zero6.{dst,src}`) are **register
descriptor / destination** fields, where an observable that does *not* move is far more likely
to mean the carrier never read the register the field selects than to mean the field is inert —
i.e. the arm lacked detection power; and the G4 verdict itself is evidence the arm's liveness
was never demonstrated. **Deciding this is an orchestrator policy call, not an audit finding.**
What this experiment establishes is only that the question is worth **29 rows across 15
instructions**, and that answering it "yes" by reflex would have been 29 promotions this gate
refuses.

---

## 6. Bounding EXP-0194's format blind spot

EXP-0194 §5.5 recorded that it only read `.jsonl` under `raw/`, so per-case evidence in another
format was invisible. `analysis/scan_nonjsonl_raw.py` walks **all 6 499**
`experiments/**/raw/**/*.json` files, recursing into nested structures, looking for objects that
carry `instr` + `field` + `bytes` (the per-case shape the gate needs):

```
blocked rows with per-case (instr,field,bytes) records in a .json raw file: 0
rows this adds to the uncited-raw population: 0
```

So for `.json` the blind spot is empty and **132 is the exact count, not a floor**. It remains
open in principle for `.hex` (10 820 files), `.txt` (1 552) and `.log` (1 002), which are not
per-case JSON records and cannot be adjudicated by a byte-field gate at all —
`rt_ray_mem.field_off` (EXP-0194 §6) is the live instance of that shape and is unchanged here.

---

## 7. How this method could have failed to say "no"

Stated so the next reader can attack it. The brief warned that twelve "checks that cannot come
out the other way" were found in this corpus this week; here is where mine could have been the
thirteenth.

1. **The whole experiment could have been a rubber stamp on Run A.** EXP-0194's chain already
   sees uncited raw — its carrier groups are keyed on the experiment — so re-running it and
   reporting the same 1 would have proved nothing about the *uncited* half. Run B (restricted
   stream) is what makes the claim falsifiable, and it did move six rows from AMBIGUOUS to
   BLOCKED, so the restriction is doing real work rather than being decorative.
2. **The 132 could have been defined so that it contained the answer.** The population is
   defined *before* any adjudication, purely by "raw exists in a directory the evidence list
   does not name", from EXP-0194's own snapshot, and it reproduces 566/79/487/220/132 by an
   independent script. It was not filtered by anything correlated with passing.
3. **I could have counted the already-promoted row as a find.** I nearly did: EXP-0194's
   `blocked_rows.json` snapshot still lists `falu2_ext.srcB_neg` as `untested`, so Run B reports
   it as a pass. Diffing the snapshot against the live `validation.json` shows the label was
   already merged (and that it is the *only* row changed since). The honest headline is
   therefore **zero new**, and this is the single place where an unattentive read of my own
   output would have manufactured a recovery.
4. **G7 could have been failing for clerical reasons.** Directly falsified in §3: no AMBIGUOUS
   row passes G7 under any alternative prediction key the raw carries. Had that returned a
   non-zero count, the correct move would have been to report a **schema** defect, not a
   promotion — reading a differently-named key is not the same as knowing it is a
   pre-registered prediction rather than a null-hypothesis stand-in, which is the trap that
   killed `tile_read.b7`.
5. **My "documented refusal" search can miss refusals, never invent them.** It is a keyword
   scan (`withheld`, `DECLINED`, `NOT PROMOTED`, `UNSTABLE`, `does not take it`, …) over
   `validation.json` notes plus committed `RESULTS.md`/`PROGRESS.md`. It found 69 of 132. A
   refusal phrased in words not on that list is missed, which biases toward *proposing* a row,
   not toward refusing it. Since nothing is proposed, the bias could not have fired — but it
   would matter to anyone using this list as a green light.
6. **I inherit every one of EXP-0194's seven stated limitations**, including the one it
   flagged against itself: **G8 compares only encoded values clean in every run**, dropping a
   value that faulted in one run instead of counting it as a disagreement. That is a check
   biased toward passing. It does not touch §2 (that arm has 6 records, all clean, none
   dropped), but a *new* candidate reaching G8 would have needed it re-examined first, and I
   did not fix it.
7. **The direction I could not test.** Everything above concerns false YES. The failure mode I
   *did* find is the opposite one — §5's 29 inert rows, which this gate can never pass by
   construction. I did not act on them, so this experiment cannot have over-promoted; but a
   reader should not read "105 HARDWARE-BLOCKED" as "105 rows needing device time". Some
   fraction of the 51 G4 rows need a **criterion**, not a GPU.
8. **`_instruction` pseudo-fields are excluded from the denominator** (79 of the 566), as in
   EXP-0194 bucket B. If one thinks an uncited experiment could settle an opcode-level claim,
   that is a different question with a different method, and it is not asked here.

---

## 8. What this changes

Nothing. No label, no `docs/` page, no `PROVENANCE.md` row, no file in `tools/agx-isa/` was
edited, and nothing was committed. The single-field move EXP-0194 earned stands; **this
experiment adds zero fields and zero instructions on top of it.**

The whole pipeline was re-run end to end from a clean scratch directory as a final check: the
index, the record stream and all eight committed output artefacts
(`uncited_rows.json`, `documented_refusals.json`, `verdicts_e0195_rerun.json`,
`verdicts_uncited_only.json`, `classification.json`, `g7_diagnostics.json`,
`nonjsonl_raw_rows.json`, `row_table.md`) came back **byte-identical**.

The one line of downstream work this does justify is procedural rather than evidential:
`EXP-0164/analysis/audit.py`'s `gather()` iterating `for eid in evidence` is a real defect, and
EXP-0194 proved it lost a promotable row. This experiment measures the blast radius of that
defect on the current corpus: **132 rows are in its shadow, and exactly 1 of them was
recoverable.** A citation-scoped audit is a weaker instrument than a corpus-scoped one, but on
this corpus, at this bar, the difference is worth one field.

---

## Appendix A — all 132 rows

Generated by `analysis/make_table.py` from `analysis/classification.json`. Verdict, stop gate
and counts are from **Run B** (uncited evidence only). `stop` is the furthest gate the best
uncited carrier group reached; `enc` is distinct **encoded** field values read out of `bytes` at
`db.json` geometry, not the harness's nominal values.

| # | instruction | field | current label | uncited raw in | verdict | stop | clean | enc | payloads | runs | refusal on record |
|--:|---|---|---|---|---|---|--:|--:|--:|--:|---|
| 1 | `falu2_ext` | `srcB_neg` | untested | EXP-0138 | **RECOVERED** | PASS | 6 | 2 | 2 | 3 | - |
| 2 | `atomic_tg` | `op_desc` | untested | EXP-0141 | **AMBIG** | G7 | 380 | 252 | 4 | - | yes |
| 3 | `falu2_ext` | `ctrl` | untested | EXP-0138,EXP-0154 | **AMBIG** | G7 | 93 | 32 | 2 | - | yes |
| 4 | `falu2_ext` | `srcA_size` | untested | EXP-0138 | **AMBIG** | G7 | 6 | 2 | 2 | - | yes |
| 5 | `falu2_ext` | `srcB_imm` | untested | EXP-0138 | **AMBIG** | G7 | 6 | 2 | 2 | - | yes |
| 6 | `falu2_srcmod10` | `ctrl` | untested | EXP-0138 | **AMBIG** | G7 | 285 | 96 | 2 | - | - |
| 7 | `falu2_srcmod10` | `opsel` | corpus-correlation | EXP-0138,EXP-0154 | **AMBIG** | G7 | 21 | 7 | 5 | - | - |
| 8 | `falu2i` | `ctrl_lo` | untested | EXP-0138,EXP-0160 | **AMBIG** | G7 | 192 | 64 | 3 | - | yes |
| 9 | `falu2i` | `mods` | untested | EXP-0138 | **AMBIG** | G7 | 768 | 256 | 4 | - | yes |
| 10 | `falu3` | `op` | untested | EXP-0138,EXP-0154 | **AMBIG** | G7 | 660 | 224 | 20 | - | yes |
| 11 | `falu3_ext` | `op` | untested | EXP-0138,EXP-0154 | **AMBIG** | G7 | 667 | 236 | 26 | - | yes |
| 12 | `falu3_srcmod12` | `ctrl` | untested | EXP-0138 | **AMBIG** | G7 | 287 | 96 | 4 | - | - |
| 13 | `falu_srcmod12b` | `ext_srcmod` | tokenization-only | EXP-0138 | **AMBIG** | G7 | 3631 | 1208 | 16 | - | - |
| 14 | `iadd2` | `addsub` | untested | EXP-0139,EXP-0153,EXP-0154 | **AMBIG** | G7 | 6 | 2 | 2 | - | yes |
| 15 | `iadd2` | `srcB_imm` | untested | EXP-0139,EXP-0154 | **AMBIG** | G7 | 314 | 256 | 16 | - | yes |
| 16 | `ibfins` | `srcdesc` | corpus-correlation | EXP-0139,EXP-0154 | **AMBIG** | G7 | 494 | 256 | 8 | - | - |
| 17 | `if_push_pred` | `level` | tokenization-only | EXP-0140,EXP-0156 | **AMBIG** | G7 | 124 | 92 | 2 | - | - |
| 18 | `imad` | `srcC_desc` | corpus-correlation | EXP-0139,EXP-0154,EXP-0160 | **AMBIG** | G7 | 376 | 192 | 14 | - | yes |
| 19 | `mesh_out_src` | `sel` | tokenization-only | EXP-0157 | **AMBIG** | G7 | 256 | 256 | 2 | - | yes |
| 20 | `op04_len8` | `body` | tokenization-only | EXP-0157 | **AMBIG** | G7 | 142 | 142 | 4 | - | - |
| 21 | `ret` | `scoreboard` | corpus-correlation | EXP-0140,EXP-0156,EXP-0172 | **AMBIG** | G7 | 9 | 9 | 2 | - | yes |
| 22 | `rt_query_traverse` | `opB` | untested | EXP-0184,EXP-0187 | **AMBIG** | G7 | 30 | 15 | 3 | - | yes |
| 23 | `scoreboard_fence` | `kind` | corpus-correlation | EXP-0147,EXP-0157 | **AMBIG** | G7 | 530 | 255 | 5 | - | - |
| 24 | `scoreboard_fence` | `mask` | tokenization-only | EXP-0147,EXP-0157 | **AMBIG** | G7 | 576 | 255 | 132 | - | - |
| 25 | `scoreboard_fence` | `scope` | tokenization-only | EXP-0147,EXP-0157 | **AMBIG** | G7 | 254 | 127 | 3 | - | yes |
| 26 | `tex_deriv` | `dstsrc` | untested | EXP-0155 | **AMBIG** | G7 | 186 | 56 | 3 | - | yes |
| 27 | `unpack_convert` | `src` | untested | EXP-0168 | **AMBIG** | G7 | 32 | 16 | 8 | - | yes |
| 28 | `ibfins` | `b10` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 29 | `ibfins` | `b6hi` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 30 | `ibfins` | `b7` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 31 | `ibfins` | `cache` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 32 | `ibfins` | `mask_hi` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 33 | `ibfins` | `mask_imm` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 34 | `ibitcount` | `cache` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 35 | `ibitcount` | `dst` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 36 | `icmp_pred` | `cond` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 37 | `icmp_pred` | `opclass` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 38 | `icmpsel` | `cache` | tokenization-only | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 39 | `icmpsel` | `cmpmode` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 40 | `icmpsel` | `cond` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 41 | `icmpsel` | `neg_lo` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 42 | `icmpsel` | `sel_marker` | tokenization-only | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 43 | `icmpsel` | `sel_operand` | tokenization-only | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 44 | `icmpsel` | `srcA` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 45 | `icmpsel` | `tail` | tokenization-only | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 46 | `imad` | `b2_bit0` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 47 | `imad` | `store_en` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 48 | `isel10_c` | `cc` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 49 | `isel8` | `cmpA` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 50 | `isel8` | `cmpB` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | yes |
| 51 | `isel_reg` | `cmpB` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 52 | `isel_reg` | `cmp_mode` | untested | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 53 | `isel_reg8` | `cc` | corpus-correlation | EXP-0139 | **BLOCKED** | G1 | - | - | - | - | - |
| 54 | `mask_op` | `mask_bank` | corpus-correlation | EXP-0156 | **BLOCKED** | G1 | - | - | - | - | - |
| 55 | `mask_op` | `scope_kind` | single-template-inference | EXP-0156 | **BLOCKED** | G1 | - | - | - | - | - |
| 56 | `packed_half2_hi` | `srcA` | untested | EXP-0144 | **BLOCKED** | G1 | - | - | - | - | yes |
| 57 | `packed_half2_hi` | `srcB` | untested | EXP-0144 | **BLOCKED** | G1 | - | - | - | - | yes |
| 58 | `call` | `tail` | untested | EXP-0189 | **BLOCKED** | G2 | 512 | 1 | - | - | yes |
| 59 | `half_alu_fma12` | `dst` | untested | EXP-0138,EXP-0169 | **BLOCKED** | G2 | 768 | 1 | - | - | yes |
| 60 | `isel_reg` | `cc` | corpus-correlation | EXP-0139,EXP-0154 | **BLOCKED** | G2 | 767 | 1 | - | - | - |
| 61 | `falu3_srcmod12` | `opsel` | untested | EXP-0138 | **BLOCKED** | G2b | 22 | 4 | - | - | yes |
| 62 | `half_alu_fma12` | `ext` | untested | EXP-0169 | **BLOCKED** | G2b | 4096 | 2041 | - | - | - |
| 63 | `irotate` | `operands` | untested | EXP-0154 | **BLOCKED** | G2b | 2432 | 1212 | - | - | yes |
| 64 | `tile_read` | `tail` | untested | EXP-0147 | **BLOCKED** | G2b | 1928 | 990 | - | - | yes |
| 65 | `compute_fence_scoped` | `kind` | tokenization-only | EXP-0147 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 66 | `compute_fence_scoped` | `scope` | tokenization-only | EXP-0147 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 67 | `copysign` | `operands` | untested | EXP-0138,EXP-0168 | **BLOCKED** | G4 | 768 | 256 | 1 | - | yes |
| 68 | `cvt_f2i` | `b9` | single-template-inference | EXP-0144,EXP-0168 | **BLOCKED** | G4 | 512 | 256 | 1 | - | yes |
| 69 | `frag_color_store` | `store_mode` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 512 | 256 | 1 | - | yes |
| 70 | `frag_tile_setup` | `access` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 71 | `frag_tile_setup` | `b5` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 72 | `frag_tile_setup` | `sel` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 73 | `get_sr` | `dst_hi` | untested | EXP-0169 | **BLOCKED** | G4 | 16 | 8 | 1 | - | yes |
| 74 | `get_sr` | `form` | untested | EXP-0140,EXP-0168,EXP-0169 | **BLOCKED** | G4 | 6 | 2 | 1 | - | yes |
| 75 | `iadd2` | `srcB_reg_hi` | untested | EXP-0139,EXP-0154 | **BLOCKED** | G4 | 161 | 113 | 1 | - | yes |
| 76 | `ibfe` | `b2_bit0` | single-template-inference | EXP-0139,EXP-0154,EXP-0161 | **BLOCKED** | G4 | 4 | 2 | 1 | - | yes |
| 77 | `ibfe` | `sign_ext` | single-template-inference | EXP-0139,EXP-0154,EXP-0161 | **BLOCKED** | G4 | 4 | 2 | 1 | - | yes |
| 78 | `imad` | `b11` | untested | EXP-0154 | **BLOCKED** | G4 | 58 | 29 | 1 | - | yes |
| 79 | `imad` | `b1hi` | untested | EXP-0154 | **BLOCKED** | G4 | 52 | 26 | 1 | - | yes |
| 80 | `imad` | `b2_fmt` | untested | EXP-0154 | **BLOCKED** | G4 | 46 | 23 | 1 | - | yes |
| 81 | `imageblock_store` | `b4` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 768 | 256 | 1 | - | yes |
| 82 | `ishift` | `pad9` | untested | EXP-0154 | **BLOCKED** | G4 | 58 | 29 | 1 | - | yes |
| 83 | `ishift` | `src_cache` | untested | EXP-0154 | **BLOCKED** | G4 | 58 | 29 | 1 | - | yes |
| 84 | `iter` | `b9` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 768 | 256 | 1 | - | yes |
| 85 | `jump` | `branch_ctrl` | untested | EXP-0140 | **BLOCKED** | G4 | 256 | 256 | 1 | - | yes |
| 86 | `jump_cond` | `cf_scope` | untested | EXP-0140 | **BLOCKED** | G4 | 512 | 256 | 1 | - | yes |
| 87 | `jump_cond` | `offset` | untested | EXP-0140 | **BLOCKED** | G4 | 36 | 36 | 1 | - | yes |
| 88 | `jump_cond` | `reserved` | untested | EXP-0140 | **BLOCKED** | G4 | 512 | 256 | 1 | - | yes |
| 89 | `n4_cf_word` | `b3` | tokenization-only | EXP-0172 | **BLOCKED** | G4 | 512 | 256 | 1 | - | yes |
| 90 | `op04_len8` | `dst` | tokenization-only | EXP-0157 | **BLOCKED** | G4 | 15 | 15 | 1 | - | - |
| 91 | `op04_len8` | `mode` | tokenization-only | EXP-0157 | **BLOCKED** | G4 | 255 | 255 | 1 | - | - |
| 92 | `pop_reconverge` | `reserved` | untested | EXP-0140 | **BLOCKED** | G4 | 34 | 34 | 1 | - | yes |
| 93 | `ray_move` | `b3` | untested | EXP-0157 | **BLOCKED** | G4 | 510 | 255 | 1 | - | yes |
| 94 | `ray_move` | `dst` | untested | EXP-0157 | **BLOCKED** | G4 | 30 | 15 | 1 | - | - |
| 95 | `ray_move` | `src` | untested | EXP-0157 | **BLOCKED** | G4 | 510 | 255 | 1 | - | - |
| 96 | `ray_move_copy6` | `dst` | untested | EXP-0157 | **BLOCKED** | G4 | 49 | 15 | 1 | - | - |
| 97 | `ray_move_copy6` | `src` | untested | EXP-0157 | **BLOCKED** | G4 | 535 | 255 | 1 | - | - |
| 98 | `ray_move_zero6` | `b3` | untested | EXP-0157 | **BLOCKED** | G4 | 510 | 255 | 1 | - | - |
| 99 | `ray_move_zero6` | `dst` | untested | EXP-0157 | **BLOCKED** | G4 | 49 | 15 | 1 | - | - |
| 100 | `ray_move_zero6` | `src` | untested | EXP-0157 | **BLOCKED** | G4 | 535 | 255 | 1 | - | - |
| 101 | `simd_ballot` | `cache` | single-template-inference | EXP-0155,EXP-0163 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 102 | `simd_shuffle` | `cache` | single-template-inference | EXP-0155,EXP-0163 | **BLOCKED** | G4 | 4 | 2 | 1 | - | - |
| 103 | `tex_coord_setup` | `b9` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 1024 | 256 | 1 | - | - |
| 104 | `tex_write` | `amode` | untested | EXP-0155 | **BLOCKED** | G4 | 768 | 256 | 1 | - | yes |
| 105 | `tex_write` | `rsv11` | untested | EXP-0155 | **BLOCKED** | G4 | 768 | 256 | 1 | - | yes |
| 106 | `tg_addr_compute` | `b3` | untested | EXP-0141 | **BLOCKED** | G4 | 514 | 256 | 1 | - | yes |
| 107 | `tg_addr_compute` | `b4` | untested | EXP-0141 | **BLOCKED** | G4 | 514 | 256 | 1 | - | yes |
| 108 | `tg_addr_compute` | `b5` | untested | EXP-0141 | **BLOCKED** | G4 | 514 | 256 | 1 | - | yes |
| 109 | `tile_read` | `b2` | untested | EXP-0147 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 110 | `tile_read` | `b4` | untested | EXP-0147 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 111 | `tile_read_mrt` | `b4` | untested | EXP-0147 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 112 | `vary_store` | `b7` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 113 | `vary_store` | `hint2` | single-template-inference | EXP-0155 | **BLOCKED** | G4 | 512 | 256 | 1 | - | - |
| 114 | `vtx_out_pos` | `dst` | untested | EXP-0147 | **BLOCKED** | G4 | 32 | 16 | 1 | - | yes |
| 115 | `vtx_out_pos` | `slot` | single-template-inference | EXP-0147 | **BLOCKED** | G4 | 512 | 256 | 1 | - | yes |
| 116 | `compute_fence_scoped` | `mask` | tokenization-only | EXP-0147 | **BLOCKED** | G5 | 512 | 256 | 9 | - | - |
| 117 | `fspecial_est` | `srcA` | untested | EXP-0138,EXP-0154,EXP-0161 | **BLOCKED** | G5 | 763 | 256 | 2 | - | yes |
| 118 | `iadd2` | `b2_fmt` | single-template-inference | EXP-0139,EXP-0146,EXP-0154 | **BLOCKED** | G5 | 190 | 64 | 2 | - | yes |
| 119 | `if_push` | `scope` | single-template-inference | EXP-0140,EXP-0168 | **BLOCKED** | G5 | 740 | 256 | 2 | - | yes |
| 120 | `ilogic` | `z6` | single-template-inference | EXP-0146,EXP-0154 | **BLOCKED** | G5 | 768 | 256 | 2 | - | yes |
| 121 | `ilogic` | `z8` | single-template-inference | EXP-0146,EXP-0154 | **BLOCKED** | G5 | 768 | 256 | 2 | - | yes |
| 122 | `ilogic` | `z9` | single-template-inference | EXP-0146,EXP-0154 | **BLOCKED** | G5 | 768 | 256 | 2 | - | yes |
| 123 | `imageblock_store` | `src` | untested | EXP-0155 | **BLOCKED** | G5 | 738 | 246 | 24 | - | yes |
| 124 | `n2_op10` | `opdesc` | tokenization-only | EXP-0146 | **BLOCKED** | G5 | 757 | 256 | 15 | - | - |
| 125 | `n2_op10` | `opsel` | tokenization-only | EXP-0146 | **BLOCKED** | G5 | 452 | 235 | 14 | - | - |
| 126 | `n2_op10` | `src` | tokenization-only | EXP-0146 | **BLOCKED** | G5 | 763 | 256 | 5 | - | - |
| 127 | `n2_op8` | `dst` | tokenization-only | EXP-0146 | **BLOCKED** | G5 | 41 | 16 | 6 | - | - |
| 128 | `shift_amt_move` | `src_flag` | untested | EXP-0146,EXP-0154 | **BLOCKED** | G5 | 6 | 2 | 2 | - | yes |
| 129 | `tex_coord_setup` | `b1` | untested | EXP-0155 | **BLOCKED** | G5 | 1020 | 255 | 2 | - | - |
| 130 | `tex_coord_setup` | `form` | corpus-correlation | EXP-0155 | **BLOCKED** | G5 | 1016 | 256 | 2 | - | - |
| 131 | `tex_coord_setup` | `srcA` | corpus-correlation | EXP-0155 | **BLOCKED** | G5 | 1024 | 256 | 2 | - | - |
| 132 | `tile_read` | `b7` | untested | EXP-0147 | **BLOCKED** | G5 | 384 | 222 | 44 | - | - |

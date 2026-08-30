# EXP-0194 — RESULTS

## 1. The three counts

Of the **566** blocked field-labels that hold back the 134 non-emittable instructions:

| bucket | count | share |
|---|---:|---:|
| **DESK-PROMOTABLE** | **1** | 0.2 % |
| **AMBIGUOUS** | **46** | 8.1 % |
| **HARDWARE-BLOCKED** | **519** | 91.7 % |

The one desk-promotable row is on **M4/G16G**, not the G17P closure target, and its
instruction stays blocked on three other fields. **The practical answer to "can this move the
headline without device time" is: no.**

### Why the 519 are hardware-blocked

| | reason | count |
|---|---|---:|
| A | no per-case raw record for this field anywhere in `experiments/**/raw/**.jsonl` | 267 |
| B | `_instruction` pseudo-field — the open question is whether the opcode/match bits do what the descriptor claims; a field byte-diff cannot answer it | 79 |
| C | an isolated per-value sweep exists but **the observable never moved** | 96 |
| D | raw exists but fewer than 2 clean *executed* cases in any one carrier group | 41 |
| F | movement not reproducible per encoded value within the run | 24 |
| E | clean cases exist but fewer than 2 distinct **encoded** values in any group | 8 |
| H | the harness's value→encoding map is non-injective (DEF-0166-1) | 4 |
| | **total** | **519** |

By current label: 225 `untested`, 135 `corpus-correlation`, 129 `tokenization-only`,
30 `single-template-inference` — i.e. **every one of the 30 `single-template-inference`
rows and 135 of the 141 `corpus-correlation` rows are hardware-blocked**, which is what one
would expect: those labels mean nothing was executed.

## 2. The one DESK-PROMOTABLE row

### `falu2_ext.srcB_neg`

Current label: `untested` / target `G17P` / evidence `["EXP-0154"]`, note *"EXP-0164 withheld:
2 values dispatched, 1 carrier(s) tested, **0 observations moved**. Never moved anything on the
ONE carrier tried… Needs a second, structurally different carrier."*

**That second carrier is already committed, in an experiment the label does not cite.**
Reproduce with `python3 analysis/verify_survivor.py`:

| raw file | line | bytes | bit 43 | outcome | match | observed | oracle |
|---|---:|---|---:|---|---|---|---|
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run01/sweep.jsonl` | 1282 | `6901040501000080` | 0 | ok | true | `w0=8.0` | `w0=8.0` |
| `EXP-0138-m4-emit-falu/raw/m4_20260828_run01/sweep.jsonl` | 1283 | `6901040501080080` | 1 | ok | true | `w0=2.0` | `w0=2.0` |
| `…/m4_20260828_run05/sweep.jsonl` | 1282–1283 | (identical pair) | 0,1 | ok | true | `8.0`, `2.0` | `8.0`, `2.0` |
| `…/m4_20260828_run06/sweep.jsonl` | 1282–1283 | (identical pair) | 0,1 | ok | true | `8.0`, `2.0` | `8.0`, `2.0` |

Against the gate chain:

- **G1** 6 clean executed cases, zero faults/hangs/victims/sentinel trips anywhere in the arm.
- **G2/G2b** 2 encoded values, injective (2 values → 2 byte strings).
- **G3** the two 8-byte strings differ in exactly one bit — bit 43, which is `srcB_neg`
  (`db.json` `start=43, width=1`). `verify_survivor.py` prints "distinct *everything except
  bit 43* values = 1".
- **G4** the observable moved: `w0` 8.0 → 2.0. The two sentinel words (`w4=26.0`, `w8=5.0`)
  held, so the arm had detection power and the move is not a co-varying artefact.
- **G5/G8** identical in all **three** runs, per value.
- **G7** the host oracle **discriminated**: it predicted 8.0 for bit 43 = 0 and 2.0 for
  bit 43 = 1, and hardware matched both. This is the "ran with the predicted effect" clause,
  and it is a prediction *about the field*, not about the instruction.
- 1 bit wide, both values run ⇒ this is the **complete encodable range**.

**EXP-0138's own committed `analysis/field_verdicts.json` already says so**, independently of
anything in this experiment:

```
"falu2_ext.srcB_neg": {"label": "hardware-run", "range": "0..1 dense (all 2 values)",
                       "target": "M4", "evidence": ["EXP-0138"],
                       "semantics": "ok@8.0: 0; ok@2.0: 1",
                       "deterministic": true, "live": true, "distinct_results": 2,
                       "cross_run": {"m4_20260828_run05": {"cases_shared": 2,
                                     "cases_agreeing": 2, "identical": true}}}
```

**How the corpus lost it, precisely.** `EXP-0164/analysis/audit.py`'s `gather()` iterates
`for eid in evidence` — it only reads the raw of the experiments **the label already cites**.
`falu2_ext.srcB_neg`'s label cited `EXP-0154` alone, so EXP-0164 audited EXP-0154's arm
(2 values, 1 carrier, 0 moved) and withheld. Its own committed index *does* contain the
EXP-0138 arm, with `moved: 1`, `n_contam: 0`, `n_within_run_unstable: 0`, in all three runs —
it was indexed and then never consulted:

```
EXP-0164/work/raw_index.json.gz → index["EXP-0138-m4-emit-falu"]["falu2_ext.srcB_neg"]
  m4_20260828_run01/05/06 : {"attribution": ["bit-exact"], "n_values": 2, "moved": 1,
                             "n_cases": 2, "n_contam": 0, "n_within_run_unstable": 0}
```

**This is a citation-scoped audit: it can confirm or refute the evidence a label already
names, but it can never discover evidence in an experiment the label forgot to cite.** The
same displacement hit `falu2_ext.srcA_size` and `.srcB_imm` — both are EXP-0138
`hardware-run`/M4 in that experiment's own verdicts, both now read `untested`/G17P citing
EXP-0154 with the same "0 observations moved" note. They land in AMBIGUOUS rather than
DESK-PROMOTABLE only because their EXP-0138 oracle did not discriminate (see §3).

### What the promotion is actually worth

- The evidence is **M4 / G16G**. `docs/evidence-classification.md` §3.2 says committed M4
  evidence stays valid on its own target and is not retracted, but is **not** relabelled A18;
  and `CLAUDE.md` says closure is measured against full G17P. On G17P this field has been
  tried on exactly one carrier, which could not express it. So the honest promotion is
  `isolated-byte-diff` (conservative floor) or `hardware-run` (EXP-0138's own verdict),
  **target M4**, evidence `["EXP-0138"]` added — and G17P stays open.
- `falu2_ext` has **four** blocked fields (`srcA_size`, `ctrl`, `srcB_imm`, `srcB_neg`).
  Promoting one does not make the instruction emittable. **The 32/166 headline does not
  move. The field count moves by exactly one, 543 → 544.**

## 3. The 46 AMBIGUOUS rows — what is missing

All 46 fail at the **same** gate, G7, and only G7. Each has, in committed raw, an isolated,
injective, deterministic, cross-run-reproduced per-value sweep whose observable moved. What
none of them has is **a committed prediction that discriminates between field values**: the
per-case `oracle` is constant while the field varies, so the only recorded prediction is about
the instruction, not the field. Fitting a value→behaviour model to that data now would be
fitting to the same observations it would be validated against — `corpus-correlation` strength
by construction, not `isolated-byte-diff`.

31 of the 46 additionally carry an **explicit documented refusal** in their current
`validation.json` note (EXP-0164 "withheld", EXP-0189 "UNSTABLE", EXP-0169 "disagreed with the
HOST-COMPUTED oracle" / "no (arm,carrier) passed its liveness ladder", EXP-0179 "DECLINED",
EXP-0141 "NOT PROMOTED"). Those are settled; re-promoting them would undo a considered ruling
with strictly less analysis.

The remaining **15** have no documented refusal, and are the only rows where a *new* desk
experiment could plausibly change something — by supplying a discriminating oracle offline,
where the semantics are strong enough to predict from an independent source (`db.json` prose,
a sibling descriptor) rather than from the sweep itself:

| instruction | field | current | evidence | best committed group |
|---|---|---|---|---|
| `imad` | `srcC_desc` | `corpus-correlation`/M4 | EXP-M4-13 | EXP-0154 (non-cited), 192 encoded values, 14 payloads |
| `ibfins` | `b6hi` | `untested`/G17P | EXP-0154 | EXP-0154, 128 values, 5 payloads |
| `ibfins` | `b7` | `untested`/G17P | EXP-0154 | EXP-0154, 192 values, 33 payloads |
| `ibfins` | `b10` | `untested`/G17P | EXP-0154 | EXP-0154, 256 values, 8 payloads |
| `ibfins` | `srcdesc` | `corpus-correlation`/M4 | EXP-M4-13 | EXP-0154 (non-cited), 256 values, 8 payloads |
| `scoreboard_fence` | `kind` | `corpus-correlation`/A18 | RT-ISA-FIX | EXP-0157 (non-cited), 255 values, 5 payloads |
| `scoreboard_fence` | `scope` | `tokenization-only`/M4+A18 | EXP-0036, EXP-M4-12/13 | EXP-0157 (non-cited), 127 values, 3 payloads |
| `scoreboard_fence` | `mask` | `tokenization-only`/M4+A18 | EXP-0036, EXP-M4-12/13 | EXP-0157 (non-cited), 255 values, **132** payloads |
| `if_push_pred` | `level` | `tokenization-only`/M4+A18 | EXP-0036, EXP-M4-12/13 | EXP-0140 (non-cited), 92 values, 2 payloads |
| `falu2_srcmod10` | `opsel` | `corpus-correlation`/M4 | EXP-M4-13 | EXP-0154 (non-cited), 2 payloads |
| `falu2_srcmod10` | `ctrl` | `untested`/G17P | EXP-0154 | EXP-0138 (non-cited), 96 values, 2 payloads |
| `falu3_srcmod12` | `opsel` | `untested`/G17P | EXP-0154 | EXP-0154, 4 encoded values |
| `falu3_srcmod12` | `ctrl` | `untested`/G17P | EXP-0154 | EXP-0138 (non-cited), 96 values, 4 payloads |
| `falu_srcmod12b` | `ext_srcmod` | `tokenization-only`/M4+A18 | EXP-0036, EXP-M4-12/13 | EXP-0138 (non-cited), 1208 values, 16 payloads |
| `op04_len8` | `body` | `tokenization-only`/A18 | EXP-M4-13/14 | EXP-0157 (non-cited), 142 values, 4 payloads |

Three caveats on that table: `scoreboard_fence.mask` and `op04_len8.body` (and
`mesh_out_src.sel`, which carries a refusal) additionally fail the cross-run gate G8, so they
are weaker than the other twelve; `falu_srcmod12b` and `op04_len8` are already `emit_unsafe` in
`db.json`, and `op04_len8` additionally carries an EMITTABLE VETO — a field promotion there
buys nothing. And 11 of the 15 have their best evidence in an experiment their label **does
not cite**, the same blind spot §2 describes.

## 4. Five candidates that did not survive — and how each was caught

A first pass (`analysis/adjudicate.py`, since deleted) with gates G1–G5 and a weaker G7
returned **five**. All five were false, in exactly the three ways the brief warned about. They
are recorded here because the way each failed is the reusable part.

| candidate | first-pass reason | what actually killed it |
|---|---|---|
| `tile_read.b7` | 256 values, 43 payloads, 2 oracles, 4 matches | **The second "oracle" is the classifier's did-nothing reference, written after the observation.** All four matching cases share one constant oracle — a prediction about `tile_read`, not about `b7`. And `EXP-0178/RESULTS.md` line 395 already adjudicated it: *"correct at exactly those four; movement does not reproduce (91.0 % agreement, 23 disagreeing values)"* → `untested`. My single-run view could not see that. → gates G7 and G8. |
| `tile_read.tail` | 1053 values, 8 payloads | same; EXP-0178 records 91.7 % cross-run agreement and refuses it. |
| `falu2_srcmod10.opsel` | 3 values, 2 payloads, 2 oracles | **The sweep is aliased.** `db.json` pins bits 17 and 18 of this descriptor by `match`, and the assembler cannot clear them, so nominal values 0 and 4 assemble to the *identical* byte string `69010405…`. The harness computed its oracle from the value it *meant* to encode, so two "different" cases ran the same program. → gate G2b. |
| `falu3_srcmod12.opsel` | 4 values, 3 payloads, 3 oracles | same aliasing (bit 17 pinned). Nominal 4 and 6 both assemble `…0106…`, observed 22.0 in both, scored `wrong_value` at 4 and `ok` at 6 purely by the harness's bookkeeping. Also: `EXP-0138/RESULTS.md` §8 lists this field **by name** among seven it deliberately declined to promote from the run05+run06 pair — "*This experiment does not take it*". Promoting it from run05 alone would re-litigate a documented refusal with less data. |
| `falu2_ext.srcB_neg` | — | survived all eight gates, and is the row in §2. |

## 5. How this method could have failed to come out the other way

Stated so the next reader can attack it.

1. **The gate is far stricter than the project's own promotion rule, and that is not neutral.**
   Positive control (`analysis/control.py` + `control_verdicts.json`): the identical chain run
   over the **543 fields already at emitter grade** passes only **25** (4.6 %), calls 313
   AMBIGUOUS and 205 HARDWARE-BLOCKED. So the chain *can* say yes — but it would refuse 95 %
   of the corpus's existing emitter-grade labels. **"1" is a floor under a stricter-than-project
   bar, not a proof that exactly one row could ever be promoted.**
2. **The looser, project-stated bar gives 44, and that number is wrong.** Dropping G7 —
   leaving movement + isolation + injectivity + cross-run agreement, which *is* what
   `emit-worklist.md` states as the promotion rule — yields **44** DESK-PROMOTABLE
   (`analysis/verdicts_loose.json`). **31 of those 44 carry an explicit documented refusal**
   from EXP-0164 / EXP-0189 / EXP-0169 / EXP-0179 / EXP-0141 in their current label — the same
   31 as in §3. The loose gate re-promotes rows those audits demoted for a stated reason, i.e.
   it reproduces precisely the error they corrected. This is the strongest evidence
   that G7 is doing real work rather than merely being conservative.
3. **G8's reproducibility check is biased toward passing, and I did not fix it.** It compares
   only encoded values that were *clean in every run*. A value clean in run A and faulting in
   run B is dropped from the comparison instead of counted as a disagreement — a "check that
   cannot come out the other way" of exactly the kind this corpus keeps finding. It does not
   touch the §2 result (that arm has 6 records, all clean, no dropped case), but it inflates
   the loose-bar 44 and probably the control's 25.
4. **A field with no `bytes` column is invisible to me.** G2/G3 read the encoding out of
   `bytes`. Groups that record no byte string are dropped at G1/G2 and land in
   HARDWARE-BLOCKED. EXP-0164's collector handles that case with a label-level fallback; mine
   does not. Reason buckets D (41) and E (8) may therefore be slightly overstated.
5. **I only read `.jsonl` under `raw/`.** Per-case evidence stored as `.json`, `.csv`, `.hex`
   or `.txt` is not in the index. `rt_ray_mem.field_off` is a live instance — see §6.
6. **"Movement" is payload-hash inequality after stripping a fixed volatile-key list**
   (`gputime_ns`, timestamps, retry counters). A per-dispatch varying key I failed to list
   would manufacture movement everywhere. The 96 rows in bucket C show the stripping is not
   over-aggressive in the other direction: those genuinely never moved.
7. **I did not re-verify the six-gate closure rules.** DESK-PROMOTABLE here means only "the
   label could be raised from committed data". Whether the *instruction* then clears
   `docs/P0-P1-CLOSURE.md` is a separate question, and for `falu2_ext` the answer is no.

## 6. One row that is half-derivable, and is not counted

`rt_ray_mem.field_off` — current `corpus-correlation`/M4 citing EXP-M4-13.
`EXP-0157/analysis/field_verdicts.json` carries `isolated-byte-diff`/G17P for it, from
differential compilation of three of our own `intersection_query<triangle_data>` kernels that
differ only in the getter: byte `+10` takes `0xc4` / `0xc6` / `0xc8`, everything else identical.
That upgrade was never merged into `validation.json`.

**The byte-diff half is committed and desk-verifiable right now** —
`EXP-0157/raw/g17p_census01/getter_diff.json` lists the 14 differing offsets and the three
values, beside the three committed `.hex` files. **The execution half is not.** The verdict's
note asserts *"Each of the three programs was executed and returned its own host-computed
oracle exactly"*, but no committed raw in that experiment records those three dispatches:
`getter_diff.json` is a static diff, `provocation_census.json` is a static tokenization census,
and a grep for `baryx` across `EXP-0157/raw/` returns only those two files plus source-hash
manifests. The verdict itself is hand-written into `analysis/merge.py` with
`captures_agreeing: 1`.

So it is **AMBIGUOUS in substance** — what is missing is the raw record of the three
executions — but it is not in the §3 count because it never reaches my gate chain: its
evidence is not `.jsonl` per-case raw (limitation §5.5). It is the best single candidate for a
*small* desk follow-up: if those three dispatches were recorded anywhere, the row promotes
without a device; if they were not, the note overstates what the raw supports and should be
corrected.

## 7. Reproduction

```
python3 analysis/scan_raw.py              # -> analysis/raw_index.jsonl
python3 analysis/extract_candidates.py    # -> candidate_records.jsonl (244 MB; kept out of the repo)
python3 analysis/adjudicate2.py           # -> analysis/verdicts_final.json     (the headline)
E0194_NO_G7=1 E0194_OUT=verdicts_loose.json python3 analysis/adjudicate2.py   # the loose bar
python3 analysis/control.py               # positive control row list
python3 analysis/verdict_crosscheck.py    # -> analysis/verdict_crosscheck.json
python3 analysis/verify_survivor.py       # the §2 claim, straight from raw
```

`analysis/extract_candidates.py` reads `blocked_rows.json` and writes a 244 MB intermediate;
it is deliberately **not** committed. `analysis/control_verdicts.json` is the positive
control's output over the 543 emitter-grade fields.

**Nothing in `tools/agx-isa/`, `docs/`, or `PROVENANCE.md` was read-modified. No label was
changed. Nothing was committed.**

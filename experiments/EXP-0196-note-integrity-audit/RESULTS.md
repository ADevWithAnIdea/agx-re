# EXP-0196 — RESULTS

## 0. Headline

**Eleven notes in `tools/agx-isa/validation.json` state observations that committed raw
contradicts. Nine of them sit on emitter-grade fields, and six of those nine sit on
instructions in the published `emittable_mnemonics` list.** Every one is quoted below with
the exact file and line that contradicts it.

Two of the eleven are one defect each; the other nine are two defects with a shared
mechanism. Both mechanisms are already documented in this corpus under other names — a
threshold applied to the wrong units (`sel`), and an index that cannot see a record whose
field key is `null` or underscore-prefixed (`DEF-0190-1`, the citation repairs).

**No note cites a file that does not exist.** All 87 distinct `EXP-*` references inside
note text resolve to an experiment directory; the single `raw/…` path named in a note
exists.

---

## 1. The seed case: `rt_ray_mem.field_off` — the note overstates, and the raw does not exist

**Verdict: the three executions are NOT recorded anywhere in `experiments/`. This is an
absence, not a search failure — the experiment's own manifest says so in three places.**

First, a correction to the framing. The claim is **not in `tools/agx-isa/validation.json`**.
`rt_ray_mem.field_off` there is `corpus-correlation` / target `M4` / evidence `["EXP-M4-13"]`
and carries **no `note` at all**. The claim lives one level upstream, in EXP-0157's unmerged
verdict, which is what `EXP-0194` §6 was reading:

> `experiments/EXP-0157-g17p-emit-misc/analysis/field_verdicts.json:424`
> `"outcomes ok=3 | carrier k_rq_getters.metal :: k_cand_baryx / k_cand_baryy / k_cand_td_dist,
> anchor +None, 1 agreeing captures (gate differential-compilation) | … `**`Each of the three
> programs was executed and returned its own host-computed oracle exactly, so the byte change
> produced the predicted effect.`**` …"`

(identically at `analysis/field_verdicts_by_carrier.json:2163`, and authored at
`analysis/merge.py:97-105`.)

**The same experiment says, three times, that the run those kernels belong to dispatched nothing:**

| where | text |
|---|---|
| `EXP-0157/RESULTS.md:647` | <code>&#124; `g17p_census01` &#124; 0 &#124; own-MSL compile census (no dispatches) &#124;</code> |
| `EXP-0157/manifest.json` → `raw_runs.g17p_census01` | `{"records": 0}` |
| `EXP-0157/analysis/summary.py:37` | `"g17p_census01": "own-MSL compile census (no dispatches)"` |

`raw/g17p_census01/` contains exactly five files: `getter_diff.json` (a static byte diff),
the three `.hex` programs, and `provocation_census.json` (a static tokenization census).
There is no `sweep.jsonl`.

**Nor were those three kernels dispatched by any other run in the experiment.** The harness's
carrier table, `experiments/EXP-0157-g17p-emit-misc/harness/carriers.py:112-120`, defines
eight ray-query carriers — `rq_cprim, rq_cgeom, rq_cdist, rq_ccount, rq_mprim, rq_mdist,
rq_mtype, rq_all` — and **none of them is `k_cand_baryx`, `k_cand_baryy`, or `k_cand_td_dist`**.
Enumerating the `carrier` column of all 22 `raw/*/sweep.jsonl` files returns 16 distinct
carriers; none is one of the three. The three kernels use `intersection_query<triangle_data>`,
a query type no dispatched carrier instantiates.

**Nor anywhere else in the repo.** `grep -rlI "cand_baryx" experiments/` returns six files:
`kernels/k_rq_getters.metal`, `analysis/{merge.py, field_verdicts.json,
field_verdicts_by_carrier.json}`, `raw/g17p_census01/provocation_census.json`, and
`EXP-0194/analysis/verdict_crosscheck.json`. Not one is a per-case dispatch record.

**Verdict: OVERSTATED.** The byte-diff half is fully committed and desk-verifiable
(`raw/g17p_census01/getter_diff.json` lists 14 differing offsets, each taking
`0xc4`/`0xc6`/`0xc8`). The execution half is asserted and unrecorded. Since the label
`isolated-byte-diff` requires *"the resulting program ran with the predicted effect"*
(`docs/evidence-classification.md` §2), the unmerged verdict does not meet its own bar —
which is a second, independent reason not to merge it, beyond the target mismatch
`EXP-0194` already noted.

---

## 2. What was checked, and against what denominator

`tools/agx-isa/validation.json` holds **1 212 entries** (1 040 field + 172 `_instruction`).
**855 carry a non-empty `note`**: 429 on emitter-grade fields (of the 544 at
`hardware-run` + `isolated-byte-diff`), 36 on emitter-grade `_instruction` entries, 390 on
everything else. 1 606 typed claims were extracted from them.

### 2.1 The four buckets

| bucket | all 855 | emitter-grade fields (429) |
|---|---:|---:|
| **SUPPORTED** — every checkable claim tested and holds | **380** | **210** |
| **OVERSTATED** — ≥1 claim contradicted by committed raw | **11** | **9** |
| **UNCHECKABLE** — no falsifiable claim in the note | 297 | 97 |
| *NOT CHECKED* — has a numeric/existential claim, no instrument built here | 167 | 113 |
| **CITES-MISSING-FILE** | **0** | **0** |

**The denominator I actually tested is 391 notes (219 emitter-grade), not 855.** The 167
"NOT CHECKED" are a real gap in this audit, not a property of the notes: they carry claims
like *"18 values return a silent zero"*, *"3/256 values excluded as not reproducible"*,
*"DENSE-INERT: 0 of 256 sub-values moved"* that are perfectly falsifiable and that I ran out
of instruments for. They are listed in `work/not_checked.json`. Counting them as
"UNCHECKABLE" would be exactly the kind of cannot-fail bookkeeping this corpus keeps
catching, so they are separated.

### 2.2 The exhaustive checks (100 % of their population)

| check | population | result |
|---|---:|---|
| every `EXP-*` named **inside note text** resolves to an experiment dir | 697 refs, 87 distinct | **87/87 resolve** |
| every `raw/…` path named inside a note exists | 1 | **1/1 exists** |
| `N of M` / `N/M` arithmetically possible (N ≤ M) | 308 ratios | **2 impossible ratios, in 4 entries** (→ §3.1); 2 further regex hits were false positives (`24 of 203 / 32 of 256`, `1024 of 2^32`) |
| percentage self-consistency (`K of N (P %)`, agreement `(x×)`) | 39 | **39/39 consistent** |
| `outcomes {…}` histogram vs raw, under the producing experiment's own gate | 75 (67 emitter-grade) | **75/75 SUPPORTED** |
| `moved on N of M ladder-passing carriers` vs raw | 53 emitter-grade | **53/53 SUPPORTED**, 81 arms |
| `X % agreement over K shared values, M moved vs D disagreements` vs raw | 11 emitter-grade | **11/11 SUPPORTED** |
| `EXP-0164 withheld: N values dispatched, M carrier(s), K moved` vs EXP-0164's own outputs | 66 | **66/66 exact, numbers agree** |
| `EXP-0189 withheld …: 0 values dispatched` vs raw | 57 zero-claims | 56 SUPPORTED, **1 CONTRADICTED** |
| `EXP-0189 citation repair … has no per-value records for it` vs raw | 28 (27 emitter-grade) | 22 SUPPORTED, **6 CONTRADICTED** |
| `Compared against … on N measurements: K overturned (P %)` vs EXP-0144's `reval_vs_original.json` | 28 | **28/28 reconcile exactly** |
| machine-readable `values_dispatched` / `distinct_bytes` vs raw | 174 | 140 SUPPORTED, 9 instrument-limited, 25 no jsonl raw |

The two largest families are clean and were regrounded from raw with our own code, not by
importing the producing experiment's script:

* **EXP-0169, 53 notes.** `analysis/check_0169.py` re-derives the observation signature,
  `moved_of`, the cross-run gate and the liveness ladder from 47 746 raw records in
  `raw/g17p_20260830_run01..04`. Over **81 arms** it reproduces `movedA`, `movedB`, `common`,
  `agree`, `disagreements`, `n_valuesA/B`, `distinct_bytes`, `ladder_pass` and `gate_live`
  **identically in every single case**. 53/53 SUPPORTED.
* **EXP-0154 and siblings, 75 `outcomes {…}` histograms.** `analysis/check_outcomes2.py`
  reproduces every histogram exactly.

---

## 3. The eleven OVERSTATED notes

### 3.1 `sel.b1`, `sel.b2`, `sel.selFalse`, `sel._instruction` — a threshold applied in the wrong units

`sel` is one of the 32 mnemonics in `coverage.emittable_mnemonics`. Three of its four
affected entries are `hardware-run` emitter-grade fields.

**The note, verbatim** (`tools/agx-isa/validation.json`, identical on `sel.b1`, `sel.b2`,
`sel.selFalse`):

> "db.json models `body` as one opaque 24-bit raw field; it is three located byte-fields.
> **255/128 byte+3 values >=0x80 and 1/128 values <0x80 matched their host-computed oracle
> exactly.** FIELD-MODEL CORRECTION (EXP-0140, HW): `body` is not an opaque 24-bit field.
> byte+3 is the predicate-FALSE operand (bit7 = immediate flag, value = the byte itself;
> **255 immediate matches vs 1 in the register region**); …"

and on `sel._instruction`:

> "… byte+3 is the predicate-FALSE OPERAND whose value appears in the output (**255 of 128
> values >= 0x80 and 1 of 128 < 0x80** matched their host-computed oracle exactly)."

**"255 of 128" is not a possible measurement.** There are exactly 128 byte values ≥ 0x80.

**What the raw shows.** `experiments/EXP-0140-m4-emit-mov-cf/raw/m4_20260828_run01/sweep.jsonl`,
group `sel.body.b3`: **512 records, 256 distinct byte values × 2 input vectors, outcome `ok`
on all 512.** Split at bit 7:

| | claimed | raw run01 | raw run02 | raw run03 |
|---|---:|---:|---:|---:|
| byte+3 ≥ 0x80 matching its oracle | **255 of 128** | **128 of 128** | 128 of 128 | 128 of 128 |
| byte+3 < 0x80 matching its oracle | **1 of 128** | **128 of 128** | 128 of 128 | 128 of 128 |

Both regions matched — with *different* oracles, each recorded in the raw. Line 1618 of
`raw/m4_20260828_run01/sweep.jsonl` (`bytes: "16c2a000"`, byte+3 = 0x00):

```
"note": "byte+3 < 0x80 predicted to read an unwritten operand -> 0 [a=A1]",
"outcome": "ok", "match": true, "oracle": {...,"6":100,"7":100}, "observed": {...,"6":100,"7":100}
```

and for `bytes: "16c2a0c3"` (byte+3 = 0xC3):

```
"note": "byte+3 predicted to be the FALSE-arm 8-bit immediate (value = byte) [a=A1]",
"outcome": "ok", "match": true, "oracle": {"0":195,...}, "observed": {"0":195,...}
```

**Root cause, committed and quotable** — `experiments/EXP-0140-m4-emit-mov-cf/analysis/verdicts.py:424-425`:

```python
imm_matches = [v for v in per[imm_tag]["matched_prediction"] if v >= 128]
low_matches = [v for v in per[imm_tag]["matched_prediction"] if v < 128]
```

For `sel`, `imm_tag = "b3"`, and `per["b3"]["matched_prediction"]` holds **field-level**
values (`byte << 16`): `0, 65536, 131072, … 16711680`. So `v >= 128` selects every value
except `0` → **255**, and `v < 128` selects only `0` → **1**. The threshold belongs on
`(v >> 16)`. Applying it there gives 128 and 128, which is what the raw shows.

**Consequence.** The label is unaffected — `verdicts.py:426` gates on
`len(imm_matches) + len(low_matches) >= 240`, and 255+1 and 128+128 are both 256. What is
wrong is the *observation*: the note asserts an asymmetry across bit 7 (immediate region
matches, register region does not) that the raw does not contain. The interpretive sentence
"bit7 = immediate flag" is separately supported by the two different per-case oracles in the
raw — but not by the 255-vs-1 figure the note offers as its evidence.

### 3.2 `mov_zext16.src_reg` — a negative existential claim the raw contradicts, on an emittable instruction

`mov_zext16` is in `coverage.emittable_mnemonics`; this field is `hardware-run`.

**The note, verbatim** (second clause):

> "**EXP-0189 citation repair: the records supporting this row live in EXP-0146-m4-emit-int-misc;
> the original citation EXP-0161, EXP-0165 has no per-value records for it.** Both are kept —
> the stale one is where the claim came from, the new one is where the evidence is."

**The raw.** `experiments/EXP-0161-g17p-carry-fspecial/raw/g17p_20260829_run01/sweep.jsonl`:

* **line 3371** — `{"instr": "mov_zext16", "field": "src_reg", "value": 0, "bytes": "13000001",
  "carrier": "SYNTH+LIFTED:k_zext16@mov_zext16+0", "arm": "B_ZEXT_SYNTH", "outcome": "ok"}`
  — **256 such records** in run01, 256 in run02, 128 each in `supp01`/`supp02`/`supp03`
  (896 total under the *named* field);
* **line 3755** — `{"arm": "B_ZEXT_SYNTH", "byte_index": 0, "bytes": "00000001", …,
  "field": "__raw_b0", "instr": "mov_zext16"}` — the **dense 0..255 byte0 sweep**, 256 records
  per arm × 2 arms in each of run01 and run02.

**The same entry's own `range` cites exactly those records:**

> "byte0 HIGH nibble: all 16 values exercised, as the complete 0..255 byte0 raw-byte probe
> in **B_ZEXT_SYNTH (run01 + run02**, judged by the full 16-register architectural dump), plus
> 16 GENERATED encodings (gen01/gen02/gen03)"

So the row's `range` and its `note` disagree about the same experiment. The `note` is the
one the raw refutes.

**Mechanism.** `EXP-0189`'s index keys on the `field` string. The byte0 sweep is filed as
`__raw_b0` and is dropped by the same underscore filter that `DEF-0190-1` (quoted in 21 other
notes in this very file) identifies as the reason INERT verdicts cannot fail. Here the same
filter manufactures a false *absence*.

*(One honest sub-note: the `src_reg` records in EXP-0161 sweep byte+1, which this entry no
longer labels after DEF-0161-2 re-pointed it to byte0's high nibble. The `__raw_b0` records
do sweep byte0. The claim is contradicted either way, but the byte0 records are the decisive
half.)*

### 3.3 Five rows citing `EXP-0171` — the note calls its own source "stale" and empty

Affected, all `hardware-run` emitter-grade: `ilogic.outmod`, `ilogic.lut_a_z`, `iadd2.srcA`,
`ibfe.srcA`, `fspecial_est.subop`.

**The note, verbatim** (on `ilogic.outmod`; the other four differ only in the leading clause):

> "MOVED 128 of 256 on NAT:k_and@ilogic+32; cross-run agreement 1.0000 (256 agree / 0 disagree);
> 7 admitted carriers [FRAME,NAT,SYNTH | k_and,k_andn,k_nand,k_or,k_xor]; accept-set size 128;
> outcomes {"ok": 128, "silent_zero": 128} | **EXP-0189 citation repair: the records supporting
> this row live in EXP-0146-m4-emit-int-misc, EXP-0154-g17p-emit-alu; the original citation
> EXP-0171 has no per-value records for it. Both are kept — the stale one is where the claim
> came from, the new one is where the evidence is.**"

**Two contradictions, in one sentence.**

**(a) The note's own first clause is EXP-0171's committed verdict text.** `grep -rlF "MOVED 128
of 256 on NAT:k_and@ilogic+32"` finds it in
`experiments/EXP-0171-g17p-ilogic-srca/analysis/field_verdicts.json` — and in no other producing
experiment. That file's `verdicts` object is keyed by exactly the five field names in question:
`ilogic.outmod`, `ilogic.lut_a_z`, `iadd2.srcA`, `ibfe.srcA`, `fspecial_est.subop` (plus
`b_alu10_loe.outmod` / `b_alu10_lof.outmod` carrying the same text). The measurement the row
reports *is* EXP-0171's, taken on EXP-0171's own carriers (`NAT`, `SYNTH`, `FRAME` with
`k_and…k_xor`), which appear in no other experiment's raw. The note says its source has no
per-value records for the field, in a sentence that quotes that source's per-field verdict.

**(b) EXP-0171's raw holds hundreds of per-value records per field per run**, at exactly the
byte each field occupies (spans from `tools/agx-isa/db.json`):

| field | db.json span | byte | `EXP-0171/raw/g17p_20260830_run01/sweep.jsonl` | `…run02/sweep.jsonl` |
|---|---|---:|---|---|
| `ilogic.outmod` | start 56, w 8 | 7 | **1 792 records, 256 distinct values, 3 carriers**, first at line 1282 | 1 792 / 256 / 3, first at line 26964 |
| `ilogic.lut_a_z` | start 37, w 3 | 4 | 1 792 / 256 / 3, line 770 | 1 792 / 256 / 3, line 26708 |
| `iadd2.srcA` | start 56, w 8 | 7 | 768 / 256 / 3, line 23229 | 768 / 256 / 3, line 11185 |
| `ibfe.srcA` | start 64, w 8 | 8 | 768 / 256 / 2, line 33132 | 768 / 256 / 2, line 1026 |
| `fspecial_est.subop` | start 24, w 8 | 3 | 768 / 256 / 3, line 20154 | 768 / 256 / 3, line 14260 |

Sample (`run01`, line 1282):
`{"instr": "ilogic", "field": null, "byte_index": 7, "value": 0, "bytes": "2b031f01000000000000",
"carrier": "NAT", "arm": "ILOGIC", "outcome": "silent_zero"}` — the byte sweeps 0..255 dense
on each of `NAT`, `SYNTH`, `FRAME`.

For four of the five fields the field **is** the whole byte, so a dense byte sweep is a
complete per-value sweep of the field. `EXP-0171/RESULTS.md:50` names it in the section
heading — *"`ilogic` / `b_alu10_*` byte+7 (`outmod`) — the primary target"* — and
`RESULTS.md:260` concludes *"`outmod` → `hardware-run`"*. EXP-0171 is where this field was
promoted; the note calls it the stale citation with no records.

**Mechanism.** Same as §3.2, one step further: EXP-0171's records carry `"field": null` with
the byte in `byte_index`, so a field-name-keyed index sees nothing at all.

### 3.4 `half_alu_fma12.dst` — "0 values dispatched" against 1 536 committed records

Label `untested` (a blocked field, so lower stakes), but the claim is flatly false.

**The note, verbatim:**

> "EXP-0189 withheld (UNVERIFIABLE): **0 values dispatched over 0 arm(s), 0 observations moved**,
> re-derived from raw under EXP-0164's frozen thresholds (>=2 gated runs, moved>=1 in both,
> >=99% per-value agreement, moved >= 2x disagreements). **Reason: field-named-but-unstructured.**"

**The raw** — `experiments/EXP-0180-g17p-halfalu-rerecord/`:

| file | records with `instr = half_alu_fma12` | of which `field ∈ {dst, __dst_nibble}` | distinct values | first |
|---|---:|---:|---:|---|
| `raw/g17p_run02/sweep.jsonl` | 7 824 | **768** | **256** | line 4426, `field: "dst"`, `value: 255`, `carrier: "C_HI"` |
| `raw/g17p_run03/sweep.jsonl` | 7 824 | **768** | **256** | line 5473, `field: "dst"`, `value: 0`, `carrier: "C_HI"` |

And again the row's own `range` describes that sweep: *"0..15 dense: all 16 values of byte0's
high nibble dispatched on two carriers in both gated runs, 16/16 per-value records identical
across runs … r15 is never non-zero in any of the **16 335 observed cases**"*.

"`Reason: field-named-but-unstructured`" is the honest part — the collector found the records
and could not structure them. "0 values dispatched" then reports the collector's zero as if it
were the hardware's.

### 3.5 A related, smaller class: 13 entries whose `note` and `range` contradict each other

Beyond §3.4, twelve `untested` rows on `b_alu10_loe` / `b_alu10_lof` (`modA`, `modB`, `outmod`,
`srcA`, `src_flag`, `src_reg`) carry `note: "…0 values dispatched over 0 arm(s)…"` next to
`range: "256 of 256 sub-values, DENSE (256 distinct encodings of the byte)"`.

**These twelve are NOT counted as OVERSTATED here.** Under my instrument the note's claim is
literally true: no raw record anywhere carries `"instr": "b_alu10_loe"`. EXP-0171 measured the
same bytes through records labelled `"instr": "ilogic"` and keyed its verdict
`b_alu10_loe.outmod`, so which of the two statements is wrong — the note or the range — is a
descriptor-identity question this audit is not equipped to settle. Recorded so the label owner
can rule on it; `analysis/e0189_zero_check.json` has the per-row evidence.

---

## 4. Notable SUPPORTED results (so the negatives are legible)

* **All 53 EXP-0169 "moved on N of M ladder-passing carriers" notes.** 81 arms regrounded from
  47 746 raw records; every cross-run statistic reproduced identically. Includes the four
  `no observable effect over the swept range on 2 structurally different ladder-passing carriers`
  rows, which are accurate as written (the separate DEF-0190-1 objection is about what an
  inert arm can *establish*, not about whether the note reports the raw correctly).
* **All 75 `outcomes {…}` histograms.** Exact, to the case, in every bucket.
* **All 11 EXP-0168 agreement notes.** e.g. `cvt_f2h.op` — claim *99.609 % over 256 shared
  values, 221 moved vs 1 disagreements* → raw best pair `CVTF2H/consumed`,
  `run02|run03`: `agree_pct 99.609, common 256, moved 221, disagreements 1`.
* **All 28 EXP-0144 `rv01` notes.** Every "N measurements: K overturned (P %)" reconciles
  exactly with `EXP-0144/analysis/reval_vs_original.json`, including the five composed ones:
  `pack_convert.cvt_enable`'s 2312/2 is bytes +5,+6,+7,+8,+9 = 512+512+264+512+512 with
  0+0+2+0+0 overturned, exactly the five-byte field model the note itself states.
* **`matrix_mac.dst_en` and `matrix_mac.c_neg_*`** — recomputed from
  `EXP-0147/raw/m4_20260828_run0{1,2}/sweep.jsonl`: `dst_desc` is `ok` on exactly the 64 values
  `0x40–0x7f` (set identity, both runs), `silent_zero` on 128, `wrong_value` on 64; `b11hi` is
  `ok` on exactly the 32 values with `(v & 3) == 0`. Both notes are exact.
* **The four EXP-0138 "N/M pre-registered predictions REFUTED" notes.** These look mis-sourced
  (validation's `falu3.ctrl_len` carries EXP-0138's `falu3.srcB` figure of 60/64) but are
  **correct**: re-deriving which byte each EXP-0138 sweep actually varied from the `bytes`
  column shows EXP-0138's `falu3.srcB` sweep varies **byte+4**, which is db.json's `ctrl_len`
  (start 32), and its `dst_lo` varies byte+0, which is db.json's `dst`. The rename the note
  describes was applied correctly.
* **`h_coord_hi`, `rtq_state_move`, `sr_read_wide` `_instruction` case counts** — the notes
  claim 5 750 / 5 756 / 9 579 cases; counting non-`__` records for those mnemonics across all
  22 EXP-0157 raw runs gives **5 750 / 5 756 / 9 579**. (Minor imprecision, not counted as a
  finding: `sr_read_wide` says "3 ray-query carriers" where the raw shows five distinct
  carriers — an undercount, i.e. conservative.)

---

## 5. How this method could have failed to say "no"

Stated so the next reader can attack it. Two of these already fired during the audit.

1. **A naive recomputation manufactures findings, and mine did.** The first
   `outcomes {…}` pass (`analysis/check_outcomes.py`, kept in the tree) counted every record in
   a run and reported **20 mismatches**, 15 of them emitter-grade — e.g. `imad.dst` claim
   `fault: 2` vs raw `fault: 64`. Every one was an artefact: `EXP-0154/analysis/verdicts.py:167-181`
   drops a case if any run recorded `victim: true` (innocent-victim command-buffer errors) and
   drops cross-run outcome disagreements. Applying the documented gate
   (`check_outcomes2.py`) moves all 20 to SUPPORTED. **Had I stopped at pass 1 I would have
   published 20 false findings.** The same happened on the citation repairs: a name-only pass
   reported `half_alu.dst` CONTRADICTED (a `dst` record belonging to another instruction);
   pairing `instr` with `field` cleared it.
2. **My "record exists" instrument is field-name-keyed, which is the very defect §3.2–3.3
   describe.** For 15 of the 28 citation-repair rows the *positive* half —
   "the records supporting this row live in EXP-XXXX" — came back NOT-FOUND. That is almost
   certainly my instrument, not the note: EXP-0163/0172 raw keys sweeps by byte name (`b1`,
   `b7`, `loc`) and EXP-0189 used a span-based mapping I did not reimplement. **I therefore
   report nothing about those 15.** The audit is asymmetric on purpose: it can prove a
   negative existential claim wrong (a record exists) but not right (an absence in my index is
   not an absence in the corpus). All six findings in §3.2–3.4 are of the first kind.
3. **The gate constants are copied, not re-derived.** `check_0169.py` and `check_0168.py`
   re-implement the arithmetic themselves but take ≥99 % agreement, `moved ≥ 2×disagreements`,
   `common ≥ 2` from the producing experiments' docstrings, because the claim is *stated in
   those terms*. A note whose numbers are right under a wrong gate reads SUPPORTED here.
4. **391 of 855 notes were actually tested.** 167 carry falsifiable claims I built no
   instrument for (`work/not_checked.json`) — the "silent zero" counts, the sibling-GPU
   contamination exclusions, the DENSE-INERT counts, the `no_store` reclassifications. The
   base rate of defects in the part I did check is 11/391 ≈ 2.8 %; if that rate held over the
   167, roughly **four or five more findings are sitting there unexamined.** This audit's
   "zero further findings" is a statement about coverage, not about the corpus.
5. **I checked notes against raw, not raw against reality.** Where a producing experiment's
   own analysis JSON and its raw agree, I mark SUPPORTED. If a harness wrote a wrong
   `outcome` or a wrong `moved` flag into the raw in the first place, this audit reproduces
   the error and calls it support. `EXP-0169`'s `moved` flag in particular is read from the
   record, not recomputed from `observed`.
6. **The defect is concentrated in merge-time prose, and the sample that shows it is small.**
   53 + 75 + 11 = 139 of my 219 tested emitter-grade notes come from EXP-0169,
   EXP-0154(+siblings) and EXP-0168, which print their notes from a script — and all 139 are
   SUPPORTED. Matching each note against the committed artifact that carries it
   (`analysis/note_provenance.py`) puts 372 of the 429 emitter-grade notes as *verbatim* copies
   of an experiment's own output, 22 as a committed clause plus appended text, and 35 as
   authored at merge time. **Ten of the eleven findings sit in text that is not a verbatim copy
   of any experiment's output**: the three `sel` rows are merge-authored outright, and in the
   seven citation-repair rows the contradicted sentence is the clause *appended* after the
   committed verdict text (the committed half — "MOVED 128 of 256 on NAT:k_and@ilogic+32 …" —
   is correct; the appended half is the defect). The eleventh, `half_alu_fma12.dst`, is the
   exception that matters: it is an *exact* copy of
   `EXP-0189/analysis/reclassify.json`, so a faithful transcription of a wrong upstream number.
   The pattern is suggestive, not established — 11 events is far too few to put a ratio on, and
   the merge-authored population is itself the population my instruments happened to cover best.
7. **Two findings rest on reading "per-value records for it" strictly.** In §3.3, EXP-0171's
   records carry `field: null` and identify the swept byte only through `byte_index`. If
   "records for it" is read as "records keyed by this field's name", the notes are defensible.
   I read it as "records that dispatch values of this field's bits", because that is what the
   sentence is used for — to move a citation — and because four of the five fields *are* the
   whole swept byte. A reader who prefers the narrower reading should downgrade §3.3 from
   five findings to zero and keep §3.2 and §3.4, which have records under the field's own name.

---

## 6. Files

`analysis/classification.{json,tsv}` — the four buckets, per note, with which checks ran.
`analysis/check_0169.json`, `check_0168.json`, `outcomes_check2.json`,
`citation_repair_check2.json`, `e0189_zero_check.json`, `coverage_keys_check.json` — per-check
evidence. `analysis/outcomes_check.json` and `citation_repair_check.json` are the **superseded
first passes**, retained deliberately as the negative control for §5.1.

**Nothing in `tools/agx-isa/`, `docs/`, or `PROVENANCE.md` was modified. No label was changed.
Nothing was committed.**

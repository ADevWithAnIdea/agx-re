# EXP-0215 — RESULTS

```
Clean-room provenance: derived analysis of already-committed artifacts in this repository.
Device contacted:      NONE. EXP-0213 held the A18 Pro for quiet Gate E confirmations.
Apple binary read:     NONE.  Shader compiled: NONE.
Inputs pinned:         tools/agx-isa/db.json         sha256 02a47fc6f8ac4589…
                       tools/agx-isa/validation.json sha256 ebb0866193fb7868…
                         (both frozen into work/ before the first scoring run, because
                          other agents write both concurrently)
Citations removed:     0.   Labels changed: 0.   Raw files touched: 0.   Committed: NOTHING.
```

## 0. Headline

**496 citation additions over 372 of the 1053 field rows. Zero removals. Every addition
names a file and a line in a committed `raw/` tree, and every one is anchored to the
field's own bits at its *current* span — never to its name.**

**741 further candidates were refused, each with its reason recorded.** The refusals are
the load-bearing half: they include the exact failure modes that were named as the way to
recreate the EXP-0189 disaster, and each of them fired on real data, not on a synthetic
example.

* `carry_gen.srcA` ← EXP-0154 — **refused**: the records declare `fstart/fwidth (24,8)`
  while the row's span is `(8,8)`. Same name, different bits. So did 14 more, among them
  `mov_zext16.src_reg` ← EXP-0154 (declared `(8,7)`, current `(4,4)`) and `half_alu.dst` ←
  EXP-0169 (declared `(8,8)`, current `(4,4)`) — the two rows EXP-0197 §4.1 and §4.2 had to
  correct by hand, re-derived here by rule, on different candidate experiments.
* `bf_alu.srcA/srcB/tail` ← EXP-0171 and `cvt_f2h.op` ← EXP-0144 — **refused**: **every**
  committed encoding fails the descriptor's own `match` bits. Our own disassembler says
  those 10 938 records dispatched `bf_add_dst` (7 964) and `bf_mul_dst` (2 650), and those
  4 700 dispatched `cvt_f2h_dst` (4 665). The experiment's `instr` key and its committed
  bytes disagree.
* `simd_shuffle.src` ← EXP-0172 — **refused**: the only attribution was the carrier string
  `simd_shuffle@dead**src**/compute#0` on a `_baseline` record. A substring, not an
  observation.
* 438 candidates — **refused** as P4 dispatched-program corpora: program-level credit for
  every field of every instruction in a program that ran.
* 40 candidates — **refused** because the swept *byte* moved while the *field's own bits*
  did not (EXP-0214's `half_pack.dst` hazard).

**And the additions move the dashboards a long way — but not evenly, and not all upward.**
Five rows go *down* on geometry because the added experiment brings Gate A disagreements,
and those five are kept, because excluding evidence that scores badly is how a repair
becomes a wish (§4).

**The legacy index is not the lever here.** Under my citations it adds 4 rows on limits
and nothing else; under the *committed* citations it moves exactly 2 rows. EXP-0211
measured a 110-row ceiling for it under a blanket counterfactual; almost all of that
ceiling was P4 program-level credit, which this experiment refuses.

---

## 1. What was proposed

| | |
|---|---:|
| field rows in `validation.json` | 1053 |
| rows receiving at least one addition | **372** |
| additions | **496** |
| … justified by the modern evidence index | 456 |
| … justified by EXP-0211's legacy parsers | 40 |
| rows where an addition moves at least one dashboard rung | 268 |
| rows where it moves none (pointer restored, score unchanged) | 104 |
| additions whose locator is an **observation** record (outcome + value or bytes) | **496 of 496** |
| candidates refused, with reason | **741** |
| existing citations removed | **0** |

By tier: **458 T1** (≥2 distinct values of the field's own bits decoded out of committed
bytes at the current span, ≥2 of them match-preserving, ≥2 distinct requested values) and
**38 T3** (a legacy byte sweep whose match-preserving values move the field's own bits).
**T2 admitted nothing**: every candidate that declared the current span and swept it also
committed bytes, and was adjudicated on those bytes instead.

By row label: 212 `hardware-run`, 70 `untested`, 29 `isolated-byte-diff`, 22
`tokenization-only`, 20 `single-template-inference`, 19 `corpus-correlation`. **No label
was changed.** 70 `untested` rows now point at hundreds of dispatched records each; several
read as promotable on their face, and the ruling is the orchestrator's, not mine.

### The locator pattern

Every addition carries `locator: "<path>:<line>"` into a committed `raw/` file plus, for
the modern index, `first_record` (the first record of any kind). The two differ on purpose:
`EXP-0141-m4-emit-mem/raw/m4-20260828-run01/00_manifest.json:70` is the first *record* for
`atomic_tg.op_desc` and it is the **run plan** — `{"arm": …, "field": "op_desc", "instr":
"atomic_tg", "n_cases": 128}`, no value, no bytes, no outcome, and it sorts first in the
directory. The locator instead points at
`raw/m4-20260828-run12/sweep.jsonl:14768`, an observation. Two candidates were refused
outright because the plan was *all* they had.

Worked example, `atomic_tg.op_desc` (row cites `EXP-0156`, scored `no-data`):

> add **EXP-0141-m4-emit-mem** — 389 records, **386 with an execution outcome**, over 3
> raw runs on G16G; **256 distinct requested values, 256 distinct actual encodings of bits
> 40..47, all 256 match-preserving, 386 Gate A agreements and 0 disagreements**; outcomes
> `{ok 8, wrong_value 372, fault 4, hang 2}`.
> `experiments/EXP-0141-m4-emit-mem/raw/m4-20260828-run12/sweep.jsonl:14768`

The row's base reason string was, verbatim: *"cited raw holds 7 non-record file(s)
(.txt/.log/.hex) and 0 machine-readable records: FORMAT-UNREADABLE, not absent"*.

### Target hygiene

Of the 456 modern additions, **209 carry G16G/M4 run directories and 203 carry G17P**; the
rest name no target. **No addition can promote a target it did not run on**: dashboard 5
derives the target from the raw run-directory name, exactly as `evidence_index._target_of_run`
does, so a G16G addition to a G17P row lands on `G16G-direct-only` and says so in the row's
own `dashboard_effect` — `atomic_tg.op_desc` above is the worked case, a `G17P` row whose
only addition is 389 G16G records. That is why dashboard 5's `G16G-direct-only` bucket
*falls* by 15 while `G17P-direct-repeated` rises by 85: 15 rows that had M4-only evidence
gained a G17P experiment, and no row gained a target it has not run on.

---

## 2. The seven dashboards

Four runs. `base` and `prop` share the same evidence index and differ only in the
citations, so `prop − base` is **this experiment's own contribution**. `base_leg` and
`prop_leg` add EXP-0211's legacy parsers, so `prop_leg − prop` is **the legacy index's**.
This is the same control EXP-0211 used (`m3 − m3ctl`).

| dashboard | rung | base | +EXP-0215 citations | base +legacy index | +both | Δ mine | Δ legacy |
|---|---|---:|---:|---:|---:|---:|---:|
| 1. encoding geometry (of 1053) | `no-data` | 426 | **355** | 425 | 354 | **-71** | -1 |
|  | `bytes-seen` | 63 | **68** | 64 | 69 | **+5** | +1 |
|  | `ledger-verified` | 54 | **64** | 54 | 64 | **+10** | +0 |
|  | `geometry-mapped` | 510 | **566** | 510 | 566 | **+56** | +0 |
| 2. field/bit liveness (of 1053) | `no-data` | 426 | **355** | 424 | 353 | **-71** | -2 |
|  | `records-no-control` | 459 | **508** | 460 | 509 | **+49** | +1 |
|  | `decided-one-carrier` | 50 | **32** | 51 | 33 | **-18** | +1 |
|  | `decided-multi-carrier` | 118 | **158** | 118 | 158 | **+40** | +0 |
| 3. semantic map (of 1053) | `no-semantic-check` | 975 | **895** | 975 | 895 | **-80** | +0 |
|  | `checks-present` | 58 | **129** | 58 | 129 | **+71** | +0 |
|  | `bounded-map` | 5 | **4** | 5 | 4 | **-1** | +0 |
|  | `semantically-mapped` | 15 | **25** | 15 | 25 | **+10** | +0 |
| 4. canonical recipe (of 166) | `not-generated` | 148 | **148** | 148 | 148 | **+0** | +0 |
|  | `generated-point` | 14 | **14** | 14 | 14 | **+0** | +0 |
|  | `generated-no-donor` | 2 | **2** | 2 | 2 | **+0** | +0 |
|  | `canonical-recipe-proven` | 2 | **2** | 2 | 2 | **+0** | +0 |
| 5. direct G17P revalidation (of 1053) | `no-direct-target-evidence` | 434 | **363** | 434 | 363 | **-71** | +0 |
|  | `G16G-direct-only` | 177 | **162** | 177 | 162 | **-15** | +0 |
|  | `G17P-direct` | 3 | **4** | 3 | 4 | **+1** | +0 |
|  | `G17P-direct-repeated` | 439 | **524** | 439 | 524 | **+85** | +0 |
| 6. reproducible evidence chain (of 1225) | `incomplete` | 378 | **370** | 378 | 370 | **-8** | +0 |
|  | `citation-resolves` | 243 | **216** | 242 | 215 | **-27** | -1 |
|  | `auditable` | 322 | **174** | 323 | 175 | **-148** | +1 |
|  | `independently-confirmed` | 282 | **465** | 282 | 465 | **+183** | +0 |
| 7. finite-resource limits (of 1002) | `no-data` | 400 | **333** | 399 | 332 | **-67** | -1 |
|  | `partial-sweep` | 77 | **61** | 78 | 62 | **-16** | +1 |
|  | `full-domain-swept` | 388 | **400** | 388 | 396 | **+12** | -4 |
|  | `limit-mapped` | 137 | **208** | 137 | 212 | **+71** | +4 |
### 2.1 Read the audit row carefully

`independently-confirmed` +183 is the largest single number on this page and it is the
**weakest**. Dashboard 6's top rung is `≥2 raw runs AND (≥2 carriers OR ≥2 cited
experiments)`. A row that already had two raw runs reaches it the moment a *second cited
experiment* exists. That is a statement about the citation graph, which is exactly what
this experiment changed — it is **not** a second method, and it must not be read as one.
The `auditable` column falls by 148 for the same mechanical reason: those rows did not get
worse, they moved up a rung.

`decided-one-carrier` −18 on liveness is the same shape in the other direction: those rows
moved *up* to `decided-multi-carrier`, not down.

### 2.2 The legacy index, isolated

Under the **committed** citations the legacy parsers move exactly two rows:

* `jump.offset` — `no-data → records-no-control` (liveness) and `citation-resolves →
  auditable` (audit). This reproduces EXP-0211's single finding against the *repaired*
  `db.json`, four descriptor revisions later.
* `simd_reduce.op_hi` — `no-data → bytes-seen`, `→ decided-one-carrier`, `→ partial-sweep`.
  This field **did not exist** when EXP-0211 ran; EXP-0212 created it this morning by
  narrowing `simd_reduce.op` from `(8,8)` to `(8,3)`.

Under my citations the legacy parsers add **four rows on dashboard 7 only**
(`falu2.dst`, `falu2.opflags`, `iadd2.addsub`, `iminmax.dst`, all
`full-domain-swept → limit-mapped`): the legacy byte sweeps include hard outcomes, so they
cross the legal/rejected boundary that a `full-domain-swept` row is missing. Everything
else the 38 legacy-justified additions do is restore a pointer:
`device_load.elem_size`, `icmp_pred.srcA` and `icmp_pred.srcB` go
`auditable → independently-confirmed`, and the 14 `falu2.*` rows were already at the top
rung of every ladder they can reach.

**EXP-0211's 110-row geometry ceiling is not reachable under these rules, and should not
be.** 110 of its 112 movements came from `P4`, the dispatched-program corpus parser, which
credits every field of every instruction in a program that ran. 438 of my 741 refusals are
exactly that population.

---

## 3. Additions resting on post-repair spans

`db.json` gained 13 fields and moved 5 spans this morning (EXP-0212, commit `55b307e4`;
re-derived from git in `work/span_repair.json`, not from prose). **Five additions on three
rows rest on a post-repair span**, and every one of them is a span that *moved*:

| row | old span | new span | addition | what makes it valid at the NEW span |
|---|---|---|---|---|
| `half_alu_fma12.ext` | (32,64) | **(48,48)** | EXP-0169, EXP-0180 | 9 216 of 12 288 records sweep bytes 6…11 — the new span — at 256 values each; **1 531 = 6 × 256 − 5** distinct encodings is the arithmetic signature of a per-byte dense sweep over exactly six bytes. Agrees with EXP-0212 §3's own re-derivation. |
| `irotate.operands` | (24,40) | **(48,8)** | EXP-0154 | 512 of 2 560 records sweep byte 6 = the whole new span, 256 distinct encodings. EXP-0212 §3 names the same arm. |
| `pop_reconverge.reserved` | (32,16) | **(32,8)** | EXP-0140, EXP-0156 | 23–24 distinct encodings of byte 4 over 34–35 requested values: **sampled, not dense**, consistent with EXP-0212's finding that this sweep covers 33 of 256 low bytes. |

**None of the 13 new fields received an addition.** They are new rows with no citation and
no experiment whose raw the two indexers can attribute to them — except
`simd_reduce.op_hi`, which the legacy index reaches through the row's *existing* citation
(§2.2). That is a real gap, stated as a gap.

The same repair is what makes 15 refusals correct rather than pedantic: `half_alu_fma12.ext`'s
own current citation, **EXP-0203**, carries records declaring `(32,64)` — the *old* span. The
row is `untested`, so nothing rests on it, but it is on the suspect list in §5 and it was
left alone.

---

## 4. Five rows where an addition makes the score WORSE

Kept, not filtered. `analysis/downgrades_from_additions.json`.

| row | rung | caused by | the disagreement |
|---|---|---|---|
| `falu3.op` | `geometry-mapped → bytes-seen` | EXP-0138 (M4) | 384 agreements **and 384 Gate A disagreements**; 128 distinct encodings for 256 requested values |
| `falu3_ext.op` | `geometry-mapped → bytes-seen` | EXP-0138 (M4) | the same, 384/384, 128 of 256 |
| `falu3_srcmod12.opsel` | `geometry-mapped → bytes-seen` | EXP-0138 (M4) | 12 agreements, 12 disagreements, 4 encodings for 8 requested values |
| `irotate.b2` | `geometry-mapped → bytes-seen` | EXP-0146 (M4) | 97 agreements, **696 disagreements**, 32 encodings for 256 requested values |
| `jump_cond.offset` | `ledger-verified → bytes-seen` | EXP-0140 (M4) | 72 agreements, 16 disagreements over a 48-bit field |

All five are the **DEF-0166-1 signature**: the harness requested a value the assembler
could not set. Note what the same table shows on the other side — for `falu3.op` the two
G17P additions (EXP-0154, EXP-0160) report **768 and 3 740 agreements with zero
disagreements and 256 of 256 encodings**. So the failure is the *M4-era emitter*, not the
field. Dropping EXP-0138 to keep the green number would have hidden a real defect in a
real harness; per §9 the correct action is to record both and let the axes stay separate.

---

## 5. Existing citations that look wrong — listed, and left alone

§9: *"A broken citation or missing raw artifact downgrades auditability; it does not by
itself prove the hardware fact false."* Nothing below was removed, rewritten, or annotated
onto a row. `analysis/suspect_citations.json`.

**A. Unresolvable citations: 0.** Every citation string in the sidecar globs to exactly one
directory, and no citation prefix is ambiguous.

**B. 372 (row, citation) pairs whose cited experiment has no `raw/`, no authored probe, or
both — 240 distinct rows, 9 distinct citations.** `EXP-M4-13` (168), `EXP-M4-12` (129) and
`EXP-M4-14` (35) are the compile-only census experiments the sidecar's own `_conventions`
already flags; `EXP-0165` (21), `EXP-0214` (13), `EXP-0181` (3), `EXP-0190`, `EXP-0192` and
`EXP-M4-10` (1 each) are analysis-only experiments cited as evidence. This reproduces
EXP-0209 §2's R1 finding from the other end. **It is why 232 of my 741 refusals are H1
refusals: I will not add a citation of that shape either.**

**C. Cited experiments with machine-readable raw and zero records for the row: 0.** Every
zero in this corpus is either a format-unreadable case or a B case.

**D. 26 (row, citation) pairs where the cited records name the field but do not carry its
current bits.** Twenty-two declare a different `fstart`/`fwidth`; four commit bytes that
fail the descriptor's `match` on every record. The full list is in the
JSON; the ones that matter most:

| row | label | citation | complaint |
|---|---|---|---|
| `mov_zext16.src_reg` | hardware-run | EXP-0161 | records declare `(8,7)`; the row's span is `(4,4)` — **EXP-0197 §4.1, re-derived independently** |
| `fspecial.dst` / `.src` / `.src_ext` | hardware-run | EXP-0161 | declared `(12,4)`/`(24,8)`/`(40,8)` against current `(24,8)`/`(40,8)`/`(12,4)` — the three names look **rotated** relative to the spans |
| `imad.srcB` / `.srcC_lo` | hardware-run | EXP-0154 | declared `(40,8)`/`(48,8)` against current `(48,8)`/`(40,8)` — **swapped** |
| `half_alu.srcA` / `.srcB` | hardware-run | EXP-0169 | declared `(24,8)`/`(32,8)`; current `(8,8)`/`(24,8)` — shifted by one operand slot |
| `half_alu_ext8.dst` / `.srcA`, `half_alu_fma12.srcA`, `falu3.srcA`, `falu3_ext.srcA`, `iminmax.srcA`/`.srcB` | hardware-run | EXP-0180 / EXP-0154 / EXP-0160 | same shape |
| `cvt_f2h.b1` / `.src` / `.b4` / `.tail` | hardware-run, isolated-byte-diff | EXP-0144 | **1 280 of 1 280** committed encodings fail `cvt_f2h`'s `match`; our disassembler reads them as `cvt_f2h_dst` |
| `half_alu_fma12.ext` | untested | EXP-0203 | records declare the **pre-EXP-0212** span `(32,64)` |
| `iter_at.grp` | isolated-byte-diff | EXP-0168 | records declare `(0,8)`; the field is bit 7 alone |
| `reg_move_cb.form`, `shift_amt_move.kind` | hardware-run | EXP-0169 / EXP-0154 | declared `(16,8)`; current `(20,4)` |

Two readings are open for every row in D and this experiment does not adjudicate between
them: either the sidecar's `start`/`width` moved out from under a verdict that measured
different bits (which EXP-0212 §3 shows happens, and deliberately did **not** re-point), or
the harness's declared span is simply wrong. Both are answered by opening one file, and
neither is answered by deleting a citation.

### 5.1 The sibling-descriptor finding

`analysis/sibling_mnemonics.json`. Two experiments key records to a mnemonic their own
committed bytes do not decode to, under today's `db.json` and our own disassembler:

| experiment | keyed `instr` | what the bytes tokenize to |
|---|---|---|
| EXP-0171 | `bf_alu` (10 938 records) | `bf_add_dst` 7 964, `bf_mul_dst` 2 650, and 324 assorted |
| EXP-0144 | `cvt_f2h` (4 700 records) | `cvt_f2h_dst` 4 665, `cvt_f2h` 5, 30 assorted |

`bf_alu`'s match is byte0 `0x11` + byte1 `0x02`; the committed anchor is
`31001c001100c081`. This is **not** proposed as a re-attribution to `bf_add_dst.*`: byte 3
is `bf_alu.srcA` but `bf_add_dst.srcB`/`.tail`, so re-pointing would move a label onto a
different operand. It is a descriptor question, and it is handed over rather than answered.

---

## 6. What this experiment did and did not establish

* **New raw observations:** none. No device was touched.
* **New geometry facts:** none about the hardware. About the evidence: 71 of 426 `no-data`
  geometry rows have machine-readable per-field records at their current span in an
  experiment they do not cite: 54 of the 71 reach `geometry-mapped` (the field's
  complete encodable domain dispatched), 16 reach `ledger-verified`, 1 `bytes-seen`.
* **New liveness facts:** none about the hardware. 71 rows leave liveness `no-data`; 40
  reach `decided-multi-carrier` on controls that were already committed and already firing.
* **New semantic facts:** none. 71 rows gain `checks-present` and 10 reach
  `semantically-mapped` from host oracles already in the corpus (e.g. `cvt_f2i.signflag`,
  1 280 checks over 3 buckets, 4 distinct oracle payloads, 10 runs, from EXP-0202).
* **New generated recipes:** none. Dashboard 4 is unchanged at 148/14/2/2, as it must be —
  it reads the recipe registry, not the evidence index.
* **Claims downgraded:** none. No label changed and nothing was retracted. Five *scores*
  fall (§4) and are reported as scoped downgrades with the exact reason.
* **Bounded unknowns remaining:** the 355 rows that stay geometry `no-data` even with every
  addition; the 13 new fields, 12 of which no indexer can attribute anything to; the 26
  span-disagreeing citations in §5; the two sibling-descriptor experiments in §5.1; and the
  entire `.txt`/`.hex` era, which neither indexer reads (§7.6).

---

## 7. How this method could have proposed a citation to an experiment that does not contain the evidence

Stated so the next reader can attack it. Three of these fired during the work and changed
the answer; the rest are open.

1. **Matching on the field NAME.** The whole disaster class. Refused three ways — a
   declared `fstart`/`fwidth` that differs from the current span (15 refusals), a declared
   `byte_index` outside the field's current byte span, and K3 group-string substring
   matches (3 refusals). **The K3 rule fired on real data**: `simd_shuffle.src` was being
   proposed on the carrier string `simd_shuffle@dead**src**/compute#0` attached to a
   `_baseline` record. It was in the proposal set for two iterations before I looked at the
   line. **That is exactly how the disaster happens, and the only reason it did not is that
   I opened the file.**
2. **Counting the run plan as the run.** `00_manifest.json` carries `instr`, `field`, `arm`
   and `n_cases` — enough for every indexer in this repository to count it as a record —
   and it sorts first, so it is what a naive locator points at. My first draft published
   `experiments/EXP-0141-m4-emit-mem/raw/m4-20260828-run01/00_manifest.json:70` as the
   evidence for `atomic_tg.op_desc`. A reader who opened it would have found a plan and
   concluded the citation was invented. Fixed by requiring ≥2 records with an execution
   outcome and by pointing the locator at one.
3. **A parent-field sweep credited to a sub-field.** EXP-0214's `half_pack.dst` case. My
   guard is that `distinct_actual_encodings` is decoded from committed bytes **at the
   field's own current span**, not counted from the byte — 40 candidates were refused with
   256 distinct bytes and ONE value of the field's bits. It cost nothing to apply and it
   would have manufactured 40 citations.
4. **Bytes that are no longer this instruction.** A byte sweep through a byte carrying
   `match` bits produces mostly programs that decode to something else. Applied to the
   committed encodings (4 refusals, 10 938 + 4 700 records) and to legacy requested bytes.
   It also *saved* a proposal: `bf_fma_dst.dst` has 512 records of which **480 destroy the
   match**, and the 32 survivors carry all 16 values of the `dst` nibble — the addition is
   made on the 32, not the 512.
5. **Compile-only and program-level credit.** 438 refusals. EXP-0211 held 9 807 compile-only
   records in a separate stream for this reason and I never merged that stream; P4's
   dispatched-program records I do read, and refuse, because "a program containing this
   descriptor executed" is not "this field was exercised".
6. **Where it can still be wrong, and I could not close it:**
   * **The mnemonic is still the experiment's own word.** T1 anchors the *field* to bits
     but the *descriptor* to the record's `instr` string, checked only against that
     descriptor's `match`. A sibling descriptor with identical match bits would pass
     silently. §5.1 shows two experiments where the check fired; it cannot show me the ones
     where it could not.
   * **`bytes` is trusted to be the bytes that ran.** `legacy_index` refuses to synthesize
     dispatched bytes precisely because a synthesized ledger passes by construction. The
     modern harnesses *claim* their `bytes` column is the actual dispatched encoding, and
     for 439 of 456 modern additions the requested value equals the value decoded from it
     at least twice — but if a harness wrote the *requested* encoding into that column, my
     Gate A check is circular and my distinct-encoding count is a restatement of intent.
   * **Cross-arm variation can look like a sweep.** `distinct_actual_encodings` is a set
     over the whole cell. If an experiment sweeps field X while two carriers happen to
     differ in field Y's bits, Y gets ≥2 encodings for free. The byte-index guard catches
     this only when a `byte_index` is declared; for the 438 additions without one the
     defence is that `requested == decoded` at least twice, which a cross-arm accident
     cannot produce. I did not prove that bound is tight.
   * **A locator proves a line exists, not that hardware produced it.** I require an
     outcome from a closed vocabulary. If a harness mis-recorded an outcome, this
     experiment reproduces the error and calls it a record — the same limit EXP-0197 §6.6
     stated.
   * **The refusals are a filter over what two indexers can see.** 1 553 `.txt` files across
     86 experiments and 10 820 `.hex` files yield zero records to both. EXP-0197's strongest
     verdicts live in that era. An experiment can hold real per-field evidence there and get
     no proposal from me; my "zero additions" for those rows is a statement about format,
     not about the hardware, and I cannot bound how many rows it costs.
   * **`_instruction` rows were not examined at all.** 172 of the 1 225 audit rows are
     `<mnemonic>._instruction`. The brief scoped this to field rows and I kept to it; those
     rows' citations are unexamined, and none of the numbers here speaks to them.
   * **One experiment's raw was growing while I read it.** EXP-0213 was writing new
     `g17p_e0213_*` run directories into `experiments/EXP-0204-g17p-tex-carrier-dimensions/raw/`
     throughout this work. Five additions cite EXP-0204, and their record counts, run lists
     and target counts are a snapshot of a directory that has since grown. The additions can
     only get stronger, but the numbers printed beside them are not stable; re-derive them.
   * **One `db.json`, one moment.** Every span in this analysis is the one committed at
     `02a47fc6`. `simd_reduce.op_hi` did not exist six hours ago. A further descriptor
     repair invalidates the span-anchored half of every proposal here, and the fix is to
     re-run `locate.py` and `build_proposals.py`, not to trust this file.

**Self-test:** `python3 scripts/build_proposals.py --selftest` — **20 assertions, 3
must-admit and 12 must-refuse**, plus 5 checks of the match and field-bit helpers in both
directions. The must-admit half is not decoration: a rule set that refuses everything would
have produced the same "zero additions" headline while learning nothing, and it would have
looked like caution.

# EXP-0211 — RESULTS

```
Clean-room provenance: derived analysis of already-committed artifacts in this repository.
Device contacted:      NONE. EXP-0210 held the A18 Pro throughout.
Apple binary read:     NONE.
Inputs pinned:         tools/agx-isa/db.json           sha256 2412eac1cad4449e…
                       tools/agx-isa/validation.json   sha256 f7ba7aa5886de6ac…
                         (frozen to work/validation_frozen.json before the first scoring
                          run, because another agent writes the sidecar concurrently)
Labels changed:        NONE.  Raw files touched:  NONE (read-only).  Committed:  NOTHING.
```

## 0. Headline

**The legacy formats are now parseable, and parsing them moves the dashboards by one row.**

That sentence is the result, and both halves matter.

* 33 760 per-field records were recovered from formats the modern indexer cannot see, over
  **456 distinct `(mnemonic, field)` keys**, with a 13.4 % refusal rate overall.
* Scored through the committed citation graph, that changes **1 of the 417 `no-data` rows**:
  `jump.offset` moves `no-data → records-no-control` on liveness and
  `citation-resolves → auditable` on the evidence chain. Nothing else moves at all.
* The reason is not the format. **It is the citation graph.** A dashboard row only ever
  reads the experiments its own `evidence` list names. Only **36 of 1212** claim rows cite an
  experiment in which this index found any record at all, and the `(mnemonic, field)` keys
  those rows carry are almost never the keys the legacy raw actually supports.
* Repair the citations (a scratch counterfactual, not a proposal) and the same index moves
  **110 geometry rows, 112 liveness rows, 105 limit rows, 76 target rows and 1 semantic
  row** off the bottom rung. **110 of the 112 come from the weakest parser** — whole
  dispatched programs, which earn only `bytes-seen`.

So EXP-0209's §4 limitation 4 is now quantified in both directions: `format-unreadable` was
real, and it was **not** the binding constraint. The binding constraint is that rows cite
experiments that never observed the field.

`jump.offset` is the concrete correction. EXP-0208 §4.1 lists it among "25 rows that held
an emitter-grade label and have no per-field dispatched raw I can find". It has three
dispatched records, in prose, at `EXP-0010-control-flow/raw/run_experiments.log:93–95`:
`offset→0` **HANG**, `offset→+8` **CMDBUF_ERROR**, `offset→−22` **CMDBUF_ERROR**, anchored
to the committed encoding `0f0054d4ffffffffff00` on line 92, which our own disassembler
tokenizes to `jump` with `offset` at bits 24..71.

---

## 1. The format inventory

274 experiment directories. **226 have a `raw/` tree; 48 have none.** Of the 226,
**185 yield zero cells to `evidence_index.py`** — that is the size of the invisible era, and
it is six times larger than the 29 directories EXP-0197 examined.

| ext | files | bytes | experiments | what it is | machine-readable to the modern indexer |
|---|---:|---:|---:|---|---|
| `.hex` | 10 820 | 1 724 335 699 | 40 | whole compiled program dumps, one per shader | no |
| `.json` | 6 704 | 35 421 843 | 125 | per-case process captures; payload nested in a `stdout` string | only if a record carries `instr`+`field` |
| `.txt` | 1 553 | 49 777 595 | 86 | narrated validation transcripts, field tables, main-hex listings | no |
| `.log` | 1 003 | 13 984 124 | 41 | splice-and-observe transcripts and dense sweep tables | no |
| `.jsonl` | 907 | 2 443 367 857 | 98 | the modern sweep format (and legacy unkeyed streams) | mostly yes |
| `.bin` | 735 | 19 597 712 | 6 | binaries | no (skipped) |
| `.meta` | 586 | 83 488 | 4 | per-trial metadata | no |
| `.out` / `.stdout` / `.stderr` | 251 | 99 739 | 11 | captured tool output | no |
| `.metal` / `.py` / `.m` / `.c` / `.sh` | 74 | 143 755 | 14 | authored probe copied beside the raw | n/a |
| `.md` | 45 | 91 033 | 30 | per-run notes | n/a |
| `(noext)` / `.trace` / `.err` | 34 | 351 485 | 12 | misc | no |

Full table with the per-experiment breakdown: `analysis/format_inventory.json`.

Within those extensions the distinct **record shapes** that carry per-field observations are
few. Line-shape census over all 3 394 raw text files (977 620 lines):

| shape | lines | files | experiments |
|---|---:|---:|---:|
| dense sweep row (`0xVV  OK  <class>  [obs]  raw=…`) | 5 443 | 25 | 5 |
| bracketed status token (`[OK]`/`[HANG]`/`[CMDBUF_ERROR]`/`[PASS]`) | 8 374 | 37 | 8 |
| `splice … ->` | 77 | 18 | 15 |
| `0xAA->0xBB` byte substitution | 152 | 35 | 20 |
| `out=… exp…=… PASS` | 96 | 8 | 4 |
| `main[NN]` index | 52 | 4 | 3 |

And within the 6 704 raw `.json` files, 290 distinct top-level key sets; the dominant one is
the process capture `argv|cwd|exception|exit|started_utc|stderr|stdout|timed_out|timeout_seconds`
(3 847 files, 13 experiments), whose real payload is a JSON document inside the `stdout`
string. Of the inner payload shapes, only two families carry a per-field splice
(`applied_splices`, 246 files in EXP-0114) and only one family carries program bytes beside
a render result (`main_hex` + `render`, EXP-0050). **Everything else in the `.json` era is a
capability or format census, not a field sweep** — that is a finding, not a parser gap.

---

## 2. Records extracted, by format and by parse confidence

**33 760 records** over **456 distinct `(mnemonic, field)` keys**, plus **9 807 compile-only
records held in a separate stream and never merged**.

| parser | records | confidence | distinct keys | source |
|---|---:|---|---:|---|
| `P1` byte-sweep table | 7 936 | `table` | 26 | `.log` |
| `P3` absolute-offset sweep | 176 | `table` | 2 | `.log` |
| `P5` key/value dispatch record | 4 | `table` | 2 | `.log` |
| `P2` prose splice | 51 | `prose` | 19 | `.log` |
| `P4` dispatched program corpus | 25 593 | `structured` | 454 | `.json` (20 682), `.jsonl` (4 911) |
| `C0` compile-only (**not merged**) | 9 807 | `structured` | — | `.json` |

`parse_confidence` is on every record, with `_src_file` and `_src_line`, so a consumer can
weight or exclude by provenance. `structured` means the source was machine-readable JSON;
`table` means a fixed-column table under a stated header; `prose` means an English sentence
anchored to committed bytes. The 51 `prose` records are the ones that would be hardest to
defend, and they are individually citable to a line.

**Coverage of the inventory is thin and unevenly so, which is the honest picture:**

| ext | files in raw | files that yielded a record | experiments | experiments that yielded |
|---|---:|---:|---:|---:|
| `.log` | 1 003 | 27 | 41 | 8 |
| `.json` | 6 704 | 53 | 125 | 3 |
| `.jsonl` | 907 | 3 | 98 | 1 |
| `.txt` | 1 553 | **0** | 86 | **0** |
| `.hex` | 10 820 | **0** | 40 | **0** |
| `.out`/`.stdout`/`.meta` | 827 | **0** | 14 | **0** |

**`.txt` yields nothing, and that is the single largest remaining gap.** §6 says why.

---

## 3. The unparsed fraction — reported per parser, with the reason

**852 of 6 359 candidate lines/records were refused: 13.4 % overall.** A "candidate" is a
line or record that matched a parser's trigger and was then adjudicated.

| parser | candidates | refused | % | emitted | refusal reasons |
|---|---:|---:|---:|---:|---|
| `P1` | 5 464 | 344 | 6.3 % | 7 936 | `no_anchor_bytes_in_header` 344 |
| `P2` | 194 | 153 | **78.9 %** | 51 | `splice_line_shape_not_modelled` 126, `no_live_anchor` 21, `named_target_is_not_a_db_field` 2, `no_db_field_covers_that_byte` 2, `ambiguous_anchor` 2 |
| `P3` | 88 | 0 | 0 % | 176 | — |
| `P4` | 607 | 351 | **57.8 %** | 25 593 | `program_bytes_with_no_execution_outcome` 351 (→ the compile-only stream) |
| `P5` | 6 | 4 | **66.7 %** | 4 | `splice_changes_descriptor_identity` 3, `no_byte_changed` 1 |

Records exceed candidates for `P1`/`P3` because one swept byte can be covered by more than
one `db.json` field, and each gets its own record — the same fan-out `evidence_index`'s K2
keying performs.

Three refusals are worth naming individually because they are correct in a way that
matters:

* **`P2 / no_db_field_covers_that_byte` on `splice stop b0 0x0e->0x00`** — byte 0 of `stop`
  is its `match`, not a field; `db.json` gives `stop` only `reserved` at bits 8..31. The
  parser refuses without being told to.
* **`P5 / splice_changes_descriptor_identity`, 3 of 6** — EXP-0003's
  `SPLICE _agc.main@0x34: 0e000000 -> ffffffff` and `-> 00000000`. The spliced program no
  longer tokenizes to `stop` at that offset, so it is not evidence about `stop.reserved`.
  **This independently reproduces EXP-0197 §4.4 from the raw**, by a rule written before
  that section was consulted for this case.
* **`P2 / ambiguous_anchor`, 2** — EXP-0013's `val_conv_fma.log` has two `ALU=` encodings
  live when the splice line appears. Proximity would have picked one. The parser refuses.

---

## 4. The seven dashboards, before and after

All six runs score the same frozen sidecar and the same `db.json`. `base` is the before.
The full ladder for every run is `analysis/dashboard_delta.json`; `work/reports_*/` holds
each run's own reports.

Denominators: geometry / liveness / semantics / target **1040** (every `db.json` field);
recipe **166**; audit **1212** (every `validation.json` claim row); limits **987**
(fields ≤ 8 bits).

### 4.1 With the citation graph as committed (`base` → `m2`)

| # | dashboard | rung | base | M1 (text only) | M2 (all) | Δ |
|---|---|---|---:|---:|---:|---:|
| 1 | geometry | `no-data` | 417 | 417 | 417 | **0** |
| | | `bytes-seen` | 62 | 62 | 62 | 0 |
| | | `ledger-verified` | 54 | 54 | 54 | 0 |
| | | `geometry-mapped` | 507 | 507 | 507 | 0 |
| 2 | liveness | `no-data` | 417 | 416 | 416 | **−1** |
| | | `records-no-control` | 464 | 465 | 465 | **+1** |
| | | `decided-one-carrier` | 52 | 52 | 52 | 0 |
| | | `decided-multi-carrier` | 107 | 107 | 107 | 0 |
| 3 | semantics | all four rungs | 962 / 58 / 5 / 15 | = | = | **0** |
| 4 | recipe | all four rungs | 148 / 14 / 2 / 2 | = | = | **0** |
| 5 | target | all four rungs | 425 / 177 / 3 / 435 | = | = | **0** |
| 6 | audit | `incomplete` | 365 | 365 | 365 | 0 |
| | | `citation-resolves` | 247 | 246 | 246 | **−1** |
| | | `auditable` | 328 | 329 | 329 | **+1** |
| | | `independently-confirmed` | 272 | 272 | 272 | 0 |
| 7 | limits | all four rungs | 391 / 76 / 386 / 134 | = | = | **0** |

The single moving row is `jump.offset`. Its `base` reason string was, verbatim:
*"cited raw holds 33 non-record file(s) (.txt/.log/.hex) and 0 machine-readable records:
FORMAT-UNREADABLE, not absent"*. Its `m2` reason is *"3 record(s) but no detection-power
control in the cited raw — Gate B: zero movement without a firing control is
carrier-undecidable, not inertness"*. Three records is exactly what
`run_experiments.log:93–95` contains.

Geometry does **not** move, by construction: rule 1 forbids synthesizing dispatched bytes,
so the legacy transcripts carry no Gate A ledger and cannot reach `bytes-seen`.

### 4.2 With the citation graph repaired (counterfactual: `m3ctl` → `m3lite` → `m3`)

`m3ctl` is the control: the same repaired citations, scored against the **unmodified**
index. `m3 − m3ctl` is therefore the legacy index's own contribution.

| # | dashboard | bottom rung | `m3ctl` (citations only) | `m3lite` (+ text parsers) | `m3` (+ all parsers) | legacy Δ |
|---|---|---|---:|---:|---:|---:|
| 1 | geometry | `no-data` | 413 | 413 | **303** | **−110** |
| 2 | liveness | `no-data` | 413 | 409 | **301** | **−112** |
| 3 | semantics | `no-semantic-check` | 962 | 961 | **961** | **−1** |
| 4 | recipe | `not-generated` | 148 | 148 | 148 | **0** |
| 5 | target | `no-direct-target-evidence` | 421 | 421 | **345** | **−76** |
| 6 | audit | `incomplete` | 578 | 578 | 578 | **0** |
| 7 | limits | `no-data` | 387 | 384 | **282** | **−105** |

Where those rows land:

* geometry `bytes-seen` 62 → 172; `geometry-mapped` unchanged at 511.
* liveness `records-no-control` 443 → 549, `decided-multi-carrier` 122 → 168.
* target: every one of the 76 lands on `G16G-direct-only` (177 → 253). Not one reaches
  `G17P-direct`; the legacy era is M4 and A18-pre-pivot, and its run directories say so.
* limits `partial-sweep` 76 → 180, `limit-mapped` 135 → 138.
* audit `auditable` 158 → 177 and `independently-confirmed` 271 → 290 — but `incomplete` is
  unchanged at 578, because the counterfactual citations themselves already pushed it there.

**The `m3lite` column is the load-bearing one.** The legacy *text transcripts* — the thing
this experiment was commissioned to unlock — move geometry by **0**, liveness by **4**,
limits by **3**, semantics by **1**. Everything else comes from `P4`, the dispatched
program corpus, which credits `bytes-seen` to every field of every instruction in a program
that ran. That is honest evidence at the ladder's rung 1, and it is nothing more: it says
"a program containing this descriptor executed", not "this field was exercised".

### 4.3 Recipe and audit did not move, and should not have

Dashboard 4 reads the generated-recipe registry, not the evidence index, so no indexer can
touch it — the same cross-dashboard independence EXP-0209 demonstrated. Dashboard 6's
top rung needs ≥ 2 raw runs plus a second carrier or experiment; the legacy tree is flat
(`raw/*.log`, no run directories), so this tool assigns it exactly **one** run per
experiment. A file is not a run, and inventing one per file would have manufactured
`independently-confirmed` out of a directory listing.

---

## 5. Which of the `no-data` rows become populated, and which stay

EXP-0209 reported **420**. Against the sidecar frozen for this run the figure is **417**;
the sidecar has been written since. Both numbers are quoted so the difference is not
mistaken for movement.

| | geometry | liveness | limits | target | semantics |
|---|---:|---:|---:|---:|---:|
| bottom rung, `base` | 417 | 417 | 391 | 425 | 962 |
| **populated under the committed citations** | **0** | **1** | **0** | **0** | **0** |
| the legacy index holds records for the key (citation-blind) | 117 | 117 | 109 | — | — |
| **populated with citations repaired** | **110** | **112** | **105** | **76** | **1** |
| **still bottom rung after everything** | **303** | **301** | **282** | **345** | **961** |

The one row is `jump.offset`. Per-key lists: `analysis/nodata_movement.json`.

**Why the 303 stay `no-data`** (`analysis/nodata_residue.json`), grouped by what they cite:

| cited evidence | rows | why "no data" is the correct answer |
|---|---:|---|
| `EXP-0036` + `EXP-M4-12` + `EXP-M4-13` | 105 | byte0-group census / residue closure / full-corpus convergence — **compile-only, no dispatch**, exactly as `validation.json`'s own `_conventions` says. EXP-0208 §4 reached the same conclusion for the same rows. |
| *no citation at all* | 33 | `bf_mul_dst.*`, `rt_*`, `h_alu_hi_ext.*` … nothing to open |
| `EXP-0156` | 32 | a modern `.jsonl` experiment; its raw simply does not carry these fields |
| `EXP-M4-14` | 29 | the experiment marks these rows `NOT HW-splice` in its own provenance |
| `EXP-0148` | 18 | token-resync framing census — 2.9 M records, no field values |
| `EXP-M4-13` alone | 12 | compile-only, as above |
| `EXP-0171` | 9 | swept a sibling descriptor, explicitly not counted |
| `EXP-O2C`, `EXP-0162`, `EXP-0139`, `EXP-0147`, `EXP-0180`+`EXP-0183`, … | 65 | corpus census or a different field of the same descriptor |

**So the residue is not a format problem.** 117 of the 303 residual rows citing the
compile-only census experiments would still be `no-data` under any parser, because those
experiments dispatched nothing. The remaining format-shaped debt is §6.

---

## 6. Where this instrument is still blind, stated as numbers

1. **`.txt` yields zero records from 1 553 files across 86 experiments.** This is the
   narrated era and it is where several of EXP-0197's strongest FALSE verdicts live. The
   shape is the problem, not the parser: `EXP-0037/raw/hw_validations.txt` reads
   `store4(va.x).b4 0x80->0x00 (abs 12296)   TL/TR/BL=0,0,0,0 (BLACK) …`, and the only
   statement of *which instruction* byte 12296 belongs to is an English sentence eleven
   lines earlier ("The 8 varying stores (each 8 bytes: 57 b1 b2 SRC SLOT 40 b6 00) at
   main-off 100..156"). Turning that into `vary_store.out_slot` requires reading prose and
   trusting it. **A future experiment can make this era machine-readable for one line of
   extra output: print the instruction bytes on the splice line.** EXP-0010 and EXP-0012 do,
   and they are the two `.log` experiments this tool reads successfully.
2. **`P2` refuses 78.9 % of its candidates.** 126 of those are shapes not modelled and 21
   are splices whose anchor is out of scope (e.g. `splice load +5 0x04->0x01` in
   `EXP-0012/raw/mem_probe.log:39`, where "load" is an English word and the last committed
   encoding is more than twelve lines back). Widening the anchor window or matching "load"
   to `device_load` by substring would recover them and would be a guess.
3. **`.hex` — 10 820 files, 1.7 GB — is not read at all**, because a program dump with no
   outcome beside it is compile-only under rule 3. EXP-0209's `--deep` K4 tokenization is
   the right instrument for that population and it remains opt-in.
4. **456 of 1040 field keys were touched.** 411 of them only by `P4`, and only 2 keys are
   reached by the text parsers and not by `P4`.
5. **The `.json` era is mostly not field evidence.** 3 847 of 6 704 raw `.json` files are
   process captures of capability/format census cases; they carry a real dispatched result
   and no `(mnemonic, field)` at all. EXP-0114's 246 `applied_splices` records are the
   sharpest loss: they pair a requested value with an observed `out_word_hex` **and** a
   pre-registered expectation in `CAPTURE_CONTRACT.json`, but they state the splice as a
   `rel_offset` into a program the experiment never commits. Nothing in the corpus resolves
   that offset to an instruction. They are reported as unattributable, not invented.

---

## 7. Self-test: the parser must be able to say "no"

`python3 tools/agx-isa/legacy_index.py --selftest` — **35 assertions, 13 must-extract and
15 must-refuse**, plus attribution and record-shape checks. The must-extract half is not
decoration: a parser that refuses everything is as broken as one that refuses nothing, and
it would have hidden the whole point of this experiment behind a zero.

**Must extract** — all from text taken verbatim from committed raw:

* `jump.offset → 0` from `EXP-0010/raw/run_experiments.log` as a **HANG**, with the anchor
  `0f0054d4ffffffffff00`; and `offset → +8` as `cmdbuf_error` from the next line.
* `splice +12 0x46->0x42` on `6710440001012000510100404600` reaches
  `device_load.elem_size` (byte 12), outcome `ok`.
* RT-5's `[a_reg(+5)=b_reg 0x08 …] STATUS OK` against `cf02560200040809d4432401` reaches
  `matrix_mac.a_reg`.
* EXP-0013's `out=[…] exp abs=[…] PASS` emits an `oracle` and `sem_match` — a Gate C check,
  not a liveness prediction.
* a `P1` sweep row and a `P1` `FAULT:CMDBUF_ERROR` row.
* `P4` program bytes **with** a committed outcome.
* `P5` emits the requested byte **and** the actual dispatched bytes.
* `main[4]` resolves through a committed program to the instruction that owns that byte.
* `P3` resolves an absolute offset when exactly one candidate program matches.

**Must refuse** — each is a real line, or a one-character mutation of one:

* `splice cp[0] 0x03->0x00` and `splice cp[0:4]->0e000000` — the **constant program**, not
  an instruction. Both are in `EXP-0010/raw/run_experiments.log` two lines from records the
  parser does accept.
* a splice with no anchored bytes; an anchor whose bytes our own disassembler cannot
  tokenize; two live anchors (ambiguous); a splice with no outcome token.
* `splice stop payload->ff` — `payload` is not a `db.json` field of `stop`.
* `splice +9` on a 4-byte `stop` — outside the instruction.
* `[a_reg(+9)=…]` — the named field's own bit span says byte 5, so the line contradicts
  itself.
* a sweep table with no committed baseline encoding; a sweep table with no stated byte index.
* program bytes with **no** outcome → compile-only, never a dispatch record.
* `P3` with two candidate programs of the stated length.
* `P5` where the replacement destroys the descriptor's match bits.
* the attributor: odd-length hex, non-hex, a byte past the descriptor length, a field name
  not in `db.json`.
* and the shape checks: the emitted record is admitted by `evidence_index`'s **own**
  `Indexer`, and a `hang` is not counted as a valid payload.

---

## 8. How this parser could have manufactured a record

Stated so the next reader can attack it. Each was a real temptation with a real payoff in
dashboard movement, and each is refused by a rule that is self-tested.

1. **Reconstruct the dispatched bytes.** Every `P1` sweep states a baseline encoding, a byte
   index and a requested value. Writing `bytes = baseline with byte[i] := value` would have
   given 7 936 records a Gate A ledger — one that passes **by construction**, because it
   assumes the splice landed. That is the DEF-0166 failure exactly: a requested bit the
   assembler could not clear would still "agree". **This is the single largest fabrication
   available here**, and refusing it is why geometry moves by 0 in `m1` and by 0 in
   `m3lite`. The zero in that column is the rule working, not the parser failing.
2. **Anchor by proximity.** Taking the nearest preceding hex blob as "the instruction" would
   have attributed `splice cp[0] 0x03->0x00` to whatever ran last, and would have resolved
   EXP-0013's two live `ALU=` encodings by picking one. Refused by section scope, a
   twelve-line window, and an explicit ambiguity check.
3. **Match a prose target to a field by name similarity.** `payload → reserved`,
   `offset_field → offset`, `load → device_load`, `store4.b4 → vary_store.out_slot`. Exact
   `db.json` membership only; 2 refusals plus the whole of §6.1 and §6.2 are the cost, and
   the cost is correct.
4. **Widen the outcome vocabulary.** `NO CHANGE` in EXP-0037 would have become an inertness
   observation; a bare `FAIL` would have become a hardware outcome rather than a possible
   measurement failure. The vocabulary is closed, and `FAIL` is accepted only in the
   `out=/exp=` form where the observation and the prediction are both printed.
5. **Count compiled bytes as dispatched.** 9 807 compile-only records would have moved
   geometry to `bytes-seen` and limits to `partial-sweep` for programs that never ran —
   liveness rung 1's own definition is "dispatched". They are in
   `index/compile_only_records.jsonl` and are never merged. Admitting them would roughly
   have doubled §4.2's counterfactual movement on pure compile evidence.
6. **Skip the match-bit check in `P5`.** EXP-0003 spliced `0e000000 → ffffffff` over the
   `stop`; without the check that becomes `stop.reserved = 0xffffff, STATUS OK` — a clean,
   citable, **false** hardware-run record for a row that is currently and correctly
   `untested`. EXP-0197 §4.4 identified this by hand; the parser refuses it by rule.
7. **Promote the README's device line into the `target` axis.** Every pre-EXP-0046 README
   carries `**Device state:** Apple A18 Pro / G17P …`. Parsing that would have credited
   **248 field rows** with direct-target evidence on the strength of a sentence in a
   markdown file. Target is derived only from run-directory names, exactly as
   `evidence_index._target_of_run` derives it, so every one of those rows still reports no
   direct target.
8. **One run per file.** The legacy tree is flat, so naming each `.log` a "run" would have
   given EXP-0007 sixteen runs and pushed rows to `independently-confirmed` on a directory
   listing. A flat tree is one run.

**Where it could still be wrong, and I could not close it:**

* **`P4`'s status pairing.** The execution outcome is searched at the top level of a record
  and one level into child dicts, because EXP-0050 nests it under `render`. If a single
  raw record ever held two cases side by side, one case's bytes could be paired with the
  other's status. I bounded the search to one level; I did not prove no such file exists.
  Every `P4` record names its file and its position so the pairing is checkable.
* **`P4` is a program-level credit.** It attributes the dispatched bytes to **every** field
  of every instruction in the program. That is what `bytes-seen` means and it is the rung it
  earns, but a reader skimming §4.2's 110-row movement could easily read it as per-field
  evidence. It is not.
* **Tokenization is our own.** Every attribution rests on `tools/agx-isa/isadb.py`. A wrong
  descriptor length in `db.json` would silently mis-attribute a byte index to the wrong
  field, in this tool and in `evidence_index.py` alike. The `hex` and the byte index are on
  every record so a later `db.json` fix can re-derive without re-parsing.
* **Coverage is not proven complete.** The parsers were written from a line-shape census
  over 977 620 raw text lines and 290 JSON key sets. A shape present in one file and
  matching no trigger is invisible to exactly the procedure that found the others; it is
  counted in neither `records` nor `unparsed`, because it never became a candidate.

---

## 9. What this experiment did and did not establish

* **New raw observations:** none. No device was touched.
* **New geometry facts:** none about the hardware. One about the evidence: the legacy text
  era can produce liveness and outcome evidence but **cannot** produce a Gate A ledger,
  because it does not commit the dispatched bytes — except EXP-0003, which does, in 2 of
  its 6 splice records.
* **New liveness facts:** none about the hardware. `jump.offset` has three dispatched
  records (1 hang, 2 faults) that were previously unreadable; EXP-0208 §4.1's "no per-field
  dispatched raw I can find" for that row is superseded.
* **New semantic facts:** none. One row gains a `checks-present` rung under the
  counterfactual, from EXP-0013's `out=/exp=/PASS` pairs.
* **New generated recipes:** none.
* **Claims downgraded:** none. No label was changed and nothing was retracted.
* **Bounded unknowns remaining:** the `.txt` era (1 553 files, 86 experiments, 0 records);
  EXP-0114's 246 unattributable per-case splices; `P2`'s 147 refused splice lines; and the
  303 rows that stay `no-data` because the experiments they cite dispatched nothing.

The actionable consequence is not a relabel. It is that **the largest single lever on the
`no-data` figure is the citation graph, not the indexer** — 117 of the 417 `no-data` rows
have records somewhere in the corpus under their own key, in an experiment they do not
cite. Repairing those citations is a desk task with a measurable ceiling (§4.2), and it must
be done row by row with the target and authored-probe consequences in view, because the
blanket counterfactual used here to *measure* the ceiling also pushes 213 audit rows from
`citation-resolves`/`auditable` down to `incomplete`.

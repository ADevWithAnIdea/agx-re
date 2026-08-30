# EXP-0166 — PRE-REGISTRATION

**Frozen:** 2026-08-30, before any adjudication script was written or run.
**Repo revision at freeze:** `b7dedbf0` (working tree dirty — see §7 for the exact pinned inputs;
per `SUBAGENT_BRIEF.md` the gate is the *authored blob hashes*, not live `HEAD`).
**Target of the evidence under adjudication:** Apple **M4 / G16G** (EXP-0146's only target).
**Target of this experiment:** none by default — this is an **offline re-derivation** from
committed raw evidence. A device arm on the A18 Pro / G17P is pre-registered in §6 as
*conditional* and may only run after the offline analysis is complete.

---

## 1. The question

`experiments/EXP-0146-m4-emit-int-misc/analysis/field_verdicts.json` contains 94 field verdicts,
all labelled `hardware-run`, none of which ever reached `tools/agx-isa/validation.json`. The
mechanical cause is a key-convention mismatch: EXP-0146 keys its verdicts
`<mnemonic>.<field>@<carrier>`, and `work/merge_verdicts.py` requires exactly
`<mnemonic>.<field>`, so every key was rejected as "not a field of \<mnemonic\> in db.json" and
the whole file was skipped.

**The question is not "can the keys be renamed".** It is: *which of those 94 verdicts still
survive as defensible, mergeable, emitter-grade evidence, given (a) a re-derivation from
EXP-0146's own raw records rather than from its analysis JSON, and (b) the later G17P work that
has overtaken parts of EXP-0146's interpretation?*

Why it matters: each surviving row moves one ISA field from `corpus-correlation` /
`tokenization-only` toward emitter grade, and `n2_op10` / `n2_op8` / `irotate` / `mov_zext16` /
`n3_mov` each have **all or most** of their fields below emitter grade today, so a field-complete
recovery would change instruction-level emittability counts in `validation.json`.

## 2. Hypotheses

- **H1 (recoverability).** A majority of the 94 EXP-0146 verdicts do **not** survive the liveness
  policy in §4, because EXP-0146's oracle is the *unmutated baseline output*, so its "ok at
  {N values}" sets measure **inertness**, not demonstrated control of the field.
- **H2 (per-carrier split matters).** For at least one field swept on two carriers (`n2_op6` is
  the only such field in EXP-0146), the two carriers give materially different accept-sets, so
  flattening the `@carrier` suffix would silently destroy information.
- **H3 (constraints that are really fields).** At least one EXP-0146 "exact rule" of the form
  `(v & M) == K` is not a legality constraint but an unmodelled **operand sub-field**: the
  supposedly-forbidden bits select a register/operand and therefore encode information the
  descriptor does not expose. Concretely pre-registered: `iadd2.srcB_ext` in the `u64sub` carrier.
- **H4 (raw byte probes are descriptor defects).** Of the EXP-0146 keys that are not `db.json`
  fields at all (`<mnemonic>.byte+N`, plus fields since split or renamed), a non-empty subset
  demonstrates that `db.json` is **missing a field** or mis-typing a `match` bit as invariant.

## 3. Falsifiers (pre-registered; at least one must be checkable in the data)

- **F1 — refutes H1.** If ≥ 60 of the 94 verdicts pass §4 as `stable-live`, H1 is refuted and
  EXP-0146's verdict file was substantially correct and merely mis-keyed.
- **F2 — refutes H2.** If `n2_op6`'s six fields produce identical accept-sets and identical
  liveness verdicts on both the `u64eq` and `sfu_sin` carriers, the per-carrier split carried no
  information for this file and the `@carrier` convention was pure overhead.
- **F3 — refutes H3.** If, across EXP-0146's `iadd2.srcB_ext` sweep, the 124 values excluded by
  `(v & 0x7C) == 0x00` produce outputs that are **not** explicable as a different source-register
  selection (e.g. they fault, or they silently zero, or their outputs bear no monotone relation to
  a register index), then the "constraint" reading stands and H3 is refuted for this field.
- **F4 — refutes H4.** If every `byte+N` probe's accept-set is exactly the singleton the `db.json`
  `match` list already fixes, then the raw probes only re-confirm the match bits and reveal no
  missing field.
- **F5 — method sanity / positive control.** `carry_gen.byte+2` must reproduce
  `(v & 0xCD) == 0x05` from EXP-0146's raw under my own re-derivation. EXP-0161 independently
  found the identical rule on G17P (DEF-0161-6). If my re-derivation does **not** reproduce it,
  my pipeline is wrong and every other number in this experiment is void.

## 4. The adjudication policy — thresholds fixed here, before any statistic is computed

### 4.1 Inputs used, and inputs excluded

- **Gated runs:** `raw/run01/sweep.jsonl` and `raw/run03/sweep.jsonl` only.
- **`raw/run02/` is EXCLUDED** — EXP-0146 declared it contaminated (M7) and retained it
  append-only. I do not re-admit it.
- **`raw/run04/` (adjudication, 5 serial repetitions per case) is used ONLY to classify a value's
  behaviour when the two gated runs disagree.** It never rescues a field's *agreement rate*
  (§4.4), which is a stability metric and is computed on run01-vs-run03 alone.
- **`raw/run05/`, `raw/run06/`, `raw/trial00/`, `raw/pilot/`** are context, not verdict inputs.

### 4.2 The observable

For a case record `r`, the observable is the pair

```
(outcome_class(r), tuple(r["observed"].get("words", [])))
```

`outcome_class` ∈ {`ok`, `wrong_value`, `silent_zero`, `fault`, `hang`, `undecodable`}.

**Informativeness filter** (FIELD-SWEEP-PROTOCOL §7, instrument 3): a run's observation for a
value is **non-informative** iff `observed.fault_class == "innocent_victim"` — it was discarded as
the victim of another context's error and carries no information about our bytes. Non-informative
observations are dropped from both numerator and denominator. `run01` predates the `fault_class`
field entirely, so no `run01` observation can be classified as a victim; this is recorded as a
known limitation, not silently patched.

**Baseline** for an arm `(instr, carrier)` is that arm's `_baseline` record **within the same
run**. A value "moved an observable" iff its observable differs from that run's baseline
observable.

### 4.3 Per-value classification (over values where both gated runs are informative)

| symbol | definition |
|---|---|
| `N` | values where both run01 and run03 are informative |
| `D` | of those, values where the two observables **differ** between runs |
| `M` | of those, values where the two observables **agree** and **differ from the arm baseline** |
| `I` | of those, values where the two observables **agree** and **equal the arm baseline** |

`N = D + M + I`.

### 4.4 The three verdicts — thresholds

- **`stable-live`** iff `M ≥ 1` **and** `(M + I) / N ≥ 0.99` **and** `M ≥ 2·D`.
- **`inert-envelope`** iff `M == 0` **and** `(M + I) / N ≥ 0.99` **and** the same field was swept
  inert on **≥ 2 structurally different carriers** — either two carriers inside EXP-0146, or one
  EXP-0146 carrier plus a corroborating independent experiment on a different carrier.
- **`withheld`** — everything else. Explicitly including: `M == 0` on exactly one carrier
  (however dense the sweep); and any field whose movement fails the 99 % / 2× reproduction test.

**Representative arm.** Where a field was swept on more than one carrier, the merged row takes the
**strongest** arm (`stable-live` > `inert-envelope` > `withheld`; ties broken by larger `M`, then
larger `N`). **If two carriers disagree in verdict class, that disagreement is reported as a
finding in `RESULTS.md` and both arms' counts are carried in the merged row** — it is never
silently collapsed.

### 4.5 Label mapping (the 8 labels of `docs/evidence-classification.md`, nothing else)

- `stable-live` → **`hardware-run`**. Justified: arbitrary values including boundaries and holes
  were executed, and the field demonstrably controls the observable.
- `inert-envelope` → **`isolated-byte-diff`**, never `hardware-run`. A field that never moves an
  observable has not had "arbitrary operands execute"; what was shown is that the program still
  runs with the predicted effect across the envelope. This is deliberately one notch weaker than
  EXP-0146 claimed.
- `withheld` → **not merged at all**; it goes to `analysis/withheld.json` with reason and numbers.
  It is *not* emitted as a downgrade row, because `merge_verdicts.py` refuses weakenings and a
  withheld verdict is an absence of evidence, not a refutation.

### 4.6 Hard gates applied on top of the statistics (a row must clear ALL of them)

1. **G1 — db.json field existence.** `<field>` must be a field of `<mnemonic>` in the pinned
   `tools/agx-isa/db.json`. Non-fields (`byte+N`, split/renamed fields) are ineligible for
   `analysis/field_verdicts.json` and are routed to `analysis/proposed_db_defects.json`.
2. **G2 — no downgrade.** If the pinned `validation.json` already records the field at a label ≥
   the one I would assign, the row is dropped as redundant (reported, not merged).
3. **G3 — later-experiment veto.** If a later experiment (esp. on G17P) **contradicts** EXP-0146's
   interpretation of the field, the row is withheld and the divergence reported. Contradiction
   means: the later experiment found the field inert where EXP-0146 called it live, found it live
   where EXP-0146 called it inert, found no carrier for the instruction at all, or repaired the
   descriptor such that EXP-0146's byte boundaries no longer name the same bits.
4. **G4 — target labelling.** Every merged row carries `"target": "M4/G16G"` verbatim and
   `"evidence": ["EXP-0146", "EXP-0166"]`. Closure is measured against G17P, so these rows are
   **supporting evidence, never closure evidence**, and must never be relabelled `A18`/`G17P`
   without a fresh G17P run.
5. **G5 — no `db.json` edits.** `tools/agx-isa/db.json` is owned by EXP-0165 this session. This
   experiment reads it and proposes defects in a JSON file; it never writes it. Likewise
   `validation.json`, `docs/`, `PROVENANCE.md`, `work/merge_verdicts.py` are read-only here, and
   nothing is committed.

## 5. Confounders acknowledged in advance

1. **The oracle is the unmutated baseline.** EXP-0146's `match` flag means "output equals the
   *unmutated* program's output", so `match: true` means the mutation was **inert**, and the
   published "ok at {…}" sets are inert-sets. Any reading of those sets as "the field works at
   these values" is a category error, and my re-derivation must not repeat it.
2. **Concurrency contamination.** EXP-0146 §2 measured up to 22 wrong answers per 100 identical
   unmutated dispatches while sibling agents ran. run01 lacks `fault_class`, so victim cases in
   run01 are invisible. The 99 %/2× thresholds are set to survive a background error rate of that
   order, but a field near the threshold is reported as near-threshold, not rounded up.
3. **Carrier scope.** A value that reproduces the baseline may be inert *or* invisible to this
   carrier. §4.4 encodes this: single-carrier inertness is never promoted.
4. **Descriptor drift.** `db.json` has changed since EXP-0146 ran (e.g. `ilogic.lut_a` has been
   split into `lut_a_sel`/`lut_a_free`/`lut_a_z`; `carry_gen` now declares a `srcB`). A byte
   offset that named field *X* in August may name a different field now. G1 + G3 handle this.
5. **`db.json` is being edited concurrently by EXP-0165.** I pin its SHA-256 at freeze (§7) and
   re-check it at write time; if it changed, I report the drift rather than silently re-deriving.

## 6. Conditional device arm (may not start before the offline analysis is complete)

A confirmation run on the A18 Pro / G17P (`users-MacBook-Neo.local`, currently `192.168.10.243`,
SSH user `user`, working dir `~/agxre/EXP-0166/`) is permitted **only** if all of:

- a field's M4-vs-G17P status is genuinely undecidable from committed data; **and**
- that field is load-bearing for an instruction's emittability (i.e. it is the last non-emitter-
  grade field of its mnemonic, or one of few); **and**
- the offline deliverables (§8) already exist on disk.

If run, it takes a fresh run id under `raw/`, artifacts are pulled back to this directory before
any conclusion is drawn, and `macvdmtool` is **never** invoked (subagent prohibition). If the neo
becomes unresponsive: STOP and report BLOCKED.

## 7. Frozen inputs (SHA-256)

```
a55a574bdc4ec51f3c455c0b820bf807ff94ea7fd155c65a8e329061415f98f3  EXP-0146/raw/run01/sweep.jsonl
99529b1445cceb5be68fb704beb2e1f0749dfec8bbcf37bb14e7dcf25a49d742  EXP-0146/raw/run02/sweep.jsonl  (EXCLUDED)
47357d772da1e407ababff2b919128f3a13f9a5683aba6769683ead77b012e2a  EXP-0146/raw/run03/sweep.jsonl
c72794bbcf357c20ae29e4a7dcf6237d45182559580aa4bd4e8d67925f46f0c8  EXP-0146/raw/run04/sweep.jsonl
ce0a392a05d268bf1c0427b26d8dfaaea2b00cca897b4f9a0201678263f1c315  EXP-0146/raw/run05/sweep.jsonl
a1af2de9ddf7e22056cdffa6b1b7b2b54e9204453a7f3d3caf0bef75dae99d62  EXP-0146/raw/run06/sweep.jsonl
fec9d594f605a227fecce32acad958432855dc281c36d7ede076f65223a49c85  EXP-0146/raw/trial00/sweep.jsonl
5dff397b31146a6e9ea944eb59ae8f47d3253ac06e16f9a9a9f5fe04267cb825  EXP-0146/analysis/field_verdicts.json
2a85a497426039a632c22544dfeeb5ea3389ca5b86bc8ea37f597e3dd38bbc27  EXP-0146/harness/arms.py
83b83a350ece33b8fd9e98b773f02be2da89a5f942824896574ff22827042341  tools/agx-isa/db.json
94e229c1cac73f0404e67f8864c53981dc62fa408b135458f50b92c534efefc2  tools/agx-isa/validation.json  (working tree, dirty)
```

## 8. Deliverables

| file | content |
|---|---|
| `analysis/adjudicate.py` | the re-runnable re-derivation; single entry point |
| `analysis/derived_stats.json` | per (instr, field, carrier): N, D, M, I, agreement, verdict, accept-set, movement map |
| `analysis/field_verdicts.json` | **merge-ready**, flat `<mnemonic>.<field>`, survivors only |
| `analysis/withheld.json` | every rejected key with reason + numbers |
| `analysis/proposed_db_defects.json` | §4.6 G1 routing + H3/H4 findings, with evidence |
| `RESULTS.md` | observation vs interpretation, survivor count, emittability delta, limitations |
| `manifest.json` | inputs, hashes, environment, commands |
| `PROGRESS.md` | append-only milestone log |

## 9. Clean-room statement

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed raw evidence only)
Inputs inspected: EXP-0146's append-only JSONL raw captures, produced from MSL we authored;
                  tools/agx-isa/{db,validation}.json; later experiments' committed RESULTS.md
Apple binary introspection: NONE
Reproduction: python3 analysis/adjudicate.py
Evidence: EXP-0146 raw/ (hashes above) + this directory's analysis/
```

No Apple binary is disassembled, decompiled, symbol-dumped, strings-scanned or debugged in this
experiment. No new machine code is inspected at all; the only bytes read are hex strings recorded
in EXP-0146's own raw JSONL, which came from compiling `EXP-0146/kernels/*.metal`, which we wrote.

---

## 10. AMENDMENT A1 — composite (multi-byte) fields

*Added 2026-08-30, still **before** `analysis/adjudicate.py` was written and before any statistic
was computed. Recorded here rather than decided at analysis time so it cannot be tuned.*

Four `db.json` fields in scope are wider than one byte and were swept **byte-wise** by EXP-0146
(one byte varied over 0..255 at a time, the rest held at the carrier's compiled value):

| field | db.json `start`/`width` | bytes swept |
|---|---|---|
| `irotate.operands` | 24 / 40 | +3 … +7 |
| `irotate.tail` | 64 / 32 | +8 … +11 |
| `n2_op8.body` | 24 / 40 | +3 … +7 |
| `n2_op10.immword` | 32 / 48 | +4 … +9 |

A merged row for such a field licenses an emitter to choose a value for the **whole** field, so:

- composite → **`stable-live`** iff **every** constituent byte arm is `stable-live` under §4.4
  **and** the swept bytes cover every bit of the field;
- composite → **`inert-envelope`** iff **every** constituent byte arm is inert **and** the ≥2-carrier
  rule of §4.4 is satisfied;
- otherwise → **`withheld`**, with the per-byte verdicts reported in `analysis/withheld.json`.

A composite whose constituent bytes split into live and inert groups is additionally reported in
`analysis/proposed_db_defects.json` as a **mis-modelled field boundary** (one descriptor field
spanning bits with different roles), which is exactly the `FIELD-SWEEP-PROTOCOL` §6 case.

Every composite `range` string must state that only **marginal** (one-byte-at-a-time) variation
was exercised — never joint values — so no reader can mistake 1 280 marginal cases for coverage
of a 40-bit space.

## 11. AMENDMENT A2 — bit-range re-location from raw bytes (the G1 mechanism)

*Same timestamp and same condition as A1.*

`db.json` has been edited since EXP-0146 ran, so a verdict key's `<field>` name is **not**
sufficient to prove it names the same bits today. G1 is therefore decided mechanically:

For each `(instr, field, carrier)` arm, the swept bit range is **re-derived from EXP-0146's own
raw `bytes` strings**: the set of bit positions that differ between the arm's cases is computed,
and a `(start, width)` is accepted only if extracting those bits from every case's byte string
reproduces that case's recorded `value` exactly, for all cases. The arm is eligible for merge only
if the re-derived `(start, width)` **equals** the `(start, width)` of a field of that mnemonic in
the pinned `db.json`. Any other outcome — no field at that range, a field at a different range
with the same name, or a partial overlap — is a G1 failure and routes to
`analysis/proposed_db_defects.json` / `analysis/withheld.json`.

This makes descriptor drift (confounder §5.4) detectable from the evidence itself rather than from
my reading of two versions of a JSON file.

---

## 12. AMENDMENT A3 — the baseline comparator (method correction, not a threshold change)

*Added 2026-08-30 after the first pass of `analysis/adjudicate.py` produced `I == 0` across whole
arms, which is diagnostic of a broken comparator rather than of field liveness. The **thresholds of
§4.4 are unchanged**; only the definition of "equals the baseline" is corrected, and both the
corrected and the literal-§4.2 statistics are computed and reported side by side so the change is
auditable.*

**What was wrong.** §4.2 defined the baseline as the arm's `_baseline` *record* in the same run.
That record is a single GPU measurement, and it flaked in **5 of the 24 arm-baselines** across the
two gated runs:

| run | arm | baseline outcome |
|---|---|---|
| run01 | `n2_op6@u64eq` | `silent_zero` |
| run01 | `n2_op8@sfu_sin` | `silent_zero` |
| run01 | `n2_op10@roundmodes` | `silent_zero` |
| run03 | `shift_amt_move@rot_var` | `fault` |
| run03 | `sfu_marker@sfu_sin` | `silent_zero` |

Comparing every case against a flaked baseline marks the *unmutated* encoding as "moved" and
inflates both `M` and `D`. Separately, the `sfu_sin` carrier is float-valued and EXP-0146 judged it
with a `1e-3` tolerance, so exact word-tuple equality is the wrong comparator there and marks even a
clean baseline as "moved".

**The correction.** The pre-registered *quantity* was "the unmutated program's output". EXP-0146
records that quantity **host-side, independent of the GPU**, in every single case record's `oracle`
key (FIELD-SWEEP-PROTOCOL §3.4), and its `match` flag is exactly "this case reproduced the oracle",
tolerance included. So:

- **inert(v, run)** := `rec["match"] is True and rec["outcome"] == "ok"` (verified over both gated
  runs: `match` is `True` **iff** `outcome == "ok"`, 4 222/4 222 in run03 and 4 176/4 176 in run01 —
  the two encodings of the same fact);
- **moved(v, run)** := not inert;
- cross-run **agreement** is unchanged: the observable `(outcome, words)` must be identical.

This follows EXP-0160's evidence-validity principle, now in FIELD-SWEEP-PROTOCOL §7: *contamination
can destroy an observation but never fabricate a coherent one.* A flaked `_baseline` is a destroyed
observation; the host-computed oracle is not a GPU measurement at all.

`analysis/derived_stats.json` carries **both** sets of counters (`*_A3` primary, `*_lit` literal
§4.2) and `RESULTS.md` reports every row whose verdict differs between them.

## 13. AMENDMENT A4 — coverage is counted in distinct spliced encodings

*Same timestamp and condition as A3.*

EXP-0146 assembled each mutated instruction through `tools/agx-isa/isadb.py`, which **ORs the
`db.json` `match` constant over the encoded word**. Where a declared *field* overlaps a `match`
range, the byte actually spliced is `value | match_bits`, so the sweep is **not** dense even though
256 values were dispatched. Verified directly from the recorded `bytes` strings, e.g.
`shift_amt_move.kind` (`match [16,4,12]`): `v=0,4 → 0x0c`, `v=1 → 0x0d`, `v=2 → 0x0e`, `v=3 → 0x0f`.

Therefore:

1. Coverage for every arm is reported as the number of **distinct spliced byte-strings** recovered
   from the raw `bytes` field, never as the number of values dispatched, and the `range` string of
   any merged row states that number.
2. An arm whose distinct-encoding count is below `2^width` was **not** densely swept; the row says
   so explicitly and never claims "full N-bit dense".
3. Where the shortfall is caused by a **field/`match` overlap in `db.json`**, that overlap is
   reported in `analysis/proposed_db_defects.json`: a declared field whose bits a `match` constant
   also pins cannot be filled by an emitter through the DB's own assembler, which is a descriptor
   defect in the sense of FIELD-SWEEP-PROTOCOL §6.

---

## 14. AMENDMENT A5 — sub-field decomposition of dense byte sweeps

*Added 2026-08-30, after A2's bit-relocation showed that several EXP-0146 arms sweep a **superset**
of a current `db.json` field's bits, and before any decomposed statistic was computed.*

A2 makes G1 a strict equality test, which throws away real evidence in one recoverable case: an arm
that swept a whole byte densely **contains** a complete dense sweep of any `db.json` field whose
bits lie inside that byte. `ilogic.lut_a` (split since into `lut_a_sel`/`lut_a_free`/`lut_a_z`) and
the repaired `mov_zext16` fields are exactly this case.

**Decomposition rule.** For a `db.json` field `F = (start, width)` of mnemonic `M` in carrier `C`:

1. Pool **every** case record of `(M, C)` across all of EXP-0146's arms for that instruction.
2. Keep a case iff its spliced bytes differ from the arm's **unmutated** bytes *only* in bits
   `[start, start+width)`. (Testing the bytes, not the arm's declared field, makes this immune to
   the `match`-OR of A4 and to the renames of §5.4.)
3. Index the kept cases by `sub-value = extract(bytes, start, width)`.
4. The decomposed arm is admissible **only if all `2^width` sub-values are present** — a dense
   sweep of `F` with every other bit of the instruction at its compiled value. A partial cover is
   reported with its exact count and is **never** merged as `hardware-run`.
5. `M`/`I`/`D` and the §4.4 thresholds are then applied to the decomposed arm unchanged.

A decomposed row records `"decomposed_from"` naming the source arm(s), so a reviewer can see the
row was not an independent sweep of that field but an extraction from a wider one.

## 15. G3 VETO LIST — fixed here, from committed later experiments

Entered before the verdict pass, each with its committed source. A veto never changes a statistic;
it only stops a row from merging.

| key | veto |
|---|---|
| `iadd2.srcB_ext` | EXP-0154 (G17P, 128/128): these bits are the **srcA register selector** (`reg<<2`), not a modifier. `db.json` carries a verbatim "Do NOT adopt EXP-0146's `(v & 0x7C) == 0x00` rule" warning. |
| `iadd2.srcA` | EXP-0154 DEF-0154-4 + EXP-0158 (G17P): byte+7 is not the srcA register selector and its inertness is refuted (44/64 sampled values wrong). |
| `carry_gen.*` | Superseded value-for-value on G17P by EXP-0161 (two carriers) and already merged; **and the fields were renamed because of EXP-0146** (`subop`→`srcA`, `srcA`→`srcB`), so a name-keyed merge would write two rows into the wrong fields. |
| `n2_op6.*` | Superseded: EXP-0157 swept four carriers on G17P; all six fields already `hardware-run`. |
| `n3_mov.dst`, `.srcA_reg`, `.srcA_uni` | EXP-0157 measured **the same `u64eq` carrier** on G17P and the orchestrator **explicitly withheld those three rows** under the liveness policy (`PROVENANCE.md`). Merging the M4 copy of a withheld G17P row would be inconsistent. |
| `mov_zext16.*` | Descriptor under active repair by **EXP-0165** this session (DEF-0161-2); EXP-0161's own verdicts are held back because "their field names change under the fix". Findings are reported as corroboration and as proposed defects, not merged. |
| `ilogic.srcA`, `ilogic.srcB` | EXP-0154 DEF-0154-5: the operand labels are **swapped** relative to EXP-0146's published LUT table. Both fields are already `hardware-run` (G17P) under the corrected labelling. |

**Not vetoed, but flagged:** `n2_op8` has **no carrier on G17P** (EXP-0157: 0 occurrences across 59
own-MSL programs, two provocation rounds). That is a **G16G↔G17P divergence, not a contradiction** —
G17P can neither confirm nor refute, and `CLAUDE.md` keeps M4 evidence valid on its own target. Any
`n2_op8` row therefore merges as `target: M4/G16G` supporting evidence, and `RESULTS.md` must warn
that `merge_verdicts.py`'s `emittable_instructions` counter is target-blind, so a full `n2_op8`
merge would make an instruction that **cannot be reached on the closure target** count as emittable.

---

## 16. AMENDMENT A6 — wide fields cap at `isolated-byte-diff`

*Added 2026-08-30 before the deliverables were written. It is a **downgrade** rule: it can only
weaken a row, never strengthen one.*

`FIELD-SWEEP-PROTOCOL` §3.3 is binding and predates this experiment: for `w > 8` a sweep must
exercise the boundaries `{0, 1, 2, max-1, max}`, all powers of two, and ≥16 interior samples. A
**byte-wise marginal** sweep (A1) exercises every power of two and 0, but never `max`, never
`max-1`, and never a joint value. It therefore does not meet the protocol's coverage bar for a wide
field, and a composite that passes A1 is labelled **`isolated-byte-diff`**, never `hardware-run` —
which is also the literal reading of that label: "ran with the predicted effect at one or more
points, but the field's range was not swept".

## 17. AMENDMENT A7 — a `reg`-typed field with a singleton accept-set caps at `isolated-byte-diff`

*Same timestamp and condition as A6; also a downgrade-only rule.*

This is the lesson of `iadd2.srcB_ext` (EXP-0154 DEF-0154-4) applied prospectively. When a field
`db.json` types as `reg` has an accept-set of exactly one value — the carrier's own compiled value —
the sweep has established "every other value breaks this carrier", **not** "value *N* selects
register *N*". There is no register-granularity oracle, so `hardware-run`'s "the output matched
prediction" is unmet for 15 of 16 values. Such a row is labelled `isolated-byte-diff` with an
explicit note that a register-granularity carrier is required before an emitter may choose a
register through it.

## 18. Amendment ledger

| id | what | direction |
|---|---|---|
| A1 | composite (multi-byte) fields adjudicated per constituent byte | neutral |
| A2 | swept bit range re-derived from the raw `bytes`, not from field names | neutral |
| A3 | baseline = the host-computed `oracle` in every record, not the flaky `_baseline` record | both (reported side by side) |
| A4 | coverage counted in distinct spliced encodings, not values dispatched | **downgrade only** |
| A5 | dense byte sweeps decomposed into the `db.json` sub-fields they contain | **upgrade only** (recovers evidence G1 would discard) |
| A6 | `w > 8` composites cap at `isolated-byte-diff` | **downgrade only** |
| A7 | `reg`-typed field with a singleton accept-set caps at `isolated-byte-diff` | **downgrade only** |

Five of the seven amendments can only weaken a row or are neutral. A3 is the only one that can move
a verdict in either direction, and both its versions are reported.

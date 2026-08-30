# RESULTS — EXP-0170: how much of the emitter-grade record does DEF-0166-1 actually cost, and was the 122-field withdrawal computed against evidence its own experiments disown?

**Clean-room provenance**

```
Clean-room provenance: OWN-SHADER + HW-PROBE (offline re-analysis of committed evidence only)
Inputs inspected: this repository's own committed raw sweep records (JSONL written by
  harnesses we authored, from MSL we authored), tools/agx-isa/{db,validation}.json,
  and our own harness/analysis source.
Apple binary introspection: NONE
Device work: NONE. No SSH, no GPU dispatch, no macvdmtool, no A18, no M4 GPU, no M5.
Reproduction: README.md "Reproduction"
Evidence: experiments/*/raw/**/*.jsonl (append-only, unmodified); hashes in manifest.json
```

**Target of this experiment: none.** Pure analysis on the repo host. **Target of the
evidence audited:** mixed M4/G16G, A18, and G17P per each `validation.json` row's own
`target`; no row's target is changed here and no M4 evidence is promoted to G17P.

**EXP-0170 promotes NOTHING.** It only withholds and reports. `analysis/wrongly_withdrawn.json`
is deliberately not in `FIELD-SWEEP-PROTOCOL` §5 merge schema (`_meta.mergeable: false`, no
top-level `label`), so `work/merge_verdicts.py` cannot consume it even by accident.

---

## 0. Headline

| question | answer |
|---|---|
| `db.json` fields overlapping their own descriptor's `match` | **53** over 42 instructions — DEF-0166-1 reproduced exactly (**H1 confirmed**) |
| …of those, currently emitter-grade | **28** |
| …**proven** by raw evidence to have exceeded the old assembler's limit | **31 of 53** (harness spliced bytes directly, bypassing `assemble()`) |
| Emitter-grade fields audited on distinct-`bytes` | **617** |
| **UNDER-COVERED** | **8** — and only **1** (`falu2_ext.opsel`) is attributable to DEF-0166-1 |
| FULL-RANGE / UNKNOWN | 435 / 174 |
| **F3 (< 25 UNDER-COVERED)** | **FIRED.** The corpus overwhelmingly wrote bytes directly; the defect's evidential cost is **small**. |
| Round-trip self-check users | **28 files**, 7 distinct bodies, **all symmetric and all blind** |
| The repo's own suite under the **defective** assembler | test (A) 173 cases / **0 failures**; test (B) 37 cases / **0 failures** — **demonstrated blind**, not merely argued |
| EXP-0164 withheld fields re-scored | **266** → AGREES **253**, STILL-WITHHELD-OTHER-REASON **11**, **WRONGLY-WITHDRAWN 2** |
| **F7 (< 10 wrongly withdrawn)** | **FIRED.** The disowned-run defect is **narrow**. |
| Withheld fields whose verdict used a run its source experiment disowns | **19 of 266 (7.1 %)**, all M4 |
| Spans moved since EXP-0164's `db.json` (merge_verdicts DEF-0166-2 guard) | **0 of 266** |

**Plainly: little is affected, and I am saying so with the numbers.** Both materiality
falsifiers fired. Neither the assembler defect nor the run-selection defect justifies a
second mass withdrawal. **Two** fields were withdrawn for a reason the committed evidence
does not support; **eleven** more were withdrawn for a reason that is wrong even though the
withdrawal outcome stands. Against the **40 of 166 / 614 fields** headline the net exposure
is **13 rows**, all M4, and **0** of them blocked by a moved span.

**One correction to the dispatch.** Of the four figures handed to me, two reproduce exactly
and **two do not** (§4.3). In particular `cvt_f2h.op` is **not** affected by the placeholder
defect at all (0 placeholders in its scoring; agreement unchanged at 91.41 %), and
`cvt_f2i.dst` re-scores to **98.14 %**, *below* the ≥99 % bar. So **one** field clears the
bar on committed data, not two — and that one (`pack_convert.b7`) clears it only against a
capture EXP-0144's own `RESULTS.md` disowns.

---

## 1. Arm A — the static blast radius

`analysis/static_overlap.py` → `analysis/static_overlap.json`, over the pinned `db.json`.

For each descriptor field `f` at `(start s, width w)`, with `M_f` = the descriptor's own set
`match` bits restricted to `[s, s+w)` and `p = popcount(M_f)`:

> under the OR-only encoder the word was `match | Σ_or (val << start)`, so a supplied `v`
> landed as `v | (M_f >> s)`. The image of `v ↦ v | m` over the `w`-bit range has exactly
> `2^(w − p)` elements. Hence **`reachable_old = 2^(w − p)`**.

- **53 fields over 42 instructions overlap** (**H1 confirmed; F1 did not fire**).
- **H2 confirmed; F2 did not fire** — the closed form reproduces all six of EXP-0166's
  tabulated numbers exactly: `iter.grp` 8, `iter_at.grp` 8, `tex_sample.kind` 4,
  `pack_convert.fmt_class` 16, `irotate.b2` 32, `shift_amt_move.kind` 64.
- Reachable-fraction histogram: `1/2`:21, `1/4`:18, `1/8`:7, `1/16`:3, `1/32`:4.
- **One field is fully pinned:** `falu2_uni.uni_mode` — `reachable_old = 1` of 2 encodings.
- **Zero field↔field span overlaps**, so the only collapse mechanism is field↔own-match.

## 2. Arm B — the decisive test: distinct `bytes`, not dispatched values

`analysis/coverage_index.py` + `analysis/classify.py` → **`analysis/coverage.json`**.
Reuses `EXP-0164/analysis/collect_raw.py`'s parsing and bit-exact attribution and adds the
two counters the audit does not compute. **4,677,940 raw lines parsed, 771,793 per-value
field records, 0 unparseable; 4,354 sweep groups.**

Per `(experiment, instr, field_label, arm, run)` cell: `n_values` = distinct dispatched
`value`s, `n_bytes` = distinct `bytes` strings, both over the same usable subset.
Classification (frozen in §3 of the pre-registration, `cited` evidence scope):
`FULL-RANGE` if some cited informative cell delivered `n_bytes ≥ max n_values`;
`UNDER-COVERED` if none did; `UNKNOWN` if no cited cell carries a usable `bytes` column.

### 2.1 Result: 435 FULL-RANGE, 8 UNDER-COVERED, 174 UNKNOWN of 617

**F3 fired.** Fewer than 25 UNDER-COVERED, so the pre-registered "material" bar is not met
and this is reported as the headline, as promised.

| field | label | w | ratio | severity | cause | vals → bytes | evidence |
|---|---|---|---|---|---|---|---|
| **`falu2_ext.opsel`** | hardware-run | 3 | **0.500** | **severe** | **assemble-match-overlap** | 8 → **4** | EXP-0138 |
| `iunary.dst` | hardware-run | 8 | 0.996 | marginal | not-assemble | 1281 → 1276 | EXP-0139 |
| `iunary.op_enable` | hardware-run | 8 | 0.996 | marginal | not-assemble | 1281 → 1276 | EXP-0139 |
| `iunary.src` | hardware-run | 8 | 0.996 | marginal | not-assemble | 1281 → 1276 | EXP-0139 |
| `iunary.srcdesc` | isolated-byte-diff | 8 | 0.996 | marginal | not-assemble | 1281 → 1276 | EXP-0139 |
| `iunary.tail` | hardware-run | 8 | 0.996 | marginal | not-assemble | 1281 → 1276 | EXP-0139 |
| `n3_sample_read.tail` | isolated-byte-diff | 48 | 0.991 | marginal | not-assemble | 1603 → 1589 | EXP-0147 |
| `vtx_coord_xform.operand` | isolated-byte-diff | 40 | 0.997 | marginal | not-assemble | 1339 → 1335 | EXP-0147 |

**Only `falu2_ext.opsel` is attributable to DEF-0166-1**, and it matches the Arm A
prediction exactly: `db.json` pins 1 bit inside its 3-bit span, so `reachable_old = 4`, and
the raw shows exactly 4 distinct byte strings for 8 dispatched values. **H5 holds for it.**

The other seven are ≥ 99.1 % and tagged **`cause: not-assemble`** — they have **no `match`
overlap at all**, so per the pre-registered **F5** rule they must **not** be attributed to
DEF-0166-1. A handful of duplicate program bytes out of 1,281–1,603 is far more consistent
with two case vectors happening to assemble to the same program than with under-coverage.
I flag them `review-only` rather than `withhold`, and I do **not** recommend acting on them.

`analysis/reclassify_frozen_rule.json` records what the *mechanical* frozen rule would emit
for all 8 (it is the rule's output, kept for auditability); `analysis/reclassify.json` is the
**single** row I would actually put to the orchestrator: `falu2_ext.opsel`.

### 2.2 The negative control held — H4 confirmed, F4 did not fire

`EXP-0154` writes its bytes directly. Across its **57** cited emitter-grade fields:
**0 collapses.** The instrument is not manufacturing false positives.

### 2.3 The 53 overlapping fields, against raw

**31 of 53 EXCEED the old limit** — their raw contains more distinct field-span encodings
than `2^(w−p)`, which is only possible if the harness put the mutated byte in directly rather
than through `assemble()`. **22 have no attributable per-value raw** (`no-raw`).

This is the structural explanation for why the cost is so low, and it is worth stating
plainly: **DEF-0166-1 corrupted the carrier scaffolding, not the field under test.** The
harnesses built their carrier program with `isadb.assemble()` (so its unmutated instructions
carried stuck bits) but spliced the *swept* byte in directly. Where the swept field itself
went through `assemble()` — `falu2_ext.opsel` — coverage did collapse, exactly as predicted.

Five emitter-grade rows among the 53 have **no raw at all** to prove they escaped:

| field | label | reachable_old / encodable | evidence |
|---|---|---|---|
| **`falu2_uni.uni_mode`** | isolated-byte-diff | **1 / 2** | EXP-0020, RT-1a-FIX |
| `link_save_restore.scope` | hardware-run | 64 / 4096 | EXP-M4-14 |
| `link_save_restore.marker` | hardware-run | 32 / 256 | EXP-M4-14 |
| `reg_move_cb.form` | hardware-run | 32 / 256 | EXP-0140 |
| `rt_intersect.subop` | isolated-byte-diff | 8 / 256 | RT-5-…-falsify |

These are **UNKNOWN, not proven-affected**: their citing waves are old enough that their
harnesses may never have called `isadb.assemble()`. `falu2_uni.uni_mode` is the one I would
look at hardest — if its byte *was* built by `assemble()`, only one of its two encodings was
ever emittable, and an `isolated-byte-diff` label on a 1-of-2 field is not safe.

### 2.4 The 174 UNKNOWN are an auditability gap, not a refutation

156 have no cited experiment with an attributable per-value `bytes` column; 18 more have one
only in an **uncited** experiment. This restates EXP-0164's UNVERIFIABLE finding on a
different axis and adds no new withdrawal.

## 3. Arm C — round-trip blindness

Full write-up: **`analysis/roundtrip_blindness.md`**. Summary:

- **28 committed files** define `assert_round_trip`; **7 textually distinct bodies, all
  semantically identical**, all of the form
  `assemble(mnemonic, disassemble(buf)["fields"]) == buf`. There is **no parameter** through
  which a caller's intended value could enter, so the function is structurally incapable of
  detecting DEF-0166-1 — and it was the pre-flight gate in EXP-0090…EXP-0171. **H6 confirmed;
  F6 did not fire.**
- The `rt_ok` column in those experiments' raw records therefore means *"our tokenizer agrees
  with itself"*, not *"the bytes carry the value the harness asked for."*
- **Demonstrated, not asserted:** `roundtrip_blindspot.py` re-implements the pre-fix OR-only
  assembler and re-runs `tools/agx-isa/roundtrip_test.py` against it. Test (A)
  `asm(disasm(b))==b`: **173 cases, 0 failures.** Test (B) `disasm(asm(fields))==fields`:
  **37 cases, 0 failures**, **9** touching one of the 53 overlapping fields, **0** supplying
  a value that clears an overlapping `match` bit.
- Test (B) is the *right shape* — it compares against the caller's ledger — and missed the
  defect only because its `SYNTH` vectors were seeded from really-observed instructions,
  whose values already carry the `match` bits. **Circular provenance, not a coding error.**
- **`tools/agx-isa/roundtrip_test.py` is a tokenizer regression test, not an emitter gate,
  and should not be cited as one.** It passes unmodified with an assembler that cannot clear
  a bit. Concrete fix offered in `roundtrip_blindness.md` §5 (one `SYNTH` vector per
  overlapping field that clears a `match` bit — fails on the old encoder, passes on the new).

## 4. Arm D — disowned-run selection and placeholder scoring

Pre-registered as **AMENDMENT D**, frozen 2026-08-30 *before any Arm D number was computed*.
`work/collect_raw_D.py` (EXP-0164's `collect_raw.py`, 47 changed lines, **D.2 only**),
`analysis/run_eligibility.py`, `analysis/rescore_D.py`.

`rescore_D.py` **imports** `cross_run`, `stable_live` and `classify` from
`EXP-0164/analysis/audit.py` and asserts `(MIN_COMMON, MIN_AGREE_PCT,
MOVED_OVER_DISAGREE) == (2, 99.0, 2.0)`. **The gate is provably EXP-0164's own and cannot
have been retuned here.** Only two things change: D.2 (placeholders stop contributing
signatures) and D.3 (disowned runs stop being eligible).

### 4.1 The placeholder signature — corpus-wide, and worse than expected

`EXP-0144/raw/m4_20260828_run04/sweep.jsonl`, a representative record:

```json
{"arm":"F","attempts":[],"bytes":"c101144a0402","carrier":"c_f2h_dst","confirm":null,
 "field":"src+match[28:32]=8","instr":"cvt_f2h_dst","observed":null,"outcome":"hang",
 "retries":0,"status":"SKIPPED","validity":"skipped_after_hangs","value":74}
```

Nothing was ever dispatched — `attempts: []`, `observed: null`, `retries: 0`,
`status: "SKIPPED"`, `validity: "skipped_after_hangs"` — yet `outcome: "hang"`.
`collect_raw.py:42` treats only `{invalid_run, victim, skipped}` as contamination and checks
`"skip_reason" in rec`; this record has neither. `sig_of()` puts `hang` in `HARD`, so every
placeholder gets the identical signature `hang|-` and **was scored as an observation**.

A whole-corpus census (4,719,822 records, 617 JSONL files) shows this is not local to
EXP-0144:

| marker | records |
|---|---|
| `validity == "skipped_after_hangs"` | **24,100** |
| `validity == "not_run"` | 6 |
| `status == "SKIPPED"` | 29,210 |
| empty `attempts` list | 24,106 |
| **`outcome == "hang"` (total)** | **24,201** |

**24,100 of the corpus's 24,201 `hang` records are never-dispatched placeholders.** Only
~101 `hang` records in the entire repository are genuine hangs. The D.2 rule is therefore
structural (P1–P5) and deliberately does **not** treat `outcome == "hang"` as a marker — a
real hang is a real hardware observation and must be kept.

### 4.2 The selection rule, and what it picked

`EXP-0164/analysis/audit.py:78-80`:

```python
order = sorted(runs.items(), key=lambda kv: (-kv[1]["n_values"], kv[0]))
```

Most distinct values wins, ties alphabetical. A placeholder-dominated run scores **maximum**
on that key: it has a complete case list, so `n_values` is maximal, while almost none of
those values was measured. Nothing in the key asks whether the source experiment stands
behind the run.

`analysis/run_eligibility.json` — **467 runs, 49 ineligible**, from E1 (marker file in the
run dir), E2 (**15 hand-curated prose disownments, each with its quote and `file:line`**,
as D.3 requires) and E3 (EXP-0164's own `NONGATED` regex, unchanged).

**19 of the 266 withheld fields (7.1 %) had their verdict scored against a run its source
experiment disowns** — 25 of 138 arm-cells (18.1 %). All 19 are M4:

| experiment / run | cells | fields | the source experiment's own words |
|---|---|---|---|
| `EXP-0144/m4_20260828_run03` | 19 | 13 | *"run01–run05 are retained as append-only history and **back no label**"* (`RESULTS.md:29-33`) |
| `EXP-0144/m4_20260828_run05` | 10 | 8 | same passage — but see §4.5, its own `SCOPE.md` contradicts it |
| `EXP-0138/m4_20260828_run02` | 4 | 4 | *"run02 and run03 were killed by a machine-wide `MTLCompilerService` collapse … all are retained as partials. The gated pair analysed is **run01 + run06**"* (`README.md:52-58`) |
| `EXP-0140/m4_20260828_run01` | 2 | 2 | *"retained, **NOT used for any field verdict**"* (`QUARANTINE-NOTE-run01.md:1`) |

**F9 fired — the defect is NOT confined to EXP-0144.** EXP-0138 and EXP-0140 are implicated
too. **F10 fired** — **0** withheld cells reached the `gating_fallback` path, so
`if not gruns: gruns = dict(runs)` is *not* a second route; H10 is refuted.

### 4.3 Re-scored: 253 AGREES, 11 wrong-reason, 2 WRONGLY-WITHDRAWN

| audit bucket | → S3 primary | n |
|---|---|---|
| UNVERIFIABLE (144) | UNVERIFIABLE | **144** |
| INERT-SINGLE (81) | INERT-SINGLE | **81** |
| UNSTABLE (41) | UNSTABLE | 28 |
| UNSTABLE | **SINGLE-RUN** | **11** |
| UNSTABLE | **STABLE-LIVE** | **2** |

**F7 fired (2 < 10): narrow.** Not one of the 144 UNVERIFIABLE or 81 INERT-SINGLE rows moves
a single bucket. The entire exposure is inside the 41 UNSTABLE rows.

**H8 — the four figures I was handed. Two reproduce, two do not; F8 partially fired, so my
numbers stand per the pre-registered rule.** All four *audit* figures reproduce exactly,
which validates my re-implementation:

| field | audit | dispatch's re-score | **my re-score (S2)** | pair I used | verdict |
|---|---|---|---|---|---|
| `pack_convert.b7` | 2.73 % ✔ | 100.00 % | **100.00 %** ✔ | run05 / rv01__pack_convert | **reproduces** |
| `unpack_convert.dst` | 25.78 % ✔ | 98.96 % | **98.96 %** ✔ | rv01__unpack_convert / run05 | **reproduces** |
| `cvt_f2i.dst` | 82.42 % ✔ | 99.56 % | **98.14 %** | rv01__cvt_f2i / run03 | **differs** — below the ≥99 % bar |
| `cvt_f2h.op` | 91.41 % ✔ | 98.44 % | **91.41 %** | run03 / rv01__cvt_f2h | **differs** — **0 placeholders dropped; unchanged** |

So **one** field clears the ≥99 % bar on committed data, not two. `cvt_f2h.op` is not touched
by the placeholder defect at all and its withdrawal is not implicated by Arm D.

**The sharpest single number:** five `unpack_convert` fields (`cache`, `fmt_sel`, `opdesc`,
`size`, `src`) were scored by the audit at **0.00 % agreement over 256 common values** — and
at **100.00 %** once placeholders are dropped. Zero-percent agreement was *entirely* the
artifact of comparing 256 never-dispatched placeholders against 256 real measurements.

### 4.4 The 2 WRONGLY-WITHDRAWN — `falu2.srcA_class`, `falu2.srcB_class`

| | |
|---|---|
| label when withheld | `hardware-run`, target **M4**, evidence EXP-0138 |
| spans | `srcA_class` (40, 1); `srcB_class` (41, 2). **Unmoved** in EXP-0164's db *and* in today's `db.json`. |
| audit | run01 vs **run02** → **96.88 %** on 64 common values → fails the 99 % bar → UNSTABLE |
| mine (S3) | run01 vs **run05** → **100.00 %** on 64 common values → passes the **unchanged** gate → STABLE-LIVE |
| placeholders involved | **none** (0 dropped) — this is purely the run-selection defect |

`run02` is the run EXP-0138's own `README.md` says was killed by a machine-wide
`MTLCompilerService` collapse and whose replacement is `run06`; the pair EXP-0138 actually
analysed is `run01 + run06`, with `run05` as a third annotating run. The audit scored these
two fields against the one capture the source experiment had already replaced.

### 4.5 The 11 wrong-reason rows — and the real question they raise

All 11 are EXP-0144, all `hardware-run`, all M4: `cvt_f2h.op`, `cvt_f2i.dst`,
`cvt_i2f_src.dst_desc`, `pack_convert.b7`, `unpack_convert.{cache,dst,fmt_sel,opdesc,size,
src,src_class}`.

The audit's stated reason — *"the movement does not reproduce across the two gated runs at
≥99 % per-value agreement"* — **is not supported by committed evidence**: it rests on
`run03`/`run05`, which EXP-0144's `RESULTS.md` disowns, and on placeholders scored as
observations. But once the disowned runs are excluded, **EXP-0144 has only ONE admissible
run per instrument**, so every one of the 11 re-scores **SINGLE-RUN**, not STABLE-LIVE. They
cannot clear a *cross-run* gate on committed evidence either way.

**This is a policy question, not an audit finding, and it belongs to the orchestrator.**
EXP-0144 `RESULTS.md` §6.5 says, deliberately and with a reason:

> *"Every promoted label rests on **within-run majority-of-3 (escalated to 5)**, not on a
> cross-run gate. That is the right control here: the thing being suppressed is per-attempt
> machine noise, not per-run drift, and the originals cannot serve as a gate partner because
> they are inadmissible. 99.4 % of cases were unanimous at 3 repetitions and none was
> indeterminate."*

EXP-0164 imposed a cross-run gate anyway, found the only available partner was a capture
EXP-0144 had ruled inadmissible, and failed the field on it. **Whether a within-run
majority-of-3/5 control is accepted in place of a cross-run pair is yours to rule on.**

**A conflict inside EXP-0144 that the orchestrator should see.** `RESULTS.md:29-33` disowns
`run01`–`run05` wholesale, but `raw/m4_20260828_run05/SCOPE.md:1-12` says:

> *"m4_20260828_run05 — **PARTIAL BUT USED**, within the scope stated here. … Everything it
> recorded before that point is a valid measurement and IS used, within this scope:
> `pack_convert` — **complete** (arms C, S, F, W, X). Gated against `m4_20260828_run03`:
> 6,251/6,255 gated records byte-identical (99.936 %). `unpack_convert` — arms C, S and the
> full per-byte F sweep **complete**."*

Both statements are committed; they cannot both be operative. Recorded in
`run_eligibility.json` as `source_conflict`, and carried per field. The frozen D.3 rules
keep `run05` ineligible for the **primary** scoring, and a clearly-labelled sensitivity
variant **S3b** re-admits it: **under S3b, 8 fields reach STABLE-LIVE instead of 2**
(`pack_convert.b7` and 5 `unpack_convert` fields join the 2 `falu2` ones). I am **not**
recommending S3b — I am showing you what turns on the contradiction.

### 4.6 A bug in my own instrument, found and fixed mid-arm

My first Arm D pass reported 92 STILL-WITHHELD-OTHER-REASON. The cause was mine:
`withhold_inert_single.json` yielded the bucket string `INERT_SINGLE` while
`classify()` returns `INERT-SINGLE`, so 81 unchanged rows never compared equal and were
misfiled. Fixed (`.replace("_", "-")`), re-run, and recorded here rather than quietly
corrected — the corrected totals are the ones above.

## 5. What this experiment did NOT do

- It **promoted nothing** and changed no `label`, `range`, `target`, `db.json`,
  `validation.json`, `isadb.py`, `merge_verdicts.py`, `docs/`, or `PROVENANCE.md`. No commit.
- It **cannot** say anything about hardware. `UNDER-COVERED` means *this evidence does not
  support the merged range* — never "the field is dead", never "the hardware rejects it".
- It did **not** re-audit EXP-0158's provenance claim. **EXP-0167 owns** the
  EXP-0158-specific ledger check (204,044 `assemble()` calls, 0 differences, 0 ledger
  mismatches). Arm C is a census of an idiom, not a verdict on any generated program.
- It did **not** re-open Arms A/B/C when Arm D was added; Arm D is a dated amendment.

## 6. Deferrals to the G17P work in flight — I would rather wait, and mostly you should

Every one of the 13 rows in `wrongly_withdrawn.json` is **target M4** and rests on
**EXP-0138** or **EXP-0144**, both M4/G16G. Per `CLAUDE.md`, closure is measured against
**full G17P**. So I checked each row against the pre-registered device scope of the G17P
experiments now in flight, rather than guessing.

**`EXP-0168-g17p-dst-resweep` already owns 4 of my 13 rows** (`PRE_REGISTRATION.md:52-54`):
group A is *"the `dst` field name (13 instructions blocked)"* including **`cvt_f2i`** and
**`unpack_convert`**; group B is the twelve "one-field-away" fields including **`cvt_f2h.op`**
and **`pack_convert.b7`**. Its §4.6/§4.7 sweep the exact bytes, and its `PRE_REGISTRATION.md:363`
shows it was pre-registered *already knowing* about EXP-0144's `pack_convert.b7` placeholders.

**`EXP-0169-g17p-rerecord`** owns *"everything else in the 144"* UNVERIFIABLE set (57 fields
in device scope) and explicitly does **not** emit a verdict for any `.dst` field, to stay
verdict-disjoint from EXP-0168.

| row | in flight on G17P? | my recommendation |
|---|---|---|
| `cvt_f2h.op` | **YES** — EXP-0168 group B | **DEFER.** Do not rule on M4 evidence. |
| `cvt_f2i.dst` | **YES** — EXP-0168 group A | **DEFER.** |
| `pack_convert.b7` | **YES** — EXP-0168 group B | **DEFER.** This is the one field that reaches 100.00 % on committed data, and it is exactly the one about to be measured properly on the documentation target. Restoring it now means upgrading it again within the hour. |
| `unpack_convert.dst` | **YES** — EXP-0168 group A | **DEFER.** |
| `cvt_i2f_src.dst_desc`, `unpack_convert.{cache,fmt_sel,opdesc,size,src,src_class}` (7) | not named in either scope | **your §4.5 policy call.** No cross-run restoration is available. |
| **`falu2.srcA_class`**, **`falu2.srcB_class`** | **NO** — in the UNSTABLE 41, not the UNVERIFIABLE 144 that EXP-0169 owns, and not in EXP-0168's list | **RESTORE-CANDIDATE.** Nothing in flight will supersede these. |

So the deferral answer to your question is: **4 of the 13 are about to be superseded — wait
on those.** The only rows where an M4 ruling is both available and not about to be overtaken
are `falu2.srcA_class` and `falu2.srcB_class`, which are also the only two that actually
re-score to STABLE-LIVE.

### 6.1 Ranked, what I would put to you

1. **`falu2.srcA_class` / `falu2.srcB_class` → RESTORE-CANDIDATE.** Clean **100.00 %** on 64
   common values against an eligible partner (`run01` + `run05`) under the **unchanged**
   EXP-0164 gate; spans (40,1) and (41,2) unmoved in today's `db.json`; withdrawn only
   because the audit paired them against `run02`, the capture EXP-0138's own `README.md`
   says was killed by a machine-wide `MTLCompilerService` collapse and replaced by `run06`.
   Placeholders are not involved. **Nothing in flight supersedes them.**
2. **`falu2_ext.opsel` → WITHHOLD** (`analysis/reclassify.json`) — the single Arm B row I
   would act on. Only **4 of its 8** encodings ever reached the GPU. Also a **re-sweep
   candidate on G17P** now that `assemble()` is fixed: 4 encodings became newly reachable.
3. **The 4 EXP-0168-owned rows → DEFER**, per the table above.
4. **The 7 remaining EXP-0144 rows → your §4.5 policy call** on within-run majority-of-3/5
   versus a cross-run pair. Also worth resolving the `RESULTS.md` ↔ `run05/SCOPE.md`
   contradiction inside EXP-0144, since S3b turns on it (8 STABLE-LIVE instead of 2).
5. **`falu2_uni.uni_mode`** — already in **EXP-0169**'s scope (its `C3_uni` carrier is named
   as *"the only carrier where `falu2_uni.uni_mode` … exist[s]"*), so **DEFER** — but flag it
   to that experiment: under the old encoder only **1 of its 2** encodings was reachable, and
   an `isolated-byte-diff` label on a 1-of-2 field is not safe. Same for `reg_move_cb.form`,
   also in EXP-0169's list.
6. **Tooling** (`analysis/roundtrip_blindness.md` §5): stop citing `roundtrip_test.py` as an
   emitter gate in `PROVENANCE.md` and `docs/`; add one `SYNTH` vector per overlapping field
   that clears a `match` bit, as a permanent DEF-0166-1 regression test.

## 7. Drift noted during the run

`tools/agx-isa/{db.json, validation.json, isadb.py}` **all changed** while this experiment
ran (pre-registration §5 confounder 7 anticipated this). Everything above is computed
against the snapshots in `work/`, hashed in `manifest.json`. Re-checked against the
**current** `db.json` (`322847…`): **0 of the 13 rows has a moved span**, so
`merge_verdicts.py`'s DEF-0166-2 guard blocks none of them.

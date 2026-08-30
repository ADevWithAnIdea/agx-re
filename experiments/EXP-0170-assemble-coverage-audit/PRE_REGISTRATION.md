# EXP-0170 — PRE-REGISTRATION

**Frozen: 2026-08-30, before any verdict, ratio, or classification was computed.**
Repo revision at freeze: `4b16d0b4f8f535c5a37e995aff83824984c3bb79` (working tree dirty in
unrelated experiment dirs — 32 entries; none of them under `tools/agx-isa/`, `work/`, or
`experiments/EXP-0164-inert-audit/`).

Pinned inputs (sha256 at freeze):

| file | sha256 |
|---|---|
| `tools/agx-isa/db.json` | `07ad894d3e7041eaa35692489e90df58ed0b623b4de9378a9d8ea5ca104646d0` |
| `tools/agx-isa/validation.json` | `1fd62e55afbfc0eb6d5872710c5beaa158f448579a6c049edf55045d6c1da695` |
| `tools/agx-isa/isadb.py` (post-DEF-0166-1 fix) | `c97c2a22fe4eb3aaa2140ff716686dcdbbbb099dcd68d2af77f7f9054174dd36` |
| `work/merge_verdicts.py` | `cb369168ec3a0daa1d26937d4c2fd46cfc43f18c0081e7af070204ff6c7368c1` |
| `experiments/EXP-0164-inert-audit/analysis/collect_raw.py` (reused) | `aa15cd24d69d6ab5f06a34f0dda6467c3325105402b1ed112b2a10e0b0c06cde` |

`validation.json`'s own `db_sha256` pin equals the `db.json` hash above, so labels and
encodings are consistent at freeze time.

---

## 0. Target and clean-room statement

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (offline re-analysis of committed evidence only)
Inputs inspected: this repository's own committed raw sweep records (JSONL produced by
                  harnesses we authored, from MSL we authored), tools/agx-isa/{db,validation}.json,
                  and our own harness/analysis source.
Apple binary introspection: NONE
Device work: NONE. No SSH, no GPU dispatch, no macvdmtool, no A18, no M4 GPU, no M5.
Reproduction: python3 analysis/static_overlap.py && python3 analysis/coverage_index.py \
              && python3 analysis/classify.py && python3 analysis/roundtrip_idiom.py
Evidence: experiments/*/raw/**/*.jsonl (append-only, unmodified), hashes in manifest.json
```

**Target of the evidence audited:** mixed M4/G16G and A18/G17P, per the `target` recorded on
each `validation.json` row. **Target of this experiment:** none — pure analysis on the repo host.

## 1. Question

`EXP-0166` / `DEF-0166-1` established that `isadb.assemble()` OR-ed a descriptor's `match`
constants and then OR-ed field values into the same word. An OR cannot clear a bit, so every
`match` bit that lies inside a declared field's span was **stuck at 1 for every caller**. The
failure is silent under-coverage, not an error: a sweep counts *N* dispatched values and
publishes "dense", while the hardware only ever saw *N / 2^p* distinct encodings.

Three questions, pre-registered as three arms:

- **Arm A (static).** Exactly which `db.json` fields overlap their own descriptor's `match`,
  and how many encodings of each was the old assembler able to reach?
- **Arm B (dynamic — the decisive test).** For every `(instruction, field)` currently at
  **emitter grade** in `validation.json`, how many **distinct `bytes` strings** does the
  committed raw evidence actually contain, versus how many **distinct dispatched `value`s**
  the same records claim? Where distinct-bytes is materially smaller, that sweep
  under-covered — whatever built its bytes.
- **Arm C (idiom — added by coordinator amendment before freeze).** Which committed
  experiments and tools verify themselves with a **disassemble → re-assemble → compare**
  round trip? Such a check is blind to any defect that is *symmetric across encode and
  decode*: a stuck bit is present on both sides and the comparison still passes. Arm C
  enumerates who relies on the idiom and states what it did and did not prove. It is
  reported **separately** from Arm B because the consequence differs: under-coverage means a
  field was under-tested; a stuck bit inside a *generated* program means a **provenance
  claim** may be wrong. **EXP-0167 owns the EXP-0158-specific ledger check
  (decode every program, compare each field against its intended value); EXP-0170 does not
  duplicate it and will not report a verdict on EXP-0158's oracle result.**

## 2. Hypotheses and falsifiers

| id | hypothesis | falsifier (pre-registered) |
|---|---|---|
| **H1** | Recomputing "field span intersects own descriptor's set `match` bits" over the pinned `db.json` yields **53** fields, reproducing DEF-0166-1. | **F1:** the count differs from 53 by more than ±0 → report my number, reconcile against EXP-0166's, and treat *mine* as authoritative for this experiment (it is recomputed from the pinned file). |
| **H2** | For the six fields EXP-0166 tabulated (`iter.grp`, `iter_at.grp`, `tex_sample.kind`, `pack_convert.fmt_class`, `irotate.b2`, `shift_amt_move.kind`), the closed form `reachable_old = 2^(width − popcount(match ∩ span))` reproduces 8, 8, 4, 16, 32, 64 respectively. | **F2:** any of the six disagrees → the closed form is wrong and Arm A's numbers are withdrawn. |
| **H3** | A material share of currently-merged emitter-grade fields is UNDER-COVERED by the §4 rule. "Material" is pre-registered as **≥ 25 fields**. | **F3:** fewer than 25 UNDER-COVERED → report plainly that the corpus mostly wrote bytes directly and the defect's evidential cost is small. **This falsifier is a perfectly acceptable outcome and will be reported as the headline if it fires.** |
| **H4** | `EXP-0154` is a negative control: its `irotate`/`iadd2` sweeps show distinct-bytes == distinct-values (its harness wrote bytes directly). | **F4:** EXP-0154 shows collapse → the instrument is producing false positives; Arm B's numbers are withdrawn pending a cause analysis. |
| **H5** | The observed collapse ratio for an UNDER-COVERED field with a `match` overlap equals the Arm A prediction `2^−p`. | **F5:** observed collapse without a `match` overlap, or with a ratio that does not match `2^−p`, means a *different* cause (harness pinned bits, sparse value list, label/field mismatch). Such fields are still reported UNDER-COVERED but tagged `cause: not-assemble` and must not be attributed to DEF-0166-1. |
| **H6** | At least one committed self-check besides `EXP-0158/synth.py::assert_round_trip` uses the disassemble→re-assemble→compare idiom, including `tools/agx-isa/roundtrip_test.py`. | **F6:** no other user of the idiom exists → report that the blind spot is confined to EXP-0158. |

## 3. Method, frozen

### Arm A — static overlap scan (`analysis/static_overlap.py`)

For every instruction descriptor `I` in the pinned `db.json` and every field `f` with
`(start s, width w)`:

1. `span = [s, s+w)`.
2. `M_f = OR over match entries (ms, mw, mv) of ((mv & ((1<<mw)-1)) << ms)`, restricted to `span`.
3. `overlap := M_f != 0`; `p := popcount(M_f)`.
4. `reachable_old := 2^(w − p)`; `reachable_fraction_old := 2^(−p)`.

Justification of the closed form: under the old code the word was `match | Σ_or (val_f << s)`,
so a supplied value `v` landed as `v | (M_f >> s)`; the image of `v ↦ v | m` over the full
`w`-bit range has exactly `2^(w − popcount(m))` elements, and the other fields are held constant
during a sweep. Secondary scan (reported, not used for classification): **field↔field** span
overlaps within one descriptor, which the old OR also collapsed whenever the other field's held
value was non-zero.

### Arm B — distinct-bytes audit (`analysis/coverage_index.py`, `analysis/classify.py`)

**Reuses `EXP-0164/analysis/collect_raw.py`'s parsing and bit-exact attribution design**
(it already indexes every per-value record under `experiments/*/raw/**` and knows the
per-experiment schema differences); this experiment adds the two counters that audit does not
compute. Nothing under `experiments/*/raw/**` is written, moved, or edited.

**Group key** (identical to EXP-0164 amendment A5): `(experiment, instr, field_label, arm, run)`
where `arm = "|".join(carrier, arm)` over whichever of those keys the record carries.

**Usable record:** `bytes` is a non-empty even-length hex string. Both counters are computed
over the *same* usable subset, so they are always paired.

- `n_values_g` = number of distinct `value` entries (JSON-canonicalised if not scalar).
- `n_bytes_g` = number of distinct `bytes` strings.
- `n_span_g` = number of distinct values of the db field's own bit span, extracted from the
  instruction word at the offset fitted by `db.json`'s `match` constraints (EXP-0164's
  `fit_offset`). Diagnostic only.

**Informative group:** `n_values_g >= 4`. (A 2- or 3-value arm cannot carry a headline and its
duplicates are indistinguishable from bookkeeping.)

**Degenerate group:** `n_bytes_g == 1` while `n_values_g >= 4`. The `bytes` column is not
tracking the mutation (harness logged an unmutated program, or the column is a constant
carrier). These are **not** counted as collapse — they are `UNKNOWN/bytes-constant`. This is the
conservative direction and is fixed here so it cannot be tuned later.

**Collapse:** informative, not degenerate, and `n_bytes_g < n_values_g`.
Severity bands, frozen: `severe` ≤ 0.50, `moderate` 0.50–0.90, `marginal` 0.90–1.00
(ratio = `n_bytes_g / n_values_g`).

**Attribution to db fields:** bit-exact where the group's `bytes` vary (attribute the group to
every db field whose span intersects the group's varying-bit mask, at the fitted offset);
`label-level` fallback via EXP-0164's `resolve_label` otherwise. Attribution method is recorded
per row and rows resting only on `label-level` are marked, because a byte-level label can name
several fields.

**Per-field classification** (over the cells attributable to that field):

| class | rule |
|---|---|
| `UNKNOWN` | no informative, non-degenerate cell attributable to the field (includes: cited experiments have no per-value JSONL at all; no `bytes` column; only degenerate cells). |
| `FULL-RANGE` | `Bmax >= Vmax`, where `Vmax = max n_values` and `Bmax = max n_bytes` over informative non-degenerate cells. If some cell collapsed but another delivered `Bmax >= Vmax`, the row is `FULL-RANGE` with `rescued: true`. |
| `UNDER-COVERED` | `Bmax < Vmax` — i.e. **no** sweep anywhere delivered as many distinct encodings as the most ambitious sweep dispatched values. |

Two evidence scopes are computed and both reported: **cited** (only experiments named in the
field's `validation.json` `evidence` list) and **any** (every experiment in the corpus).
**The `cited` scope is the one that classifies**, because that is the evidence the merged label
rests on; the `any` scope is reported as a rescue search.

**Claim check** (secondary axis, `claim_check`): parse `validation.json`'s `range` string for an
explicit count using only these frozen patterns — `all N values` → `N`; `0..N dense` → `N+1`;
a bare comma list `a,b,…` → its length. Anything else → `unparseable`. Then
`met` if `n_span_max >= claimed_count`, `short` if below, `no-raw` if there is no usable cell.

### Arm C — round-trip idiom census (`analysis/roundtrip_idiom.py`)

Textual + AST-level census over committed `experiments/**` and `tools/**` Python for the
pattern *decode(bytes) → re-encode(fields) → compare*, plus manual reading of every hit.
Reported as a table: file, what it compares, whether the comparison is symmetric across the
encode/decode pair, and what it therefore does and does not establish. **No verdict is issued
on EXP-0158's oracle result** (EXP-0167 owns it).

## 4. Deliverables, frozen

- `analysis/coverage.json` — one record per emitter-grade field: instruction, field, start,
  width, label, target, cited evidence, claimed range (verbatim + parsed count), distinct
  dispatched values, distinct bytes observed, distinct field-span encodings observed,
  `reachable_fraction_old`, classification, cause tag, and the raw files each number came from.
- `analysis/reclassify.json` — `FIELD-SWEEP-PROTOCOL` §5 schema, flat `<mnemonic>.<field>`,
  `label: "untested"`, plus `start`/`width` (required by `merge_verdicts.py`'s DEF-0166-2
  check) and a `note` carrying **both counts**.
- `analysis/static_overlap.json` — Arm A.
- `analysis/roundtrip_idiom.json` — Arm C.
- `RESULTS.md`, `manifest.json`, `README.md`, `PROGRESS.md`.

## 5. Confounders, named in advance

1. **Byte-label vs field mismatch.** Many harnesses sweep a whole byte and label the record with
   one field name; distinct-`bytes` is immune to this (the byte strings genuinely all differ),
   which is why it is the primary instrument and `n_span` is only diagnostic.
2. **`value` is not always a field value.** Some harnesses log an index or a case id. This
   inflates `n_values` and biases *toward* flagging. Mitigated by the informative threshold and
   by reporting the raw label per row so a reviewer can check.
3. **Multi-arm groups.** Collapsing two carriers into one group would inflate `n_bytes`. The
   `(carrier, arm)` pair key (EXP-0164 A5) prevents it.
4. **Contaminated / victim cases.** Not filtered: this arm counts *encodings that reached the
   splice*, not outcomes, so a victim case still proves the encoding was distinct.
5. **Sparse-by-design sweeps.** A `w > 8` field is *supposed* to be sampled, not dense. Those
   have `n_bytes == n_values` and correctly read FULL-RANGE; the claim check catches an
   over-claimed `range` string separately.
6. **Attribution error.** A `label-level` cell can smear one byte's evidence over several
   fields. Marked per row; a row whose only support is `label-level` is reported as such.
7. **Live tool state.** `db.json` / `validation.json` are owned by the orchestrator and may move
   under this experiment. Everything is computed against the pinned snapshots copied into
   `work/`, and `manifest.json` records their hashes.

## 6. What this experiment may NOT conclude

- It **cannot** conclude that the hardware does or does not do anything. A row classified
  UNDER-COVERED means *this evidence does not support the merged range*, never "the field is
  dead" and never "the hardware rejects those values".
- It **cannot** promote anything. It only withholds.
- It **cannot** settle EXP-0158's provenance claim; Arm C is a census of an idiom, not a
  re-audit of any generated program.
- No row may change `target`. No M4 evidence is promoted to G17P here.

## 7. Prohibited actions (self-imposed, per dispatch)

No `git commit`. No edit to `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
`tools/agx-isa/isadb.py`, `work/merge_verdicts.py`, `docs/**`, `PROVENANCE.md`, or any file
under another experiment's directory. No write anywhere outside
`experiments/EXP-0170-assemble-coverage-audit/`. No device contact of any kind.

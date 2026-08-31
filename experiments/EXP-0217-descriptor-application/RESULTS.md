# EXP-0217 — RESULTS

```
Clean-room provenance: derived application of already-committed artifacts in this repository.
Device contacted:      NONE. EXP-0213 held the A18 Pro for quiet Gate E confirmations.
Apple binary read:     NONE.  Shader compiled: NONE.  New raw observations: NONE.
Inputs frozen:         raw/db.json.BEFORE         sha256 02a47fc6…  (matches the dispatch)
                       raw/validation.json.BEFORE sha256 6e7ff3f1…
                       raw/isadb.py.FROZEN        sha256 731e8a2f…
Result:                tools/agx-isa/db.json         02a47fc6… -> 90166d96…
                       tools/agx-isa/validation.json 6e7ff3f1… -> 7e90e4d5…
Labels changed:        ZERO.  Rows added/removed/renamed: ZERO.  Spans moved: ZERO.
Committed:             NOTHING.
```

## 1. Headline

**Eight triage items applied — nine `db.json` lines and two `validation.json` notes, all of
them prose or field metadata; six proposals refused; three match-bit candidates built,
measured, and refused — two of them because they break the assembler round trip.**

Every gate is identical before and after, and *identical* here means byte-identical, not
"within noise":

| check | before | after |
|---|---|---|
| `validate_labels.py` | rc 0, 172 instructions, **1053 fields** | **rc 0, 172, 1053 — output diff is EMPTY** |
| emitter-grade (`hardware-run` + `isolated-byte-diff`) | 492 + 68 = **560** | **560 — unchanged** |
| emittable instructions | **37 / 166** (corrected denominator) | **37 / 166 — unchanged** |
| `roundtrip_test.py` | 302 OK / 0 FAIL | **302 OK / 0 FAIL** |
| corpus decode, strict (1 080 own-MSL files) | 842 clean / 387 550 leftover / 25 656 instrs | **identical** |
| corpus decode, resync | 842 clean / 4 392 gap / 78 860 instrs | **identical** |
| corpus descriptor firing mix (strict **and** resync) | — | **no delta at all** |
| record-set decode (13 144 + 6 555 committed encodings) | 11 050 / 4 700 decoded | **identical** |
| `match_overlap_report.py` | rc 0 | rc 0 |
| whole-db field overlap / overrun sweep | — | **0 problems** |

**No count moved, and that is the honest outcome rather than a suspiciously clean one:**
every applied edit is a `note`, a `semantics` string, or one `type` value, and
`isadb.decode_one` reads none of the three. The two edits that *would* have moved a count —
adding a `dst` field to `cvt_f2h`, and renaming `imad.srcC_lo` — are both refused, for
reasons given below.

---

## 2. What was applied

Triage table: `TRIAGE.md`. Transform: `analysis/apply_db_edits.py` (db.json) and
`analysis/apply_validation_notes.py` (validation.json). Both are re-runnable.

### 2.1 `imad` — the descriptor said "never swept" about a byte its own sidecar says was swept dense

The field note on `imad.srcC_lo` (byte+5) opened with **"ROLE UNRESOLVED — never swept."**
Both halves are false, and the second is falsifiable from *this repository alone*:
`validation.json`'s `range` for the same row reads "byte+5: 0..255 dense (256 values,
EXP-0154)". The descriptor and its own evidence sidecar contradicted each other.

EXP-0216 resolved the first half from EXP-0154's committed G17P records. Applied:

* **byte+5 is a MULTIPLICAND REGISTER SELECTOR, `reg = v >> 2`.** With
  `SEED_I = {r0:10, r1:21, r2:34, r3:47, …}`, byte+5 = 0..3 → 101, 4..7 → 211, 8..11 → 341
  (the anchor), 12..15 → 471 — exactly `SEED[v>>2] * 10 + 1`, with the selected register
  released to zero on read. Host oracle `SEED[b5>>2] * SEED[b6>>3] + 1` scores **64/64**
  in-domain; **both addend models score 0/64** (an addend would have given
  340 + SEED[reg] = 350/361/374/387).
* **`type` "mod" → "reg"** on that field. This is the one non-prose edit. `type` is
  documentation metadata — `isadb.decode_one` never reads it; only the XML/table generators
  do. No name, span, match, or label moves.
* A **packing warning**: `reg = v >> 2` here, **not** the project-standard `(reg<<1)|size`
  and **not** byte+6's `reg = v >> 3`. Three different packings in one instruction is
  exactly the sort of thing an emitter gets wrong.
* **`imad` has no field named `srcA` at all**, so the descriptor's own semantics line
  `d = m * (srcA * srcB) + A` names an operand its field table does not contain. Recorded.
* **EXP-0165's byte+5 ↔ byte+6 swap fixed nothing**: it moved the wrong name `srcC_lo` from
  byte+6 to byte+5 rather than removing it.
* The **addend is still missing**, and the two bytes that move it are named: byte+7 shifts
  the destination by {0, 1, 256, 16256, 46038, 49045} above an unchanged product of 340,
  and byte+8 gates the addend between 1 (12 of 256 values, all low-nibble-0) and 0.

`validation.json`'s two `imad` notes are amended to match — including the clause
**"Do not emit a register number here"**, which is now wrong: an emitter *may*, packed
`reg << 2`. Label, range, target and evidence list are untouched; the sweep that earned
them is the same sweep.

### 2.2 `cvt_f2h` and `bf_alu` — the over-fits are now counted, not just asserted

Both descriptors already *said* they were over-fit on a destination nibble. Neither carried
a number, so neither could be acted on. Re-derived here from EXP-0216's committed
`q2_sibling.json` before being written:

| | `cvt_f2h` (EXP-0144, **M4/G16G-direct**) | `bf_alu` (EXP-0171, G17P-direct) |
|---|---:|---:|
| committed encodings keyed to it | 6 555 | 13 144 |
| satisfy its own `match` | **5** | **0** |
| satisfy the dst-parameterised sibling | 5 315 (`cvt_f2h_dst`) | 7 972 `bf_add_dst` + 2 652 `bf_mul_dst` |
| the failing constraint | byte0 only; low nibble holds on **6 515** | byte+1 on **all 13 144**; byte0 on **12 626** |

The `cvt_f2h` entry keeps EXP-0216's target bound verbatim: **G16G-direct, not promoted to
G17P.** The `bf_alu` entry records that per *swept byte* all three bfloat descriptors assign
identical spans, so no field row moves and none needs to.

### 2.3 The eight accepted bfloat byte+2 encodings, bounded

Applied to `bf_add_dst` in the §7 wording EXP-0216 specified: **bits 3–5 of byte+2 are
accepted-inert aliases of the bfloat add *in the EXP-0171 NAT carrier*; global role
unknown.** With the sweep line numbers (`sweep.jsonl:25540` for `0x04` vs `:25564` for
`0x1c`, bit-identical output words), the neighbours that are *not* aliases (`0x1d` = the
multiply; `0x44/0x5c/0x7c` = silent zero; `0x1f`/`0xff` = fault), and the current tokenizer
disposition (see §4).

A separate note on `bf_mul_dst` records that the corresponding multiply question is
**UNTESTED** — EXP-0171 saw only `0x1d` as the coherent multiply and established no alias
family. That note exists because this experiment's own refused candidate assumed symmetry
(§6, item 2), and the next reader should not repeat it.

### 2.4 `mov_zext16` — P5 was already applied

The descriptor's field note and semantics already read "byte0 HIGH nibble = the ONE
register, used as **BOTH source and destination**", with the N = 0..10 fit and the N ≥ 11
no-op bound. **Verified, not re-asserted.** The only edit is one sentence recording that the
`(8,7)` inertness is now a *two-experiment* result (EXP-0154 **and** EXP-0161: one identical
16-register vector across all 128 values in both).

---

## 3. The three refused match candidates, measured

Retained as isolated trees under `work/`, so the next agent starts from the measurement.
All three were built with `analysis/mkvariant.sh` and measured against **two** denominators.

| candidate | change | clean files | strict leftover | instrs | resync gap | **round trip** |
|---|---|---:|---:|---:|---:|---|
| baseline | — | 842 | 387 550 | 25 656 | 4 392 | 302 OK / 0 FAIL |
| **m1** `work/var_m1` | `cvt_f2h` match `[[0,8,17]]` → `[[0,4,1]]` + `dst (4,4)` | 842 | 387 550 | 25 656 | 4 392 | **1 FAILURE** |
| **m2** `work/var_m2` | `bf_alu` match `[[0,8,17],[8,8,2]]` → `[[0,4,1]]` | 842 | 387 550 | 25 656 | 4 392 | **2 FAILURES** |
| **m3** `work/var_m3` | `bf_add_dst` `[16,8,28]` → `[16,3,4]+[22,2,0]`; `bf_mul_dst` `[16,8,29]` → `[16,3,5]+[22,2,0]` | 842 | 387 550 | 25 656 | 4 392 | 302 OK / 0 FAIL |

**Every headline corpus number is identical for all three.** If the corpus totals were the
whole test, all three would have passed. They are not, and the two things that actually
decided the question were the **round trip** and the **firing mix**.

### 3.1 m1 — `cvt_f2h` narrowed: breaks the round trip, and adds an evidence-free field

```
[FAIL] cvt_f2h({'b1':3,'op':28,'src':129,'b4':0,'tail':194})
       -> 01031c8100c2 -> cvt_f2h_dst[?] {...}
```

At 4 match bits `cvt_f2h` loses every tie to the 8-match-bit `cvt_f2h_dst`, so its own
assembled bytes no longer decode back to it. Firing mix: `cvt_f2h` 16 → 11 strict
(22 → 17 resync), `cvt_f2h_dst` +5; on the record set the 5 encodings that satisfied
`cvt_f2h` all move to `cvt_f2h_dst`. The descriptor becomes dominated — which is EXP-0216's
own observation that option (a) "argues for deleting one of them", i.e. a structural
retirement decision this proposal does not license. It also adds a `dst (4,4)` field with
**no evidence row**, which would land at `untested` and move the field count — the
`half_pack.dst` hazard EXP-0212 flagged.

Option (b), re-pointing the four field citations to `cvt_f2h_dst`, is refused on EXP-0216's
own caveat: **1 200 of `cvt_f2h.src`'s 1 280 records sweep byte+3 outside `cvt_f2h_dst`'s
`(28,4)==8` pin.** The bits coincide; the descriptors do not.

### 3.2 m2 — `bf_alu` widened: breaks the round trip, and hands 135 tokens a *worse* name

```
[FAIL] bf_alu({'opsel':28,...}) -> 01001c020900c081 -> n1_word[?] {}
[FAIL] bf_alu({'opsel':29,...}) -> 01001d020900c081 -> n1_word[?] {}
```

`bf_alu8_var`'s match is `[[0,4,1]]` — 4 bits, the same as widened `bf_alu`. `decode_one`
breaks ties by list order and `bf_alu` comes first, so it **swallows `bf_alu8_var` entirely**:
135 → 0 resync firings, 17 → 0 strict. Per-offset diff:

```
('bf_alu8_var', 8) -> ('bf_alu', 8)     135     e.g. 11043c0a0d00c001, 31042c801100c001
('bf_alu',      8) -> ('bf_add_dst', 8)   4     e.g. 11021c020900c001
('bf_alu',      8) -> ('bf_mul_dst', 8)   5
('bf_alu',      8) -> ('cvt_bf16',   8)   2
```

The 11 losses are an improvement — `bf_alu` correctly gives those up to more specific
siblings. The 135 gains are the opposite: `bf_alu`'s own semantics say it names the
**byte+1 == 0x02 scalar** form, and the swallowed tokens carry byte+1 = 0x04 and byte+2
values like `0x3c` and `0x2c` that its `opsel` enum does not contain. `bf_alu8_var` exists
precisely to be the honest residual ("the byte+1 != 0x02 residual of the 0x11 group").
**135 tokens would get a more confident and less accurate name.** Refused.

### 3.3 m3 — the tempting one: clean on every metric, and still refused

m3 is the db-side counterpart of the length-rule fix that already went in. It passes the
round trip, leaves every corpus total unchanged, and does exactly what the capability gap
asks for — on the record set it takes all **112** alias encodings off the catch-all and
hands them to the named descriptors:

```
records:  bf_add_dst 7964 -> 8020 (+56)   bf_mul_dst 2650 -> 2706 (+56)   bf_alu8_var 112 -> 0
corpus :  bf_alu8_var 135 -> 98 (resync); bf_add_dst +15, bf_mul_dst +22
```

Three findings refuse it, in increasing order of force.

1. **It reassigns rather than adds.** The binding precedent is explicit: strictly additive
   is safe (that is why the `_n1_len` widening went in), reassignment is not.

2. **The alias evidence exists at exactly one byte+1 value, and none of the tokens it would
   re-claim shares it.** EXP-0171 held **byte+1 == 0x00** throughout its byte+2 sweep. Of the
   37 own-MSL corpus tokens m3 re-claims, the byte+1 distribution is
   `{0x03:4, 0x04:4, 0x05:1, 0x06:6, 0x09:1, 0x80:4, 0x82:9, 0x83:1, 0x84:2, 0x8a:1, 0xa1:1, 0xb1:2, 0xc1:1}` —
   **0 of 37 carry byte+1 == 0x00.** Every single one is at a context the alias sweep never
   tested. That is `RE_EXPERIMENT_PROCESS_CORRECTIONS` Phase 4 verbatim: *a byte that is
   inert under one opcode or length is not globally inert.*

3. **The same byte+2 value demonstrably means something else one nibble away.** `0x14` is in
   the alias set **and** is the byte+2 of the HW-validated fp32→fp16 convert anchor
   `010114810402` (EXP-0144, outcome `ok`). The eight values are therefore not globally "the
   bfloat add" — the length rule separates the two readings by **byte+3's high nibble**, not
   by byte+2. Bits 3–5 of byte+2 are context-dependent, from committed bytes, with no new
   hardware needed.

**m3 is a positive result and is handed on, not taken.** The missing pieces are named: a
second and third structurally different carrier for the alias set (§7 wants three), at
least one of them at a byte+1 other than `0x00`; and *any* evidence at all for the multiply
side. Both facts are now written into the descriptors so the next reader inherits the bound,
not just the idea.

---

## 4. The `_n1_len` widening, independently re-measured

Commit `1fd2f16f` widened the bfloat length gate to `(byte+2 & 0xc7)` before this experiment
began; it was **not** re-applied here. Its stated measurement was on EXP-0171's 16 991
distinct encodings (unsized 523 → 502). Re-measured here on two *different* denominators,
with `db.json` held constant in both arms (`work/var_prewiden`):

| metric | pre-widening | current | delta |
|---|---:|---:|---:|
| corpus strict — clean files | 841 | **842** | +1 |
| corpus strict — leftover bytes | 387 686 | **387 550** | **−136** |
| corpus strict — instructions | 25 637 | **25 656** | **+19** |
| corpus resync — gap bytes | 4 416 | **4 392** | −24 |
| corpus resync — instructions | 78 848 | **78 860** | +12 |
| EXP-0171 record set — decoded OK | 10 938 | **11 050** | **+112** |
| EXP-0144 `cvt_f2h` record set — decoded OK | 4 700 | 4 700 | **0** |

**It is strictly length-additive on both record sets: zero reassignments.** Every changed
case is `None → 8` or `None → 10`; not one encoding that already had a length got a
different one (1 200 `cvt_f2h`-keyed records `None → 8`, all byte0 `0x01`; 168 `bf_alu`-keyed
records `None → 8`/`10`, all byte0 `0x31`). The claim in the commit message holds on
denominators it did not use.

Two things it did **not** say, both worth handing to the length-rule owner:

* **All +112 recovered encodings land on `bf_alu8_var`, not on a named bfloat descriptor.**
  The length rule now sizes the seven aliases; no descriptor claims them. That is the P4
  db-side gap, and §3.3 is why it was left open rather than closed by widening a match.
* **The widened gate is not disjoint from the convert group.** The HW-validated convert
  anchor `010114810402` carries byte+2 = `0x14`, and `0x14 & 0xc7 == 0x04`. Today the
  convert is rescued by the *earlier* `(byte+3 & 0xf0) == 0x80` test, so no live encoding is
  mis-sized — but the guard is byte+3 alone, and the 1 200 six-byte `cvt_f2h` records that
  went `None → 8` are what that overlap looks like when byte+3 is swept off the convert
  marker. Not a defect today; a fragility worth knowing about before the gate is widened
  again.

---

## 5. Bounded status of everything this experiment touched

Per `RE_EXPERIMENT_PROCESS_CORRECTIONS` §9, stated separately:

* **New raw observations:** none. No device was touched.
* **New geometry facts:** none discovered here; two *recorded* into the database from
  EXP-0216 (`imad` byte+5 `reg = v>>2`, byte+6 `reg = v>>3`, no `srcA` field).
* **New liveness facts:** none. The eight accepted byte+2 values are EXP-0171's, recorded
  with their carrier bound intact.
* **New semantic facts:** one, and it is this experiment's own: **byte+2 `0x14` carries the
  fp32→fp16 convert in one sub-group and is an accepted bfloat-add alias in another**, so
  bits 3–5 of byte+2 are context-dependent (§3.3, point 3). Derived from committed bytes.
* **New generated recipes:** none.
* **Claims downgraded:** none. **No label, range, evidence list, target, span, or row name
  changed anywhere.** Three clauses in existing notes are marked superseded (`imad.srcC_lo`'s
  "ROLE UNRESOLVED", "never swept", and "Do not emit a register number here"), with the
  measurement that supersedes each.
* **Tool defects reported, not patched:** the `_n1_len` / convert-group byte+2 overlap (§4).
* **Bounded unknowns remaining:** which `imad` multiplicand is A and which is B (commutativity
  — undecidable in EXP-0154's carrier); where `imad`'s addend lives (byte+7/byte+8 move it,
  neither carries it); whether the seven bfloat byte+2 aliases hold at any byte+1 other than
  `0x00`; whether the multiply has an alias family at all; whether `cvt_f2h` should be
  repaired or retired; what `(40,8)` is in `iminmax` and `(32,8)` in `half_alu` (old names
  refuted, new ones unconfirmed — EXP-0216's P6, left untouched as it asked).

---

## 6. How this process could have applied an edit the evidence does not carry

Four ways, three of which fired.

1. **Applying the rename because the proposal named it.** *(fired — caught at triage.)*
   P1 says in so many words: "rename (40,8) to a multiplicand name and keep (48,8) as the
   other". Read alone, that is an instruction. Read next to the sentence three lines down —
   "do NOT choose which is A and which is B … multiply is commutative" — it is a trap, because
   **any** name placed opposite `srcB` re-asserts the ordering by contrast, and EXP-0216
   supplies no name that doesn't. Renaming *both* to neutral names would dodge that and walk
   straight into the other hazard: a rename carries `imad.srcB`'s `hardware-run` label onto a
   new name, which is exactly the `tex_write.rsv10` refusal. **What stopped it:** noticing
   that db.json already keeps two refuted names on purpose (`iminmax.dst_full`,
   `mov_zext16.src_flag`) with the correction in the note, and that this is the repo's
   settled answer to this exact situation.

2. **Assuming the multiply is symmetric with the add.** *(fired — I built the wrong thing.)*
   My m3 candidate widened `bf_mul_dst` to `(byte+2 & 0xc7) == 0x05` alongside the add. There
   is **no evidence for that at all**: EXP-0171 observed `0x1d` as a single coherent multiply
   point and established no alias family. I wrote the symmetric half because it looked tidy,
   and **22 of the 37 corpus tokens m3 re-claims come from that invented half.** Nothing in
   EXP-0216 proposed it. What stopped it from shipping was measuring the candidate rather
   than reasoning about it — and the fix in the deliverable is a note on `bf_mul_dst` saying
   the question is untested, so the next reader cannot make the same assumption silently.

3. **Letting the corpus totals be the verdict.** *(fired.)* All three refused candidates leave
   clean files, leftover bytes, instruction count and resync gap **bit-identical**. On the
   metric EXP-0212 used as its primary gate, all three pass. m1 and m2 are nonetheless
   *broken* — they fail `roundtrip_test.py`, which the totals cannot see — and m3's problem is
   visible only in the byte+1 distribution of the tokens it moves. **A tokenization change
   that does not move the totals has not been measured; it has been sampled.** The firing mix
   and the round trip are the tests that discriminate, and the corpus is our own compiler's
   output, so a change can be invisible to it and still wrong.

4. **Writing EXP-0216's counts into normative notes without re-deriving them.** Not fired,
   because I re-derived all four from `q2_sibling.json` first — but it is the cheap failure
   here. `6 515` is not printed anywhere in that file; it is `6 440 + 5×15` summed out of the
   low-nibble × high-nibble table. Had that sum been wrong, a wrong number would now be in
   `db.json` under a hardware-sounding sentence, and no later reader would have a reason to
   check it.

**And one process failure that actually happened.** Re-applying the edits after improving the
P4 note, I passed `--labels raw/validation.json.BEFORE` to the apply script and **wrote into
my own frozen `raw/` copy** — a direct violation of the append-only rule. It was caught
immediately (the script's idempotence assertion fired on the next invocation), the file was
restored from `git HEAD` and re-verified byte-for-byte against the dispatch's expected
`6e7ff3f1…`, and `apply_validation_notes.py` now refuses any path containing `/raw/`. The
guard is in the committed script, not just in this prose. Worth stating plainly: the frozen
copy was recoverable **only** because `validation.json` was unmodified at HEAD. Had this
experiment been the second writer of the day, the pristine input would have been gone, and
the immutability of the whole run with it.

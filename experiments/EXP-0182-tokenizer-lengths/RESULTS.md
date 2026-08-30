# EXP-0182 — RESULTS

**Verdict in one line: four of the five now tokenize; the fifth is blocked by a `db.json`
`match` constant I am not allowed to edit and have built the fix for. So the honest
emittability figure is at most one instruction away from the live headline, not five.**

| | |
|---|---|
| target of the evidence | **G17P** (EXP-0156, EXP-0162, EXP-0180) with two M4/G16G corroborations (EXP-0144) |
| device work in this experiment | **NONE** — pure re-analysis |
| file edited | `tools/agx-isa/isadb.py` only (`9cda47a1d4b3857c9…` → `500db91a6077cd19…`, +149/−38 lines) |
| `db.json` | **unchanged**, sha256 `1ada4e7bb7879cd6…` at freeze and now |
| corpus gate | **833 → 840 clean / 1080**, **388604 → 387496 leftover**, 25419 → 25587 tokens |
| round trip (subprocess) | 302 OK / 0 FAIL / 0 crash / **ALL PASS** — unchanged |
| HW-anchor regression corpus | **245/255 → 249/255**, 4 fixed, **0 regressed** |
| `validate_labels.py` | exit 0, unchanged |
| live emittability headline | **55 of 166, 628 emitter-grade fields** — unchanged by this edit |

> **Amendment A1 — the dispatch's number moved under me, and it was not my edit.**
> The dispatch quotes *"48 of 166 emittable, 621 emitter-grade fields"* and asks whether the
> honest figure is 43 or 48. Between my pre-registration freeze (`0f38e2f8`) and now, the
> orchestrator committed `20613a44 exp(0178)`, which edited `validation.json`. The live
> headline is **55 / 628**. `emit_worklist.py` imports only `collections, json, os, sys` — it
> never imports `isadb` — so my edit provably cannot move it, and measurement confirms 55
> before and after. Every figure below is stated against the live file, and the 43-vs-48
> ruling is restated in those terms in §6.

---

## 1. Re-derivation — every defect checked against committed `raw/` BEFORE anything changed

Per the dispatch and the EXP-0165 / EXP-0175 precedent: a defect that does not survive its
own re-derivation is reported and **not** applied. All three survived, and the re-derivation
strengthened two of them.

### 1.1 DEF-0181-2 — all five anchors are real, and the oracle behind each is a *semantic* one

`analysis/collect_anchors.py` located each anchor in committed append-only raw. None rests on
a baseline-hash comparison; each was scored against a **host-computed value**:

| descriptor | anchor as dispatched | raw evidence | target |
|---|---|---|---|
| `bf_add_dst` | `21001c001100c081` | `EXP-0156/raw/g17p-20260830-bf03/sweep.jsonl`, `outcome: ok, match: true`, carrier `bfadd`, note *"native bfloat ADD, host oracle = exact bf16 of a+b (inputs chosen so the sum is exactly representable, so rounding cannot confound)"* | G17P |
| `bf_fma_dst` | `21001e0086041000c081` | same run, carrier `bffma`, *"host oracle = exact bf16 of a\*b+c"* | G17P |
| `hminmax` | `22001c0010c0` | same run, carrier `hmax`, *"native fp16 MAX, host oracle = exact fp16 of max(a,b)"* | G17P |
| `cvt_bf16` | `0101148105024000` | `EXP-0162/raw/g17p_20260829_run01__cvt_bf16/sweep.jsonl`, *"unmutated carrier"* + 30 further `SEM` vectors `ok`; **same bytes also `ok` on M4** in `EXP-0144/raw/m4_20260828_run02` | G17P + M4 |
| `cvt_f2h_dst` | `c10114810402` | `EXP-0162/raw/g17p_20260829_run01__cvt_f2h_dst/sweep.jsonl`, *"unmutated carrier"*; also on M4 in EXP-0144 | G17P + M4 |

The three EXP-0156 anchors additionally appear in that run's `00_inputs.json` under
`raw_sites` as the **lifted instruction at a named offset** in our own compiled kernel:
`bfadd → [bf_add_dst, off 32, 21001c001100c081]`, `bffma → [bf_fma_dst, off 46, …]`,
`hmax → [hminmax, off 32, 22001c0010c0]`.

**The re-derivation found something EXP-0181 did not report: the desync is visible in our own
compiled carrier, in committed evidence.** The same `00_inputs.json` stores `carrier_tokens`,
the tokenizer's own walk of each 80–96 byte `_agc.main`. For `bf_add.metal`:

| off | tokenizer said | what is actually there |
|---:|---|---|
| 32 | `operand_word`, 2 B, `2100` | the first 2 bytes of an 8-byte `bf_add_dst` |
| 34 | `mov_imm`, 2 B, `1c00` | its op-select and byte+3 |
| 36 | `cvt_f2h`, 6 B, `1100c0810ca5` | its last 4 bytes **plus 2 bytes of the next instruction** |
| 42 | `iminmax`, 6 B, `02a416002d0d` | garbage spanning two real ops |

For `hmax` the tokenizer emitted a single `n2_op10` of length 10 (`22001c0010c00ca502a4`),
swallowing the two ops that follow the 6-byte `hminmax`. **This is not a hypothetical
decode gap; our tokenizer mis-reads our own compiler's output.**

### 1.2 DEF-0180-7 — confirmed independently, and it is exactly as stated

`100d0411891500c0` (destination `r1`) decodes as `half_alu_ext8`. `700d0411891500c0` — the
**same instruction at destination `r7`**, which EXP-0180 ran on G17P in both gated runs —
returns **no length and no decode**. EXP-0169's demonstration case `00021c0300c0` is still
called `pad_operand`. The gate is `if b0 == 0x10`, a full byte, four lines below a docstring
that says byte0's high nibble is the destination and records the identical bug being fixed
for `0x09`.

### 1.3 DEF-0180-2 — re-derived, and it is worse than "the two rules disagree"

**Both are wrong.** EXP-0180's `analysis/length_rule.json` (4,096 cases, two gated G17P runs,
zero cells with more than one observed length) puts `db.json`'s stated rule wrong in 25 of 32
`(op-select, byte+4 & 3)` cells and `isadb.py`'s implemented rule wrong in 18 of 32. I did
not re-measure hardware; I verified the two rules against that committed table and against my
own `analysis/opsel_length_map.py`. **EXP-0180 is complete, not still running** — its
`RESULTS.md`, `manifest.json` and `analysis/length_rule.json` are on disk and its `PROGRESS.md`
records M11 "GATED PAIR COMPLETE". Its verdict is treated as authoritative below.

### 1.4 One claim in the dispatch that my re-derivation does NOT support as stated

The dispatch says `hminmax` *"decodes at only 2 of 16 destination nibbles"*. That is right,
and `analysis/opsel_length_map.py` reproduces it independently from `db.json` alone. But the
cause is **not** a `0x10`/`0x11`-shaped full-byte gate on `hminmax` itself: the low-nibble-2
family's op-select dispatch is already destination-general, and `0x1c` is simply **missing
from its 6-byte op-select list**, so the length falls through to the full-byte per-destination
fallbacks `if b0 == 0x02 / 0x12 / 0x22 / 0x32` underneath. Those give 6 at nibbles 0/1, 10 at
nibble 2 (the validated one) and nothing at all at 4..15. Same class, different mechanism —
and the difference matters, because the general fix is to complete the op-select table, not to
widen a byte0 comparison.

---

## 2. The general instruments — the defect is not five accidents

Two of these did not exist and are the reason the finding generalises.

**`analysis/collect_anchors.py` + `analysis/anchor_decode_test.py`** — the asymmetric test the
repo lacked. `roundtrip_test.py` cannot see any of this: it disassembles and re-assembles from
the disassembled fields, so a defect present on both sides cancels (EXP-0170 proved it passes
173/173 against an assembler that could not clear a bit; EXP-0173 proved it passes with two
operands swapped). The anchor test instead asserts that **bytes real hardware executed
correctly** decode to the descriptor they were dispatched as, at that descriptor's declared
length. Under a frozen selection rule (R-A1..R-A5, `PRE_REGISTRATION.md`) it collected **255
anchors over 95 mnemonics**, and at baseline **10 of them failed** — the five in the dispatch
plus `bf_alu`-adjacent `cvt_f2h`, `falu_srcmod12b`, `isel8`, `n3_mov`, `packed_half2_hi`.

> The selection rule earned its fifth clause the hard way: `field: null` alone is **not** a
> baseline marker. EXP-0171 writes field-less *mutated* sweep records, and admitting them put
> a `byte+2 = 0x04` record into the set under the name `bf_alu`, whose real anchor has
> `byte+2 = 0x1c`. The rule now requires `field in {"-", "_baseline"}` or an explicit
> baseline note.

**`analysis/family_gate_audit.py`** asks the DEF-0180-7 question mechanically, from `db.json`
alone: *for every descriptor whose own `match` leaves byte0's high nibble free — it pins
`[0,4,v]` and never `[0,8,v]` — does `instr_length` return the declared length at all sixteen
destinations?* Of **74** such descriptors, **17 decoded at only some destinations** before the
fix.

**`analysis/opsel_length_map.py`** does the same for the low-nibble-2 family's op-select:
for each `byte+2` in `0..0x3f`, what length do `db.json`'s own descriptors imply, and what does
`instr_length` return at each destination? **Six op-selects — `0x05, 0x06, 0x0e, 0x15, 0x16,
0x1c` — had exactly one `db.json`-implied length that the code got wrong at most
destinations.** `hminmax`'s `0x1c` is one of six, not a special case; `0x06/0x0e/0x16` are
`iminmax`'s own low op-selects and `0x05/0x15` are `isel10_c`'s.

---

## 3. What was changed, and what each change is grounded in

Six named patches, all in `analysis/apply_fix.py`, all applied:
`python3 analysis/apply_fix.py --inplace ../../tools/agx-isa n1 r9 n2 n2b n2c n0c`.

### `n1` — the low-nibble-1 group (single-source convert + native bfloat ALU)

The old code had two rules for this group and **both keyed the length on operand bytes**:

* the convert gate demanded `byte+2 & 0x0f == 0x0c`, so the anchors `01 01 14 81 05 02 40 00`
  and `c1 01 14 81 04 02` (`byte+2 = 0x14`) had **no length at all**;
* the bfloat gate demanded `byte+1 in {0x02, 0x04}`, but **G17P's own compiler emits
  `byte+1 == 0x00`**, so `21 00 1c 00 11 00 c0 81` was not this group either.

The replacement keys on the bits that **identify** the instruction, and is one rule for all
sixteen destinations: `byte+3` high nibble 8 ⇒ single-source convert, length from `byte+4`
bit0 (→half 6 / →bfloat 8) — which is `cvt_f2h_dst`'s own `match [28,4,8]`; otherwise
`byte+2` op-select `0x1c`/`0x1d` ⇒ 8, `0x1e` ⇒ 10 — which is `bf_add_dst`'s `match [16,8,28]`
and `bf_fma_dst`'s `[16,8,30]`. Every previously-correct `byte0 == 0x11` length is reproduced
by keeping that block's three sub-rules verbatim *below* the two general ones.

### `r9` — the R9 trailing-word closure must not shadow a real instruction

`n1` alone does not reach `bf_add_dst`: `_R9_SIGS[(0x21, 0x00)] = 2` fires **first**, at the
very top of `instr_length`. That table documents itself as firing *"only where baseline
instr_length was None at a real boundary"*, and it does not. The guard restores its own
contract for this group: never claim a 2-byte pad where the low-nibble-1 rule yields a length
at which a **real named descriptor** matches.

This is the **narrower guard EXP-0165 asked for**. EXP-0165 built the general version, measured
that it regressed the corpus (833 → 832, +398 bytes) and recorded it unapplied. I measured the
general version too, at full scale — see §5 — and it is far worse than EXP-0165 saw. The
family-scoped one *improves* the gate.

### `n2`, `n2b`, `n2c` — complete the low-nibble-2 op-select table

Derived mechanically from `db.json` by `analysis/opsel_length_map.py`, not case by case:
add `0x1c` (`hminmax`, 6 B), `0x06/0x0e/0x16` (`iminmax`'s remaining unambiguous op-selects,
6 B) and `0x05/0x15` (`isel10_c`, 10 B). After these, **the count of op-selects where
`db.json` is unambiguous and `instr_length` disagrees is 6 → 0.**

### `n0c` — DEF-0180-7, closed as far as the evidence allows and no further

The family gate `if b0 == 0x10` is replaced by a low-nibble gate, mirroring the
already-committed low-nibble-8 high-half sibling. Two limits are deliberate and both are
measured:

1. **The generalisation fires only in the nine `(op-select, byte+4 & 3)` cells where the
   committed corpus-anchored formula and EXP-0180's G17P measurement AGREE** (`_half_len_agreed`:
   op-select 4/5 with `m ∈ {0,1,2}`, op-select 6 with `m ∈ {1,2,3}`). They disagree in 18 of 32
   cells. Extending the committed formula to fifteen more destinations in a cell hardware has
   already refuted would manufacture confident wrong lengths; adopting the measured formula
   instead costs 17 clean corpus files (§5). Neither rule may be extended on its own authority,
   so the gate is closed exactly where the evidence is unanimous.
2. **`0x30`/`0x90`/`0xb0` are excluded** — they are the texture sampler leaders, and byte0 alone
   cannot separate a sampler op from a half ALU writing `r3`/`r9`/`r11`. Those three
   destinations stay UNKNOWN: a real, bounded residue.

Result: `instr_length` now lengths the half-ALU family at **12 of 16 destinations** instead of
1 (`r0` is lost to the `byte0 == 0x00` pad catch-all, `r3`/`r9`/`r11` to the sampler
ambiguity). **Decode is still blocked, and not by this file** — see §4.

---

## 4. The fifth anchor: `cvt_bf16` is blocked by `db.json`, and the fix is built and measured

After `n1`, `0101148105024000` is lengthed correctly at **8**. It still does not decode to
`cvt_bf16`, for a reason no length rule can touch: `db.json` gives `cvt_bf16` the match
`[[0,4,1],[24,8,129],[32,8,1]]`, pinning **byte+4 to the single value `0x01`**, and the
hardware-validated anchor carries `0x05`. `decode_one` filters candidates by `match`, so the
descriptor cannot claim its own validated encoding; the only length-8 candidate left is the
catch-all `bf_alu8_var`.

**EXP-0162 already measured that constant to be wrong, not merely narrow.** Its dense 0..255
sweep of byte+4 on the unmutated `cvt_bf16` carrier found **52 values that reproduce the
convert — `05 0d 21 25 29 2d 31 35 …` — and `0x01` is not among them** (re-derived here from
`EXP-0162/raw/g17p_20260829_run01__cvt_bf16/sweep.jsonl`; the accepted set is all-odd but is
not a simple mask, so `byte+4` is not one field). EXP-0162 could not act on it and said why:

> *"`instr_length()` has **no rule at all** for `byte0 == 0x01`, so `cvt_bf16` cannot be
> lengthed and no match relaxation can reach it. **Db defect 28 must land first**, and it
> needs its own pre-registration."*

**Db defect 28 is this experiment's `n1` patch. The prerequisite is met.**
`analysis/demo_cvt_bf16_dbfix.py` builds the change in `work/demo_dbfix/` and measures it:

| tree | anchor decodes to | corpus |
|---|---|---|
| `cand_full` (this experiment's `isadb.py` fix only) | `bf_alu8_var` (len 8) | 840 clean / 387496 leftover |
| `+ cvt_bf16.match [32,8,1] → [32,1,1]` | **`cvt_bf16` (len 8)** | 840 clean / 387496 leftover |

**Zero corpus change.** `db.json` is the orchestrator's file, so this is a measured
recommendation, not an edit. The recommended constant is `[32,1,1]` — byte+4 **bit 0** only,
which is the length selector — with the rest of byte+4 modelled as a field (`cvt_f2h_dst`'s
anchor carries `0x04` in the same byte and `cvt_bf16`'s carries `0x05 = 0x04 | 0x01`, so the
upper bits look like a destination-half selector shared with `cvt_f2h_dst.dhalf`).

---

## 5. Two candidates MEASURED and REFUSED — reported, not forced through

The frozen T2 rule was: a candidate that lowers clean files or raises leftover bytes is
**reported, not applied.** Two did.

### `n0m` — EXP-0180's measured half-ALU length rule, applied verbatim

| | clean | leftover | tokens |
|---|---:|---:|---:|
| baseline | 833 | 388604 | 25419 |
| `n0m` | **816** (−17) | **391824** (+3220) | 24965 |

The firing delta shows why: `half_compact4` 8 → 0 and `half_alu_fma12` 7 → 0. The measured
rule assigns 10 or 8 bytes to op-selects 0 and 1, where the corpus-anchored `falu_compact4`
sibling (EXP-0148 H2-narrow) says 4 — and the corpus contains those forms. **This is a real
tension between EXP-0180's G17P measurement on synthesised single-instruction carriers and
1,080 M4-compiled shaders, not a defect in either.** EXP-0180 bounded its own result
("bytes +6.. are the marker chain in every case, so a length dependence on byte +6 or later
is UNTESTED"), and the compact forms are exactly where a byte-+6 dependence would live.
**Recommendation: do not merge the measured table into `isadb.py` until a G17P arm runs the
compact-accumulate encodings the corpus actually contains.**

### `r9g` / `r9s` — enforcing the R9 closure's documented contract generally

| variant | scope | clean | leftover |
|---|---|---:|---:|
| applied `r9` | byte0 low nibble 1 only | **840** (+7 with `n1`) | **387496** |
| `r9s` | + low nibble 2 | 838 (−2) | 399126 (+11,630) |
| `r9g` | every byte0 | **759 (−81)** | **427374 (+39,878)** |

**So the R9 trailing-word table's stated contract is false, and enforcing it costs 81 clean
files.** In 80-odd corpus files a real named descriptor *does* match at the family-computed
length and the 2-byte pad is nevertheless the correct tokenization. That is a hardware/decoder
fact worth recording: the table is load-bearing well beyond "fires only where baseline
`instr_length` was None". It also explains why `hminmax` still loses two of its sixteen
destinations (nibbles 3 and 7, shadowed by `_R9_SIGS[(0x32,0x00)]` / `[(0x72,0x00)]`) — the
same shape as the `(0x32, byte+1)` / `carry_gen.srcA` over-claim EXP-0165 and EXP-0173
recorded and could not fix without regression. **It is still unfixed, and now quantified.**

---

## 6. The number

**Observed.** Before: 0 of the five anchors decoded. After: **4 of 5**. `cvt_bf16` has the
correct length and is blocked solely by a `db.json` `match` constant that hardware has
already refuted, with the one-line fix built and measured at zero corpus cost.

**Interpretation, stated in the dispatch's own terms.** The dispatch framed the open ruling as
*43 vs 48 of 166*, on the premise that five descriptors might have to be withdrawn. Against the
live `validation.json` the headline is **55 of 166** (Amendment A1), so the same ruling is
**50 vs 55**. After this fix:

* four of the five are no longer at risk on tokenization grounds at all;
* `cvt_bf16` is the only one still in question, and it is in question because of a
  `db.json` row, not because the hardware fact is doubtful;
* so the honest figure is **55**, or **54** if the orchestrator declines the `cvt_bf16`
  `match` relaxation and holds the strict rule. In the dispatch's original scale that is
  **48, or 47** — not 43.

**Alternatives not excluded.** Decoding an anchor proves the tokenizer can read an encoding the
hardware accepted. It does **not** prove the descriptor's fields can be freely chosen — that is
`validation.json`'s question, and this experiment did not touch it. The decode→assemble
re-emit check below is a stronger statement than a round trip but is still symmetric in the
same way; it is reported as a consistency check, not as emitter evidence.

```
decode -> assemble -> compare, on the anchors as dispatched:
  bf_add_dst   21001c001100c081       -> bf_add_dst    re-emit byte-identical
  bf_fma_dst   21001e0086041000c081   -> bf_fma_dst    re-emit byte-identical
  hminmax      22001c0010c0           -> hminmax       re-emit byte-identical
  cvt_f2h_dst  c10114810402           -> cvt_f2h_dst   re-emit byte-identical
  cvt_f2h      110114810402           -> cvt_f2h       re-emit byte-identical
```

---

## 7. Every anchor that failed at baseline, and where it stands now

| mnemonic | anchor | decl | BEFORE | AFTER | disposition |
|---|---|---:|---|---|---|
| `bf_add_dst` | `21001c001100c081` | 8 | 2 / `operand_word` | **8 / `bf_add_dst`** | FIXED (`n1`+`r9`) |
| `bf_fma_dst` | `21001e0086041000c081` | 10 | 2 / `operand_word` | **10 / `bf_fma_dst`** | FIXED (`n1`+`r9`) |
| `hminmax` | `22001c0010c0` | 6 | 10 / truncated | **6 / `hminmax`** | FIXED (`n2`) |
| `cvt_f2h_dst` | `c10114810402` | 6 | no length | **6 / `cvt_f2h_dst`** | FIXED (`n1`) |
| `cvt_bf16` | `0101148105024000` | 8 | no length | 8 / `bf_alu8_var` | **length fixed; decode BLOCKED on `db.json` — §4** |
| `cvt_f2h` | `010114810402` | 6 | no length | 6 / `cvt_f2h_dst` | **harness mis-attribution, not a defect.** `cvt_f2h`'s own `match` pins `byte0 == 0x11`; these bytes have `0x01`, so they are `cvt_f2h_dst`'s. EXP-0144 tagged them `cvt_f2h`. |
| `packed_half2_hi` | `900405000020` | 6 | no length | no length | **mis-attribution, not a defect.** `packed_half2_hi`'s `match [[0,4,8],[16,8,36]]` needs byte0 low-nibble 8 and `byte+2 == 0x24`; these EXP-0144 M4 bytes have `0x90`/`0x05` and satisfy no descriptor. EXP-0162's G17P anchor for the same descriptor, `980424000020`, decodes correctly. |
| `isel8` | `02010f8081040702` | 8 | 10 | 10 | **OPEN, and not resolvable from `db.json`.** `isel8` and `isel10` carry *identical* matches `[[0,4,2],[16,3,7]]` at lengths 8 and 10, so byte+2 cannot separate them; the code decides on a following store head. Needs a descriptor change or a discriminating probe. |
| `n3_mov` | `03000001` | 4 | 4 / `mov_zext16` | 4 / `mov_zext16` | **descriptor overlap, length correct.** `mov_zext16` (`[[0,4,3],[24,3,1]]`, 7 match bits) legitimately outranks `n3_mov` (`[[0,4,3]]`, 4 bits) on these bytes. A `validation.json`/`db.json` question. |
| `falu_srcmod12b` | `690100050300008000000000` | 12 | 4 / `falu_compact4` | 4 / `falu_compact4` | **OPEN**, and already flagged `emit_unsafe` in `db.json` (`opsel==4` corrupts an unrelated register). Its 12-byte form is shadowed by the 4-byte compact rule. |

---

## 8. Limitations, and what is explicitly NOT claimed

* **No hardware was run.** Every hardware fact here is quoted from committed raw and
  re-derived; nothing new was measured on a GPU. Where a length is asserted at a destination
  register no experiment has dispatched, it is asserted **only** in the nine cells where two
  independent evidence sources agree (`n0c`), and nowhere else.
* **The corpus is M4/G16G own-MSL** (`EXP-M4-13-full-corpus`, 1,080 files). A corpus
  improvement is evidence about our decoder, not about G17P silicon. The five anchors are
  G17P (two also M4).
* **`op04_len8` keeps its EMITTABLE VETO.** This fix does not touch it and does not resolve
  its tension: its declared 8-byte length is refuted on hardware (EXP-0157 measured 12 by a
  register-witness probe) while the corrected rule regresses the corpus gate. It is the
  same shape as the `n0m` conflict in §5 — a G17P measurement against the M4 corpus — and
  it needs the same remedy: a G17P arm over the encodings the corpus actually contains.
  **Veto left in place.**
* **The half-ALU family still does not DECODE at any destination but `r1`,** because
  `db.json` gives `half_alu`, `half_alu_ext8` and `half_alu_fma12` the match `[[0,8,16]]`,
  pinning the full byte0 (DEF-0180-1, HW-refuted by EXP-0180's DSTNIB arm, 16/16). DEF-0180-7
  is therefore **half closed**: the length gate is fixed here; the `match` is the
  orchestrator's to relax.
* **`instr_length` remains a 700-line ordered cascade.** These patches key six families on
  identifying bits, and the audit scripts are committed so the same question can be asked of
  the rest; **15 of 74 destination-generalised descriptors still decode at only some
  destinations** (`analysis/family_gate_audit_after.json`).
* **A decoding win is not an emitting win.** `docs/evidence-classification.md`'s bar is
  unaffected by anything in this experiment.

---

## 8b. Two housekeeping facts found on the way out, neither of them mine to fix

**(a) `docs/isa/agx3.xml` and `docs/isa/encoding-tables.md` are STALE relative to `db.json`,
and were already stale before this experiment.** Running the committed generators
(`gen_agx3_xml.py`, `gen_encoding_tables.py`) as a smoke test rewrote both; I reverted them
immediately (`git checkout --`, `docs/` is the orchestrator's) and then measured the cause in
a sandbox. Regenerating from the **pre-fix** tree produces the same diff, and regenerating
from the pre-fix and post-fix trees produces **byte-identical** output — so **my change does
not affect the generated docs at all**; the drift is `db.json` content merged without
regenerating (the diff is enum definitions such as `ray_move_form` and
`frame_marker_srcA_uni`). The diff is kept for the orchestrator at
`work/docs_regen_effect.diff`. `docs/` is clean in the working tree.

**(b) Commit `20613a44 exp(0178)` swept this experiment's in-progress directory into the
repo**, including eight ~1.3 MB candidate `tools/agx-isa` copies under `work/`. Those trees
are pruned now — `work/candidate_isadb/` keeps just the `isadb.py` each one produced, and
`work/README.md` gives the one-line command that rebuilds any of them — so the working tree
shows those files as deleted. That is intentional; nothing of evidential value was removed.

---

## 9. Recommended next, in priority order

1. **`db.json`: relax `cvt_bf16.match` `[32,8,1]` → `[32,1,1]`** and model the rest of byte+4
   as a field. Built, measured, zero corpus cost (§4). Closes the fifth anchor. EXP-0162's
   defect 3 and its blocked defect 27 (`cvt_f2h`/`cvt_f2h_dst` merge) both become actionable.
2. **`db.json`: relax `half_alu` / `half_alu_ext8` / `half_alu_fma12` `match [[0,8,16]]` to
   `[[0,4,0]]` + an op-select pin** (DEF-0180-1). Without it the DEF-0180-7 length fix cannot
   produce a decode at any destination but `r1`.
3. **A G17P arm over the compact half-ALU encodings the corpus contains** (`byte+2` in
   `{0x18,0x19,0x21,0x30,0x31,0x38,0x39}`), to settle `n0m` — currently the measured rule and
   the corpus disagree by 17 clean files. The same arm shape settles `op04_len8`'s veto.
4. **`db.json`: separate `isel8` from `isel10`.** Identical matches at different lengths is
   not decidable, and it costs an HW anchor today.
5. **A successor for the R9 trailing-word table.** It is now quantified: its documented
   contract is false and enforcing it costs 81 clean files. It needs a positive model, not a
   guard.
6. **Regenerate `docs/isa/agx3.xml` and `docs/isa/encoding-tables.md`** — stale since before
   this experiment (§8b), independent of this change.
7. **Run `analysis/anchor_decode_test.py` in CI, or at least in every ISA experiment's gate
   set.** It caught ten defects that `roundtrip_test.py` cannot see by construction, and it
   now has a committed baseline (`analysis/anchor_decode_baseline.json`) so a regression is
   visible immediately.

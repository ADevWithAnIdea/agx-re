# EXP-0165 — RESULTS

**No hardware was run.** Every claim below is re-derived from the immutable `raw/`
trees of EXP-0161, EXP-0160 and EXP-0157 (all **Apple A18 Pro / G17P**), plus
EXP-0146's M4/G16G evidence where a defect cites it.

```
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed raw
  observations from our own authored probes)
Inputs inspected: the raw/ trees and harnesses of EXP-0161 / EXP-0160 / EXP-0157,
  and experiments/EXP-M4-13-full-corpus/hex (our own compiled shader bytes)
Apple binary introspection: NONE
Reproduction: README.md, "Reproduction"
Evidence: analysis/*.py, work/*.json, analysis/ab_metrics.json
```

---

## 1. Headline

| | |
|---|---|
| Defects examined | **13** (EXP-0161 x7, EXP-0160 x5 applicable, EXP-0157 x2) |
| Re-derived and **CONFIRMED** | **11** |
| **CONFIRMED IN PART / REFUTED IN PART** | **1** (`DEF-0161-3`) — applied only in its corrected form |
| Severity claims found **WRONG** | **1** (`DEF-0161-2`'s "invisible to an emitter") |
| Applied to `db.json` | **12** (in **two** coherent writes) |
| Measured and **NOT applied** | **4** (3 length-rule changes + `carry_gen`'s match relaxation) |
| `roundtrip_test.py` | **ALL PASS**, 0 FAIL — unchanged |
| Corpus clean files | **833 / 1080 → 833 / 1080** (unchanged) |
| Corpus strict leftover bytes | **388604 → 388604** (unchanged) |
| Functional check (decode the encodings the HW accepted) | **42 ok / 37 bad → 72 ok / 7 bad** |
| `validate_labels.py` | exit **1**, with **exactly 2** `MISSING label` errors, both for `sfu_marker`'s newly-exposed fields — see §7 |
| Field verdicts re-expressed for merge | **27** (`analysis/field_verdicts.json`) |
| **New defect found by this experiment** | legal `carry_gen` encodings are mis-lengthed by our own tokenizer (§6) |

`db.json` sha256: `83b83a35…` (before) → `30ae6a41…` (after write 1) →
`addf5eda…` (final).

---

## 2. EXP-0161 — the two blockers

### DEF-0161-1 — `fspecial`'s operands are swapped — **CONFIRMED**

`analysis/rederive_def1_fspecial.py`, `def1_summary.py`, `rederive_gen03.py`.
Inputs: `raw/g17p_20260829_run01` + `run02` (arm `D3_FSPEC_SYNTH`, 16-register
architectural dumps) and `raw/g17p_20260830_gen03`. Re-derived from the authored
float seed vector and the register dumps only; EXP-0161's verdicts were not read.

| byte | db.json said | what I measured |
|---|---|---|
| byte+1 hi nibble (`dst`) | destination GPR | **INERT**: all 16 values give a dump byte-identical to the baseline, in BOTH gated runs |
| byte+3 (`src`) | source register | **DESTINATION**, `reg = v>>1`: **28/28 fit, 0 misfits**, both runs |
| byte+5 (`src_ext`) | source extension | **SOURCE**, `reg = v>>2`: **60/60 fit, 0 misfits**, both runs |

Two independent observables agree per case: the computed `rsqrt` matches that
register's seed, **and** the source register is released to zero (56/56 where
src != dst). An exhaustive search over all 256 candidate masks returns exactly
`(v & 0xFE) == 0` for byte+3 and `(v & 0xFC) == 0` for byte+5 — precisely the free
bits the corrected model predicts, and nothing else fits.

Two apparent misfits are seed artefacts, not failures: byte+3 = 12/13 writes r6,
whose seed 0.5 already equals `rsqrt(seed[r0]=4.0)`, so the write is invisible;
byte+3 >= 30 and byte+5 >= 60 name registers outside the 16 the dump covers.

**Generation, re-scored from the block bytes with EXP-0161's own `verdict` field
ignored: the corrected model passes 20/20; the committed db.json model scores 10
fail + 10 unpredictable on the same 20 cases.**

One thing the raw data says that EXP-0161's summary did not: `reg = byte+3 >> 1`
maps `v = 0..191` onto **r0..r95 — exactly the 96-GPR register file** — and
`v = 192..255` onto r96..r127, which do not exist. That is a much better
explanation of the hang region than "bit 7 of byte+3", and it is now the
descriptor's stated rule.

### DEF-0161-2 — `mov_zext16`'s register is byte0's high nibble — **CONFIRMED**, but its **severity claim is wrong**

`analysis/rederive_def2_zext.py`. Inputs: run01/run02 (`B_ZEXT_SYNTH`,
`B_ZEXT_INPLACE`), supp02/supp03 (`B2_ZEXT_SYNTH_R5`), gen03.

* `byte0 = 0xN3` narrows `r[N]` **and nothing else**: **11/11 fits, 0 misfits** in
  both gated runs, for N = 0..10. Nibbles 0xB..0xF are a **no-op** (no register
  changes at all), 4 independent observations each.
* No byte0 whose **low** nibble is not 3 ever narrows anything — all 16 low-nibble
  buckets checked, so the low nibble is the group discriminator.
* byte+1: **128/128** values of bits 0-6 and **2/2** of bit 7 give a dump identical
  to the baseline, in run01, run02, supp02 **and** supp03 (the r5 form).
* The `byte0 := 0x00` falsifier fires (`wrong_value`) in the synthesized carrier
  and is `ok` in EXP-0146's carrier — that carrier is dead, exactly as EXP-0161 says.
* gen03 re-scored from block bytes: 11/16 pass, failures exactly 0xB..0xF.

**One anomaly, recorded rather than smoothed:** nibble 0x8 (r8) narrowed correctly
in 4 of 5 observations (both gated sweeps, gen01, gen02) and was a no-op once, in
gen03. The reachable range is stated as r0..r10 with that noted.

**The severity claim does not hold.** EXP-0161 says "an emitter using the committed
descriptor can only ever produce the r1 form: the register selector is invisible to
it." It is not invisible: **`n3_mov` already models byte0's high nibble as a 4-bit
`dst` register field** (match `[0,4,3]`), and its own committed semantics says it
"Generalises mov_zext16 (0x13) and frame_marker (0x43) to all dst regs".
`assemble("n3_mov", {dst: 7, srcA_reg: 0, srcA_uni: 0, subform: 0, companion: 1})`
already produces `73 00 00 01`, the encoding the hardware executes as
`r7 = r7 & 0xFFFF`. EXP-0161's `RESULTS.md` never mentions `n3_mov`. The defect is
real — a mis-modelled descriptor — but it was never an unreachable register.

### The other five EXP-0161 defects

| defect | verdict | what I measured |
|---|---|---|
| `DEF-0161-3` `fspecial.fnclass` | **CONFIRMED IN PART, REFUTED IN PART** | see below |
| `DEF-0161-4` `roundmode` bit 0 → NaN | **CONFIRMED** exactly | 128/128 odd values all-NaN in 12/12 lanes and 128/128 even values bit-matching the baseline, in 2 carriers x 2 gated runs — four independent tables, no exceptions. Tested with `math.isnan`, not a tolerance compare (the IEEE trap EXP-0161 disclosed) |
| `DEF-0161-5` `device_store` not interlocked | **CONFIRMED** | P1/P3 (load order reversed) both leave r0..r4 stale → follows STORE order; P5 (dump order reversed) moves the stale set to r11..r14; P4 reproduces it with only 5 loads outstanding; P7/P6/P2 (4/16/64 filler ops) leave 5/3/0 stale → a latency, not a capacity limit; P8 (second load wave) leaves 0 |
| `DEF-0161-6` `carry_gen` byte+2 | **CONFIRMED EXHAUSTIVELY** | over all 256 swept values in both carriers x both gated runs the accepted set is exactly {05,07,15,17,25,27,35,37}, and an exhaustive search over all 256 candidate masks returns `(v & 0xCD) == 0x05` as the **unique** separator — 0 false accepts, 0 false rejects |
| `DEF-0161-7` `carry_gen` size bit | **CONFIRMED** | predicate recomputed directly from the committed register dumps (not from the harness' `observed_predicate`): the size-aware model scores **16/16** (gen02) and **48/48** (gen03) across both widths and both settings of the inert bit 7; an always-32-bit model scores 7/16 and 39/48 |

**`DEF-0161-3`, where my re-derivation disagrees.** EXP-0161 says "on the
standard-SFU datapath only the LOW TWO BITS of the nibble are live: values
1,3,5,7,9,11,13,15 all compute the same function." Measured by computed value in
three carriers x two gated runs (`analysis/rederive_def3_fnclass.py`):

* **bit 3 IS a don't-care** — `v` and `v+8` are identical in all 8 pairs, on both
  datapaths. Confirmed.
* **bit 2 is NOT.** At `class&3 == 0` it is live on *both* datapaths (classes 4 and
  12 store nothing at all). At `class&3 == 1` it is live on 0x2f (classes 5 and 13
  **FAULT** the command buffer) and inert on 0xaf.
* "values 1,3,5,…,15 all compute the same function" holds on the **0xaf carrier
  only**. On 0x2f: 1 → rsqrt, 3 → NaN for 11 of 12 inputs, 5 → fault.

The measured map is now in the descriptor: `fn_hi=1` (0xaf) `class&3` 1 → rsqrt,
2 → exp2, 3 → rsqrt, 0 → +inf for every input; `fn_hi=0` (0x2f) 0 → rint,
1 → rsqrt, 2 → log2, 3 → NaN-producing. `fn_hi`'s enum is now HW-confirmed **by the
value the SFU produced** at class 2 (0 → log2, 1 → exp2). Also worth recording:
on this datapath class 0 does **not** compute rcp — rcp needs `fnsel` 0x10.

---

## 3. EXP-0160 — the imad defects (the most serious)

`analysis/rederive_imad.py` solves `r0 = m*(seed[a]*seed[b]) + A` from scratch with
**both multiplicand registers left free**, requiring one solution to satisfy **both
seed sets simultaneously**. Nothing is read from EXP-0160's verdicts.

* **`DEF-0160-6` CONFIRMED.** Over the 2-D (byte+7 x byte+6) probe, 132 points x 2
  seed sets, **0 points had no solution**. byte+6 = 0x10 pins the multiplicand to
  **r2 uniquely**; 0x00/0x02/0x04 → r0, 0x08 → r1, 0x20 → r4, 0x40 → r8 all contain
  the predicted `reg = v >> 3`. The rule fits **10 of the 11** probed values; the
  eleventh (0xFF → r31) lies outside the 16 seeded registers and is unmeasurable,
  not a counterexample. The residual ambiguity at other points is exactly the a↔b
  symmetry of a product. bit 0 = 1 → the source reads 0; bits 1, 2 inert.
* **`DEF-0160-3` CONFIRMED, and sharpened.** Over the dense 256-value byte+7 sweep,
  **191 of the 192** values with a clean two-seed observation fit the model exactly.
  The single exception is a dispatch that returned status OK having written nothing
  — `DEF-0160-5`'s class, not a model failure. `m` is determined **entirely** by
  bits 0-1: **0 → keep the product, 1 → drop, 2 → drop, 3 → reproducible FAULT**
  (all 64 values with `(v & 3) == 3` fault; no other value does). Bit 2 is inert
  (**zero** disagreeing pairs across the whole sweep). `A` is single-valued per
  `K = (v>>3) & 0x1F` across all 32 K and seed-independent by construction, and the
  recovered values are the carrier's own constants' 16-bit halves (K=13 → 0x3F80,
  K=14 → 0xBF95, K=15 → 0xB3D6 — the halves of `1.0000001f` and `-1e-7f`).
  **There is no immediate addend.**
* **`DEF-0160-7` CONFIRMED.** The recovered addend is constant across every `mulsel`
  point, for all 12 byte+7 values probed.

**One thing EXP-0160 did not say, and an emitter needs to know.** The *second*
multiplicand in that anchor is demonstrably **r2**, while the anchor's byte+5 is
`0x08`, which the project-standard `(reg<<1)|size` packing reads as **r4**. So
byte+5 either uses a different packing (`reg<<2` fits) or the second multiplicand is
selected elsewhere. **It was never swept.** The descriptor now says so and tells an
emitter not to put a register number there yet.

### The other EXP-0160 defects

| defect | verdict | measured |
|---|---|---|
| `DEF-0160-1` `falu3`/`falu3_ext` `op` | **CONFIRMED** | accepted set exactly {0x16,0x1E,0x36,0x3E}; `(v & 0xD7) == 0x16` is the unique separating mask over all 256 candidates; **bit 5 is the only inert bit** (0 of 512 flip-pairs differ; every other bit changes the dump); operation by the low 3 bits, agreeing in both seed sets: 0 = a+b, 1 = a*b, 2 = a*b+a, 4 = -b, 5 = 0, 6 = a*b+c; all 32 values with `(v & 7) == 7` fault |
| `DEF-0160-2` `iminmax` slots | **CONFIRMED** | the anchor `02 01 1e 05 07 00` computes `imin(r0, r2) → r0` in **both** seed sets (10 and 7), and **r2 — the register byte+3 names — is released to zero**, identifying it as an operand. byte+5 has exactly four inert bits (3, 5, 6, 7) and no value→register model fits (`v>>1` and `v>>2` each explain 32 of 256), so it cannot be `srcB` |
| `DEF-0160-4` `half_pack` | **CONFIRMED** | the splice controls are decisive: replacing bytes +2..+3 with `mov_imm r6,77` leaves r6 holding its **seed** (the mov_imm never ran), while replacing **both** halves runs both (r6 = 77 **and** r7 = 99) — the positive control fires. byte+2 has three inert bits (3,4,5), so it is not a register selector |
| `DEF-0160-5` (methodological) | **CONFIRMED**, no db.json change | a contaminated dispatch can return status OK having written nothing; only a poisoned read-back buffer catches it. It is what my imad fit's single non-fitting point turned out to be |

---

## 4. EXP-0157

* **`sfu_marker` — APPLIED.** A descriptor with zero fields can carry no evidence at
  all. It now has two fields covering the free bits of its two live bytes, with the
  match relaxed to pin only the bits the hardware requires (`byte+0` bits 0-2 and
  4-7 via `(v & 0xF7) == 0x06`; `byte+1` bits 0-1 and 4 via `(v & 0x13) == 0x02`).
  **Decode is unchanged**: `isadb.py`'s length rule still admits length 2 for
  `byte0 == 0x06` only when `byte+1 == 0x02`, so no additional byte pattern is
  claimed — verified by a corpus A/B with **zero firing delta**.
* **`op04_len8` — MEASURED, NOT APPLIED, and it REGRESSES.** EXP-0157's
  register-witness probe measures the consumed length directly and finds 12 bytes,
  not 8. Applying `8 if (byte+1 & 0x80) else 12` gives **823 clean files (−10)** and
  **390568 leftover bytes (+1964)**, with `op04_len8`'s own firings collapsing
  55 → 1. Per the orchestrator's instruction this is reported and left. Recorded in
  `db.json :: length_rule_gaps.hw_measured_lengths_20260830` with those numbers.
* **`half_pack` length — MEASURED, NOT APPLIED, and it IMPROVES.** Dropping the
  `byte+1 == 0x05` gate gives 833 clean files (unchanged) and **388584 leftover
  bytes (−20)**, round-trip still ALL PASS. It is a one-line `isadb.py` change and
  the length-rule call is the orchestrator's; the exact patch and numbers are in
  `length_rule_gaps`.
* **`mesh_out_src`** — the measured 2-byte / 4-byte split on `byte+1` bit 7 is
  recorded; the change belongs with the `op04` rework, because `mesh_out_src`'s
  match (`byte0 == 0x04`) and `op04_len8`'s (low nibble 4) overlap and only the
  length rule separates them.
* `coord_madf`, `n2_op8`, `rtq_pred`, `rtq_dualsrc` are **reachability** findings
  ("not emitted by any G17P provocation" / "unreached"), not descriptor defects. No
  db.json change; they belong in the labels, not the encoding table.

---

## 5. What changed in `db.json`, and what it costs

Two coherent writes (`analysis/apply_defects.py`, then `analysis/apply_defects2.py`),
141 insertions / 72 deletions.

**Write 1 (EXP-0161).** `fspecial`: a 3-cycle over the names `dst` / `src` /
`src_ext` so that `dst` is byte+3, `src` is byte+5 and byte+1's inert nibble keeps
the historical name `src_ext`; `fnclass`, `fn_hi`, `roundmode`, `sched_flag` notes
and enums corrected. `mov_zext16`: match `[0,8,19]` → `[[0,4,3],[24,3,1]]`, the
register exposed as `src_reg` (byte0 hi nibble), `src_flag` widened to the whole
inert byte+1, `extend` narrowed to byte+3 bits 3-7. `n3_mov`: its open question
closed. `carry_gen`: operand packing, the 16/32-bit size bit, the byte+2 accept set.
`scoreboard_model`: the `device_store` hazard.

**Write 2 (EXP-0160 / EXP-0157).** `imad`: `srcB` ↔ `srcC_lo` swapped so that
`srcB` names the real multiplicand selector at byte+6, plus the full mode /
addend-source / fault map. `iminmax`: a 3-cycle so `srcA` is byte+1, `srcB` is
byte+3 and the modifier byte keeps the historical name `dst_full`. `falu3` /
`falu3_ext`: the byte+2 bit map. `half_pack`: `src` retyped, 4-byte length
confirmation. `sfu_marker`: two fields. `length_rule_gaps`: the three length
findings with their measured corpus deltas.

**Naming debt, stated plainly.** Three fields now carry names that describe what
db.json used to believe rather than what the byte does: `fspecial.src_ext` (an
inert nibble), `mov_zext16.src_flag` (an inert byte), `iminmax.dst_full` (the
modifier byte), and `imad.srcC_lo` (role unresolved). Each says so in its own
`note`. They are kept because renaming a db.json field orphans its
`validation.json` evidence row and hard-fails `validate_labels.py`, which this
experiment may not fix. **Recommendation: rename all four in the same commit that
updates `validation.json`.**

### Gate numbers

| gate | before | after |
|---|---|---|
| `roundtrip_test.py` | ALL PASS, 302 OK / 0 FAIL | **ALL PASS, 302 OK / 0 FAIL** |
| corpus clean files | 833 / 1080 | **833 / 1080** |
| corpus strict leftover bytes | 388604 | **388604** |
| corpus tokens | 25419 | **25419** |
| firing delta | — | `n3_mov` 336 → 259, `mov_zext16` 54 → 131 (105 in, 28 out); nothing else, either write |
| functional check, decode | 42 ok / 37 bad | **72 ok / 7 bad** |
| functional check, re-emit | 73 ok / 6 bad | 73 ok / 6 bad (the 6 are §6, pre-existing) |
| `validate_labels.py` | exit 0 | exit **1**, 2 errors — §7 |

The 133 reclassified corpus instances all move between `mov_zext16` and `n3_mov`,
which are the same compact 4-byte family and the same length, so tokenization is
byte-identical. 80 of the 131 `mov_zext16` firings carry a `subform` outside the
HW-accepted narrow set; the tighter match that excludes them was built and measured
(`work/cand2` of write 1) and **steals 70 firings from `frame_marker`**, whose
8-bit `byte0` match loses the specificity tie-break, so it was rejected.

---

## 6. NEW FINDING: legal `carry_gen` encodings are mis-lengthed by our own tokenizer

Found by `analysis/functional_check.py`, which re-emits the encodings the hardware
**accepted** in EXP-0161's generation runs. `isadb.py`'s EXP-M4-13 R9 trailing-word
closure fires **before** the low-nibble-2 length rule and maps 16 `(0x32, byte+1)`
pairs to a 2-byte pad word: `byte+1 ∈ {0x00, 0x10, 0x14, 0x19, 0x1e, 0x20, 0x22,
0x25, 0x28, 0x2a, 0x51, 0x87, 0x9d, 0xa3, 0xa5, 0xcb}`. Those are legal `carry_gen`
`srcA` selectors — `(reg<<1)|is32` for r0(16-bit), r8, r10, r12, r15, r16, r17,
r18, r20, r21, r40 and four bit-7 forms — so a 6-byte `32 <b1> 35 .. 22 ..` that
**the hardware executes correctly** tokenizes as a 2-byte `operand_word` and the
remaining 4 bytes desync. **6 of EXP-0161's 48 passing generated `carry_gen`
encodings are in this set.**

The obvious guard (do not honour the R9 closure on a low-nibble-2 leader whose
byte+2 is a real op-select) was built and measured (`work/probe_r9`): it fixes all
six (functional re-emit 73/79 → **79/79**) but **regresses** the corpus metric to
832 clean files (−1) and 389002 leftover bytes (+398), so it was **not applied**.
Recorded in `db.json :: length_rule_gaps.carry_gen_r9_shadow_20260830`. It needs a
narrower guard and belongs in its own experiment.

---

## 7. `validate_labels.py` exits 1 — exactly two errors, and why

```
FAIL: instructions[sfu_marker].b0_hi: MISSING label for a db.json field
FAIL: instructions[sfu_marker].b1_hi: MISSING label for a db.json field
```

Nothing else. `sfu_marker` had **zero** fields, so exposing its two measured live
bytes necessarily introduces two names that `validation.json` does not yet carry,
and this experiment may not edit `validation.json`. Merging
`analysis/field_verdicts.json` supplies both and clears it —
`python3 work/merge_verdicts.py --dry-run analysis/field_verdicts.json` applies 27
verdicts with **0 skipped**. If green is wanted *before* the merge,
`analysis/revert_sfu_marker_fields.py` backs out the two fields (and only those).

Every other repair was deliberately shaped to keep the checker green: the field
name set is otherwise unchanged.

---

## 8. The 27 re-expressed verdicts

`analysis/field_verdicts.json`, generated by `analysis/make_verdicts.py`, flat
`<mnemonic>.<field>` schema per `FIELD-SWEEP-PROTOCOL.md` §5. **Verdicts follow the
BYTE, not the name.** Notable:

* `fspecial.dst` / `.src` / `.src_ext` are re-pointed at byte+3 / byte+5 / byte+1-hi.
* `mov_zext16.src_reg` is re-pointed at byte0's high nibble; its range says the
  evidence is the 256-value `__raw_b0` probe plus 16 generated encodings, because
  the *old* `src_reg` sweep (byte+1) is now `src_flag`'s evidence.
* `mov_zext16.src_flag` covers the whole of byte+1 and its range says so honestly:
  **129 of the 256 byte values were exercised** (bits 0-6 dense with bit 7 = 0, plus
  bit 7 dense with bits 0-6 = 0). The other 127 combinations were **not** swept and
  the range says that rather than claiming a dense 8-bit sweep.
* `mov_zext16.extend` is narrowed to byte+3 bits 3-7; three of its eight bits became
  match bits, so the old 8-bit verdict is **not** translated across unchanged.
* `imad.srcB` / `.srcC_lo` and `iminmax.srcA` / `.srcB` / `.dst_full` are
  name→byte re-points of rows **already in `validation.json`**. Merging them is
  **required**, or those rows describe the wrong byte.
* `fspecial_est.srcA` and `.subop` are EXP-0161's deliberate NON-promotions, passed
  through verbatim. They are weaker than the recorded labels and `merge_verdicts.py`
  will refuse them without `--allow-downgrade`; that refusal is correct.
* `n3_mov`'s fields are **not** relabelled. The hardware evidence bears on them, but
  under the repaired match the tested encodings decode as `mov_zext16`, so a
  hardware label on `n3_mov`'s fields would not be supported by an encoding that
  descriptor actually claims. Its semantics were corrected; its labels were not.

---

## 9. What is NOT claimed

* **No hardware was run.** Every number is a re-analysis of committed raw. Where a
  claim needs fresh hardware it is marked so and left.
* **Four measured changes were deliberately not applied**: `op04_len8`'s HW-measured
  12-byte length (regresses the corpus gate), `half_pack`'s unconditional 4-byte
  length (improves it, but is an `isadb.py` length-rule call the orchestrator
  reserved), `mesh_out_src`'s byte+1 bit-7 length split (belongs with the `op04`
  rework), and `carry_gen`'s byte+2 match relaxation (needs three match entries plus
  two new field names, which cannot be added without editing `validation.json`).
* **`imad`'s byte+5 role is UNRESOLVED**, and `iminmax`'s byte+5 live bits (0, 1, 2,
  4) are mapped onto falu2's roles by EXP-0160's *interpretation*, not by a
  per-bit measurement in this data. Both are recorded as such.
* **The `fspecial` round-family round-mode enum is still untested by computed
  value.** EXP-0161's `D4_FSPEC_FLOOR` arm is committed but was never run.
* `roundtrip_test.py`'s synthesized `fspecial` cases still carry comments naming the
  pre-repair byte layout (`"exercises the dst field split -> af 21 56 …"`). The test
  passes — it checks field round-trip, not the commented bytes — but the comment is
  now stale. Not edited: this experiment's remit is `db.json`.
* `docs/isa/encoding-tables.md` is generated from `db.json` by
  `tools/agx-isa/gen_encoding_tables.py` and is now stale. Regenerating it is the
  orchestrator's call (`docs/` is theirs).

---

## 10. Verdict

**The repair is done and gated.** Eleven of thirteen defects re-derived cleanly,
one was corrected before being applied, and one severity claim was found wrong and
reported rather than propagated. `db.json` now says what the hardware does for
`fspecial`'s destination and source bytes, `mov_zext16`'s register,
`carry_gen`'s operand packing and size bit, `imad`'s first multiplicand and
addend-source model, `iminmax`'s operand slots, `falu3`'s opsel/opflags split,
`half_pack`'s length, `sfu_marker`'s two live bytes, and the `device_store`
scoreboard hazard — with round-trip, corpus clean-file and leftover-byte counts all
unchanged, and the functional check (does the descriptor decode what the hardware
accepted?) improving from 42 ok / 37 bad to 72 ok / 7 bad.

The weakest parts are named rather than smoothed over: four fields carry historical
names because renaming them requires a `validation.json` edit this experiment may
not make; `sfu_marker`'s two new fields leave `validate_labels.py` at exit 1 until
the verdicts are merged; four measured changes were left unapplied; and one new
defect — our own tokenizer mis-lengthing 16 legal `carry_gen` `srcA` values — is
recorded with a measured-but-regressing fix rather than a working one.

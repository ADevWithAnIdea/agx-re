# EXP-0203 — PRE-REGISTRATION (frozen before any harness code was written)

**Target: Apple A18 Pro / G17P** (`192.168.170.254`, `AGXAcceleratorG17P`, `applegpu_g17p`,
5 GPU cores, macOS 26.6). Every claim in this experiment is a **G17P** claim.

**Written: 2026-08-30, before `harness/` and `kernels/` existed.** The only prior work done
before this file was frozen is the OFFLINE model fit in `analysis/fit_model_offline.py`,
which reads **our own committed raw** from `EXP-0180-g17p-halfalu-rerecord/raw/g17p_run02`
and touches no device. That fit is what makes §4's oracle a *pre-registered prediction*
rather than a post-hoc curve.

---

## 1. The four fields, and why the previous sweeps could not promote them

| field | span (`db.json`) | current label | why it is open |
|---|---|---|---|
| `half_alu_fma12.dst`  | bits 4..7 (byte0 high nibble), width 4 | `untested` | see §1.1 |
| `half_alu_fma12.ext`  | bits 32..95, width 64 | `untested` | encodable range 2^64 |
| `half_pack.dstlo`     | bits 8..15 (byte+1), width 8 | `untested` | EXP-0164: 88 moved, cross-run agreement failed |
| `half_pack.b3`        | bits 24..31 (byte+3), width 8 | `untested` | EXP-0164: 86 moved, cross-run agreement failed |

### 1.1 A correction this experiment must state, and which changes what it builds

`validation.json`'s `half_alu_fma12.dst` note (written by EXP-0196) says the sweep exists —
*"768 records over 256 distinct values in each of `EXP-0180-*/raw/g17p_run02` and
`g17p_run03`, all status OK"* — and that it fails to promote because `oracle` is `null` and
cross-run agreement is 0.00%.

**Those 768 records are not records of this field.** Verified offline before this
pre-registration (`analysis/fit_model_offline.py`, and the arm census in §9):

* In EXP-0180's raw, the records keyed `field: "dst"` on `half_alu_fma12` carry
  `fstart: 8, fwidth: 8` — **byte+1**, not byte0's high nibble. EXP-0183 later **renamed
  that span to `srcA`** and moved the name `dst` to bits 4..7. EXP-0196 keyed EXP-0180's raw
  by field *name*, so it attributed the old `dst` (bits 8..15, now `srcA`) records to the new
  `dst` (bits 4..7). A 4-bit field cannot have 256 distinct values; that is the tell.
* EXP-0180's only bits-4..7 arm is `DSTNIB`, **32 records, and it runs on
  `half_alu_ext8` (the 8-byte form), not on `half_alu_fma12` at all.**

So `half_alu_fma12.dst` has **never been swept in the 12-byte form**. The diagnosis that
"it does not need more values, it needs an oracle" is half right: it needs an oracle **and**
its 16 values, in the 12-byte form. This experiment dispatches both.

The two defects EXP-0196 *did* identify are real and are what §3–§5 are built to remove:
no host prediction anywhere in EXP-0180's records (`oracle` is absent from every one), and a
read-back whose payload is not isolated from run-varying register content.

---

## 2. Question

**Can each of the four fields be given arbitrary values in a carrier where a HOST-COMPUTED,
PER-VALUE-DISCRIMINATING oracle predicts the complete post-state, and does the hardware
match that prediction across its whole encodable range in two independent gated runs?**

---

## 3. Hypotheses (falsifiable, one per field)

* **H1 (`half_alu_fma12.dst`).** Bits 4..7 of byte0 select the destination GPR *n* of the
  12-byte fp16 FMA form. The result lands in **`r[n]`'s LOW 16 bits with `r[n]`'s HIGH 16
  bits preserved**, and no other architectural register changes. All 16 values are legal.
  *Refuter:* any dispatched value for which the result appears in a register other than
  `r[value]`, or for which `r[value]`'s high half is not preserved, or which faults/hangs.
* **H2 (`half_alu_fma12.ext`).** `ext` is **not one field**. Within it, byte+4 bits 0..1 are
  the length selector, byte+4 bits 2..7 are operation modifiers, and **byte+5 is the third
  fp16 operand's half-register descriptor**; bytes +6..+11 are largely inert at this
  (opsel, length) point. *Refuter:* a byte+5 value whose observed result is not the frozen
  oracle's prediction for that operand; or a byte in +6..+11 that moves the observable on
  more than a handful of values (which would show the residue is live and the split wrong).
  **Pre-registered outcome bound: `ext` CANNOT reach `hardware-run` whatever happens** —
  2048 sampled values out of 2^64 is 0.0% coverage. Its deliverable is a `db_defects` entry.
* **H3 (`half_pack.dstlo`) and H4 (`half_pack.b3`).** `half_pack` (`byte0 == 0x18`) is the
  **high-lane sibling** of the `byte0 low-nibble 0` half-ALU family, in the same
  `[dst<<4|tag] [hB] [(opflags<<3)|opsel] [hA]` operand shape. Therefore **byte+1 and byte+3
  are SOURCE half-register descriptors**, not a destination and not a raw byte, and
  `r[byte0>>4]`'s **HIGH** 16 bits receive the result while its LOW 16 bits are preserved.
  *Refuter:* a value of byte+1 (or byte+3) whose observed result does not equal the oracle's
  prediction for the half-lane that descriptor names; or an observable that does not move
  when the descriptor is changed to a different seeded lane.

---

## 4. The oracle — host-computed, per-value discriminating, and its precision assumption

### 4.1 Where it comes from

Fitted OFFLINE, before this file was frozen, from **our own committed EXP-0180 raw**
(`g17p_run02`, arms `F12_FMA`, fields `dst`+`srcA`, 512 usable cases per carrier, both
carriers), by `analysis/fit_model_offline.py`. Against the **observed pre-dump** of each
case, the model

> `r[byte0>>4].lo = fp16_rn( |h(byte+1)| * h(byte+3) - h(byte+5) )`, `r[byte0>>4].hi` preserved

matched **256/256 on carrier C_HI and 256/256 on carrier C_LO**, where
`h(d) -> (GPR (d & 0x7F) >> 1, half d & 1)` and a descriptor naming an unseeded GPR reads 0.
Six competing models (`a*b+c`, `-(a*b+c)`, `a*b-c`, `abs(a)*b+c`, `c*b-a`, `a-c`) each matched
strictly fewer cases. EXP-0180's base carried `byte+4 = 0x93`; the same offline pass shows
`byte+4 = 0x13` gives the identical arithmetic **without** the source-release side effect
(`0x93` zeroes the half-lane named by byte+5; `0x13` does not), so **this experiment's base
instance uses `byte+4 = 0x13`** and its oracle predicts no side effect.

### 4.2 What is predicted, per case

The oracle predicts **the entire 16-word post-dump**, computed on the host from
(a) the case's own **observed pre-dump** and (b) the frozen model:

```
post[j] = pre[j]                                  for every j not written
post[d] = (pre[d] & 0xFFFF0000) | result16        d = destination GPR      (fma12: LOW half)
post[d] = (result16 << 16) | (pre[d] & 0xFFFF)    d = destination GPR      (half_pack: HIGH half)
post[R_IDX] = 0                                   (zeroed by the dump's own index re-seed)
post[m] = marker_value(m)                         for each surviving length marker m
```

This is **discriminating by construction**: for `half_alu_fma12.dst` the predicted vector
differs at a *different word* for each of the 16 values; for `half_pack.dstlo`/`b3` and for
`ext` byte+5 the predicted *value* differs per value of the field. A gate on a constant
oracle is pre-registered as a FAILURE (§6, G5).

### 4.3 Precision assumption — stated, and measured both ways

The oracle evaluates the expression in **IEEE binary64** and rounds **once** to
**binary16, round-to-nearest-even** (Python `struct.pack("<e", ...)`), i.e. it assumes the
hardware FMA is **fused: a single rounding after the multiply-add**. This is not asserted,
it is *tested*: every case also records `oracle_alt2r`, the **two-rounding** prediction
(round `|a|*b` to fp16, then subtract, then round again). If the two ever disagree and the
hardware follows the two-rounding model, the raw says so per case and the verdict follows the
data, not this paragraph.

Two further precision facts are recorded per case rather than assumed:

* `oracle_subnormal` — true when the predicted fp16 result is subnormal. If mismatches
  concentrate there, the finding is **flush-to-zero**, a hardware fact, and must not be
  charged against the field.
* `oracle_overflow` — true when the binary64 value is outside binary16's finite range.

`half_pack`'s predicted op is a single fp16 add, so it has exactly one rounding and no
fused/unfused ambiguity; the subnormal and overflow flags still apply.

### 4.4 The unseeded-register assumption, and how it is checked

Descriptors naming GPRs >= 16 are predicted to read **0**. This is a property of the
*carrier*, not of the silicon, and it is verified per run by a dedicated control
(`__ctl_unseeded`) that names three high registers and requires the oracle-with-zero
prediction to hold. If the control fails, every value whose descriptor names an unseeded
register is marked `undecidable` and excluded from both numerator and denominator, and the
`range` string says so.

---

## 5. Method

### 5.1 Carrier (two authored MSL kernels, four (carrier, layout, seed) arms)

Two authored kernels (`kernels/carrier_a.metal`, `kernels/carrier_b.metal`) with different
buffer signatures give a long `_agc.main` region whose **whole body is replaced** by a
program assembled through the pinned `tools/agx-isa`. The synthesized program is:

```
seed r_j (falu2i -> high half; half-ALU add -> low half) for every non-infrastructure j
PRE sentinel  (mov_imm + device_store)            <- independent of the instruction under test
PRE-DUMP  of all 16 GPRs
[ BLOCK: the instruction under test, then 4 two-byte mov_imm LENGTH MARKERS ]
POST-DUMP of all 16 GPRs
POST sentinel (mov_imm + device_store)            <- re-materialized AFTER the block
stop
```

* **Poison.** The read-back buffer is filled with `0xDEADBEEF` before every dispatch, so
  *wrote the right value* / *wrote a wrong value* / *never ran* are three distinguishable
  outcomes. `carrier_dead` (PRE sentinel present, everything after it still poison, status
  OK) is its own outcome and is never scored as an observation.
* **Integrity sentinels.** PRE in memory before the block; POST written after the block *and*
  after the dump, from a register re-materialized by `mov_imm` at that moment, so the
  instruction under test cannot fake it (EXP-0138 lost six sweeps to a sentinel the
  instruction could clobber).
* **Per-case seed proof.** Every case dumps all 16 GPRs *before* the block. There is **no
  refreshed baseline anywhere**; a case whose pre-dump does not match the frozen seed vector
  is `invalid_run` and can never count as movement.
* **Length markers.** Four `mov_imm` markers immediately follow the instruction under test.
  The number that survives measures the **hardware's** consumed length per case, so a value
  that changes instruction identity can never be scored as movement (G7).

**Two infrastructure layouts**, because the dump's index register and the markers are
unobservable destinations:

| layout | `R_IDX` | `R_ZERO` | markers | dst values OBSERVABLE |
|---|---|---|---|---|
| `HI` | r15 | r14 | r10..r13 | 0..9, 14 |
| `LO` | r0  | r1  | r2..r5   | 1, 6..15 |

Their union covers all 16 dst values and 6 values (1, 6, 7, 8, 9, 14) are covered twice.
A value unobservable in a layout is recorded `undecidable_layout` — never `inert`.

### 5.2 Arms (frozen)

| arm | instruction | field(s) swept | kernel | layout | seeds |
|---|---|---|---|---|---|
| `F12_DST_A` | `half_alu_fma12` | `dst` 0..15 | A | HI | A |
| `F12_DST_B` | `half_alu_fma12` | `dst` 0..15 | B | LO | B |
| `F12_DST_C` | `half_alu_fma12` | `dst` 0..15 | A | LO | B |
| `F12_DST_D` | `half_alu_fma12` | `dst` 0..15 | B | HI | A |
| `F12_EXT_A` | `half_alu_fma12` | `ext` bytes +4..+11, 0..255 each | A | HI | A |
| `F12_EXT_B` | `half_alu_fma12` | `ext` bytes +4..+11, 0..255 each | B | HI | B |
| `HP_A` | `half_pack` | `dstlo` 0..255, `b3` 0..255 | A | HI | A |
| `HP_B` | `half_pack` | `dstlo` 0..255, `b3` 0..255 | B | HI | B |

Base instances (operands are drawn from **r6..r9 only**, the registers that are
non-infrastructure in *both* layouts, so the operand values do not move between arms):

* `half_alu_fma12`: `[ (dst<<4)|0x0 ] [ 0x0D ] [ 0x06 ] [ 0x11 ] [ 0x13 ] [ 0x12 ] [ 00 00 00 80 01 00 ]`
  — `hA = 0x0D` (r6.hi), `hB = 0x11` (r8.hi), `hC = 0x12` (r9.lo); byte+2 = opsel 6 (hfma),
  opflags 0; byte+4 = 0x13 (length selector 3 -> 12 bytes, negate-c, no source release).
* `half_pack`: `[ 0x18 ] [ 0x0D ] [ 0x18 ] [ 0x11 ]` — dst r1, `hB = 0x0D` (r6.hi),
  byte+2 = 0x18 (the value our own compiled `half2 add` uses), `hA = 0x11` (r8.hi).
  When `dstlo` is swept, byte+3 is held at 0x11; when `b3` is swept, byte+1 is held at 0x0D.

### 5.3 Coverage (FIELD-SWEEP-PROTOCOL §3.3)

* `dst`, width 4 -> **all 16 values**, dense, in each of 4 arms.
* `dstlo`, `b3`, width 8 -> **all 256 values**, dense, in each of 2 arms.
* `ext`, width 64 -> every constituent byte swept 0..255 (8 x 256 = 2048 per arm).
  **Coverage 2048 / 2^64 = 0.0%; pre-registered as unable to reach `hardware-run`.**

### 5.4 Falsifiers and controls (each pre-registered to produce a specific NON-match)

| id | what it does | pre-registered expectation |
|---|---|---|
| `__fals_F1_null` | the block is replaced by four `mov_imm(R_ZERO,0)` pads | oracle MISMATCH on every arm: no result is written anywhere. Proves the criterion can return "no". |
| `__fals_F2_opsel` | `half_alu_fma12` byte+2 opsel 6 -> 4 (hadd) | oracle MISMATCH (and, per EXP-0180's measured length map, an instruction-identity change: 6 bytes at m=3) |
| `__fals_F3_hp_opsel` | `half_pack` byte+2 0x18 -> 0x19 | oracle MISMATCH: a different operation in the same slot |
| `__fals_F4_dstshift` | `half_alu_fma12` dst nibble fixed at 1 but the oracle is asked to predict dst 2 | oracle MISMATCH by construction (a host-side self-check that the comparison is not vacuous) |
| `__ctl_live_srcA` | at fixed `dst`, byte+1 walks 8 seeded descriptors | the observable MUST move, and the oracle MUST match, on >= 6 of 8 — the **detection-power conjunct**. An arm that fails it cannot support an inert or a null verdict (FIELD-SWEEP-PROTOCOL §5a). |
| `__ctl_unseeded` | descriptors naming GPRs 16, 31, 63 | oracle-with-zero prediction must hold (§4.4) |
| `__ctl_hp_live` | `half_pack` byte+1 walks 8 seeded descriptors | as `__ctl_live_srcA`, for the half_pack arms |

### 5.5 Runs

* `pilot01` — instruments only (anchors, falsifiers, controls, the 16 dst values, and byte+4
  of `ext`). **Not evidence for any field verdict.** Its job is to admit or reject each arm.
  A carrier that fails admission is REJECTED, not repaired.
* `g17p_run01`, `g17p_run02` — the two **gated** runs, full matrix, `run02` in reverse case
  order so an order-dependent artefact cannot survive both.
* Run ids are **never reused or topped up**. A partial capture is retained and a replacement
  takes a new id.

### 5.6 Timeouts, safety, and what is NOT done

* Per-request watchdog **8.0 s**; `harness/saferunner.py` (one reader thread per child,
  DEF-0178-1) so a timeout cannot manufacture a cascade of false hangs. A **malformed**
  response is `measurement_failed` — a failure to measure, never an observation, retried up
  to 3 times, and excluded from `values_dispatched` if it never resolves.
* Every remote command is wrapped in a hard `perl -e 'alarm N; exec @ARGV'` timeout.
* **No abort path**: every value dispatches regardless of outcome. Faults, hangs and silent
  zeros are results and are kept.
* Non-`ok` cases record the **OS fault-classification string** verbatim;
  `...InnocentVictim` and friends are segregated as sibling-contamination, not as encodings.
* `fault`/`hang` are never concluded from a single observation: up to 3 attempts, and the
  poisoned buffer adjudicates offline where it can.
* **Known hazard, declared as a courtesy (FIELD-SWEEP-PROTOCOL §7):** the `ext` byte+4 sweep
  deliberately drives the family's **length selector** through all four settings, so
  instruction-stream desync is expected by design. EXP-0180 ran the same sweep on this
  machine with zero hangs, so no budget is pre-set; if two genuine hangs occur in one arm,
  that arm STOPS and is reported PARTIAL.
* `macvdmtool` is **never** run. If the neo stops answering, this experiment reports BLOCKED.
* The neo is a compute target: `raw/` is pulled back after every run, not at the end.

---

## 6. The promotion gate — written so it CAN return "no"

Per field, per gated run, and then across the two runs. **All of G1..G7 must hold.**

* **G1 dense + non-aliased.** `values_dispatched == encodable_range`, and
  `distinct_bytes == values_dispatched`, and every dispatched encoding differs from the
  anchor **only inside the field's `start`/`width` span taken from `db.json`**. (The aliasing
  trap: `match`-pinned bits the assembler cannot clear make different values assemble to
  identical bytes. This experiment builds the family byte-by-byte precisely so the span is
  reachable, and asserts the span-only property in `harness/selftest.py` offline.)
* **G2 valid observations.** Every value has, in BOTH runs, `status OK`, `seed_ok`, correct
  PRE and POST sentinels, and is not `carrier_dead` / `measurement_failed` / `undecodable`.
* **G3 cross-run agreement >= 99%** of values, comparing the observed post-vector digest.
* **G4 movement.** `moved >= 2 * disagree AND moved > 0`, where `moved` counts values whose
  observed post-digest differs from the arm's single anchor observation. (Written as
  `2 * disagree`, **not** `2 * max(disagree, 1)` — that form cannot promote a width-1 field
  by arithmetic alone, DEF-0178.)
* **G5 oracle discrimination and agreement.** The oracle must produce **>= 2 distinct
  predicted post-digests** across the swept values — a constant oracle predicts the
  instruction's effect, not the field's, and is pre-registered as a FAILING gate — **and**
  `oracle_match` must hold on **>= 99%** of decidable values in **both** runs.
* **G6 the falsifiers fired.** Every `__fals_*` case for the arm must be a **non-match**.
  If a falsifier matches, the criterion cannot say "no" and the arm is void.
* **G7 identity stable.** `tok_instr` and the surviving-marker count equal the anchor's.
  Values that change identity are RECORDED and excluded from G3/G4/G5's numerator **and**
  denominator, and the exclusion count is reported in `range`.

**Outcomes.** All gates pass over the full encodable range -> `hardware-run`. Gates pass only
at sampled points, or the range is not dense -> `isolated-byte-diff`. Any of G2/G3/G5/G6
fails -> the field stays `untested` and the failure is stated. A field whose observable never
moves is **not** promoted and **not** declared inert: per FIELD-SWEEP-PROTOCOL §9 an inert
claim needs a positive control in the same dimension, and `__ctl_live_*` is exactly that
conjunct.

`half_alu_fma12.ext` is pre-registered as **unable to pass G1** (2048 of 2^64). Its result is
recorded under `db_defects` and its label stays `untested`, whatever the sweep shows.

---

## 7. Confounders considered

1. **Aliased encodings** — addressed by G1 and by building byte-by-byte instead of through
   `isadb.assemble` (which cannot clear `match`-pinned bits).
2. **Observable co-varying with the field** (EXP-0140/DEF-0168) — the observable is the
   *whole* 16-GPR post-dump plus both sentinels, and the oracle is computed from the case's
   own pre-dump. For `dst` the field selects *where* the write lands, and the read-back reads
   **every** register, so the observable cannot follow the field.
3. **Round-trip is not an emitter gate** (EXP-0170) — `rt_ok` is recorded and is never cited.
4. **Reader-thread cascade** (DEF-0178-1) — `saferunner.py`, and malformed != hang.
5. **Busy-machine contamination** (EXP-0158/0160) — sweeps run unlocked, but a case that is
   `fault`/`hang`/victim is retried, and the poisoned buffer adjudicates offline. Concurrent
   GPU activity is sampled into `raw/<run>/03_procsample.jsonl` so "the machine was quiet" is
   a measurement and not a claim.
6. **Host-side precision** — §4.3. A mismatch that is a host rounding error must not be
   recorded as a hardware fact, so both rounding models are computed per case.
7. **Unseeded registers** — §4.4.
8. **Length selector inside the swept region** — G7 plus the hardware marker chain.

## 8. Environment, pins, reproduction

* Pinned ISA: `work/frozen/db.json` `2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4`,
  `work/frozen/isadb.py` `500db91a6077cd1968570dd1f7c08ae22a63bbfb39e688168ce711397375aa9f`.
  Resolution is explicit and there is **no fall-through** to a shared copy on the neo.
* Repo revision at pre-registration: `f59821fe5e896b09a1bd33b41e7a9f1b7df6b4b4` (recorded, not
  gated on — sibling experiments commit continuously; a capture is valid if the **authored
  blob hashes** match, per SUBAGENT_BRIEF).
* Authored-source hashes are frozen in `CAPTURE_CONTRACT.json` before the first gated run,
  together with `raw/FREEZE_MARKER.txt`.
* Reproduction commands: `README.md` §Reproduction.

## 9. Raw record schema (one JSON object per case, appended and fsync'd immediately)

```json
{"arm":"F12_DST_A","instr":"half_alu_fma12","field":"dst","value":7,
 "fstart":4,"fwidth":4,"byte_index":null,"bytes":"70...","anchor":"10...",
 "carrier":"A","layout":"HI","seeds":"A",
 "observed":{"pre":[16 words],"post":[16 words],"pre_sent":90,"post_sent":111,
             "stray":[[word,value]...],"n_stray":0},
 "oracle":{"post":[16 words],"result16":15360,"model":"abs(a)*b-c",
           "alt2r":15360,"subnormal":false,"overflow":false,"undecidable":null},
 "oracle_match":true,"oracle_match_alt2r":true,
 "outcome":"ok","status":"OK","fault_class":null,"victim":false,
 "seed_ok":true,"sentinel_bad":false,"tok_instr":"half_alu_fma12","tok_len":12,
 "rt_ok":true,"hw_markers":4,"identity_changed":false,
 "match":false,"attempts":[...],"resp_raw":[...],"seq":1,"t":1788000000.0}
```

`outcome` domain (frozen, ordered — a failure to MEASURE is never an observation):
`measurement_failed` | `hang` | `fault` | `undecodable` | `carrier_dead` | `invalid_run` |
`silent_zero` | `wrong_value` | `ok`.

## 10. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/), our own assembled bytes, our own committed raw
                  from EXP-0180, and tools/agx-isa (our own DB)
Apple binary introspection: NONE
Reproduction: README.md -> Reproduction
Evidence: raw/pilot01, raw/g17p_run01, raw/g17p_run02
```

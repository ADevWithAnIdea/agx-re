# EXP-0166 — RESULTS

**Target of the evidence adjudicated:** Apple **M4 / G16G**. **Target of this experiment:** none —
offline re-derivation only. The A18 Pro was never touched, M5 was never touched, `macvdmtool` was
never invoked, and no GPU was dispatched to.

**Clean-room provenance**
```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed raw evidence only)
Inputs inspected: EXP-0146's append-only JSONL captures (from MSL we authored) and
                  tools/agx-isa/{db,validation}.json; later experiments' committed analysis
Apple binary introspection: NONE
Reproduction: python3 analysis/emit_deliverables.py
Evidence: EXP-0146 raw/run01, raw/run03, raw/run04 (hashes in manifest.json) + this analysis/
```

---

## 0. Headline — the plain number

**Of EXP-0146's 94 verdicts, 12 survive as merge-ready rows. Not one survives with the label
EXP-0146 gave it as its own independent claim.**

That is a recovery of **12.8 %**, and the recovered rows are mostly *not* the ones EXP-0146 was
proudest of. Hypothesis **H1 was confirmed and falsifier F1 did not fire** (F1 would have needed
≥ 60 survivors).

The single sentence that explains most of the loss:

> **EXP-0146's oracle is the unmutated baseline output, so its `match: true` / "ok at {N values}"
> sets measure INERTNESS, not demonstrated control of a field.** A verdict reading "hardware-run,
> 256 values tested, ok at {128 values}" means *128 values changed nothing* — which, on exactly one
> carrier, is the weakest possible evidence, not the strongest.

Two consequences worth separating:

- **All 53 withheld keys were withheld on evidence grounds or because someone else already did it
  better** — 23 vetoed because a later (mostly G17P) experiment overtook them, 11 already at an
  equal-or-stronger label, 12 too unstable across the two gated runs, 7 inert on exactly one
  carrier. None was withheld for the key-convention problem that orphaned the file.
- **27 of the 94 keys were never `db.json` fields at all.** They are raw `byte+N` probes. They are
  not a bookkeeping remainder — they are where the most valuable findings in this experiment came
  from, and they are reported as **six proposed descriptor defects** (§5).

The `@carrier` key convention was *right* and must not be flattened: **H2 confirmed, F2 did not
fire.** `n2_op6`'s six fields verdict `stable-live` on the `sfu_sin` carrier and `withheld` on
`u64eq` in the same experiment, with cross-run disagreement rates of 0 % and 100 % respectively.
Dropping the suffix would have merged a coin flip.

---

## 1. What was directly observed

### 1.1 The twelve survivors

| key | new label | was | carrier | N | D | M | I | agree |
|---|---|---|---|---:|---:|---:|---:|---:|
| `iadd2.addsub` | `hardware-run` | untested | `k_u64sub` | 2 | 0 | 1 | 1 | 1.000 |
| `iadd2.opc_tail` | `hardware-run` | untested | `k_u64sub` | 256 | 0 | 192 | 64 | 1.000 |
| `iadd2.opc_tail2` | `hardware-run` | untested | `k_u64sub` | 256 | 0 | 192 | 64 | 1.000 |
| `iadd2.srcB_imm` | `hardware-run` | untested | `k_u64sub` | 256 | 0 | 252 | 4 | 1.000 |
| `iadd2.srcB_reg_hi` | `hardware-run` | untested | `k_u64sub` | 128 | 0 | 64 | 64 | 1.000 |
| `ilogic.lut_a_sel` | `hardware-run` | untested | `k_logic_and` | 4 | 0 | 3 | 1 | 1.000 |
| `ilogic.lut_a_z` | `hardware-run` | corpus-correlation | `k_logic_and` | 8 | 0 | 7 | 1 | 1.000 |
| `irotate.operands` | `isolated-byte-diff` | tokenization-only | `k_rot_imm` | *(5 bytes)* | 1 | 1102 | 143 | — |
| `irotate.tail` | `isolated-byte-diff` | tokenization-only | `k_rot_imm` | *(4 bytes)* | 1 | 795 | 198 | — |
| `n2_op10.dst` | `isolated-byte-diff` | tokenization-only | `k_roundmodes` | 16 | 0 | 15 | 1 | 1.000 |
| `n2_op8.opsel` | `hardware-run` | tokenization-only | `k_sfu_sin` | 254 | 1 | 252 | 1 | 0.996 |
| `n2_op8.srcA_desc` | `hardware-run` | tokenization-only | `k_sfu_sin` | 256 | 1 | 254 | 1 | 0.996 |

`N` = values where both gated runs are informative; `D` = cross-run disagreements; `M` = moved the
observable, agreeing across runs; `I` = reproduced the host-computed oracle, agreeing across runs.
Full per-value detail: `analysis/derived_stats.json`, `analysis/decomposed_fields.json`.

`work/merge_verdicts.py --dry-run` applies all 12 with **0 skipped and 0 problems**: +12
emitter-grade fields (605 → 617). **No instruction changes emittability status** (44 → 44).

### 1.2 Why "no instruction becomes emittable" is the honest answer

Three near-misses, each blocked by exactly one field:

- **`irotate`** — `operands` and `tail` recovered here; **`b2` is `untested`** and this experiment
  cannot fix it, because EXP-0146's `b2` arm only ever reached **32 of 256 encodings** (§5, DEF-0166-1).
- **`ilogic`** — `lut_a_sel` and `lut_a_z` recovered here; **`lut_a_free` stays withheld**. It is
  dense-INERT (8/8 sub-values reproduce) but on exactly **one** carrier, and single-carrier
  inertness is not emitter grade. **One dense byte+4 sweep on a second carrier closes `ilogic`.**
- **`iadd2`** — five fields recovered (`addsub`, `opc_tail`, `opc_tail2`, `srcB_imm`,
  `srcB_reg_hi`), but `srcA` and `srcB_ext` are hard-vetoed as refuted on G17P, `b2_fmt` and
  `b2_bit0` are inert on this one carrier, and `lenbit`/`store_en` are single-bit arms that this
  carrier cannot strengthen further.

### 1.3 H3 confirmed: a "constraint" that is really a register field — visible in EXP-0146's own raw

The dispatch flagged `iadd2.srcB_ext`, where EXP-0146 published `(v & 0x7C) == 0x00`. Pre-registered
test: if bits 2–6 select a register in the `reg<<2` packing, then grouping the 128 values by `v>>2`
must give 32 groups that are each *internally identical*, because the low two bits are then
don't-care.

**Result: 128/128 values agree across the two gated runs, and 32 of 32 groups collapse to exactly
one observable.** Falsifier F3 did not fire. Only 6 distinct observables appear across the 32
indices and groups 6…31 are all identical — the carrier only distinguishes the registers it
actually loaded, so **the packing is established and the per-register map is not**.

This reproduces EXP-0154's G17P finding (DEF-0154-4) **on M4, from data captured a day before
EXP-0154 ran.** The refutation was latent in EXP-0146's own capture the whole time; its analysis
simply never grouped the values. Full evidence: `analysis/h3_srcB_ext.json`.

### 1.4 A measurement artefact that had to be corrected before any number was trustworthy

**5 of the 24 arm-baselines across the two gated runs are themselves bad measurements** —
`n2_op6@u64eq`, `n2_op8@sfu_sin`, `n2_op10@roundmodes` are `silent_zero` in run01;
`shift_amt_move@rot_var` is a `fault` and `sfu_marker@sfu_sin` a `silent_zero` in run03. Comparing
cases against a flaked baseline marks the *unmutated* encoding as "moved" and inflates the counters.
Separately, the `sfu_sin` carrier is float-valued and judged with a `1e-3` tolerance, so exact word
equality is the wrong comparator there and flags even a clean baseline.

Amendment **A3** replaces the baseline *record* with the host-computed `oracle` carried in every
case record — the same quantity, measured off the GPU. It changes the verdict of **12 of 90 arms**,
every one of them inside a flaked-baseline arm, and every one in the same direction. Both
comparators are computed and both are in `analysis/derived_stats.json` (`*_A3` and `*_lit`).

This is EXP-0160's principle applied offline: *contamination can destroy an observation but never
fabricate a coherent one.*

---

## 2. Where M4 and G17P disagree — reported, not averaged

### 2.1 `ilogic.outmod` — the one live contradiction, and it is withheld

| | M4 (EXP-0146, carrier `k_logic_and`) | G17P (EXP-0154, carrier `SYNTH+LIFTED:k_and@ilogic[32:42]`) |
|---|---|---|
| coverage | 0..255 dense, 256/256 encodings | 253 values sampled |
| result | **128 values move the observable** — every value with bit 7 **clear** silently zeroes | **"inert across the whole encodable range"**, 253/253 ok |
| cross-run | D = 0 | 2 gated runs |

That is literally the G3 veto condition ("a later experiment found the field inert where EXP-0146
called it live"), so **the row is withheld**, per the frozen rule and *not* because the M4 evidence
is weak — it is one of the cleanest arms in the file.

The likeliest explanation is the carrier and not the silicon: EXP-0154 judges by a 16-register
dump, in which a store-enable bit is invisible, while EXP-0146's carrier stores the result so the
same bit gates the observable. **That is a hypothesis, not a measurement.** Note the field currently
reads `untested` in `validation.json` — EXP-0164's audit withdrew EXP-0154's row for being
inert-on-one-carrier — so this is exactly the EXP-0155 pattern the dispatch cites, and the M4 arm
would be a two-notch upgrade if the orchestrator chooses to override the veto.

**Recommended: one G17P `ilogic` arm with a store-consumed observable and a dense byte+7 sweep
settles it.** Whichever way it lands, one of two committed records needs correcting, and an emitter
that trusted "inert" would drop the store.

### 2.2 `n2_op8` — a target divergence, not a contradiction

EXP-0157 found **zero occurrences of `n2_op8` across 59 own-MSL programs on G17P** in two
provocation rounds, including 20 SFU-family programs. G17P can therefore neither confirm nor refute
EXP-0146, and `CLAUDE.md` keeps M4 evidence valid on its own target — so `n2_op8.opsel` and
`n2_op8.srcA_desc` merge as `target: M4`.

**⚠ The orchestrator must weigh this before merging:** `merge_verdicts.py`'s
`emittable_instructions` counter is **target-blind**. These two rows do not flip `n2_op8` (`dst` and
`body` are still withheld), but completing it later would make an instruction **that cannot be
reached at all on the closure target** count as emittable. Closure is measured against full G17P.

### 2.3 `irotate` — G17P is weaker, and one byte is dangerous

EXP-0154 swept the same nine bytes on G17P and left **byte+7, +8 and +10 `untested`**; the M4 rows
merged here are the only evidence for those three. That is not a contradiction, but it is a
divergence, and it carries a safety fact that rides along in the merged note:
**EXP-0154 reports `irotate.operands` byte+7 = 231/232 genuinely hangs the GPU on G17P**
(`kIOGPUCommandBufferCallbackErrorHang`, contained, majority-of-3).

### 2.4 A reproduction, for balance

The dispatch's positive control (**F5**) passed: re-deriving `carry_gen` byte+2 from EXP-0146's raw
gives exactly `(v & 0xCD) == 0x05`, accept-set `{0x05,0x07,0x15,0x17,0x25,0x27,0x35,0x37}` — the
value-for-value G16G→G17P reproduction EXP-0161 records as DEF-0161-6. The pipeline can see a real
result; it is not rejecting everything because it is broken.

---

## 3. What the 23 vetoed keys tell us

| instruction | why nothing merges |
|---|---|
| `carry_gen` (5) | superseded value-for-value on G17P by EXP-0161 in two carriers, already merged — **and `db.json` renamed these fields *because of EXP-0146***: `subop`→`srcA`, `srcA`→`srcB`. A name-keyed merge would have written two rows into the **wrong fields**. Bit-relocation (A2) caught it automatically. |
| `n2_op6` (6) | EXP-0157 swept four independent G17P carriers vs EXP-0146's two; all six already `hardware-run`. |
| `n3_mov` (3) | EXP-0157 measured **the same `u64eq` carrier** on G17P and the orchestrator **explicitly withheld those three rows**. The M4 arm adds no second structurally different carrier; merging it would contradict that decision. |
| `mov_zext16` (4) | descriptor under active repair by EXP-0165 (DEF-0161-2); EXP-0161's own verdicts are held back because the field names change under the fix. See §5 DEF-0166-3 — EXP-0146's own data now *supports* the repair. |
| `iadd2.srcB_ext`, `.srcA` (2) | refuted on G17P; `db.json` carries a verbatim "Do NOT adopt EXP-0146's rule" warning. §1.3 confirms the refutation on M4 too. |
| `ilogic.srcA`, `.srcB` (2) | operand labels swapped relative to EXP-0146's LUT table (DEF-0154-5); already `hardware-run` under the corrected labelling. |
| `ilogic.outmod` (1) | §2.1. |

---

## 4. What this says about the *convention* problem

The dispatch's framing — "the cause is mundane, a key-convention mismatch" — is right about the
mechanism and understates the consequence. Three independent naming hazards showed up:

1. **Renames.** `carry_gen`'s two operand bytes were renamed *because of EXP-0146*. Its own verdict
   keys now point at different fields.
2. **Splits.** `ilogic.lut_a` became `lut_a_sel`/`lut_a_free`/`lut_a_z`, and `mov_zext16` was
   re-modelled outright. A name-keyed merge would silently drop the evidence (`lut_a` no longer
   exists) or apply it to the wrong bits.
3. **New fields.** `sfu_marker` gained `b0_hi`/`b1_hi` *while this experiment was running*.

**A verdict file keyed by field NAME is not safely mergeable across a moving `db.json`.** The fix
used here — re-locate the swept bits from the recorded `bytes` and match on `(start, width)` — is
mechanical, needs no trust in either party's bookkeeping, and is what let §3's `carry_gen` trap and
§5's `mov_zext16` corroboration fall out automatically. **Recommendation: require every
`field_verdicts.json` row to carry the `(start, width)` it swept**, and have `merge_verdicts.py`
refuse a row whose bits no longer match the named field.

---

## 5. Six proposed `db.json` defects (`analysis/proposed_db_defects.json`)

`db.json` was **not** edited — EXP-0165 owns it this session.

### DEF-0166-1 — 53 fields have bits that a `match` constant also sets (the biggest finding here)

`tools/agx-isa/isadb.py::assemble()` ORs the match constant, then ORs the field values. **An OR
cannot clear a bit.** So wherever a declared field overlaps a `match` bit that is *set*, that bit is
stuck at 1 for every value an emitter — or a sweep — supplies. A static scan of `db.json` finds
**53 such fields across 40+ instructions**.

Demonstrated, not merely inferred, from EXP-0146's recorded bytes:

| arm | dispatched | distinct encodings actually spliced | claimed in EXP-0146 |
|---|---:|---:|---|
| `irotate.b1` | 256 | **128** | "256 values tested (full 8-bit dense)" |
| `irotate.b2` | 256 | **32** | "256 values tested (full 8-bit dense)" |
| `shift_amt_move.kind` | 256 | **64** | "256 values tested (full 8-bit dense)" |

Worked example — `shift_amt_move.kind`, `match [16,4,12]` pins byte+2's low nibble to `0xC` while
the field is declared over the whole byte: `v=0 → 0b010c05`, `v=1 → 0b010d05`, `v=2 → 0b010e05`,
`v=3 → 0b010f05`, **`v=4 → 0b010c05` (identical to `v=0`)**.

Two consequences, one for evidence and one for the deliverable:
- **Any sweep built through `isadb.assemble()` may silently under-cover its field.** The check is
  cheap and offline: count distinct `bytes` strings, never trust the dispatched-value count.
  EXP-0154 is *not* affected for `irotate.b1` — its raw shows 256 distinct byte strings, so its
  harness wrote bytes directly.
- **An emitter built from `db.json` literally would emit the same over-set bits.** Proposed fix:
  narrow the field or drop the redundant match entry (both are DECODE changes needing the corpus
  A/B), and make `assemble()` **raise** when a supplied field value's bits are already pinned.

### DEF-0166-2 — `iadd2.srcB_ext` is a register selector, and EXP-0146's own M4 raw proves it
§1.3. The M4 half of EXP-0154's G17P DEF-0154-4.

### DEF-0166-3 — EXP-0146's `zext16` carrier is DEAD for `mov_zext16`, on M4, by its own data
Decomposing EXP-0146's sweeps into the *repaired* field model gives: byte0's high nibble (the
repaired `src_reg`, 16/16 sub-values) **inert**; byte+1 (129 of 256 encodings reached) **inert**;
byte+3 bits 3–7 (the repaired `extend`, 32/32) **inert**. Only `subform` (byte+2) moves.
A live carrier cannot produce that. EXP-0161 diagnosed the carrier as dead **from G17P**; this is
the same conclusion **from M4, out of EXP-0146's own bytes**, and it independently supports
EXP-0165's repair.

### DEF-0166-4 — `n2_op10.immword` and `n2_op8.body` each span bytes with different roles
`n2_op10` byte+5 moves the observable for 242 of 256 values while **byte+9 moves it for zero of
256** — a dead byte inside a field typed `imm`. `n2_op8` byte+3/+5/+6/+7 are stable-live while
byte+4 is unstable. Both composites are withheld here; a descriptor split would let the live bytes
reach emitter grade without dragging a dead byte along. *Clean-room: only per-byte accept/reject
envelopes are recorded — the SFU range-reduction / marshalling coefficient sequence is deliberately
not reconstructed.*

### DEF-0166-5 — `ilogic.outmod` M4-vs-G17P divergence
§2.1.

### DEF-0166-6 — `sfu_marker.b0_hi`'s M4 half is unstable; its G17P half is what carries it
The structural blocker is **gone**: EXP-0165 landed the C7b relaxation mid-experiment, `sfu_marker`
now has two real fields, and both were merged citing EXP-0146 + EXP-0157 + EXP-0165 — which
vindicates this recovery direction. The caveat: re-adjudicated here, `b1_hi` is clean (N=64, D=0,
accept-set exactly the published rule) but **`b0_hi` has 19 cross-run fault↔silent-zero flips**
(agreement 0.906) and does not clear the 99 % bar *on M4*. Its label should rest on EXP-0157's three
G17P carriers. This experiment offers no `sfu_marker` row — both are G2-redundant.

---

## 6. Limitations — what a reader must not over-read

1. **Everything here is M4/G16G supporting evidence.** Closure is measured against full G17P. No
   row may be relabelled `A18`/`G17P` without a fresh G17P run. `target: M4` is used rather than the
   dispatch's `M4/G16G` because `validate_labels.py` accepts only a fixed target vocabulary and
   hard-fails anything else; that file's own comment records `M4 == G16G`.
2. **Carrier scope.** Every accept-set is "what reproduces *this carrier's* result". A singleton
   accept-set (`n2_op8.opsel` → `{0x49}`, `n2_op8.srcA_desc` → `{0xc2}`, `n2_op10.dst` → `{0x3}`)
   establishes "every other value breaks this carrier", **not** an operand map. `n2_op10.dst` is
   capped to `isolated-byte-diff` for exactly this reason (A7); the same caution applies in prose to
   the two `n2_op8` rows, which are typed `raw` and escape A7's literal scope.
3. **The two `irotate` composites are marginal-coverage only.** 1280 of 2^40 and 1024 of 2^32
   combinations, one byte at a time; neither `max` nor `max-1` of either field was ever encoded, so
   `FIELD-SWEEP-PROTOCOL` §3.3's bar for `w > 8` is not met — hence `isolated-byte-diff`, never
   `hardware-run`. The rotate amount is **not** independently emittable from this carrier (byte+6
   admits only `{0x6c,0x6e}`).
4. **`run01` cannot report `innocent_victim`.** It predates the `fault_class` field, so victim cases
   in run01 are invisible and some of the residual `D` is certainly contamination rather than
   hardware. That biases *against* merging, which is the safe direction.
5. **This adjudicates EXP-0146's captures; it does not re-measure the hardware.** A withheld row
   means "this evidence does not support the claim", never "the hardware does not do this".
6. **The tool state moved three times under me.** `db.json` and `validation.json` are being edited
   live by EXP-0165 and the orchestrator; the G2 redundancy gate was computed against the pinned
   snapshots in `work/` (hashes in `manifest.json`) and is **advisory** — `merge_verdicts.py`
   recomputes it at merge time, which is the authority. One row (`sfu_marker.b1_hi`) was dropped
   between passes for exactly this reason, correctly.
7. **No device confirmation.** §6 of the pre-registration was not exercised (coordinator hold), and
   under the amended `FIELD-SWEEP-PROTOCOL` §7 a busy-machine re-run would not have been
   confirmation anyway.

---

## 7. Verdict

**PARTIAL RECOVERY — and the honest number is small.** 12 of 94 verdicts survive; 0 instructions
change emittability; +12 emitter-grade fields. The dispatch asked for "6 defensible upgrades rather
than 26 shaky ones", and 12 is what the evidence actually carries.

The larger return is not in `field_verdicts.json`. It is that re-deriving from raw turned up
**a systemic descriptor defect affecting 53 fields repo-wide**, an M4 reproduction of a G17P
refutation that was sitting unnoticed in EXP-0146's own capture, independent M4 support for
EXP-0165's `mov_zext16` repair, one live M4↔G17P contradiction with a one-arm experiment that would
settle it, and a concrete fix for the merge-convention problem that caused the whole situation.

---

## 8. Recommended next work, in value order

1. **Have `merge_verdicts.py` require and check `(start, width)` per row** (§4). This is the actual
   fix for the class of failure that orphaned EXP-0146, and it is cheap.
2. **Audit the 53 field/`match` overlaps** (DEF-0166-1), and make `isadb.assemble()` raise instead of
   silently ORing. Then re-check any sweep built through it by counting distinct `bytes`.
3. **One `ilogic` arm on G17P with a store-consumed observable**, dense byte+7 — settles DEF-0166-5,
   and a dense byte+4 sweep in the same arm closes `lut_a_free`, which is the **single field**
   standing between `ilogic` and emittable.
4. **A second carrier for `irotate.b2`** — the only field left blocking `irotate`, and EXP-0146's
   arm can never supply it (32 of 256 encodings reachable).
5. **Split `n2_op10.immword` and `n2_op8.body`** (DEF-0166-4) so the live bytes can be promoted
   without the dead ones.
6. **Re-sweep `n2_op10` on G17P** — it has 230 live occurrences there (EXP-0157's census), so a
   fresh G17P sweep is strictly better than the single M4 row merged here.

# EXP-0160 — PRE-REGISTRATION (frozen before any build or run)

**Experiment:** `EXP-0160-g17p-last-field` — close the ONE remaining blocking field on
eight ALU instructions.
**Target:** Apple A18 Pro / **G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9), `192.168.10.243`. Every verdict is `target: G17P`.
**Frozen:** 2026-08-29, before any anchor extraction or dispatch.
**Protocols:** `CODEX.md`, `experiments/FIELD-SWEEP-PROTOCOL.md` (including the new §7A),
`experiments/NEO-TARGET-BRIEF.md`, `experiments/SUBAGENT_BRIEF.md`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal + kernels/carrier_dag.metal (authored by us),
  and the AGX machine code the PUBLIC Metal runtime compiled from that source.
  tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
  EXP-0154's committed raw JSONL was read as PRIOR EVIDENCE for experiment design only.
Apple binary introspection: NONE
```

---

## 1. The question

`tools/agx-isa/validation.json` says eight instructions are blocked from `emittable` by
**exactly one field each**. An emitter that cannot choose that field's value cannot emit the
instruction at all, so each of these is one field away from being usable:

| instruction | blocking field | committed label | width |
|---|---|---|---|
| `falu2_ext` | `ctrl` | `tokenization-only` | 7 |
| `falu3` | `op` | `untested` | 8 |
| `falu3_ext` | `op` | `untested` | 8 |
| `iminmax` | `srcB` | `untested` | 8 |
| `isel8` | `cmp_mode` | `untested` | 8 |
| `imad` | `srcC_desc` | `corpus-correlation` | 8 |
| `half_pack` | `src` | `corpus-correlation` | 8 |
| `falu2i` | `ctrl_lo` | `tokenization-only` | 7 |

Verified against `tools/agx-isa/{db.json,validation.json}` at freeze time; no sibling
experiment has closed any of them.

**Why EXP-0154 did not close them.** Six of the eight were already swept densely on G17P by
EXP-0154 and still came back `untested`. Its promotion rule admitted only two model shapes:
a single mask rule `ok ⟺ (v & M) == V`, and a value→register-index map. Re-reading its
committed raw records (`analysis/prior_scan.py`, `analysis/design_check.py`, desk-only)
shows the failures were **model-class failures and density failures, not data failures**:

* `falu2_ext.ctrl`, `iminmax.srcB`, `isel8.cmp_mode`, `half_pack.src` have a **complete,
  0-exception class table over ≤5 relevant bits** which no mask rule can express;
* `falu3.op` and `falu3_ext.op` **do** satisfy an exact mask rule `(v & 0xd7) == 0x16`,
  and failed only the density test because ~32 values per field were lost to the cross-run
  gate (they fault at `opsel == 7`);
* `imad.srcC_desc` fits neither and needs a wider probe.

This experiment therefore changes the **instrument**, not just the sample size.

## 2. What is new here (and why it can settle the question)

1. **Two independent seed sets per case.** Every case runs twice with different register
   seeds and a byte-identical program shape. A model fitted on set 1 then makes a genuine
   **out-of-sample prediction** about set 2's 16-register post-state. This is what separates
   "value v reproduced the anchor" from "we can predict what value v does".
2. **Poison-buffer framing detection.** The read-back buffer is pre-filled with `0xDEADBEEF`
   (FIELD-SWEEP-PROTOCOL §7A). A dumped word still holding poison proves that register's
   `device_store` never ran — a *framing break* (the mutation changed the instruction's
   LENGTH) rather than a wrong computed value. Recorded as `frame`/`poison_words`.
3. **A richer, pre-registered model class** (§7) that can express "bits 2,3,4 are inert; bits
   0,1 are the length selector; bits 5,6 corrupt the result" — the shape the data actually has.
4. **Decisive structural probes** for the two fields a sweep alone cannot settle
   (`half_pack.src`, `imad.srcC_desc`), described in §5.

## 3. Hypotheses (falsifiable, one per arm)

* **H1 `falu2_ext.ctrl`** — byte+4 bits 0..6 carry the same roles already HW-established for
  `falu2.ctrl` (EXP-0105/0113/0119): bits 0,1 select the instruction LENGTH, bits 2,3,4 are
  inert, bits 5,6 corrupt the destination to zero. Predicted: exactly 4 behaviour classes over
  relevant bits {0,1} × {5,6}, dense over 128 values.
* **H2 `falu3.op` / H3 `falu3_ext.op`** — byte+2 is **not one field**. It is `falu2`'s
  `opsel` (bits 16..18) plus `opflags` (bits 19..23). Predicted: the ok-set is exactly
  `(v & 0xd7) == 0x16`; the low 3 bits change the arithmetic (identifiable across seed sets);
  `opsel == 7` faults; bits 22,23 (byte value bits 6,7) are the silent corruptors.
* **H4 `iminmax.srcB`** — byte+5 is **not a register selector**. `iminmax` follows the same
  6-byte layout as `falu2` (byte+1 srcA, byte+3 srcB, byte+5 modifier byte), so db.json's
  operand slots are shifted by one. Predicted: no value→register model exists, ≥4 of the 8
  bits are inert, and `min(seedA, seedB)` is reproduced by the *byte+1/byte+3* pair under both
  seed sets.
* **H5 `isel8.cmp_mode`** — byte+4 bits 0,1 are the length selector and bits 2..7 are inert.
  Predicted: exactly 128 `ok` values, `(v & 3) ∈ {1,2}`.
* **H6 `imad.srcC_desc`** — byte+7 selects the ADDEND SOURCE, and the immediate addend is
  assembled jointly from byte+6 (`srcC_lo`), byte+7 and byte+8 (`mulsel`). Predicted: the
  observed addend is a function of those three bytes, identifiable from the 2-D grid.
* **H7 `half_pack.src`** — `half_pack` is **two 2-byte half-lane instructions**, not one
  4-byte instruction (this is the mechanism behind DEF-0154-1: A18 emits `18 05 18 03`,
  G17P emits `18 03 18 05`, i.e. the two halves swap with register allocation). Predicted:
  splicing a 2-byte `mov_imm` over bytes +2..+3 leaves the rest of the state intact and writes
  the `mov_imm`'s register.
* **H8 `falu2i.ctrl_lo`** — same family and same byte position as H1; same predicted roles.

**Refuters.** H1/H5/H8 are refuted if the length-selector bits are inert or if >2 bits beyond
{0,1,5,6} are live. H2/H3 are refuted if the ok-set is not `(v & 0xd7) == 0x16` over the dense
range, or if the low 3 bits do not change the computed value. H4 is refuted if any value→register
model reaches ≥90% over ≥6 distinct registers (that would make it a register selector after all).
H6 is refuted if the addend does not depend on byte+6/byte+8. H7 is refuted if the `mov_imm`
splice at +2 breaks the program or fails to write its register.

## 4. Variables

* **Independent:** the one field's value (dense over its full encodable range), and the seed set.
* **Controlled:** carrier, block bytes, program shape, grid/threadgroup (1/1), timeouts,
  the frozen matrix, `db.json`/`isadb.py`/`persistrun.py` (pinned copies on the device).
* **Measured:** the 16-register post-state, the PRE and POST integrity sentinels, the
  command-buffer status and the OS fault-classification string, and the poison-word count.

## 5. Method

Carrier style **SYNTH-WITH-LIFTED-BLOCK**, as EXP-0154: the whole `_agc.main` of an authored
carrier is replaced by a program assembled from `tools/agx-isa`'s own field rules —
seeds → PRE sentinel → **block lifted byte-for-byte from the compiled form of our own MSL** →
16-register dump → POST sentinel → `stop`. Only the swept byte is mutated. Both integrity
sentinels live where the instruction under test cannot name them (PRE stored to memory before
the block; POST written after it), which is the fix for EXP-0138's self-inflicted sentinel trap.

Extra probes (frozen in `harness/casematrix.py`):

* `HALFPACK __split_at2_r6 / __split_at2_r7 / __split_at0_r6 / __split_at0and2` — splice a
  2-byte `mov_imm` we assembled over byte+2..+3 and/or byte+0..+1 of the `half_pack` descriptor.
* `IMAD __2d_desc_lo` (12 × 11) and `__2d_desc_mul` (12 × 8) — `srcC_desc` crossed against
  `srcC_lo` and `mulsel`.

**Falsifier, one per arm:** byte0 of the instruction under test forced to `0x00`. It MUST NOT
score `ok`. If it does, that arm cannot see a difference and **nothing in it is promoted**
(EXP-0154 lost `CARRY_GEN` and `MOV_ZEXT16` exactly this way, correctly).

**Positive control, one per arm:** the anchor's own field value must score `ok` in both seed
sets and both gated runs. If it does not, the arm is reported broken and nothing is promoted.

**Independent (host-computed) oracle:** for each arm the unmutated block's expected result is
computed on the host from the seeds alone (e.g. `saturate(seed[0]+seed[2])` for `falu2_ext`,
`seed[0]*seed[2]+seed[4]` for `falu3`, `min(seed[0],seed[2])` for `iminmax`) and compared with
the measured baseline, in both seed sets. This is what makes the baseline an oracle and not
merely a reference run.

## 6. Runs, safety, timeouts

* Two gated sweep runs of the identical frozen matrix, executed in **opposite arm order**
  (`--order reverse`) so concurrent sibling experiments do not hit the same illegal encodings
  at the same moment. Unlocked and concurrent, per NEO-TARGET-BRIEF.
* Per-request watchdog 8 s (persistent runner); every remote command wrapped in a hard
  `alarm` timeout; `shdump` compile timeout 300 s.
* Baseline re-validated every 250 cases per (arm, seed set); a drift restarts the child.
* Majority-of-3 in the unlocked runs before any `fault`/`hang` is *recorded*.
* **§7A, binding:** no `fault`/`hang` verdict is *promoted* from an unlocked run. Every case
  whose unlocked outcome was `fault`/`hang`/`undecodable` in either run is re-run **5× under
  `~/agxre/gpulease.sh`** by `harness/confirm_faults.py`, and the isolated verdict is what the
  analysis uses.
* Known hang hazard: none of these eight arms is on the known-hang list, but `falu3`'s
  `opsel == 7` faulted 32× per run in EXP-0154. **After two genuine hangs in one arm that arm
  STOPS** and is reported PARTIAL (FIELD-SWEEP-PROTOCOL §8).
* Every case record appended and `fflush`+`fsync`ed as it completes; `PROGRESS.md` per
  milestone; `raw/` pulled back into the repo as each run finishes.
* A partial capture is retained under its own run id, never topped up or reused.

## 7. Promotion rule (FROZEN — this is what the analysis will apply)

A field is promoted only if **all** of P1–P5 hold. Otherwise it stays `untested` (or
`isolated-byte-diff` where stated) and the reason is reported verbatim.

* **P1 — arm validity.** The arm's `__falsifier_byte0` did NOT score `ok`; the anchor's own
  field value scored `ok` in both seed sets and both gated runs; and the host-computed oracle
  matched the measured baseline in both seed sets.
* **P2 — density and cross-run agreement.** All `2^w` values are present, and for each value
  the `outcome` **and** the observed 16-register digest agree between the two gated runs,
  within each seed set.
* **P3 — out-of-sample structural prediction.** For every value, the *register-role signature*
  (per register: unchanged / zeroed / changed / poison) is IDENTICAL under seed set 1 and seed
  set 2. The seeds differ, so a stable signature is a prediction, not a fit.
* **P4 — an exact model, 0 exceptions, from this frozen class:**
  * **M1 MASK** — `ok ⟺ (v & M) == V` over the dense range;
  * **M2 CLASS TABLE** — the set `R` of non-inert bits (bit *i* is inert iff
    `sig(v) == sig(v ^ (1<<i))` for every `v`), with `|R| ≤ w-2` so every equivalence class is
    confirmed by ≥4 distinct field values, and the collapsed table a 0-exception function of `R`;
  * **M3 REGMAP** — a value→register-index model matching ≥90% of identified releases/writes
    over ≥6 distinct registers;
  * **M4 ARITH** — a value→operation map identified from the written value against a
    host-computed function library, agreeing across BOTH seed sets.
* **P5 — fault adjudication.** Every `fault`/`hang`/`undecodable` value in the range has an
  isolated 5× verdict from `confirm_faults.py` under the GPU lease, and that verdict is used.

**Label:** `hardware-run` if P1–P5 hold. `isolated-byte-diff` if P1, P2, P3, P5 hold and P4 is
satisfied only with ≤2 exceptions, or if the field is inert over a merely SAMPLED set.
`untested` otherwise. A model that must be *searched* beyond this frozen class is reported as a
finding, not a promotion.

**Explicitly NOT promotable here:** a field whose class table is entirely inert in this carrier
(no live class) — that proves the carrier is not live for it and is reported as such, per
FIELD-SWEEP-PROTOCOL §3.2.

## 8. Confounders

Concurrent sibling GPU experiments (`…ErrorInnocentVictim` contamination — mitigated by fault
classification, majority-of-3, cross-run gating and §7A isolation); the `db.json` length rule
disagreeing with the hardware (recorded as a defect, never repaired in place); `half_pack`'s
known tokenization defect DEF-0154-1 (worked around: block bounds are literal byte offsets, not
tokenizer output); release-on-read destroying a sentinel (avoided by construction); sibling
agents editing the shared `~/agxre/tools` (avoided: this experiment pins its own copies of
`agx-isa` and `persistrun.py` under `~/agxre/EXP-0160/tools/`).

## 9. Deliverables

`PRE_REGISTRATION.md` (this file), `CAPTURE_CONTRACT.json` (frozen hashes + matrix sha256),
`README.md`, `harness/`, `kernels/`, `analysis/field_verdicts.json` (FIELD-SWEEP-PROTOCOL §5
schema, plus `db_defects`), `RESULTS.md`, `PROGRESS.md`, and immutable `raw/` for every run.
`db.json`, `validation.json`, `docs/` and `PROVENANCE.md` are NOT edited, and nothing is
committed by this experiment.

---

## Addendum A (frozen 2026-08-30, BEFORE the extension runs) — `falu3`/`falu3_ext` `srcB`

**Why.** The dispatch's premise was that each of the eight instructions is ONE field from
emittable. For `falu3` and `falu3_ext` that is **wrong**: `tools/agx-isa/validation.json`
leaves **both** `op` and `srcB` below emitter grade, so closing `op` alone does not unblock
them. `srcB` was sampled at only 29 of its 256 values by EXP-0154 (`ok at {0x81}` for `falu3`,
`ok at {}` for `falu3_ext`) and left `untested`. This addendum sweeps it densely with the same
instrument, under the same promotion rule.

* **H9.** `falu3`/`falu3_ext` byte+3 is the SECOND source-operand descriptor (EXP-0138's
  operand-slot rename), in the family's `(reg<<1)|size` packing. Predicted: the 16-register
  release-on-read dump yields a value→register map that a candidate model explains for ≥90% of
  the identified releases over ≥6 distinct registers, and the anchor value `0x05` names r2.
* **Refuter.** No register model reaches that bar, or the ok-set has no exact model in the
  frozen class — in which case the field is reported as not a register selector, exactly as
  `iminmax.srcB` was.
* **Everything else is unchanged:** same carriers, same lifted blocks, same two seed sets, same
  falsifier (byte0 → `0x00`), same P1–P5, same evidence-validity gate.
* **Frozen separately.** `harness/casematrix_ext.py` + `harness/run_ext.py`; the original
  `harness/casematrix.py` and `harness/run.py` stay byte-identical to the copies hashed in
  `CAPTURE_CONTRACT.json`, so run01/run02 remain exactly reproducible. Extension matrix:
  **1028 cases, sha256 `e919aa1b93a437e7394b707bb4d7ef58d12f994f59b2b5eb0e1f218b83d4d858`**.
  Runs `g17p_20260830_ext_run01` (forward) and `g17p_20260830_ext_run02` (reverse).

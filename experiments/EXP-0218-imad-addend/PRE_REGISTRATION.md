# EXP-0218 — PRE-REGISTRATION (frozen before any addend model was fitted)

**Experiment:** `EXP-0218-imad-addend` — *which byte, if any, carries `imad`'s ADDEND?*
**Kind:** desk re-analysis of already-committed artifacts. **NO DEVICE IS CONTACTED.**
EXP-0213 holds the A18 Pro for quiet Gate E confirmations; this experiment dispatches nothing.
**Frozen:** 2026-08-30, before the first addend model was scored.

```
Clean-room provenance: derived analysis of committed artifacts in this repository.
Device contacted:  NONE.   Apple binary read: NONE.   Shader compiled: NONE.
Raw files written: NONE (raw/ is append-only and this experiment produces no raw).
Repo HEAD at freeze:  f66060f91e35a790db7007d35f4756daf8862d61
Frozen inputs:
  work/db_frozen.json          sha256 90166d9605eef649dc6fa27bf4d2f8610b92b666f285bec1521372277ff2f267
  work/validation_frozen.json  sha256 7e90e4d59ec31911b4c9c09e2c6e4c17cf675e461aba3be4a38bbcc7ca567cce
  work/raw_inputs.sha256       — sha256 of every raw JSONL this experiment reads (13 files)
Files to be edited in tools/agx-isa, docs/, PROVENANCE.md: ZERO. Labels changed: ZERO.
Nothing will be committed by this experiment.
```

---

## 1. The question, and why it is still open

EXP-0216 established from committed bytes that `imad`'s two multiplicands are
**byte+5 (`reg = v>>2`)** and **byte+6 (`reg = v>>3`)**, that `imad` has **no `srcA` field**,
and that **both addend models it tried scored 0**. It closed with the addend explicitly
unresolved: *"WHERE THE ADDEND ACTUALLY LIVES IS STILL OPEN."*

EXP-0160 §5.2 had earlier proposed an answer for one byte — byte+7 bits 3..7 select an
addend held **outside** the instruction — but that conclusion was reached while byte+5 was
believed to be un-swept and un-modelled, and while the descriptor still claimed an immediate
addend. It has never been scored against the whole committed `imad` population, and the two
other bytes EXP-0216 flagged as moving the result (byte+7, byte+8) were never separated.

**4,118 distinct 12-byte `imad` encodings are committed**, with bytes +3 through +11 each
covering all 256 values. That population, not one arm, is what this experiment fits.

## 2. Carriers (the two independent instruments already in the corpus)

| id | experiment(s) | target | carrier | anchor bytes | what makes it informative |
|---|---|---|---|---|---|
| **C-M4** | EXP-0139 (`run01`, `run02`, `reval01`, `reval02`) | **M4 / G16G** | `NAT:k_imad@imad+0x020` — our own `k_imad` kernel left INTACT, one instruction overwritten; MSL is `o[i] = a[i]*b[i] + 7u` | `9f00560002080038d0260a00` | **8 lanes** with 8 distinct known `(a,b)` pairs, so the addend is recoverable **per lane**; **two separate process launches** (`run01`, `run02`), so a source whose content varies per launch is detectable |
| **C-G17P** | EXP-0154 (`run02`, `run04`), EXP-0160 (`run01`, `run02`, `confirm01..06`) | **A18 Pro / G17P** | `SYNTH+LIFTED:k_imad@imad[32:44]` — whole `_agc.main` synthesized, 16 GPRs seeded by us, `k_imad` block (MSL `a*b + 12345`) lifted verbatim | `9f00560002080060d02e0a00` | all 16 GPR values known; EXP-0160 runs **two independent seed sets** per case, so a GPR-sourced addend is detectable |

Seed tables (from each experiment's own committed harness, not from any name):

```
C-G17P set 1  SEED_I  = {0:10, 1:21, 2:34, 3:47, 4:58, 5:65, 6:71, 7:83,
                         8:94, 9:101, 10:113, 11:119, 12:125, 13:127, 14:3, 15:0}
C-G17P set 2  SEED_I2 = {0:7, 1:13, 2:19, 3:29, 4:37, 5:43, 6:53, 7:61,
                         8:73, 9:79, 10:89, 11:97, 12:103, 13:109, 14:5, 15:0}
C-M4 lanes    A_IN = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF,
                      0x00000001, 0x00000000, 0x80000000, 0x7FFFFFFF]
              B_IN = [3, 5, 8, 1, 31, 32, 2, 0]
```

**Confounder recorded up front: carrier and target are confounded.** C-M4 is *G16G + natural*;
C-G17P is *G17P + synth*. A difference between them cannot, by itself, be attributed to the
carrier rather than the target. Two comparisons inside a single target/carrier are therefore
load-bearing and are pre-registered as such: EXP-0139 `run01` vs `run02` (same target, same
carrier, different process launch) and EXP-0160 seed set 1 vs 2 (same target, same carrier,
different GPR contents).

## 3. The addend observable

For a case whose product `P` is known and held, the recovered addend is

```
A_obs = (observed_destination - P)  mod 2**32
```

* **C-G17P:** destination register `= bytes[3] >> 1` (db.json's `(reg<<1)|size`, and byte+3 is
  `0x00` in every population except the byte+3 sweep itself). `P = SEED[b5>>2] * SEED[b6>>3]`
  (EXP-0216's fitted multiplicand map, re-derived here rather than assumed — see §5 step 0).
* **C-M4:** destination is the store buffer; word *i* is lane *i*. `P_i = A_IN[i] * B_IN[i]`
  in every population except the byte+5 / byte+6 sweeps (where the multiplicand registers move
  and the natural carrier's register→lane map is unknown; those populations are reported but
  are **not** used to score addend models).

## 4. Competing models (frozen; every one of these is scored, including the failures)

### Group I — the addend is NOT an operand of this instruction

* **M-NONE-FIXED** — `A` is a constant of the carrier and depends on no instruction byte.
  Predicts: exactly one distinct `A` across every population where the product is held.
* **M-NONE-EXT(K)** — `A` is fetched from an **external scalar source** (uniform / constant
  file) *indexed* by `K = (b7 >> 3) & 0x1F`; the addend VALUE is nowhere in the encoding.
  Predicts, jointly: (i) `A = f_carrier(K)`, a function of K alone within a carrier;
  (ii) `A` independent of the GPR seed set; (iii) `A` identical across all 8 C-M4 lanes
  (scalar, not per-lane); (iv) `f` differs between carriers with different constant pools for
  at least one K; (v) `A` fits in 16 bits; (vi) at least one K may differ between process
  launches (a slot holding launch-varying data such as a buffer address).
* **M-NONE-EXT(other)** — same shape but indexed by some byte other than +7. Scored for every
  byte position with a dense sweep.

### Group II — the addend VALUE is encoded in the instruction

* **M-IMM-K** — `A = (b7 >> 3) & 0x1F` (5-bit literal). Refuted by one K where `A != K`.
* **M-IMM-K8** — `A = b7` (whole byte literal).
* **M-IMM-KSH** — `A = ((b7 >> 3) & 0x1F) << s` for `s in 1..8`.
* **M-IMM-K9** — **db.json's own historical claim** (EXP-M4-13 R6, still quoted in the
  descriptor): `A = (((b8 & 0xF) << 5) | ((b7 >> 3) & 0x1F))`, a 9-bit immediate spanning
  byte+7 bits 3..7 and byte+8 bits 0..3. Predicts `A` steps by 32 per unit of `b8`'s low nibble.
* **M-IMM-BN** for `N in {1,2,3,4,8,9,10,11}` — `A = bN`, or `A = bN << s`, or `A = bN + c`.
* **M-IMM-WIDE** — `A` = a 16-bit `b9 | b10<<8`, or a 24-bit `b9 | b10<<8 | b11<<16`.

### Group III — the addend is a REGISTER named by some byte

* **M-REG-bN(k)** for `N in {3,4,5,6,7,8,9,10,11}` and shift `k in {0,1,2,3,4}` —
  `A = SEED[(bN >> k) & 0xF]`. **The shift is not assumed; it is derived** (the two known
  multiplicand bytes already use two *different* shifts, `>>2` and `>>3`, so no project
  convention may be imported). Scored on C-G17P only, where the register file is seeded.
  The decisive prediction of every model in this group: **`A` must change between EXP-0160's
  two seed sets, in exactly the way the two seed tables predict.**
* **M-REG-LANE** — `A` is per-lane on C-M4 (i.e. sourced from a per-lane register rather than
  a scalar). Predicts the 8 recovered lane addends disagree.

### Group IV — joint / contextual

* **M-JOINT(b7,b8)** — `A = g(K, b8)` and does not separate. Tested against EXP-0160's
  `__2d_desc_mul` 12x8 grid **and** against the two dense byte+8 sweeps taken at two different
  byte+7 anchors (`0x38` on C-M4, `0x60` on C-G17P).
* **M-MODE** (control, already established) — `b7` bits 0..1 gate whether the product is added
  at all; `(b7 & 3) == 3` faults. Re-derived here as a positive control that the instrument
  can see byte+7 at all.

## 5. Method (frozen)

**Step 0 — re-derive, do not assume.** The product map `P = SEED[b5>>2] * SEED[b6>>3]` is
re-scored on C-G17P from the committed bytes before it is used as the subtrahend, with exact
counts. If it does not hold on the populations used for addend recovery, the addend recovery
is reported as unavailable for those populations rather than fitted around.

**Step 1 — co-variation census.** For every byte position 0..11, over its own dense
single-byte sweep with the product held, report `n scored`, `n excluded`, `distinct A values`,
and the `A` value at each byte value. A byte with **one** distinct `A` over its whole sweep
does not carry the addend *in that carrier* (safe wording per RE_EXPERIMENT_PROCESS_CORRECTIONS
§1: `inert in <exact tested envelope>; global role unknown`).

**Step 2 — function test.** For every byte with >1 distinct `A`: is `A` a function of that byte
alone within the carrier? Report `max cases per byte value` and `byte values with >1 distinct A`.

**Step 3 — selector vs literal.** For every byte surviving step 2, run all five discriminators:

| # | test | a LITERAL predicts | a SELECTOR predicts |
|---|---|---|---|
| a | same byte value, two carriers with different constant pools | same `A` | may differ |
| b | GPR seed set 1 vs 2 (EXP-0160, same target/carrier) | same `A` | *register* selector: differs |
| c | per-lane spread on C-M4 | identical across 8 lanes | *register* selector: differs |
| d | process launch `run01` vs `run02` (EXP-0139, same target/carrier) | same `A` | *external* selector: may differ |
| e | width: is `max(A) < 2**fieldwidth`? | yes | no constraint |

**Step 4 — score every model in §4** over every population, reporting
`hits / in_domain / scored / excluded` as **exact numerators and denominators** (§5 of
RE_EXPERIMENT_PROCESS_CORRECTIONS: never a percentage alone). Failing models are reported with
their counts, not omitted.

**Step 5 — adjudicate.** A model is **selected** only if it is exact (0 exceptions) over the
scored in-domain population of every population where it is evaluable, and it makes at least
one out-of-sample prediction no rival makes. If two models fit equally, the verdict is
**UNDECIDABLE** and the experiment states the discriminating experiment that would settle it.
"The addend is not encoded in this instruction" is a permitted, complete verdict.

### Exclusion rules (frozen, applied before any scoring)

A case is **excluded** (and counted) if any of:
`outcome` in {`fault`, `hang`, `timeout`, `undecodable`, null}; `victim` true or the error
string contains `InnocentVictim` (that is `measurement_failure`, never a hardware outcome);
the destination word still holds the poison `0xDEADBEEF`; the record is `__falsifier_*`,
`_poscontrol` or `_baseline`; or the mutation changed the instruction length (byte+1 bit 0,
the `lenbit`), which breaks framing rather than computing a different value.

`in_domain` means the model is evaluable at all (e.g. a register index inside the 16-entry
seed table). `hit` means the model's predicted 32-bit destination equals the observed one
exactly.

### What is NOT trusted

* the record's `field` key and its `instr` string — every byte is decoded from `bytes`;
* the record's `fstart`/`fwidth` — this experiment addresses **byte positions**, not named
  spans, so a stale `db.json` in a harness cannot move a single number here;
* `db.json`'s field names, notes and semantics string — they are the hypotheses under test;
* EXP-0160's and EXP-0216's conclusions — both are re-derived from the bytes.

The one thing that **is** trusted, and is the experiment's blind dimension: the `bytes` column
is what actually ran. If any harness wrote the *requested* rather than the *dispatched*
encoding there, every count in this experiment is circular. This is the same standing caveat
as EXP-0215 §7.6 and EXP-0216 §5.9.

## 6. Falsifiers

* **Group I is refuted** if any single byte's sweep yields an `A` that is a 1:1 function of the
  byte's own value across its full swept range **in both carriers**.
* **M-NONE-EXT(K) is refuted** if `A` depends on the seed set, or varies per lane, or exceeds
  16 bits, or is not a function of `K` alone within a carrier.
* **M-IMM-K is refuted** by a single K with `A != K`.
* **M-IMM-K9 is refuted** if the dense byte+8 sweep does not move `A` by 32 per low-nibble step.
* **Group III is refuted** for a byte if `A` is identical under both seed sets while the
  seed tables differ at the register the model names.
* **M-NONE-FIXED is refuted** by any second distinct `A` in a product-held population.

## 7. Stopping rule

The census is over the whole committed `imad` population — 13,937 records, 4,118 distinct
encodings, across both targets. There is no sampling and no early stop. Every population in
§5 step 1 is reported whether or not it moves the addend.

## 8. What this experiment may NOT do

* It may not edit `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/`, or
  `PROVENANCE.md`; any descriptor change is written as a **proposal** under
  `analysis/proposed_db_edits.json` and nothing else.
* It may not change or propose an evidence label.
* It may not write into any `raw/` path, or commit.
* It may not promote a C-M4 (G16G) observation to G17P or vice versa. Every count carries the
  target it was measured on.

# EXP-0180 — PRE-REGISTRATION (frozen before any build or device dispatch)

**Successor to EXP-0169** under `CODEX.md` §2 / `SUBAGENT_BRIEF.md` ("never repair a
quarantined or withdrawn arm in place; a successor takes a NEW number and a fresh
pre-registration"). EXP-0169 withdrew its `C2_load` carrier mid-experiment for
**DEF-0169-1** (`device_load` on G17P is asynchronous and its harness had no wait
anywhere) and **held** 16 rows rather than downgrading them. This experiment owns those
rows.

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
`Mac17,5`, macOS 26.6, Metal family Apple9). Every claim below is a **G17P** claim.
No result here is promoted to any other target.

**Repo revision at pre-registration:** `db7c3c957a8788b8589978a48c044b049dde2cc2`
(working tree dirty with sibling experiments; per `SUBAGENT_BRIEF.md` the gate is the
authored blob hashes recorded in `CAPTURE_CONTRACT.json`, **not** live `HEAD`).

---

## 1. The question, and the exact set of rows

**Can the 25 emitter-grade row-claims over the half-precision ALU family be substantiated by
a fresh, per-case, attributable capture on the documentation target — and if not, which of
them must be WITHDRAWN?**

These rows have already failed to substantiate twice: once because `EXP-M4-14` has **no
`raw/` tree at all** (EXP-0164), and once because EXP-0169's carrier had no detection power
for them. **A third inconclusive result is itself a reportable finding, and withdrawing a row
that cannot be reproduced is an accepted — indeed preferred — outcome.**

### 1a. The target set: 25 row-claims over 16 DISTINCT fields

Resolved mechanically by `analysis/target_rows.py` → `work/target_rows.json`.
**The 9 `EXP-M4-14` rows are a strict subset of the 16 rows EXP-0169 held**, so the union is
16 fields; nine of them carry two independent claims and receive two verdicts each.

| # | field | start | width | encodable | current label | current target | current evidence |
|---|---|---|---|---|---|---|---|
| 1 | `half_alu_ext8.b5` | 40 | 8 | 256 | `hardware-run` | A18 | EXP-M4-14 |
| 2 | `half_alu_ext8.b7_lo` | 56 | 1 | 2 | `untested` | G17P | EXP-0169 |
| 3 | `half_alu_ext8.b7_mid` | 58 | 5 | 32 | `untested` | G17P | EXP-0169 |
| 4 | `half_alu_ext8.dst` | 8 | 8 | 256 | `hardware-run` | M4 | EXP-0138 |
| 5 | `half_alu_ext8.op_valid_marker` | 63 | 1 | 2 | `hardware-run` | A18 | EXP-M4-14 |
| 6 | `half_alu_ext8.opflags` | 19 | 5 | 32 | `hardware-run` | M4 | EXP-0138 |
| 7 | `half_alu_ext8.opsel` | 16 | 3 | 8 | `isolated-byte-diff` | A18 | EXP-M4-14 |
| 8 | `half_alu_ext8.rsv6` | 48 | 8 | 256 | `hardware-run` | A18 | EXP-M4-14 |
| 9 | `half_alu_ext8.saturate` | 57 | 1 | 2 | `hardware-run` | A18 | EXP-M4-14 |
| 10 | `half_alu_ext8.srcA` | 24 | 8 | 256 | `hardware-run` | A18 | EXP-M4-14 |
| 11 | `half_alu_ext8.srcB_desc` | 32 | 8 | 256 | `isolated-byte-diff` | A18 | EXP-M4-14 |
| 12 | `half_alu_fma12.dst` | 8 | 8 | 256 | `hardware-run` | M4 | EXP-0138 |
| 13 | `half_alu_fma12.ext` | 32 | 64 | 2^64 | `untested` | G17P | EXP-0169 |
| 14 | `half_alu_fma12.opflags` | 19 | 5 | 32 | `hardware-run` | M4 | EXP-0138 |
| 15 | `half_alu_fma12.opsel` | 16 | 3 | 8 | `isolated-byte-diff` | A18 | EXP-M4-14 |
| 16 | `half_alu_fma12.srcA` | 24 | 8 | 256 | `hardware-run` | A18 | EXP-M4-14 |

Rows 1, 5, 7, 8, 9, 10, 11, 15, 16 are the nine `EXP-M4-14` claims and get a **second,
separately reported verdict** against the text of that citation (§6).

**Span re-check before dispatch (dispatch requirement):** every one of the 16 spans is
byte-identical between this experiment's pinned `db.json`
(`a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22`) and the spans EXP-0169
measured. **0 moved, 0 absent.** `analysis/merge_check.py` re-asserts this at merge time and
**refuses any row whose `start`/`width` has moved**.

### 1b. Explicitly OUT of scope, named rather than half-done

* `half_alu.*` (6 fields) — already `hardware-run` on G17P from EXP-0169 with a ladder that
  passed. Swept here **only** as the ladder/instrument control; **no verdict is emitted**
  except where this experiment's model probes contradict it, which is reported as a defect,
  not as a relabel.
* Every other `EXP-M4-14`-citing row outside this family (**37 of the 46**).
* `bf_alu`, `cvt_f2h*`, `hminmax`, `pack_convert` — the neighbouring byte0 groups. They are
  named in §3 as corroboration for DEF-0180-B and are **not** measured here.

---

## 2. Why the previous attempt could not have succeeded (established OFFLINE, before this build)

Full derivation with numbers: `PROGRESS.md` M3/M4. Compressed:

* **DEF-0180-A (carrier).** The `half_alu_ext8` / `half_alu_fma12` anchors EXP-0169 lifted
  name half-registers `0x81`/`0x83` = **registers 64/65**, which the synthesized carrier
  never seeds, and the carrier's `falu2i` float seeds have **zero low 16 bits**, so every
  even half-register descriptor reads `0.0`. The anchors' results were `0`, written where
  `0` already was. Only 28 of 256 `dst` values and 28 of 256 `b5` values could move, and
  those 28 are exactly `{2k+1} ∪ {128+2k+1}` for `k = 0..13` — the odd (high-half)
  descriptors of the **seeded** registers. `rsv6` 0/256, `b7_lo` 0/2 and
  `op_valid_marker` 0/2 moved because there was nothing to disturb.
* **DEF-0180-B (db model).** The destination GPR of this family is **byte0's high nibble**
  (result written to that register's LOW 16 bits), directly visible in EXP-0169's own
  falsifier case; `db.json` pins all 8 bits of byte0 in `match` and models bits 8..15 as
  `dst`, when bits 8..15 are a **source** half-register descriptor.
* **DEF-0180-C/D (length model).** `db.json`'s stated length rule for byte0 `0x10`
  (`6, or 8 if byte+2 & 0x02`) contradicts `isadb.instr_length`'s implemented rule
  (`6 + 2*(byte+4 & 3)`, with an `8`-when-zero override if `byte+2 & 2`). **Neither has been
  measured on hardware.** The implemented rule predicts EXP-0169's `half_alu.srcB` sweep
  exactly, including the all-`0xDEADBEEF` cases at `srcB ≡ 2 (mod 4)`.
* **The pre-registered falsifier was not a falsifier.** `byte0 → 0x00` changes only the
  destination register of this family. It cannot null the op.

**None of this is a hardware claim yet.** §3's hypotheses put every part of it on the device.

---

## 3. Hypotheses, each with its refuter

Independent variable in every arm: **exactly one `db.json` field of the instruction under
test**, except where a crossing is named. Controlled: carrier program, seed table, dispatch
shape (`grid=1`, `tg=1`), poison, both sentinels, and the anchor's other bytes.

### H0 — the destination is byte0's high nibble (`db_defect`)
For `byte0 = (n << 4) | 0x0`, `n = 0..15`, the half-ALU result is written to the **low 16
bits of GPR `n`**, leaving GPR `n`'s high 16 bits unchanged.
*Expected:* a 16-value sweep in which case `n` changes exactly one register, `r[n]`, and its
low half only.
**Refuter:** the result lands in `r1` (or anywhere fixed) for every `n`; or the whole
register is overwritten. Either refutes H0 and `db.json`'s `match` on byte0 stands.

### H1 — the carrier repair restores detection power
A carrier whose GPRs carry **distinct non-zero fp16 values in BOTH halves**, with the
instruction re-based onto seeded operands and `opflags = 0`, makes every pre-registered
ladder step move, on the same device, in the same run, where EXP-0169's arm did not.
*Expected:* `E8_FMA@C_HI` and `F12_FMA@C_HI` ladders pass while the paired `E8_LIFT` /
`F12_LIFT` control arms (EXP-0169's exact anchors, unchanged) reproduce EXP-0169's failure.
**Refuter:** the repaired arm's ladder still fails → the cause is not the carrier, the 16
rows stay unsubstantiated, and this experiment says so.

### H2 — `half_alu_fma12` is an over-consumer; `ext` is not a field
`db.json` gives `half_alu_fma12` length 12 with a 64-bit `ext` covering bytes +4..+11, while
`length_rule.byte0_table` admits no 12-byte form for byte0 `0x10`.
*Decisive test (`LEN` arm):* place a chain of four 2-byte `mov_imm` markers
(`r8←101, r9←102, r10←103, r11←104`; all HW-VALIDATED encodings) starting at the
instruction's byte **+6**. The number of markers that execute reads the **hardware's**
instruction length directly: 4 → 6 bytes, 3 → 8, 2 → 10, 1 → 12, 0 → 14.
*Expected:* the length is a function of `byte+4 & 3` (and, where that is 0, of `byte+2 & 2`),
and the 12-byte form occurs only at `byte+4 & 3 == 3`.
**Refuter:** all four markers are consumed at every `byte+4` value (length ≥ 14), or the
marker count is independent of `byte+4` → the implemented rule is wrong and `db.json`'s
stated rule may stand.

### H3 — `srcB_desc`'s low 2 bits and `opsel`'s bit 1 are LENGTH selectors, so their
### encodable ranges are smaller than `db.json` says
*Expected:* over `srcB_desc = 0..255`, only the 64 values with `v & 3 == 1` keep the 8-byte
`half_alu_ext8` framing; the rest encode a 6/10/12-byte instruction and re-frame the stream.
Same for `half_alu_fma12`'s byte+4 (`v & 3 == 3` keeps 12).
**Refuter:** the measured length is constant across `srcB_desc` → the low bits are ordinary
operand bits and the full 256 is encodable.

### H4 — per-field substantiation (the 16 rows)
Each field is `LIVE`, `INERT-MULTI`, or unsubstantiated, by the §7 rules.
**Refuter for a `LIVE` claim:** < 99 % per-value cross-run agreement, or movement < 2 ×
disagreements, or no ladder-passing carrier, or the movement is explained by a change of
instruction identity/length (`tok_instr` or the measured length differs between the two
values) — the `falu2_uni.uni_mode` self-catch, generalised.

### H5 — the nine `EXP-M4-14` claims, re-tested at value level
Each is restated as a prediction and tested with a **host-computed** oracle:

| row | the committed claim, verbatim | prediction under test |
|---|---|---|
| `ext8.op_valid_marker` | "every byte+7 value WITHOUT bit7 set nulls the op (result 0)" | for all 128 byte+7 values with bit 7 clear, the destination low half is **unchanged from the pre-dump**; for all 128 with bit 7 set, it is written |
| `ext8.saturate` | "byte+7 0x82 clamps saturate(9) to 1; 0x80 passes 9 unclamped; 0xc0 also passes" | on `C_HI` (result magnitude > 1.0) `saturate=1` gives exactly `1.0`; `saturate=0` gives the unclamped sum. On `C_LO` (< 1.0) both give the same value |
| `ext8.rsv6` | "0x00..0xc0 swept, every value kept the result — fully INERT/reserved" | all 256 values inert on **two** ladder-passing carriers |
| `ext8.b5` | "bits3/4 null in this instance; largely inert" | tested on **both** instances; in the fma instance `b5` is expected LIVE, which would make the committed range instance-specific and not a property of the field |
| `ext8.srcB_desc` | "0x01 required in the add+saturate instance; carries the fma srcA-negate (byte+7 0xc0 → 0xc8)" | note the claim's own byte+7 example is **not** `srcB_desc`; tested as written and reported as a citation defect if it is |
| `ext8.srcA` | "byte+3 0x02 works, 0x04/0x06 break; byte+6 swept 0x00..0xc0 all inert" | byte+3 **is** `srcA`; byte+6 is `rsv6` — one row's `range` documents two different fields |
| `ext8.opsel` / `fma12.opsel` | "gains 6 = hfma (byte+2 = 0x1e)" | `opsel` 6 selects fma; the other 7 values are characterised, including their effect on length |
| `fma12.srcA` | "byte+4 0x83 → fma(\|a\|,b,c); 0x82 → \|a\| alone; 0x80 → 0" | **`fma12.srcA` is bits 24..31 = byte+3, not byte+4.** The claim documents a byte that lies inside `ext`. Reported as a citation defect and both bytes are swept |

**Refuter for each:** the observation contradicts the claim on ≥ 1 value with ≥ 99 %
cross-run agreement → the row **DOES-NOT-REPRODUCE** and is recommended for withdrawal.

---

## 4. Carriers, arms, and why each pair is genuinely two carriers

> Two carriers identical in the dimension a field controls are **one** carrier
> (`FIELD-SWEEP-PROTOCOL` §3, rule 5).

### 4a. The two carriers

| id | shader | seed table | anchor operands | result magnitude | why it is a different carrier |
|---|---|---|---|---|---|
| `C_HI` | `kernels/carrier_dag.metal` (buffers: out/float/int) | `SEED_A` | two **large** fp16 halves | **> 1.0** | the only carrier on which `saturate` can be observed at all |
| `C_LO` | `kernels/carrier_uni.metal` (different buffer signature; also preloads the UNIFORM register file) | `SEED_B` — a different permutation, so a given half-register descriptor selects a **different** value | two **small** fp16 halves | **< 1.0** | `saturate` must be a no-op here; every operand descriptor resolves to a different number; different buffer signature (the dimension EXP-0087 documented for read-back) |

Both carriers are seeded **without `device_load`** — DEF-0169-1 cannot recur.

### 4b. The seed construction, and how "the seeds landed" is proved PER CASE

1. `mov_imm(r14, 0)`, then `falu2i` writes an exact minifloat fixed point into each of
   `r0..r13` (the EXP-0169 construction, which its own raw shows lands every time). This
   fills the **high** 16 bits of every GPR with a distinct non-zero fp16 pattern.
2. For each `j` in `0..13`, one half-ALU add
   `[(j<<4)|0x00, hB_j, 0x1c, hA_j, 0x00, 0xc0]` writes `hi[A_j] + hi[B_j]` into
   **`r_j`'s low 16 bits**, leaving the high half intact. `(A_j, B_j)` are chosen so the 14
   low halves are distinct, non-zero, normal, finite fp16 values, none equal to any high
   half. *(This uses the byte0-high-nibble destination that H0 tests; if H0 is refuted the
   pilot's seed-adequacy predicate fails and construction **S2** below is used instead.)*
3. **Frozen fallback S2**, used iff the pilot's seed-adequacy predicate fails: `cvt_f2h_dst`
   (`db.json`: "fp32 → fp16 narrowing convert, for ANY dst register (byte0 high nibble)")
   writes `half(r_k)` into the destination's low half, same shape, different opcode group.
4. **Frozen fallback S3**, used iff S1 and S2 both fail: the experiment proceeds with
   high-halves-only seeding and reports every descriptor sweep as covering
   **`{odd descriptors}` only**, with the even half explicitly labelled
   `reads 0.0 — movement observed but weakly identifying`. It does **not** claim
   `hardware-run` at full range in that case.

**Seed adequacy predicate (frozen):** all 28 half-lanes of `r0..r13` are non-zero, pairwise
distinct, finite, and not fp16-subnormal, as read back from the **pre-dump** on hardware.

**Per-case proof (this is the structural kill of DEF-0169-1).** Every case dumps all 16 GPRs
**before** the block under test (`pre[]`, words 0..63) and **again after** it (`post[]`,
words 80..143). A case with `pre[] != SEED_EXPECTED` is `outcome: invalid_run`, is retried up
to 3 times, and **can never be counted as movement**. There is no periodically refreshed
baseline anywhere in this experiment.

### 4c. Arms

| arm | instruction | base instance | carriers | cases/carrier |
|---|---|---|---|---|
| `E8_ADD` | `half_alu_ext8` | add+saturate shape (`byte+2 = 0x1c`, `byte+4 & 3 = 1`), operands re-based onto seeded halves, `opflags = 0` | `C_HI`, `C_LO` | 1358 |
| `E8_FMA` | `half_alu_ext8` | fma shape (`byte+2 = 0x1e`, `byte+4 = 0x81`), re-based, `opflags = 0` | `C_HI`, `C_LO` | 1358 |
| `F12_FMA` | `half_alu_fma12` | fma-abs shape (`byte+2 = 0x1e`, `byte+4 = 0x83`), re-based, `opflags = 0` | `C_HI`, `C_LO` | 2600 |
| `E8_LIFT` | `half_alu_ext8` | **EXP-0169's exact anchor, byte-for-byte, base unchanged** | `C_HI` | 1358 |
| `F12_LIFT` | `half_alu_fma12` | **EXP-0169's exact anchor, byte-for-byte, base unchanged** | `C_HI` | 2600 |
| `LEN` | length probe (H2/H3) | marker chain from byte +6 | `C_HI` | 2048 |
| `DSTNIB` | H0 probe | `byte0 = n<<4`, `n = 0..15`, on both instruction shapes | `C_HI`, `C_LO` | 32 |

`E8_LIFT` / `F12_LIFT` are **controls, not evidence for the rows**: they exist so that any
difference between this experiment and EXP-0169 is attributable to the repair and measured on
the same device in the same run.

`E8_ADD` vs `E8_FMA` is an **instance** axis, not a carrier axis: `EXP-M4-14`'s `b5` and
`srcB_desc` claims are explicitly instance-specific ("in the add+saturate instance"), so a
single instance cannot test them.

**Total ≈ 16,700 cases per gated run** (EXP-0169 dispatched 16,827 in 190 s).

---

## 5. Coverage rule (frozen)

* width ≤ 8 → **all `2^w` values, densely**.
* `half_alu_fma12.ext` (width 64, encodable range `2^64`) → each of its 8 constituent bytes
  swept `0..255` (2048 values, `coverage_pct ≈ 0.0`). **It is pre-registered here that this
  row CANNOT reach `hardware-run` under `docs/evidence-classification.md` §2's range bar**,
  whatever the outcome; the honest verdict space for it is `db_defect` + `untested`.
* `distinct_bytes` is counted over **distinct encodings actually dispatched**, never over
  dispatched values. A row where `distinct_bytes < values_dispatched` is flagged
  `under_covered` and cannot be promoted.
* Every emitted row carries `values_dispatched`, `distinct_bytes`, `encodable_range`,
  `start`, `width`, `coverage_pct`, `thin`, `under_covered` — **0 rows may be missing a
  coverage key** (EXP-0169 reached 113/113; that is the bar).

---

## 6. Oracles

**Tier 1 — host-computed, GPU-independent.** For `opsel`, `saturate`, `op_valid_marker`,
`dst`(byte+1 as a source), `srcA`, `b5` and the `DSTNIB` probe, the expected post-state is
computed on the host as *the case's own observed `pre[]` with the predicted write applied*,
using Python `struct` `'e'` (IEEE binary16) arithmetic. `oracle.out` is the predicted 32-bit
word of the destination register; `match_sem` is exact equality.

**Tier 1L — the length oracle (`LEN` arm).** Expected marker count from the candidate rule
under test; the observed count is read from `r8..r11`. Five distinguishable outcomes, no
interpretation needed.

**Tier 2 — anchor difference.** For fields with no published semantics (`rsv6`, `b7_lo`,
`b7_mid`, `opflags`, `ext`), the oracle is difference from **the arm's own anchor
observation**, captured **once per (arm, carrier) per run** and never refreshed.
`RESULTS.md` states, per row, which tier it was ruled on.

**Falsifiers pre-registered to FAIL (per arm, per carrier):**
`F1` `opsel → 4` (hadd) must change the result on an fma anchor;
`F2` `srcA → h(r14)` (a zero half) must change the result;
`F3` byte0 `→ (7<<4)` must move the write to `r7` (H0);
`F4` the marker chain with **no** instruction in front of it must set all four markers.
`F4` is the instrument's own zero point: if it fails, the `LEN` arm is void.

---

## 7. Verdict rules (frozen; nothing is decided after the fact)

Two gated runs, `run01` **forward** and `run02` **reverse**, identical case matrix
(`matrix_sha256` asserted equal in both `00_env.json`).

* **`gate_stable`** — ≥ **99.0 %** per-value cross-run agreement on the observation digest.
* **`gate_live`** — `moved ≥ 2 ×` the disagreement count, and `moved > 0`.
* **`gate_ladder`** — the (arm, carrier)'s liveness ladder passed. A carrier that fails its
  ladder supports **neither** a live nor an inert reading; its rows are `untested` /
  `NO-DETECTION-POWER`, never "the field is inert".
* **`gate_identity`** — a value counts as movement only if it did **not** change the
  instruction's identity: `tok_instr` equal to the anchor's **and** the hardware-measured
  length (from the `LEN` map) equal to the anchor's. Values failing this are recorded,
  reported, and **excluded from `encodable_range`**, which is then restated as the measured
  range. *(This is EXP-0169 §16b's `falu2_uni.uni_mode` self-catch, made a standing rule.)*

Label mapping:

| verdict class | condition | label |
|---|---|---|
| `LIVE-FULL` | ladder passed on ≥ 2 carriers, stable, live, full measured encodable range | `hardware-run` |
| `LIVE-PARTIAL` | as above but coverage below the measured encodable range, or only 1 ladder-passing carrier | `isolated-byte-diff` |
| `INERT-MULTI` | ladder passed on ≥ 2 carriers, stable, **0 moved** over the full range | `hardware-run` with an explicit `inert` semantics note |
| `INERT-SINGLE` | as above on 1 carrier | `untested` |
| `UNSTABLE` | `gate_stable` failed | `untested` |
| `NO-DETECTION-POWER` | `gate_ladder` failed everywhere | `untested` |
| `NOT-A-FIELD` | `gate_identity` fails structurally (the span is a length/identity selector) | `untested` + a `db_defects` entry |

**Withdrawal rule (the outcome this experiment is most willing to reach).** A row whose
committed claim is contradicted at ≥ 1 value under `gate_stable`, **or** whose committed
citation has no reproducible support and which this run cannot substantiate either, is
reported `WITHDRAW` with the numbers behind it. No row is stretched to save it.

---

## 8. Confounders named in advance

1. **Instruction-identity change masquerading as movement** — the whole point of
   `gate_identity`. `srcB_desc`, `opsel` and `ext` byte+4 are all suspected length/identity
   selectors.
2. **Release-on-read.** `opflags` bits release source registers; a register going to zero is
   an *oracle*, not a fault. Base anchors use `opflags = 0` so arithmetic is the signal; the
   `opflags` sweep then exposes the release bits by which register zeroes.
3. **Sentinel capture.** The POST sentinel register is written **after** the block, so the
   instruction under test cannot retroactively clobber it; the PRE sentinel is in memory
   before the block. `r15` (the store index) is re-seeded before **every** store.
4. **Co-varying observable** (rule 3a). The read-back is 32 fixed `device_store`s with
   constant `data_reg`; nothing in the dump path is derived from the field under test.
5. **Contamination.** Poison `0xDEADBEEF` everywhere; the OS fault-classification string is
   recorded verbatim on every non-`ok` case; `InnocentVictim`-class cases are segregated and
   re-run; `harness/procsample.py` samples concurrent GPU activity into
   `raw/<run>/03_procsample.jsonl` so "the machine was quiet" is a measurement.
   **Contamination can destroy an observation but never fabricate a coherent one**
   (EXP-0160) — and, because this experiment has no refreshed baseline and verifies seeds per
   case, it cannot fabricate movement either (DEF-0169-1).
6. **Stale shared `db.json` on the neo.** `isadb` is resolved **explicitly** to
   `work/frozen/`; there is no path fall-through. The resolved path and both sha256s are
   asserted at run start and written into `raw/<run>/00_env.json`.
7. **`rt_ok` is recorded and never cited.** A round trip is not an emitter gate (EXP-0170).

---

## 9. Safety

* **No abort path.** Every value in every sweep dispatches regardless of outcome, exactly as
  EXP-0169 Part II did — that is how its two exact fault walls were mapped. There is no
  per-field hang budget, so a contiguous hazard cannot be hidden by a stop rule
  (`FIELD-SWEEP-PROTOCOL` §3(c)).
* Hard timeout **8 s** per request; the persistent runner's watchdog; `PersistRunner` restart
  after a hang.
* Every case is appended to `raw/<run>/sweep.jsonl` and `fflush`+`fsync`ed immediately;
  `PROGRESS.md` gets an entry per milestone. A kill costs at most one milestone.
* **Courtesy warning (`FIELD-SWEEP-PROTOCOL` §7):** this sweep deliberately mutates
  **length- and identity-selecting bits** of a 6/8/10/12-byte polymorphic family, so it will
  desync the instruction stream on a large fraction of cases. EXP-0169 saw **0 hangs** on
  this family and 254/256 silently-dropped stores on the `device_store` walls; faults are
  expected, hangs are not. This will be announced in `PROGRESS.md` before dispatch.
* `macvdmtool` is **forbidden**. If the neo stops answering: STOP, report **BLOCKED**, do not
  scan, do not recover.

---

## 10. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us in this project; carrier bodies reuse
  the shape, not the results, of our own EXP-0169/EXP-0154/EXP-0138 carriers), and the AGX
  machine code the PUBLIC runtime API (`newLibraryWithSource:`, via tools/shdump) compiled
  from that source; the committed raw/ trees of EXP-0169 and the committed
  tools/agx-isa/{db.json,isadb.py,validation.json}, all READ-ONLY.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. The only machine code inspected or spliced is
  the compiled form of our own MSL.
Reproduction: README.md
Evidence: raw/ (append-only), analysis/field_verdicts.json, work/target_rows.json
```

---

## 11. AMENDMENT 01 — two rules adopted from EXP-0179, before any dispatch

Adopted 2026-08-30 on the coordinator's message, **before the first device dispatch**. Both
change the design, so they are recorded here and mirrored in `CAPTURE_CONTRACT.json`.

### 11a. A frozen carrier can be DEAD, and only the hardware says so

EXP-0179 froze a carrier in which **1,395 cases wrote the PRE sentinel and then nothing** —
all 16 registers, the POST sentinel and the breadcrumb still `0xDEADBEEF`, `status OK`, tail
intact — because an unconditional `if_push` with `scope_kind == 0x01` masked off the only
lane of a one-thread dispatch. It retained that run, **burned the run id**, fixed the carrier
and re-ran under new ids.

Adopted here:

* **New outcome class `carrier_dead`**, distinct from `silent_zero` and from `fault`:
  `status == OK` **and** `pre_sent` landed **and** every one of the 16 `post[]` words plus
  `post_sent` is still `0xDEADBEEF`. Against a zero-initialised buffer this is invisible;
  against the poison it is unambiguous. `carrier_dead` **never** counts as movement and
  **never** counts as inertness.
* **Pilot gate, frozen:** if any (arm, carrier) shows `carrier_dead` on **> 0.5 %** of pilot
  cases, or on its anchor case at all, that carrier is **rejected before the gated pair** and
  the rejection is reported. It is not "worked around".
* **Run-id burn rule, restated:** a run found defective is retained **in full and unedited**,
  its id is **burned**, and the replacement takes a **new** id. Never topped up, never
  reused, never deleted.
* This is why the ladder runs **first** in every arm and why `F4` (the marker chain with no
  instruction in front of it) is a pre-registered falsifier: it is the instrument's zero
  point.

### 11b. Inertness measured on a carrier that cannot express the field is NOT evidence of inertness

EXP-0179 declined `ret.scoreboard` — inert over 0..255, agreement 1.0, zero disagreements,
mechanically promotable — because the dimension it controls is **ordering**, and neither
carrier differed there. It stayed `corpus-correlation`. That is the same shape as these 25
rows, and it is the reason they were **held** rather than downgraded.

**Frozen consequence: an `INERT-MULTI` verdict may map to `hardware-run` ONLY for a field
whose controlled dimension appears in the "carriers differ?" column below as `YES`.** For
every `NO` row, an inert reading maps to `corpus-correlation` at best, and the row is
reported as *not answerable by this experiment* — never as "the field is inert".

| field | dimension it controls | do the carriers/arms differ in it? | what an INERT reading may mean |
|---|---|---|---|
| `ext8.dst` (byte+1 — a SOURCE, per DEF-0180-B) | which half-register supplies an operand | **YES** — `SEED_A` vs `SEED_B` give different values at the same descriptor | `INERT-MULTI` → `hardware-run` (inert) |
| `ext8.srcA`, `fma12.srcA` | operand selection | **YES** — same | `hardware-run` (inert) |
| `ext8.b5` | third operand / modifier, instance-specific | **YES** — two instances (`E8_ADD` / `E8_FMA`) × two seed tables | `hardware-run` (inert) |
| `ext8.srcB_desc`, `fma12.ext` byte+4 | **instruction LENGTH / framing** (DEF-0180-D) | **YES, but only after 11c** — `C_HI` has the dump immediately after the block, `C_LO` has 8 bytes of slack, and the `LEN` arm measures length directly | `NOT-A-FIELD` where identity changes; otherwise `hardware-run` |
| `ext8.opsel`, `fma12.opsel` | operation select (+ conditional length) | **YES** — operand magnitudes differ, so hadd/hmul/hfma are distinguishable in both, and framing differs | `hardware-run` |
| `ext8.opflags`, `fma12.opflags` | source **release** and result **publication / last-use ordering** | **PARTIAL** — release is visible in both (a released register reads 0 in `post[]`); *publication/ordering* is expressible only after 11c adds a second consumer to `C_LO` | release bits: `hardware-run`. Any bit inert on both carriers: **`corpus-correlation`, explicitly "the carriers cannot ask this"** |
| `ext8.saturate` | output clamp | **YES** — `C_HI` result > 1.0, `C_LO` result < 1.0. This is the designed difference | `hardware-run` |
| `ext8.op_valid_marker` | whether the op writes at all | **YES** — visible on both, at both result magnitudes | `hardware-run` |
| `ext8.rsv6`, `ext8.b7_lo`, `ext8.b7_mid` | **UNKNOWN — no dimension can be named** | **NO** | **`corpus-correlation` / `untested` ONLY.** An inert reading here is pre-registered as *not promotable*, whatever the agreement statistics say |
| `fma12.ext` (64 bits) | everything in bytes +4..+11 at once | n/a — the span is not a field | `NOT-A-FIELD` + `db_defects`; pre-registered as unable to reach `hardware-run` |

`ext8.rsv6` is the sharpest case: `EXP-M4-14` labels it `hardware-run` on exactly the
evidence this rule forbids — "0x00..0xc0 swept, every value kept the result — fully
INERT/reserved". **Reproducing that inertness is therefore NOT sufficient to keep the row.**
If this experiment measures it inert and no carrier can express what it controls, the honest
outcome is **WITHDRAW to `corpus-correlation`**, and that is pre-registered here as the
expected result rather than discovered afterwards.

### 11c. Two carrier differences added to make the above true rather than aspirational

1. **Tail slack.** `C_HI` places the 16-register post-dump **immediately** after the block, so
   an over-consuming length swallows dump code and desyncs. `C_LO` places **8 bytes of
   two-byte `mov_imm` markers** between the block and the post-dump, so an over-consuming
   length eats markers instead and the program survives with a *readable* signature. The two
   carriers therefore differ in exactly the framing dimension `srcB_desc` and `ext` byte+4
   control, and `C_LO` turns a catastrophic desync into a measurement.
2. **Second consumer.** `C_LO` emits, after the block and before the post-dump, one further
   half-ALU op that reads **the same source half-registers** into a scratch GPR. A
   release / last-use / publication flag in `opflags` that has no effect on the block's own
   result can still change that second read. `C_HI` has no second consumer. This is the
   ordering dimension `ret.scoreboard` lacked.

Neither addition touches the field under test; both are recorded in `00_arm_resolution.json`
and are constant across every case of a carrier, so neither can co-vary with a swept field.

---

## 12. AMENDMENT 02 — the shared runner can manufacture hangs, and geometry is a carrier variable

Adopted 2026-08-30 on the coordinator's second EXP-0179/EXP-0178 relay, **still before any
device dispatch**. Both items change the design and are mirrored in `CAPTURE_CONTRACT.json`.

### 12a. A false `hang` and a real inertness look identical in a summary

`tools/agxtest/persistrun.py` starts a **fresh reader thread per line** and abandons it on
timeout; the abandoned thread re-resolves `self.proc` at execution time, so after the first
watchdog timeout it wakes on the **replacement** child's stdout and races the foreground
reader. Responses come back truncated (`OUT 0 ` with no hex), the shared parser raises
`ValueError: not enough values to unpack`, and the run dies. In EXP-0178's `work/pilot02`
**one genuine hang poisoned every later request including the unspliced health check, and
three consecutive cases were recorded `hang` with `restarts=99` — all false.**

This is squarely on this experiment's critical path: §9 pre-registers **no abort path and no
hang budget**, and the `LEN`/`E8_*`/`F12_*` arms deliberately mutate length- and
identity-selecting bits, so desyncs — and therefore watchdog timeouts — are *expected by
design*. If one genuine hang manufactured a cascade of false ones, this experiment could
**withdraw rows for a harness artefact** — the exact inverse of the defect that put them in
this state.

Adopted, frozen:

* **`harness/saferunner.py`** — `SafePersistRunner`, adopted from EXP-0178's own
  `harness/saferunner.py` (our code, this project, cited in the file header): **exactly one
  reader thread per child**, bound to that child's lifetime, feeding a queue tagged with the
  owning process object; lines from a killed child are **discarded**, never handed to the
  wrong request.
* **The shared tools are NOT modified.** `tools/agxtest/persistrun.py` stays exactly as it
  is — EXP-0179 is running against it and mutating it mid-run would break that experiment's
  reproducibility (`FIELD-SWEEP-PROTOCOL` §7 courtesy).
* **New outcome class `measurement_failed`.** A response with `status == "MALFORMED"` — a
  truncated or unparseable `OUT` line — is a **failure to measure, not a measurement**. It is
  never `hang`, never `fault`, never `ok`, never movement, never inertness. The offending raw
  lines are kept verbatim in the case record (`resp["raw"]`), the case is retried up to 3
  times, and any case still `measurement_failed` after 3 attempts is reported as such and
  **excluded from `values_dispatched`**, so it cannot inflate a coverage figure either.
* **Post-hang quarantine.** After any `hang`, the runner is restarted and the **next** case
  is preceded by an unspliced health check; if the health check does not return `ok`, every
  case since the hang is re-run. `RESULTS.md` reports the count of hangs, health-check
  failures, and re-run cases.

### 12b. Dispatch geometry is a carrier variable, and it is checked rather than argued

EXP-0178 root-caused EXP-0169's `get_sr` ladder failure: `k_sr` was lifted and run at
**grid=1 / tg=1**, where every reachable system value reads `0`, so the ladder could not
move. `casematrix.py:78` states that relaxation in EXP-0169's own source. That is the same
class as these 25 rows — **a carrier that cannot express what is asked of it produces a null
result indistinguishable from inertness.**

None of this experiment's 16 fields is a system-value read, and the half-ALU operates on
lanes *within* a register rather than across threads, so `grid=1 / tg=1` is expected to be
adequate. **That expectation is measured, not asserted:**

* Every (arm, carrier) runs its **anchor + full liveness ladder + the four falsifiers** at
  **both** `grid=1, tg=1` and `grid=32, tg=32` (one full SIMD group) in the pilot, and the
  two geometries' results are recorded side by side in `raw/pilot01/geometry.jsonl`.
* **Frozen decision rule:** if any ladder step's pass/fail or any falsifier's outcome differs
  between the two geometries, the arm is re-based to the geometry in which the ladder passes,
  the difference is reported as a first-class result, and `00_arm_resolution.json` records
  the geometry each arm actually ran at. If they agree, the gated pair runs at
  `grid=1, tg=1` and `RESULTS.md` says the check was run and agreed.
* At `tg=32` every thread executes identical code with identical seeds and writes the same
  output words, so a *difference* between the geometries is itself evidence of lane- or
  geometry-dependent behaviour in this family — a reportable hardware fact, not noise.

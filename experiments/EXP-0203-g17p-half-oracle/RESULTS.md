# EXP-0203 — RESULTS

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9, `192.168.170.254`). Every observation below was taken on
**G17P**. Nothing is carried over from M4/G16G except one *offline* model fit from our own
committed `EXP-0180` raw, which was itself a G17P capture.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/), bytes this experiment assembled through
                  tools/agx-isa, and our own committed raw from EXP-0180
Apple binary introspection: NONE
Reproduction: README.md -> Reproduction
Evidence: raw/pilot01, raw/g17p_run21..23, raw/g17p_run31..32 (append-only)
```

---

## 1. Verdicts

Legacy label plus the six independent axes required by
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §2. Exact numerators and denominators throughout;
no bare percentages.

| field | span | legacy | geometry | liveness | semantics | recipe | target | reproducibility |
|---|---|---|---|---|---|---|---|---|
| `half_alu_fma12.dst` | 4..7 (w4) | **`hardware-run`** | geometry-mapped | live | **semantically-mapped** | generated-point | G17P-direct | independently-confirmed |
| `half_pack.dstlo` | 8..15 (w8) | **`hardware-run`** | geometry-mapped | live | **semantically-mapped** | generated-point | G17P-direct | independently-confirmed |
| `half_pack.b3` | 24..31 (w8) | **`hardware-run`** | geometry-mapped | live | **semantically-mapped** | generated-point | G17P-direct | independently-confirmed |
| `half_alu_fma12.ext` | 32..95 (w64) | `untested` *(forced)* | ledger-verified | live, per byte | bounded-map | not-generated | G17P-direct | auditable |

### Counts, per field (primary pair `g17p_run31` forward / `g17p_run32` reverse)

| | `dst` | `dstlo` | `b3` | `ext` |
|---|---|---|---|---|
| encodable range | 16 | 256 | 256 | 2^64 |
| arms | 4 | 4 | 4 | 3 |
| dispatched per run | 64 | 1024 | 1024 | 6144 |
| distinct requested values | 16 | 256 | 256 | 256 per byte x 8 bytes |
| **distinct ACTUAL encodings** | 16 per arm | 256 per arm | 256 per arm | **2041** per arm (see below) |
| ledger `requested == decoded` | 64/64 | 1024/1024 | 1024/1024 | 6144/6144 |
| decidable per arm | 11/16 | 256/256 | 256/256 | 1920/2048 |
| **values covered (union of arms)** | **16/16** | **256/256** | **256/256** | 1920 of 2^64 |
| moved (vs the arm anchor) | 40 | 1016 | 1016 | 3650 |
| cross-run disagreements | 0 | 0 | 0 | 1 in 5760 |
| **oracle match, decidable values** | 44/44 and 44/44 | 1024/1024 and 1024/1024 | 1024/1024 and 1024/1024 | see §5 |
| distinct oracle predictions | 11 per arm | 29 per arm | 29 per arm | 29 per arm (byte+5) |
| faults / hangs / measurement failures | 0 | 0 | 0 | 1 fault (§6) |

**The one encoding collision, fully explained.** `ext` dispatches 2048 cases (8 bytes x 256
values) but yields **2041** distinct actual encodings. The seven collisions are exactly the
"set byte *b* to the value it already has" cases: the anchor's bytes +4..+11 are
`13 12 00 00 00 80 01 00`, so the eight identity mutations all reproduce the anchor encoding
and collapse to one — 2048 − 8 + 1 = 2041. This is a benign self-collision, not a `match`-bit
collision, and Gate A reports it rather than hiding it. `dst`, `dstlo` and `b3` have **no**
collisions: 16/16 and 256/256 distinct actual encodings per arm.

---

## 2. What was OBSERVED (separate from interpretation)

### 2.1 `half_alu_fma12`, 12-byte form, `byte+2 = 0x06`, `byte+4 = 0x13`

For every dispatched case, all 16 GPRs were dumped **before** and **after** the instruction,
into a read-back poisoned with `0xDEADBEEF`, with independent PRE and POST sentinels.

Observed, on 4 arms x 11 decidable values x 2 runs = 88 cases, with **zero** exceptions:

* exactly one architectural register changed, and it was **`r[byte0 >> 4]`**;
* only that register's **LOW 16 bits** changed; its **HIGH 16 bits were preserved**;
* the value written equalled the host prediction
  `fp16_rn(|h(byte+1)| * h(byte+3) - h(byte+5))` computed from that case's **own** pre-dump,
  where `h(d) -> (GPR (d & 0x7F) >> 1, half d & 1)`;
* all four 2-byte length markers survived, i.e. the hardware consumed exactly 12 bytes, on
  **16 of 16** values in every arm and run.

### 2.2 `half_pack` (`byte0 = 0x18`), 4-byte form

Observed on 4 arms x 256 values x 2 fields x 2 runs = 4096 cases, with **zero** exceptions:

* `r[byte0 >> 4]`'s **HIGH 16 bits** changed and its **LOW 16 bits were preserved**;
* the value written equalled `fp16_rn(h(byte+1) + h(byte+3))`;
* **both named source half-lanes were zeroed** — and *which* lane, per case, followed the
  descriptor value;
* `hw_markers == 4` on 256/256 values, i.e. the hardware consumed exactly 4 bytes for every
  value of byte+1 and of byte+3;
* descriptor values `v` and `v | 0x80` produced identical observations: **bit 7 is a
  don't-care**, 128/128 pairs.

### 2.3 Rounding — measured, not assumed

The oracle evaluates in IEEE binary64 and rounds **once** to binary16 (RNE), i.e. it assumes
a **fused** multiply-add. Every case also carried the two-rounding prediction.

> Of 4244 `half_alu_fma12` cases with an oracle, the fused and two-rounding predictions
> **differ in 8**. The **fused** model matched in **8 of 8**; the two-rounding model in
> **0 of 8**.

That is a narrow but real discrimination: **the G17P fp16 FMA rounds once.** Bounded
honestly: **no case in this carrier produced a subnormal or an overflowing prediction**
(0 of 4244 each), so flush-to-zero, infinity and NaN behaviour are **UNTESTED here**.
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §5 Phase 3 asks for those inputs; the `falu2i`
minifloat immediate encoder this carrier seeds with cannot reach them, so that is a stated
gap for a successor, not a claim.

---

## 3. The correction this experiment owes the record

`validation.json`'s `half_alu_fma12.dst` note (written by EXP-0196) says the sweep already
exists — *"768 records over 256 distinct values in each of `EXP-0180-*/raw/g17p_run02` and
`g17p_run03`, all status OK"*.

**Those 768 records are not records of this field.** In EXP-0180's raw they carry
`fstart: 8, fwidth: 8` — **byte+1** — and EXP-0183 later **renamed that span to `srcA`** and
moved the name `dst` to bits 4..7. A 4-bit field cannot have 256 distinct values; that is the
tell. EXP-0180's only bits-4..7 arm is `DSTNIB`, 32 records, and it runs on **`half_alu_ext8`,
the 8-byte form**. So the 12-byte form's destination nibble had **never been swept at all**,
and EXP-0196's diagnosis ("does not need more values, needs an oracle") was half right.

EXP-0196's other two findings were correct and are exactly what this experiment fixed:
no `oracle` key existed on any of those records, and the read-back was not isolated.

---

## 4. Model corrections (`analysis/field_verdicts.json` → `db_defects`)

1. **`half_pack.dstlo` is misnamed** — it is a **source** half-register descriptor
   `h = (reg<<1)|is_high`, not a destination-low field.
2. **`half_pack.b3` is typed `raw`** — it is the **second source** half-register descriptor.
3. **`half_pack`'s destination is byte0's HIGH nibble**, and `db.json` pins all eight bits of
   byte0 in `match` (0x18), so every db-expressible encoding writes `r1`. Arms `HP_C`/`HP_D`
   run the same instruction at destination nibble 7 (`78 0d 18 11`) with 256/256 oracle match,
   so the nibble is a real destination selector.
4. **`half_pack` writes the destination's HIGH half** and preserves the low half — the
   mirror of its byte0-low-nibble-0 sibling. A `half2` op is one instruction per lane.
5. **`half_pack` releases both named source half-lanes** at `byte+2 = 0x18` (opflags 3).
6. **`half_alu_fma12.ext` should be split** (§5).
7. **Hardware confirmation of DEF-0154-1** (§7).
8. **A self-reported defect in this experiment's own harness** (§6).

**Operand order is NOT established** for `half_pack`: the measured operation is commutative,
so this sweep cannot separate byte+1 from byte+3 by role. The proposed names follow the
family's positional convention, and that is stated as a convention, not an observation.

---

## 5. `half_alu_fma12.ext` — what a 64-bit "field" actually contains

`ext` is **forced to `untested`**: 2048 sampled values out of 2^64 is not a range, and the
pre-registration said so before the first dispatch. That is a statement about the descriptor.
The structure inside it was measured (`analysis/ext_bytes.json`, 2048 values x 3 arms x 2
runs), at (opsel 6, length selector 3):

| bits | byte | what was measured |
|---|---|---|
| 32..33 | +4 low 2 | **length selector** — 128 of 256 values change the consumed length (marker chain), and every one of those is excluded from every semantic claim |
| 34..39 | +4 high 6 | **modifier bits**; live at bits 3,4,5,6,7; bit 2 showed no effect on any of 3 arms. Bit 4 negates the third operand (`|a|b+c` at 0x03/07/0b/0f → `|a|b−c` at 0x13/17/1b/1f); bit 7 additionally **releases** the byte+5 source lane |
| **40..47** | **+5** | **`srcC` — the third fp16 source half-register descriptor.** 256/256 hardware identity preserved **and** 256/256 full-post-state oracle match on **all three arms in both runs**; bit 7 a measured **don't-care** (128/128 pairs identical) |
| 48..55 | +6 | live at bits 2..7 (carrier-dependent); 7, 9 and 11 distinct payloads on arms A, C and B |
| 56..63 | +7 | live at **bit 4**; 4 distinct payloads on all three arms |
| 64..71 | +8 | live at **bit 1** only; 2 payloads |
| 72..79 | +9 | live at **bit 1** only; 2 payloads |
| 80..87 | +10 | live at **bit 0**: **1 payload on carrier A, 2 on carriers B and C in the same runs** |
| 88..95 | +11 | **1 payload on all three arms** |

**Nothing here is declared inert.** byte+10 is the reason, and it is the cleanest
demonstration of the trap in this whole experiment: on carrier A it looks completely dead over
all 256 values, and on carriers B and C, in the *same runs*, it moves. The correct status for
byte+11 is the protocol's safe negative wording:

> `inert in this exact tested envelope (opsel 6, length selector 3, three compute carriers,
> 16-GPR readback); global role unknown`

`half_alu_fma12` must keep `emit_unsafe`: bits 48..95 are a liveness map, not a semantic one.

---

## 6. Faults, contamination, and a defect in our own harness

**Runs 31/32.** 1 fault in 16,820 dispatches: `F12_EXT_C`, `ext` byte+7 = 0xEE
(`70 0d 06 11 13 12 00 ee 00 80 01 00`), `kIOGPUCommandBufferCallbackErrorHang`, in run31
only; the same case was clean in run32. It is recorded as a fault, kept, and **not**
generalized — a single observation never concludes `fault`.

**Runs 21/22/23.** 7 faults, all in run23 (reverse order), all in `ext` arms or the
`__fals_F2_opsel` falsifier, none reproducing in the two forward runs.

**One InnocentVictim, and what it exposed.** In run32 arm `F12_EXT_C`'s **anchor** dispatch
returned `...ErrorInnocentVictim` — a sibling context's GPU error/recovery. That revealed a
**defect in this experiment's own harness**, which is reported rather than hidden:

> `harness/run.py::classify()` returns `ok` when the arm's anchor observation is `None`, so a
> **lost anchor silently becomes a pass** for every case in that arm. 2048 of run32's outcome
> labels defaulted to `ok` because of it. `classify()` should return `invalid_run`.

**Impact on the verdicts: none.** The promotion gate never reads `outcome` for movement — it
compares observed post-state digests against run31's (clean) anchor, and the oracle is
computed per case from that case's own pre-dump. Cross-run agreement over the affected arm is
2047/2048. The fix is recorded, not applied: the raw is append-only and the runs are gated.

**Gate E's quiet-machine clause is NOT met, and that is stated rather than glossed.**
`raw/*/03_procsample.jsonl` is a *measurement*, not a claim: during runs 31 and 32 the device
was concurrently running EXP-0199, EXP-0200, EXP-0201, EXP-0202, EXP-0204 and EXP-0206
(load average 0.94–1.35). A genuinely quiet window is the orchestrator's to grant and was not
available. What the confirmation rests on instead, explicitly:

* **five** gated runs in three orderings (`run21`, `run22`, `run31` forward; `run23`, `run32`
  reverse), all agreeing;
* **0 cross-run disagreements** on all three promotable fields, over 4096 half_pack and 128
  `dst` case-pairs;
* **0 faults, 0 hangs, 0 victims, 0 measurement failures** on those three fields;
* poisoned read-back plus two independent sentinels, so *never ran* is distinguishable from
  *wrote zero*;
* EXP-0160's evidence-validity filter, which is what `FIELD-SWEEP-PROTOCOL` §7 authorises as
  the alternative to a quiet window: **contamination can destroy an observation but it cannot
  fabricate a coherent one** — and here every observation matched an independently computed
  host prediction, in both run orders.

**Bounded unknown, recorded:** the promotable verdicts have not been confirmed on a measured-
quiet machine. If the orchestrator wants that, it is a 4-minute rerun of `run31`/`run32`.

---

## 6b. Reading `tools/agx-isa/wave_audit.py`'s numbers on this experiment

The arrival gate reports, over all six runs: `dst` V=24 valid payloads / L=16 legal values,
16 distinct encodings, 0 hard outcomes, 100.00% cross-run agreement; `dstlo` and `b3` V=116 /
L=256, 512 distinct encodings, 0 hard outcomes, 100.00% agreement; `ext` V=168 / L=256, 4082
distinct encodings, 7 faults counted **separately** from payloads, 100.00% agreement.

**`V` being far below `L` for `half_pack` is the PREDICTED result, not weak detection power.**
Both fields are half-register descriptors over a 16-GPR file: 32 lanes are reachable, bit 7 is
a measured don't-care, and every descriptor naming an unseeded GPR reads 0 — so 256 values can
only produce 29 distinct payloads per arm, and 29 x 4 arms = 116. The whole point of the
oracle is that it says **which** of the 29 each value must produce, in advance, and it was
right on 1024/1024 values per run. A liveness-only sweep would have had to treat V=116 as a
weakness; a semantic one treats it as a confirmation. `distinct oracles` is 64 / 126 / 93 —
nowhere near the constant oracle that would make the whole exercise vacuous.

---

## 7. Gate-by-gate result

| gate | result |
|---|---|
| **A — actual-byte ledger** | **PASS.** Per case: requested value, requested bytes, actual bytes read back from the artifact handed to the GPU, value decoded from those actual bytes, program sha256 + instruction offset, db + harness revision (`db:2412eac1cad4\|harness:804bf23b1e32`). **16820/16820 `bytes_match`; 16512/16512 field cases `requested == decoded`** (308 instrument cases have no field value). Distinct actual encodings equal dispatched count in every arm. Independently re-verified offline by `analysis/ledger_check.py`: the host re-synthesizes each program and reproduces the on-device bytes **16820/16820**. `program_sha256` differs between runs and that is explained, not swept up: it covers the whole spliced container and `shdump` recompiles our MSL per run; `instr_offset` and `actual_instr` are identical 8410/8410. |
| **B — carrier can see the effect** | **PASS.** `__ctl_live_srcA` / `__ctl_hp_live`: **88/88 oracle matches across 11 arms** in run31, 8 distinct payloads per arm. `__ctl_unseeded`: 33/33. Poisoned read-back, independent PRE/POST sentinels, complete 16-GPR dumps before and after, and **two disjoint register/readback plans** per promotable field. The observable cannot co-vary with the field: it is the whole 16-word post-state, and the oracle is computed from the case's own pre-dump. |
| **C — independent model** | **PASS.** 9 frozen competing `half_alu_fma12` models and 7 frozen `half_pack` models, per-case host prediction, and a per-case `semantic_class` over all ten buckets. `sem_checked` is 4096/4096 for `half_pack` (**all `correct`**) and 88/88 for `dst`. Adversarial cases: **33 falsifiers, 0 oracle matches, in both runs**; the null-block falsifier additionally matched the independent null prediction 11/11. Offline gate G10 proves the classifier can return every bucket including `unexplained`. |
| **D — compiler recipe** | **PARTIAL, declared.** `generated-point`, not `canonical-recipe-proven`. Donor regions named: `half_alu_fma12` bytes +6..+11 keep the values our own `k_hfma_abs` compiled to, and byte+2's opsel 6 and `half_pack`'s byte+2 = 0x18 are compiler-observed constants. Everything else is constructed from rules — necessarily, since `db.json` pins byte0 and no assembler can express another destination. |
| **E — clean confirmation** | **PARTIAL.** Two runs in opposite case order with identical actual-byte ledgers and no victim/cascade evidence on any promotable field — but **not on a measured-quiet machine** (§6). |

Offline gates (`harness/selftest.py`, a **code** test and not evidence): 20/20 pass,
including that the promotion gate **refuses** a constant oracle, a low oracle rate, a matched
falsifier, a missing liveness control, an incomplete ledger, aliased actual encodings, and
`sem_checked == 0` — and that it does **not** refuse a width-1 field by arithmetic
(the `2*max(disagree,1)` trap).

---

## 8. Limitations and bounded unknowns

1. **`dst` is decidable at 11 of 16 values per arm.** Five per arm are overwritten *after* the
   block by that arm's own infrastructure. They are recorded `carrier_undecidable`, never
   `inert`. The two readback plans are complementary, so all 16 are decidable somewhere and 6
   in both — but no single arm saw all 16.
2. **Operand order in `half_pack` is not established** (commutative operation).
3. **`ext` cannot be promoted** and its bytes +6..+11 are a liveness map only.
4. **byte+11 is not inert**, only `inert in the stated envelope`.
5. **fp16 special values are untested**: 0 subnormal and 0 overflowing predictions occurred, so
   flush-to-zero, infinity, NaN and signed zero are open. `falu2i`'s minifloat immediates
   cannot seed them; a successor needs a different seeding path.
6. **One operation only.** `dst`, `dstlo` and `b3` were swept at a single `(opsel, opflags,
   length)` point each. Per §4 of the corrections document a byte inert or live under one
   opcode is not globally so; the same caution applies to a destination selector, though far
   more weakly.
7. **Gate E's quiet-machine clause** (§6).
8. **`emit_unsafe` stays** on `half_alu_fma12`.

## 9. Progress accounting (§9 of the corrections document)

* **New raw observations:** 41,032 case records over 6 runs (1 pilot, 5 gated), append-only.
* **New geometry facts:** the 12-byte fma destination nibble and both `half_pack` operand
  bytes are ledger-verified over their full encodable range with distinct actual encodings;
  `half_pack`'s hardware length is 4 bytes for all 256 values of byte+1 and byte+3.
* **New liveness facts:** per-bit liveness map for all eight bytes of `ext`.
* **New semantic facts:** three fields `semantically-mapped`; `ext` bits 40..47 identified as
  a third source operand; `half_pack`'s write target, source release and don't-care bit;
  the fp16 FMA rounds once.
* **New generated recipes:** none claimed (`generated-point` only).
* **Claims downgraded:** none. EXP-0196's `dst` note is **corrected** (§3), not withdrawn —
  its two substantive findings stand.
* **Bounded unknowns remaining:** §8.

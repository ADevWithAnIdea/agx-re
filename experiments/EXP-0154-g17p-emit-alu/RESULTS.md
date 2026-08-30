# EXP-0154 — RESULTS: making the float and integer ALU emittable on **G17P**

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9), `192.168.10.243`. **Every field verdict below is
`target: G17P`, measured directly on the documentation target.** No M4 GPU work; no M5.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal (27 authored kernels) and kernels/carrier_dag.metal,
  both authored by us for this experiment, and the AGX machine code the PUBLIC runtime API
  compiled from that source. tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
Apple binary introspection: NONE.
Reproduction: README.md section "Reproduction".
Evidence: raw/g17p_20260829_run02/, raw/g17p_20260829_run04/ (the gated pair);
          raw/g17p_20260829_run01/, raw/g17p_20260829_run03/ (retained partials);
          work/smoke/smoke.json, work/anchor_report.json, work/frozen/
```

---

## 1. Headline

| | |
|---|---|
| Blocking fields at dispatch (db.json x validation.json, 32 ALU instructions) | **135** |
| Cases executed per gated run | **23,267** x 2 runs |
| Cases surviving the cross-run gate | **22,340** (896 victim-class excluded, 31 disagreements over 14 fields) |
| Field verdicts produced | **213** (96 `hardware-run`, 32 `isolated-byte-diff`, 85 `untested`) |
| Fields **upgraded** over committed `validation.json` | **58** |
| **Instructions that become EMITTABLE** | **7** |
| Emittable count | **38 -> 45** |

### The seven instructions unblocked

**`iadd2`, `ibfe`, `ishift`, `isel10`, `ilogic`, `falu_acc`, `shift_amt_move`**

`iadd2` and `ilogic` are the two that matter most for a compiler: integer add/subtract and
the whole 2-input boolean-logic family.

### The method that did it

**50 operand-selector fields got a real value -> register-index map** — including 17 of the
45 selectors EXP-0139 explicitly could not map. The instrument is a behaviour EXP-0138
recorded as a *trap*: **reading a GPR as a 32-bit source zeroes it (release-on-read)**. By
seeding all 16 registers with distinct values and dumping all 16 after the instruction, the
register that goes to zero *identifies the operand the descriptor named*, independently of
the instruction's arithmetic. Confirmed directly on G17P (pilot S3, and again in the
`iadd2.srcB_ext` sweep). Distribution of the recovered packings:

| packing | fields |
|---|---|
| `reg = (v>>1) & 63` | 20 |
| `reg = v & 127` | 12 |
| `reg = v>>1` (`(reg<<1)\|size`) | 7 |
| `reg = v & 15` | 6 |
| `reg = v>>2` (`reg<<2`) | 5 |

---

## 2. The load-bearing finding: `iadd2.srcB_ext` is not a modifier

EXP-0139 (32-bit carrier) declined to promote it; EXP-0146 (64-bit carrier) promoted it as a
modifier with `(v & 0x7C) == 0x00`. **Both framings are wrong.**

**Observed.** On a 32-bit carrier (`SYNTH+LIFTED:k_u32add@iadd2[32:42]`, `opmode` held at
`0x02`), dense over all 128 values:

```
d = r[srcB_ext >> 2] + r[srcB_imm >> 2]        matched 128/128
```

confirming all 16 observable registers r0..r15; every value naming an unseeded register
(>= r16) reads 0, exactly as the model predicts. **`srcB_ext` is the srcA REGISTER SELECTOR,
in the `reg<<2` packing.**

**Width proof (this carrier is 32-bit, not 64-bit):** the baseline writes r0 = 44 = 10 + 34,
a single register, and leaves r1 at its seed 21. A 64-bit add would have written the pair.

**Interpretation.** EXP-0146's `(v & 0x7C) == 0x00` *does* fit the ok-set exactly — because
it encodes "srcA must be r0" for that carrier. Adopted as a modifier constraint it would tell
an emitter that bits 2..6 must be zero, when those bits are precisely how a register is
chosen. EXP-0139 was right to decline; its "no <=4-bit rule" bar was looking for the wrong
kind of rule. **The field is not width-dependent.**

**Corrects a prior HW-VALIDATED claim.** EXP-0128/EXP-0139 recorded that `iadd2`'s `srcA`
byte (byte+7 = `0xa8`) "always reads r0". It read r0 only because `srcB_ext` was 0 in every
compiler-emitted anchor. byte+7 is **not** the srcA register selector. (`db_defects` ::
DEF-0154-4.)

---

## 3. `ilogic`: all 16 boolean functions on G17P — and an emitter-breaking label swap

**Observed.** The 2-D probe (`op_base` x `lut_a` 0..15 x `lut_b` 0..15, 512 combinations,
dense) realizes **all 16 two-input boolean functions on G17P**, with the selector
`(op_base, lut_a & 3, lut_b & 0x0f)` **collision-free** over the swept space. The function is
recovered bit-exactly and only accepted when the result is a *consistent* bitwise function
across all 32 bit positions.

**M4 -> G17P reproduction:** EXP-0146's complete M4 table reproduces **16/16**.

**But only under the opposite operand labelling.** Scored both ways:

| convention | functions | M4 minimal selectors reproduced |
|---|---|---|
| `a` = db.json `srcA` (byte+1) | 16/16 | **8/16** |
| `a` = db.json `srcB` (byte+3) | 16/16 | **16/16** |

The eight that fail under db.json's names are **exactly the eight asymmetric functions**
(`a_and_not_b`, `a`, `not_a_and_b`, `b`, `not_b`, `a_or_not_b`, `not_a`, `not_a_or_b`); the
eight symmetric ones look correct either way. So an emitter combining
`EXP-0146/analysis/ilogic_lut_table.md` with db.json's field names emits half the boolean
functions backwards, and the bug surfaces late and looks data-dependent.
(`db_defects` :: DEF-0154-5.)

---

## 4. Other db.json defects recorded (NOT edited — protocol section 6)

* **DEF-0154-1 — `half_pack`'s length rule is over-constrained.** Compiling our own
  `half2 add` on G17P produces `_agc.main` whose tail our DB **cannot tokenize**: 22 bytes are
  left undecoded. `isadb.py` accepts byte0 `0x18` as a 4-byte `half_pack` only when
  byte+1 == `0x05`; G17P's own compiler emits `18 03 18 05`. EXP-0038 recorded the A18 form as
  `18 05 18 03` — the two differ by swapping byte+1 and byte+3, i.e. by register allocation,
  so **byte+1 is an operand descriptor and must not be a length gate**.
* **DEF-0154-2 — `ilogic` has no destination field.** db.json models byte0 as a fixed 8-bit
  match (`0x0b`) and lists no destination at all, so an emitter has no modelled way to choose
  where the result lands. The 16-register dump locates it directly.
* **DEF-0154-3 — fields that behave as operand descriptors but are not typed `reg`**,
  enumerated from the data in `analysis/field_verdicts.json`.

---

## 5. Negative results and honest failures (first-class)

* **Two arms FAILED their pre-registered falsifier and nothing in them was promoted.**
  `CARRY_GEN` and `MOV_ZEXT16`: forcing byte0 of the instruction under test to `0x00` still
  reproduced the entire 16-register baseline, so those arms cannot see a difference.
  For `CARRY_GEN` the cause is diagnosable and is my own design error: **the integer seeds
  (all <= 127) never produce a carry out of the low word**, so the carry-generate is a no-op
  in this carrier whatever its encoding. A successor must seed operands that actually carry.
  This withdrew 5 upgrades that an earlier pass of my own analysis had granted.
* **`irotate.operands` genuinely hangs the GPU on G17P.** Around byte+7 = 231/232 the
  command buffer returns `Caused GPU Hang Error
  (00000003:kIOGPUCommandBufferCallbackErrorHang)` — **genuine**, not `InnocentVictim`, and
  reproducible across majority-of-3. They are *contained* (0 watchdog hangs, no host wedge)
  but they reset the device for other agents. A successor should take
  `gpulease.sh` around this arm.
* **The `IBFE` arm's `offset`/`width` are only weakly live**, because the lifted anchor's
  source values are the integer seeds (<= 127), so bits 4..11 are mostly zero and the anchor's
  own result is 0. **The pre-registered F4/F5 M4-reproduction tests for `ibfe.offset`
  (literal) and `ibfe.width` (mod-32) are therefore INCONCLUSIVE here** and are reported as
  such, not as reproductions. `ibfe` still becomes emittable, but on the strength of `dst`,
  `b5` and `srcA` (register maps over 14 registers) merged with the *existing*
  `offset`/`width` labels — not on anything this experiment claims about those two fields.
* **`fspecial` was never opened** (11 fields, still blocked). EXP-0138 recorded three
  reproducible GPU hangs on its byte+3 bit7 and stopped that arm; this experiment respects
  that rather than re-running it.
* **No own-MSL anchor exists** in 27 authored probe kernels for `icmpsel`, `isel10_c`,
  `isel_reg8`, `int_alu_ehi` or `ibfe_mesh_attr`, so those were not swept. Notable corpus
  facts: `insert_bits` compiles to `b_alu10_lof`, **not** `ibfins` (which appears instead
  inside a *variable rotate*); and `a<b ? a : b` compiles to `iminmax`, not to a select.
* **51 cases tripped the integrity sentinel** while otherwise executing; they are recorded
  with `sentinel_bad: true` and are not promoted.

### Within one field of emittable (the highest-value follow-ups)

`falu2_ext` (`ctrl`) · `falu3` / `falu3_ext` (`op`) · `iminmax` (`srcB`) · `isel8`
(`cmp_mode`) · `imad` (`srcC_desc`) · `half_pack` (`src`) · `falu2i` (`ctrl_lo`).

---

## 6. Pre-registered M4 -> G17P reproduction tests (H5)

| test | M4 result | G17P | verdict |
|---|---|---|---|
| `iadd2.lenbit = 0` selects the 12-byte form | not `ok` | not `ok` | **reproduced** |
| `iadd2.dst >= 192` (reg >= 96) faults | reproducible fault | 2/2 fault | **reproduced, but only 2 values tested** (the field was sampled, not dense) |
| `ilogic` reaches all 16 boolean functions | 16/16 | 16/16 | **reproduced** |
| `ilogic` minimal selector table | EXP-0146 table | 16/16 | **reproduced** (under the swapped labelling, section 3) |
| `ibfe.offset` literal / `ibfe.width` mod-32 | EXP-0139 | — | **INCONCLUSIVE** (section 5) |
| release-on-read zeroes a GPR source | M4 (EXP-0138) | observed | **reproduced on G17P** |

No G16G <-> G17P *hardware* divergence was found. The two apparent divergences both turned
out to be **documentation defects on our side** (DEF-0154-1, DEF-0154-5).

---

## 7. Concurrency, fault discipline, and what it cost (FIELD-SWEEP-PROTOCOL section 7.4)

**This experiment did NOT run alone.** Throughout both gated runs, sibling GPU experiments
were live on the same device — EXP-0155 and EXP-0156 (the latter holding `gpulease.sh`), plus
further `run.py` processes. The two gated runs also ran concurrently **with each other**, in
opposite arm order so they would not hit the same illegal encodings simultaneously.

| | run02 | run04 |
|---|---|---|
| cases | **23,267 (complete)** | **23,267 (complete)** |
| ok / wrong_value / silent_zero | 7,385 / 11,940 / 3,309 | 7,392 / 11,958 / 3,305 |
| fault | 633 | 612 |
| watchdog hangs | **0** | **0** |
| baseline failures | 0 | 0 |
| order | forward | reverse |

Across both runs the OS's own classification splits as **2,239 `...ErrorHang`** (ours) and
**1,861 `...ErrorInnocentVictim`** (a sibling's device reset landing in our command buffer).
Every non-OK case carries the string verbatim; victim-class cases are excluded from the
cross-run gate. **896 cases were excluded as victim-class and 31 more disagreed across the
two runs** — those 31 are the honest cost of running against five other agents, and they are
listed per field in `analysis/field_verdicts.json :: _meta.cross_run_disagreements`.

The counters agreeing to within 0.1% on an identical 23,267-case matrix executed in opposite
order is the strongest available evidence that the measurement is stable.

---

## 8. Process integrity (disclosed)

* **`run01` (2,306 cases) and `run03` (9,000 cases) are retained exactly as they stopped** —
  not topped up, not reused, not deleted. run03 died when a **sibling's** hang caused a device
  reset, our baseline was discarded as `InnocentVictim`, and a missing null guard killed the
  process. The anti-cascade machinery worked; the guard did not.
* **Three amendments are recorded in `CAPTURE_CONTRACT.json`**, including
  **`amendment_03`, which corrects a wrong measurement of my own**: the "~3.3 dispatches/s"
  that justified reducing the case matrix was inferred from a bad assumption about elapsed
  wall time. The runs' own timestamps show 44.9 cases/s. The reduction was therefore
  unnecessary; it is left in place because every field *below* emitter grade is still swept
  densely, and `EXP0154_DENSE_ALL=1` (matrix v3, 36,222 cases) is available to close the
  remainder in ~15 minutes.
* **Analysis is pinned to `work/frozen/`**, a sha256-verified copy of the exact
  `db.json`/`isadb.py`/`validation.json` the hardware ran against. The repo host's
  `tools/agx-isa/db.json` **drifted during this experiment** (a sibling split `ilogic.lut_a`
  into `lut_a_sel`/`lut_a_free`/`lut_a_z`), which would have silently re-keyed these verdicts
  against a descriptor the hardware never saw.
* Four analysis flaws were found and fixed **by my own liveness checks after the first
  verdict pass**, each of which had inflated the result: an "INERT across the whole encodable
  range" verdict being granted from a ~30-value sample; destination writes being
  misattributed as release-on-read when the result value is 0; the LUT decoder unable to see
  the carrier's *own* function; and the register-map path bypassing the falsifier gate. The
  headline fell from a naive +6/63 to the audited **+7/58** after these were corrected
  (`ilogic` was added, `CARRY_GEN`/`MOV_ZEXT16` withdrawn).
* `db.json`, `validation.json`, `docs/` and `PROVENANCE.md` were **not edited**, and nothing
  was committed.

---

## 9. Verdict

**SUBSTANTIAL — and honestly bounded.** Seven instructions move from decodable to
**emittable on G17P**: `iadd2`, `ibfe`, `ishift`, `isel10`, `ilogic`, `falu_acc`,
`shift_amt_move`. 58 fields upgraded, 50 of them with a real operand -> register-index map
rather than a "this one value works" rule — which is the difference between a table an
emitter can use and a table that merely records what the compiler happened to emit.

The two results most likely to change what a downstream emitter writes are
**`iadd2.srcB_ext` being a register selector** (section 2) and the **`ilogic` LUT operand
labelling** (section 3): both are cases where the previously committed answer would have
compiled, run, and produced wrong results silently.

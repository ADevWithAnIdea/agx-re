# EXP-0138 — RESULTS: M4 float-ALU emission closure (`DRV-ISA-01` / `P0.6`)

**Target:** Apple **M4 / G16G**, local host only (macOS 26.6.2, 25G82, Metal 4).
No A18 Pro contact of any kind. No M5. Every claim below is a **G16G** claim.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal + work/pilot/anchors*.metal, 42
  authored kernels), the AGX bytes those compile to, and the outputs the GPU
  produced from them. tools/shdump, tools/agxtest and tools/agx-isa were used
  READ-ONLY and unmodified.
Apple binary introspection: NONE.
Reproduction: harness/build.sh; harness/run.py --run <id>;
  analysis/verdicts.py raw/m4_20260828_run01 raw/m4_20260828_run06;
  analysis/annotate.py raw/m4_20260828_run01 raw/m4_20260828_run06 raw/m4_20260828_run05;
  analysis/model_check.py raw/m4_20260828_run01 raw/m4_20260828_run05 raw/m4_20260828_run06
Evidence: raw/{smoke01,smoke02,m4_20260828_run01..run07}/
```

---

## 1. Headline

| | |
|---|---|
| Previously-blocked float-ALU fields | **98** (the dispatch said 107; `falu2_ext8b`'s 9 were deleted by EXP-0148 — it was never an instruction) |
| Fields actually swept on hardware | **86** |
| Fields reaching **emitter grade** | **65** = 59 `hardware-run` + 6 `isolated-byte-diff` |
| Fields still `untested` after the sweep | 21 |
| Fields never swept | 12 (`fspecial`'s 11 — arm STOPPED for hangs; `half_alu_fma12.ext` — `emit_unsafe` by design) |
| **Instructions that become emittable** | **4: `copysign`, `falu2`, `half_alu`, `half_alu_ext8`** |

**`falu2` — the most-used instruction in the ISA — is now emittable.** Its sole
blocking field `mod_lo` is `hardware-run`, dense over all 8 values, with an
**identical per-case outcome map in all three independent runs (98/98 cases in
`run01`, `run05` and `run06`)**.

---

## 2. Priority 1: `falu2.mod_lo` — what it actually is

**Observed** (98 cases: all 8 values x 8 operand configurations, plus a 33-point
sweep of `srcB_reg` at `mod_lo=2`, plus the pre-registered refuter):

`mod_lo` is **not a spare modifier. It is an operand-SOURCE-CLASS field.**

* **bit0** selects `srcA`'s source class. `0` = GPR at `srcA_reg`. `1` = a second
  class that returned **0.0 at every index tested** (`srcA_reg` in {0, 6}) — in
  particular it is **NOT** the uniform file: at `srcA_reg=6`, where the uniform
  file holds 101.0, `mod_lo=1` still produced 0.0.
* **bits[2:1]** select `srcB`'s source class:
  * `0` = GPR at `srcB_reg`;
  * `1` = the **non-GPR operand file** addressed by `srcB_reg` (see §3);
  * `2` and `3` both read **0.0**, and **bit2 dominates bit1** — `mod_lo=6` reads
    0.0 at the very index where `mod_lo=2` reads 101.0.

The pre-registered hypothesis **H-MODLO** ("bit0 = srcA reads the uniform file;
bit2 behaves like bit1") is therefore **REFUTED in both of its halves** and
replaced by the rule above. The replacement was then scored against every case:
**98/98 exact in each of the three runs, 294/294 overall**
(`analysis/model_check.py`).

The pre-registered **refuter fired as designed**: `mod_lo=2` with `srcB_reg=2`
(an unbound uniform index) returned **5.0**, not the GPR answer 8.0 — proving the
sweep could see the difference it was looking for.

## 3. The largest single find: `falu2` has an inline float immediate

With `mod_lo` bits[2:1] = 1, `srcB_reg` is **not a register index**, and its
**bit6 is live** — which is why this was never visible in GPR mode, where
EXP-0099/EXP-0112 correctly found bit6 inert (`r(R mod 64)` aliasing).

* `srcB_reg` **0..63** → uniform-register file index. The bound
  `constant float4& = {101,202,303,404}` appeared at indices **6..9**.
* `srcB_reg` **64..127** → an **inline 8-bit minifloat immediate**, with
  `k = srcB_reg - 64`, `e = k>>3`, `m = k&7`:

  ```
  value = m * 2^-5              (e == 0)
  value = (8 + m) * 2^(e-6)     (e  > 0)
  ```

  HW-confirmed at `k` = 0, 2, 3, 31, 32, 48, 56, 61, 62, 63 →
  0, 0.0625, 0.09375, 1.875, 2.0, 8.0, 16.0, 26.0, 28.0, 30.0.
* Consequence for safety: indices **126/127 do NOT fault in this mode** (they are
  the immediates 28.0 and 30.0), unlike GPR mode where EXP-0112 recorded a fault.
  The register model does **not** transfer across `mod_lo` classes.

Caveat, stated because it is fitted rather than derived: uniform index **10**
read back ≈1.0 in this carrier. That is the carrier's **own literal**, a property
of `kernels/carrier_uni.metal`, not a hardware fact; `analysis/model_check.py`
marks it `CARRIER_SPECIFIC`.

## 4. The other three instructions unblocked

* **`copysign` (4 B) — `operands` (byte+3) is INERT**: all 256 values return the
  same result. That is a hardware fact, not a dead path, because the
  pre-registered **falsifier arm on byte+1 fired hard**: 240/256 values silently
  zero, 8 return −5.0, 8 return +5.0 (the sign flips). `db.json` models byte+1
  and byte+2 as fixed match constants; **byte+1 is a live operand field and
  byte+2 is a 256/256 don't-care.**
* **`half_alu` — `dst`(byte+1) and `opflags` both `hardware-run`, dense.**
  **H-HALF-LAYOUT is CONFIRMED**: byte+1 is the **first source descriptor**, not
  the destination. Its live values track the MODE-B carrier's memory operands
  exactly (`0x04` -> 5.0+3.0 = 8.0, `0x02` -> 3.0+3.0 = 6.0, everything else
  -> 0.0+3.0 = 3.0), and **descriptor bit7 is confirmed inert**: `0x82` behaves
  identically to `0x02` and `0x84` to `0x04` — an independent reproduction of
  EXP-0099's inert-top-bit finding, on a different family. `opflags` 0..7 behave
  as the anchor, 8..29 change the result (release-source semantics, cf.
  EXP-0086/0099), 10..31 silently zero.
* **`half_alu_ext8` — `dst`, `opflags`, `b7_lo`, `b7_mid` all dense
  `hardware-run`.** `b7_lo`/`b7_mid` are inert across their whole range, with the
  same-carrier sensitivity witness recorded per field.

## 5. `db.json` defects found (recorded, NOT edited — protocol section 6)

Full detail in `analysis/field_verdicts.json` → `"db_defects"`.

1. **`falu2.mod_lo`** is an operand-source-class field, not an unlabelled modifier.
2. **`falu2.srcB_reg` bit6 is live in the non-GPR class** and 64..127 is an inline
   minifloat immediate, not a register.
3. **`falu3`/`falu3_ext` field NAMES are misleading.** **H-FALU3-LAYOUT is
   CONFIRMED**: byte0's high nibble is the DESTINATION (`dst_lo`, 14/16 exact);
   byte+1 (`dst`) is the FIRST SOURCE (228/256); byte+3 (`srcA`) the SECOND
   (228/256); byte+5 (`srcC`) the THIRD (252/256); byte+4 (`srcB`) is a CONTROL
   byte whose low 2 bits are the 0x09-group LENGTH selector (192/256 re-length the
   instruction). An emitter following db.json's names would put the destination in
   a source slot. **The 28 `dst`/`srcA` "misses" are not misses**: they are exactly
   the descriptor values with **bit0 clear**, i.e. a 16-bit read of an f32-seeded
   register, which returns 0.0 — that **confirms** `(reg<<1)|is32`. byte+5's bit0
   does **not** behave as a size bit (`srcC` = 22 and 23 both read r11 = 26.0).
4. **`copysign` byte+1/byte+2** (above).
5. **`fspecial` byte+3 bit7 is SAFETY-CRITICAL** (§6).

## 6. Negative results (first-class)

* **`fspecial.src` (byte+3) values 192..255 fault or hang the GPU.** `run01`
  (contended host): 60 reproducible `fault`s. `run05` (isolated host): values
  192, 193, 194 each **HUNG the GPU three times in a row** under the 12 s
  watchdog. Only values 2 and 3 give the correct `rsqrt(4)=0.5`; 188 values
  silently return 0.0; values 6 and 7 leave the poison intact (the store never
  ran). **An emitter must never set byte+3 bit7 of `fspecial`.**
  Per FIELD-SWEEP-PROTOCOL section 8 ("after two genuine hangs in one area, STOP
  that arm") the whole `fspecial` arm was stopped. **`fspecial` therefore has ONE
  gated run only and all 11 of its fields keep their existing labels.** This is
  reported PARTIAL, not rounded up.
* **`falu2_uni` has no compiler-emitted anchor** across 42 authored kernels; the
  encoding was constructed from `db.json`'s descriptor. 31/31 of its `srcA_reg`
  predictions and 10/31 of its `usrc` predictions were refuted; both are capped at
  `isolated-byte-diff` because the carrier held too few live sources to establish
  a register→value RULE. `opsel`, `opflags`, `ctrl_lo` remain `untested`.
* **`falu_srcmod12b.srcB_neg` and `.mod_lo` are inert** at the operands tested,
  although the *same-named* fields on `falu2` are live. Do not assume one operand
  model across the float-ALU families — the same lesson EXP-0139 recorded for
  `iadd2.dst`.
* **`falu_srcmod12b` `opsel == 4` was excluded from every sweep** (EXP-0119:
  corrupts an unrelated, independently seeded register). Both `falu_srcmod12b` and
  `half_alu_fma12` remain **`emit_unsafe` regardless of their field labels**, and
  `analysis/field_verdicts.json` says so in `_meta`.

## 7. Concurrency — how many other GPU experiments were running

**This materially changes the evidence and is stated per run.**

| run | cases | host state | victims | faults | hangs | cascades |
|---|---|---|---|---|---|---|
| `run01` | **16,202 (complete)** | ~9 concurrent GPU siblings | **41** | **254** | 0 | 0 |
| `run02` | 253 (partial) | — killed by a machine-wide `MTLCompilerService` collapse | 17 retries | — | 4 | — |
| `run03` | 188 (partial) | — same collapse | 1 | — | 4 | — |
| `run04` | **0** | killed by the host reboot | — | — | — | — |
| `run05` | 13,564 (partial) | isolated (quiet window) | **0** | 15 | 3 (`fspecial.src`) | 0 |
| `run06` | **14,119 (complete over 19 of 20 groups)** | isolated (quiet window) | **0** | **15** | **0** | **0** |
| `run07` | 280 (partial) | EXP-0143 + EXP-0151 holding live `agxrun_persist` children | 0 | — | ≥1 | — |

`run01`'s 254 faults and 41 victims against `run06`'s 15 and 0, on the identical
case matrix, is the contamination FIELD-SWEEP-PROTOCOL section 7 warns about,
measured. **All four partial runs are retained exactly as they stopped; none was
topped up, reused, or deleted.**

## 8. Which gated pair the labels rest on, and the honest alternative

The frozen promotion rule (`PRE_REGISTRATION.md` section 7) requires an identical
per-case outcome map in **two** gated runs. The pair analysed is
**`run01` + `run06`** (`run06` replaces the contract's dead `run02`), with
`run05` carried as a third, annotating run. **That is the conservative reading and
it is what `label` holds.**

The alternative is stated rather than buried: the same frozen script over the two
**isolated-host** runs (`run05` + `run06`) promotes **7 more fields** and would
make **8** instructions emittable instead of 4 (adding `falu2_ext`, `falu2i`,
`falu3_srcmod12`, and `falu_srcmod12b` — the last still `emit_unsafe`). Every one
of those 7 is held back **by `run01` alone**:

```
falu2_ext.ctrl  falu2_srcmod10.ctrl  falu2_uni.ctrl_lo  falu2i.ctrl_lo
falu3_srcmod12.ctrl  falu3_srcmod12.opsel  falu_srcmod12b.ext_srcmod
```

FIELD-SWEEP-PROTOCOL 7.1 ("a value is only `fault` if it faults *reproducibly, in
isolation*") arguably licenses the larger number. **This experiment does not take
it.** Each such field carries `label_isolated_pair` and a note; the orchestrator
decides. The smaller number is the one that stands.

## 9. Limitations / what remains unknown

* `fspecial` (11 fields): one gated run only, arm stopped for hangs. **PARTIAL.**
* `falu3.op`, `falu3.srcA`, `falu3.srcC` (and the `falu3_ext` twins),
  `falu_acc.srcA/.srcB`, `fspecial_est.dst`: held at `untested` by the frozen rule
  because 2–64 cases per field tripped the integrity sentinel. The cause is
  **demonstrated, not unknown** — see `db_defects.sentinel_release`: reading a GPR
  as a 32-bit source through these slots **zeroes that register afterwards**
  (release-on-read). Direct evidence: `falu3.dst`=23 returned **w0 = 85.0 =
  26*3+7**, i.e. the operand read r11 = 26.0 *correctly*, while the later
  read-back of r11 returned 0.0, with the poison still intact in every untouched
  word. These are valid measurements whose sentinel was destroyed **by the field
  working** — exactly the situation `verdicts.py` already excuses for `dst`
  fields. They are **reported, not promoted**; a successor experiment should
  re-run these six sweeps with the sentinel routed through a register no
  descriptor value can name.
* `falu2_uni`: constructed encoding, no compiler anchor; three fields untested.
* Wide `ext`/`ext_srcmod` tails are `isolated-byte-diff` only: each constituent
  byte was swept 0..255, **the full 16/32/48-bit space is not claimed.**
* 7-bit register fields were swept `0..15` dense plus 17 boundary values, not
  0..127 dense. The claim's scope is that range and no further.
* Everything here is **G16G**. Nothing is promoted to G17P.

## 10. Contract integrity (disclosed)

* `harness/families.py`, `harness/isa_helpers.py`, `harness/build.sh`, all three
  `kernels/*.metal` and `PRE_REGISTRATION.md` hash **exactly** as frozen.
* **`harness/bench.py` and `harness/run.py` were modified after the freeze**
  (commit `93822c0c` → `97162755`): retry `shdump`/`agxrun_persist` **startup**
  through a transient machine-wide `MTLCompilerService` outage, plus one extra
  counter in a `print`. It touches **no** part of case generation, splicing,
  poisoning, majority-of-3, victim classification, the sentinel, or outcome
  classification. Recorded in `CAPTURE_CONTRACT.json` → `amendments`; the frozen
  `authored_sha256` block was left untouched.
* **`tools/agx-isa/db.json` drifted** (sibling EXP-0144 at `ef86175e`). Diffed
  instruction-by-instruction: only `pack_convert`/`unpack_convert` changed, **no
  float-ALU instruction**. Verified empirically too — regenerating the whole
  16,202-case matrix under the current `db.json` reproduces `run01`'s recorded
  `bytes`/`instr`/`field`/`value` for **all 16,202 cases, 0 mismatches**.
* `db.json`, `validation.json`, `docs/` and `PROVENANCE.md` were **not edited**,
  and nothing was committed.

## 11. Verdict

**PARTIAL — substantial, honestly bounded.** 65 of 98 previously-blocked
float-ALU fields reached emitter grade on G16G; **`falu2` is emittable**, together
with `copysign`, `half_alu` and `half_alu_ext8`. `fspecial` is stopped for hangs
and stays where it was. The `falu2` inline-minifloat-immediate operand and the
confirmed `falu3`/`half_alu` layout corrections are the results most likely to
change what a downstream emitter writes.

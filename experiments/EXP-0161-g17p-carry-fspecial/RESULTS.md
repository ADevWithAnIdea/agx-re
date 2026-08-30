# EXP-0161 — RESULTS

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9, `Mac17,5`), `192.168.10.243`. **Every field verdict below
is `target: G17P`, measured directly on the documentation target.** No M4 GPU work; no M5.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal (13 authored kernels) and kernels/carrier_seed.metal,
  both authored by us for this experiment, and the AGX machine code the PUBLIC runtime API
  compiled from that source. tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
Apple binary introspection: NONE
Reproduction: README.md, "Reproduction"
Evidence: raw/g17p_20260829_run01 + run02 (the main gated pair);
          raw/g17p_20260830_supp02 + supp03 (second-carrier gated pair);
          raw/g17p_20260830_gen01/gen02/gen03 (the generation proof);
          raw/g17p_20260830_danger01 (the hang region);
          raw/g17p_20260830_adj01 (fault re-adjudication);
          raw/g17p_20260830_supp01 (RETAINED, self-contaminated -- see section 8);
          raw/prefreeze/ (the pre-freeze pilots);
          analysis/field_verdicts.json, analysis/fspecial_function_map.json,
          analysis/sfu_precision.json, analysis/adjudication.json
```

---

## 1. Headline

| | |
|---|---|
| The question EXP-0154 could not answer | **answered: the carrier fix works** |
| `carry_gen` falsifier `byte0 := 0x00` | **FIRES** (was `ok` in EXP-0154) |
| `carry_gen` falsifier `byte+2 := 0x00` | **FIRES** |
| `mov_zext16` falsifier `byte0 := 0x00` | **FIRES** in the synthesized carrier |
| Cases executed, main gated pair | **11,942 x 2**, 0 watchdog hangs, 0 baseline failures |
| Cross-run agreement, main pair | 11,754 agreed / 175 victim-excluded / **13 disagreements** |
| Cases over all gated pairs | 13,238 agreed / 639 victim-excluded / **17 disagreements** |
| Fields moved to emitter grade on G17P | **26 `hardware-run` + 1 `isolated-byte-diff`** |
| **Instructions that become EMITTABLE** | **`carry_gen`, `fspecial`, `fspecial_est`, `mov_zext16`** (two of them only after a `db.json` fix — section 10) |
| Generated (never-compiled) encodings executed | `fspecial` **20/20**, `carry_gen` **48/48**, `mov_zext16` **11/16** |
| `fspecial` byte+3 >= 192 | **45 of 64 values give a genuine `kIOGPUCommandBufferCallbackErrorHang`; 19 never cleanly observed; 0 ever worked** |
| Fault verdicts re-adjudicated 5x (section 8) | 60 sampled: **58 confirmed, 2 were not faults** |
| Contained `ErrorHang` command buffers this experiment caused | **1,571 over 30,056 dispatched cases** — disclosed in section 8 |

### The three answers the dispatch asked for

1. **Did the `carry_gen` carrier fix work? YES.** Seeding the registers so the lifted
   64-bit low-word add actually carries turns the arm from "nothing observable" into a
   fully mapped instruction. Both pre-registered falsifiers fire in **both** carriers.
2. **How many of EXP-0154's withdrawn upgrades are now legitimately earned? All nine —
   but two of them not in the way anyone expected.** EXP-0154 withdrew **5 `carry_gen` +
   4 `mov_zext16` = 9**. All five `carry_gen` fields (`dst`, `srcA`, `srcB`, `cmpmode`,
   `b5`) are earned outright, with value->register maps and accept-rules. Of the four
   `mov_zext16` fields, `subform` and `extend` are earned outright; `src_reg` and
   `src_flag` are earned as **HW-tested INERT in two independent register forms** — which
   is emitter-grade knowledge ("any value is safe") but is the *opposite* of what
   `db.json` says they are, and only became sayable once the real register field was
   located in byte0 (section 4).
3. **`fspecial` is open.** All 11 fields swept, the operand model corrected, the function
   map measured by computed value, and the dangerous region bounded exactly.

---

## 2. The load-bearing result: EXP-0154's arm died of a seed, and the seed is fixable

EXP-0154's `RESULTS.md` §5 said it plainly: *"the integer seeds (all <= 127) never produce
a carry out of the low word, so the carry-generate is a no-op in this carrier whatever its
encoding. A successor must seed operands that actually carry."*

`mov_imm`'s immediate is **seven bits** (EXP-0128/EXP-0140), so a seed that carries cannot
come from `mov_imm` at all — which is why the defect survived. This experiment seeds
r0..r14 with one `device_load` per register out of an authored SEED buffer, giving
arbitrary 32-bit values, and chooses them so that:

* the pair the lifted low-word add names (r1 and r3 in the `k_u64add` anchor) both have
  bit31 set, so **that add always carries**;
* the seeds are *spread* over `[0, 2^32)` rather than clustered, so `carry_gen`'s unsigned
  compare is TRUE for some register pairs and FALSE for others — without that spread the
  predicate would be constant and the sweep still could not tell operands apart;
* every high halfword is non-zero and distinct, so `mov_zext16` is not the identity and its
  result *names its own source*;
* every `extract_bits(v,4,8)` is distinct, so `ibfe` identifies its source too.

**Observed, in both carriers, both gated runs:** `carry_gen byte0 := 0x00` -> `wrong_value`;
`carry_gen byte+2 := 0x00` -> `wrong_value`; `mov_zext16 byte0 := 0x00` -> `wrong_value`.
All three were `ok` (i.e. undetectable) in EXP-0154.

---

## 3. `carry_gen`: fully mapped, and EXP-0146's M4 result reproduces exactly on G17P

| field | accepted values | rule | note |
|---|---|---|---|
| `srcA` (byte+1) | `{0x01, 0x81}` | `(v & 0x7F) == 0x01` | `(reg<<1)\|is32`, **bit 7 INERT** |
| `srcB` (byte+3) | `{0x03, 0x83}` | `(v & 0x7F) == 0x03` | same packing, same inert bit 7 |
| `dst` (byte0 hi nibble) | `{3}` of 16 | `(v & 0x0F) == 0x03` | selects the predicate register the following `psel` reads |
| `cmpmode` (byte+4) | 8 of 256 | `(v & 0xA7) == 0x22` | bits 3, 4 and 6 are **don't-care**; db.json enumerates only `0x22` |
| `b5` (byte+5) | `{0x01,0x05,0x09,0x81}` / `{0x01,0x05,0x81}` | — | live; no clean mask fits |
| byte+2 (a db MATCH byte, not a field) | 8 of 256 | `(v & 0xCD) == 0x05` | **identical to EXP-0146 on M4** |

**The srcA/srcB/byte+2 rows are an exact G16G -> G17P reproduction.** EXP-0146 measured
`srcA` on M4 as "exactly `{0x01,0x81}` — the project-standard `(reg<<1)|is32` packing with an
INERT bit 7" and byte+2 as "`(v & 0xCD) == 0x05`, 8 of 256 values
`{0x05,0x07,0x15,0x17,0x25,0x27,0x35,0x37}`". Both reproduce **value for value**, in both of
this experiment's independent carriers. `srcB` was `untested` on M4; it has the same shape.

**The register map, recovered directly.** In the synthesized carrier the register a swept
operand names is released to zero, so the value -> register map is read off the 16-register
dump: `carry_gen.srcB` fits `reg = (v>>1) & 0x3F` at **22/22**.

**And the size bit is real.** 16 generated encodings built with the size bit CLEAR while
predicting a 32-bit compare failed 9 of 16 — and **every one of the 16 outcomes is explained
exactly by the hardware comparing only the LOW 16 BITS** when the bit is clear. The
corrected model then passed **48/48** generated encodings across both widths and both
settings of the inert bit 7 (`db_defects :: DEF-0161-7`). This is a semantic db.json does
not record, and it is the kind of thing a compiler back-end gets wrong silently.

---

## 4. `mov_zext16`: EXP-0146's OPEN question is CLOSED — and the answer is "no"

EXP-0146 found byte+1 (`src_reg`) inert over all 128 values and left two explanations open:
**(a)** byte+1 is not a source-register selector, or **(b)** the operand was ALU-forwarded
from the immediately preceding `device_load`, making it a don't-care *in that instance*.

Three observations settle it as **(a)**:

1. **In EXP-0146's own carrier, deleting the whole instruction changes nothing.** The
   pre-registered falsifier `byte0 := 0x00` scores **`ok`** in `B_ZEXT_INPLACE` — the
   correct `a & 0xFFFF` still comes out. That arm therefore **fails its gate and nothing is
   promoted from it**, and EXP-0146's inertness finding is explained as a carrier artefact
   rather than a fact about the field.
2. **In the synthesized carrier the instruction IS live** (its falsifier fires, `subform`
   discriminates 8 accepted of 221, `extend` 32 of 256) and `src_reg` is **still inert over
   all 128 values, and `src_flag` over both** — in a carrier where fifteen loads and a
   sentinel store separate the source from the instruction, so forwarding cannot explain it.
3. **byte0's HIGH NIBBLE is the register field.** A dense byte0 sweep shows
   `byte0 = 0xN3` performs `r[N] = r[N] & 0xFFFF` — one register, used as **both source and
   destination** — for N = 0..10, verified by the 16-register dump identifying the exact
   narrowed seed each time. `db.json` models byte0 as a fixed 8-bit match `== 0x13`, so the
   register is invisible to an emitter (`db_defects :: DEF-0161-2`).

**Generation proof:** 11 of 16 generated `r[n] = r[n] & 0xFFFF` encodings pass against a
host-computed 16-register prediction. The 5 failures are the honest bound: **nibbles
0xB..0xF execute as a no-op**, so the field reaches r0..r10 only.

**Second carrier (`B2_ZEXT_SYNTH_R5`).** To make sure the inertness is a property of the
field and not of the `r1` anchor, the whole sweep was repeated on the **r5 form**
(`byte0 = 0x53`, which performs `r5 = r5 & 0xFFFF`), as its own gated pair. `src_reg` is
inert over all 128 values there too, `src_flag` over both, and `subform` / `extend` give
**the same accept-rules** (`(v & 0xC7) == 0x00`, 8 of 256; `(v & 0x07) == 0x01`, 32 of 256).

So all four `db.json` fields reach emitter grade, and by the letter of the emittable rule
`mov_zext16` is emittable. **It should not be recorded that way until `DEF-0161-2` is
applied**, because an emitter using the committed descriptor can only ever produce the
`r1` form: the register selector is invisible to it. `analysis/field_verdicts.json` carries
that as an explicit `caveat` on the instruction rather than a bare `EMITTABLE: true`.

---

## 5. `ibfe`: the offset/width asymmetry reproduces on G17P under a strongly-live carrier

EXP-0154 reported its `ibfe.offset` / `ibfe.width` reproduction tests **INCONCLUSIVE**
because its seeds were `<= 127`. With a 32-bit stimulus in which every bit position is live:

| carrier | `offset` accepted | `width` accepted |
|---|---|---|
| `k_bfe` (`extract_bits(a,4,8)`) | `{4}` only; **32 of 64 values return a silent zero** | `{8, 40}` |
| `k_shr_const` (`a >> 5`) | `{5}` only; 32 silent zeros | `{0, 27..32, 59..63}` |
| synthesized | `{4}` only; 35 silent zeros | `{6..9, 38..41}` |

* **`offset` is LITERAL.** Only the one true offset works, and values 32..63 shift the field
  out entirely (silent zero) — exactly 32 of 64 in each carrier. The hardware does **not**
  implement NIR's offset-mod-32 masking.
* **`width` is MOD 32.** `k_bfe` accepts `8` **and `40 = 8 + 32`**. `k_shr_const` accepts
  `{0, 27..31}` and each of those `+ 32` — i.e. every width that, mod 32, is 0 or wide
  enough to reach the MSB from offset 5. Both patterns are exactly what mod-32 predicts and
  neither is consistent with a literal or a clamp-at-32 model.

This is a **third** confirmation (EXP-0139 on M4, EXP-0153 on G17P, and here on G17P in two
independent lowerings plus a synthesized carrier), now under a carrier where the fields are
strongly live rather than mostly zero.

---

## 6. `fspecial`: opened, and `db.json` has its operands mis-assigned

Eleven fields, never swept before. All eleven are now swept densely (byte+3 over its safe
region 0..191), in **three** independent carriers.

### 6.1 The operand model is wrong in `db.json` — and it is emitter-breaking

| byte | `db.json` says | **hardware says (G17P)** |
|---|---|---|
| byte+1 high nibble (`dst`) | destination GPR | **HW-TESTED INERT** over all 16 values, in both carriers; the result always lands in the same register |
| byte+3 (`src`) | source register, low bits | **DESTINATION** register, `(reg<<1)\|size`, `reg = v>>1` — destination map fits **26/26** |
| byte+5 (`src_ext`) | source register extension | **SOURCE** register, `reg<<2`, `reg = v>>2` (low two bits don't-care) — released-register map fits **56/56** |

Recovered two independent ways at once: the 16-register dump shows *which register is read*
(it is released to zero) and *which register receives the result*, and the **computed
rsqrt value** identifies the source register's seed exactly — e.g. `src_ext` 4..7 gives
`0.333333 = rsqrt(9.0) = rsqrt(seed[r1])`, 8..11 gives `2.0 = rsqrt(0.25) = rsqrt(seed[r2])`,
and so on through r14.

**Generation proof: 20/20.** `r_i = rsqrt(r_j)` for arbitrary `i, j` — encodings the
compiler never emitted — predicted host-side and executed correctly every time.

This also **explains EXP-0138's observations** without contradicting them: its byte+3 report
("only values 2 and 3 give the correct `rsqrt(4)=0.5`; 188 values silently return 0.0;
values 6 and 7 leave the poison intact") is exactly what a *destination* selector does in a
carrier whose store reads `r1`.

### 6.2 Emitter rules for the remaining nine fields

| field | rule | meaning |
|---|---|---|
| `fn_hi` (byte0 bit7) | 0 / 1 | **HW-confirmed by computed value:** at `fnclass&3 == 2`, `0 -> log2`, `1 -> exp2` |
| `fnclass` (byte+1 lo nibble) | `v & 3` | bits 2-3 **don't-care**. With byte0 `0xaf`: 1 -> rsqrt, 2 -> exp2. With `0x2f`: 0 -> rint, 1 -> rsqrt, 2 -> log2 |
| `src_cache` (byte+2) | `(v & 0x02) == 0x02` (natural carrier) | **carrier-dependent**: load-bearing when the operand comes straight from a `device_load`, inert in the synthesized carrier |
| `src_class` (byte+4) | `(v & 0x02) == 0x02` | one live bit; clearing it silently zeroes |
| `fnsel` (byte+6) | `(v & 0x99) == 0x90` | 16 of 256 accepted, **identical in all three carriers** |
| `precsel` (byte+7) | `(v & 0x64) == 0x40` | 32 of 256 in the natural carriers; the synthesized carrier is looser (`(v & 0x60) == 0x40`, bit 2 don't-care) |
| `roundmode` (byte+8) | `(v & 0x01) == 0x00` | **bit 0 set returns NaN for every input** — see 6.3 |
| `sched_flag` (byte+9) | any | HW-tested INERT over all 256 values in both carriers |
| `dst` (byte+1 hi) | any | HW-tested INERT (6.1) |

### 6.3 `roundmode` bit 0 returns NaN — and a bug in MY analysis nearly said otherwise

128 of 256 `roundmode` values (every odd one) produce **NaN in all 12 output lanes**, in
three independent carriers; all 128 even values reproduce the correct function to **>= 24
good mantissa bits**. `db.json` documents byte+8 as a round-mode enum plus a "reciprocal
precision flag"; on the rsqrt (`0xaf`) and log2 (`0x2f`) SFU datapaths only bit 0 is live and
it is a **do-not-emit** bit.

**Disclosed:** the first version of `analysis/fspecial_functions.py` classified those NaN
vectors as a "~1% low-precision estimate", because every `abs(nan - w) > tol` comparison is
False under IEEE semantics. The NaN guard is the fix; the claim above is the corrected
reading, and the wrong one never left this file. `analysis/precision.py` now counts
all-NaN cases explicitly.

---

## 7. `fspecial` byte+3 >= 192: the bounded negative, complete

**Observed (`raw/g17p_20260830_danger01`, 64 values x 3 attempts):**

* **45 of 64** values produced a genuine `command buffer failed: Caused GPU Hang Error
  (00000003:kIOGPUCommandBufferCallbackErrorHang)` — 27 once, 16 twice, 2 three times.
* **19 of 64 were never cleanly observed**: all three of their attempts came back
  `...ErrorInnocentVictim`. In a region where *every* value resets the device, a case's own
  neighbours swamp it. Those 19 are recorded `fault` by majority, but that record is
  victim-class and **must not be read as a property of the encoding**. They are listed by
  value in `analysis/field_verdicts.json :: _meta.danger_arm.values_NEVER_CLEANLY_OBSERVED`.
* **No value in 192..255 was ever observed to work** — 0 `ok`, 0 `wrong_value`,
  0 `silent_zero` across all 192 attempts.
* **0 watchdog hangs, no host wedge**, and the arm's unmutated baseline was `ok`
  immediately before.

Combined with the safe-region sweep (0..191 dense in three carriers, no `ErrorHang`
anywhere), the boundary is **exactly bit 7 of byte+3**, dense on both sides — with the
caveat above on 19 of the 64 upper values, and with EXP-0138's independent M4 evidence
(60 reproducible faults across 192..255, plus three watchdog hangs at 192/193/194) covering
the same region.

> **Driver rule: never emit `fspecial` byte+3 with bit 7 set.** Under the corrected operand
> model of 6.1 that byte is the *destination* register selector, so the rule reads: the
> destination field's bit 7 must be clear — destination registers reachable through this
> field are `r0..r95` (`v <= 191`, `reg = v>>1`).

**Deviation from a pre-registered safety rule, disclosed.** The pre-registration armed a
stop rule of "two genuine hangs end the arm". **It never fired anywhere in this
experiment**, because the implementation keyed on the runner's **watchdog** `HANG` status
while every genuine hang here came back as a *contained* `CMDBUF_ERROR` carrying the OS's
`ErrorHang` classification. Consequences, both disclosed in section 8: the danger arm ran
all 64 values instead of stopping after two, and — the larger cost — the
`E2_FSPEC_EST_RCP` arm produced roughly 300 `ErrorHang`s **per run** across three runs
without ever tripping the rule. `harness/run.py` now classifies a genuine hang as
"watchdog wedge **or** an attempt whose OS error string contains `ErrorHang`"; the fix is
committed but the runs above were made before it.

---

## 8. Process integrity, concurrency, and what it cost

### 8.1 The device impact this experiment caused — stated plainly

| run | cases | contained `ErrorHang` attempts | victim-class attempts |
|---|---|---|---|
| `run01` (main, forward) | 11,942 | 221 | 125 |
| `run02` (main, reverse) | 11,942 | 154 | 159 |
| `supp01` (RETAINED, superseded) | 1,952 | 435 | 841 |
| `supp02` (2nd-carrier, forward) | 1,952 | 296 | 624 |
| `supp03` (2nd-carrier, reverse) | 1,952 | 357 | 867 |
| `danger01` | 65 | 65 | 127 |
| `adj01` (5x re-runs) | 60 | 43 | 54 |
| `gen01`/`gen02`/`gen03` | 191 | **0** | **0** |
| **total** | **30,056** | **1,571** | **2,797** |

**`hang` as an outcome (watchdog wedge, host unresponsive) is 0 everywhere.** But 1,571
command buffers came back with the OS's own `kIOGPUCommandBufferCallbackErrorHang`, each of
which resets the device and discards other agents' in-flight work. Two arms dominate:
`E2_FSPEC_EST_RCP` (~300 per run — the precise-reciprocal lowering is fragile under
mutation) and `G_FSPEC_DANGER` (65, by construction). This is the honest cost of the
experiment and it is larger than it should have been; the stop-rule bug in section 7 is why.
**A successor re-running the `fspecial_est` arms should expect to reset the device several
hundred times and should say so in `PROGRESS.md` first.**

### 8.2 Concurrency
This experiment did **not** run alone. Sibling GPU experiments were live on the neo
throughout (a `harness/run.py --run-id g17p_run03` from another agent was observed
mid-chain, among others). Despite that, the main gated pair lost only **175 of 11,942**
cases to victim-class failures and disagreed on **13**; `ok` came out **identical at 3,531
in both runs** on a matrix executed in opposite arm order. The supplementary pair's much
higher victim rate (624 / 867 attempts) is **self-inflicted**, not sibling load: its own
`E2_FSPEC_EST_RCP` hangs are what its later cases were victims of. Its `ok` counts still
agree to one case (856 vs 857).

### 8.3 A retained, superseded run
`raw/g17p_20260830_supp01` was launched in the background and then overlapped by my own
`danger01` arm. It is **retained exactly as it stopped**, is used for no verdict, and was
replaced by a fresh gated pair under new ids (`supp02`/`supp03`) rather than being topped up
or deleted. (Its victim rate turned out to be in line with the clean pair, so the overlap
was not the dominant contaminant — but the run was superseded on the strength of the design
error, not of its numbers.)

### 8.4 Fault adjudication (FIELD-SWEEP-PROTOCOL §7A)
308 cases had both gated runs agreeing on `fault`. Re-running all of them 5x would mean
~1,540 more dispatches, a large share of them device-resetting `ErrorHang`s. **No field
verdict in `analysis/field_verdicts.json` rests on a `fault` classification** — every
accept-rule is an `ok` set — so a **stratified sample of 60 across all 12 (arm, field)
strata** was adjudicated instead, 5x each, in a dedicated process:

* **58 of 60 confirmed**; **2 were not faults at all** (`B_ZEXT_SYNTH.subform` values 62 and
  118, both `wrong_value` on re-run) — a **3.3%** unlocked-run false-fault rate, the same
  phenomenon EXP-0153 documented, at a much lower rate here.
* Both corrections are applied to the gated outcomes before the verdicts are computed.
* The proportionality argument, and the fact that it is a sample, are recorded in
  `analysis/adjudication.json` and in `harness/adjudicate.py --sample`'s own help text.

### 8.5 Other integrity notes
* **Poisoned read-back.** Every dispatch reads back a buffer pre-filled with
  `0xDEADBEEF + i`, so an unwritten word identifies itself positionally and a suspect case
  can be settled offline from the committed digest.
* **A defect in MY harness, found before the gated runs and reported as a hardware fact.**
  The first smoke run delivered only 10 of 15 seeds. `harness/pilot_seed.py` (8 controlled
  variants) isolated it: **a `device_store`'s data-register read is not interlocked against
  a pending `device_load` on G17P** — the first ~5 stores after a load wave read the
  register's pre-load value, and the effect follows the STORE order, not the load order.
  `db.json`'s `scoreboard_model` claims ">= 20 loads outstanding, all consumed correctly";
  that is true for ALU consumers and false for a `device_store` consumer
  (`db_defects :: DEF-0161-5`).
* **A bug in MY analysis, found and disclosed.** 128 NaN output vectors were briefly
  classified as a "~1% low-precision estimate" because IEEE makes every `abs(nan - w) > tol`
  comparison False. Corrected reading in section 6.3; the wrong one never left this file.
* **A promotion my own rule would have made, and I overrode.** `fspecial_est.srcA` and
  `.subop` are inert across all 256 values in *two* carriers, which mechanically qualifies
  as "inert confirmed in two independent carriers". Both carriers are precise
  Newton-Raphson lowerings, and NR converges from a wrong seed — so they share the confound
  and are one observation, not two. Both are recorded `untested` with the reason
  (`CONFOUNDED_INERT` in `analysis/verdicts.py`); their prior M4 labels stand untouched.
  `ibfe.sign_ext` is held back for the same kind of reason: `db.json`'s own model says
  signed extract needs this bit **and** a `srcC_flags` change, and only the bit was swept.
* **Analysis is pinned to `work/frozen/`**, a sha256-verified copy of the exact
  `db.json` / `isadb.py` / `validation.json` the hardware ran against, because the repo
  host's `tools/agx-isa` drifts while sibling experiments land.
* `db.json`, `validation.json`, `docs/` and `PROVENANCE.md` were **not edited**, and nothing
  was committed.

## 9. What is NOT claimed

* **`mov_zext16` and `fspecial` are emittable only after the `db.json` fix.** Every field is
  at emitter grade, but the committed descriptors would make an emitter write the wrong
  register without faulting (`DEF-0161-1`, `DEF-0161-2`). Recorded as a `caveat` on the
  instruction, not as a bare `EMITTABLE: true`.
* **`fspecial_est.srcA` and `.subop` are not promoted from this experiment**, and neither is
  `ibfe.sign_ext` — see section 8.5. Their prior labels stand untouched; these are
  statements about our carriers, not retractions. `fspecial_est` still reaches "emittable",
  but only by combining this experiment's G17P `b4`/`b5` with a **prior M4-target** label
  for `subop`; `analysis/field_verdicts.json` records that dependency explicitly under
  `fields_at_grade_only_via_a_NON_G17P_prior_label`.
* **The round-family round-mode enum** (`0` nearest / `2` floor / `4` ceil / `6` trunc) is a
  claim about the DIRECT round family, not about byte+8 in general. An arm to test it by
  computed value on a `floor` carrier (`D4_FSPEC_FLOOR`, 788 cases) is **built and committed
  in `harness/cases.py :: SUPP2_ARMS` but was NOT RUN**: after 1,571 device resets (section
  8.1) the proportionate call was to stop adding GPU load for a nice-to-have refinement of a
  field that is already `hardware-run` from three carriers. A successor can run it with
  `harness/run.py --supp2`.
* **Everything here is the compute stage.** No fragment, texture or varying carrier was used.
* **`fspecial` byte+3 192..255 rests on one genuine observation per value** (plus 63 other
  values agreeing, plus EXP-0138's independent M4 evidence). It was not re-run, because
  each case resets the device for every other agent and a second pass buys little against
  that cost.

---

## 10. Verdict

**SUBSTANTIAL, and the specific question the dispatch asked is answered YES.**

**The `carry_gen` carrier fix worked.** EXP-0154's arm was killed by a seed, not by the
hardware: with `mov_imm`'s seven-bit immediate the lifted 64-bit add could never carry, so
the instruction was unobservable whatever its encoding. Seeding the registers by
`device_load` from an authored buffer makes both pre-registered falsifiers fire in both
carriers, and the instruction maps completely.

**All nine of EXP-0154's withdrawn upgrades are now earned** — five `carry_gen` fields
outright, `mov_zext16.subform`/`.extend` outright, and `mov_zext16.src_reg`/`.src_flag` as
HW-tested inert in two independent register forms. That last pair is earned in the opposite
sense to the one anyone expected: they are **not** source-register selectors, and the real
register field is byte0's high nibble, which `db.json` models as part of a fixed match.

**Four instructions reach emitter grade on G17P** — `carry_gen`, `fspecial`, `fspecial_est`,
`mov_zext16` — and `ibfe`'s offset-literal / width-mod-32 asymmetry is confirmed a third
time, now in a carrier where both fields are strongly live.

**Two of those four must not be promoted until `db.json` is corrected.** The two results
most likely to change what a downstream emitter writes are **`fspecial`'s destination and
source bytes being swapped relative to the descriptor** (`DEF-0161-1`; byte+3 is the
destination, byte+5 the source, byte+1's high nibble is inert) and **`mov_zext16`'s register
living in byte0's high nibble** (`DEF-0161-2`). Both are cases where the committed answer
would compile, run, fault nothing, and write the wrong register.

**`fspecial`'s dangerous region is closed as a bounded negative — and bounded honestly**:
45 of the 64 values in 192..255 produce a genuine contained
`kIOGPUCommandBufferCallbackErrorHang`, 19 were swamped by their own neighbours' resets and
were never cleanly observed, and **none of the 64 ever worked**, against 0..191 dense and
clean in three carriers. The boundary is exactly bit 7. Under the corrected operand model
that reads: **the destination-register field reaches r0..r95, and bit 7 must never be set.**

The weakest parts of this experiment are named rather than smoothed over: a pre-registered
stop rule that never fired because it watched the wrong signal, 1,571 device resets that
cost every other agent on the machine, a sampled rather than exhaustive fault adjudication,
and three fields held back from a promotion the mechanical rule would have granted.

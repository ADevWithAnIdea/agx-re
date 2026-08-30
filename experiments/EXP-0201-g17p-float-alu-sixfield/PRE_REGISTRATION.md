# EXP-0201 — PRE-REGISTRATION (frozen before any build or device run)

**Frozen:** 2026-08-30, before the first `clang`/`shdump` invocation and before any byte was
dispatched. **Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores,
macOS 26.6), `192.168.170.254`. **Nothing runs on the M4**; the M4 hosts the repo and analysis only.

**Repo revision at freeze:** recorded in `CAPTURE_CONTRACT.json` → `repo.revision` (+ dirty flag).
Per `SUBAGENT_BRIEF.md`, captures are gated on the **authored blob hashes**, never on live `HEAD`.

---

## 1. The question

Six fields across five float-ALU instructions each block their instruction from being *emittable*.
Can an emitter **choose** each field's value and get documented behaviour on G17P?

| # | instruction | field | span (start,width) | prior state in `tools/agx-isa/validation.json` |
|---|---|---|---|---|
| F1 | `falu3` | `op` | 16, 8 | `untested`; EXP-0160 dispatched 256, 428 moved, **withheld UNSTABLE by EXP-0189** |
| F2 | `falu3_ext` | `op` | 16, 8 | `untested`; EXP-0160 dispatched 256, 450 moved, **withheld UNSTABLE by EXP-0189** |
| F3 | `fspecial_est` | `srcA` | 8, 8 | `untested`; EXP-0171 cited, **withheld UNVERIFIABLE (`no-field-records`)** |
| F4 | `falu3_srcmod12` | `opsel` | 16, 3 | `untested`; EXP-0154 sampled 7 of 8; **aliased sweep hazard, see §4** |
| F5 | `falu3_srcmod12` | `ctrl` | 32, 7 | `untested`; EXP-0154 dispatched 128 |
| F6 | `copysign` | `operands` | 24, 8 | `untested`; EXP-0184 measured LIVE, **withheld UNSTABLE by EXP-0189** |
| F6b | `copysign` | `_instruction` | — | `corpus-correlation` (EXP-M4-13, M4, never HW-splice-isolated) |

F1, F2 and F6 carry a named debt: **their prior verdicts were degraded by concurrent GPU load and
need a QUIET-MACHINE confirmation** (`FIELD-SWEEP-PROTOCOL.md` §7, "The exception, found the hard
way"). §7 of this document is that protocol.

## 2. Hypotheses, each with its refuter

**H1 (`falu3.op`) — byte+2 is a live operation selector whose low 3 bits choose the arithmetic
function.** Pre-registered from EXP-0160's published map (`db.json` `falu3.op.note`): low3
`0 = a+b`, `1 = a*b`, `2 = a*b+a`, `4 = -b`, `5 = 0`, `6 = a*b+c`, `7 = fault`; low3 `3` unmapped.
*Predicted observation:* over 256 values on a compiled `fma(a,b,c)` carrier, the observed 8-lane
output vector equals the host-computed vector for the function selected by `v & 7`, at every value
where the outcome is `ok`/`wrong_value`, and every value with `(v & 7) == 7` is a contained fault.
*Refuter R1a:* the observed vector for some `v & 7` class does not match **any** member of the
host function library (the published map is incomplete or wrong on G17P).
*Refuter R1b:* the observable does not move at all across 256 values (field inert on this carrier)
— then, per §9 of `FIELD-SWEEP-PROTOCOL.md`, the field is **not promoted**.
*Refuter R1c:* cross-run per-value agreement < 99 % on a quiet machine — the field is unstable and
stays `untested`, and this experiment says so rather than reporting a contaminated figure.

**H2 (`falu3_ext.op`)** — identical to H1 on the 10-byte saturating form, with the oracle passed
through `clamp(x, 0, 1)`. Same refuters. The saturate inputs are chosen in §5 so that the six
predicted functions remain **distinct 8-lane vectors after clamping** — a saturating carrier whose
predictions all clamp to the same vector would be a constant oracle and is explicitly avoided.

**H3 (`fspecial_est.srcA`) — byte+1 is a live source-operand descriptor** of the
`(reg << 1) | is32` shape `db.json` documents for `falu2`.
*Predicted observation:* the compiled value and its inert-bit aliases reproduce the host-computed
correctly-rounded `rsqrt`/`rcp`/`sqrt`; other values do not (silent zero or a different value).
*Refuter R3a:* all 256 values reproduce the oracle → the byte is inert on every carrier → not
promoted (§9 asymmetry: a false *inert* claim fails silently forever).
*Refuter R3b:* the accept set is not closed under the modelled inert bits, i.e. the descriptor
model is wrong — a first-class `db_defects` result.
*Detection-power control on the same occurrence:* `fspecial_est.subop` (24, 8), already
`hardware-run` on G17P (EXP-0161/0171). **If the control does not move on an arm, that arm cannot
support an inert verdict for `srcA`** (`FIELD-SWEEP-PROTOCOL.md` §5a).

**H4 (`falu3_srcmod12.opsel`) — the modelled 3-bit field overlaps its own descriptor's `match`
constraint, so only 2 of its 3 bits are free within this mnemonic.** `db.json` pins `[17,1,1]`,
and bit 17 is `opsel`'s middle bit.
*Predicted observation:* values `{2,3,6,7}` keep the bytes decoding as `falu3_srcmod12`; values
`{0,1,4,5}` clear bit 17 and the pinned tokenizer re-labels the bytes `falu_srcmod12b`.
*Refuter R4a:* the tokenizer still reports `falu3_srcmod12` for a bit-17-clear value → the overlap
model is wrong.
*Refuter R4b:* the four in-mnemonic values produce an identical observable → inert → not promoted.
**Any movement produced by a value that re-labels the instruction is NOT counted as movement of
this field** (the trap that withdrew two fields on 2026-08-30).

**H5 (`falu3_srcmod12.ctrl`) — byte+4 bits 0..6, whose low 2 bits are the 0x09-group instruction
LENGTH selector** (EXP-0119/EXP-0138 on M4).
*Predicted observation:* over 128 values, the accept set is confined to values whose low 2 bits
keep the 12-byte length (`v & 3 == 3`); values that re-length the instruction change the
tokenization of everything after it and produce wrong values or faults.
*Refuter R5a:* the accept set is not explained by the low-2-bit length rule.
*Refuter R5b:* nothing moves across all 128 values → inert → not promoted.

**H6 (`copysign.operands`) — a live operand descriptor, `(reg << 1) | size`, with bit 0 and bit 7
inert**, reproducing EXP-0184's G17P finding under a quiet machine and a deterministic payload.
*Predicted observation:* the accept set is exactly `{0x00, 0x01, 0x80, 0x81}`; the partition over
256 values reproduces EXP-0184's four groups.
*Refuter R6a:* a different accept set, or agreement < 99 % → EXP-0184's result does not replicate
and this experiment reports that, not a promotion.
*Refuter R6b:* nothing moves → the M4 `INERT` reading of EXP-0138 is the correct one on G17P too.

> **AMENDMENT A1 (pre-build, 2026-08-30), on coordinator intel about EXP-0138's committed raw.**
> A re-derivation of `EXP-0138-m4-emit-falu` shows that sweep already dispatched **256 legal
> values and 256 distinct encodings** of this exact field — it was **not** aliased — and still
> produced **V = 1 distinct valid payload** and **1 distinct oracle**. That is the Case-C shape:
> the values ran legally, faulted nowhere, reproduced perfectly, and were *indistinguishable*.
> **The binding constraint on this arm is the ORACLE, not the range.** Dispatching 256 values
> again against a constant oracle would reproduce the same non-result.
>
> So H6 is tested with a **host-computed candidate function library** rather than a single
> expected vector, and with inputs chosen so operand *role* is observable:
>
> * `b` carries **`-0.0`** in one lane (a sign source whose sign is negative but whose value is
>   zero — the case where a sign-copy reading the wrong operand becomes visible) and the two
>   vectors are **asymmetric**, so `copysign(a,b)`, `copysign(b,a)`, `a`, `b`, `|a|`, `|b|`,
>   `-a`, `-b`, `-|a|`, `-|b|`, `0`, `a*b`, `a+b` are **thirteen pairwise-distinct 8-lane
>   vectors**, asserted on the host before the contract is frozen. Two lanes deliberately have
>   `sign(a) == sign(b)` so that `copysign(a,b) != -a`, which the naive "all signs opposite"
>   choice would have collided.
> * A **`cs_swap` carrier computes `copysign(b[t], a[t])`** — the same instruction with the
>   operand roles exchanged. That is the dimension `operands` is modelled to control, so the two
>   carriers are not "one carrier twice" (§9 condition 1).
> * Every case records `observed_fn` = **which library member the hardware actually produced**,
>   by name. A value that yields `copysign(b,a)` or `|a|` is then a *decoded operand semantic*,
>   not merely "moved".
> * The per-value oracle carries the model's real per-value content: the predicted vector where
>   the model predicts one, and otherwise the pre-registered **equivalence class**
>   `v & 0x7E` (H6 asserts bits 0 and 7 are inert, i.e. `f(v) == f(v ^ 0x81)` for every `v`) —
>   a falsifiable per-value prediction, not a constant.
>
> **If, with a discriminating oracle in place, the field still shows V = 1, that is the result and
> it is reported as such** — a much stronger negative than the existing one. This experiment does
> not stretch to make it move.

**Case-C guard, applied to ALL six fields (AMENDMENT A1).** `tools/agx-isa/wave_audit.py` is run
by this experiment against its own `raw/` **before** any verdict is reported, and its output is
committed to `analysis/wave_audit.txt`. Every field verdict records **V (distinct valid payloads)**,
**L (legal values)**, **distinct oracles**, **distinct encodings dispatched**, and hard outcomes
counted **separately** from valid payloads. A field with `V <= 1` over many legal values is
**NOT PROMOTED** regardless of any other statistic: it ran legally and was indistinguishable.
Accordingly every arm's oracle below is a **per-value host-computed prediction**, never a constant:
`falu3.op`/`falu3_ext.op` predict one of seven named arithmetic functions by `v & 7`;
`falu3_srcmod12.opsel` predicts by the descriptor's own `opsel` enum; `falu3_srcmod12.ctrl`
predicts the instruction length `6 + 2*(v & 3)` and hence whether the frame survives;
`fspecial_est.srcA` and `copysign.operands` predict the inert-bit equivalence class plus a named
library member.

**H6b (`copysign._instruction`) — the 4-byte word can be GENERATED from `db.json`'s descriptor
alone.** The descriptor pins bits 0..23 by `match` and leaves one field, so the emitter's word is
`match ∪ operands`. *Predicted observation:* a word built **only** from the pinned descriptor's
`match` list plus a chosen `operands` value, spliced over the located occurrence, executes and
reproduces the host oracle. *Refuter:* the generated word does not reproduce the oracle, or is not
byte-identical to what a from-scratch build predicts — the descriptor under-specifies the
instruction.

> **AMENDMENT A2 (pre-build, 2026-08-30), on coordinator intel about the four remaining refusals.**
> The four documented refusals failed in **three distinct ways**, and each gets a different fix:
>
> 1. **`falu3.op` and `falu3_ext.op` are UNSTABLE, not inert** — 428 and 450 observations moved,
>    over **one arm each**. Liveness is not in question and **more values will not help**. The two
>    deficiencies are (a) a single arm and (b) cross-run instability, which is the quiet-machine
>    debt. Fixes, frozen: **≥ 3 independent arms per field** (two carriers × every located
>    occurrence, each arm analysed separately, never averaged), and §8's measured quiet window.
>    **If no quiet window is obtained the cross-run figure is reported as `CONTAMINATED`, not as a
>    clean refutation** — a contaminated 97 % reads as a refutation when it is only noise, and
>    these two fields have already been destroyed once by exactly that.
> 2. **`fspecial_est.srcA` is a DETECTION-POWER problem, not an instability one** — 256 values over
>    **4 arms** with **1 observation moved**. One moved observation in ~1024 is more likely a stray
>    than a semantic and **nothing is built on it**. This is treated as a *carrier* question: what
>    dimension does `srcA` control on a special-function estimate, and can any arm express it?
>    Frozen answer: the carriers keep a **second live float of a very different magnitude**
>    (`b[t]`, stored after the estimate so it is live across it) so that an estimate seeded from
>    the wrong register cannot be rescued by the Newton–Raphson refinement, and each arm carries
>    the `subop` detection-power control at the *same* occurrence. **If no arm's control fires,
>    the field is reported as having no arm with detection power — not as inert.**
> 3. **`falu3_srcmod12.opsel` — the aliased sweep is not re-run.** The prior record is
>    "4 values, 3 payloads, 3 oracles | same aliasing". Frozen mitigation, and it runs **before**
>    dispatch, not only in analysis: `analysis/gen_arms.py` computes the mutated bytes for every
>    value of every arm on the host and **refuses to emit the arm** unless (a) the byte strings are
>    pairwise distinct and (b) every XOR against the baseline is a subset of the field's own
>    `start`/`width` mask. `distinct_bytes < values_dispatched` is a **hard stop**, not a note.
> 4. **`falu3_srcmod12.ctrl` carries no documented refusal** — open ground, swept dense.

## 3. Variables

**Independent:** the value of exactly ONE field of ONE located instruction occurrence, written by
direct bit-splice into the compiled `_agc.main` of our own MSL.
**Controlled:** carrier source, dispatch shape (`grid`/`tg`), input files, output poison, the
persistent runner process, the pinned `db.json`/`isadb.py`/`agxparse.py`/`persistrun.py`/`shdump.m`.
**Dependent:** the 8-lane read-back vector, the integrity sentinel, the poison tail, the OS
command-buffer status/fault string, and the pinned tokenizer's opinion of the mutated bytes.

## 4. The aliasing hazard, and how this experiment does not repeat it

`falu3_srcmod12.opsel` is one of seven fields a prior experiment DECLINED to promote, and its
sweep was **aliased**: an assembler that ORs `match` bits after writing the field cannot clear
bit 17, so nominal `opsel = 4` and `opsel = 6` assemble to **identical bytes** and the oracle
described a program that never ran.

Mitigations, frozen:

1. **No assembler is used to build a case.** Every case is produced by
   `patch_instr()` — a direct little-endian bit-replace over the instruction's own bytes — so a
   value written to a `match`-pinned bit really lands.
2. **A machine-checked non-aliasing assertion, per case, in `run.py`:** for each arm, the
   mutated instruction bytes are recorded, and `analysis/verdicts.py` asserts (a) all dispatched
   values within an arm produce **pairwise distinct** byte strings, and (b) for every value the
   XOR against the arm's baseline bytes is a **subset of the field's own bit mask**
   (`start`/`width` from the pinned `db.json`). A violation fails the arm; it is not analysed.
3. **`distinct_bytes` is counted from the distinct `bytes` strings in `raw/`**, never from the
   dispatched value count, and is reported in `analysis/field_verdicts.json` for every field.
4. **The pinned tokenizer's mnemonic for the MUTATED bytes is recorded on every case**, and
   movement on a case whose mnemonic differs from the arm's target is excluded from the field's
   `moved` count and reported separately.

## 5. Carriers, inputs and the DISCRIMINATING oracle

All carriers are authored MSL in `kernels/`, compiled on the device with `--no-fast-math`, 8 lanes,
`grid = tg = 8`, output buffer 16 words. **Buffer 0 is pre-filled with POISON(i) = 0xDEADBEEF + i**
before every dispatch (instrument 1). `out[8]` is an **integrity sentinel** (`7.5f` / `12345`)
written **first**, through a path independent of the instruction under test (instrument 2).
`out[9..15]` are never stored to and must stay poison. The OS fault-classification string is
recorded on every non-`ok` case (instrument 3).

**The oracle is a host-computed FUNCTION LIBRARY, not a constant.** For the two `op` fields the
predicted output *differs per predicted operation class*, so the oracle takes seven distinct 8-lane
values across the sweep and a value that produces the wrong function is detected as such. Inputs
for the plain-`fma` carriers:

```
a = [ 3.0,  5.0,  7.0, 11.0,  2.5, -4.0,  6.0,  1.5]
b = [ 2.0, -3.0,  4.0,  0.5,  8.0,  1.25, -2.0, 9.0]
c = [10.0, 20.0, -5.0,  3.0,  7.0, -1.5, 12.0,  0.25]
```

chosen so that `a+b`, `a*b`, `a*b+a`, `a*b+c`, `a-b`, `-b`, `b`, `a`, `c` and `0` are **ten
pairwise-distinct 8-lane vectors**, and none is the all-zero vector except the constant-zero
function itself. `analysis/oracle_check.py` asserts the pairwise distinctness on the host **before
the contract is frozen**; if any two collide the inputs are changed and re-frozen.

For the saturating carrier the same library is passed through `clamp(x, 0, 1)` and the inputs are

```
a = [0.25,  0.5,   0.75, 0.125, 0.375, 0.625, 0.875, 0.0625]
b = [-0.5,  0.25, -0.125, 0.75, -0.625, 0.375, -0.9,  0.5]
c = [0.6,   0.1,   0.4,  0.05,  0.8,   0.2,   0.3,   0.7]
```

with the same host-side distinctness assertion **after clamping**.

For `fspecial_est` the argument vector is
`a = [4.0, 0.25, 16.0, 100.0, 0.0625, 2.0, 9.0, 1.5625]`, chosen so every lane's
`rsqrt`/`rcp`/`sqrt` is exactly representable or well-separated, and **never zero**.

## 6. Coverage, frozen

| field | values dispatched | rule |
|---|---|---|
| `falu3.op` | 0..255, **all 256** | §3 of the protocol: `w ≤ 8` → dense |
| `falu3_ext.op` | 0..255, all 256 | dense |
| `fspecial_est.srcA` | 0..255, all 256 | dense |
| `falu3_srcmod12.opsel` | 0..7, all 8 | dense |
| `falu3_srcmod12.ctrl` | 0..127, all 128 | dense |
| `copysign.operands` | 0..255, all 256 | dense |

**No hang budget and no abort path** (`FIELD-SWEEP-PROTOCOL.md` §3c: a per-field budget cannot
characterise a contiguous hazard — it guarantees the region is never mapped). Every value in every
arm is dispatched in every gated run.

**Declared hazard, as a courtesy (protocol §7):** `falu3.op` values with `(v & 7) == 7` are a
**reproducible contained fault** per EXP-0160 (32 of 256 values). They are dispatched anyway. This
is logged in `PROGRESS.md` before the first gated run.

**Controls, declared before the run:**

* **C1 — detection power, per arm.** Each target arm carries a `_live_control` arm at the *same*
  occurrence on a field already known live: `falu3.srcA` for F1/F2, `fspecial_est.subop` for F3,
  `falu3_srcmod12.srcA_reg` for F4/F5, `copysign` byte+1 for F6. An arm whose control does not move
  **cannot support an INERT verdict** and is reported as lacking detection power.
* **C2 — falsifier, pre-registered to FAIL.** On every carrier, one arm splices a value that
  *must* break the program: `falu3.op = 0x05` (the published "constant 0" op) and
  `copysign` byte+0 = 0x00. If a falsifier does not change the observable, the instrument is blind
  and the whole carrier's results are reported as such.
* **C3 — the gate can return NO.** `analysis/verdicts.py` is required to produce at least one
  `NOT PROMOTED` verdict among the six, or the gate itself is reported as suspect. (It is not
  tuned to produce one; this is a check on the criterion, not on the data.)
* **C4 — width-1 arithmetic.** The promotion rule is `moved >= 2 * disagree AND moved > 0`,
  **never** `moved >= 2 * max(disagree, 1)`. `analysis/verdicts.py` contains a unit assertion that
  a synthetic width-1 field with `moved = 1, disagree = 0` **passes**.
* **C5 — a fault is not movement.** A case whose outcome is `fault`/`hang`/`measurement_failure`
  is **excluded** from `moved`; movement is counted only between cases that produced an actual
  read-back. A trap already paid for: a gate that counted a GPU fault as movement.
* **C6 — an undecodable token is not movement.** Our own disassembler failing to decode the
  mutated bytes is recorded and **never** counted as hardware movement.

## 7. The promotion gate (frozen; implemented only by `analysis/verdicts.py`)

A field is promoted to `hardware-run` **only if all of the following hold**:

1. **≥ 2 gated runs** of the full frozen arm set completed, run ids never reused.
2. **Per-value cross-run agreement ≥ 99.0 %** on the deterministic observation signature, over the
   values common to both runs, on the arm being promoted.
3. **`moved >= 2 * disagree` AND `moved > 0`**, where `moved` counts values whose deterministic
   signature differs from the arm's own baseline signature, over cases that produced a read-back.
4. **`distinct_bytes >= 2`** on the arm, with the §4 non-aliasing assertion passing.
5. **No case counted as `moved` had a mutated-token mnemonic different from the arm's target.**
6. **The arm's `_live_control` moved** (detection power demonstrated) **or** the field itself moved
   (a field that moves needs no proof that the arm can see movement).
7. **The sentinel was present** on every case counted, and the arm's falsifier fired.

A field that moves but fails (2) is reported `untested` with an explicit `UNSTABLE` note and the
measured agreement. A field that does not move is reported **NOT PROMOTED** with the four §9
conditions it would have to meet; per `FIELD-SWEEP-PROTOCOL.md` §9 an inert field is **not**
promoted, because a false *inert* claim fails silently forever.

**The deterministic observation signature.** `observed` in `raw/` contains **only deterministic
content**: the 8 read-back words as `u32`, the sentinel word, the poison tail, the unwritten list
and the command-buffer status. **`gputime_ns` and retry counts are recorded OUTSIDE `observed`**,
at the top level of the record. This is deliberate and is a defect this experiment is correcting:
EXP-0189's cross-run indexer hashes the **whole** `observed` dict, and EXP-0184's records carry
`gputime_ns` **inside** it, so a nanosecond timer alone can drive measured agreement from 100 % to
39 %. See `RESULTS.md` §"DEF-0201-1".

## 8. The quiet-window protocol for F1, F2 and F6 (binding)

Concurrency for *sweeps* is unrestricted and stays so. **A confirmation run is the exception.**
For the two `op` fields and `copysign.operands`:

1. `harness/gpuwatch.py` samples the device process table (`agxrun*`, `shdump`, `rendersweep`,
   `gfrun`, `MTLCompilerService`) **every 2 s for the whole duration of each gated run**, writing
   `raw/<run_id>/gpuwatch.jsonl`. Quietness is a **measurement**, not a claim.
2. A run is **QUIET** iff no sample during it observed a foreign GPU-runner process. Otherwise it
   is **BUSY**, and every verdict derived from it is labelled so.
3. If no quiet window can be obtained, the result is reported with the measured concurrency and
   the field is **not** promoted on a busy-machine confirmation. Per §7 of the protocol, the
   fallback is EXP-0160's evidence-validity filter: two agreeing clean dumps win outright, because
   *contamination can destroy an observation but never fabricate a coherent one* — and the
   `RESULTS.md` must say which of the two routes was taken.

## 9. Known confounders

* **Compiler transformation.** The carrier's `_agc.main` may not contain the target instruction at
  all, or may contain it on a path the read-back cannot observe. Handled by a census + pilot phase
  (declared here as exploratory and **not** gated evidence) that locates every occurrence and keeps
  only those whose `_live_control` fires.
* **Instruction re-framing.** `ctrl`/`ctrl_len` low bits re-length the instruction, so a sweep can
  move the observable by changing where the *next* instruction starts. Recorded via the per-case
  token and reported as a framing effect, not as operand semantics.
* **Release-on-read.** `op` bit 4 is published as a srcB release flag; its effect is only visible
  if a later instruction reads that register. The chained carriers exist for this reason, and a
  null result on the unchained carrier is not evidence of inertness.
* **Sibling contamination.** `kIOGPUCommandBufferCallbackErrorInnocentVictim` is retried first;
  §8 handles the signatures that carry no victim string.
* **Buffer aliasing between arms.** Each dispatch re-binds a freshly poisoned buffer 0.
* **A dispatch that reports OK and writes nothing** is `invalid_run`, re-run, never scored.

## 10. Environment and timeouts (frozen)

| | |
|---|---|
| Device | A18 Pro / G17P, `192.168.170.254`, ssh user `user`, password via `SSHPASS` only |
| Remote workdir | `~/agxre/EXP-0201/` |
| Per-request watchdog | 8.0 s |
| Confirm attempts on any non-OK | 3 (majority-of-3) |
| `InnocentVictim` retries | 3 |
| Canary (wrote-nothing) retries | 3 |
| Compile timeout | 600 s; `agxparse` 180 s; every ssh call wrapped in a `perl -e 'alarm N'` |
| Runner | `harness/saferunner201.py` — one reader thread per child, malformed ⇒ `measurement_failure` |

## 11. Raw record schema (append-only, one JSON object per case, flushed + fsync'd)

```json
{"carrier":"f3_fma","arm":"f3_fma#0/falu3.op","instr":"falu3","field":"op","value":30,
 "bytes":"09011e0581080200","off":123,"instr_len":8,"start":16,"width":8,
 "token":{"mnemonic":"falu3","op":"fma","length":8},
 "observed":{"status":"OK","vals_u32":[...],"sent_u32":...,"tail_u32":[...],
             "unwritten":[],"sentinel_ok":true,"tail_ok":true},
 "oracle":{"predicted_fn":"a*b+c","vals":[...]},
 "match":true,"outcome":"ok","role":"target","statuses":["OK"],
 "fault_classes":[],"innocent_retries":0,"gputime_ns":5749,"ts":1788000000.0}
```

`outcome ∈ ok | silent_zero | wrong_value | not_written | fault | hang | undecodable |
measurement_failure | invalid_run | nondeterministic`. Faults, hangs and rejections are **results**
and are kept.

## 12. Deliverables

`README.md`, this file, `CAPTURE_CONTRACT.json`, `RESULTS.md`, `manifest.json`, `PROGRESS.md`,
`harness/`, `kernels/`, `analysis/` (with `field_verdicts.json` keyed `<mnemonic>.<field>`, each
carrying `label`, `range`, `target: "G17P"`, `evidence`, `note`, `start`, `width`,
`values_dispatched`, `distinct_bytes`, `encodable_range`, `moved`, `disagree`, `agree_pct`), and
`raw/` (append-only). **`tools/agx-isa/`, `docs/` and `PROVENANCE.md` are NOT edited, and nothing
is committed** — the orchestrator owns those.

## 13. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/*.metal (authored by us) and their compiled _agc.main bytes
Apple binary introspection: NONE
Reproduction:          README.md "Reproduction"; run ids in raw/
Evidence:              raw/<run_id>/sweep.jsonl (append-only), CAPTURE_CONTRACT.json hashes
```

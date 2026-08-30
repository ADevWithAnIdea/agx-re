# EXP-0202 — PRE-REGISTRATION

**Written before any kernel was authored and before any device time.** The version frozen at
this point is preserved as `raw/prefreeze/PRE_REGISTRATION.v1.md`; the only later edit permitted
is §7's arm table, which is filled from the **pre-freeze census** (offsets and compiled field
values are facts about our own compiled code, not results), and every such amendment is recorded
in `PROGRESS.md` and preserved as a new `raw/prefreeze/CAPTURE_CONTRACT.vN.json`.

Repo revision pinned at pre-registration: **`f59821fe5e896b09a1bd33b41e7a9f1b7df6b4b4`** (16 files
dirty from sibling experiments). Per `SUBAGENT_BRIEF.md` the gate is on **authored blob hashes**,
not on `HEAD` — sibling experiments landing does not invalidate a capture.

---

## 1. Target and scope

Apple A18 Pro / **G17P**, `192.168.170.254`. Eight fields:

`irotate.operands` · `shift_amt_move.src_flag` · `ibitcount.cache` · `ibitcount.dst` ·
`iunary.b1` · `iunary.opsel` · `cvt_f2i.b9` · `cvt_f2i._instruction`

`_instruction` is not a bit-field; its claim is behavioural (§3.8) and it is scored by a separate
rule (§6.4).

---

## 2. What each field is believed to select, and therefore what dimension a carrier must span

This section is the heart of the experiment. `FIELD-SWEEP-PROTOCOL` §9 and `docs/isa/emit-worklist.md`
line 7: **a field that never moves is only promotable if the carriers differ in the dimension the
field controls. Two carriers identical in that dimension are ONE carrier.** So for every field the
dimension is named *first*, and the carrier set is designed to span it.

### 2.1 `shift_amt_move.src_flag` (bit 15 = byte+1 bit 7, width 1)

**Dimension: which REGISTER FILE supplies the staged shift/rotate amount.** `db.json` types the
byte as `src_reg` (bits 8..14) + `src_flag` (bit 15) with enum `0 = gpr`, `1 = uniform/class`,
inherited from the `reg_move_c0` compact-move layout and **never proven**.

EXP-0168's single arm was `SHIFTMOVE/gpr` — a synthesized register-dump carrier whose amount comes
from a GPR — crossed with 13 `src_reg` values. Its raw
(`EXP-0168/raw/g17p_20260830_run02/sweep.jsonl`, and again in `run03`) shows the two flag values
producing **byte-identical 16-register digests at every one of the 13 indices**. EXP-0168 scored
`moved = 22` and promoted; that 22 is `src_reg` moving, not `src_flag` — the classic co-variation
trap of `FIELD-SWEEP-PROTOCOL` §3(a). EXP-0189 re-derived it correctly as `0 moved`.

**Every one of those 13 samples is one point in the same file.** A carrier whose amount lives in
the GPR file cannot separate two files; if the flag is live, its effect is *which file index n is
read from*, and holding the file fixed makes the flag a no-op **by construction**.

**Carriers must therefore differ in where the amount comes from:**

* `sam_gpr` — `rotate(a[g], b[g])`: a per-thread device-loaded amount. Lives in a GPR.
* `sam_uni` — `rotate(a[g], sh)` with `constant uint& sh`: a **thread-invariant** amount. This is
  the operand class a compiler puts in the uniform file.
* `sam_shl_uni`, `sam_shr_uni` — the same thread-invariant amount driving `<<` and `>>` rather
  than a rotate, so the `kind` nibble differs too.
* `sam_uni2` — two *different* thread-invariant amounts in one kernel, so the uniform file holds
  two distinct known values at two distinct indices.

**Positive control in the same dimension (mandatory, §6.3):** `src_reg` — the **index within the
selected file** — swept **densely 0..127** on the same arm. If sweeping the index moves the
observable, the source operand is being read and its content reaches the output; the read path is
demonstrably live. An arm on which `src_reg` never moves has no detection power and is barred.

**The actual test is a PROFILE COMPARISON, not a two-value poke.** For each carrier, the observable
is recorded over all 128 `src_reg` values at `src_flag = 0` and again at `src_flag = 1`. If the two
files differ anywhere in 128 slots, the profiles differ.

**H1.** `src_flag` selects the source register file; the profile over `src_reg` at flag=0 differs
from the profile at flag=1 on at least one carrier.
**Expected if true.** At least one index where the two flag settings give different observables,
reproducibly in both gated runs.
**Refuter (pre-registered).** If, on **every** carrier whose `src_reg` control fires, the 128-index
profile at flag=0 is byte-identical to the profile at flag=1, H1 is refuted and the honest verdict
is that the bit produced **no observable difference over the full index space of two structurally
different amount sources** — recorded as such, **not rounded up to emitter grade** (§6.5).
**Second, independent line of evidence, taken at census time and free:** *what does the compiler
itself emit?* If any authored carrier compiles to `src_flag = 1`, the compiler demonstrates the
dimension the way EXP-0188's `if_push.scope` was demonstrated. If **no** kernel we can write emits
`src_flag = 1`, that is itself a first-class result and is reported.

### 2.2 `irotate.operands` (bits 24..63, width 40)

**Not an inertness problem — a stability and single-arm problem.** EXP-0189: *1276 values
dispatched over 1 arm, 2365 observations moved*, withheld **UNSTABLE**. It moves enormously.

**Two fixes, and neither is more values.**

1. **A quiet window.** `FIELD-SWEEP-PROTOCOL` §7's stated exception: a confirmation run on a busy
   machine manufactures faults (EXP-0160: `imad` v=186 `silent_zero` in both gated runs, `fault`
   3/5 unlocked; EXP-0158: 102 of 174 cases MIXED across five runs of byte-identical programs).
   `harness/gpuwatch.py` samples the process table every 2 s for the duration of both gated runs.
   **If the measured window is not quiet, the cross-run figure is reported CONTAMINATED and no
   promotion is made** — a contaminated 97 % looks like a refutation when it is only noise.
2. **A second arm.** Four carriers, each emitting a single-op immediate `irotate`
   (`27 01 56 ...`, 12 bytes) at a *different rotate amount*, so the arm set is not one program.

**H2.** `irotate.operands` is a live 40-bit operand blob whose per-byte accept sets reproduce
across two arms and two gated runs on a quiet machine.
**Refuter.** Cross-run agreement < 99 % per value on every arm, or `moved < 2 * disagree`.

**The coverage bar (`FIELD-SWEEP-PROTOCOL` §3.3, `w > 8`) has never been met for this field**, and
the current row says so: *"the 40-bit field was NEVER swept jointly and its max/max-1 were never
encoded."* This experiment dispatches, **jointly over the whole 40 bits**: `{0, 1, 2, 2^40-2,
2^40-1}`, **all 40 powers of two**, the compiled baseline and baseline±1, and **24 asymmetric
interior samples** (fixed, listed in `harness/arms202.json`, generated by a seeded PRNG recorded in
the contract) — plus the byte-wise marginal sweep (5 bytes × 256) that the earlier work did, so the
two are comparable.

**A per-value EXACT oracle for one sub-byte.** The census byte-diffs `rotate(a, K)` for
`K ∈ {1,5,7,13,19,31}` and identifies which byte of `operands` carries the immediate amount. For
the 256-value sweep of *that* byte the oracle is the **exact host-computed rotate result** for the
amount the model predicts — a fully discriminating, per-value oracle. If the model holds, an
implementer can emit an arbitrary rotate amount; if it does not, that is a db-defect result (§8).

**Hang policy for the joint arm, pre-registered.** `FIELD-SWEEP-PROTOCOL` §3(c) forbids a hang
budget where it would prevent mapping a *contiguous* hazard; a 2^40 space cannot be mapped by any
sweep, so that concern does not apply and §8's rule governs instead. **No abort on faults.** The
joint 40-bit arm aborts only after **3 genuine hangs** (a `MALFORMED` response is a measurement
failure, never a hang), and if it aborts the arm is reported **PARTIAL** with the exact value at
which it stopped. Byte-wise arms have no abort path.

### 2.3 `ibitcount.cache` (bit 17 = byte+2 bit 1, width 1)

**Dimension: RESULT ROUTING — whether the result is consumed by a following ALU op or written back
standalone.** `db.json`: *"cache (byte+2 bit17, writeback-enable): only 0x54/0x55 (bit1 clear)
break the stored result, 0x56 standalone writes back"*, and the same 0x54/0x56 pair appears on six
unrelated descriptors (EXP-0188 §1). The one carrier EXP-0169 had was a standalone popcount stored
straight to memory — **one point in the routing dimension**.

The coordinator's warning is recorded and acted on: *`cache` fields in this corpus read inert
because a single-pass, single-threadgroup carrier physically cannot express a memory/coherency
dimension.* This carrier set therefore spans **routing**, and additionally varies **dispatch
shape** (§2.7) so that a coherency reading of the name is not silently excluded.

* `pc_store` — `out[g] = popcount(a[g])`: result goes straight to memory (standalone).
* `pc_alu` — `out[g] = popcount(a[g]) * 3u + 7u`: result **consumed by a following ALU op**.
* `pc_cmp` — `out[g] = popcount(a[g]) > 3u ? a[g] : b[g]`: result consumed by a **compare**.
* `pc_two` — two popcounts summed: result consumed, and two occurrences in one program.
* `pc_tg`  — popcount whose result crosses **threadgroup memory** before being stored, so a
  coherency reading of "cache" has a carrier that can express it.

**Positive control in the same dimension:** `srcdesc` (byte+6) and `op_enable` (byte+4) are
`hardware-run` on this instruction (EXP-0169, EXP-M4-14) and both break the result when cleared —
they are swept on every arm as the control. **Additionally**, the census records which byte+2 the
compiler emits per carrier: if it emits **both** 0x54 and 0x56, the dimension is spanned by
demonstration rather than by assertion.

**H3.** `cache` is live on at least one routing arm. **Refuter:** identical observables at both
values on every arm whose control fires, in both runs.

### 2.4 `ibitcount.dst` (bits 24..31, width 8)

**Model (pre-registered, from `db.json`):** `dst = reg << 1`; the value selects which physical
register receives the count. **Prediction per value:** the following store still reads the
*compiled* register, so the program reproduces the oracle **iff `value == compiled_dst`**, and is
broken otherwise. That is a two-class, per-value, host-computed oracle.
`iunary.dst` (the same byte, M4, EXP-0139) **faults reproducibly at 192–241 and 243–255**; the
G17P behaviour of that region is a pre-registered secondary question. Dense 0..255, no abort path.

**H4.** `dst` is live; exactly one value reproduces the oracle and it is the compiled one.
**Refuter:** more than one value reproduces the oracle, or none does.

### 2.5 `iunary.b1` (bits 8..15) and `iunary.opsel` (bits 16..23)

**No raw exists for either.** `iunary` is the loose `byte0 == 0x27` catch-all: the RT / interpolation /
convert residue left over once the tight `ibitcount` descriptor (byte+2 == 0x56, 15 match bits) has
claimed the popcount member. A carrier must therefore emit a `27 ..` instruction that **does not**
tokenize as `ibitcount`. The census enumerates candidates across ~20 authored kernels
(`kernels/k_iu202.metal`) and the arms are built only from occurrences the **pinned tokenizer calls
`iunary`**.

**Dimension for both fields: the DATAPATH the 0x27 opcode is steering** (`opsel` names it:
0x56 int-unary/convert, 0x22 rt/interp, 0x10 convert, 0x26 convert2, 0x07 logic), and for `b1` the
**function/source descriptor** within it. Carriers are chosen to land on *different* `opsel` values
where our own MSL can reach them.

**H5.** Both are live: dense 0..255 each, with movement.
**Refuter:** no movement on any arm whose control fires.
**Known confounder, pre-registered:** on a descriptor this loose, many swept values re-tokenize as
a *different* instruction. Every case records the tokenized mnemonic and `encodable_range` counts
only values that still tokenize as `iunary`; movement outside that set is reported separately and
**never** supports the field verdict.

### 2.6 `cvt_f2i.b9` (bits 72..79, width 8)

**The refusal is specific and is quoted in full** (`EXP-0168/PROGRESS.md:249`):

> **(g) `cvt_f2i.b9` is INERT-SINGLE, not UNSTABLE** — 256/256 `ok` in BOTH runs, one distinct
> observed word, rv01 unanimous. Like `copysign.operands` it does not need a third run; it needs a
> second, structurally different carrier.

EXP-0184 then supplied five carriers and all five were **destination width / sign / source width**
(`s32`, `u32`, `s16`, `u16`, `h32`) — the dimension `db.json` already assigns to **byte+8**
(`dst_class`) and **byte+4** (`src_class`). If `b9` is a *different* descriptor, five carriers that
vary byte+8's dimension are, for `b9`, still **one carrier**.

**Dimensions never yet varied for this field, and the carriers that span them:**

* **result routing** — `cvt_alu`: `int(a[t]) * 3 + 7`, the convert consumed by a following ALU op.
  Every EXP-0184 carrier stored the result straight to memory.
* **destination WIDTH beyond 32 bits** — `cvt_i64`: `long(a[t])`, a register-pair destination.
* **source class** — `cvt_uni`: converting a **thread-invariant** `constant float&`.
* **vector form** — `cvt_v4`: `int4(f4)`, four converts in one expression.
* **rounding path** — `cvt_rnd`: `int(rint(a[t]))`, a rounded rather than truncated convert.

**A second, independent question the same arm answers.** `b9` is the last byte of the modelled
10-byte length. The census tokenizes the surrounding bytes with the pinned DB and reports whether
the following instruction starts at +10; if `b9` is really the next instruction's leader, sweeping
it will not be quietly inert. Either outcome is a first-class result (protocol §6).

**H6.** `b9` moves on at least one of the five new dimensions.
**Refuter:** 256/256 identical on every arm whose control fires — in which case the honest verdict
is `single-template-inference` **with the dimensions now spanned recorded in `range`**, and it is
still not emitter grade.

### 2.7 A dispatch-shape cross, applied to every compute arm

Every arm is dispatched at **two grid/threadgroup shapes** (`grid=8, tg=8` and `grid=64, tg=32`,
so the second is multi-threadgroup and multi-wave). This is cheap and it removes one specific
excuse the corpus has hit before — that a single-threadgroup carrier cannot express a
memory/coherency dimension. Both shapes appear on the `cache` arms; the shape is recorded per case.

### 2.8 `cvt_f2i._instruction`

**H8.** The instruction executes on G17P with the documented semantics — truncation toward zero —
and the **sign of the conversion is selected by `signflag` bit 6 (0x40)**, so splicing it flips a
signed convert to an unsigned one (EXP-0013, on M4/A18, never re-run on G17P).
**Oracle: two competing host-computed vectors**, `[trunc_signed(x)]` and `[trunc_unsigned(x)]`,
which differ on the negative lanes. The case is scored by **which of the two it matched**, so the
oracle discriminates between the hypotheses rather than merely predicting "correct".
**Refuter.** If splicing bit 6 leaves the signed result unchanged, or produces neither vector, H8
is refuted and the instruction-level label stays `corpus-correlation` on G17P.

---

## 3. Independent / controlled variables

**Independent:** the value of exactly one field of exactly one instruction occurrence.
**Controlled:** every other byte of the program; the input buffers; the dispatch shape (recorded
per case, and crossed deliberately per §2.7); the compiler invocation (`--no-fast-math`, one named
function per kernel).
**Confounders named in advance:** compiler folding removing the target instruction (census catches
it — a carrier that does not emit its target is dropped *before* the freeze and recorded);
re-tokenization to a different instruction (recorded per case); sibling-agent GPU load (measured by
`gpuwatch.py`); the false-hang cascade of `FIELD-SWEEP-PROTOCOL` §3(d) (defeated by
`harness/saferunner202.py`, one reader thread per child; a malformed response is a **measurement
failure**, never a hang); `InnocentVictim` (retried before scoring).

---

## 4. The record, per case

One JSON object per case, appended and `fflush`+`fsync`'d immediately, to
`raw/<run_id>/sweep.jsonl`, with keys: `carrier, arm, instr, field, value, bytes, token, observed,
oracle, match, outcome, status, statuses, fault_classes, innocent_retries, role, occ, off,
instr_len, start, width, grid, tg, note, ts`.

`outcome` ∈ `ok | silent_zero | wrong_value | not_written | fault | hang | nondeterministic |
invalid_run | measurement_failure`. Faults and hangs are results and are kept.

---

## 5. Falsifiers that must FIRE, or the run proves nothing

Per arm, two pre-registered cases whose outcome is asserted in advance:

* **FALSIFIER (must FAIL the oracle).** For every arm, the value that clears `op_enable`/`srcdesc`
  or points the source at a register the program never wrote. If it comes out `ok`, the arm cannot
  detect a difference and is **barred from supporting any verdict**.
* **LADDER / CONTROL (must MOVE).** A field on the *same instruction occurrence* already at
  emitter grade — `ibitcount`: `srcdesc`, `op_enable`; `shift_amt_move`: `src_reg`, `op_desc`;
  `irotate`: `b2`; `cvt_f2i`: `dst`, `mode`. It is swept on every arm in every run. **An arm whose
  control never moves has no detection power and cannot establish liveness OR inertness**
  (DEF-0190-1; ten instances of the missing-detection-power defect are on record).

---

## 6. THE GATE — frozen. `analysis/verdicts.py` implements this and nothing else.

1. **Two gated runs**, byte-identical programs, the same frozen `harness/arms202.json`
   (sha256 recorded in every run's `env.json`).
2. **≥ 99 % per-value cross-run agreement** on the outcome partition (outcome + exact observed
   word vector), **and `moved >= 2 * disagree` AND `moved > 0`**.
   Written exactly that way. **Not** `moved >= 2 * max(disagree, 1)`: that form demands
   `moved >= 2` and so **cannot promote any width-1 field by arithmetic** (DEF, EXP-0178) — and
   three of this experiment's eight fields are width 1.
3. **Detection power.** The arm's control must have moved in **both** runs, and the arm's
   falsifier must have failed the oracle in **both** runs. An arm failing either is barred from
   supporting a verdict of **any** kind, live or inert.
4. **Baselines.** The arm-open and arm-close unmutated baselines must both be `ok`.
5. **Inertness requires a spanned dimension.** A `0 moved` verdict may only be recorded when
   ≥ 2 carriers **differ in the dimension named in §2** for that field and both pass rule 3.
   Otherwise the verdict is `STILL-UNDERPOWERED` → label `untested`. Never rounded up.
6. **V, the distinct-VALID-payload test** (`tools/agx-isa/wave_audit.py`). Hard outcomes
   (`fault`, `hang`, `undecodable`, `measurement_failure`) are counted **separately** and never as
   movement. A field with **V ≤ 1** across many legal values ran legally and was
   **indistinguishable**: its "movement" is a hazard map, not a semantic, and it is **withheld**.
7. **Oracle discrimination.** The per-case `oracle` must take **more than one distinct value**
   across an arm. A constant oracle predicts the instruction's effect, not the field's, and any
   arm with a constant oracle is reported but **cannot promote**.
8. **Quiet-window gate.** `raw/<run>/gpuwatch.jsonl` must show **no non-EXP-0202 GPU process** for
   the duration. If it does not, the cross-run figure is labelled **CONTAMINATED**, no field is
   promoted from that pair, and the contamination is reported as the result.

**Label policy.** LIVE → `hardware-run`. INERT with the dimension spanned →
`single-template-inference` (**not** emitter grade: emitter grade asserts an implementer may
*choose* the value; "emit what the compiler emitted" is a captured-template dependency).
Underpowered → `untested`. `_instruction` under H8 → `hardware-run` only if the sign splice
matched the *competing* host vector.

---

## 7. Arms

Frozen in `harness/arms202.json` after the pre-freeze census; its sha256 is recorded in
`CAPTURE_CONTRACT.json` and in each run's `env.json`. **The census is calibration: no verdict may
cite `raw/prefreeze/`.**

## 8. Anything that turns out not to be a field

Recorded in `analysis/field_verdicts.json` under `_db_defects` with the evidence.
**`tools/agx-isa/db.json` is NOT edited** — the orchestrator owns it.

## 9. Environment and timeouts

Compile 600 s · per-request watchdog 8 s (compute) · SSH connect 15 s · every remote call wrapped
in a hard alarm. Run ids are never reused; a partial capture is retained and a replacement takes a
**new** id.

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

> **CENSUS RESULT (pre-freeze, `raw/prefreeze/census.json`), and the amendment it forced.**
> Across **50 authored carriers**, `shift_amt_move` is emitted at **6 boundary-aligned
> occurrences** and **every one has `src_flag = 0`** — including both thread-invariant-amount
> carriers, which compile to *byte-identical* `0b011c05` with the GPR-sourced one. Our own MSL
> cannot make the compiler choose the other value.
>
> **But the same bit, at the same position, with the same 7+1 split and the same enum, exists on
> the sibling descriptor `b_alu10_lo7` — and there the compiler emits BOTH values**: `src_flag = 1`
> at `cvt_i64@46` and `cvt_i64@78`, `src_flag = 0` at `pc_tg@12`. That is the **positive control in
> the same dimension** that `FIELD-SWEEP-PROTOCOL` §9 rule 1 demands, and it is added as a
> `dimension`-role arm. It also yields a verdict for `b_alu10_lo7.src_flag` in its own right.
>
> **What each outcome now means, stated before the run:** if the `b_alu10_lo7` arm MOVES and the
> `shift_amt_move` arms do not, the source-class bit is observable on this harness and inert on
> this instruction — a real inertness result. If **neither** moves, the harness has not been shown
> able to see the source-class dimension at all and **no inertness claim may be made**; the honest
> verdict is `untested`, and the gate's rule 3 enforces that mechanically.

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

> **CENSUS RESULT (pre-freeze), and the amendment it forced.** With instruction-boundary
> alignment required, **ZERO of the 50 authored carriers emit a boundary-aligned `iunary`.** Every
> `byte0 == 0x27` instruction our compute MSL produces is claimed by a tighter descriptor
> (`ibitcount`, `irotate`, `cvt_f2i`). EXP-0139 reported the same thing for 30 kernels of its own.
> The apparent `iunary` hits in the first census pass were **interiors of longer instructions** —
> a `b_alu10_lo7` at `cvt_i64@46` contains the bytes `27 11 00 02 …` — which is exactly the
> "movement that is really a different instruction" failure, one step earlier.
>
> **So the fields are reached by SYNTHESIS, which is the sanctioned method** (`CLAUDE.md`,
> "extrapolate, then test") and the one EXP-0139 used: byte+1 = `0x2d` with byte+2 = `0x22` is a
> `byte0 == 0x27` 8-byte member that tokenizes as `iunary` (NOT `ibitcount`) and still computes.
> An 8-byte `ibitcount` occurrence is rewritten **in place** into that form, keeping its operand
> bytes, and the field is swept on top. **The arm's own baseline is the synthesized form with no
> field mutation**, so if the synthesis does not compute on G17P the arm has no detection power and
> the gate bars it. Verified offline against the pinned tokenizer: it is byte+2, not byte+1, that
> decides `iunary` vs `ibitcount`, so the `b1` arm stays `iunary` across all 256 values and the
> `opsel` arm leaves it at exactly 4 (`0x54..0x57`).

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
4. **Baselines.** For an arm with **no prepatch**, the arm-open and arm-close unmutated
   baselines must both be `ok`. For a **prepatched** arm — the synthesized `iunary` form (§2.5)
   and the `src_flag` arms that move the source index (§2.1) — the program is *deliberately*
   altered before the sweep, so `ok` is not the right test; the requirement is that the open and
   close baselines be **identical to each other and identical across both runs**. Stability is
   what a baseline is for. *(Amendment recorded in `PROGRESS.md`, pre-freeze, after the pilot
   showed the prepatched arms' baselines are by design not `ok`.)*
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

## 6a. Pre-freeze census facts the arms are built from (calibration; no verdict cites them)

`raw/prefreeze/census.json`, 50 carriers, all compiled, none dropped for a compile error.

| fact | consequence |
|---|---|
| `shift_amt_move`: 6 boundary-aligned occurrences, `src_flag = 0` on all 6 | the compiler never chooses the other value; the same-dimension control moves to `b_alu10_lo7` |
| `b_alu10_lo7.src_flag`: compiler emits **both** 0 and 1 | the positive control in the dimension (§2.1) |
| `ibitcount`: 9 occurrences, `cache` compiled **0 on two and 1 on seven** | the result-routing dimension is spanned **by demonstration**, and both splice directions are testable |
| `irotate`: 10 occurrences; byte-diff over rotate amounts {1,5,7,13,19,31} shows **byte+6 is the ONLY byte that moves**, at **byte+6 = 4·(32−K)** | an EXACT per-value host oracle for the amount sub-byte (§2.2) |
| `cvt_f2i`: 9 occurrences spanning `mode` {0x54,0x56}, `cvtop` {0x96,0xac,0xb4}, `src_class` {2,3}, `dst` {0,4,6,8}; **`b9` = 0 in every one** | the dimensions EXP-0184 never varied, now spanned |
| `cvt_f2i` length model: the pinned tokenizer's walk puts the next instruction at **+10**, with +8/+9 decoding only as spurious mid-instruction hits | the 10-byte model that makes `b9` a field is self-consistent |
| `iunary`: **0 boundary-aligned occurrences in 50 carriers** | the fields are reached by synthesis (§2.5) |

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

---

# AMENDMENT v3 — frozen 2026-08-30, BEFORE its first dispatch

**Trigger.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` was added to the repository while
`g17p_20260830_run02` was in flight. It is **normative and wins where it conflicts** with §6
above. §4 of that document requires that a design change after observations are seen **retain the
old run and start a named amendment whose revised pre-registration is frozen before its first
dispatch**. That is what this is.

**What is retained, not discarded.** `g17p_20260830_run02` ran to completion against
`CAPTURE_CONTRACT.json` v2 and `harness/arms202.json`. It is retained **in full** as the
**discovery** run and is cited only for liveness and geometry, never for a promotion. Its harness
files — `run.py`, `harness/carriers202.py`, `harness/oracles202.py`, `analysis/gen_arms.py`,
`analysis/census.py`, `harness/arms202.json` — are **not edited**, so its chain stays reproducible
byte-for-byte. The amendment adds new files beside them.

## A3.1 What changes

| gate | change | new file |
|---|---|---|
| **A** actual-byte ledger | every case records `requested_value`, `requested_bytes`, `actual_bytes`, `decoded_actual` (decoded by the **pinned tokenizer**, a different code path from the patcher), `ledger_ok`, `main_sha256`, `off`, and the db/arms/harness/driver revisions. **No hardware conclusion for a field until every one of its cases satisfies `requested == decoded-from-actual`.** Reported: cases, distinct requested values, distinct **actual** encodings, and `match`-bit collisions. A round trip is explicitly not this gate. | `run2.py`, `analysis/verdicts.py` |
| **B** detection power | unchanged in kind, but the failure verdict is renamed to what it is: a control that does not move **and** fail the oracle in both runs makes the arm **`carrier-undecidable`**, and zero movement is then **not** evidence of inertness. | `analysis/verdicts.py` |
| **B/§6** register lifecycle and operand provenance — **a required dimension**, and the one `src_flag` most likely needs | five new `shift_amt_move` carriers whose staged amount is produced by a **different producer class**: ALU (`sam_alu`), thread-position system value (`sam_sys`), SIMD lane index (`sam_lane`), an overwrite / intervening-independent-ALU lifetime (`sam_ovr`), and a control-flow merge (`sam_cf`). The v1 set had, *in practice*, exactly one producer class: the compiler lowered the thread-invariant `constant uint&` amount through a GPR and emitted bytes **identical** to the memory-load carrier. | `kernels/k_sam2_202.metal` |
| **B/§6** two disjoint readback plans | `pc_dump` keeps **four mutually distinct live values per lane at fixed store indices**, so a redirected `ibitcount.dst` shows up as one of the other three words taking the count instead of being invisible. | `kernels/k_pc2_202.metal` |
| **C** semantics ≠ liveness | every case carries a pre-registered `predicted_bucket` ∈ {`ok`, `not_ok`, `rejected`} and a scored `sem_match`. **`sem_checked == 0` can never produce `hardware-run`.** Stable movement with no semantic check is reported as **`live; role unknown`**. | `harness/oracles202b.py` |
| **E** clean confirmation | the confirmation pair runs in **opposite case order** (`--order forward` / `--order reverse`); a malformed response stays `measurement_failure` and is never a hardware outcome; the measured quiet-window state of each run is reported and a non-quiet window is labelled **CONTAMINATED**. | `run2.py`, `analysis/verdicts.py` |
| verdict shape | six independent axes — encoding geometry, liveness, semantics, compiler recipe, target, reproducibility — with exact numerators and denominators. Negative wording is `inert in <exact tested envelope>; global role unknown`; never "unused" or "reserved". | `analysis/verdicts.py` |

## A3.2 The pre-registered semantic models (Gate C), stated before the dispatch

| field | model | what refutes it |
|---|---|---|
| `shift_amt_move.src_flag` | SOURCE-CLASS SELECT: at the compiled value the amount comes from the file the compiler chose (`ok`); at the other value it comes from the other file, whose contents at that index we did not place (`not_ok`) | every value of every powered arm coming out `ok` |
| `ibitcount.cache` | WRITEBACK-ENABLE: `ok` at the compiled value, `not_ok` at the other | `ok` at both |
| `ibitcount.dst` | `dst = reg<<1`; the store still reads the compiled register, so `ok` **iff** value == compiled — **plus a CROSS-TARGET TRANSFER TEST**: `iunary.dst`, the same byte, faults reproducibly at **192–241 and 243–255** on M4 (EXP-0139), and those values are predicted `rejected` on G17P | any of: a second value delivering; the M4 fault region not faulting |
| `iunary.b1`, `iunary.opsel` | FUNCTION / DATAPATH SELECT: `ok` at the synthesized base, `not_ok` elsewhere | a second value delivering |
| `cvt_f2i.b9` | **the LIVE model**: `ok` at the compiled value, `not_ok` elsewhere. If byte+9 is genuinely a reserved constant this is refuted at 255 of 256 values — **and that refutation is the result** | 256/256 `ok` |
| `irotate.operands` byte+6 | **the strongest form**: an EXACT host-computed vector per value — rotate-left by `K` where `byte+6 = 4·(32−K)`, extrapolated from the census byte-diff over amounts {1,5,7,13,19,31} | any modelled value whose observed vector is not the predicted rotate |
| `cvt_f2i.signflag` | bit 6 selects signed vs unsigned; scored on lane 7 (2³¹+2⁸, outside int32) against the arm's **own unmutated baseline** | lane 7 unchanged by the splice |

## A3.3 What an inertness claim may say after this amendment

§7 of the corrections document requires, for a general accepted-inert rule: **three structurally
different carrier/context classes**, a positive control in **every** one, interactions with every
plausible selector, **two clean isolated repetitions**, and an independent method. This experiment
supplies the carrier classes and the controls; it does **not** supply an independent
compiler-differential method for `src_flag` (the compiler emits only one value of it — that *is*
the differential result, and it is negative). So the strongest inertness statement this experiment
may make is bounded:

> `inert in <exact tested envelope>; global role unknown`

and where the control does not fire, the verdict is `carrier-undecidable`, which is a **recorded
result**, not a failure.

## A3.4 Runs

`g17p_20260830_run02` — discovery, contract v2, `arms202.json`, **retained, never topped up**.
`g17p_20260830_run03` — confirmation A, contract v3, `arms202b.json`, `--order forward`.
`g17p_20260830_run04` — confirmation B, contract v3, `arms202b.json`, `--order reverse`.
Run ids are never reused. `harness/gpuwatch.py` measures the window of every run.

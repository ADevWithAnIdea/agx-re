# EXP-0168 — PRE-REGISTRATION

**Frozen 2026-08-30, before any device work.** Hashes in `CAPTURE_CONTRACT.json`.

**Target: Apple A18 Pro / G17P** — `applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9, `users-MacBook-Neo.local`. Every result
carries `target: G17P` and is **direct** evidence for the documentation target.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
  (+ PUBLIC for IEEE-754 and the MSL conversion definitions, used ONLY to write
   host oracles, never to source an Apple9 encoding fact)
Inputs inspected: kernels/probes.metal + kernels/carrier_dag.metal (authored by
  us) and the AGX machine code the public newLibraryWithSource: /
  MTLBinaryArchive API compiled FROM THEM; plus this repository's own committed
  raw observations from EXP-0138/0140/0141/0144/0147/0155/0163/0164.
Apple binary introspection: NONE
Reproduction: see README.md
Evidence: raw/prefreeze/** (calibration, never evidence);
          raw/<run id>/sweep.jsonl (gated, append-only, flush+fsync per record)
```

---

## 1. The question

EXP-0164 re-derived every emitter-grade field in `tools/agx-isa/validation.json`
from committed `raw/` and withdrew the emittability headline from 79/166 to
41/166, downgrading 122 fields to `untested`. It named the cheapest way back up:

1. **`dst` is the single most load-bearing field NAME in the DB — it blocks 13
   instructions.**
2. **Twelve instructions are exactly ONE field away** from keeping emittable
   status.

**Can those fields be re-established with evidence that survives a re-audit?**

The fields were withheld because the old evidence was *underpowered*, not
because it was absent. Re-running the same weak probe cannot help. So the real
question this experiment answers is narrower and harder:

> For each withheld field, is there a **buildable carrier that can express what
> the field controls**, and does the field move in it — with detection power
> demonstrated *first*, and the result reproducing across gated runs?

## 2. Scope

**26 field rows**, agreed with the orchestrator as disjoint from EXP-0169:

| set | rows |
|---|---|
| A. the `dst` field name (13 instructions blocked) | `uniform_mov`, `falu2`, `falu2i`, `get_sr`, `cvt_f2i`, `unpack_convert`, `frag_color_pack`, `matrix_mac`, `vtx_out_pos`, `reg_move_c0/c1/c2var/c9/cb` |
| B. the 12 one-field-away | `atomic_mem.addr_desc_hi`, `copysign.operands`, `cvt_f2h.op`, `falu_acc.cache`, `if_push.scope`, `iter_at.grp`, `mov_imm.imm_top`, `pack_convert.b7`, `pixel_order.kind`, `shift_amt_move.src_flag`, `stop.reserved`, `uniform_mov.dst` |
| C. two companions that COMPLETE a descriptor | `cvt_f2i.b9`, `vtx_out_pos.slot` — each the only *other* withheld field on its instruction |

`matrix_mac.dst` is **deliberately not attempted** (§10).

## 3. The standard this experiment is built to

Four rules, each derived from a failure already documented in this repository.
They are the design, not decoration.

**R1 — THE OBSERVABLE MUST NOT CO-VARY WITH THE FIELD.**
EXP-0140's `uniform_mov.dst` sweep built its read-back as
`device_store(..., data_reg=D)` where `D` is the dst being swept
(`EXP-0140/harness/cases.py:92-100`). Field and observable moved together, so a
*correct* hardware result is a constant observed vector **by construction**, and
the audit's "16 values dispatched, 0 moved" was the **passing** outcome of a test
that could only ever return that. Here the store list is identical in every case
— all 16 GPRs, always — and the verdict is a function of *which slot changed*.

**R2 — TWO CARRIERS IDENTICAL IN THE CONTROLLED DIMENSION ARE ONE CARRIER.**
`iter_at.loc` read inert on every EXP-0155 arm and moves 128/256 at
`rasterSampleCount = 4` (EXP-0163) — at one sample the centroid, the sample point
and the pixel centre are the same point. Its two "independent" carriers were both
`samples=1`. Every arm below names the **dimension** it varies, and arms that
pair must differ in it. Carrier *count* proves nothing.

**R3 — PROVE DETECTION POWER BEFORE CONCLUDING ANYTHING.**
Every arm runs a **liveness ladder** first: a known-live control of the *same*
instruction, with the citation that makes it known-live, over ≥8 values. An arm
whose ladder does not produce ≥2 distinct observed digests **in every gated run**
is DISCARDED, and its inertness is not evidence of anything.

**R4 — BYTE-MATES.** Only the field's own bits are mutated (`set_field`, LSB-first
per db.json). For every sub-byte field a **byte-mate control** additionally
sweeps the *complementary* bits of the same byte with the field pinned at its
anchor, so a reader can see whether movement credited to the field could have
come from a neighbour.

## 4. Hypotheses, refuters and carriers, per field

Format: **H** hypothesis · **D** dimension the field controls · **C** carriers
that differ in D · **L** liveness ladder · **O** oracle · **R** refuter.

### 4.1 `dst` — the destination-register selector (14 rows)

**H1.** `dst` names the register that receives the result. For `dst = v`, exactly
one register changes and its index is `v`.
**D.** *Which register slot changes.*
**C.** three genuinely different observation paths:
 - `*/dump` — 16-GPR dump, fixed store list (R1).
 - `REGMOVE/consumer` and `/consumer9` — a *dependence* path: a fixed consumer
   reads `rC` (C = 3, then 9) and only the coincidence `dst == rC` changes it.
   **The coincidence index must MOVE with the consumer** — something a single
   consumer index can never show.
 - `REGMOVE/form` — the **dst × form cross-product**. This is the measurement
   EXP-0140 never made: it swept `dst` at ONE byte+2 value and
   `analysis/verdicts.py:327` fanned that single verdict verbatim onto all six
   descriptor names, though its own probe shows the forms behave differently
   (c0/c2var `silent_zero`, c9 `wrong_value` returning byte+1 verbatim, cb
   `wrong_value`, c1 `ok`). All three of those still WRITE the destination, so
   the dump makes `dst` live for every form.
**L.** `usrc`/`src_reg` (byte+1) — EXP-0101/EXP-0113 HW: "the readback depends
only on `src_reg`". For `falu2`/`falu2i`: `srcA_reg`, EXP-0020/EXP-0101 HW. For
`get_sr`: `sr_sel`, EXP-0031 HW.
**O.** Host-computed. The GPU-independent half is the **seed table**: fifteen
slots must still hold values this program wrote into them, known a priori. The
written value itself comes from the unmutated anchor — ONE GPU measurement reused
across the sweep — so the oracle is labelled `slot_pattern`, not `value_exact`.
For `falu2`/`falu2i` the written value is *also* host-computable from the seeds;
where the two agree the record is upgraded and that agreement is reported.
**R.** If sweeping `dst` changes a slot whose index is **not** `v`, or changes
more than one slot, or changes nothing while the ladder moves, H1 is refuted for
that form and the observed rule is recorded instead.

### 4.2 `falu_acc.cache` (byte+2 bit5, 0x18 vs 0x38)

**H2.** It is a source-cache / **last-use** hint: it does not change the
arithmetic, it changes whether the source register survives the read.
**D.** *Whether the accumulate's source is read again.* RT-1a-FIX tested
0x18↔0x38 by checking the reduction **result** (`out2 = 33` either way) — which a
cache hint cannot change. The carrier could not express the field.
**C.** `FALU_ACC/lastuse` (sources never read again) · `FALU_ACC/reuse`
(`k_sum_reuse`: every source read a second time) · `FALU_ACC/reread` (an
**authored** falu2i re-reads srcB after the block, so the re-read is guaranteed
rather than left to the scheduler). Crossed with 14 `srcB` values.
**L.** `srcB` (byte+3) — EXP-0025 HW.
**O.** Baseline-null; movement is the signal. Release-on-read is a documented
Apple9 behaviour (EXP-0138: reading a GPR as a 32-bit source zeroes it), so the
predicted signature is *the source slot going to zero under one cache value and
not the other*.
**R.** If all three carriers give identical digests for both values while all
three ladders move, H2 is refuted and the field is a **PROVEN-DONT-CARE** (§7).

### 4.3 `shift_amt_move.src_flag` (byte+1 bit7)

**H3.** Bit 7 selects the **file** the staged shift amount comes from (EXP-0140:
"bit7 selects immediate-vs-uniform-file").
**D.** *Which file supplies the amount.* A carrier holding the source index fixed
cannot separate two files that happen to hold the same value at that index.
**C.** `SHIFTMOVE/gpr` (`k_rot_var`: per-thread GPR amount) ·
`SHIFTMOVE/uni` (`k_rot_uni`: thread-invariant amount) — **crossed with 13
`src_reg` values**, which is the actual test: at flag=0 the result should track
our distinct per-register seeds; at flag=1 it should not. **Two profiles over the
index is the movement signal.**
**L.** `src_reg` — EXP-0101/EXP-0113 HW.
**R.** If the two flag values produce the same profile across all 13 indices in
both carriers, H3 is refuted.

### 4.4 `mov_imm.imm_top` (bit 15)

**H4.** `imm_top = 1` selects a **different, longer instruction**: it does not
extend the immediate, it does not zero the destination, and unpadded it
**consumes the following 2-byte instruction** (EXP-0140, from two records).
**D.** *Whether the next instruction is consumed.*
**C.** `MOVIMM/padded` (next instruction is inert padding: destination must keep
its seed) · `MOVIMM/unpadded` (next instruction is a **load-bearing witness**
`mov_imm r5, 99`: if consumed, r5 keeps its seed instead of taking 99).
Crossed with dst ∈ {2, 7, 13}; byte+1 swept densely 0..255.
**L.** `imm7` at `imm_top = 0` — EXP-0031 HW ("out == the byte+1 literal",
splice-proven).
**O.** Fully host-computable: for `imm_top = 0`, `reg[dst] == imm7`.
**R.** If r5 takes 99 in the unpadded arm at `imm_top = 1`, the consumption model
is refuted. If the destination is **zero** rather than its seed, EXP-0128's
original "silent zero" reading is right and EXP-0140's correction is wrong.
*Note:* `imm7 == 12` does not tokenize under the current length rule; those cases
are dispatched anyway and recorded with `rt_ok = false` — the hardware, not our
disassembler, is the authority.

### 4.5 `copysign.operands` (byte+3)

**H5.** byte+3 is the src/dst **register operand descriptor**.
**D.** *The size of the resolvable operand space.* EXP-0138 swept all 256 values
and nothing moved — in a carrier holding **two** live floats
(`k_copysign` loads `a[t+0]`, `a[t+1]`, stores one word). A register selector
in a two-register space has a two-outcome observable.
**C.** `COPYSIGN/lowpress` (EXP-0138's configuration, reproduced as the control)
· `COPYSIGN/highpress` (`k_copysign_rp`, 12+ simultaneously live values) — and
**both** read back 16 distinctly-seeded registers, so a register selector has 16
resolvable outcomes instead of 2.
**L.** byte+1 — EXP-0138 HW: 240/256 values silently zero, 8 give −5.0 and 8 give
+5.0. (This is also a **db.json defect** to report: byte+1 is a live operand
field that the descriptor pins as a match constant, and byte+2 is a 256/256
don't-care likewise pinned. Not acted on here — EXP-0165 owns `db.json`.)
**R.** If byte+3 is inert in the 16-register carrier while its ladder moves, H5
is refuted and the byte is a PROVEN-DONT-CARE.

### 4.6 `cvt_f2h.op` (byte+2) and `cvt_f2i.dst`/`b9` (byte+3 / byte+9)

**H6.** db.json says byte+2 of this family selects
*result-consumed-by-following-ALU (0x54) vs standalone (0x56)*. **Every EXP-0144
carrier for both ops is standalone**, so the dimension was never tested.
**H6b.** EXP-0144's own `byte_scans.json` says **62 of 256 byte+2 values turn the
fp32→fp16 convert into an fp32→bfloat16 convert**, and 8 redirect the source.
This experiment tests that on G17P.
**D.** *Consumption.*
**C.** `CVTF2H/standalone` + `CVTF2H/consumed` (`k_f2h_consumed`: the half result
feeds a half-ALU op) · `CVTF2I/standalone` + `CVTF2I/consumed`.
**L.** the source byte — EXP-M4-13 R9 own-MSL byte-diff (byte+5 = src reg) and
EXP-0144 HW.
**R.** If byte+2's value→behaviour map is identical in the consuming and
standalone carriers, the db.json consumption model is refuted for these two ops.

### 4.7 `pack_convert.b7` (byte+7) and `unpack_convert.dst` (byte+3)

**H7.** b7 lies inside the format-conversion descriptor, so it interacts with the
**format**. EXP-0144's "two carriers" were arms `F` and `W` over the *same*
compiled program (`EXP-0144/harness/casematrix.py:6-17`) — one carrier counted
twice.
**D.** *Format.*
**C.** `PACK/unorm2` · `PACK/snorm2` · `PACK/unorm4` (three formats, three
kernels) and `UNPACK/unorm` · `UNPACK/snorm` · `UNPACK/consumed`.
**L.** byte+5 (a real source register, EXP-0144 HW).
**Predicted:** `(v & 0xfb) == 0x50` reproduces the pack (EXP-0144, exact over
256/256 with zero false positives). **Recorded in advance so a match is a
confirmation and a mismatch is a finding.**
**R.** If the rule differs between formats, b7 is format-coupled and the single
rule is wrong.

### 4.8 `stop.reserved` (24-bit body)

**H8.** The body is inert padding: corrupting any of it is a no-op (EXP-0003,
EXP-0010 E4).
**D.** *Whether the token terminates, and what it consumes.*
**C.** `STOP/terminal` (control: everything before it ran; full dump + both
sentinels are the observable) · `STOP/midprogram` — the stop sits **before the
dump**, so if it terminates the dump never runs and the window stays
`0xDEADBEEF`; if some body value made it not terminate, the dump appears. **A
terminal-stop carrier is blind to that by construction.**
**L.** replacing the mid-program stop with padding must make the dump appear —
this is the ladder, and it is what proves the observation can distinguish
"executed" from "not executed".
**Coverage.** the 24-bit field at boundaries + all powers of two + 16 asymmetric
interior values, **plus each constituent byte densely 0..255**.
**R.** Any body value that changes the dump in `STOP/terminal`, or that makes the
dump appear in `STOP/midprogram`, refutes H8.

### 4.9 `if_push.scope` (byte+2)

**H9.** `scope` selects the **reconvergence mask bank**, ping-ponging 0x54/0x56
with nesting parity.
**D.** *The mask bank, which only exists when there is more than one live scope.*
EXP-0140's carrier was NOT blind — its `scope_kind` moved 178 cases and produced
6 distinct vectors — but three properties bound what its null means: its MSL
if/else lowered to `isel10`, **a select that exercises no mask stack at all**;
both of its live pushes carried scope **0x54**, so the bank model was never
instantiated; and its observable was ONE GPR, one word per lane, over 8 lanes in
a partially filled 32-wide SIMD.
**C.** `IFPUSH/flat` (one scope — the **blind negative control**, kept
deliberately) · `IFPUSH/nest3.outer` · `IFPUSH/nest3.inner` (three genuine
nesting levels, so forcing the inner push to the outer's bank has an outer mask
to destroy) · `IFPUSH/loop` (a `scope_kind` 0x1a loop scope inside a 0x01 guard).
**Every divergent region contains a STORE**, which cannot be if-converted, so the
execution mask must predicate it — and against a poisoned output buffer the
per-lane × per-region slot pattern **is** the execution mask. 32 lanes × 8 slots.
**L.** `scope_kind` — EXP-0140 HW.
**R.** If the nested carriers reproduce EXP-0140's flat null across all 256 values
while `scope_kind` moves in the same carriers, H9 is refuted and `scope` is a
PROVEN-DONT-CARE over the tested nesting depths.

### 4.10 `atomic_mem.addr_desc_hi` (byte+6 bits 6..7)

**H10.** The two bits sit immediately above the 7-bit operand-register field
(`oper_reg_lo` bit47 + `oper_reg_hi` bits 48..53) and **extend the operand
register number** — untestable at a low index, and EXP-0141 tested exactly one
(its range note: "0x01/0x41/0x81/0xC1 all select index 3").
**D.** *The operand register number.*
**C.** `ATOMIC/lowreg` (`k_atomic_lo`) · `ATOMIC/highreg` (`k_atomic_hi`: 24
simultaneously live **named** scalars — not an array, which would go to scratch —
force a high allocation) · `ATOMIC/minop` (a different atomic operation), each
crossed with 9 `oper_reg_hi` values.
**L.** `oper_reg_hi` — EXP-0141.
**R.** If the four values are interchangeable at every operand register in all
three carriers, H10 is refuted and the bits are a PROVEN-DONT-CARE.

### 4.11 Render/vertex fields

`vtx_out_pos.dst` + `.slot`, `pixel_order.kind`, `frag_color_pack.dst`,
`iter_at.grp` — carriers, ladders, oracles and hazard budget in
**`RENDER-DESIGN.md`**, which is part of this pre-registration. Design summary:

- `vtx_out_pos.slot` selects **which varying slot**; EXP-0147's carrier was
  **single-varying** and its own RESULTS names "slot in a multi-varying carrier"
  as the open follow-up. Carriers therefore differ in the **number of varyings**,
  and the vertex stage gets a **direct** observable (a device buffer written from
  the vertex shader, which `gfrun2.m` already binds but no carrier ever used) in
  addition to the interpolated pixel.
- `frag_color_pack.dst` and `iter_at.grp`: EXP-0155's paired arms were **two
  occurrences of one instruction in one program** at one attachment format and
  `samples=1`. Carriers differ in attachment format and RT count.
- `iter_at.grp`: see §10 — a db.json defect bounds it before any sweep does.

## 5. Independent / controlled / confounding variables

| | |
|---|---|
| **Independent** | the value of the field under test (and, where crossed, the second dimension) |
| **Controlled** | carrier program, seed table, store list, poison pattern, grid/threadgroup, buffer bindings, `db.json` snapshot, timeouts, dispatch order within an arm |
| **Confounders and how each is handled** | **compiler codegen drift** → anchors are re-extracted per run and the anchor report is committed; **db.json drift** → a `work/frozen/` snapshot is pinned and sha256'd, and every case records the full instruction `bytes` so attribution never depends on a label (EXP-0144's committed raw can no longer be joined by `field` because db.json's labels moved); **sibling GPU contamination** → poison + sentinels + tail region + victim re-runs + a quiet window; **release-on-read** → the PRE sentinel lives in memory before the block and the POST sentinel is written after it, so neither can be destroyed by the instruction under test (EXP-0138 lost six sweeps to a sentinel in r11); **allocator/order effects** → the two gated runs execute the same frozen matrix in opposite arm order |

## 6. Raw record schema (frozen)

One JSON object per case appended to `raw/<run_id>/sweep.jsonl`, **flushed and
fsynced immediately**. Keys:

```
idx arm role instr field value bytes anchor byte_index fstart fwidth
cross_field cross_value style dim kind occ probe block_lo block_hi tgt
observed{digest,regs,pre,post,probe,tail_ok} | observed{hash,words,poison_slots}
oracle{kind,regs|hash,derived_from}
outcome validity match moved moved_slots predicts rt_ok victim os_class error
attempts[{status,error,os_class,validity}] note seq t
```

`role` ∈ `sweep | ladder | bytemate | falsifier | baseline | arm_not_run`.
`outcome` ∈ `ok | silent_zero | wrong_value | fault | hang | undecodable`
(the FIELD-SWEEP-PROTOCOL §4 enum, unchanged).
`validity` ∈ `valid | invalid_poison | invalid_sentinel | invalid_victim |
invalid_nodata` — **run integrity, deliberately separate from `outcome`.**

Companions: `00_env.json` (device identity read **from the live device**, never
from a literal — `EXP-0138/harness/run.py:110` hardcoded "Apple M4 (G16G) local"
into its evidence file), `01_progress.json`, `02_summary.json`, `baseline.jsonl`.

### The oracle convention, stated once because it inverts between arms
`outcome == "ok"` always means **matched the host prediction**. For a
destination-register field the prediction is **movement** (`predicts =
moves_to_slot_v`); for every other field the prediction is **no change**
(`predicts = no_change`, the null hypothesis being inertness). Every record also
carries `moved` and `moved_slots`, so the audit's own `moved_total` metric is
recomputable from this raw without knowing the convention.

## 7. Promotion gate — fixed in advance

A field is promoted to `hardware-run` only if **all** of:

1. **≥99.5% per-value cross-run agreement** on `outcome` between each pair of
   gated runs, over values both runs actually dispatched. *(The orchestrator's
   bar is ≥99%; this is deliberately above it.)*
2. **movement ≥ 4× the disagreement count.** *(His bar is ≥2×.)*
3. **the arm's liveness ladder passed in every gated run** (≥2 distinct observed
   digests).
4. **the arm's falsifier failed in every gated run** (`byte0 = 0x00` must not
   score `ok`).
5. **coverage** per FIELD-SWEEP-PROTOCOL §3.3 — dense for w ≤ 8.
6. **no case counted whose `validity != "valid"`.**
7. **the byte-mate control interpreted and reported**, not merely collected.

**Skip placeholders are not observations.** Cases not dispatched because a hang
budget was exhausted are written with `role`/`note` marking them as placeholders
and are excluded from every count. This is not hypothetical: EXP-0164 scored 248
of EXP-0144's `pack_convert.b7` placeholders as measurements and withheld the
field at "2.73% agreement" when the two runs that actually measured agree
**256/256** (`analysis/rescore_0144.py`).

### PROVEN-DONT-CARE — a separate verdict, declared in advance
A field that is genuinely inert **can never satisfy clause 2**, by construction.
Rather than silently label it `hardware-run` or silently fail it, this experiment
records `proven-dont-care` when: dense coverage · **≥2 carriers that differ in
the field's dimension, each PASSING its ladder** · 0 movement in every gated run ·
≥99.5% cross-run agreement · falsifier fired. The verdict is reported to the
orchestrator **with the ladder numbers as the detection-power proof** and with an
explicit note that clause 2 is unmeetable, so he decides — not me.

### The honest fallback
If a field cannot be reached with a carrier we can build, it is reported
**STILL-UNDERPOWERED**, naming the carrier that would be needed. Recovering 6
instructions with evidence that survives a re-audit is worth more than claiming
25 that do not.

## 8. Runs

Minimum **two** gated runs, target **three**: `run02` forward, `run03` reverse,
`run04` forward. `run01` is reserved for the smoke/calibration pass and is
**pre-freeze, never evidence** (`raw/prefreeze/`). Anchor extraction is likewise
pre-freeze calibration. A run id is **never reused**; a partial capture is
retained exactly as it stopped and its replacement takes a new id.

**Confirmation runs need a quiet machine** (FIELD-SWEEP-PROTOCOL §7, amended
2026-08-30). The window is coordinated with the orchestrator, and concurrent GPU
activity is **sampled into `raw/<run_id>/gpuwatch.jsonl` for the duration**, so
"the machine was quiet" is a measurement rather than a claim.

## 9. Timeouts and safety

| | |
|---|---|
| per dispatch | 8 s watchdog (`persistrun`), child killed and restarted on wedge |
| compile | 300 s |
| remote ssh/scp | `perl -e 'alarm N'` on every call: 120 s ssh, 300 s scp, 900 s pull |
| hang budget | **2 per field**, then the field STOPS and is reported PARTIAL; **6 per arm**, then the arm stops (FIELD-SWEEP-PROTOCOL §8) |
| after a hang | 2 s cooldown, then continue |
| baseline | re-validated every 300 cases; drift restarts the child |
| victim / invalid | re-run with backoff, child restarted on the 3rd attempt, never scored |
| if the neo stops answering | **STOP and report BLOCKED.** `macvdmtool` is the orchestrator's alone. |

**Declared hazards.** `if_push.scope` sweeps control flow and may hang;
`atomic_mem` sweeps device atomics and may hang; `iter_at.grp` is a known
minefield (§10). Expected device resets are estimated in `RENDER-DESIGN.md` and
reported to the orchestrator before the window opens.

## 10. Declared in advance: what will NOT be attempted, and why

- **`matrix_mac.dst`** — needs a simdgroup-matrix carrier over a full 32-lane
  simdgroup with fragment-register readback, and it is one of **twelve** withheld
  fields on `matrix_mac`, so repairing `dst` alone cannot recover the
  instruction. Reported as **NOT ATTEMPTED**, never as inert.
- **`iter_at.grp` beyond its legal values** — `db.json` declares `grp` as 8 bits
  at `start=0` while the descriptor's own match constant `[0, 7, 47]` **pins bits
  0..6**. Only bit 7 is free: `grp` has exactly two legal values (0x2f, 0xaf) and
  every other value is a *different instruction*, not a value of this field. That
  is the same declares-a-field-over-pinned-bits self-contradiction EXP-0162 fixed
  in `pixel_order`, and it explains the hang record — EXP-0155 hung at grp = 0x00,
  0x01, 0x0f, 0x12, 0x16, 0x18 and EXP-0163 at 0x00, 0x50, and **both runs tripped
  the two-hang stop rule, so no run has ever swept past ~25 of 256 values.** This
  experiment sweeps the two legal values densely, reports the descriptor defect
  under `db_defects`, and opens the out-of-descriptor region only as a small,
  pre-declared, hang-budgeted arm — a device reset costs every other agent on the
  machine.
- **`db.json` is not edited.** EXP-0165 owns it. Corrected models are recorded
  under `db_defects` in `analysis/field_verdicts.json` with their evidence.
- **`validation.json`, `docs/`, `PROVENANCE.md` are not edited**, and nothing is
  committed — the orchestrator reviews and commits.

## 11. Predictions committed before the first dispatch

1. `uniform_mov.dst` (and the four other `reg_move_*` forms) **will move** in the
   16-GPR dump, with the moved slot index equal to `v`, at forms where the
   instruction writes anything — including the `silent_zero` forms, because a
   silent zero still writes the destination.
2. `pack_convert.b7` will reproduce `(v & 0xfb) == 0x50` on G17P.
3. `stop.reserved` will be inert in **both** carriers (H8 confirmed) — the
   mid-program carrier's value is that it makes the null *meaningful*, not that
   it is expected to break it.
4. `mov_imm.imm_top = 1` will leave the destination holding its **seed**, not
   zero, in the padded arm, and will suppress the witness write in the unpadded
   arm.
5. `cvt_f2h.op` will show a value region converting to **bfloat16** rather than
   fp16, reproducing EXP-0144's M4 observation on G17P.
6. `falu_acc.cache`, `copysign.operands`, `if_push.scope` and
   `atomic_mem.addr_desc_hi` are the four where I expect a real chance of
   PROVEN-DONT-CARE rather than movement. Committing that in advance is the
   point: if they move, the prediction was wrong and the carriers earned it.

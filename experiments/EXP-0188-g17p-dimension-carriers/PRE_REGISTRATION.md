# EXP-0188 — PRE-REGISTRATION

**Frozen before any build or device time.** Amendments are numbered, dated, and appended in §9;
`raw/prefreeze/CAPTURE_CONTRACT.v*.json` retains every superseded version. Nothing in this file is
edited after the first capture.

**Target:** Apple A18 Pro / **G17P** (`users-MacBook-Neo.local`, `192.168.10.243`, SSH user `user`,
`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal family Apple9).
**Nothing runs on the M4**, which is the repo host and analysis machine only.
**Repo revision pinned at pre-registration: `45d97d6237c9b0324ed97aba7ad0a2aa83193384`.** Captures are
gated on the *authored blob hashes*, never on live `HEAD` — sibling experiments land continuously and
a "HEAD must not move" gate would abort this run through no fault of its own (EXP-0082).

---

## 1. The question

`docs/isa/emit-worklist.md` lists sixteen instructions one field away from emittable, **nine of them
blocked by a field labelled `single-template-inference`** — proven inert on the carriers tried, role
unknown. That label is not emitter-grade, because emitter-grade asserts an implementer may *choose*
the value, and "emit whatever the compiler emitted" is a captured-template dependency.

That label has been overturned five times in the last day, always the same way: **by a carrier that
differs in the dimension the field actually controls.** `iter_at.loc` read inert on every arm of one
experiment because all its carriers were `samples=1`, where centroid and sample are the same point;
at 4 samples it moves 128/256. `get_sr.form` was declined on eight arms and moved on a ninth that
changed *stage*. `tex_sample.samp_extra` read 256/256 inert on nine arms and moves on the
explicit-LOD arm. The rule distilled from those: **eight arms that cannot express a field are one
arm.**

So the question here is not "is field X inert" but:

> For each target field, **what dimension does it plausibly control**, can we build a carrier that
> differs in that dimension, and does the field move there?

A field that stays inert on a carrier that **provably can** express its dimension is a materially
stronger result than the present label — a real `proven-dont-care` — and is reported as such.

## 2. Targets selected, and the four dropped, with reasons

Nine fields were offered. Ranking is by **whether the dimension can actually be built inside this
window**, per the dispatch: *three fields with a carrier that differs in the right dimension beats
nine swept blind.*

| # | field | dimension it plausibly controls | carrier axis built | decision |
|---|---|---|---|---|
| 1 | `if_push.scope` | **REGION KIND**: conditional-skip (`scope_kind` 0x01) vs loop-iteration (0x1a) | six nested / memory-bounded loop shapes | **BUILD** |
| 2 | `iadd2.b2_fmt` | **OPERAND FORMAT / WIDTH**: 16 / 32 / 64-bit, register-vs-immediate srcB, uniform operand | seven integer-add carriers | **BUILD** |
| 3 | `simd_ballot.cache` | **EXECUTION-MASK BANK / divergence depth** | five SIMD carriers at depth 0,1,2,3 + loop | **BUILD** |
| 4 | `simd_shuffle.cache` | same (**width 1**, one bit of a byte that is 0x54 everywhere) | same carriers, free | **BUILD** |
| 5 | `iter.b9` | MSAA / interpolation mode | needs a fragment-stage render harness | **DROP** |
| 6 | `imageblock_store.b4` | imageblock layout / tile memory | needs a fragment-stage render harness | **DROP** |
| 7 | `frag_color_store.store_mode` | MRT count / render-target format | needs a fragment-stage render harness | **DROP** |
| 8 | `vtx_out_pos.slot` | system output slots (`[[point_size]]`, `[[clip_distance]]`, RT array index) | needs a vertex+render harness | **DROP** |
| 9 | `cvt_f2i.b9` | destination width and sign | **already spanned today** | **DROP** |

**Why 5–8 are dropped rather than swept.** All four are fragment- or vertex-stage fields whose
dimensions (sample count, MRT count, imageblock layout, system output slot) are **pipeline-state**
dimensions: expressing any of them requires building and validating a render pipeline harness on
G17P — a render driver, a render-target set, an MSAA resolve path, and a fresh oracle — before a
single value is dispatched. Swept on the compute harness that exists, they would be four more arms
that cannot express their dimension, which is precisely the failure this experiment is dispatched to
stop repeating. They are named as the next experiment's work, not attempted here.

**Why 9 is dropped.** EXP-0184 swept `cvt_f2i.b9` on 2026-08-30 across five carriers spanning
**destination width and sign** (int / uint / short / ushort destinations, float and half sources),
2560 dispatches, with the `dst` control firing on all five. We can name no further dimension for a
byte the descriptor calls reserved, and a sixth arm along the same axis would be one arm.

## 3. Hypotheses, falsifiers, and confounders

### H1 — `if_push.scope` is the reconvergence mask bank, and the bank is only distinguishable in a **loop-iteration** region

`db.json` says `scope` "ping-pongs 0x54/0x56 with nesting parity", and its provenance is
EXP-M4-13 R6: a **loop-nesting ladder** on the M4, compile-only, in which every push carried
`scope_kind == 0x1a`. EXP-0184 swept 256 values across ten occurrences spanning nesting depth 1..3
with every control firing and got **0/2560** — and stated its own limitation: every occurrence was
`0f 05 54 01`, none of its loop shapes emitted an `if_push` at all, and **the 0x1a region kind was
never reached**.

* **Predicted if true:** at least one occurrence with `scope_kind == 0x1a` exists in the new
  carriers, and at that occurrence some subset of the 256 `scope` values changes the 32-lane result
  vector — most likely a partition around 0x54 / 0x56.
* **Refuter A:** an occurrence with `scope_kind == 0x1a` is swept dense, its control fires, and
  **nothing moves**. Then `scope` is a don't-care across region kinds too, which is a real
  `proven-dont-care` and the strongest available negative for this field.
* **Refuter B:** no carrier emits an `if_push` with `scope_kind == 0x1a` at all. Then the dimension
  was not built, the arm has no standing, and the field is reported **STILL-UNDERPOWERED** with the
  compiler shapes tried listed — not as inert.
* **Confounders:** (i) *dispatch geometry* — an unconditional `if_push` with `scope_kind == 0x01`
  masks off the only lane of a **one-thread** dispatch in both banks (EXP-0179), so every carrier
  here is grid 32 / threadgroup 32 and the observable is the full 32-lane vector; (ii) the compiler
  may lower memory-bounded loops without any push, exactly as EXP-0184's `(t & 3) + 1` loops did —
  hence six differently-shaped loop carriers and a census that drops the empty ones as measured
  negatives; (iii) `0f 05` is shared with the 14-byte direct `call` and with `if_push_pred`, so
  occurrences are located by **descriptor signature** and every case records the pinned tokenizer's
  mnemonic for the mutated bytes.

### H2 — `iadd2.b2_fmt` selects an operand format, so it can only move when the operand format varies

EXP-0171 swept all 64 sub-values dense and inert on **one** carrier: a 32-bit unsigned
register+register add. Its detection-power argument is sound (byte+2 moves 128/256 there, via bits
0–1), which makes the null meaningful *for that format* and silent about every other.

* **Predicted if true:** either the compiler's own `b2_fmt` value differs across width/operand-class
  carriers — visible in the census, **before any device time** — or a dense sweep moves on the 16-bit,
  64-bit, immediate-srcB or uniform-operand carrier where it did not on the 32-bit one.
* **Refuter:** `b2_fmt` is the same value in every carrier's compiled code **and** dense-inert on all
  of them with controls firing. Then the six bits are a don't-care across every operand format the
  compiler will produce for us.
* **Confounders:** (i) a 16-bit add may not be an `iadd2` at all — the census drops such a carrier as
  a measured negative rather than mislabelling another instruction's bytes; (ii) `dst` bytes
  0xBE..0xFF are a known contained-fault region in this family (EXP-0139/0146), so `dst` is **not**
  used as a control; (iii) the `store_en` control is one bit — see §6 rule 2 on the gate arithmetic.

### H3 — `simd_ballot.cache` / `simd_shuffle.cache` is an execution-mask **bank** selector, not a cache hint

This is a structural hypothesis about the byte, not about the field's name. Four control-flow
descriptors in this ISA place an execution-mask bank selector at byte+2 in the same low form:
`if_push` 0x54/0x56 ("mask bank", nesting parity), `jump_cond` 0x54/0x64 ("reconvergence mask bank"),
`mask_op` 0x04/0x24 ("execution-mask bank selector"), `pop_reconverge` 0x04/0x24 (the same low-form
selector). `simd_shuffle`'s byte+2 is **0x54 in every occurrence ever observed**, with `cache` as its
0x02 bit — i.e. 0x54/0x56, the `if_push` pattern exactly.

EXP-0163 held both fields INERT-ROBUST across 3–4 carriers built for the dimension the *name*
suggests — operand reuse / last use (`k_scache` maximises reuse distance and register pressure;
`k_sdiv` adds divergence). That axis is spanned. What it did not span is **divergence depth**:
`k_sdiv` is one region deep and every other carrier is zero deep, and **two mask banks are
indistinguishable in a program that is never more than one region deep** — the `iter_at.loc` failure
transposed onto divergence.

* **Predicted if true:** at depth ≥ 2, or inside a loop-iteration region where the active set shrinks
  between iterations, some `cache` value changes which lanes the ballot/shuffle sees.
* **Refuter:** dense-inert at depths 0..3 and in the loop region with controls firing. Then the byte
  is a don't-care across mask-bank structure, and the reuse-hint reading stands unrefuted but
  unsupported.
* **Confounders:** (i) reading an **inactive** lane through a shuffle is undefined, so every
  divergence condition tests bit 2, 3 or 4 of the lane id and the active set is always a union of
  whole 4-lane quads — `simd_shuffle_xor(v,1)` and `(v,2)` therefore always read an active lane;
  (ii) `simd_ballot` under divergence is scored against active-lanes-only semantics, the single
  assumption in the oracle, **calibrated pre-freeze** against the unmutated carrier — a carrier whose
  unmutated baseline does not match its oracle is dropped before the contract is frozen, not repaired
  afterwards; (iii) `simd_shuffle.cache` is **width 1**: a null covers two values of one bit and must
  not be reported as "byte+2 of simd_shuffle is inert".

## 4. Independent and controlled variables

* **Independent:** the value of the target field at one located occurrence — nothing else in the
  program changes between cases.
* **Controlled and identical across every case of an arm:** carrier source, compile flags
  (`--no-fast-math`), dispatch geometry, input buffers, output poison, the located offset.
* **The dimension** is varied **between carriers/occurrences**, never within an arm.
* **The observable does not co-vary with the field** (protocol 3a): every swept field lies inside the
  instruction under test, and every observable is a fixed-address result word written by a separate
  store that the field cannot name or relocate. This is the defect that made EXP-0140's
  `uniform_mov.dst` sweep return its passing result by construction.

## 5. Instruments (protocol §7), all three, on every case

1. **Poisoned read-back.** The output slot is bound as an input pre-filled with
   `POISON(i) = 0xDEADBEEF + i`. A word still holding its poison was **never written**, which against
   a zero-initialised buffer is indistinguishable from a genuine silent zero. EXP-0160 saw 25
   dispatches report `STATUS OK` and write nothing at all with no victim string.
2. **Integrity sentinel** `0x5A5A1234`, stored **before** any divergent region, through a path
   independent of the instruction under test. A measurement without it is `invalid_run`, re-run, never
   scored. **Absence of a fault proves nothing** — the sentinel and the poison are what prove the
   program ran.
3. **OS fault-classification string** recorded on every non-`ok` case;
   `kIOGPUCommandBufferCallbackErrorInnocentVictim` cases are retried first and segregated.

Every oracle is **host-computed by simulating our own MSL**, and every expected value is **non-zero**
(asserted at import): a zero oracle would score Apple9's characteristic silent zero as a pass.

**Seeding.** Operands arrive from device memory because that is what makes the carriers differ in
width, but no spliced instruction's source is seeded *from* an asynchronous `device_load` result in
the sense the dispatch warns about: the splice is on the instruction's own control byte, the
read-back is poisoned, and the baseline is re-taken at arm open, mid-arm and arm close.

## 6. The gate — the only thing that may promote a field

1. **Two gated runs**, byte-identical programs, the same frozen `arms188.json`.
2. **≥ 99 % per-value cross-run agreement** on the outcome partition, **and**
   `moved >= 2 * disagree AND moved >= 1`.
   **Explicitly NOT `moved >= 2 * max(disagree, 1)`**: that form demands `moved >= 2`, which no
   width-1 field can ever produce, so it refuses such fields by arithmetic rather than by evidence.
   EXP-0178 found it suppressing a real result. **`simd_shuffle.cache` is width 1** and would be the
   next casualty.
3. **Detection power.** At the arm's occurrence, at least one control — a field of the *same*
   instruction at the *same* offset, already known live — must have moved. **No control here is a
   match byte**: changing a match byte changes which instruction the bytes are, which produced a
   false "inert" on the M4 today and withdrew two fields. Every case additionally records the pinned
   tokenizer's mnemonic for the mutated bytes and every row reports `encodable_range`.
4. **Baselines** at arm open and arm close must both be `ok`.
5. **Measurement failures** (`MALFORMED`, protocol 3d) are removed from the agreement computation and
   from `values_dispatched`, never scored as `ok`, `fault` or inertness; a field above a 1 %
   measurement-failure rate is refused outright.
6. **For a never-moving field**, rule 2 is satisfiable only by the carrier set spanning the dimension
   the field controls, and the spread actually achieved is emitted in `dimension_spread` so a
   reviewer can check it instead of taking it on trust.

Labels: LIVE → `hardware-run`; INERT-ROBUST → `single-template-inference` (**not** emitter-grade);
STILL-UNDERPOWERED → `untested`. No rounding up.

## 7. Method

7.1 **Carriers** — `kernels/k_cf188.metal` (6 control-flow shapes), `kernels/k_sd188.metal` (5 SIMD
shapes), `kernels/k_ia188.metal` (7 integer-add shapes); all authored by us, compiled on the neo by
our own `shdump` through the public `newLibraryWithSource:` path with `--no-fast-math`.

7.2 **Location** — by **descriptor signature** from this experiment's **pinned** `db.json`/`isadb.py`
(`harness/locate188.py`), with a hard exit if the pinned copies are absent. `tools/agx-isa/isadb.py`
and `db.json` are owned by concurrent experiments (EXP-0182 / EXP-0183) and nothing here resolves
through them.

7.3 **Pre-freeze census** (`analysis/census.py`) — calibration only; **no verdict may cite it**. It
records which carriers compile, which emit the target instruction, at which offsets, with which
compiled value of the target field and of the dimension field, and what the pinned tokenizer decodes
there. Its output lands in `raw/prefreeze/census.json`.

7.4 **Arm selection** (`analysis/gen_arms.py`, frozen rule, reproduced in its docstring) — carriers
with no occurrence are dropped as measured negatives; only parcel-aligned occurrences are swept;
occurrences are ordered so **the dimension spreads first** (an unseen `scope_kind` before a repeat),
then an unseen baseline value, then by offset; every target arm dispatches the field's full dense
range for width ≤ 8; controls are sampled.

7.5 **Sweep** (`run.py`) — one JSON object per case appended to `raw/<run_id>/sweep.jsonl` and
`flush`+`fsync`'d immediately. **NO ABORT PATH and no hang budget anywhere**: a per-field budget
cannot characterise a contiguous hazard, it guarantees the region is never mapped (protocol 3c;
`frag_color_pack.dst`'s wall at 0xC0 was missed by three experiments this way). Every value of every
arm is dispatched. Non-`ok` cases go to majority-of-3 with `InnocentVictim` retried first; a dispatch
that reports OK and writes nothing is `invalid_run`, not a silent zero.

7.6 **Runner** — `harness/saferunner188.py`, the EXP-0178/0185 leak-free subclass: **one reader thread
per child, tagged by owner**, and a malformed response returned as `MALFORMED` rather than raised. A
mere watchdog timeout on the shared `persistrun.py` starts a false-hang cascade in which one benign
case poisons every later request, and **a false hang is indistinguishable from real inertness in a
summary**. The shared tool is not modified: siblings run against it concurrently.

7.7 **Remote verification** — `harness/verify_remote.py` is run as **its own command** after every
push, and its exit code is read. A frozen contract hashes what we *authored*; it says nothing about
what the *device* is running. It caught 7 of 18 blobs missing or stale against its own author on its
first run, and EXP-0179 burned a run id by chaining a capture behind a push that failed silently.

7.8 **Concurrency** — sweeps run **unlocked and concurrent** with EXP-0187 per protocol §7; there is
no GPU lease. `concurrent_gpu_procs` is sampled into each run's `env.json`, so "the machine was busy"
is a measurement and not a claim.

## 8. Timeouts, safety, recovery

* Per-request watchdog **8 s**; compile 600 s; remote command 120 s.
* `PROGRESS.md` after every milestone; `raw/` written incrementally; a kill costs at most one case.
* Run ids are **never reused**; a partial capture is retained as-is and the replacement takes a new id.
* If the neo stops answering: **STOP and report BLOCKED**. `macvdmtool` is forbidden to this agent.
* Courtesy note (protocol §7): no arm here sweeps a known hazard region — `iadd2.dst` is deliberately
  not swept, and EXP-0184 measured 0 hangs over 14,352 dispatches of `if_push` byte+2 on a 32-lane
  dispatch. If a hang appears it will be recorded in `PROGRESS.md` with the encoding.

## 9. Amendments

*(appended below, numbered and dated; superseded contracts retained in `raw/prefreeze/`)*

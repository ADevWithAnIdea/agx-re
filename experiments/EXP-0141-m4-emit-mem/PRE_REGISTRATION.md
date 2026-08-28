# PRE-REGISTRATION — EXP-0141 M4 memory/atomic/fence family: emission, not decoding

**Frozen:** 2026-08-28, before either gated run.
**Target:** local Apple M4 / G16G only (`Mac16,10`, macOS 26.6.2). A18 Pro is
hands-off; M5 is out of scope. Every claim below is an M4 claim.
**Repository revision pinned at pre-registration:** `f17938ee0105c8f1fb1e1c25be3aa22fa4a77a5c`
(dirty: sibling experiments EXP-0133/0139/0140 untracked). Per `SUBAGENT_BRIEF.md`
this revision is **recorded, not gated**: a capture is valid if the authored blob
hashes in `CAPTURE_CONTRACT.json` match, regardless of where `HEAD` moves.

---

## 1. Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DOC-02 / `docs/evidence-classification.md`:
58 of the 81 fields of the ten memory/atomic/fence instructions
(`atomic_mem atomic_rmw atomic_tg dev_scoreboard_fence device_load device_store
mem_fence mem_fence8 tg_addr_compute threadgroup_barrier`) are below
emitter grade, and the family gates every load, store and atomic a compiler emits.

The single named blocker is `device_load.dst_lo` / `dst_ext9`
(`single-template-inference`): `EXP-0112`'s generator produces 100 correct random
DAGs only by copying these two fields **verbatim** from a compiled shader.
`EXP-0101` established that the ALU-visible destination register is
`device_load.extmode / 2` and that `EXP-M4-13`'s `dst = dst_lo | (dst_ext9 << 2)`
is **refuted**, but it never swept `dst_lo`/`dst_ext9` — it only showed that
`(1,1)` works and that four derived alternatives break the load.

**This experiment asks: as a function of the target register, what must
`dst_lo`/`dst_ext9` contain — or are they derived / inert / a descriptor of
something else entirely?** And, for the remaining 56 fields: can an emitter
choose arbitrary values, and what happens when it does?

## 2. Hypotheses, each with its pre-registered refuter

**H1a — `extmode` is a register selector with a don't-care low bit.**
The ALU-visible destination is `extmode >> 1`; `extmode` bit 0 is a don't-care.
*Predicted observation:* over `extmode` = 0..255 DENSE, each paired with a
consumer reading `r(extmode >> 1)`, the program yields `-7.0` for every value
except where the target register is itself unusable (`EXP-0112`: `r126/r127`
fault; `R in [64,112]` aliases `r(R mod 64)`, which this program tolerates
because the consumer's own register field aliases identically).
*Refuter:* an even `extmode` whose paired consumer silently zeroes, or an odd
value behaving differently from its even neighbour.

**H1b — `dst_lo`/`dst_ext9` do NOT encode the target register.**
The SET of `(dst_lo, dst_ext9)` pairs that keep the load working is **identical**
at target registers 3, 7, 20 and 33.
*Refuter:* the working set differs between any two of those target registers —
which would mean the pair IS (part of) a register field and `EXP-0101`'s
"copy it verbatim" advice is target-dependent.

**H1c — the working set is larger than the single verbatim token `(1,1)`.**
`dst_ext9` was originally named `dst_width`; we predict the pair is a
destination *descriptor* (width/count/valid), so a structured subset of the 512
encodable combinations will work, and that subset will be describable as a rule
an emitter can apply.
*Refuter (explicitly registered as the live alternative):* exactly one of the
512 combinations works at each target register, i.e. the field really is an
opaque per-shape token and the family stays "decodable, not yet emittable".

**H2 — `device_store.addr_mode` bit 1 is a live DATA-SOURCE selector, not inert.**
`0x54` selects the ALU-computed source, `0x56` the direct live load-result. This
CONTRADICTS `validation.json`'s current `device_store.addr_mode` range text
("bit1 ... INERT here", `EXP-0119`), which was measured only with an
ALU-computed source.
*Predicted observation:* in the ALU program `0x54` works and `0x56` fails (or
vice-versa); in the load-forward program the opposite. *Refuter:* both values
work in both programs (genuine inertness).

**H3 — exactly one byte of `atomic_mem` selects the RMW operand register.**
`db.json`'s own semantics say the operand register "is implicit (supplied by the
preceding op / amode)" and `DOC-02` ranks this a **missing field**. The carrier
keeps `a[1] = 1007`, `a[2] = 2007`, `a[3] = 3007` live across the atomic while
`a[0] = 7` is the operand.
*Predicted observation:* some value of some byte in `+1..+13` makes the counter
read 1007 / 2007 / 3007 (or their sum/AND with 0), identifying the selector.
*Refuter:* no byte value in the whole 13 x 256 dense sweep ever produces a
counter equal to any of the other live registers — the operand really is not
encoded in the instruction.

**H4 — `threadgroup_barrier.flags` (byte+4) and `b5` (byte+5) do not carry the
fence.** `mem_scope` (byte+3) does. *Predicted observation:* all 512 swept
values of `flags`/`b5` leave the 256-lane tile litmus exact. *Refuter:* some
`flags` value reproduces the stale-read failure with `mem_scope` intact.

**H5 — `tg_addr_compute`'s byte0 high nibble and byte+1 are operand selectors
that `db.json` does not model** (`EXP-M4-14`, A18). *Predicted observation:*
a dense M4 sweep of byte0, byte+1, byte+2 changes the tile dataflow for some
values and not others, and the map is recoverable. *Refuter:* both bytes are
inert on M4 (which would be an A18<->M4 divergence, reported not resolved).

**H6 — `dev_scoreboard_fence.scope_flag` accepts arbitrary values.**
No own-MSL kernel we could compile emits `80 02 00 xx`, so the instruction is
SYNTHESISED into the validated load->ALU->store program. *Predicted
observation:* all 256 `scope_flag` values execute and leave the surrounding
dataflow at `-7.0`. *Refuter:* some value faults or corrupts the dataflow.
**Declared limitation, frozen now:** this carrier has no memory-ordering
observable, so a pass bounds *acceptance and dataflow-inertness only* and will
NOT be labelled `hardware-run` for ordering semantics.

## 3. Independent / controlled variables

Independent: exactly one field (or one byte) per case. Controlled: everything
else in the program, the carrier, the dispatch shape, the input buffers, and the
oracle. Coverage per `FIELD-SWEEP-PROTOCOL.md` 3.3: every field of width <= 8
is swept **densely over all 2^w values**; the one wider field pair
(`dst_lo` x `dst_ext9`, 9 bits) is swept over its **full 512-value product**.

## 4. Oracles

Host-computed in `carriers.py` from the MSL **we wrote**, never read off a GPU
run, and checked against the UNSPLICED carrier before any mutation:

| carrier | oracle |
|---|---|
| `synth` | per case: `-7.0` (load -> falu2i(+1.5) -> store) or `-8.5` (load -> store forward) |
| `atdev` | `o[0] = 7`, `dbg = [1007, 2007, 3007, 0]` |
| `atdevimm` | `o[0] = 5000`, `dbg = [7, 1007, 2007, 3007]` |
| `attg` | `o[0] = sum(a[0..15]) = 120112`, `o[1] = a[8] = 8007` |
| `tgtile` | `o[i] = ((i+1)&255) + ((i+2)&255)` for all 256 lanes |
| `devfence` | `o[i] = 65558 + i`, `c = 65558` |

Silent-zero signatures are pre-declared: `out0 == 1.5` (ALU program, `srcA` read
as 0), `out0 == 0.0` (forward program), all-zero output (splice carriers).

## 5. Falsifiers (arm `CTRL` / `CTRL_SPLICE`, `expect_match = False`)

1. `device_load` `dst_lo=dst_ext9=0` with `extmode` correct -> must silently zero.
2. `device_load` `extmode = 0` with the consumer reading `r7` -> must silently zero.
3. `device_store` forward-source store with `addr_mode = 0x54` -> must store 0.
4. `atomic_mem` op `add(0x20) -> and(0x22)` -> counter must become 0, not 7.
   (`xchg(0x3C)` was **rejected** as a falsifier during harness smoke: with a
   zero-initialised counter both `add` and `xchg` yield 7, so it could not
   detect the change. Recorded here rather than silently swapped.)
5. `atomic_tg` op-selector bit flip -> the threadgroup reduction must change.
6. `threadgroup_barrier` `mem_scope 0x61 -> 0x00` -> the tile litmus must break.

A run in which any `expect_match` case disagrees with its prediction is a STOP,
not a result to be reinterpreted.

## 6. Known confounders, and how each is handled

1. **Innocent-victim transients.** A GPU fault poisons subsequent command
   buffers, which return `kIOGPUCommandBufferCallbackErrorInnocentVictim /
   Discarded (victim of GPU error/recovery)`. Handled by a bounded retry that
   fires ONLY on that error text; every attempt's status is kept in the record.
   Established in this experiment's own pilot (`PROGRESS.md` M3).
2. **Archive-path reuse.** Overwriting one splice archive filename across
   persistent-runner requests produced 28/360 spurious `CMDBUF_ERROR` on
   byte-identical known-good archives; a unique path per request gave 0/360.
   Every request now gets its own inode. (Pilot, `PROGRESS.md` M3.)
3. **Register aliasing.** `EXP-0112`: a register field value R in [64,112]
   aliases `r(R mod 64)`; 126/127 fault. The index register is chosen per case
   to avoid the swept target's alias class (`isa_helpers.pick_idx_reg`).
4. **`mov_imm` width.** `dst` is 4 bits and `imm7` is 7 bits (`EXP-0128`:
   128..255 silently zero), so the index register lives in r0..r15 and only ever
   holds 0.
5. **Re-tokenization.** Sweeping a byte that participates in another
   instruction's `match` (e.g. `device_load` byte+1 == 0x01 is `atomic_mem`'s)
   changes how OUR decoder reads the program. The round-trip result is recorded
   per case (`"rt"`), never asserted, except on controls where a failure is a
   build-time stop.
6. **Buffer initialisation.** The atomic oracles assume zero-initialised output
   buffers; verified 120/120 unmutated runs per carrier in the pilot.
7. **Padding.** Synthesised programs pad with `mov_imm(r13,0)` AFTER `stop`, so
   padding never executes.

## 7. Frozen procedure

Two independent gated runs, `m4-20260828-run01` and `m4-20260828-run02`, each
into its own append-only `raw/<run_id>/`. Run 02 is a full independent repeat,
not a top-up. Per-case record appended and `fflush`+`fsync`ed immediately.
`PROGRESS.md` entry per milestone. Per-request watchdog 8 s; per-arm hang budget
2 (arm ABORTED and reported PARTIAL); per-carrier hang budget 6.
**No `db.json`, `validation.json`, `docs/`, `PROVENANCE.md` edits. No `git commit`.**

## 8. Disclosed pilot

Mechanics-only pilot runs were made into `work/` (never `raw/`) before freezing:
carrier compilation, oracle checks against the UNSPLICED kernels, persistent-runner
throughput, the two harness defects in section 6.1/6.2, and a rerun of
`EXP-0101`'s own known construction. The pilot established that the harness can
see a difference; it did not test any hypothesis in section 2. Pilot artifacts
are retained in `work/` and are not evidence.

## Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal), our own hand-assembled AGX
  programs (tools/agx-isa isadb.assemble), our own compiled shader bytes
Apple binary introspection: NONE
Reproduction: python3 -B run.py --run-id <id> --execute
Evidence: raw/<run_id>/sweep.jsonl (append-only), raw/<run_id>/00_manifest.json
```

---

# AMENDMENT 1 — 2026-08-28, BEFORE any capture (`raw/` empty)

`experiments/FIELD-SWEEP-PROTOCOL.md` gained a new binding section 7
(*"Concurrent sweeps CONTAMINATE each other"*, commit `43c7cb0d`) after this
pre-registration was first frozen and before this experiment captured anything.
This experiment is batched with **EXP-0139 (IALU)** and **EXP-0146 (integer
misc)** on the same GPU. Nothing in section 2 (hypotheses) or section 4
(oracles' arithmetic) changes; the amendment strengthens the *measurement* so a
sibling's fault cannot become one of our labels. `raw/` was empty when this was
written, so amending is legitimate rather than post-hoc.

## A1.1 What the protocol now requires, and what was built for it

1. **No `fault` from one observation.** A non-`ok` verdict of any kind is
   re-measured until two observations agree or three have been made; the
   verdict is the majority. `fault`/`hang` additionally require the failure to
   reproduce in >= 2 of 3 attempts. A case with no majority is recorded
   `nondeterministic`, never `fault`.
2. **OS fault classification recorded.** Every record carries `fault_classes`
   (e.g. `kIOGPUCommandBufferCallbackErrorInnocentVictim`) and
   `innocent_retries`. Innocent-victim-class failures are retried (bounded, 6)
   and **segregated**: they never by themselves make a case a fault.
3. **Mid-run baseline health checks.** The unmutated carrier is re-measured at
   every carrier's start and end and every 100 cases. A failure restarts the
   runner process and re-checks; a second failure declares a **cascade**, stops
   that carrier, and is recorded in `raw/<run>/01_progress.json` — the cascade
   is not recorded as field data.
4. **Concurrency recorded.** `raw/<run>/01_progress.json` carries a `ps`
   snapshot of sibling GPU-runner processes at the start and end of the run.

## A1.2 A THIRD contamination mode, found while implementing the above

Under sibling GPU load a command buffer can return **`STATUS OK` having
executed nothing**: the output buffer comes back at its zero-initialised
contents. This is materially worse than an innocent-victim fault, because for
this ISA an all-zero readback is the *expected* signature of a wrongly-encoded
field ("silent zero"), so the artifact forges a real-looking negative result.
It was caught by the amendment's own smoke: the **pre-registered baseline**
`synth/_baseline` — EXP-0101's HW-VALIDATED construction — read back a wrong
value with `STATUS OK`, and the `attg` carrier's unmutated health check
returned all zeros with `STATUS OK`.

**Mitigation: an integrity sentinel in every carrier.** Each carrier now writes
a fixed value through a path that does not involve the instruction under test —
`out[4] = 8.0`, written by `mov_imm`/`falu2i`/`device_store` *before* the swept
instruction, for the synthesised programs; an unconditional first store
(`0xA5A5A5A5`) for each own-MSL splice carrier. A measurement whose sentinel is
absent is **INVALID**: it is repeated (up to 4 times) and, if never obtained,
recorded `invalid_run` and excluded from verdicts. It is never read as a
property of the swept value.

The synthesised sentinel must use `falu2i` `mods = 0` and not EXP-0101's
`0xC0`: `0xC0` is required only when the `falu2i` operand is `device_load`
-sourced and it *breaks* the `mov_imm`-sourced seed (pilot, `work/canary`).

## A1.3 The barrier litmus was too weak to falsify anything — replaced

`kernels/tg_tile.metal`'s first two shapes could NOT detect a neutralised
barrier, so the `threadgroup_barrier` arm would have proven nothing:

| tile litmus shape | barrier spliced out |
|---|---|
| `o[li] = tile[li+1] + tile[li+2]` (every lane writes its own slot) | litmus still PASSED |
| `o[li] = tile[li+128] + tile[li+37]` (cross-SIMD-group reads) | litmus still PASSED |
| **lane 0 fills the whole tile, all 256 lanes read it** | **224 / 256 lanes read stale zeros, deterministically** |

224 = 256 - 32 is exactly the set of lanes outside lane 0's own 32-lane SIMD
group. Both neutralisations (`mem_scope 0x61 -> 0x00`, and physically replacing
the 6 barrier bytes with three `mov_imm`) give the same 224. The falsifier
`_falsifier_barrier_off` is therefore live; its *outcome label* wobbles between
`wrong_value` and `nondeterministic` because the `mem_scope = 0` splice
sometimes also faults, but `match = False` is stable, which is what is
pre-registered.

## A1.4 Amended acceptance state

Re-verified after the amendment, three consecutive control-only runs: 13/13
controls give an identical outcome vector each time, all 6 falsifiers fail as
pre-registered, all baselines hold, **0 / 36 health checks failed**. All six
carriers' host-computed oracles re-verified against the UNSPLICED kernels.
`CAPTURE_CONTRACT.json` re-frozen over the amended blobs before run01.

---

# AMENDMENT 2 — 2026-08-28, after a partial capture was stopped

`m4-20260828-run01` was stopped by me at 3240/20529 cases on a HARNESS defect
introduced by AMENDMENT 1: a reproducibly faulting case has **no output at
all**, so its integrity sentinel is trivially absent, and the canary loop
therefore retried every real fault 12+ times and mislabelled it `invalid_run`
instead of `fault`. `device_load.index_reg >= 96` faults reproducibly (the known
r95/r96 boundary), so that arm became a fault storm.

**Fix:** a `fault`/`hang` verdict — which `issue()` has already reproduced in
>= 2 of 3 non-innocent attempts — short-circuits both the canary loop and the
outer majority loop. Nothing about the hypotheses, oracles, coverage or
falsifiers changes.

**The partial capture is RETAINED and its id is NOT reused**
(`raw/m4-20260828-run01/PARTIAL.md`). The gated runs are renamed
`m4-20260828-run11` / `m4-20260828-run12`, and `CAPTURE_CONTRACT.json` is
re-frozen over the amended blobs.

---

# AMENDMENT 3 — 2026-08-28, ADDENDUM MATRIX for `atomic_rmw`

Frozen after `m4-20260828-run11` and before the addendum captures
`m4-20260828-run21` / `run22`. It does not touch the main matrix or its
captures.

**Why.** Both of this experiment's device-atomic carriers compile to
`atomic_mem` (byte+1 == 0x01). `atomic_rmw` differs from it only in byte+1
(0x11) and shares its field layout in `db.json`. Run 11's
`atdev_atomic_mem_b1` arm shows that byte+1 == 0x11 executes correctly in the
same carrier with everything else unchanged — but that is evidence about
**byte+1**, not a per-field sweep of the 0x11 form. Labelling `atomic_rmw`'s 14
fields from `atomic_mem`'s sweeps would be exactly the strength mismatch
`docs/evidence-classification.md` was written to prevent (it is the same error
as `EXP-M4-13`'s `device_load` destination formula: a correlation promoted as
though it had been executed).

**H7.** With byte+1 pinned to 0x11, each of bytes +2..+13 swept densely over all
256 values yields the SAME accepted-value set as the corresponding
`atomic_mem` arm.
*Refuter:* any byte whose accepted set differs between the two forms — which
would mean the two mnemonics do not share a field layout and `db.json`'s
"identical field layout" note is wrong.

**Matrix.** 13 arms, 3 074 cases: one control arm (baseline + the same
`op add -> and` falsifier, both with byte+1 pinned) and twelve dense byte
sweeps. Same carrier, same oracle, same robustness machinery, same two-run gate.
If the addendum is absent or fails its gates, `atomic_rmw`'s fields keep their
prior labels and `analysis/field_verdicts.json` says so explicitly under
`atomic_rmw._NOT_CLOSED`.

## AMENDMENT 3b — two more addendum hypotheses, frozen with it

**H8 — the `dst_lo`/`dst_ext9` rule is INDEPENDENT of `ld_format`.**
`EXP-0101`'s operational advice was to copy the pair verbatim "from a
compiler-observed `device_load` of the same `addr_mode`/`ld_format` shape",
which implies a per-shape token. The main matrix swept the pair at four target
registers but at ONE `ld_format` (0x11). This arm re-runs the **full 512-value
2-D product under each of the 21 `ld_format` codes that work** (taken from
run11's own `L_ld_format` arm as a covariate, not as a hypothesis).
*Predicted observation:* the accepted set is `v & 0x181 == 0x81` under every one
of the 21 codes. *Refuter:* any `ld_format` under which the accepted
(dst_lo, dst_ext9) set differs — which would restore "it is a per-shape token"
and mean the emitter rule in section 0 is incomplete.

**H9 — the atomic operand-register index is
`(byte+5 >> 7) | ((byte+6 & 0x3F) << 1)`.**
The main matrix moves one byte at a time and therefore only ever built indices
0, 1 and 2; the `<< 1` multiplier is interpolated from two points. This arm pins
`byte+5 = 0x80` and sweeps `byte+6` densely, constructing **index 3** for the
first time. *Predicted observation:* `byte+5 = 0x80` with `byte+6 = 0x01` makes
the atomic add **`a[3]` = 3007**, and `a[3]`'s later reader then reads 0.
*Refuter:* index 3 does not select `a[3]` — in which case the two-byte model is
wrong and only the three individually-constructed points stand.

Addendum matrix after 3b: **35 arms, 14 082 cases**, still two independent
gated runs (`run21`, `run22`) with the same robustness machinery and gates.

## AMENDMENT 3c — H10, frozen with the rest of the addendum

**H10 — `device_store.extmode` is the SOURCE REGISTER (`extmode >> 1`), and its
bits 6-7 are a modifier, not register bits.** The main matrix swept it with the
stored value in ONE register (r8) and accepted only `{16, 208}`: 16 = 2*8 as
`EXP-0090`'s formula predicts, and 208 = `16 | 0xC0` unexplained. This arm
repeats the dense sweep with the ALU result in **r4 and r12** as well.
*Predicted observation:* the accepted set MOVES to `{8, 8|0xC0}` and
`{24, 24|0xC0}` respectively. *Refuter:* the accepted set does not move — which
would mean `extmode >> 1` is not the store's source register and the r8 result
was a coincidence of that one register.

Addendum matrix after 3c: **39 arms, 14 853 cases.**

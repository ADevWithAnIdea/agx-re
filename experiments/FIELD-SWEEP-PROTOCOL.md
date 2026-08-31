# Field-sweep protocol — how to move a field to `hardware-run`

**Read with** `../CLAUDE.md`, `../CODEX.md`, `SUBAGENT_BRIEF.md`, and
`../docs/evidence-classification.md` (the label definitions this protocol serves).

**Purpose.** 777 of 1026 ISA fields are not emitter-grade, and the goal is to *emit* every real
instruction, not merely decode it. This protocol defines what a sweep must prove and what it must
record, so eleven agents working in parallel produce evidence that merges mechanically instead of
eleven incompatible harnesses.

---

## 1. The bar you are clearing

From `docs/evidence-classification.md` §2:

> `hardware-run` requires that **arbitrary operands executed**, not that the instruction executed.
> To claim it you must have run values the compiler would not have chosen — boundaries, holes, and
> out-of-range — and recorded what happened, including the silent zeros.

Compiling a shader that happens to use the field is **not** evidence. Round-trip is **not**
evidence. You are proving an emitter can choose a value and get the documented behaviour.

## 2. Use the existing tools — do not rebuild them

- `tools/agxtest/agxrun_persist` + `tools/agxtest/persistrun.py` — the persistent runner. One live
  device for the process lifetime, **logs and continues past contained command-buffer faults**, so a
  256-value sweep is one launch, not 256. It already has the per-request watchdog.
- `tools/agxtest/agxrender.m` — the render/fragment analogue, for FRAG/TEX/varying work.
- `tools/shdump/` — compile our MSL, locate `_agc.main` for in-place splicing.
- `tools/agx-isa/` — `db.json` is now the **single source of truth** (`isadb.py` loads it).
  Use `isadb.py` to assemble/disassemble; do not hand-compute byte offsets.

## 3. Required sweep shape, per field

> **Two rules added 2026-08-30, each found the hard way. Read them before designing an arm.**
>
> **(a) The observable must not CO-VARY with the field under test.** EXP-0140 swept
> `uniform_mov.dst` while building its read-back as `device_store(data_reg=D)` where `D` *was*
> the swept dst. Field and observable moved together, so a **correct** hardware result is a
> constant observed vector *by construction* — "16 values, 0 moved" was the **passing** outcome
> of a test that could not return anything else. It cannot see an aliased extra write, and its
> register scan ran at a single dst value. Found by EXP-0168. This is the same failure as
> `iter_at.loc` one level up: there the *carrier* could not express the field; here the *oracle*
> could not.
>
> **(d) ON THE SHARED DRIVER, THE FIRST HANG CAN SILENTLY MANUFACTURE EVERY HANG AFTER IT.**
> `tools/agxtest/persistrun.py` and the `rsdrv.py` render driver start a **fresh reader thread per
> line and abandon it on timeout**, and that thread **re-resolves `self.proc` at execution time** — so
> after the first watchdog timeout the abandoned thread wakes on the **replacement child's** stdout and
> races the foreground reader. Responses return truncated (`OUT 0 ` with the hex missing), the shared
> parser raises `ValueError: not enough values to unpack`, and the run dies. In EXP-0178's pilot **one
> benign case poisoned every later request including the unspliced health check, and three consecutive
> cases were recorded `hang` with `restarts=99` — all false.** This is the sibling of DEF-0153-2 (the
> EOF spin fixed in the same file); the reader-thread lifetime bug is separate.
>
> Two consequences. **A false `hang` and a real inertness are indistinguishable in a summary**, so a
> sweep that hits one genuine hang can withdraw fields for an artefact. And **any experiment that
> recorded a cascade of hangs after a first real one may have a tail of artefacts** — EXP-0163 alone
> recorded 88 non-OK cases, most hangs by design.
>
> **WIDENED 2026-08-30 — a REAL hang is not required to start the cascade; a mere WATCHDOG TIMEOUT is
> enough.** EXP-0178 verified by hand, outside the harness, that its pre-registered hang candidate is
> not a hang at all: clearing byte0 bit 2 of a `get_sr` anchor runs clean on G17P with `STATUS OK`,
> `GPUTIME_NS 5000` and the integrity sentinel written. **All four "hangs" in its pilots were
> manufactured by the reader-thread defect on a case the hardware handles without complaint.** So the
> suspect set is not "experiments that hit a real hang" but **any experiment whose runner ever timed
> out** — a far larger set. Treat a hang cascade as unproven until re-measured on a runner with a
> per-child reader thread.
>
> Until the shared tool is fixed: **one reader thread per child, tagged by owner**, and **record a
> malformed response as a MEASUREMENT FAILURE with the raw lines kept — never as a hang.** A malformed
> response is not an observation and must not be scored as one. EXP-0178's `harness/saferunner.py` is
> the reference subclass; it deliberately did not modify the shared tool while a sibling ran against it.
>
> **(c) A per-field hang budget CANNOT characterise a CONTIGUOUS hazard — it guarantees the region is
> never mapped.** `frag_color_pack.dst` has an exact wall: **0x00..0xBF all clean, 0xC0..0xFF all hang,
> contiguous with no exceptions**, so `dst[7:6] == 0b11` is illegal and the encodable range is **192, not
> 256**. Three experiments walked into it and none saw it, because with a budget of 2 each run discovers
> exactly **two** more hazardous values and stops: one halted at 194, the next at 197, the next at 199.
> EXP-0168's own "defer the known-bad values" fix was inadequate — **it only moved the wall, twice.** A
> budget meant to protect the machine had become a guarantee that the region could never be characterised.
> So: when hangs at adjacent values suggest a **contiguous** hazard, stop treating it as a per-value
> accident. Declare a named, non-gated **mapping pass** that deliberately overrides the frozen safety
> parameter, say so in the run id (EXP-0168 used `MAPPING_..._hangtolerant`), and dispatch the whole range.
> The device survived all 64 hangs — no reset, no wedge, no `macvdmtool`.
>

> **(b) A round trip is NOT an emitter gate.** `assert_round_trip()` — 28 files define it, 7
> distinct bodies, all semantically identical and **all symmetric** — disassembles and then
> re-assembles *from the disassembled fields*, so a defect symmetric across encode and decode
> sits on both sides and the check passes. EXP-0170 proved this rather than arguing it: it
> re-implemented the pre-fix OR-only assembler (which **could not clear a bit**) and re-ran the
> repo's own suite against it — **173 cases, 0 failures**, including 9 touching an affected field.
> **`tools/agx-isa/roundtrip_test.py` passes unmodified with a broken assembler.** It is a
> tokenizer regression test and must stop being cited as evidence that an encoding can be
> *emitted*; `rt_ok` in any raw from EXP-0090…0171 means only "our tokenizer agrees with itself".
> The right shape compares against **the caller's ledger** (EXP-0167 did this: 204,044 calls,
> 0 mismatches) — and even that misses the defect when its vectors are seeded from really-observed
> instructions, since their values already carry the `match` bits. Circular provenance.


For field `F` of width `w` in instruction `I`:

1. **Baseline.** Capture the unmutated program's output first. Every later case is a delta against it.
2. **Carrier.** State which carrier shader you spliced into, and why the field is *live* on the
   observed output path. A field whose value cannot reach the output proves nothing —
   EXP-0129 lost its fragment-stage arm exactly this way, and reported it rather than faking it.
3. **Coverage:**
   - `w <= 8` → **sweep all 2^w values**, densely. This is cheap on the persistent runner.
   - `w > 8` → boundaries `{0, 1, 2, max-1, max}`, all power-of-two values, and ≥16 interior
     samples including asymmetric ones. Never only 0/1.
4. **Oracle.** A host-computed expected value per case, independent of the GPU. Say how it was
   derived. "It looked right" is not an oracle.
5. **Falsifier.** At least one case pre-registered to *fail*. If everything passes, the sweep proves
   nothing about your ability to detect a difference. EXP-0136's address-mode code 5 is the model:
   it showed the method could still see a real difference.
6. **Record the silent zeros.** On Apple9 a wrong field value usually yields a **silent zero, not a
   fault**. A value that produces zero is a *result*, not a skipped case.

## 3z. PRECONDITION: prove the offset is an instruction BOUNDARY before sweeping it

**Adopted 2026-08-30 from EXP-0200. Run this BEFORE any field sweep at a signature-derived site.**

`isadb.decode_one` answers *"do these bytes match a descriptor"*. It never answers *"does an
instruction START here"*. Those are different questions, and the corpus has been conflating them:
EXP-0200 scanned 7 signature-derived occurrences and **0 of 7 were boundaries**. Four of its six
target descriptors are not instructions at the sites everyone had been sweeping — they are
signatures matching **interior bytes of longer instructions**:

| descriptor | sites | hardware boundaries | actually interior to |
|---|---:|---:|---|
| `n4_rt_word` `04 <dst> 20 80` | 3 | **0** | byte +6 of a 10-byte instruction (3/3) |
| `n4_cf_word` `04 01 00 00` | 4 | **1** | byte +2 of the 6-byte `pop_reconverge` (3/3) |
| `rtq_pred` `06 c2 00 00` | 1 | **0** | byte +6 of a 10-byte instruction |

This mechanically explains DEF-0172-4: EXP-0172's 256-value `n4_cf_word.b3` sweep was sweeping
**byte +5 of a `pop_reconverge`**. It is the same "shadowed, not absent" shape EXP-0204 found for
`cubearray_coord_const` the same day, by a different method — so treat it as a general hazard, not
two coincidences.

**The instrument (the "stop-ruler"):** write a `stop` — `_instruction: hardware-run`, body
HW-proven free filler — at every offset on a 2-byte grid, and see where the program stops producing
output. **A halt proves the offset is a boundary the hardware honours.** ~105 s for ~900 offsets.
It would have saved EXP-0172, EXP-0184 and EXP-0187 from sweeping operand tails.

**Its claim is deliberately ONE-SIDED and must stay that way: a halt proves a boundary; a no-halt is
INCONCLUSIVE.** Rest conclusions on span *consistency* across independent sites, never on a single
reading.

**Known confound — EXP-0200 found this in its own instrument and withdrew it.** `not_written` has
**three** producers: halt, masked store, and a clobbered store-address register. Byte-identical
8-byte fills read `not_written` at two offsets and `ok` at two others, 100% reproducibly. That is a
Gate B failure of the ruler itself. A scan must therefore detect anchor inconsistency and return
**`carrier-undecidable`**, not a length refutation. EXP-0200's first pass produced `LENGTH-REFUTED`
before this check was added.

**Also watch for a self-aliasing fill:** EXP-0200's `n2_compact2` fill `02 00` plus a stop composes
to `02 00 0e …`, which satisfies `iminmax`'s match — so that arm never tested the intended
descriptor at all. A pre-registered token record caught it. Record the tokenization of the composed
bytes, not just the fill you intended.

## 4. Required record, per case — emit exactly these keys

Append one JSON object per case to `raw/<run_id>/sweep.jsonl`, flushed immediately:

```json
{"instr":"falu2","field":"mod_lo","value":3,"bytes":"09051c0100c0",
 "observed":{"out0":7.0},"oracle":{"out0":7.0},"match":true,
 "outcome":"ok","carrier":"carrier_dag","note":""}
```

`outcome` ∈ `ok` | `silent_zero` | `wrong_value` | `fault` | `hang` | `undecodable`.
`fault`/`hang` are results; keep them.

## 5a. Verdict per field — PITFALL: inertness

> **PITFALL — an INERTNESS verdict needs a detection-power conjunct, or it cannot fail either.**
> DEF-0190-1: an arm whose observable never varies returns `moved = 0` **by construction**, and a
> classifier that reads `moved == 0` as "the field is inert" will certify it. Measured across this
> corpus: **8 arms record no observation at all, and 128 arms — 80,138 field records — record
> exactly ONE distinct `observed` payload across every case.** 21 fields rested entirely on such
> arms and 5 held emitter-grade status through it.
>
> This is the mirror of the promotion-gate defect one section down: there a gate could not refuse,
> here a gate cannot doubt. **Both are the same error — a check that cannot come out the other way.**
> Ten distinct instances have now been found in this corpus.
>
> **The remedy needs no hardware and is already in the raw:** the `_detect`, `__ladder_L_*` and
> `_live_control` records. Consume them as a **gate on INERT verdicts** — an arm that cannot show
> its observable moving for a known-live control cannot establish that anything else is inert —
> rather than as measurements in their own right.
>
## 5b. Verdict per field — PITFALL: width-1 arithmetic

> **PITFALL — a gate written `moved >= 2.0 * max(disagree, 1)` CANNOT promote any width-1 field.**
> The rule is `moved >= 2.0 * disagree, AND moved > 0`. A 1-bit field has at most one value that can
> differ from its own baseline, so the `max(..., 1)` form demands `moved >= 2` and refuses every such
> field **by arithmetic rather than by evidence**. EXP-0178 found this in its own gate against its own
> frozen text, where it had been silently suppressing `read_en` — the exact silent-zero read-enable
> that experiment was dispatched to re-verify. Check your gate against a 1-bit field with 0
> disagreements before you trust a null result from it.
>
## 5. Verdict per field — write `analysis/field_verdicts.json`

```json
{"falu2.mod_lo": {"label":"hardware-run",
                  "range":"0..7 dense (all 8 values)",
                  "target":"M4",
                  "evidence":["EXP-0140"],
                  "semantics":"...",
                  "note":"values 5..7 silently zero"}}
```

Use the **eight labels from `docs/evidence-classification.md`** and nothing else. If a sweep is
inconclusive, say `corpus-correlation` or `untested` — do not round up. The orchestrator merges
these into `tools/agx-isa/validation.json` and re-runs `validate_labels.py`, so a dishonest label
becomes someone else's silent-zero bug.

## 6. When a field turns out not to be a field

Several descriptors are wrong, not merely unlabelled. If a sweep shows the modelled boundaries do
not match the hardware — a "field" that is really two, a live byte `db.json` does not expose, a
length that swallows the next instruction's leader — **that is a first-class result**. Record the
corrected model in `field_verdicts.json` under `"db_defects"` with the evidence. Do **not** edit
`db.json`; the orchestrator owns it and eleven agents editing it concurrently would corrupt it.

Already known and flagged `emit_unsafe` in `db.json` — do not re-derive, but do respect them:
`half_alu_fma12`, `falu2_ext8b`, `op04_len8` (lengths over-consume the following leader),
`vary_store` (0x57/byte+2=0x54 collision), `tg_addr_compute` (over-fitted match, two live operand
bytes unmodelled), `falu_srcmod12b` (`opsel==4` corrupts an unrelated register).

## 7. Run everything in parallel. Instrument instead of serializing.

**There is no GPU lease. Run every sweep concurrently and unlocked.** The GPU has many hardware
contexts and they isolate ordinary work correctly. This section replaces three earlier attempts
(a blanket lease, then unlocked-with-majority-of-3, then a lease for fault verdicts only) — each
was wrong in the same direction: they treated a **detectable, recoverable** event as a reason to
serialize, and serializing cost far more than the contamination did. One bulk run once held the
device for 14 minutes with eight agents queued behind it.

### What actually happens

A GPU **hang** triggers a device-level reset. That reset kills in-flight command buffers in *other*
contexts — correct recovery behaviour, not a context-isolation failure. Concurrency is not the
problem; hangs are, and only briefly.

### The three instruments that make it a non-issue

**1. Poison your read-back buffer.** Fill every output with `0xDEADBEEF` before dispatch. This is
the single most important one, because it distinguishes the three outcomes that otherwise look
alike: *wrote the right value* / *wrote a wrong value* / **never ran at all**. On this ISA a wrong
field value usually produces a silent zero, so a zero-initialised buffer cannot tell "wrote 0" from
"did not execute".

EXP-0153 is the proof: five cases passed majority-of-3 **and** agreed across two independent runs,
and were still not faults. Isolation caught it — but so did the buffer, **offline, from data
already captured**: poison everywhere except the pre-test sentinel proved the program ran and that
neither following `device_store` executed. You do not need the device to adjudicate this.

**2. Write an integrity sentinel through a path independent of the instruction under test**, and
put it in a register no descriptor under test can name. A measurement without the sentinel is
`invalid_run` and gets repeated. EXP-0138 lost six sweeps by seeding its sentinel in r11, which the
instruction then read and zeroed.

**3. Record the OS fault-classification string on every non-`ok` case.**
`kIOGPUCommandBufferCallbackErrorInnocentVictim` means "discarded, victim of another context's
error/recovery" — a sibling's reset, not a property of your encoding. Segregate those and re-run.

### The exception, found the hard way: CONFIRMATION runs need a quiet machine

Everything above is right for *sweeps* and stays. It is **not** right for a re-run whose whole
purpose is to confirm an earlier observation, and two experiments established that independently on
2026-08-30:

- **EXP-0160** re-ran cases for confirmation while the machine was busy and the re-run
  **manufactured faults**: `imad` v=186 was `silent_zero` in *both* gated runs and `fault` 3/5 on the
  unlocked re-run. It retracted that path and gated instead on an evidence-validity filter — two
  agreeing clean dumps win outright, since **contamination can destroy an observation but never
  fabricate a coherent one**. That filter is the reusable idea here.
- **EXP-0158** ran its confirmation against 8-12 sibling experiments and got **102 of 174 cases
  giving MIXED outcomes across five runs of byte-identical programs**, with 427 `ErrorHang`
  observations arriving in streaks. Its cross-run gate FAILS and was left failing.

And the instruments are not a complete defence, which is the part to internalise:

- **`InnocentVictim` is not the only contamination signature.** EXP-0158's streaks carried none.
- **A contaminated dispatch can report `STATUS OK` and write nothing.** EXP-0160 saw 25 observations
  with all 16 registers *and both sentinels* still poisoned and no victim string anywhere. Against a
  zero-initialised buffer those would have been 25 confident `silent_zero`s.

**So: sweep unlocked, but do not treat a busy-machine re-run as confirmation.** For a confirmation
or re-validation pass, either (a) get a genuinely quiet machine — coordinate it with the
orchestrator, who owns the window — or (b) adjudicate offline from the poisoned buffer and the
sentinel, per EXP-0160's filter, and say in `RESULTS.md` which of the two you did.

**Do not reinstate a lease to solve this.** `~/agxre/gpulease.sh` is a passthrough shim that takes
no lock; it is deliberate, and a private lock nobody else is pointed at buys exclusivity you would
still have to verify by other means. If you need a quiet window, ask for one and **record concurrent
GPU activity for the duration** (sample the process table into `raw/`) so "the machine was quiet" is
a measurement rather than a claim.

### The one remaining rule

**Never conclude `fault` from a single observation.** Re-run every `fault`/`hang`/victim case,
majority-of-3 minimum, and adjudicate from the poisoned buffer where you can. EXP-0139 would have
labelled **692 legal field values as `fault`** without this; EXP-0144's revalidation reached a
**0.02% hang rate** purely by re-running victims.

### Courtesy, not a rule

If you are about to sweep a region you *know* hangs — `fspecial` byte+3 ≥ 192, control-flow
displacement sweeps, `atomic_tg` byte+5 `0x7E`/`0x7F` — say so in `PROGRESS.md`. A hang resets the
device for everyone, and it is useful for the orchestrator to know which agent caused it. Do not
serialize for it.

## 8. Safety — this host has no out-of-band recovery

`mov_imm.imm7` values 128..255 silently zero, and combined with `iadd2`'s N=0 self-read this
produced **two real GPU hangs** in EXP-0128. Expect more.

- One hypothesis per dispatch; hard timeout on every request; use the persistent runner's watchdog.
- Append + `fflush` every case as it completes. Never buffer to write at the end.
- `PROGRESS.md` entry per milestone.
- **After two genuine hangs in one area, STOP that arm** and report it PARTIAL, as EXP-0128 did.
  A partial sweep honestly bounded is worth more than a wedged host.
- Never `macvdmtool`. Never touch the A18. Never write outside your experiment directory.

---

## 9. Promoting an INERT field — the criterion, and why 29 rows are still open

**Ruling, 2026-08-30 (orchestrator).** EXP-0195 surfaced **29 field rows across 15 instructions**
whose uncited raw already carries an emitter-grade verdict, and which fail EXP-0194's gate at G4
("the observable never moved"). **All 29 are DECLINED for now.** They are a named debt, not a
withdrawal and not a backlog of easy wins.

The auditor's analysis was right and is worth restating: for a bit that is *supposed* to be inert,
"the observable did not move" **is** the predicted effect, so a constant oracle is the correct
oracle. G4/G7 can never be satisfied by any amount of good data — EXP-0194's chain is
**structurally incapable of passing an inert field**. That is a category mismatch, not a defect in
the data.

**Why they are declined anyway.** The asymmetry decides it. A false *active* claim gets caught the
first time an implementer emits the instruction and the value is wrong. A false *inert* claim tells
an implementer "this bit does nothing" — and it fails silently, forever, in exactly the way that
is hardest to trace back to us. And the corpus's own history says inertness is usually **our
carrier's blind spot, not the silicon**:

- `iter_at.loc` read inert on every arm of EXP-0155, then **moved at 4 samples** once EXP-0163
  varied `rasterSampleCount` — at one sample, centroid and pixel centre are the same point.
- `tex_sample.samp_extra` read **256/256 INERT on nine arms** and moved on **128/256** values on
  the tenth (explicit-LOD).

This is the user's standing challenge in operational form: *encoding space is expensive, so Apple
would use it well.* That argument says these 29 bits are **probably live and we cannot see them** —
which is a reason to withhold, not to promote.

**The criterion an inert-field promotion must meet.** Not satisfiable from the desk; it needs
hardware. Per row, all four:

1. **A positive control in the same dimension.** The carrier must be proven live in the dimension
   the field would control — some *other* value in that dimension must move the observable on that
   same arm. Two carriers identical in the dimension the field controls are one carrier.
2. **A swept range, not a sampled one.** Several of the 29 already fail this on their own
   admission (`imad.b11` reports 29 of 256 values; `ilogic.z6` states outright that the full
   256-value range was not swept).
3. **Cross-run agreement** at the standing bar (>=99% per value).
4. **A stated falsifier** — what observation would show the bit is live — recorded before the run.

**Extra caution for six of them.** `ray_move.{dst,src}`, `ray_move_copy6.{dst,src}` and
`ray_move_zero6.{dst,src}` are **register-descriptor / destination** fields. There, an observable
that does not move is far more likely to mean the carrier never read the register the field
selects than to mean the field is inert — the arm lacked detection power, and the G4 verdict is
itself evidence that its liveness was never demonstrated.

The full 29: `copysign.operands`, `cvt_f2i.b9`, `frag_color_store.store_mode`,
`frag_tile_setup.{sel,access,b5}`, `iadd2.srcB_reg_hi`, `ibfe.{b2_bit0,sign_ext}`,
`imad.{b1hi,b2_fmt,b11}`, `imageblock_store.b4`, `ishift.{src_cache,pad9}`, `iter.b9`,
`ray_move.{dst,src,b3}`, `ray_move_copy6.{dst,src}`, `ray_move_zero6.{dst,src,b3}`,
`tex_write.{amode,rsv11}`, `tg_addr_compute.{b3,b4,b5}`.

---

## 10. Operational facts learned on 2026-08-30 — read before designing a sweep

These cost real device time to learn. Each is measured, not inferred.

### 10.1 A quiet GPU FAILS HARDER — every severity label from a busy machine is suspect

Same encodings, same ok/not-ok partition, **escalated severity**: silent-no-write → fault
(**18 → 355**, identical in both orders); `if_push.scope` fault → **HANG** at the same values;
`tex_deriv` 7 and 11 hangs → **48 and 48**. One experiment is the counterexample with
byte-identical hard outcomes, so this is **not** an instrument artefact. Confirmed later over full
256-value arms on three carriers: same partition 256/256, **zero flips**, exactly **64 values
differing only in severity** (`fault` → `hang`) at `(v&7) ∈ {4,5}`.

A busy machine was also **MASKING** contained faults as OK-but-wrote-nothing: `(v&7)==7` is 32/32
`not_written` busy and **32/32 fault quiet**, with the other 224 values byte-identical.

**Rule: the ok/not-ok PARTITION is trustworthy across machine states; the SEVERITY LABEL is not.
Scope every fault/hang claim to the machine state it was measured on.**

### 10.2 A hang is TWO different things, and only one makes a sweep impossible

- **Driver-recoverable:** `recoveryCount` advances (+225 over 37 hangs), no cascade, the sweep
  continues, and the partition still matches the busy run 149/149.
- **Accumulating:** `recoveryCount` is **FROZEN** (4,509 s unchanged) and after ~40 values
  **every remaining value hangs** (102 of 102).

**Record `recoveryCount` pre/post for every capture and classify.** A frozen counter on a clean run
means "nothing reset the device", not the pathological case — do not read it as evidence either way
without hangs to explain.

### 10.3 Invoke a per-arm harness ONE ARM AT A TIME

One experiment's `run.py` aborts its **entire arm loop** on a cascade. Invoked once per arm through
its own selector, with nothing edited: **66/66 captures, 102/102 complete field sweeps, 0 cascades,
9,276 records per order — against 5,055** for the same harness run whole. The full 22-arm run still
aborts at **case index 5240 in three independent orders**: accumulated **in-process** state, not the
carrier, not occupancy, not the ~22,000 prior device resets.

### 10.4 A capture can contaminate the NEXT capture on a totally idle machine

One stage left **58 stuck `agxrun_persist` processes holding 1.6 GB and ~58 GPU contexts**; the next
capture's `carrier_open` hung and a known-good arm could not render its unmutated baseline. It
cleared itself in ~8 minutes with 3 driver resets. **Check for your own leftovers before declaring a
machine quiet** — the quiet metric cannot see contexts you are holding yourself.

### 10.5 "Unstable" may be PERIODIC — repeat a value inside one process before believing it

`tex_sample.mode` bit 6 read as instability for two experiments. It is a **strictly periodic
function of the dispatch index**: smallest period **4 or 8**, **240/240 sequences, 0 aperiodic**,
confirmed out of sample at N=24, with the phase following the **global dispatch counter**. The
matched bit-clear twin set is **0 of 33** everywhere, so it is not a harness artefact.

**Rule: before recording a field as unstable, repeat one value N times inside a single process and
test for periodicity.** Where a field is periodic in the dispatch index, **Gate E as
payload-equality is unmeetable on any machine** — score the partition and the period structure
instead.

### 10.6 A length change must be MEASURED against the corpus, and "additive" is the safety test

Two hardware-founded length changes, opposite outcomes. One was **strictly additive** — 21
encodings gained a length, **none was reassigned**, every other bucket identical — and went in. The
other was correct at **7/7 insertion boundaries** on hardware and was **REFUSED** as a measured
regression: clean files 841 → 838, **+410 leftover bytes, −69 instructions**, because it *moved*
lengths rather than adding them.

And a corpus TOTAL is not the test: three match-bit candidates left clean files, leftover,
instructions and resync gap **bit-identical**, and were refused on a broken round-trip, on one
descriptor **swallowing all 135 firings of another by winning a match-bit tie on list order**, and
on re-claiming 37 tokens of which **none carried the byte+1 the hardware sweep actually held**.

### 10.7 Measure the delta on the population that CONTAINS the affected encodings

A length change measured against a 292-file sample showed a delta of **exactly zero** — because the
sample did not contain the affected encodings, not because the change was inert. **A zero delta on
the wrong population is the easiest way to mistake "no effect" for "no risk."**

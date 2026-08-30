# Unattended run — goal, plan, and resume point

**DEADLINE: 10:00 AM PST** (set 2026-08-29, ~11h30m from the setting message). A successor
session should compute remaining time against that wall-clock and prioritise accordingly: with
under ~2 hours left, **stop dispatching new sweeps** and spend the remainder auditing, merging
verdicts, and writing the honest final accounting. An unmerged result is not progress.

**Set 2026-08-29 by the user:** *"you are unattended; your goal is to have 100% of the real
instructions emittable and have closed all the RE goals in the next 12 hours."*

This file is the single resume point. A successor session should read this first, then
`work/RESUME-STATE.md`, then `experiments/NEO-TARGET-BRIEF.md`.

## Live progress (update this as results land)

| | at start | now |
|---|---|---|
| Emittable instructions | 38 / 165 | **53 / 165** |
| Emitter-grade fields | 443 / 1036 | **552 / 1057 (52.2%)** |
| Part-II questionnaire | 145/181, 21 open | **ALL resolved** except `SFU-04` (blocked by clean-room rule 5) |
| Cross-target contradictions | 1 open (`tg_addr_compute`) | **0 open** — settled as genuinely target-driven (EXP-0156) |

**Landed on G17P:** EXP-0153 (revalidation: 7 reproduced / 0 refuted), EXP-0154 (ALU),
EXP-0156 (CF+MEM+bf16), EXP-0159 (questionnaire tail). **In flight:** EXP-0155 (TEX+FRAG),
EXP-0157 (MISC), EXP-0158 (generator synthesis), EXP-0160 (one-field-from-emittable),
EXP-0161 (carry_gen/fspecial), EXP-0162 (PACK + descriptor splices).

**Concurrency: the GPU lease was REMOVED** (protocol §7). Unrestricted parallelism; contamination
is handled by a poisoned read-back buffer, an integrity sentinel, the OS fault-class string, and
majority-of-3 on faults. The deployed `gpulease.sh` on the neo is a no-op passthrough so in-flight
callers still work.

## Baseline at start of the unattended run

| | |
|---|---|
| Emittable | **38 of 171 descriptors** (denominator is wrong — see below) |
| Emitter-grade fields | **443 / 1036 (42.8%)** |
| Remaining | 195 `untested` · 203 `tokenization-only` · 182 `corpus-correlation` · 13 `single-template-inference` |
| Test target | **A18 Pro / G17P**, `users-MacBook-Neo.local` @ `192.168.10.243` (DHCP) |
| All existing evidence | **M4/G16G** — G17P revalidation in flight (EXP-0153) |

## The honest read on "100%"

Worth stating up front so nobody later mistakes a shortfall for a failure to try. **Some fields
cannot be promoted by more sweeping**, and the reasons are already documented:

- **No dispatchable carrier** — `mem_fence8` (EXP-0141).
- **No ordering observable** — the fence fields. EXP-0141 and EXP-0147 both swept them densely and
  both *declined* to promote, because a pass proves nothing without ordering-specific litmus power.
  `compute_fence_scoped.mask` breaks reproducibly at exactly 10 of 256 values and *still* was not
  promoted. That restraint is correct and must not be traded away for a percentage.
- **Deliberate clean-room boundaries** — the compression codec bitstream (EXP-0134), `SFU-04`.
- **Descriptor defects, not sweep gaps** — `tg_addr_compute` has unmodelled live operand bytes plus
  a live G16G↔G17P divergence; `vary_store` has an unresolved opcode collision. These need the
  *model* fixed before any sweep is meaningful.
- **The denominator itself is wrong.** `rtq_pred` and `sfu_marker` have **zero fields** in
  `db.json`; EXP-0148 found **six of the 23 scaffolding entries are data words** by their own
  committed semantics. A db-defect agent is computing the corrected metric — expect the real
  denominator nearer **147** than 171.

So the target is: **every real instruction that CAN be made emittable, is** — with each exception
named, evidenced, and justified. A truthful 92% with 8 documented blockers beats a claimed 100%.

## Agent concurrency budget — 4 (was 6, was 8)

**User directive, revised three times from observed usage: 8 -> 6 -> 4.** Lowered to **4** on 2026-08-30 mid-wave, with the standing instruction "don't kill any as usual" -- so the count falls as agents finish and is never refilled above the budget. At the moment of the change seven were running; none was stopped. Above the budget the account hits usage limits, which is what
killed entire waves earlier — an agent stopped by a usage limit loses whatever it had not written
to disk, so overshooting costs more than it buys.

**Never stop running agents to get under budget** — that discards work already done. Let the count
fall naturally, then **refill toward 6, never above it**.

Practical consequence for a successor session: when several agents finish at once, resist
refilling all the slots immediately. Audit and commit the returned work first — an unaudited result
is not progress, and the merge (`work/merge_verdicts.py`) is where a wave's value actually lands.

## Standing rules for this run

1. **Concurrency is free.** Run device sweeps unlocked. GPU contexts isolate ordinary work; only a
   *hang* breaks isolation, and the driver reports it (`…ErrorInnocentVictim`), so contamination is
   always detectable. Take `~/agxre/gpulease.sh` **only** for known-hang-prone sweeps and for
   re-validation runs.
2. **Never conclude `fault` from one observation** — majority-of-3 minimum. Without this, EXP-0139
   would have shipped 692 legal field values labelled `fault`.
3. **Label `target: G17P`** for anything run on the neo. Never relabel M4 evidence as G17P.
4. **Pull `raw/` back to the repo as you go.** Nothing on the neo is evidence until committed here;
   a reboot loses it.
5. **Do not promote a field to reach a number.** Every prior agent that declined a larger claim
   (EXP-0138 declined 7 fields, EXP-0144 withdrew 44→33, EXP-0147 declined six fence fields) was
   right to, and those decisions are why the corpus is trustworthy.

## Failure modes already seen, and their fixes

| Mode | Fix |
|---|---|
| Account session limit kills all agents | Work is committed incrementally; relaunch from disk |
| Host sleep | `caffeinate -dimsu` running on the M4 |
| VPN drop kills SSH | Hard-timeout every remote call; lease self-releases, no wedge |
| WindowServer/compiler-service collapse | **Solved by the pivot** — GPU work no longer runs on the session host |
| Cross-agent GPU contamination | Fault-class recording + majority-of-3 re-runs |

## Merge policy revision, 2026-08-30 — "inert" is not a free pass

**User challenge:** *"i really don't buy anything is inert -- encoding space is expensive so it
seems like apple would use it well."* They are right, and the audit that followed proved it on our
own data before any new hardware run.

Re-deriving EXP-0155 field-by-field from `raw/` per carrier, **every field examined that looked
inert was live on a carrier the analysis had not picked**:

| field | reads inert on | actually live on | both runs |
|---|---|---|---|
| `tex_sample.samp_extra` | 9 of 10 arms | `lo_1` (explicit LOD), 128/256 moved | 128 / 128 |
| `frag_color_store.flags` | `fcs@iter0` | `fcs@pack0`, 128/256 moved | 128 / 128 |
| `tex_sample.coord` | 3 arms | 3 arms, up to 157/256 | unstable |

EXP-0163 then supplied the mechanism for a fourth: `iter_at.loc` selects centroid-vs-sample
interpolation and was only ever swept on a **samples=1** carrier, where centroid and sample are the
same point. The field could not have moved anything there *whatever it does*. That is the whole
hypothesis in one line.

**The rule now applied at merge time** (implemented in the flattening step, recorded in each
`_meta.orchestrator_policy`):

1. **stable-live** — moves an observable, **>=99% per-value cross-run agreement**, and
   **movement >= 2x the disagreement count** so a handful of flipped cases cannot masquerade as a
   live field. The representative arm must be the strongest such arm, not the first one seen.
2. **inert-envelope** — never moved anything, but on **>=2 structurally different carriers**.
   Emitter-grade only within the recorded envelope, which is written into the note.
3. **withheld** — never moved anything on exactly **one** carrier (underpowered), or movement that
   does not reproduce.

Applied to EXP-0155 this withheld 15 of 105 offered verdicts and re-pointed 14 to a stronger arm.
The published number is **66/166, not the agent's 72/166**; `tex_sample`, `tex_coord_setup`,
`vary_slot`, `vary_store`, `simd_ballot` and `simd_shuffle` stay non-emittable.

**Two experiments now test this directly:** EXP-0163 hunts liveness for the 22 never-moved fields on
new carriers; EXP-0164 audits every already-merged emitter-grade field in `validation.json` for the
same weakness and reports what the honest count would be.

---

## Status at 2026-08-30 02:50 PDT — read this first if you are a successor session

**Headline: 35 of 166 emitter-relevant instructions emittable, 588 emitter-grade fields.**
27 commits since midnight. **The number FELL from 79 today, across three withdrawals, and each was
confirmed by an independent audit.** That fall is the run's main result, not its failure: the
corpus now says what it can prove.

### The four tooling defects that had been inflating confidence — all fixed

| defect | what it did | how it was caught |
|---|---|---|
| `isadb.assemble()` OR-ed `match` then fields | any overlapping bit **stuck at 1**; sweeps silently under-covered | EXP-0166, from EXP-0146's recorded bytes |
| `roundtrip_test.py` cited as an emitter gate | **passes unmodified against an assembler that cannot clear a bit** (173 cases, 0 failures) | EXP-0170, by re-implementing the broken assembler |
| oracle co-varying with the field under test | `uniform_mov.dst` read back via `device_store(data_reg=D)` where D *was* the swept dst, so "0 moved" was the **passing** outcome of a test that could return nothing else | EXP-0168, auditing EXP-0140's harness |
| coverage unenforceable | `range` is free prose; 358 of 617 rows unparseable; **no gate had a coverage term**, so a field could pass on two dispatched values | EXP-0169's caveat on EXP-0164's gate |

Rules 3(a), 3(b) and the §7 confirmation rule are now in `experiments/FIELD-SWEEP-PROTOCOL.md`.

### The three contamination modes, in order of severity

1. **Contention destroys observations — one-directionally.** EXP-0167 under measured isolation:
   740 witness observations, **0 MIXED**, against 102 of 174 contended. `dag_040_n20` was `fault`
   5/5 contended and `ok` 5/5 clean. **No program passed under contention and failed under
   isolation.** That asymmetry is why offline adjudication from a poisoned buffer is sound.
2. **A contaminated dispatch can report `STATUS OK` and write nothing** — 25 observations with all
   16 registers *and* both sentinels still poisoned, no `InnocentVictim` string (EXP-0160).
3. **DEF-0169-1 — a diff-based movement oracle can FABRICATE movement**, which breaks the comfort
   of (1). `device_load` on G17P is **asynchronous**; with no wait a program landed 0,0,0,0,2,5,8,8
   of 8 seed registers by filler length alone, so a periodically-refreshed diff baseline reads the
   next batch as movement. An outcome-class audit cannot see this. Seed with `mov_imm` or wait.

### Live hazards a successor must know

- **The neo's shared `tools/agx-isa/db.json` is STALE** — 1036 fields vs the repo's 1060, with
  `falu2.srcA_class`/`srcB_class` replaced by `mod_lo`. A harness whose `_find_isadb()` falls
  through to it keys every falu2 verdict to the wrong field, silently. **Pin your own snapshot.**
- `iter_at` with `grp=0x50` hangs the device. `iter.grp`/`iter_at.grp` have only **two** legal
  values (their match pins bits 0..6) — which is why every sweep of them hit hangs.
- EXP-0169's DSTORE arm (`device_store.base_slot` through unbound slots) is **queued, not
  forgotten** — it is the most likely thing to wedge the device and waits for a clear machine.

### Held, not withdrawn

16 rows (`half_alu_ext8` x11, `half_alu_fma12` x5) whose only passing liveness ladder was the
withdrawn `C2_load` carrier. The carrier failed for a harness defect, **not** because the fields
resisted; a successor with a corrected carrier owns them.

### The gate, not the count

`CLAUDE.md`'s Definition of Done turns on an audit that *positively reproduces* the claimed
generation paths. **EXP-0173 is running that audit now** — it is the only thing that decides
closure. The strongest positive going into it: **EXP-0167 re-confirmed 233 of 237 generated
programs containing ZERO copied fields producing their exact host oracle**, with a ledger check
over 204,044 `assemble()` calls at 0 mismatches. The known gap: 60 of those 233 rest on rules that
experiment did not itself measure, and **24 still need a donor** (12 control-flow, 12 immediate
`iadd2`).


---

# FINAL ACCOUNTING — 2026-08-30, written before the 10:00 PST deadline

## The number

**32 of 166 emitter-relevant instructions emittable; 543 of 1040 fields emitter-grade.**

> **This figure was 55/638 until the closing audit (EXP-0189) tested it and it did not survive.**
> That audit reimplemented the *current* rule — including the `_instruction` gate I had added
> hours earlier — and **reproduced 55 exactly before withholding anything**, so 38 was measured
> against my own rule rather than a different one. I then withheld one more (`call.tail`) on its
> eighth finding. The full arc of the day is **79 → 41 → 55 → 38 → 37 → 34 → 33 → 32**, and every fall came from
> an audit that could reproduce the published number before disputing it.
>
> **The shortfall is not the merges made during this run, and that is measured rather than
> asserted:** the post-withdrawal cohort withholds at **18.31%** against **16.94%** for the corpus
> it joined. The dominant cause is inherited — **one A18 experiment has no `raw/` directory at all**,
> only a narrative summary, and is load-bearing for **7 of the 17 instructions that lost status**.
>
> **Two of my four personal rulings were wrong.** `get_sr.form` is withdrawn: I promoted it over an
> eight-arm decline, and two of my three grounds were bad — including a rebuttal that was *factually
> wrong about the experiment I was overriding*. `iter_at._instruction` was over-labelled. The other
> two (`call.b6`, and the 30-label refresh) held up.
`validate_labels.py` rc=0, `roundtrip_test.py` ALL PASS, 56 commits today, 257 provenance rows.

**Of the emitter-grade fields, 412 are measured on G17P** — the actual documentation target —
against 164 on M4 and 57 on A18. That ratio is the run's real product: at the start of the day
the corpus was overwhelmingly M4 evidence being counted toward a G17P goal.

## A wrong fact I published, corrected

In reporting the close-out I wrote that the repair path "starts with **+11** needing no device at
all." **That figure is not supported by anything in this repo.** The only "11" on the subject is
EXP-0178's finding that `verify_remote` caught 11 of 18 blobs mismatched against their author —
a different result entirely. I conflated the two and stated the product as fact.

This is the same class of error as DEF-0186-1, where my own PROVENANCE row asserted `call.b6` was
inert when bit 1 must be SET. Both were mine, both were caught by checking the index against the
data rather than by re-reading my own prose.

What the data actually says: all **566** blocking field-labels sit at `untested` (260),
`corpus-correlation` (141), `tokenization-only` (135), or `single-template-inference` (30), and
**none** is `MISSING` — the DB and the label corpus are consistent. Whether any of the 566 can be
promoted from *already-committed* raw captures without new device time is now an open audit
(EXP-0194), not a number I get to assert. The expected answer is zero.

## What is fragile about the 543 — stated, not resolved

EXP-0193 measured two things about the surviving population and **handed both over as questions
rather than acting on them.** That was the correct call and I am not overriding it: changing the
criterion after seeing which rows it would move is the exact failure this chain exists to prevent.
Both are published here so the number carries its own caveats.

1. **115 of the 497 surviving Case-A rows clear the bar by exactly one payload** (`bestV == 2`).
   They are correctly Case A under the frozen rule. They are also precisely where a stricter
   successor would land first, so **~23% of the surviving population sits one payload above the
   floor**. Anyone raising the threshold to V ≥ 3 should expect the number to fall again.
2. **The criterion is target-blind.** Two rows recorded as G17P (`ibfe.srcA`, `ilogic.outmod`)
   are Case A *only* by way of M4/G16G arms. Under the standing no-cross-target-promotion rule
   that is a defect; under the frozen criterion it is not. Adding a target conjunct now would be
   the eleventh-hour adjustment, so it is a **named debt, not a withdrawal**.

Also measured and worth recording: the record-level second pass rescued **0** rows, so the
modal-collapse confounder has **zero effect across all 503** — one of the few confounders on the
list that was quantified rather than argued about.

## The number moved DOWN more than it moved up, and that is the result

79 → 41 → 55 → … → 32. Every fall was a withdrawal an independent audit confirmed, and each was caused by
finding that a **check could not come out the other way**:

> **The last withdrawal is the sharpest instance in the corpus.** EXP-0193 applied EXP-0192's
> *unchanged* criterion to the full 337-arm STABLE-LIVE population — 503 fields, 23 experiments —
> and it fired three more times. One of them, `frag_color_pack.fmt_class`, was an 8-bit field with
> **255 legal values in which all 512 records carry one identical payload**. Its entire claim to
> emitter grade was **two cells our own disassembler could not decode** — `status: OK`, sentinel
> written, pixel readback byte-identical to the other 255 values. The hardware never moved; our
> tokenizer disagreed with itself, and a promotion gate counted that as evidence.
>
> The population sweep is also the strongest form the criterion can take: a rule that has now
> withdrawn seven rows, run against every arm it could possibly apply to, with the control
> (`call.b5`) reproducing EXP-0192's committed counters exactly and **0 of 503 rows unlocatable**.

| what looked like evidence | why it could not fail |
|---|---|
| a liveness ladder | clearing byte0 **relocates** the write rather than nulling it |
| `roundtrip_test.py` | symmetric across encode and decode — it passes against an assembler that cannot clear a bit, *and* with two operands swapped |
| an oracle | **co-varied** with the field under test, so a correct result was a constant vector by construction |
| a contiguous-suffix cascade test | trivially true at 8-of-8 non-OK |
| a clustering score of `0.0` | a **key collision**, not a cascade |
| a detection control | fired on a **match byte**, i.e. by encoding a different opcode |

Six shapes, six experiments, none found by sweeping more. **All six came from auditing work that
had already passed.**

## What an implementer can actually do now that they could not this morning

- **`nir_op_mov` is CLOSED.** `n3_mov` moves one GPR to a different GPR — 840 generated copies over
  all 240 ordered pairs, **0 failures, zero bytes copied from any compiled shader**. It is 16-bit
  granular, so a 32-bit copy is two instructions. Without this there is no register allocator.
- **The `call` is emittable**, generated end to end: `target = call_addr + 4 + offset` measured
  **forward** (every call in the corpus is backward), `call.b3` a branch-taken selector with 4 of 8
  bits live, and **the `pop_reconverge` after a call is REQUIRED while the frame marker is OPTIONAL**.
- **A system value can be read** — with a stage rule nobody had: **in a vertex shader every
  `sr_sel` with bit 7 clear FAULTS, 128 of 128**, where compute faults at none.
- **`instance_id` is not base-inclusive while `vertex_id` is** — `baseInstance` is added in software.

## What is still not done, stated plainly

**111 instructions remain non-emittable**, 16 of them one field away. `docs/isa/emit-worklist.md`
names every one with its exact blocker and is regenerated from `db.json` + `validation.json`.

**The acceptance gate is NOT passed.** EXP-0173 measured it: 0 of 16 P0/P1 rows CLOSED, closure
rule 5 met by 6 of 16. Most importantly it found that **EMITTABLE (a property of labels) and
GENERATED (a program that actually ran) are nearly disjoint** — the intersection was two
instructions. That gap is the honest distance to closure, and it is not measured by the field count.

**Every enumeration of a gap has been an undercount when someone looked harder** — the missing
provenance rows went 36 → 67 → more; the untokenizable descriptors went 5 → 10; the wrong-operand
class went 1 → 4 → 6. Treat the current numbers as lower bounds.

## The three instruments that now exist

`tools/agxtest/{saferunner,verify_remote,closure_scan}.py`, each of which caught a live defect
within an hour of being written, with a device-free selftest (`selftest_tools.py`, T0–T7, ~3 s).
**`verify_remote.py` is the one to keep**: a frozen contract hashes what you *authored*, not what
the device is *running*, and on its first run against its own author it found **11 of 18 blobs
matching** with every hash in the contract still correct.


## The one finding that outlives the number

**Ten distinct instances of a single defect were found in this corpus today: a check that cannot
come out the other way.** None was found by running more sweeps; every one came from auditing work
that had already passed.

| # | the check | why it could not fail |
|---|---|---|
| 1 | a liveness ladder | its falsifier **relocated** the write instead of nulling it |
| 2 | `roundtrip_test.py` | symmetric across encode and decode — passes against an assembler that cannot clear a bit, *and* with two operands swapped |
| 3 | an oracle | **co-varied** with the field under test, so a correct result was a constant vector by construction |
| 4 | a contiguous-suffix cascade test | trivially true at 8-of-8 non-OK |
| 5 | a clustering score of `0.0` | a **key collision**, not a cascade |
| 6 | a detection control | fired on a **match byte** — i.e. by encoding a different opcode |
| 7 | 96 whole-word liveness probes | built on match bytes; returned false negatives **while the field was faulting the GPU** |
| 8 | a promotion gate | **no `moved >= 1` conjunct** — a dead-code carrier scores `hardware-run` |
| 9 | an indexer filter | discarded any raw record whose field name starts with `_`, hiding real sweeps |
| 10 | an **inertness** gate | `moved = 0` **by construction** on an arm whose observable never varies |
| 11 | a promotion gate | `sig_of()` separates `ok` from `fault`, so **`moved` counts a FAULT as movement** |
| 12 | a promotion gate | `sig_of()` also separates `ok` from **`undecodable`**, so **`moved` counts OUR OWN DISASSEMBLER's disagreement as hardware movement** |

**#8 and #10 are the same error in opposite directions** — one gate that cannot refuse, one that
cannot doubt. #2 and #9 were load-bearing for months. Four of the ten were found by the very agent
whose result they undermined.

The practical consequence for a successor: **a green check is not evidence until you have shown it
can go red.** Every rule now in `FIELD-SWEEP-PROTOCOL` §3 and §5 exists because one of these cost a
real experiment.

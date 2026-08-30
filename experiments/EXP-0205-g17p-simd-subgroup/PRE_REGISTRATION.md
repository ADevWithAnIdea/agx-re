# EXP-0205 — PRE-REGISTRATION (frozen before any gated run)

**Target:** Apple A18 Pro / **G17P**, `192.168.170.254`, `AGXAcceleratorG17P`,
arch `applegpu_g17p`, macOS 26.6, Metal family Apple9.
**Frozen:** 2026-08-30, after the pre-freeze calibration in `raw/prefreeze/`.
**Fields under test (6, across 3 instructions):**
`simd_ballot.pred`, `simd_ballot.cache`, `simd_reduce.op`, `simd_reduce.dtype`,
`simd_shuffle.dir`, `simd_shuffle.cache`.

Everything below is fixed before any gated capture. `raw/` is append-only; a
partial run is retained under its own id and never topped up or reused.

---

## 1. The question, and why it matters

`docs/isa/emit-worklist.md` lists `simd_ballot`, `simd_reduce` and
`simd_shuffle` as **two fields away from emittable** each. An implementer who
must emit a subgroup instruction cannot today choose a value for any of these
six fields and predict what the hardware will do.

Two of the six — the `cache` fields — are the harder problem and the reason this
dispatch exists. They were **withheld twice** (EXP-0163, EXP-0172) as "never
observed to move an observable", and both times that was a **carrier failure**,
not a hardware fact. The governing rule (`docs/isa/emit-worklist.md` line 7) is
that a field that never moves is promotable only if the carriers differ **in the
dimension the field controls**; carriers identical in that dimension are ONE
carrier. The corpus precedent is exact: `tex_sample.samp_extra` read 256/256
INERT on nine arms and moved on 128/256 values on the tenth.

## 2. Hypotheses, each with its refuter

**H1 — `simd_ballot.pred` selects ballot-of-predicate against active-thread
mask.** db.json models byte+1's high nibble as `0x0 = active_mask/any/all`,
`0x1 = ballot(predicate)`.
*Predicted observation:* on `sb_ballot`/`sb_ballot2`, where all 32 lanes are
active and the predicate is the asymmetric mask, some value of `pred` yields
`0xFFFFFFFF` (the all-active mask) while another yields the predicate mask; on
`sb_active`, whose baseline result IS `0xFFFFFFFF`, some value yields a
predicate-dependent mask instead.
*Refuter:* **no value of `pred` in 0..15 produces `0xFFFFFFFF`** on the ballot
carriers, and none produces a mask-dependent value on `sb_active`.
*Already partly refuted by calibration, and recorded as such:* **both** compiled
forms carry `pred = 0` on G17P. What separates them is byte+5 (`psrctype`
0x00 vs 0x02) and the byte+7..9 tail (`58 22 12` vs `08 02 18`). db.json's
0x07/0x17 mapping is therefore **not** what our compiler emits, and the sweep
tests H1 over the whole 16-value range rather than assuming it.

**H2 — `simd_reduce.op` selects the reduction operation.**
*Predicted observation (opcls = 1, the three integer carriers):* `op = 0` gives
`ior`, `1` `isum`, `2` `smax`, `3` `umax` — four DIFFERENT 32-word vectors,
because the authored inputs contain one negative word so `smax != umax`.
*Predicted observation (opcls = 0, the float carrier):* `op = 5` gives `fmin`
(1.5), `6` `f32sum` (172.0), `7` `fmax` (9.25).
*Refuter:* the swept values produce vectors that do not correspond to any named
reduction of our inputs, or `op` moves nothing at all.

**H3 — `simd_reduce.dtype` selects data type AND reduce/scan shape.**
*Predicted observation:* with the op held at the carrier's baseline,
`dtype = 3` gives a REDUCE (all 32 lanes equal), `9` an INCLUSIVE prefix scan,
`11` an EXCLUSIVE prefix scan, and on the float carrier `18/34/50` the same trio
in f32. Those differ in 31 of 32 lanes.
*Refuter:* the scan values return a reduce vector, or reduce/scan are
indistinguishable, or nothing moves.

**H4 — `simd_shuffle.dir` (byte0 bit 7) selects broadcast/up against xor/down.**
*Predicted observation:* on `sh_bc` (baseline `dir=0`), `dir=1` turns "every lane
reads lane 5" into "lane t reads lane t^5"; on `sh_xor` (baseline `dir=1`),
`dir=0` does the reverse. Each carrier's spliced result must equal the OTHER
carrier's measured baseline vector.
*Refuter:* flipping the bit leaves the vector unchanged, or produces neither
prediction.

**H5 — the `cache` fields are operand register-cache / discard hints**, i.e.
public open-source documentation of the older AGX (`gpu_knowledge/third_party/
dougallj_applegpu_*`) describes operand hints `cache` ("retain in register
cache") and `discard` ("future reads undefined, frees register for reuse").
*Dimension that implies:* **the content of the SOURCE REGISTER after the
instruction**, observable only if the source is read AGAIN afterwards and the
register file is under enough pressure for a freed register to be reused.
*Predicted observation:* on `sb_reuse`/`sh_reuse` — 16 loads live across the
instruction, the source read again after it into out[32..63] — some value of
`cache` changes out[32..63] while leaving out[0..31] alone.
*Refuter:* out[32..63] is identical for both values of the bit (all 256 values
of `simd_ballot`'s byte) on a carrier whose IN-DIMENSION control has been proven
to move exactly that observable.

**Why the previous sweeps could not have seen H5.** EXP-0163's four carriers all
**reuse** their sources at **low** pressure. EXP-0172 added `deadsrc`, which
removed the reuse entirely (every operand loaded, used once, dead) — that makes a
discard hint harmless **by construction**, the mirror error. **Neither varied
register pressure, and neither put the post-instruction content of the source
register on the output path.** Both dimensions are varied here.

## 3. What calibration already settled (pre-freeze, `raw/prefreeze/`)

Recorded before the freeze, and kept whether or not it flattered the design:

| | |
|---|---|
| **Measured SIMD width** | **32** (`threads_per_simdgroup` read back per lane; lane ids 0..31; one simdgroup at tg=32). Measured, not assumed. |
| Occurrences | **Exactly one** per carrier, parcel-aligned, and the pinned tokenizer agrees it is the target instruction. No occurrence ambiguity. |
| `simd_ballot.pred` | **0 on BOTH forms** — H1's db mapping refuted before any splice (see H1). |
| `simd_active_threads_mask()` in a divergent `if` | returned **0xFFFFFFFF**, not the divergent mask. Either the compiler predicated the region or the mask reports resident rather than executing lanes; **we do not claim which**. |
| `simd_shuffle.dir` | CONFIRMED at both baselines against the host oracle before any splice. |
| `simd_shuffle.cache` | the compiler itself chose **both** values: 0x56 (cache=1) on `sh_bc`/`sh_xor`, 0x54 (cache=0) on `sh_reuse`, both correct. |
| `simd_reduce` opcls | 1 on the int carriers, 0 on the float carrier; db's enum pair ordering is **not** opcls order, so the oracle is anchored on measured baselines. |
| All ten oracles | reproduce the unmutated hardware output exactly, including the 32 secondary words of both reuse carriers. |

## 4. Variables

**Independent:** exactly one field of exactly one instruction occurrence per
case, patched **directly in the bytes** (never through the assembler, so the
OR-only `assemble()` defect that aliases distinct values onto identical bytes
cannot reach this experiment).

**Controlled:** carrier source, inputs, dispatch shape (grid = tg = 32, one
simdgroup), buffer bindings, poison pattern, `--no-fast-math`, the pinned
`db.json`/`isadb.py`/`shdump.m`/`agxrun_persist.m`/`saferunner.py`.

**Dependent:** the 32 per-lane value words out[0..31]; the 32 secondary words
out[32..63] on the reuse carriers; the integrity sentinel out[72]; the poison
tail; `GPUTIME_NS`; command-buffer status and the OS fault-classification string.

**Coverage:** every target field is swept **DENSELY over its entire encodable
range** — `pred` 16/16, both `cache` fields and `op` and `dtype` 256/256 and
2/2, `dir` 2/2. 35 arms, 3836 cases per run.

## 5. Confounders and how each is handled

| Confounder | Handling |
|---|---|
| A wrong value writing a **silent zero** | Output slot is bound as an INPUT pre-filled with POISON(i)=0xDEADBEEF+i, so `silent_zero` and `not_written` are distinguishable. |
| A dispatch reporting OK and writing **nothing** | Integrity sentinel out[72]=12345, stored first through a constant path; absent ⇒ `invalid_run`, retried, never scored (EXP-0160 saw 25 such with no victim string). |
| A **sibling experiment's** device reset | OS fault-classification string recorded per case; `InnocentVictim` retried up to 3× before anything is concluded. |
| A **false hang cascade** (DEF-0178-1) | The pinned `saferunner` runs one reader thread per child, tagged by owner; a malformed response is `MALFORMED` ⇒ `measurement_failure`, excluded from agreement and from `values_dispatched`, never scored as a hang or an observation. |
| A **fault** mistaken for movement | `moved` requires an outcome in {ok, wrong_value, silent_zero, unpredicted} in BOTH runs. Faults, hangs, `not_written`, `invalid_run` never count. |
| **Our own disassembler** failing to decode, mistaken for movement | The tokenized mnemonic of the MUTATED bytes is recorded on every case and reported; it never enters the gate. |
| **Aliased encodings** | `gen_arms.py` proves, per arm, that the values produce `distinct_encodings == len(values)` and that every difference is confined to the field's span. Re-checked in `verdicts.py`; an aliased arm is REFUSED. |
| The **oracle co-varying with the field** (EXP-0140/DEF) | The observable is a device buffer written by 32 lanes; no swept field names the output slot. The one field that names a register (`dst`, used only as the in-dimension control) is scored on the SECONDARY words, which is the point of that arm, and never used to promote a target field. |
| A **constant oracle** certifying inertness | A constant oracle IS correct for a bit that should be inert, and is therefore explicitly NOT what promotes anything: promotion reads MOVEMENT plus the detection-power controls. |
| **Busy machine** during a confirmation | Both gated runs are ordinary sweeps, not confirmations; concurrent GPU processes are sampled into each run's `env.json` so "the machine was quiet" is a measurement. |

## 6. THE GATE (frozen; nothing else may promote)

Implemented in `analysis/verdicts.py::classify`, and proven to be able to return
"no" by `analysis/gate_selftest.py` — **13/13 offline checks, no device**, run
before any hardware data existed.

- **G1** two gated runs, byte-identical programs, the same frozen `arms205.json`.
- **G2** ≥ **99 %** per-value cross-run agreement on the outcome partition, and
  `moved >= 2*disagree AND moved >= 1`. **NOT** `moved >= 2*max(disagree,1)`:
  that form cannot promote any width-1 field by arithmetic, and two of the six
  fields here are width 1. Asserted by selftest T1.
- **G3** movement excludes faults, hangs, `not_written`, `invalid_run` and
  measurement failures (T2).
- **G4** every arm carries a CONTROL arm on the **same instruction at the same
  occurrence**, on a field already `hardware-run` (`psrc`/`src`/`lane`). An arm
  whose control never moved is BARRED from supporting any verdict, live OR
  inert (T3). Inertness must still be reachable when the control DOES fire (T4).
- **G5 — the cache rule.** For `simd_ballot.cache` and `simd_shuffle.cache`, G4
  is not sufficient. An **IN-DIMENSION** control is required: a dense `dst`
  sweep on the same carrier must, at some value, change the SECONDARY vector
  out[32..63] — the post-instruction content of the source register, which is
  exactly the dimension H5 says the field controls. Without it the verdict is
  `UNRESOLVED-DIMENSION-NOT-EXPRESSED`. **With it, and with zero movement, the
  verdict is still `UNRESOLVED-INERT-IN-TESTED-DIMENSION`, never "inert"** —
  because a register-cache RETENTION hint's remaining observable is timing and
  power, which a functional read-back cannot express at all (T5).
- **G6** the arm-open and arm-close baselines must both be `ok`.
- **G7** aliasing check as above (T6).
- **G8** an arm with > 1 % measurement failures is refused (T7).

**Labels:** LIVE → `hardware-run`; INERT-ROBUST → `single-template-inference`
(explicitly NOT emitter-grade); UNRESOLVED and STILL-UNDERPOWERED → `untested`.
`docs/evidence-classification.md` §2 vocabulary only; nothing is rounded up.

## 7. Pre-registered cases that must FAIL

Protocol §3.5 — if everything passes, the sweep proves nothing about detection.

1. **Every control case must MISMATCH the oracle.** Controls are scored against
   the carrier's baseline prediction, and a control that moved must therefore
   come out `wrong_value`. A control scoring `ok` would mean the oracle is a
   rubber stamp.
2. **`simd_shuffle.dir` must move on `sh_bc`.** If a 1-bit field with a
   confirmed, opposite, hardware-measured baseline on a sibling carrier does not
   move, this experiment has no detection power for width-1 fields and every
   width-1 negative in it is void.
3. **`simd_reduce.dtype = 9` on `sr_sum` must produce the inclusive-scan vector**
   (31 of 32 lanes differ from the reduce vector). If it returns the reduce
   vector, H3 is refuted.
4. **`simd_reduce.op` values 4..7 on the integer carriers are predicted NOT to
   match** — we make no prediction there and record `unpredicted`. A match would
   mean the prediction was not discriminating.

## 8. Raw record schema (one JSON object per case, `raw/<run_id>/sweep.jsonl`)

`carrier, arm, instr, field, value, bytes, token{mnemonic,op,length,error},
observed{vals_u32[32], sec_u32[0|32], sent_u32, tail_poison_ok, status,
sentinel_ok, unwritten[], gputime_ns}, oracle[32]|null, match(true|false|null),
outcome, status, statuses[], fault_classes[], innocent_retries, role, occ, off,
instr_len, start, width, baseline_field, note, ts`

`outcome ∈ {ok, wrong_value, silent_zero, not_written, unpredicted, fault, hang,
measurement_failure, invalid_run, nondeterministic}`. `unpredicted` is this
experiment's declared extension and means "we predicted nothing for this value
and are recording the observation"; it is never a pass.

Each case is `write` + `flush` + `fsync`'d immediately — never buffered.

## 9. Environment, timeouts, safety

- Per-request watchdog **8 s**; compile 600 s; every remote call under a host
  alarm. Majority-of-3 on any non-OK case; 3 `InnocentVictim` retries; 3
  canary retries for a missing sentinel.
- **NO ABORT PATH and no per-field hang budget** (protocol §3(c)): a budget
  cannot characterise a contiguous hazard, it guarantees the region is never
  mapped. Every value in every arm is dispatched.
- Courtesy note in `PROGRESS.md`: this experiment sweeps `simd_reduce.op` and
  `.dtype` densely over 256 values each on four carriers, and `simd_ballot`'s
  whole byte+2 on four carriers. Regions unknown to be safe.
- `macvdmtool` is **forbidden**. If the neo stops answering: STOP and report
  BLOCKED.

## 10. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: only our own MSL in kernels/ and its compiled bytes; the
                  public dougallj/applegpu notes in gpu_knowledge/ (as a source
                  of the HYPOTHESIS H5 only, never of a value)
Apple binary introspection: NONE
Reproduction: harness/sync.sh push; python3 harness/verify_remote.py;
              python3 analysis/gen_arms.py; python3 run.py --run-id <id>;
              python3 analysis/verdicts.py raw/<run01> raw/<run02>
Evidence: raw/prefreeze/, raw/<run01>/, raw/<run02>/, CAPTURE_CONTRACT.json
```

---

# AMENDMENT 2 — REVISION B pre-registration
**Frozen 2026-08-30, BEFORE the first revision-B dispatch. Revision A's runs
(`raw/g17p_20260830_run01`, `run02`) are RETAINED unchanged as revision-A
evidence and are reclassified, not discarded (`RE_EXPERIMENT_PROCESS_CORRECTIONS.md`
§9/§10). No hypothesis is edited to match data already captured.**

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` became normative after revision A ran and
**overrides the gates above where they conflict.** Three of its requirements
revision A does not meet, and this amendment exists to meet them.

## B1. What revision A does NOT establish, stated first

| Gate | Revision A status |
|---|---|
| **A — actual-byte ledger** | **NOT MET.** Revision A recorded the bytes it *intended* to write, recomputed by the same function that built the dispatched blob. That is exactly the ledger DEF-0166 defeats. No independent decode, no program hash. |
| **B — detection power** | Met for the generic control on all 35 arms and for the in-dimension `dst` control on the two reuse carriers — but with **one readback plan** on 9 of 11 carriers, and **no multi-invocation dimension at all**. |
| **C — semantics** | Met for `simd_reduce.op`, `simd_reduce.dtype`, `simd_shuffle.dir`. **NOT met for `simd_shuffle.cache`**, which moved but matched no pre-registered model, and therefore may not be `hardware-run` however clean the movement was. |
| **E — clean confirmation** | Two runs, 100 % agreement, zero non-clean cases — but the same case ORDER, and `env.json` records a **busy** machine (EXP-0199/0204/0206 concurrent). |

## B2. The added carriers and why they have detection power

Four new carriers in `kernels/k_litmus.metal`, dispatched **grid 256 / tg 64 =
4 threadgroups × 2 simdgroups each** (measured SIMD width 32):

- **Multi-invocation ordering litmus** (§5 Phase 3, *"for synchronization, use a
  real multi-invocation ordering litmus; scalar success cannot assign ordering
  semantics"*). The subgroup result crosses **threadgroup memory** and is read
  back from a lane in the **other simdgroup**; a **device atomic** that all 256
  invocations contribute to is read back and checked against a host total, so
  "all four threadgroups ran and their writes became visible" is measured.
- **Repeated reads across barriers.** The operand is read again after two
  barriers and the atomic — the point at which a *retain in register cache* /
  *future reads undefined* hint must bite if it is one.
- **Operand provenance** (§6). Each litmus is an `_ld` / `_alu` pair differing
  only in how the operand was produced (device load vs pure ALU on the thread
  id). Revision A found `simd_shuffle.cache` live on a load-seeded source, and
  the compiler itself chose `cache=1` for `lb_shuffle_ld` and `cache=0` for
  `lb_shuffle_alu` — the split is now a named dimension, not a guess.
- **Three disjoint readback plans** (§6): out[0..255] the instruction's own
  result, out[256..511] the same after the cross-simdgroup round trip,
  out[512..767] the operand re-read. A hidden write or destination alias cannot
  masquerade as inertness in all three.
- **Unique per-invocation codewords** (§5 Phase 3): every one of the 256
  invocations is seeded with a codeword unique across the whole dispatch, so
  lane / width / swizzle / register / immediate readings of a result cannot
  alias. Asserted in `carriers205.py`, not assumed.
- **Pre AND post sentinels** (Gate B): out[1000]=12345 stored first,
  out[1001]=54321 stored last. Both are required; the post sentinel proves the
  program ran to completion past the barriers and the atomic.

Calibration (`raw/prefreeze/calibration06_litmus.json`, pre-freeze): all four
carriers `OK`, exactly one occurrence each, both sentinels present, tail still
poison, and **all four host oracles matched** — plan 1, plan 2, plan 3 and the
cross-threadgroup atomic total.

## B3. Gate A, now met

`run.py` re-reads the spliced archive **from the file handed to
`newLibraryWithURL:`**, extracts the instruction bytes at `main_off + off`,
decodes the field back out of those bytes with `locate205.get_bits`, and records
per case: `requested_value`, `requested_bytes`, `actual_bytes`,
`decoded_value`, `program_sha256`, `program_len`, `main_off`, `off`,
`start`/`width`, plus `db_sha256` and `harness_sha256`. A case where
`requested != decoded` or `requested_bytes != actual_bytes` is recorded with
outcome **`ledger_mismatch`** and is not a hardware observation.

## B4. Gate E, now met as far as a shared machine allows

Revision B runs **runB01 forward and runB02 with carriers, arms and values in
REVERSED order** (`--reverse`), so an ordering artefact cannot be shared by a
run and its confirmation. Concurrent GPU processes are sampled into each
`env.json`. **The neo is shared and cannot be made quiet by this experiment**;
per EXP-0160's filter, two agreeing clean dumps still win outright, because
contamination can destroy an observation but never fabricate a coherent one.
Where the machine was busy, `RESULTS.md` says so rather than claiming quiet.

## B5. Verdict shape (replaces §6's single label)

Six independent axes per `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §2 — encoding
geometry, liveness, semantics, compiler recipe, target, reproducibility — with
**exact numerators and denominators, never a percentage alone**, plus:

- `sem_checked == 0` can never yield `hardware-run` / `semantically-mapped`.
- A failed positive control makes the arm **`carrier-undecidable`**; zero
  movement is not evidence of inertness.
- Safe negative wording only: **`inert in <exact tested envelope>; global role
  unknown`**. Never `unused`, `reserved`, `don't-care`, or `may be chosen
  arbitrarily`.

## B6. Falsifiers for revision B

1. If the litmus carriers' **positive controls do not fire**, every `cache`
   arm on them is `carrier-undecidable` and this amendment has answered nothing.
2. If `simd_shuffle.cache` moves on `lb_shuffle_ld` but not `lb_shuffle_alu`,
   the effect is **provenance-conditional**, and the correct statement is a
   contextual field with a stated predicate — not a global one.
3. If `simd_ballot.cache` moves on a litmus carrier and not on revision A's,
   revision A's null was the single-simdgroup blind spot, exactly as suspected.
4. If it moves on neither, the claim remains bounded to the tested envelope and
   the ordering dimension is now *tested* rather than *unexpressed* — which
   changes `carrier-undecidable` to `accepted-inert in <envelope>`, and nothing
   stronger.

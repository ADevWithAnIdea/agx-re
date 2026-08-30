# EXP-0187 — PRE-REGISTRATION

**Frozen before any gated capture.** Target: Apple A18 Pro / **G17P**
(`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal family Apple9),
`users-MacBook-Neo.local` / `192.168.10.243`. **Nothing runs on the M4.**
Clean-room category: **OWN-SHADER + HW-PROBE**. Every byte spliced, decoded or
inspected is the compiled form of our own MSL in `kernels/`. No Apple binary is
disassembled or introspected.

---

## 1. The two questions

**Target 1 (device).** Is `n4_rt_word.dst` — byte+1 of the 4-byte compact word
`04 <dst> 20 80` emitted in the intersection-query traversal setup — a field an
emitter may **choose**, or is it inert / unreachable?
`validation.json` records it `tokenization-only`, *"framing only (round-trips; no
value semantics established)"*. It is the **single** field of a single-field
instruction, so promoting it moves `n4_rt_word` across the emittable line by
itself. EXP-0184 named it the next target and left the RT carrier proven.

**Target 2 (census, no device sweep).** Can any MSL we author make the G17P
compiler emit `cubearray_coord_const`, `mesh_out_src`, or `n4_cf_word` at all?
All three have been declined on a **measured** basis before (EXP-0184: 0
occurrences across 24 carriers for the first two; EXP-0172: `n4_cf_word`'s whole
4-byte word showed no detection power). The question is therefore not "sweep
them" but "can a carrier be built". **A bounded negative — "N constructs tried,
none emitted it" — is the deliverable**, and no device time is spent on a carrier
that could not be built.

## 2. Falsifiable hypotheses

* **H1 (target 1).** `n4_rt_word.dst` is a live destination selector: there
  exists at least one aligned occurrence and at least one value in 0..255 whose
  substitution changes the observed ray-query result, reproducibly across two
  gated runs.
  **Refuter A:** all 256 values at every one of the 32 aligned occurrences, in
  both runs, produce the arm-open baseline partition exactly → `dst` is inert on
  every carrier we can build.
  **Refuter B:** no control ever fires → the method had no power and the field
  stays `untested` (rounding up is forbidden).
* **H2 (target 1, the liveness discriminator).** If `dst` never moves, the
  whole-word match-byte probes (byte+2, byte+3) discriminate between *"the field
  is inert"* and *"this occurrence is never executed"*: a match byte that moves
  proves the four bytes are executed and observable; one that does not, on top of
  an inert `dst`, means the occurrence has no observable effect at all — which is
  EXP-0172's DEF-0172-4 finding for the sibling `n4_cf_word`.
* **H3 (target 2).** For each of the three opcodes there exists an MSL construct
  whose compiled `_agc.main` contains the opcode **as a token of a resync walk**,
  not merely as a byte signature.
  **Refuter:** every authored construct compiles and none yields a walk hit →
  bounded negative, reported as such, with the construct count.

## 3. Independent / dependent variables

* Independent (target 1): the 8-bit value written into `n4_rt_word.dst` at ONE
  aligned occurrence, one occurrence per arm, one value per dispatch. Nothing
  else in the program changes — the archive is byte-identical apart from that
  one field.
* Dependent: the ray-query result word `out[0]`, plus the integrity sentinel
  `out[1]`, the poison tail `out[2..3]`, the command-buffer status, the OS fault
  classification string, and the tokenized mnemonic of the mutated bytes.
* Independent (target 2): the MSL construct. Dependent: signature-hit count and
  tokenizer-walk-hit count per opcode.

## 4. Confounders, and how each is handled

1. **The observable co-varying with the field under test** (protocol 3a, EXP-0140).
   Excluded **by construction**: the swept byte is inside the traversal-setup word;
   the read-back is the store the compiler already emitted for `out[0]`, whose data
   and index registers are never touched and whose instruction is never the one
   mutated. No part of the oracle or the read-back path is derived from the swept
   value.
2. **Eight arms that are one arm** (EXP-0164). The eight carriers differ along
   three axes — query PHASE (candidate vs committed), TRAVERSAL PATH (triangle /
   bounding-box / instance), REGISTER PRESSURE (one getter vs three) — and the
   census confirms two distinct compiled baselines (`0x42` on seven carriers,
   `0x22` on `rq_inst`), i.e. both selector values `db.json` records from the
   corpus.
3. **A control that cannot fail** (EXP-0138, the sixth shape). `n4_rt_word` has
   three fixed match bytes; sweeping one of them "fires" by encoding a different
   opcode. They are therefore **never** used as controls — only as whole-word
   liveness probes, routed to `match_byte_probes`, which can never carry a field
   label. See §5 for what is used instead.
4. **False hangs from a watchdog timeout** (protocol 3d). The runner is the
   upstreamed `tools/agxtest/saferunner.py`, pinned and resolved by absolute path,
   with one reader thread per child; a malformed response is a
   **measurement failure with the raw lines kept**, never a hang, and is removed
   from the agreement computation and from `values_dispatched`.
5. **A hang budget hiding a contiguous hazard** (protocol 3c). **There is NO
   abort path.** Every value of every arm is dispatched.
6. **Silent zeros / dispatches that wrote nothing** (protocol 7). Poisoned
   read-back (`0xDEADBEEF + i`), an integrity sentinel written before the query
   through an independent path, `InnocentVictim` retried first, majority-of-3 on
   every non-OK case, and a sentinel-missing dispatch scored `invalid_run` and
   re-run — never `silent_zero`.
7. **Movement that is really a different instruction.** The tokenized mnemonic of
   the mutated bytes is recorded on **every** case, and `encodable_range` counts
   only values that still re-decode as the target mnemonic.
8. **`device_load` asynchrony on G17P.** Not applicable: no carrier seeds a
   register through a device load under test, and there is no periodically
   refreshed baseline — each arm takes its own open/close baseline of the
   **unmutated** program and every case is compared against the arm-open key.
9. **Sibling contamination.** The dispatch states the device is free. Concurrent
   GPU processes are **sampled into `raw/<run>/env.json`** so "the machine was
   quiet" is a measurement, not a claim.

## 5. Detection power — the honest statement

`n4_rt_word` is `04 <dst> 20 80`: byte0, byte+2 and byte+3 are fixed match
constants and `dst` is the only modelled field. **No same-instruction control is
possible.** Two weaker controls are generated and every verdict records which one
backed it:

* **`same_program_point`** — where the pinned tokenizer says the op at `off+4` is
  one with a known-live field, that field is swept there. The census finds this at
  **3 of 32** occurrences (all in `rq_inst`, successor `if_push`, control
  `scope_kind`, `hardware-run` per EXP-0140). This proves the program point is
  executed and observable.
* **`carrier`** — `rt_query_traverse.opB` (byte+7) at every aligned
  `rt_query_traverse` occurrence in the same carrier. HW-VALIDATED load-bearing on
  A18 (EXP-M4-14) and re-measured on G17P by EXP-0184. This proves the **carrier**
  has an observable ray-query path; it does **not** prove a given `n4_rt_word`
  occurrence is executed. The four opB values EXP-M4-14 measured as hanging the
  traversal (`0x02,0x06,0x07,0x40`) are excluded: a control only has to fire.

A target arm with neither control is **barred from supporting any verdict, inert
or live** (EXP-0172 gate rule 3).

## 6. The gate (implemented by `analysis/verdicts.py` and nothing else)

1. Two gated runs, byte-identical programs, the same frozen `harness/arms187.json`.
2. **≥ 99 % per-value cross-run agreement** on the outcome partition, and
   **`moved >= 2 * disagree AND moved >= 1`**. Written exactly that way, **not**
   `moved >= 2 * max(disagree, 1)`: that form silently cannot promote any width-1
   field, and it suppressed a real result on 2026-08-30.
3. Detection power per §5.
4. Arm-open and arm-close baselines both `ok`.
5. Measurement failures removed from agreement and from `values_dispatched`;
   a field with > 1 % measurement failures is refused.
6. Labels: LIVE → `hardware-run`; INERT-ROBUST → `single-template-inference`
   (**not** emitter grade: emitter grade asserts the implementer may *choose* the
   value, and "emit what the compiler emitted" is a captured-template dependency);
   STILL-UNDERPOWERED → `untested`. No rounding up.

## 7. Method

**7.1 Carriers (target 1).** `kernels/k_rq187.metal`, eight `intersection_query`
kernels; geometry fixed by `harness/agxrun_persist_as.m` (EXP-0157's AS-capable
runner, reused verbatim and cited): 3 non-opaque triangles at z = 3,2,1 in
geometry 0 plus 1 at z = 4 in geometry 1; a bbox AS of 3 boxes; an identity
instance AS. Ray (0,0,0) → (0,0,1), t ∈ [0,100]. Every oracle is **non-zero** and
host-computed.

**7.2 Runner.** `agxrun_persist_as` under the pinned upstreamed safe runner;
poisoned output slot bound as an input file; grid 1 / tg 1; RT request timeout
**10 s**; `CONFIRM_ATTEMPTS = 3`, `INNOCENT_RETRIES = 3`, `CANARY_RETRIES = 3`.

**7.3 Pre-freeze calibration** (`raw/prefreeze/`, **NO verdict may cite it**):
`analysis/census.py` compiles every carrier and locates occurrences; a sampled
pilot (`raw/prefreeze/pilot01`) validates the harness end to end. The pilot found
one defect and it is recorded rather than repaired silently: **the `rq_multi`
host oracle was wrong** (124 vs the 121 the unmutated program returns in all 37
baseline dispatches — committing inside the loop shrinks the ray interval after
the nearest hit, so the candidate loop runs once). The constant is corrected
pre-freeze. The gate compares each case against the **arm-open baseline**, never
against the oracle, so the wrong constant could not have fabricated movement.

**7.4 Arm selection rule** (frozen; implemented by `analysis/gen_arms.py`, whose
docstring is normative): every carrier that emits `n4_rt_word` contributes
**every parcel-aligned occurrence**, each swept **dense over all 256 values** —
no per-carrier occurrence cap, because 32 × 256 is affordable here and EXP-0184's
own conclusion was that freezing blind on a subset risks a confident meaningless
INERT verdict. Plus, per occurrence, two 16-value whole-word liveness probes
(byte+2, byte+3) and, where available, the same-program-point control; plus the
carrier-level `rt_query_traverse.opB` controls.

**7.5 Target 2** (`analysis/census2.py`): 12 cube/cube-array constructs, 8
divergent-CF/barrier/RT constructs, 6 mesh-pipeline constructs (the first
**mesh-stage** attempt at `mesh_out_src` — every previous census was blind by
construction because all 24 carriers were compute kernels). Compile with our own
`shdump` / `shdump_mesh`, then report per construct both the **signature hits**
(upper bound; a hit may be another op's operand tail) and the **tokenizer-walk
hits** (the number that decides "the compiler emits it"). Walk leftovers are
recorded, because a walk that stops early can only undercount.

## 8. Declined before any device time

* `cubearray_coord_const.b3`, `mesh_out_src.sel`, `n4_cf_word.b3` — **no device
  sweep**, by dispatch: each has already been declined on a measured basis, so
  target 2 is a census and stops at a bounded negative if no carrier exists.
* `n4_rt_word` byte0 — a match constant AND the 0x04 group leader; changing it
  changes the instruction's length as well as its identity, desynchronising the
  stream, so it is not even a useful liveness probe.
* `ret.scoreboard`, `dev_scoreboard_fence.scope_flag` — declined four
  experiments deep; not revisited here.

## 9. Raw record schema

One JSON object per case appended to `raw/<run_id>/sweep.jsonl` and
flush+fsync'd immediately (never buffered): `carrier, arm, instr, field, value,
bytes, token, observed{vals, vals_u32, sent_u32, sentinel_ok, tail_ok,
tail_u32, unwritten, gputime_ns, status}, oracle, match, outcome, status,
statuses, fault_classes, innocent_retries, role, occ, off, instr_len, start,
width, note, ts`.
`outcome` ∈ `ok | silent_zero | wrong_value | not_written | fault | hang |
invalid_run | nondeterministic | measurement_failure | carrier_ready |
carrier_start_failed`. Faults, hangs and no-ops are **kept**.

## 10. Environment, timeouts, revision

Recorded in `CAPTURE_CONTRACT.json`: the repo revision **at pre-registration**
(carried forward verbatim by every re-freeze — captures are compared against that
recorded value, never against live `HEAD`, because the orchestrator commits
sibling experiments continuously), 23 authored + pinned blob hashes, the target
description, and all timeouts. `harness/verify_remote.py` re-verifies the hashes
**on the device** as a **separate, unchained step** after every push: a frozen
contract hashes what you authored, not what the device is running, and that check
caught 11-of-18 against its own author on 2026-08-30.

## 11. Safety

No abort path (§4.5). If a contiguous hazard appears it is a first-class result
and is reported as a wall, not clipped by a budget. `macvdmtool` is **forbidden**;
if the neo stops answering the experiment STOPS and reports BLOCKED.

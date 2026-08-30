# PRE-REGISTRATION — EXP-0152 (M4/G16G)
## Closing the control-flow and memory-family remainders

**Frozen before any build or capture.** Nothing below is edited after the first gated
run; deviations are recorded in `RESULTS.md` §Deviations, never by rewriting this file.

Target: **local Apple M4 / G16G only.** No A18 (hands-off), no M5, never `macvdmtool`.

---

## 0. Question

`docs/evidence-classification.md`'s `emittable` rule says a family is emittable only when
**every** field an emitter must fill is `hardware-run` or `isolated-byte-diff`. Per
`tools/agx-isa/validation.json` at freeze, sixteen instructions in two families still have
blocking fields:

| family | instruction | blocking fields at freeze |
|---|---|---|
| CF | `if_push_pred` | `level` |
| CF | `jump` | `branch_ctrl` |
| CF | `pop_reconverge` | `reserved` |
| CF | `mask_op` | `mask_bank`, `scope_kind` |
| CF | `ret` | `linkmode`, `scoreboard` |
| CF | `ret_luse` | `linkmode`, `tail` |
| CF | `jump_cond` | `cf_scope`, `offset`, `reserved` |
| CF | `call` | `b3`, `b5`, `b6`, `tail` |
| CF | `call_indirect` | `b2`, `target_lo`, `b4`, `b5` |
| MEM | `tg_addr_compute` | (0 modelled; instruction-level `emit_unsafe` veto) |
| MEM | `dev_scoreboard_fence` | `scope_flag` |
| MEM | `mem_fence8` | `mask`, `tail` |
| MEM | `atomic_mem` | `op_lsb`, `per_lane`, `op_msb` |
| MEM | `atomic_rmw` | `op_lsb`, `per_lane`, `op_msb` |
| MEM | `mem_fence` | `sub`, `memclass`, `b5` |
| MEM | `atomic_tg` | `op_desc`, `rsv10lo`, `op`, `op_hi_rsv` |

**The question this experiment asks:** which of these can be moved to emitter grade with
carriers that make the field *live on an observable output path*, and — specifically —
**does a loop become emittable?** A loop needs `if_push_pred`, `jump_cond`, `if_push`,
`ret`, `jump` and `pop_reconverge` all emittable simultaneously.

## 1. Scope decided at freeze (and what is deliberately NOT attempted)

**IN:**

* CF: `jump.branch_ctrl`, `pop_reconverge.reserved`, `ret.linkmode`, `ret.scoreboard`,
  `ret_luse.linkmode`, `ret_luse.tail`, `if_push_pred.level`, `mask_op.mask_bank`,
  `mask_op.scope_kind`, and all three `jump_cond` fields.
* MEM: `atomic_mem` / `atomic_rmw` byte+12 (`op_lsb`|`op`|`per_lane`|`op_msb`),
  `atomic_tg` byte+5 (`op_desc`), byte+10 (`rsv10lo`|`op`), byte+11 (`op`|`op_hi_rsv`).

**OUT, with the reason stated now rather than discovered later:**

* **`mem_fence.{sub,memclass,b5}`, `dev_scoreboard_fence.scope_flag`,
  `mem_fence8.{mask,tail}` — NOT attempted.** `FIELD-SWEEP-PROTOCOL` §3.2 requires the
  field to be live on the observed output path. EXP-0141 swept all four of the first two
  densely and refused promotion because **neither carrier has a memory-ORDERING
  observable**; EXP-0147 reached the same `INSUFFICIENT` verdict on six fence fields. A
  carrier that cannot detect the fence's *removal* cannot test the fence's *scope bits*,
  and a pass would be a false `hardware-run`. `mem_fence8` has no dispatchable carrier at
  all (emitted only by `intersection_query` traversal; `agxrun_persist` cannot bind an
  acceleration structure). These six fields are pre-registered to be reported **`untested`
  with an explicit insufficiency statement**, not swept.
* **`tg_addr_compute` — the `emit_unsafe` veto STANDS** (EXP-0141 H5: on M4 only byte0
  `0x1c` works, EXP-M4-14's A18 `0xfc` does not reproduce; two live operand bytes are
  unmodelled as fields). Not re-probed.
* **`call` (14 B) and `call_indirect` (6 B) — NOT attempted.** Neither appears in the
  frozen 152-byte CF skeleton, and the only same-length splice sites available
  (`device_load`/`device_store` for `call`, `pop_reconverge` for `call_indirect`) would
  transfer control to an address computed from uninitialised state — the exact
  construction that hung the GPU in EXP-0128. Authoring a call carrier is a successor's
  job. Reported `untested`.

## 2. Hypotheses, each with its refuter

**H1 (jump).** `jump.branch_ctrl` is inert across its whole byte inside a program whose
oracle proves the back-edge executed, except for values `{0,1}` which EXP-0140 `run03`
observed as reproduced hangs (its `run02` observed them inert — the two disagree).
*Prediction:* 2..255 all reproduce the CF baseline oracle exactly.
*Refuter:* any value in 2..255 that changes the output or faults reproducibly.
*Safety:* `{0,1}` are **excluded from dispatch** and reported as a documented
do-not-emit hole, because two hangs would consume this experiment's whole CF budget.

**H2 (pop_reconverge).** `pop_reconverge.reserved` (16 bit) is inert over the protocol's
wide-field sample at both of the skeleton's two `pop_reconverge` sites.
*Refuter:* any sampled value that changes the output.

**H3 (ret).** `ret.linkmode` runs only when `(v & 7) == 4` (EXP-0140 `run02`, 224/256
faulting) and `ret.scoreboard` accepts a masked subset.
*Refuter:* an accepted-value set that differs from `(v & 7) == 4`.
*Safety:* `scoreboard` values `{8,12}` are excluded (EXP-0140 reproduced hangs).

**H4 (ret_luse).** `ret_luse` is `ret` with byte+2 `0x54 -> 0x56`; splicing that one byte
in place at the skeleton's `ret` site yields a 4-byte `ret_luse` at the identical address,
so `linkmode` (byte+1) and `tail` (byte+3) can be swept with no displacement change.
*Prediction:* `ret_luse.linkmode` has the same accepted set as `ret.linkmode`.
*Refuter:* a different accepted set, or byte+2 `0x56` alone breaking the program (which
would mean `ret_luse` is not a drop-in variant, itself a first-class result).
*Safety:* `tail` excludes `{8,12}` for the same reason as `ret.scoreboard`.

**H5 (if_push_pred).** `if_push_pred.level` accepts only `(v & 0xFC) == 0x00` (EXP-0140).
*Refuter:* an accepted value outside that mask.
*Safety:* `{62,63,180,181}` excluded (EXP-0140 reproduced hangs, both runs).

**H6 (mask_op).** `mask_op` (`0f 04 <mask_bank> <scope_kind>`) is 4 bytes, exactly the
length of the skeleton's `if_push` (`0f 05 54 1a`) at sequence index 7. Splicing `mask_op`
over `if_push` executes a real `mask_op` at a real execution-mask site with no length or
displacement change.
*Prediction (liveness gate):* the compiler-natural `mask_op` (`0f 04 04 19`) spliced over
`if_push` **changes the output** — i.e. `expect_match=False` against the CF baseline. That
is the pre-registered proof that the instruction is live; only if it holds are the two
byte sweeps interpreted at all.
*Refuter:* the substitution reproduces the baseline exactly, which would mean the site
cannot distinguish `mask_op` from `if_push` and the arm proves nothing (reported
`untested`).

**H7 (jump_cond LIVENESS — the loop unlock).** EXP-0140 found every `jump_cond` field
inert *because the branch was never taken*: the skeleton's guard is `cnt <= 0 -> skip the
loop`, the branch is uniform across the SIMD, and with `n = [0,1,2,3,4,8,16,32]` at least
one lane has `cnt > 0`, so the guard is false and the branch falls through. **Binding the
`n` buffer to all zeros makes the guard uniformly true and the branch actually taken**,
with no change to a single program byte, no length change and no displacement
recomputation.
*Prediction:* with `n = 0` and the natural offset `0x40`, the output equals the fall-through
oracle `a[tid] - 3` (the loop body runs zero times either way). With `n = 0` and a
**poison offset** the output **differs** from that oracle (`expect_match=False`), while the
same poison offset under the *original mixed* `n` **reproduces** the mixed oracle
(`expect_match=True`) because the branch is not taken there. Two pre-registered poison
offsets: **P1 = 0x5c** and **P2 = 0x52**.
*Refuter:* the poison offset reproduces the baseline under `n = 0` too — the carrier is
still dead and all three `jump_cond` fields stay `untested`, exactly as EXP-0140 reported.

**H8 (jump_cond.offset).** Under `n = 0` the displacement selects the resume point, so a
**dense** forward window of displacements is observable.
*Range dispatched:* `offset` = 58..110 **dense** (53 consecutive values; every target from
the first post-loop instruction start through one past the end of `_agc.main`), plus far
probes `{112,128,256,1024}`.
*Deliberate exclusion:* **no negative and no small (0,1,2) displacement is dispatched.**
With the branch now genuinely taken, a backward or self-targeting displacement is an
infinite loop; EXP-0128 hung the GPU exactly this way, and EXP-0115's checkerboard reach
was measured on `jump`, not `jump_cond`, so it does not transfer.

**H9 (jump_cond.cf_scope / .reserved).** Swept at a poison offset, each value is
classifiable as *branch taken* (output == the poison-offset result) or *branch not taken*
(output == the fall-through oracle) or *other/fault*. Both fields are swept densely
0..255 at **both** P1 and P2 so the conclusion does not rest on one poison target.
*Refuter:* the two poison targets disagree on a value's class.

**H10 (atomics).** `atomic_mem` / `atomic_rmw` byte+12 and `atomic_tg` bytes +5/+10/+11
each contain 2–4 modelled fields. A **dense 0..255 sweep of the whole byte executes every
value of every field it contains, crossed against every value of its byte-mates**, so a
per-field verdict is the projection of the byte's accepted set.
*Prediction:* the accepted sets reproduce EXP-0141's (`atomic_mem` b12: 56 values,
`v & 0x01 == 0` not exact; `atomic_rmw` b12: 48 values; `atomic_tg` b10: only 0;
`atomic_tg` b11: 24 values `v < 32 and (v & 3) != 2`).
*Refuter:* a different accepted set on either of the two independent device-atomic
carriers.
*Safety:* `atomic_tg` byte+5 values `{0x7E,0x7F}` are excluded — EXP-0141 reproduced GPU
hangs there and published "DO NOT EMIT".

## 3. Independent / controlled variables

Independent: exactly one named field (or one byte) of exactly one instruction, per case.
For the `jump_cond` arms a second independent variable is the **`n` input buffer**
(`cfN` = EXP-0140's `[0,1,2,3,4,8,16,32]` vs `cf0` = all zeros); it is varied only in the
pre-registered paired-control cases, never inside a field sweep.

Controlled: the whole 152-byte CF skeleton (EXP-0090/EXP-0112, HW-validated, byte-for-byte
reused — never authored or padded here: EXP-0140 §9 showed that lengthening a CF carrier
is **not** semantically neutral even with `acc`-only padding); the `a` input; the dispatch
shape (8/8); the carrier `_agc.main` length; every other instruction's bytes.

## 4. Oracles (host-computed, GPU-independent)

* `cfN` baseline: `H.cf_oracle(a,n)` per lane — loop `n` times adding 1.5, then
  `acc > 100 ? acc*2 : acc-3`. Reused verbatim from EXP-0112; HW-confirmed by EXP-0140.
* `cf0` baseline: the same function with `n = 0`, i.e. `a[tid] - 3` =
  `[7,17,27,37,47,57,67,77]`.
* atomic carriers: EXP-0141's host-computed oracles, recomputed here from the MSL we wrote
  (`a[j] = 1000j+7`), never read off a GPU run.

## 5. Falsifiers dispatched (pre-registered `expect_match=False`)

1. `cf.falsifier` — unmutated skeleton against an unreachable oracle (proves match
   detection is not a rubber stamp). One per input configuration.
2. `mask_op` liveness gate (H6).
3. `jump_cond` poison-offset gate under `n = 0`, at P1 and P2 (H7).
4. `atdev` op-splice control: byte+12 `-> 0x22` (`and` instead of `add`), which EXP-0141
   showed changes the counter.
5. `attg` op control at byte+11.
6. `ret_luse` byte+2 `0x56` alone, pre-registered `expect_match=True` (the drop-in claim)
   — its failure is H4's refuter.

## 6. Known confounders

* **Concurrency.** Sibling GPU experiments turn their faults into our `InnocentVictim`
  failures (`FIELD-SWEEP-PROTOCOL` §7). Mitigations below.
* **Silent zeros.** A wrong field value usually yields a wrong value or an unwritten word,
  not a fault.
* **Non-local tokenization.** `docs/isa/README.md`'s `_r9_succ_safe` makes some lengths
  depend on *following* bytes failing to decode. Every case here is either a
  **same-length in-place byte splice** or a whole-program build of the frozen skeleton, so
  no displacement is ever recomputed; the decoder round-trip of the spliced region is
  recorded per case as `rt` but **never** used to skip a case (the hardware does not
  consult our decoder).
* **`mov_imm` immediates** are restricted to 0..127 and never 12 (EXP-0140 db-defect 4).
  No new `mov_imm` is emitted by this experiment anyway.
* **Poisoned read-back.** Buffer 0 is bound as an input pre-filled with `0xDEADBEEF + i`
  so an unwritten word is recognisable.

## 7. Mandatory `FIELD-SWEEP-PROTOCOL` §7 defences (all binding here)

1. **Majority-of-3 replication.** Every case runs 2 trials, and 3 whenever the first is
   not `ok` or the first two disagree. A `fault`/`hang` label requires the majority.
2. **OS fault-classification string recorded verbatim** for every failing trial;
   `...ErrorInnocentVictim` failures are segregated as `invalid_run` (environmental),
   never as a property of the encoding, and are retried up to 4 times.
3. **Periodic baseline re-validation** every 250 cases; two consecutive failures =>
   runner restart, then abort rather than record a cascade.
4. **Integrity sentinel.** The atomic/fence carriers write a `0xA5A5A5A5` sentinel word
   from their own MSL. **The CF carrier cannot carry one** — its `_agc.main` is exactly
   152 bytes and the reused skeleton fills it exactly, and EXP-0140 §9 proved that
   lengthening the carrier changes its semantics. There the poisoned read-back buffer is
   the integrity check, and a case whose 8 words are all still poison is `invalid_run`
   and repeated. This limitation is declared here, not discovered later.
5. **Unique splice-archive path per request**, unlinked afterwards.
6. **Poisoned read-back buffer** on every carrier.

## 8. Safety budget (`FIELD-SWEEP-PROTOCOL` §8)

* Per-request watchdog 8 s. **2 genuine hangs stop that arm.** **4 hangs stop every
  remaining CF arm** (EXP-0128 safety-stopped after two; EXP-0140 spent five). **8 hangs
  abort the run.** Skipped cases are recorded as `skipped`, never dropped.
* Arm ORDER is part of the contract, so that a CF-wide stop cannot cost the cheap arms:
  `cf.baseline` -> `jump.branch_ctrl` -> `pop_reconverge.reserved` -> `ret.linkmode` ->
  `ret_luse.*` -> MEM arms -> `jump_cond.*` -> `if_push_pred.level` ->
  `ret.scoreboard` -> `mask_op.*`.
* Known-hang exclusion list, dispatched as `skipped` records with the reason:
  `jump.branch_ctrl {0,1}`, `if_push_pred.level {62,63,180,181}`,
  `ret.scoreboard {8,12}`, `ret_luse.tail {8,12}`, `atomic_tg` byte+5 `{0x7E,0x7F}`.
* If the host wedges: STOP, mark BLOCKED in `PROGRESS.md`, wait for a manual reboot. No
  `macvdmtool`, ever.

## 9. Capture plan and the gate

Two gated runs with **different run ids**, never reused, never topped up. A field verdict
is promoted only if:

* both runs dispatched the same case set for that arm (`coverage_equal`), and
* the accepted-value sets are **identical** across the two runs, and
* the arm's own liveness gate / falsifier behaved as pre-registered.

Anything else is reported at the weaker label. `raw/` is append-only; a partial capture is
retained under its own id and never reused.

## 10. Rounding-up is forbidden

If a sweep is inconclusive the verdict is `corpus-correlation` or `untested`. Specifically:
a field whose every value is inert **in a carrier whose liveness gate did not fire** is
reported `untested`, not `hardware-run` — that is precisely the trap EXP-0140 avoided on
`jump_cond` and EXP-0141/EXP-0147 avoided on the fences.

## 11. Clean-room

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal, all authored by this project) and the
                  machine code compiled from it; instruction bytes assembled by our own
                  tools/agx-isa (read-only use)
Apple binary introspection: NONE
```

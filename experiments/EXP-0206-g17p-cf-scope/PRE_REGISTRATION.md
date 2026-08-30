# EXP-0206 — PRE-REGISTRATION (frozen before any build or device run)

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6
build 25G5043d, Metal family Apple9). **Nothing runs on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced or inspected is the compiled form of
our own MSL in `kernels/`. **No Apple binary is disassembled, decompiled or introspected.**

**Written and frozen before any carrier was compiled and before any device run.** The census
(`analysis/census.py`) and the pilot are **pre-freeze calibration**; §8 states explicitly that **no
verdict may cite them**.

---

## 1. The question

Seven fields across six control-flow instructions are the single blocker between those
instructions and emitter grade:

| instruction | field | start | width | current label | why it is blocked |
|---|---|---:|---:|---|---|
| `if_push` | `scope` | 16 | 8 | `single-template-inference` | declined by EXP-0184 (0/2560) — **known carrier-limited**: the loop-iteration region kind (`scope_kind == 0x1a`) was never reached |
| `pop_reconverge` | `scope` | 16 | 8 | `untested` | withheld for consistency on EXP-0191's detection gate: 512 valid observations per arm, **one** distinct payload, **no control of any kind at arm level** |
| `pop_reconverge` | `reserved` | 32 | 16 | `untested` | withheld on DEF-0190-1 — the INERT bucket returns `moved = 0` **by construction** |
| `call` | `tail` | 104 | 8 | `untested` | withheld on EXP-0189: the promoting gate had **no `moved >= 1` conjunct**, so a perfectly inert field passed it |
| `ret` | `scoreboard` | 24 | 8 | `corpus-correlation` | declined as pre-registered by EXP-0179: it is an **ordering** wait mask and neither carrier had anything to wait on |
| `ret_luse` | `linkmode` | 8 | 8 | `untested` | withheld on EXP-0192 **Case C**: 1 distinct VALID payload across 32 LEGAL values — a hazard map, not a semantic |
| `stop` | `reserved` | 8 | 24 | `untested` | withheld on DEF-0190-1; a reserved-bit claim needing a positive control in the same dimension (FIELD-SWEEP-PROTOCOL §9) |

Every one of the seven refusals has the **same shape**: the arm could not express the dimension the
field controls, or the gate could not come out the other way. This experiment attacks the *carrier*
and the *gate*, not the sample size.

**Established ABI facts taken as given and NOT re-derived:** the call target is
`call_addr + 4 + offset`, measured FORWARD (EXP-0035, EXP-0179); `pop_reconverge` is REQUIRED after
a call while the `0x43` frame marker is OPTIONAL (EXP-0179); `call.b6` bit 1 is load-bearing
(EXP-0179 arm S).

---

## 2. Hypotheses, expected observations and refuters

Each hypothesis names (a) the **dimension** the field would control, (b) the **carrier axis** built
to differ in it, (c) the observation that confirms, (d) the observation that **refutes**.

### H1 — `if_push.scope` is a live reconvergence-mask-bank selector at loop-iteration pushes

* **Dimension:** region KIND — conditional-skip (`scope_kind == 0x01`) vs **loop-iteration**
  (`scope_kind == 0x1a`).
* **Carrier axis:** six memory-bounded nested-loop shapes (`kernels/k_cf206.metal`). Trip counts are
  loaded from device memory so the compiler cannot unroll or flatten; EXP-0184's register-expression
  loops emitted no `if_push` at all.
* **Predicted, per value (this is the per-case ORACLE, not a constant):** at an occurrence whose
  compiled `scope_kind == 0x1a`, the program is **correct iff bit 1 of `scope` is set**
  (`value & 0x02 != 0`); at any other `scope_kind`, all 256 values are correct.
  Basis: EXP-0188's pre-freeze hazard probe, cited as a prior observation and **re-measured here
  under the gate**.
* **Confirms:** ≥ 2 distinct VALID payloads, or a valid↔hard split that follows the bit-1 rule, at
  ≥ 1 `0x1a` occurrence, in both gated runs.
* **REFUTES:** all 256 values give one indistinguishable valid payload at every `0x1a` occurrence
  **while the detection-power control fires on the same arm**. That is a far stronger negative than
  EXP-0184's, because the region kind it named would then have been reached and still be inert.
* **Also refutes the premise:** if no carrier emits `scope_kind == 0x1a`, H1 is untestable here and
  §9 requires reporting which region kinds *were* reached.

### H2 — `pop_reconverge.scope` is the matching mask-bank selector

* **Dimension:** same as H1 — which reconvergence bank is popped.
* **Carrier axis:** the same six loop shapes; occurrences selected to span `scope_kind` 0x01
  (guard/outermost) and 0x02 (loop body).
* **Predicted:** movement at ≥ 1 occurrence, concentrated in the bit that separates db.json's two
  documented values `0x04` and `0x24` (bit 5, `0x20`).
* **REFUTES:** one indistinguishable valid payload across 0..255 at every occurrence with the
  control firing.

### H3 — `pop_reconverge.reserved` (bits 32..47) is inert

* **Dimension:** the remaining operand space of the 6-byte reconvergence word.
* **Predicted:** every sampled value gives the baseline valid payload.
* **POSITIVE CONTROL REQUIRED (FIELD-SWEEP-PROTOCOL §9.1):** on the **same arm**, `scope_kind` of the
  **same instruction occurrence** must move the observable (produce ≥ 2 distinct valid payloads, or
  a valid↔hard split). Without that, the verdict is **UNRESOLVED**, never "inert".
* **REFUTES the inertness:** any sampled value changes the valid payload in both runs.

### H4 — `ret.scoreboard` is an execution/memory-ordering wait mask

* **Dimension:** memory/execution ORDERING — how much unretired memory traffic exists when the
  `ret` executes.
* **Carrier axis (`kernels/k_cl206.metal`), five points on one axis:**
  `k_cl_pure` (nothing outstanding) → `k_cl_ldret` (load inside the callee) → `k_cl_ldacross`
  (caller's load in flight across the return) → `k_cl_stacross` (store→load hazard spanning the
  return) → `k_cl_atomic` (atomic RMW in the callee, old value consumed after the return).
* **Predicted:** on the hazard carriers, clearing the documented wait bits (`0x20` = wait-set
  present, `0x04` = second slot) yields a **wrong value** (a stale or unordered read) or a fault,
  while `k_cl_pure` shows nothing. Concretely: ≥ 2 distinct VALID payloads on at least one of
  `k_cl_stacross` / `k_cl_atomic` / `k_cl_ldacross`.
* **REFUTES:** one indistinguishable valid payload across all five carriers with controls firing —
  which, unlike EXP-0179's decline, would then be a *dimension-spanning* null and reportable as such.

### H5 — `ret_luse.linkmode` distinguishes leaf from non-leaf returns

* **Dimension:** the LINK — whether a saved return address must be restored.
* **Carrier axis:** `k_cl_leaf` (no saved link) vs `k_cl_chain` / `k_cl_deep` / `k_cl_spill`
  (non-leaf frames).
* **Construction, stated because it is not a compiler-emitted occurrence:** the compiler does not
  emit `ret_luse` (byte+2 `0x56`) in these kernels. Each `ret_luse` arm is a real compiled `ret`
  occurrence with **byte+2 forced from `0x54` to `0x56`**, which EXP-0156 ran as a pre-registered
  identity control and which matched in both of its gated runs. The arm records a
  `role: "luse_baseline"` case (byte+2 = 0x56, compiled linkmode) so the construction is itself
  measured, not assumed.
* **Predicted:** at a NON-LEAF return whose compiled `linkmode == 0x12`, substituting the leaf value
  `0x02` fails to restore the link and returns elsewhere → a **different valid payload** or a fault;
  at a LEAF return `0x02` is correct. **≥ 2 distinct VALID payloads** is the bar, exactly as
  EXP-0192 Case C demands.
* **REFUTES:** V = 1 again across all four link-dimension carriers → the withdrawal stands and is
  reported as confirmed, not as a new gap.

### H6 — `stop.reserved` (bits 8..31) is inert, at BOTH stop positions

* **Dimension:** program TERMINATION.
* **Carrier axis:** every carrier in both kernel files. A kernel with an out-of-line callee places
  the callee **after** the main body's `stop`, so that stop must genuinely terminate; a kernel
  without one has only the final stop, which EXP-0003/EXP-0010 already showed to be inert.
  Occurrences are therefore classified `mid` (code follows) or `final` (nothing follows).
* **POSITIVE CONTROL REQUIRED (§9.1), and it is deliberately a MATCH byte:** at the same occurrence,
  byte 0 is set to values other than `0x0e`. This is **not** offered as a field control — changing a
  match byte changes which instruction the bytes are, and the protocol bars that for field verdicts.
  It is offered as a **termination-dimension positive control**: if the observable cannot even detect
  that the terminator word stopped being a terminator, the arm has no power to establish anything
  about that word, and the verdict is **UNRESOLVED**.
* **Predicted:** at a `mid` stop the positive control **fires** (execution falls through into the
  callee → fault or wrong value) and the 24-bit body is nevertheless inert; at a `final` stop the
  control does **not** fire (EXP-0003/EXP-0010) and the arm is reported **UNRESOLVED** whatever the
  body does.
* **REFUTES the inertness:** any sampled body value changes the valid payload in both runs.

### H7 — `call.tail` (byte+13)

* **Dimension:** unknown. It is the last byte of the 14-byte direct call; the two neighbouring raw
  bytes `b3`/`b5` are `hardware-run` with 256 distinct payloads, and `b6` carries a load-bearing
  bit. `tail` is swept across both dimensions built here (link and ordering).
* **Predicted:** **no prediction is registered.** The prior promotion is withheld precisely because
  "it reproduces perfectly" was treated as evidence; this experiment registers only the gate.
* **Confirms live:** ≥ 2 distinct VALID payloads with `moved > 0`.
* **Confirms inert:** V = 1 across 0..255 **with the positive control firing on the same arm**
  (`call.b6` bit 1, proven load-bearing by EXP-0179 arm S; and a small `call.offset` perturbation,
  which must change the branch target).
* **REFUTES either:** control does not fire → **UNRESOLVED**.

---

## 3. Independent, controlled and nuisance variables

* **Independent:** the value of exactly one field of exactly one instruction occurrence per case.
* **Controlled and held fixed within an arm:** carrier source, compiled archive, dispatch geometry
  (grid/threadgroup), input buffers, output size, poison prefill, watchdog, retry policy.
* **Nuisance / confounders explicitly handled:**
  * *Concurrent GPU work.* Sweeps run unlocked per FIELD-SWEEP-PROTOCOL §7; every non-`ok` case
    records the OS fault-classification string and `InnocentVictim` responses are retried before
    being scored. `env.json` samples the process table.
  * *False hang cascade (§3d).* One reader thread per child, tagged by owner; a malformed response is
    a **measurement failure with the raw lines kept**, never a hang.
  * *A dispatch that reports OK and writes nothing* (EXP-0160) — poison prefill plus the sentinel
    make it `invalid_run`, which is re-run and never scored.
  * *Mutation changing which instruction the bytes are.* The pinned tokenizer's opinion of the
    mutated bytes is recorded on **every** case.
  * *Compiler inlining.* The census reports, per carrier, whether the target instruction was emitted
    at all; a carrier that does not emit it contributes no arm and is reported as a dropped carrier.
  * *Aliasing.* The distinct mutated encodings actually dispatched are counted per arm; a sweep that
    dispatches 256 values over fewer distinct byte strings is reported as aliased.

---

## 4. Arm selection rule (frozen; `analysis/gen_arms.py` implements it and nothing else)

For each target field:

1. Locate occurrences of the instruction in `_agc.main` by **two independent methods** — a
   `match`-constraint signature scan and a full pinned-tokenizer walk — and keep only offsets both
   methods agree on. Disagreements are recorded in the census as a first-class result.
2. Record, per occurrence, the compiled value of the target field and of the instruction's
   **dimension field** (`scope_kind` for `if_push` / `pop_reconverge`; `linkmode` for `ret` /
   `ret_luse`; `follows_code` for `stop`).
3. Select, per carrier, at most `max_occ` occurrences, **maximising the spread of the dimension
   field** (one occurrence per distinct dimension value first, then by ascending offset).
4. Emit one **target arm** per selected occurrence, and one **control arm** per selected occurrence
   using the control field named in §5.

`max_occ` per field is frozen in `analysis/targets206.py`.

## 5. Detection-power controls (frozen)

| target | control field | why it is known live | control is a match byte? |
|---|---|---|---|
| `if_push.scope` | `if_push.scope_kind` (24, 8) | `hardware-run` (EXP-0140); and it is the region-kind axis itself | no |
| `pop_reconverge.scope` | `pop_reconverge.scope_kind` (24, 8) | `hardware-run` (EXP-0140) | no |
| `pop_reconverge.reserved` | `pop_reconverge.scope_kind` (24, 8) | same word, same occurrence | no |
| `call.tail` | `call.b6` (48, 8) and a small `call.offset` (56, 48) perturbation | `b6` bit 1 load-bearing (EXP-0179 arm S); `offset` HW-VALIDATED at 4 distances (EXP-0035) | no |
| `ret.scoreboard` | `ret.linkmode` (8, 8) | `hardware-run` (EXP-0179/EXP-0192 Case A) | no |
| `ret_luse.linkmode` | `ret_luse.tail` (24, 8) | `hardware-run` (EXP-0156) | no |
| `stop.reserved` | **byte 0** of the stop word (0, 8) | it is the terminator itself — see H6; offered ONLY as a termination-dimension control, never as a field verdict | **yes, and stated as such** |

**A control arm that does not move bars every verdict on its own target arm** — inert *and* live.
This is EXP-0172 gate rule 3 and DEF-0190-1's remedy applied prospectively.

## 6. Coverage (frozen)

* `if_push.scope`, `pop_reconverge.scope`, `call.tail`, `ret.scoreboard`, `ret_luse.linkmode`:
  **all 256 values, dense** (w = 8 → protocol §3 requires the full space).
* `pop_reconverge.reserved` (w = 16) and `stop.reserved` (w = 24): protocol §3 for w > 8 —
  `{0, 1, 2, max-1, max}`, **every power of two**, and ≥ 16 asymmetric interior samples. The exact
  list is generated by `analysis/targets206.py::wide_values()` and frozen with the arms.
* Control arms: 16 values each (a boundary/interior mix, listed in `targets206.py`).
* **NO ABORT PATH, NO HANG BUDGET** (protocol §3c): a per-field budget cannot characterise a
  contiguous hazard, it guarantees the region is never mapped. Every value in every arm is
  dispatched. If a *contiguous* hazard appears, it is mapped, not skipped.

## 7. The gate (frozen; `analysis/verdicts206.py` implements it and nothing else)

Verdicts are recomputed from `raw/` on every invocation and never read back from a manifest.

**Step 0 — outcome partition. Hard outcomes are NEVER movement.**
`fault`, `hang`, `no_draw`, `MALFORMED`, `undecodable`, `timeout`, `innocent_victim`, `invalid_run`
are counted, reported, and **excluded from the payload set**. A gate that separates `ok` from
`fault` counts a GPU fault as evidence; that defect (EXP-0192) is the reason `ret_luse.linkmode` is
on this list at all.

**Step 1 — per arm, from valid cases only:**
* `L` = number of values that executed legally (a valid payload was produced).
* `V` = number of **distinct valid payloads**.
* `moved` = number of values whose valid payload differs from the arm's own **arm-open baseline**
  payload.
* `disagree` = values whose valid payload differs between run01 and run02.
* `agreement` = 1 − disagree / comparable.
* `aliased` = whether distinct dispatched encodings < values dispatched.

**Step 2 — promotion to `hardware-run` requires ALL of:**
1. `V >= 2` — more than one **distinct valid payload**. (EXP-0192 Case C.)
2. `moved >= 2 * disagree` **AND** `moved > 0`. Written exactly so; **not**
   `moved >= 2 * max(disagree, 1)`, which cannot promote a width-1 field by arithmetic (§5b).
3. `agreement >= 0.99` per value across the two gated runs.
4. The **control arm at the same occurrence moved** (≥ 2 distinct valid payloads, or a
   valid↔hard split).
5. The frozen coverage of §6 was actually dispatched.
6. Not aliased, or the aliasing is reported in the verdict's `range`.

**Step 3 — an INERT verdict (`V == 1` over the full range) requires ALL of §9's four:**
a positive control **in the same dimension** that moved on the same arm; the swept (not sampled)
range of §6; cross-run agreement ≥ 0.99; and the falsifier stated in §2. If any is missing the
verdict is **`untested` with `verdict: "UNRESOLVED"`** — never "inert".

**Step 4 — the gate must be able to say no.** `analysis/verdicts206.py` carries a self-test that
feeds it (i) a synthetic dead-code arm (constant observable) and asserts it is NOT promoted and NOT
declared inert, (ii) a synthetic fault-wall arm (one valid payload, many faults) and asserts it is
NOT promoted, and (iii) a synthetic width-1 arm with 1 movement and 0 disagreements and asserts it
IS promotable. The gate refuses to run if the self-test fails.

## 8. What is calibration and may not be cited

`analysis/census.py`, any `--pilot` run, and anything under `raw/prefreeze/` are **pre-freeze
calibration**. They exist to choose arms and to measure throughput. **No verdict may cite them.**
Verdicts cite only the two gated run ids recorded in `CAPTURE_CONTRACT.json` after freeze.

## 9. Reporting obligations, whatever the outcome

* Report, per field: verdict, **V**, **L**, hard-outcome counts kept separate, cross-run agreement,
  whether the control fired, and the exact range dispatched.
* For `if_push.scope`, report **which region kinds were reached**, by carrier and occurrence.
* Faults, hangs and rejections are results. A reproducible wedge is a documented hardware fact and
  its encoding is recorded.
* If the neo becomes unresponsive: **STOP and report BLOCKED**. `macvdmtool` is forbidden here.

## 10. Environment and timeouts (frozen)

* Host: `192.168.170.254`, user `user`, password supplied only through `SSHPASS` + `sshpass -e`,
  never written to any file or artifact.
* Remote working directory: `~/agxre/EXP-0206/`. Binaries rebuilt there from pinned sources.
* Per-request watchdog: **8.0 s** (recorded in `env.json`, so a capture is never trusted about its
  own watchdog). Compile timeout 600 s. Every remote command wrapped in a hard alarm.
* Retries: `INNOCENT_RETRIES = 3`, `CONFIRM_ATTEMPTS = 3` (majority-of-3 on every non-OK case),
  `CANARY_RETRIES = 3` (a dispatch that wrote nothing is `invalid_run`, re-run, never scored).
* Pinned tools (`pinned/`), sha256 recorded in `CAPTURE_CONTRACT.json`. Nothing resolves through
  `tools/agx-isa` or `tools/agxtest`, which sibling experiments may be editing.
* Repo revision is **recorded, not gated**: sibling experiments commit continuously and a
  "HEAD must not move" gate would abort this experiment through no fault of its own. Captures are
  compared against the recorded **authored blob hashes**.

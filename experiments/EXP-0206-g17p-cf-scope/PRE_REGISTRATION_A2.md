# EXP-0206 — AMENDED PRE-REGISTRATION (A2), frozen before the first gated dispatch

**Supersedes nothing.** `PRE_REGISTRATION.md` stands as written and its hypotheses H1–H7
are unchanged. This amendment adds what
`/RE_EXPERIMENT_PROCESS_CORRECTIONS.md` (normative, published mid-experiment)
requires and that the original did not have, and it records the arm reduction forced by a
measurement. It is frozen **before the first dispatch of the gated pair**, as §4 of that
document requires. Everything captured before this point — `raw/prefreeze/census.json`,
`raw/pilot_20260830_p01/`, and the killed 152-case `raw/g17p_20260830_run01/` — is retained,
is calibration, and **is cited by no verdict**.

---

## A2.1 What changed, and why

| # | Change | Forced by |
|---|---|---|
| 1 | **Gate A actual-byte ledger** on every case | corrections §3 Gate A |
| 2 | **Competing semantic models with a per-case prediction** (`analysis/models206.py`) | corrections §3 Gate C |
| 3 | **Five-bucket observation vocabulary** (`correct` / `coherent` / `dead` / `reject` / invalid) | corrections §3 Gate C |
| 4 | **Reversed case order on the second gated run** | corrections §3 Gate E |
| 5 | **Process-table sampling into `raw/<run>/procs.jsonl`** | corrections §3 Gate E + FIELD-SWEEP-PROTOCOL §7 |
| 6 | **Arm reduction** (`targets206.SELECT`) | measured throughput, below |
| 7 | **Three structurally different carrier classes for every inertness target** | corrections §7 |

### The measurement that forced the arm reduction

The pilot ran at **0.234 s/case**. Gated run01 ran at **1.756 s/case with 46 % faults** and was
stopped at 152 cases. The process table showed **two sibling experiments sweeping the same
GPU** (`EXP-0202`'s `agxrun_persist` on `k_sam202.metal`, and another `run.py`). Every
`ErrorHang` resets the device; every reset costs seconds plus a train of `InnocentVictim`
retries. The unreduced 12,173-case set would have taken about **six hours per run**.

`raw/g17p_20260830_run01/` is **retained exactly as it is at 152 cases**, is never topped up,
and its run id is never reused. The replacement pair takes **new** ids.

**Value coverage per arm is unchanged.** The reduction is in *occurrences*, never in the swept
range — FIELD-SWEEP-PROTOCOL §3 coverage is a statement about a field's value space, and
corrections §5 Phase 2 says to dispatch every encoding of a ≤8-bit field. All 256 values are
still dispatched on every 8-bit arm.

---

## A2.2 Gate A — the actual-byte ledger (frozen)

Every case records, and `analysis/verdicts206.py` re-checks from raw:

```
requested value | complete REQUESTED instruction bytes | complete ACTUAL instruction bytes
read back out of the FINAL DISPATCHED BLOB at the region's absolute file offset |
value independently re-decoded from those actual bytes | sha256-16 of the whole dispatched
program | the instruction's absolute offset | pinned db.json + isadb.py sha256 (env.json)
```

`ledger_ok := (act_decoded == requested) AND (act_bytes == req_bytes)`.

**No hardware conclusion may be drawn from a case whose `ledger_ok` is false.** The verdict
report states, per field: cases requested, distinct requested values, **distinct ACTUAL
encodings**, and any collision. A symmetric assemble/disassemble round trip is explicitly not
this gate and is not used anywhere in this experiment.

## A2.3 Gate C — competing models, frozen in `analysis/models206.py`

Each model is a total host-side function `(arm, value) -> bucket | None`, computed from the
compiled occurrence's own bytes and never from a GPU result.

| field | models |
|---|---|
| `if_push.scope` | **M1 bank-parity** (correct iff `v&2 == compiled&2` at `scope_kind==0x1a`, inert elsewhere) · **M2 bit1-set** (EXP-0188's literal reading) · **M3 inert** · **M4 exact-match-only** |
| `pop_reconverge.scope` | **M1 bank bit 5** (0x04 vs 0x24 differ in bit 5) · **M2 low nibble == 4** · **M3 inert** · **M4 exact** |
| `pop_reconverge.reserved` | **M1 inert** · **M2 exact** · **M3 any-bit-live** |
| `call.tail` | **M1 inert** · **M2 exact** · **M3 low-bit-live** |
| `ret.scoreboard` | **M1 wait-mask** (nothing can matter on `cl_pure`, which has no memory op at all; the hazard carriers are where a difference must appear) · **M2 inert** · **M3 exact** |
| `ret_luse.linkmode` | **M1 link** (the compiled mode is correct and the *other* documented link mode is `coherent`) · **M2 accepted-set `v&7==4`** (EXP-0156's rule) · **M3 exact** · **M4 inert** |
| `stop.reserved`, `stop.reserved@synth_mid` | **M1 inert** · **M2 exact** · **M3 any-bit-live** |

Observed bucket, from the run's own outcome classification:
`ok→correct`, `wrong_value→coherent`, `silent_zero→dead`, `not_written→dead`,
`fault|hang→reject`, `invalid_run|measurement_failure|nondeterministic→` **invalid, never
scored**.

**A pre-run refutation already recorded from our own compiled code:** EXP-0156's
`v & 7 == 4` accepted-set rule (model M2 for `ret_luse.linkmode`) is contradicted by this
experiment's census — the compiler itself emits `ret_luse` as `8f 12 56 00` (linkmode `0x12`,
`v&7 == 2`) in `cl_atomic`'s `m_at` callee, and `ret` as `8f 02 54 00` (`v&7 == 2`) in every
leaf callee. M2 is registered anyway so the gated data scores it rather than an argument.

**Promotion rule for semantics.** A field reaches `semantically-mapped` only if exactly one
model predicts every *checked* case over the stated domain, and survives the adversarial
cases in the same run. **`sem_checked == 0` can never produce `hardware-run`.** Liveness
without a surviving model is reported as `live; role unknown`.

## A2.4 Gate B — detection power, and the independence test

Unchanged from `PRE_REGISTRATION.md` §5, plus corrections §5 Phase 5:

> Two generated carriers with the same leaf callee, state shape, or observation path count as
> ONE method for that dimension.

Applied honestly to this experiment:

* **`call.tail`.** EXP-0179's two carriers shared a generated leaf callee, which is why its
  inert reading was withheld. The three carriers kept here are `cl_leaf` (leaf callee),
  `cl_chain` (**non-leaf** callee `c_mid` which itself calls two leaves) and `cl_atomic`
  (callee performing an atomic RMW and returning through a real `ret_luse`). They differ in
  callee structure, in link depth and in memory behaviour. **They do share one observation
  path** — 32 per-lane words at fixed addresses — and that is stated as a limitation, not
  papered over. The **independent second method** is a compiler differential over our own
  shaders: `call.tail` is `0x00` in **8 of 8** compiled call sites, so the compiler never
  varies it.
* **`ret.scoreboard`.** `cl_pure` and `cl_stacross` share the identical callee `pf` and
  therefore byte-identical `ret` bytes; they differ **only** in the dimension under test
  (outstanding memory traffic at the return). That is the controlled comparison the field
  needs, not a blind spot — and `cl_ldret` (a different callee, with the load inside it) and
  `cl_chain` (a **non-leaf** return, linkmode `0x12`) supply the structural independence.
* **`if_push.scope`.** Three different loop shapes reach `scope_kind == 0x1a`, and two of them
  differ in the compiled bank (`0x54` vs `0x56`) — which is exactly the axis that separates
  model M1 from model M2.

**If a control arm does not fire, its target arm is `carrier-undecidable` and zero movement is
NOT evidence of inertness.** This is now the recorded liveness status, not a footnote.

## A2.5 Gate E — confirmation

* Two gated runs, **`run03` forward order and `run04` reversed order** (arms reversed and
  values reversed within each arm), so an order-dependent artefact cannot reproduce.
* `raw/<run>/procs.jsonl` samples the process table at run start, every 100 cases, and at run
  end. **Whether the machine was quiet is therefore a measurement in the evidence, not a
  claim in the prose.** This experiment expects it to show sibling activity, and the verdicts
  will say so.
* A malformed runner response is `measurement_failure` and is **never** a hardware outcome.
* Because a genuinely quiet machine is not available to this agent, every fault/hang claim is
  additionally adjudicated offline from the poisoned buffer and the sentinel (EXP-0160's
  filter: contamination can destroy an observation but never fabricate a coherent one), and
  cross-run agreement is computed **only over values that produced a valid payload in both
  runs**. Any verdict resting on a fault boundary is reported as
  `reproducibility: auditable`, **not** `independently-confirmed`.

## A2.6 Verdict shape (frozen)

`analysis/field_verdicts.json` reports, per field, the six independent axes of corrections §2
— **encoding geometry, liveness, semantics, compiler recipe, target, reproducibility** — plus
exact numerators and denominators (encodable / dispatched / distinct actual encodings / legal
/ silent / faults / hangs / invalid / untested), **never a percentage alone**, and the safe
negative wording `inert in <exact tested envelope>; global role unknown`.

The legacy label required by `docs/evidence-classification.md` is emitted alongside, and it is
**capped by the semantics axis**: no field with `sem_checked == 0` or with no surviving model
is proposed above `corpus-correlation`, whatever its liveness looks like.

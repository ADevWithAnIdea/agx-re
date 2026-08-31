# EXP-0213 — PRE-REGISTRATION

**Frozen before the first dispatch.** Successor to `EXP-0210-quiet-confirmation`. Same
target, same rule: this experiment runs each source experiment's **own committed harness**
and its **own frozen contract**, unchanged, with only the run id, the harness's own
selectors (`--arms` / `--mnem` / `--carriers` / `--only`) and the harness's own `--order`
varied. It does not edit any harness, any contract, any label, `tools/agx-isa/`, `docs/`
or `PROVENANCE.md`, and it commits nothing.

```text
Target                 Apple A18 Pro / G17P, AGXAcceleratorG17P, applegpu_g17p, 5 GPU cores,
                       macOS 26.6, Mac17,5, Metal family Apple9, 192.168.170.254
Clean-room provenance  HW-PROBE (re-running our own committed harnesses over shaders we
                       compiled from our own MSL) + black-box IOKit registry PROPERTY reads
Apple binary introspection   NONE
```

---

## 1. The question

`EXP-0210` closed Gate E for 17 of 22 named fields. Five things it could not reach:

| left open | why EXP-0210 could not close it |
|---|---|
| `tex_sample.mode`, `tex_write.amode`, `tex_write.rsv11` (EXP-0204) | **both** of its captures were stopped by EXP-0204's **own** cascade guard: `tex_write@twdyn` stopped reproducing its unmutated baseline. The pair covers 5055 of 9276 keys; `mode` reaches 2388/2560 = 93.28 % |
| `tex_deriv.dstsrc` (EXP-0204) | the frozen 8-hang-per-field budget is exhausted **six times sooner** on a quiet machine (48 hangs per capture vs 7 and 11 busy); the pair shares only 216 keys |
| `cf_nl2`, `cl_atomic`, `cl_leaf`, `cl_chain` arms (EXP-0206) | on a quiet machine these encodings **hang** where they faulted; the sweep rate collapses from ~4.8 to ~0.2 cases/s |

Both failures are consequences of one measured hardware fact — **a quiet GPU fails harder**
(EXP-0210 §9: silent-no-write → fault, fault → hang, 7/11 hangs → 48/48). This experiment is
designed around that fact rather than against it.

## 2. Hypotheses, each with its refuter

**H1 — the whole-run abort, not the arm, is what truncated EXP-0204's pair.**
EXP-0204's `run.py` breaks out of the **entire arm loop** on a cascade
(`if cascade: break`, twice). One arm losing its baseline therefore discards every arm after
it. Running the same harness **one arm per invocation** — using its own `--arms` selector,
nothing edited — should complete every arm that is not itself the destabiliser.
*Refuter:* if the per-arm captures also stop, or if arms unrelated to `tex_write@twdyn` lose
their baselines in isolation, H1 is false and the instability is device-wide, not run-scoped.

**H2 — `tex_write@twdyn` is itself the destabiliser, and it is reproducible.**
*Refuter:* `twdyn/0` and `twdyn/1`, dispatched **first** in the session and in isolation,
complete both fields with `baseline_final_ok: true`. That would make EXP-0210's baseline loss
an accumulation effect rather than a property of the carrier, and would leave the
22 000-accumulated-resets confounder as the live explanation.

**H3 — EXP-0204's 172 `tex_sample.mode` cross-run disagreements are an order artefact of the
particular pair EXP-0210 took** (`--order shuffle --seed 11` vs `--order reverse`), not a
property of the field.
*Refuter:* a forward/reverse pair disagrees on a comparable number of `mode` cases. Three
orders are captured per arm (forward, reverse, shuffle) so this is decidable rather than
merely asserted.

**H4 — EXP-0206's remaining carriers are confirmable once the two hazard ARMS are named and
separated.** A quiet hang costs a measured **24.07 s** (median, EXP-0206 `g17p_quiet01` and
`g17p_quiet02`); every other outcome costs ~0.01 s. The hang cost is therefore entirely
attributable to two arms.
*Refuter:* arms that recorded **zero** faults across every committed busy run nonetheless
hang on the quiet machine. That would mean the fault→hang escalation is not confined to the
already-faulting encodings, and the remaining carriers are unconfirmable at any budget.

**H5 — the escalation preserves the ok/not-ok partition.** EXP-0210 measured this on 14
values of one arm. Stage 6B, if reached, tests it over the full 256.
*Refuter:* a value that is `ok` on the busy machine hangs, or vice versa.

## 3. Gate E, as this experiment applies it

Two clean G17P runs, **in reversed or shuffled case order**, **identical actual-byte
ledgers**, **no victim/cascade evidence**, on a machine **measured** quiet. A malformed
runner response is `measurement_failure`, never a hardware outcome.

A capture that is stopped by its own cascade guard, by its own hang budget, or by this
experiment's external wall-clock cap is **not a clean run**. Its data is retained and
reported; it does not carry a MET verdict.

## 4. The quiet instrument, and the three defects it does NOT inherit

`harness/quietsample.py` is EXP-0210's sampler, copied **byte-identical**
(sha256 `47e2829e6d99…`). `harness/quietcheck.py` is new, and deliberately differs:

1. **`MTLCompilerService` is never counted as a foreign runner.** It is an XPC service that
   **launchd** owns, so it can never be a descendant of the sampler; a ppid walk misfiles our
   own shader compiles as foreign. EXP-0201's gate refused all six of its fields on 1 of 273
   such samples while printing 100.00 % agreement. It is counted and reported separately.
2. **A parenthesised process `comm` means an EXITING process** and holds no GPU context.
   EXP-0202's gate marked a run busy on one such zombie. Here the gate is stated on
   `max_foreign_runner_live`; the STRICT count including exiting rows is printed alongside,
   with every such row named, so a reader may apply either rule.
3. **`recoveryCount unchanged` is NOT a gate.** EXP-0210's own AMENDMENT-03 established that
   this criterion can never be met by a fault-heavy experiment, because our own
   pre-registered illegal encodings reset the device — a gate that cannot come out the other
   way. Here the reset counter is **reported**: `harness/gpusnap.py` records it immediately
   **before** and **after** every capture, and the sampler records it every 2 s throughout.
   The quiet criterion is stated on **foreign attribution** instead: zero live foreign
   dispatch runners in every sample, and no submitter PID that appears in the sampled rows as
   a foreign process.

QUIET = Q1 (zero live foreign dispatch runners in every sample) ∧ Q3 (no foreign submitter)
∧ Q4 (sampler alive, sample interval < 10 s) ∧ zero `ioreg` errors.

**Disclosed residuals, before any data:** the sampler's 2 s interval cannot see a GPU client
that starts, submits and exits between two samples; `fLastSubmissionPID` is a *last* value, so
PIDs absent from the sampled rows are reported as a named category rather than scored; and
`Device Utilization %` reads a constant 100 on this host with an idle GPU, so it is recorded
and not used.

## 5. Declared budgets and declared exclusions

### 5.1 EXP-0204 — the hang budget is the harness's own, and it is NOT changed

`run.py` freezes `MAX_HANGS_PER_FIELD = 2`, `MAPPING_PASS[("tex_deriv","dstsrc")] = 8`,
`MAX_HANGS_PER_ARM = 10`. This experiment does not change them.

`tex_deriv.dstsrc` sweeps a **pre-registered 65-value sample** of a 24-bit field. Its hazard
family is already mapped and is **9 of those 65 values**:
`0x03FFFF, 0x07FFFF, 0x0FFFFF, 0x1FFFFF, 0x3FFFFF, 0x7FFFFF, 0xFBEEE7, 0xFFFFFE, 0xFFFFFF`.
With a budget of 8, **no single capture in any order can sweep all 65 values** — the budget
stops the field at the 8th hazard. This is stated in advance, not discovered:

* the confirmation claim for `tex_deriv.dstsrc` is made over the **56 non-hazard values
  only**, and only over those a given pair actually shared;
* the 9 hazard values are **excluded by name** from the agreement claim and reported
  separately as a hazard-family reproduction check;
* **four** orders are captured (forward, reverse, shuffle 213, shuffle 1213) because ascending
  order puts the hazards last (~64/65 coverage) and descending puts them first (~27/65).
  **The Gate E pair is pre-designated `D_fwd` × `D_sh1`** — chosen now, before any of the four
  runs, so that the pair cannot be selected after seeing which shuffle covered more. `D_rev`
  and `D_sh2` are additional evidence and are reported separately.

### 5.2 EXP-0206 — an explicit hang budget, in device seconds

Measured from EXP-0206's own committed quiet partials: a hang costs **24.07 s** (median);
faults and every other outcome cost **~0.01 s**. Per-arm fault counts pooled over every
committed busy run identify exactly two hazard arms on the four remaining carriers:

| hazard arm | busy faults | expected quiet hangs | cost |
|---|---:|---:|---:|
| `if_push.scope@cf_nl2._agc.main+106` | 282/600 | 128 of 256 (`(v & 2) == 0`) | ~51 min |
| `ret_luse.linkmode@{cl_atomic,cl_leaf,cl_chain}` | 384, 384, 382 of 512 each | 64 of 256 each (`(v & 7) ∈ {4,5}`) | ~26 min each |

Three staged captures, each with its own declared budget, run in this order:

| stage | selection | values | hang budget | wall-clock cap |
|---|---|---:|---:|---:|
| **6A** | the 4 carriers **minus** the keys `if_push.scope` (cf_nl2) and `ret_luse.linkmode` | 2427 | 60 | 30 min |
| **6B** | cf_nl2 `--only if_push.scope` — **maps** the contiguous hazard rather than budgeting around it | 544 | 160 | 75 min |
| **6C** | `--only ret_luse.linkmode` on cl_atomic, cl_leaf, cl_chain | 272 each | 80 each | 35 min each |

**Excluded, by name, and why.** `if_push.scope@cf_nl2._agc.main+140` (256 values, **zero**
faults in every committed run) is excluded from stage 6A **only** because EXP-0206's `--only`
selector is keyed by field name and cannot separate it from the hazard arm `+106` on the same
carrier. Stage 6B recovers it. If 6B is not reached, it is reported NOT REACHED with that
reason, not silently dropped.

A stage that exceeds its wall-clock cap is killed by an **external** `alarm` wrapper — EXP-0206's
own `run.py` deliberately has no abort path and no hang budget, and that is not changed. The
partial is retained under its own run id, never topped up, never reused, and its arms are
reported **NOT REACHED** with the measured cost.

### 5.3 Global stop rules

* **If the neo stops answering: STOP and report BLOCKED.** `macvdmtool` is forbidden here.
* Any stage whose first capture exceeds its cap is not attempted a second time; its pair is
  reported NOT REACHED.
* Device-time budget for the whole experiment: **6 hours**. Stages are ordered so that the
  cheapest, highest-value work lands first and a stop costs at most one stage.

## 6. Capture plan

Run ids are new, live in each **source** experiment's own `raw/` tree, and are never reused.
Each is pulled back **one directory at a time** (`harness/pull_run.sh`, which refuses a pull
onto an existing local directory) — EXP-0210 disclosed that a tree-wide pull overwrote a
committed raw file.

### Phase 1 — EXP-0204 `tex_sample` / `tex_write`, per arm (H1, H2, H3)

`python3 -B run.py --run-id <id> --arms <ONE arm id> --order {forward,reverse,shuffle --seed 213} --deadline-s 300`

22 arms × 3 orders. **`tex_write@twdyn/0` and `tex_write@twdyn/1` are dispatched FIRST**, at
the lowest accumulated reset count this experiment will ever see, because EXP-0210 disclosed
that its EXP-0204 captures ran last, after ~22 000 accumulated device resets, and could not
exclude that as the cause of the baseline loss.

### Phase 2 — EXP-0204, the whole 22-arm set, exactly as EXP-0210 ran it

`--mnem tex_sample,tex_write --order {forward,reverse} --deadline-s 900`. This is the
discriminator for H1: if the full run aborts at `twdyn` while the isolated `twdyn` arm is
clean, the truncation is within-run accumulation; if the isolated arm also fails, it is the
carrier.

### Phase 3 — EXP-0204 `tex_deriv`, four orders

`--mnem tex_deriv --order {forward,reverse,shuffle 213,shuffle 1213} --deadline-s 900`.

### Phase 4 — EXP-0206 stages 6A, 6B, 6C, per carrier, two orders each

`python3 -B run.py --run-id <id> --carriers <c> --only <keys> --order {forward,reversed}`

## 7. Analysis plan, frozen

* **Ledger (Gate A):** `requested == decoded from actual dispatched bytes`, per capture; and
  **byte-identical `actual_bytes` on every shared key** across the pair.
* **Cross-run agreement:** keyed by **(arm, field, value, byte_index, carrier)** — whichever
  the record carries — with volatile fields excluded: `gputime_ns`, `ts`, `elapsed`,
  `prog_hash_fnv1a64`, `program_sha256`. EXP-0210 measured that `gputime_ns` moves
  **systematically** with machine occupancy (median 1874 quiet vs 1500 busy), which is exactly
  the variable a confirmation changes, so it can never be part of the key.
  Hard outcomes (`fault`, `hang`, `not_written`, `measurement_failure`, `undecodable`) are
  counted **separately** from payload agreement and reported both ways.
  The comparator is `analysis/pairwise.py`, EXP-0210's, copied byte-identical.
* **Per-field verdicts** are computed by each source experiment's own committed
  `analysis/verdicts.py` / `verdicts206.py`, run unedited on the new captures.
* Per-arm captures are concatenated into one logical capture file per (experiment, order) in
  `analysis/out/`; `raw/` is never modified.

## 8. What a NOT MET looks like, stated before the runs

Gate E is **NOT MET** for a field if any of: a capture in its pair is not measured QUIET; a
capture was stopped by a cascade guard, a hang budget or the external cap; the pair's shared
keys do not cover the field's declared value domain minus the named exclusions; any shared key
has differing `actual_bytes`; or any non-hard cross-run disagreement remains after the named
exclusions.

**"Gate E still not met for X" is the expected outcome for at least one row and will be
reported as such.** No number is to be forced.

## 9. Known confounders, listed before the data

1. **~22 000 accumulated device resets are already on this device** and cannot be cleared —
   `macvdmtool` is forbidden to this agent, and the machine has not rebooted since EXP-0210
   (`recoveryCount` 22134 at freeze, uptime 4 h 20 m). Phase 1's twdyn-first ordering bounds
   this confounder but cannot remove it.
2. Two runs of the same harness on the same machine share every systematic error that harness
   has. Reversing case order controls ordering artefacts, **not** carrier blind spots. Gate E's
   further clause — a genuinely different carrier or second method for load-bearing inertness
   claims — is **not** satisfied by this experiment for `tex_write.amode` / `tex_write.rsv11`,
   and is stated as unsatisfied rather than argued around.
3. Only Gate E is re-run. Gates A, B, C and D are inherited from each source experiment and
   are **not** re-audited here.
4. Per-arm invocation changes the dispatch *shape*: each arm gets a fresh runner process and a
   fresh baseline. That is the intervention under test (H1) and is also a difference from the
   committed captures. Phase 2 keeps the original shape so both are on record.

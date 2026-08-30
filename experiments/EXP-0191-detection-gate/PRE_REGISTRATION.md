# EXP-0191 — PRE-REGISTRATION: a detection-power gate on every INERT verdict

**Frozen at repo revision `cd2f05dd96e8bef4ffb797ca0cdb1fa7c1f6604f`, working tree
clean (`git status --porcelain` → 0 lines), BEFORE any gate verdict was computed.**

**PURE OFFLINE ANALYSIS.** No device is contacted; the A18 Pro is down. Every input is
already-committed evidence captured by earlier experiments.

---

## 1. The question

`EXP-0190` §7 recorded **DEF-0190-1**: `audit.py`'s `classify()` reaches `INERT-MULTI` /
`INERT-SINGLE` from `moved == 0`, and `moved` is derived from the hash of each record's
`observed`. An arm whose observable never varies returns `moved = 0` **by construction**,
so the inert buckets cannot come out the other way. `INERT-MULTI` is not withheld, so a
field can hold emitter-grade status on an arm that never demonstrated it could see
anything at all.

**Question.** For every `INERT-*` field in the corpus: did the arm that produced its
inert verdict ever demonstrate that its observable can move? An `INERT` verdict from an
arm that never demonstrated movement establishes nothing; an `INERT` verdict from an arm
that provably *could* have moved is a real `proven-dont-care` and is **stronger** than it
was before this experiment.

## 2. Hypotheses

- **H1 (the gate discriminates).** A detection-power gate built only from already-committed
  records both **passes** arms with demonstrated detection power and **fails** arms without
  it. Refuter: the gate passes every arm it is applied to (or fails every arm) — in which
  case it is the eleventh cannot-come-out-the-other-way check and must be reported as one,
  not published as a result.
- **H2.** At least one of the 79 `INERT-*` fields rests entirely on arms that fail the gate.
  Refuter: all 79 have ≥1 passing arm.
- **H3 (the verification the dispatch asks for).** After the orchestrator's 2026-08-30
  withholding of five fields, **no** field currently labelled `hardware-run` /
  `isolated-byte-diff` has an `INERT-*` verdict resting on zero passing arms. Refuter: any
  such field exists — it must then be listed in `analysis/reclassify.json`.

## 3. Inputs, pinned by hash

| artifact | sha256 |
|---|---|
| `tools/agx-isa/validation.json` (live labels) | `37d92c05ea8855bd57ab5651bacf5f714abd18f7015a42b4b67e9ac9bf3802f2` |
| `tools/agx-isa/db.json` | `2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4` |
| `EXP-0190/analysis/audit.json` (bucket + arm structure) | `caeeafc3760f2683281ad312832f68e9978d3e49747b192898cbb4622c76f86e` |
| `EXP-0190/analysis/blind_arms.json` (the 8 / 128 arms) | `ccf036c286cd8294f4d2a4e144c80c79cb3b2b697d6d0e7386002346521fb77b` |
| `EXP-0190/analysis/classify_underscore.py` (the 96-name intent table) | `76516faaf4a3a983061d79821ba942d3c364e7404b146c4c7b55c116db4e4b43` |
| corpus | `experiments/*/raw/**/*.jsonl`, 727 files, append-only |

**No indexer is rewritten.** EXP-0190's corrected `collect_raw.py` and its `audit.json`
supply the bucket and `arms_tested` structure; this experiment adds one orthogonal
question and joins on the arm key those files already use. `EXP-0190/analysis/audit.json`
is pinned to a `validation.json` snapshot that predates the five withholdings; the live
`validation.json` differs from that snapshot in **exactly six rows** (verified before
freezing: `falu2i.imm_flag` restored, and the five DEF-0190-1 withholdings), so the live
file supplies the *cohort* and `audit.json` supplies the *structure*.

## 4. Classification of a record — BY INTENT, citing the emitter

The class of an underscore record is taken **verbatim** from EXP-0190's hand-written,
committed `TABLE` in `analysis/classify_underscore.py`, which carries an emitter
`file:line` for every one of the 96 names. This experiment re-partitions those names into
roles for the gate; the partition is written out in full in
`analysis/detection_gate.py::ROLE` and is fixed here. **There is no default bucket**: a
name absent from the role table aborts the script.

| role | meaning | names |
|---|---|---|
| `CONTROL_LIVE` | the emitter's own **instrument check**: run to prove the arm can see a change at all | `_detect`, `__ladder_L_*` (18), `_live_control`, `_L1_opcode_group`, `_L2_erase`, `_litmus_power`, `_sensitivity`, `_liveness_{src_alt,dst_alt,spatial,vp_alt}`, `_poscontrol`, `__power_{sr_sel,b7,fmt}`, `__sens_{byte0_bit2,byte1}`, `_ERASE{4,16,64,256}` |
| `CONTROL_FALSIFIER` | **pre-registered to fail**, i.e. pre-registered to produce a detectable difference | `_falsifier_*` (8), `__falsifier_*` (7), `_refuter_modlo2_unbound`, `_byte0`, `__split_at*` (4) |
| `CONTROL_NEG` | a control pre-registered **not** to move (form selectors that must still work) — a non-move here proves nothing | `_byte1_11`, `_byte2_56`, `_rounding`, `_ZERO4`, `_INERT4` |
| `BASELINE` | the unmutated anchor / health / drift / calibration / summary record — the reference payload, never movement evidence | `_baseline*` (8), `__baseline`, `_natural`, `_identity_splice`, `_start`, `_cascade_check`, `_detect_summary`, `_smoke_*` (3), `_calibprobe`, `_latency_*` (2) |
| `FIELD_SWEEP` | EXP-0190's 14 genuine field sweeps that happen to be underscore-named | treated exactly like a non-underscore field record (role `SIBLING`) |

`_detect` is **CONTROL_LIVE and nothing else.** EXP-0190 flagged its classification as a
judgement call rather than settling it: 3,536 records, 265/271 groups varying and landing
in real db fields, but both EXP-0163 and EXP-0172 consume it **only** as
`arms_with_proven_detection_power`. **That is exactly and only the use made of it here.**
It is never admitted as a measurement, never credited to a db field, and never allowed to
move a headline number. Its two values are chosen to maximise the chance of a change,
which is the wrong shape for a dense sweep and the right shape for an instrument check.

`_ANCHOR_VERDICT` and `_L1_opcode_group` are the reason the partition is by intent and not
by structure: `_ANCHOR_VERDICT` stores a **boolean verdict** in its `value` and writes
nothing into the encoding, yet 50 of its 94 groups vary their bytes because one group
spans several anchors. It is `BASELINE` here — a bookkeeping record, not evidence.
`_L1_opcode_group` is one fixed mutation per anchor used solely to decide whether the
anchor is live, so it **is** an instrument check and is `CONTROL_LIVE`.

## 5. Validity of an observation — frozen

A record contributes an observation only if **all** of:

1. `outcome` ∉ `HARD` = {fault, hang, undecodable, killed, not_written, no_draw,
   lost_7_of_8, nondeterministic} — EXP-0190/EXP-0164's own set, reused unchanged;
2. `outcome` ∉ `CONTAM` = {invalid_run, victim, skipped} and no `skip_reason` key;
3. `observed` is present and not one of `null`, `{}`, `[]`, `""`;
4. the payload carries **no error signature**: no `error` key, and `errdom`, `os_class`
   both absent or empty.

Rule 4 is load-bearing and is pre-registered because the first `_detect` record inspected
while designing this gate carried `outcome: "moved"` with an `observed` payload of
`kIOGPUCommandBufferCallbackErrorHang`. **A command buffer that failed is not a
demonstration that the readback can move**, and DEF-0178-1 says a timeout can be
manufactured outright. Movement into or out of an error payload is never detection power.

The observation payload is `json.dumps(observed, sort_keys=True)` **minus** the keys
`{errdom, os_class, foreign_retries, error, ovr, restarts, gputime_ns, t_ns}` — pure
run-bookkeeping that varies for reasons unrelated to the hardware observable.

## 6. The gate — frozen rule, and it must be able to fail

For an arm `A` (key exactly as EXP-0190's indexer builds it: `carrier|arm`, `-` when
neither exists), let `P(role)` be the set of distinct valid observation payloads of that
role in `A`.

- **PASS_LIVE(A)** iff `|P(CONTROL_LIVE) ∪ P(BASELINE)| ≥ 2` **and** some payload in
  `P(CONTROL_LIVE)` is not in `P(BASELINE)` — or, when `P(BASELINE)` is empty,
  `|P(CONTROL_LIVE)| ≥ 2`.
- **PASS_FALS(A)** — identical, with `CONTROL_FALSIFIER`.
- **PASS_SIB(A)** iff `|P(SIBLING)| ≥ 2`, where `SIBLING` = every non-underscore field
  record plus the 14 `FIELD_SWEEP` names. This is the exact complement of
  `blind_arm_scan.py`'s criterion and needs no underscore record at all.
- **`A` PASSES** iff `PASS_LIVE ∨ PASS_FALS ∨ PASS_SIB`; otherwise **FAILS**.

Two join levels are computed and **both are reported**:

- **strict** — exact arm key. The primary verdict.
- **carrier** — same experiment and same `carrier` value (`rec["carrier"]`, falling back to
  the arm key when the record has none). A relaxation, because a control spliced at a
  different site in the same carrier still exercises the same readback path. Reported
  separately, never merged into the primary verdict; every arm whose verdict differs
  between the two levels is listed by name.

**A carrier-level pass is NOT evidence that the field's own splice site reaches the
output.** That is the strictly stronger question of FIELD-SWEEP-PROTOCOL §3(2), and this
gate does not ask it. Saying so here, before computing, so the result cannot later be
read as more than it is.

### Field verdict

For an `INERT-*` field with tested arms `T`:

- `FAILS` iff **no** arm in `T` passes — the DEF-0190-1 condition;
- `SURVIVES` iff ≥1 arm passes;
- `SURVIVES-FULLY` iff every arm passes;
- additionally flagged **`MULTI-DEGRADED`** if the bucket is `INERT-MULTI` (whose whole
  claim is that two structurally different arms agreed) but fewer than two arms pass.
  This is a *reported sensitivity*, not a reclassification trigger.

**Reclassification trigger (frozen):** a field is written to `analysis/reclassify.json`
iff its live label in `tools/agx-isa/validation.json` is `hardware-run` or
`isolated-byte-diff` **and** its field verdict is `FAILS` **at the carrier join level**
(the more generous of the two — a field must fail even the lenient join to be pulled).

## 7. Pre-registered discrimination proof

The gate is worthless unless it can come out both ways. Fixed now:

- **D1.** The **8** arms in `blind_arms.json → arms_with_no_observation_at_all` must
  **FAIL** at the strict level. They record no observation at all, so no role can supply
  two payloads. If any passes, the gate is broken — investigate before publishing.
- **D2.** Every arm whose `_detect_summary` record carries `detect_any: true` in its note
  (EXP-0163 / EXP-0172's own published verdict that the arm has detection power) must
  **PASS**. This is an external oracle written by a different experiment for a different
  purpose. Disagreements are reported individually, in both directions, and are not
  reconciled by adjusting the gate.
- **D3.** Over the arms of the 79 `INERT-*` fields, both the pass count and the fail count
  must be **> 0**. If either is 0 the gate is declared non-discriminating and the
  experiment reports **that** as its result.
- **D4 (the negative-control check the protocol demands of a 1-bit field).** Report the
  gate verdict for at least one arm that is *known* to have detection power from a source
  other than `_detect` — the `mixed_arm_liveness` arms in `audit.json`, where the same arm
  produced a `stable_live` verdict on another field. Every such arm must PASS.

## 8. Reported diagnostics that are NOT part of the pass/fail rule

- **`all_poison`.** The fraction of an arm's SIBLING observations whose payload contains
  only the `0xDEADBEEF` poison pattern and no other content. FIELD-SWEEP-PROTOCOL §7
  instrument 1 exists precisely because a poisoned readback distinguishes "wrote the wrong
  value" from "never ran at all". An arm whose sweep observations are 100% poison did not
  observe an inert field; it observed nothing. Reported per arm; deliberately kept out of
  the frozen pass/fail rule so the rule stays the one sentence the dispatch asked for.
- **`n_distinct_sibling_payloads`, per-role record counts, and the names of the control
  records relied on**, for every arm — so a reviewer can re-derive any verdict by hand.

## 9. Confounders acknowledged in advance

- Arm-key skew: EXP-0141 keys its controls `carrier|CTRL_SPLICE` while its field records
  are `carrier|<sitename>`, so a strict join finds no control there. This is why both join
  levels are computed and both are published.
- A control that moved may have moved for a reason unrelated to the field's splice site
  (see §6). The gate measures **instrument liveness**, not site liveness.
- `_detect`'s intent classification is EXP-0190's judgement, inherited here. If a future
  reader reclassifies it as a measurement, this gate's inputs are unaffected — it is used
  as a gate either way.
- The corpus contains M4/G16G and G17P records. Detection power is a property of a
  captured arm on the target it ran on; no verdict is promoted across targets, and each
  row carries its `target`.
- `audit.json`'s own `gating_fallback` (EXP-0190 DEF-0190-2) is not repaired here; rows
  carrying it are flagged in the output.

## 10. Deliverables

`README.md`, this file, `analysis/detection_gate.py`, `analysis/gate_results.json`,
`analysis/reclassify.json` (only if §6's trigger fires), `RESULTS.md`, `manifest.json`.
No `git commit`; no edit to `db.json`, `validation.json`, `docs/`, `PROVENANCE.md`, or any
other experiment's committed files.

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json, EXP-0190/analysis/*.json
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/detection_gate.py
Evidence: analysis/gate_results.json
```

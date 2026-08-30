# EXP-0191 — RESULTS: the detection-power gate, built and found to discriminate

**PURE OFFLINE ANALYSIS. No device was contacted; the A18 Pro was down for the whole
run.** The rule, the role table, the validity test and the discrimination proof were
frozen in `PRE_REGISTRATION.md` at repo revision `cd2f05dd` (working tree clean)
**before** any verdict was computed.

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: experiments/*/raw/**/*.jsonl (725 files, 5,200,282 lines, our own
                  append-only capture records), tools/agx-isa/{db,validation}.json,
                  EXP-0190/analysis/{audit,blind_arms}.json + its 96-name intent table
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/detection_gate.py
Evidence: analysis/gate_results.json, analysis/reclassify.json
```

---

## THE HEADLINE

**The gate discriminates, and every current emitter-grade INERT verdict survives it.**

Standing headline **34 of 166 instructions, 550 of 1040 fields** — **unchanged**. Zero
fields are reclassified by the frozen rule. The five fields the orchestrator withheld on
DEF-0190-1 are confirmed to have been the right five, by an independent rule written
without consulting that decision — and the verification the dispatch asked for
(*"verify that rather than trusting me"*) comes back clean.

That is the first check tonight that was built and found nothing wrong with what it was
pointed at. It is worth saying plainly, and it is worth saying only because the gate was
first shown able to fail: **it fails 32 of the 83 arms it was applied to.**

| | |
|---|---|
| `INERT-*` fields gated | **79** (27 + 1 `INERT-MULTI`, 51 `INERT-SINGLE`) |
| of those, emitter-grade **today** | **22** |
| emitter-grade fields whose INERT verdict **FAILS** the gate | **0** |
| fields written to `reclassify.json` by the frozen rule | **0** |
| arms of those 79 fields | 83 — **51 pass, 32 fail** (strict join) |

## 1. The gate

`analysis/detection_gate.py`. For an arm, the question is *did this arm ever demonstrate
that its observable can move?* It passes iff at least one of:

- **`PASS_LIVE`** — a **known-live control in the same arm** (`_detect`, `__ladder_L_*`,
  `_live_control`, `_L1_opcode_group`/`_L2_erase`, `_litmus_power`, `_sensitivity`,
  `_liveness_*`, `_poscontrol`, `__power_*`, `__sens_*`, `_ERASE*`) produced an `observed`
  payload the arm's baseline records do not have;
- **`PASS_FALS`** — a **pre-registered-to-fail** falsifier/refuter in the same arm did;
- **`PASS_SIB`** — some other field's sweep in the same arm produced a second distinct
  `observed` payload, needing no underscore record at all.

Otherwise it **fails**, and an `INERT` verdict from it establishes nothing.

**`_detect` is consumed as a GATE and only as a gate.** EXP-0190 flagged its
classification as a judgement it had not settled — 3,536 records, 265/271 groups varying
and landing in real db fields — and noted that both EXP-0163 and EXP-0172 consume it
*only* as `arms_with_proven_detection_power`. That is precisely and exclusively the use
made of it here: it is never admitted as a measurement, never credited to a db field, and
cannot move a headline number. Saying so explicitly, as the dispatch required.

**The partition is by intent, not structure**, inherited verbatim from EXP-0190's
hand-written table with its emitter `file:line` for all 96 names. `_ANCHOR_VERDICT`
(`EXP-0157/harness/run.py:503`) stores a **boolean verdict** in its `value` and writes
nothing into an encoding, yet 50 of its 94 groups vary their bytes because one group spans
several anchors — a structural rule would have read bookkeeping as evidence. It is
`BASELINE` here. `_L1_opcode_group` (`EXP-0157/harness/cases.py:127`) is one fixed
mutation per anchor used solely to decide whether the anchor is live — an instrument
check, so `CONTROL_LIVE`. `_byte1_11` / `_byte2_56` (`EXP-0156/harness/cases.py:198`) are
controls pre-registered **not** to move, so a non-move there proves nothing: `CONTROL_NEG`,
excluded from the gate in either direction.

**One validity rule is doing real work and was frozen for a reason.** A record counts as
an observation only if its outcome is not `fault`/`hang`/`undecodable`/…, is not
contaminated, and its payload carries **no error signature**. The very first `_detect`
record read while designing the gate carried `outcome: "moved"` with an `observed` of
`kIOGPUCommandBufferCallbackErrorHang`. A command buffer that failed is not a
demonstration that a readback can move, and DEF-0178-1 says a timeout can be manufactured
outright.

## 2. Proof that the gate discriminates — all four pre-registered checks

| | check | result |
|---|---|---|
| **D1** | the **8** arms recording no observation at all must **FAIL** | **PASS — 0 of 8 pass the gate** |
| **D3** | both outcomes must occur over the arms of the 79 fields | **PASS — 51 pass, 32 fail** |
| **D2** | agree with EXP-0163/0172's own `_detect_summary → detect_any` | **136 of 138 agree**; 2 disagreements, both analysed below |
| **D4** | arms with a `stable_live` verdict on another field must **PASS** | **55 of 57 pass**; 2 failures, both analysed below |

The two counts the dispatch asked for, stated together: **the gate passes 51 arms that
demonstrably have detection power and fails the 8 arms that recorded no observation at
all** (those 8 are inside the 32 failures).

### D2 — the two disagreements are the gate being right, and they are a finding

`EXP-0172|frame_marker_compact@vhalf/vertex#0` and `…@vsrc/vertex#0` publish
`detect_any: true` in their own `_detect_summary`. Both arms contain exactly 8 records.
**Both `_detect` observations are GPU-hang error payloads** (`ErrorHang`,
`status: CMDBUF_ERROR`, empty sentinel), and the arm's three real field records are two
`fault`s and one `hang`. The "change" those arms detected was the command buffer failing.
Under §5 rule 4 that is not detection power, so the gate says FAIL — and it is right to.

**EXP-0172's `arms_with_proven_detection_power` is, for these two arms, founded on a
hang.** Neither arm underwrites any `INERT-*` field, so nothing in the headline moves;
it is recorded because it is the same DEF-0178-1 shape one level up, in an instrument
other experiments rely on.

### D4 — the two failures uncovered a *different* defect

Neither failing arm belongs to an `INERT-*` field, so neither affects this gate's verdicts.
Both fail for the same reason, and it is not a gate bug:

- `EXP-0156|cf0|jump_cond.offset` — 112 records: **55 `invalid_run`, 53 `fault`, 4 `ok`**,
  and the 4 `ok` records share one payload.
- `EXP-0179|C1_flat/idx15|M` — 12 records: 6 `fault`, 6 `ok`, one payload.

`audit.py` nevertheless scored both **`stable_live`**. The mechanism: `sig_of()` returns
`"<hard-class>|<hash>"`, so an `ok` observation and a `fault` are **different signatures**,
and `moved` counts the difference as **movement**. A STABLE-LIVE promotion can therefore be
carried entirely by faults.

## 3. What survives, what fails

**76 of 79 fields SURVIVE-FULLY at the carrier join; 3 fail.** All three are already
`untested` — none is emitter-grade:

| field | bucket | arms | why it fails |
|---|---|---|---|
| `stop.reserved` | INERT-MULTI | `EXP-0168:STOP/terminal`, `STOP/midprogram` | see below — the arm's own falsifier says so |
| `jump_cond.cf_scope` | INERT-SINGLE | `EXP-0156:cf0|…@NAT` | single arm, one distinct valid payload, no control of any kind |
| `jump_cond.reserved` | INERT-SINGLE | `EXP-0156:cf0|…@NAT` | same arm, same reason |

**`stop.reserved` is the clean case, and the raw refutes the arm without any help from
this gate.** `STOP/terminal` holds **1,672 records — every one with the identical
observed digest**, including the arm's own `_byte0` case whose note reads: *"PRE-REGISTERED
TO FAIL: byte0 forced to 0x00 is not this instruction. **If it scores `ok`, this arm's
sweep proves nothing**."* It scored `ok`, with that same digest. The arm declared its own
refutation condition and then met it. `STOP/midprogram` is worse in a different way: 1,670
of its 1,672 observations are **pure `0xDEADBEEF` poison** — the swept program never wrote
at all — and only the falsifier moved off poison. Withholding `stop.reserved` was correct.

**The survivors get stronger, which is the point.** 76 fields — including 22 emitter-grade
ones — were measured inert on an arm that provably *could* have shown movement. Their
`moved = 0` is now a result rather than an artefact of the instrument. That is what a
`proven-dont-care` is supposed to mean, and before today no row in this corpus had it
checked.

## 4. The verification the dispatch asked for — verified, not trusted

The five fields withheld on 2026-08-30 (`atomic_mem.{amode,base_slot,rsv3}`,
`pop_reconverge.reserved`, `stop.reserved`) are all `untested` in the live
`validation.json`; the live file differs from EXP-0190's pinned snapshot in **exactly six
rows** (those five, plus `falu2i.imm_flag` restored), giving 550 of 1040 — independently
recomputed here from the live file.

**All five fail the STRICT join.** One (`stop.reserved`) fails the carrier join too. Under
the gate's own frozen rule the withholding was correct, and correct for the reason claimed.

**But one emitter-grade field the withholding did not name also fails the strict join:**

> **`pop_reconverge.scope`** — `INERT-MULTI`, label `hardware-run`, arms
> `EXP-0140|cf|pop_reconverge.scope@14` and `@15`. Each arm holds **512 valid observations
> with exactly ONE distinct payload**, plus 256 `skipped` records, and **no control record
> of any kind at the arm level**. It passes only at the carrier join, because sibling arms
> on the same `cf` carrier show 7 distinct payloads.

It is **not** in `reclassify.json`, because the frozen trigger is failure at the *carrier*
level and it passes there — the rule was fixed before the number was known and is not being
bent now. But it is the one emitter-grade row whose inert verdict rests on an arm that,
taken alone, never saw anything move, and **EXP-0140 is the experiment
FIELD-SWEEP-PROTOCOL §3(a) already names for building an oracle that could not fail.** It
is the strongest candidate for the next withholding decision, and the orchestrator should
make that call explicitly rather than inherit it from a join level.

Why EXP-0190's scan did not list it: `blind_arm_scan.py` buckets an arm only when it
recorded **no** observation, or ≥8 records with exactly one distinct `observed` **and zero
empty ones**. An arm mixing empty and single-valued observations falls through both
buckets. **Five strict failures are of that shape** (`gate_results.json →
strict_failures_EXP0190_blind_scan_did_not_see`), so DEF-0190-1's measured extent — 8 + 128
arms — is an **undercount**, not an overcount.

## 5. POST-HOC, NOT PRE-REGISTERED — `moved` counts a fault as movement

D4 raised it, so it was measured rather than left as an anecdote. Of the **337** arms
`audit.py` marks `stable_live`, **7 have fewer than two distinct valid observation
payloads** — their movement cannot have come from observations at all:

| arm | records | distinct valid payloads |
|---|---|---|
| `EXP-0156|cfN|ret.linkmode` | 768 (**667 `fault`**, 5 `invalid_run`) | 1 |
| `EXP-0156|cfN|ret_luse.linkmode` | 768 (**658 `fault`**, 14 `invalid_run`) | 1 |
| `EXP-0172|irotate@rot/compute#1` | 512 (**508 `undecodable`**) | 1 |
| `EXP-0172|irotate@rot2/compute#2` | 512 (**508 `undecodable`**) | 1 |
| `EXP-0147|n3_sample_read` | 4,230 (116 `fault`, 18 `invalid_run`) | 1 |
| `EXP-0156|cf0|jump_cond.offset` | 112 (53 `fault`, 55 `invalid_run`) | 1 |
| `EXP-0179|C1_flat/idx15|M` | 12 (6 `fault`) | 1 |

**Four currently emitter-grade rows have their STABLE-LIVE promotion resting *entirely* on
such an arm**: `jump_cond.offset` (`hardware-run`), `ret.linkmode` (`hardware-run`),
`ret_luse.linkmode` (`hardware-run`), `n3_sample_read.tail` (`isolated-byte-diff`).
`call.offset` and `irotate.b2` also have a suspect arm but keep a clean one, so they are
not listed.

They are in `analysis/reclassify.json` under **`post_hoc_candidates`** — with `start`/`width`
per FIELD-SWEEP-PROTOCOL §5, since the merger refuses a row whose bits have moved — and
deliberately **not** under `fields`. **This is not a verdict of EXP-0191 and must not be
merged on its authority.** The rule that produced it was written after seeing the data,
which is exactly the move this repo does not permit; it needs its own pre-registered
successor. It is reported because a defect found while building something else is still a
defect, and this one runs in the *opposite* direction to DEF-0190-1: there an inertness
gate could not doubt, here a **liveness** gate promotes on faults.

## 6. Limitations

- **This gate measures instrument liveness, not site liveness.** An arm that passes proved
  its observable can move; it did **not** prove that the field's own splice site reaches
  the output. That is the strictly stronger question of FIELD-SWEEP-PROTOCOL §3(2), and
  `_detect` is the only instrument in the corpus that asks it per-site.
- **A carrier-level pass is the weaker of the two joins** and is used only for the
  reclassification trigger, deliberately, so that a field must fail *both* readings to be
  pulled. Every arm whose verdict differs between the joins is listed by name in
  `gate_results.json`.
- **Nothing here was measured on hardware.** Every number is a re-derivation from records
  earlier experiments captured, on the targets they name — M4/G16G for EXP-0140/0141/0147,
  G17P for EXP-0156 and above. No verdict is promoted across targets; every row carries its
  `target`.
- **`_detect`'s intent classification is EXP-0190's judgement, inherited.** If a future
  reader reclassifies it as a measurement, this gate is unaffected — it is used as a gate
  either way.
- **The gate cannot distinguish "the hardware is genuinely inert here" from "this arm
  happened to see nothing"** for an arm with no controls. It reports which of the two
  questions the evidence can answer, not the answer.
- EXP-0190's DEF-0190-2 (`gating_fallback` silently disabling the gated-run filter) is not
  repaired here; affected rows are flagged in the output.

## 7. Verdict

**The gate discriminates — 51 arms pass, 32 fail, the 8 no-observation arms all fail — and
every current emitter-grade INERT verdict survives it.** 76 of 79 INERT verdicts become
*stronger*: measured inert on an arm that provably could have shown movement. The three
that fail are already withheld, and the five withheld on DEF-0190-1 are confirmed correct
by an independent rule.

**Publish 34 of 166 and 550 of 1040 — unchanged.**

Two things the orchestrator must decide, neither of which this experiment decides for it:
**`pop_reconverge.scope`**, the one emitter-grade row that fails the strict join (§4), and
the **four STABLE-LIVE rows promoted on faults** (§5), which need a pre-registered
successor.

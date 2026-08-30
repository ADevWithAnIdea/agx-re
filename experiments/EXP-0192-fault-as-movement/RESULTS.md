# EXP-0192 — RESULTS

**The criterion fired. Three of the four rows should be withheld; one stands, and it
stands for a reason that was reachable and was reached.**

Pure offline analysis at repo revision `8d01daa35a53a478f72fe800dc94d27492c11d77` (tree
clean at freeze). No device contacted. Criterion frozen in `PRE_REGISTRATION.md` §4
**before** any count was computed.

---

## 1. What was directly observed

Per attributing arm: total attributed cases, keyed cells, cells carrying a `HARD` class,
distinct **valid** payloads `V`, distinct signatures including faults `V_all`, and
distinct **legal** field values `L`. Full table in `analysis/valid_payload_audit.json`.

| row | live label | arm | cases | fault cells | `V` valid | `V_all` | `L` legal |
|---|---|---|---|---:|---:|---:|---:|
| `ret.linkmode` | hardware-run | `EXP-0156\|cfN\|ret.linkmode` | 768 | **667** | **1** | 2 | 32 |
| | | `EXP-0140\|cf\|ret.linkmode@12` | 533 | 242 | **1** | 2 | 32 |
| | | `EXP-0179\|C1_flat/idx15\|L` | 12 | 0 | **2** | 2 | 4 |
| | | `EXP-0179\|C2_nested/idx7\|L` | 12 | 0 | **3** | 3 | 4 |
| `ret_luse.linkmode` | hardware-run | `EXP-0156\|cfN\|ret_luse.linkmode` | 768 | **658** | **1** | 2 | 32 |
| `jump_cond.offset` | hardware-run | `EXP-0156\|cf0\|jump_cond.offset` | 112 | 53 | **1** | 2 | 2 |
| | | `EXP-0140\|cf\|jump_cond.offset` | 88 | **0** | **1** | 1 | 36 |
| | | `EXP-0156\|cfN\|jc.liveness` | 9 | 0 | 1 | 1 | 3 |
| | | `EXP-0156\|cf0\|jc.liveness` | 9 | 0 | 0 | 0 | 0 |
| `n3_sample_read.tail` | isolated-byte-diff | `EXP-0147\|n3_sample_read` | 3206 | 116 | **1** | 2 | **1522** |
| *(control)* `call.b5` | hardware-run | `EXP-0179\|C1_flat/idx15\|B5` | 768 | 384 | **3** | 4 | 128 |
| *(control)* `call.b5` | hardware-run | `EXP-0179\|C2_nested/idx7\|B5` | 768 | 416 | **4** | 5 | 128 |
| *(control)* `call.b5` | hardware-run | `EXP-0179\|S_kchain_compiled\|S` | 512 | 320 | **2** | 3 | 96 |

Cross-run agreement (from `audit.py::cross_run`, unchanged):

| arm | common | agree % | movedA / movedB |
|---|---:|---:|---|
| `EXP-0156\|cfN\|ret.linkmode` | 253 | 100.0 | 32 / 32 |
| `EXP-0156\|cfN\|ret_luse.linkmode` | 244 | 100.0 | 32 / 32 |
| `EXP-0156\|cf0\|jump_cond.offset` | 28 | 100.0 | 2 / 2 |
| `EXP-0147\|n3_sample_read` | 1574 | 100.0 | 60 / 56 |

**The cross-run agreement is perfect and it does not help.** In every one of these four
arms the `moved` count is precisely the count of ok/fault transitions: the fault wall is
reproducible to 100%, and that reproducibility is exactly what carried the rows through
`stable_live()`. A perfectly reproducible fault wall is a perfectly reproducible *hazard
map*, not a semantic.

## 2. Verdicts under the frozen criterion

| row | case | verdict |
|---|---|---|
| `ret.linkmode` | **A** | **STANDS** — rescued by an independent arm |
| `ret_luse.linkmode` | **C** | **WITHHOLD** |
| `jump_cond.offset` | **C** | **WITHHOLD** |
| `n3_sample_read.tail` | **C** | **WITHHOLD** |
| `call.b5` *(R2 control)* | **A** | **not withheld** — the criterion is not a blanket refusal of fault evidence |

Written to `analysis/reclassify.json` (flat `<mnemonic>.<field>` with `start`/`width`):
`jump_cond.offset` (start 24, width 48), `n3_sample_read.tail` (start 32, width 48),
`ret_luse.linkmode` (start 8, width 8).

### 2.1 Why `ret.linkmode` stands, and what it stands on

Its **cited** arm is the worst case in the corpus: `EXP-0156|cfN|ret.linkmode` has 667
fault cells of 763, exactly one distinct valid payload across 32 legal values, and
`moved = 32 + 32` that is entirely ok-vs-fault. On its own citation the row would have
been withheld.

It survives because **`EXP-0179`'s `call` sweep independently exercised the same field**
on arms `C1_flat/idx15|L` and `C2_nested/idx7|L` — 12 cases each, **zero faults**, and
**2 and 3 distinct valid payloads over 4 legal values**. Two distinguishable valid outputs
is the whole content of Case A: the field visibly selects something.

**This is a narrow rescue and the honest label carries a narrower range.** The valid-payload
evidence covers **4 values, not 256**; the dense `0..255` sweep in the row's current
`range` string is the fault wall. Recommended (not applied — the orchestrator owns
`validation.json`): amend `ret.linkmode`'s `evidence` to include `EXP-0179` and its
`range` to something like `"0..255 dense for legality; 4 values with distinct valid
payloads (EXP-0179)"`.

### 2.2 Why the other three fall

- **`ret_luse.linkmode`** — one arm, 32 legal values, **one** valid payload, 658 faults.
  Every legal value is indistinguishable from every other. No second arm anywhere in the
  corpus attributes to it, so nothing rescues it. This is `ret.linkmode`'s twin **without**
  the `EXP-0179` arm — and it is the cleanest demonstration in this experiment that the two
  rows were never equally supported despite carrying identical labels, ranges and buckets.
- **`jump_cond.offset`** — the strongest case, and the most instructive. Its `EXP-0156|cf0`
  arm has `moved = 2` per run, and **both moved cases are fault transitions** (53 fault
  cells, `V = 1`, `L = 2`). Its other arm, `EXP-0140|cf`, has **zero faults at all**, 36
  legal values and still **one** valid payload — i.e. on that arm the field is flatly
  inert and was never scored live. So the emitter-grade label rests on two moved cases,
  both of which are faults, against 36 legal values that are demonstrably
  indistinguishable. (Its `jc.liveness` control arms show `V ≤ 1` and no movement, so the
  arm's detection power is separately unestablished — that is EXP-0191's question, and it
  points the same way.)
- **`n3_sample_read.tail`** — **1522 distinct legal values** (1536 at record level) across
  3206 cases produce exactly **one** valid payload; the 116 fault cells are the entire
  `moved` count of 60/56. A 48-bit tail that is indistinguishable across fifteen hundred
  legal values is an inert field with a fault wall, not a swept field.

## 3. The seven `STABLE-LIVE` arms, generally

The four rows above are the emitter-grade consumers. The remaining arms from EXP-0191's
`stable_live_arms_with_fewer_than_2_distinct_valid_payloads` set carry no currently
emitter-grade row and therefore trigger no withholding; they are reported in
`analysis/valid_payload_audit.json → seven_stable_live_arms_from_EXP_0191` so the defect's
full extent stays visible. The generalisable finding is the one the table shows: **in this
corpus, `moved` and "the field showed two different valid outputs" are different
quantities, and where they differ the difference is entirely fault transitions.**

## 4. Discrimination — the criterion could come out both ways, and did

- **Both directions occurred within the four rows in scope:** one Case A, three Case C.
- **R2 control satisfied.** `call.b5` — `hardware-run`, one bit, ~50% of its cases
  faulting, undisputed — is **Case A**, not withheld, because it shows 2–4 distinct valid
  payloads on each of three arms. The criterion does not refuse fault-bearing evidence; it
  refuses evidence that is *only* faults.
- **Case B was reachable and was not taken.** No row in scope had `L ≤ 1`. Had one, it
  would have stood as `legality-only`. Its absence is data, not design.
- **R3 satisfied.** Every row in scope was located in the pinned index; nothing was
  withheld for absent records.

## 5. The honest headline

`tools/agx-isa/validate_labels.py` at this revision reports **34 / 166 emittable, 549 /
1040 emitter-grade fields**. If the three Case-C withholdings are accepted:

> **33 of 166 emittable, 546 of 1040 fields.**

One family changes state: **`ret_luse`** has exactly two fields (`linkmode`, `tail`), both
`hardware-run`, and an emitter-grade `_instruction` label — withholding `linkmode` drops it
out of the emittable set. `jump_cond` (two `untested` fields) and `n3_sample_read`
(`_instruction: corpus-correlation`) were **already** not emittable, so those two
withholdings cost fields but no family.

## 6. Alternative explanations not excluded

- **`L` is observed legality, not true legality.** A value never dispatched is neither
  legal nor illegal here; `L` is a lower bound. This can only make a row *harder* to
  withhold, never easier.
- **Index modal collapse.** `collect_raw.py` keeps one modal signature per
  `rest:fieldvalue` cell, so a genuinely bimodal cell contributes one signature — a bias
  toward withholding. The record-level `payload_of` pass was run as the pre-registered
  cross-check (§4.3 rule 3) and **recovered no additional distinct valid payload** for any
  Case-C row; it did raise `n3_sample_read.tail`'s legal-value count from 1522 to 1536,
  which strengthens rather than weakens the verdict.
- **A single valid payload could mean the readback never observed the field's effect
  rather than that the field has none** — the arm might lack detection power, or the
  observable might not be on the field's output path (FIELD-SWEEP-PROTOCOL §3(2)). This
  experiment cannot distinguish those, and does not claim to: **Case C says the promotion
  is unsupported, not that the field is inert.** Either way the row is not emitter-grade.
- **DEF-0178-1.** Hangs may be manufactured by the shared runner's reader-thread defect.
  No row here is withheld on hang-only evidence; the hard classes are reported per class in
  `analysis/valid_payload_audit.json → verdicts.*.arms.*.hard_class_counts`.

## 7. Limitations

- Scope was the four emitter-grade rows named by EXP-0191 plus one control. **The full
  337-arm `STABLE-LIVE` population was not re-scored under this criterion**; that sweep is
  the obvious successor and is mechanical from `analysis/valid_payload_audit.py`.
- The criterion is a rule about *evidence*, not about hardware. It changes no fact about
  the GPU. The fault walls it declines to promote remain valid, reproducible legal-set
  bounds and should be documented as such.
- No label was edited. `analysis/reclassify.json` is a recommendation.

## 8. Verdict

**A field whose movement consists only of `ok`↔`fault` transitions does NOT meet the
`hardware-run` / `isolated-byte-diff` bar when two or more of its values ran legally and
were indistinguishable.** It does meet it when the legal set is trivial (nothing to
choose), and the fault evidence remains a first-class legal-set bound in both cases.

Three rows fall by that rule: `ret_luse.linkmode`, `jump_cond.offset`,
`n3_sample_read.tail`. One survives it on independent evidence: `ret.linkmode`, whose
citation should nonetheless be widened to `EXP-0179` and whose valid-payload range is 4
values, not 256.

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl, tools/agx-isa/{db,validation}.json,
                  EXP-0190/analysis+work, EXP-0191/analysis
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/valid_payload_audit.py
Evidence: analysis/valid_payload_audit.json, analysis/reclassify.json
```

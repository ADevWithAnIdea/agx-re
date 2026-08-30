# EXP-0193 — RESULTS

**The criterion was applied to all 337 `STABLE-LIVE` arms — 503 fields — and it fired three
more times.** Two of the three unexamined arms' fields survive; the three new Case-C rows came
from arms nobody had flagged at all.

Pure offline analysis at repo revision `7286bf04c500f726fbe3bf096a166e90b6a34e0f` (working tree
clean at freeze). **No device contacted, no SSH, no shader compiled.** The criterion is
`EXP-0192/PRE_REGISTRATION.md` §4.2, **inherited unchanged and executed by importing EXP-0192's
own `classify_row()`**. EXP-0193 froze its population, its control expectations and its stop
condition in `PRE_REGISTRATION.md` before running.

---

## 1. Controls first — the run is only readable if these hold

### R1 — the positive control, `call.b5`

Expectation recorded in `PRE_REGISTRATION.md` §5 **before the run**: Case **A**, `V` = **3, 4,
2** across three arms. Observed:

| arm | cases | fault cells | `V` valid | `V_all` | `L` legal | expected? |
|---|---:|---:|---:|---:|---:|---|
| `EXP-0179-g17p-call\|C1_flat/idx15\|B5` | 768 | 384 | **3** | 4 | 128 | ✔ all five |
| `EXP-0179-g17p-call\|C2_nested/idx7\|B5` | 768 | 416 | **4** | 5 | 128 | ✔ all five |
| `EXP-0179-g17p-call\|S_kchain_compiled\|S` | 512 | 320 | **2** | 3 | 96 | ✔ all five |

→ **case = A, verdict STANDS. R1 PASSED.** A one-bit `hardware-run` field with roughly half its
cases faulting is *not* withheld, because it shows two-to-four distinguishable valid outputs on
each arm. The criterion refuses evidence that is *only* faults; it does not refuse fault-bearing
evidence.

### R2 — re-derivation of EXP-0192's four rows

| row | expected | observed | agree |
|---|---|---|---|
| `ret.linkmode` | A | **A** | ✔ |
| `ret_luse.linkmode` | C | **C** | ✔ |
| `jump_cond.offset` | C | **C** | ✔ |
| `n3_sample_read.tail` | C | **C** | ✔ |

**R2 PASSED.** The three already-withheld rows now carry live label `untested`, so they
correctly do **not** re-enter `reclassify.json`.

### R3 / R4

- **R3 discrimination:** 497 Case A and 6 Case C in the same run — the rule demonstrably comes
  out both ways over this population. Case B was reachable and was **not** taken: **no row in
  503 has `L ≤ 1`.**
- **R4 attribution:** **0** of 503 rows scored `UNVERIFIABLE-HERE`. Every population member was
  located in the pinned index.

Determinism: run01 and run02 produced byte-identical stdout (7.6 s each).

---

## 2. What was directly observed

| | |
|---|---:|
| `STABLE-LIVE` arms enumerated | **337** (matches EXP-0191's committed `n_stable_live_arms_checked`) |
| distinct fields carried by them | **503** |
| contributing experiments | **23** |
| rows scored | **503** + 1 control |
| **Case A — STANDS** | **497** |
| **Case B — STANDS (`legality-only`)** | **0** |
| **Case C — WITHHOLD** | **6** |
| — already withheld by EXP-0192 | 3 |
| — **new in EXP-0193** | **3** |
| `UNVERIFIABLE-HERE` | 0 |

### 2.1 The six Case-C rows

| row | live label | arms | cases | hard cells | `V` valid | `L` legal | `moved_total` |
|---|---|---:|---:|---:|---:|---:|---:|
| **`frag_color_pack.fmt_class`** | **`hardware-run`** | 1 | 512 | **2** (`undecodable`) | **1** | **255** | **2** |
| **`ray_move_copy6.optype`** | **`hardware-run`** | 1 | 510 | **128** (`fault`) | **1** | **191** | **128** |
| **`vtx_coord_xform.operand`** | **`isolated-byte-diff`** | 1 | 2678 | **1026** (987 `no_draw` + 39 `fault`) | **1** | **817** (821 at record level) | **1026** |
| `jump_cond.offset` *(already withheld)* | `untested` | 4 | 218 | 53 | 1 | 36 | 4 |
| `n3_sample_read.tail` *(already withheld)* | `untested` | 1 | 3206 | 116 | 1 | 1522 | 116 |
| `ret_luse.linkmode` *(already withheld)* | `untested` | 1 | 768 | 658 | 1 | 32 | 64 |

**For all three new rows, `moved_total` equals the hard-class cell count exactly** (2 = 2,
128 = 128, 1026 = 1026). There is nothing else in their movement.

Cross-run agreement, from `audit.py::cross_run` (unchanged), for the three new rows:

| arm | common | agree % | movedA / movedB | disagreements |
|---|---:|---:|---|---:|
| `EXP-0155-g17p-emit-tex-frag\|fcp@pack0` | 256 | **100.0** | 1 / 1 | 0 |
| `EXP-0157-g17p-emit-misc\|rq_cdist\|R` | 255 | **100.0** | 64 / 64 | 0 |
| `EXP-0147-m4-emit-pipeline-misc\|vtx_coord_xform` | 1326 | **100.0** | 517 / 509 | 0 |

**The cross-run agreement is perfect and, again, it does not help.** A perfectly reproducible
fault wall is a perfectly reproducible hazard map, not a semantic — exactly EXP-0192's finding,
reproduced on three rows it never looked at.

### 2.2 `frag_color_pack.fmt_class` — the sharpest instance in the corpus

This one deserves to be read literally. The arm dispatched **256 values × 2 gated runs = 512
cases**. Every single one of those 512 records carries the **same** `observed` payload:

```
{"h": "cb70b1834dd457a983f8ade33b67fc39",
 "probe": [[153,102,51,204],[153,102,51,204],[153,102,51,204]],
 "sentinel": "OK 1", "status": "OK"}
```

510 are `outcome: ok`. The other **two** — one per run, both at **value 86** — are
`outcome: undecodable`, with the note **`re-decodes as pack_convert`**.

So the entire `STABLE-LIVE` promotion of an 8-bit field with **255 legal values** rests on
`moved = 1` per run, and that one moved cell is **our own disassembler assigning a different
mnemonic**. The command buffer completed with `status: OK`, the integrity sentinel was written,
and the pixel readback was byte-identical to all 255 other values. **The hardware never moved at
all.** `undecodable` is in the frozen `HARD` set (EXP-0190/EXP-0191), so `sig_of` gave it a
different signature and `moved` counted it.

This is not a new rule and it is not an extension of one: Case C is reached here by the
inherited criterion's own arithmetic (`V = 1`, `L = 255 ≥ 2`). It is reported in this detail
because it shows the defect at its most extreme — a *tokenizer* disagreement promoted a field to
emitter grade.

### 2.3 `ray_move_copy6.optype`

510 cases (255 values × 2 runs). **382 `ok`, all sharing one payload**
(`out0: [10.0, 7.5, -6.2598e18, -6.2598e18]`, sentinel true); **128 `fault`**, all sharing
`{"sentinel": false, "unwritten": 0}`. 191 values ran legally; 64 values are fault-only. The
191 legal values are mutually indistinguishable.

### 2.4 `vtx_coord_xform.operand` — the one that costs a family

2678 records over a **40-bit** field: **1642 `ok`, every one returning the identical
4×4 pixel matrix**; 987 `no_draw` (`status: SENTINEL_MISS`); 39 `fault` (`CMDBUF_ERROR`); 10
`invalid_run`. 817 values legal at index level, 821 at record level, 517 fault-only. One valid
payload across all of them.

---

## 3. The three arms nobody had examined — both fields STAND

EXP-0191's seven suspect arms minus EXP-0192's four rows left three arms unexamined. Under the
criterion:

| arm | field | outcome |
|---|---|---|
| `EXP-0172-g17p-onefield-tail\|irotate@rot/compute#1` | `irotate.b2` | **Case A — STANDS** |
| `EXP-0172-g17p-onefield-tail\|irotate@rot2/compute#2` | `irotate.b2` | **Case A — STANDS** |
| `EXP-0179-g17p-call\|C1_flat/idx15\|M` | `call.offset` | **Case A — STANDS** |

- **`irotate.b2`** has 7 attributing arms. The two flagged arms do indeed show `V = 1` (with
  508 of 512 cells `undecodable` and `L = 2`) — but three *other* `EXP-0172` arms on the **same
  G17P target** show `V = 2` over `L = 129`, and the record-level pass finds `V = 9` on
  `EXP-0146|rot_imm`. The rescue does **not** depend on the M4 arm. This is `ret.linkmode`'s
  situation and the same outcome.
- **`call.offset`** has 8 attributing arms. The flagged `|M` arm has `V = 1, L = 1` — but its
  sibling `C1_flat/idx15|T` shows `V = 7` over `L = 8` and `C2_nested/idx7|T` shows `V = 8`,
  both G17P, both zero-fault-dependent. It was never at risk.

**Finding:** a flagged arm is not the same thing as a flagged row, and EXP-0191 was right to
report arms rather than act on them. Two of the three unexamined arms belong to rows that a
sibling arm carries cleanly.

---

## 4. How close the rest of the population came

Distribution of the winning `V` (`bestV`, the max over all attributing arms and both passes)
across the 497 Case-A rows:

| `bestV` | rows |
|---:|---:|
| **2** (clears the bar by exactly one payload) | **115** |
| 3 | 48 |
| 4 | 52 |
| 5–8 | 90 |
| 9–16 | 116 |
| 17–64 | 46 |
| 65–421 | 30 |

**115 of 497 Case-A rows clear the bar with exactly two distinct valid payloads.** They are
correctly Case A under the frozen rule — two distinguishable valid outputs is the whole content
of the case — but they are the thin end, and a stricter successor rule (which this experiment
is expressly forbidden to invent) would land there first.

**The record-level second pass rescued nothing.** For **0** rows did the record-level
`payload_of` pass recover a second distinct valid payload that the index's modal collapse had
hidden. The pre-registered confounder in §7 of the pre-registration (index modal collapse biases
toward withholding) is therefore measured at **zero effect** across all 503 rows — the same
result EXP-0192 got on its four.

---

## 5. The honest number

`tools/agx-isa/validate_labels.py` at this revision reports (rc=0):

> **33 of 166 emittable, 546 of 1040 emitter-grade fields** (483 `hardware-run` + 63
> `isolated-byte-diff`).

If the three new Case-C withholdings are accepted:

> ### **32 of 166 emittable, 543 of 1040 emitter-grade fields.**

One family changes state. **`vtx_coord_xform`** has three fields (`mode` `hardware-run`, `sel`
and `operand` `isolated-byte-diff`) and an `isolated-byte-diff` `_instruction` label — it is
emittable today, and withholding `operand` drops it out. The other two cost fields but no
family: `frag_color_pack` already fails on `src_gate_select` and `conv_scale` (both `untested`),
and `ray_move_copy6` already fails on `dst`, `src` (both `untested`) and a
`corpus-correlation` `_instruction` label.

**No label was edited.** `analysis/reclassify.json` is a recommendation with bit geometry
(`frag_color_pack.fmt_class` start 16 width 8; `ray_move_copy6.optype` start 24 width 8;
`vtx_coord_xform.operand` start 40 width 40). The orchestrator owns `validation.json`.

---

## 6. Separating observation from interpretation

**Observed.** Per arm: attributed cases, keyed cells, hard-class cells by class, distinct valid
observation payloads, distinct signatures including hard classes, distinct legal field values,
and per-run breakdowns — for all 503 rows, in `analysis/population_audit.json`.

**Interpreted.** That a row with one valid payload and ≥2 legal values does not meet the
`hardware-run` / `isolated-byte-diff` bar. That interpretation is EXP-0192's, not this
experiment's; EXP-0193 supplies scope, not judgement.

**Targets.** `frag_color_pack.fmt_class` and `ray_move_copy6.optype` are **G17P**;
`vtx_coord_xform.operand` is **M4/G16G**. No verdict is promoted across targets.

---

## 7. Alternative explanations not excluded, and limitations

- **A single valid payload can mean the arm lacked detection power rather than that the field is
  inert** (FIELD-SWEEP-PROTOCOL §3(2), §5 / DEF-0190-1). This experiment cannot distinguish
  those and does not claim to. **Case C says the promotion is unsupported, not that the field is
  inert.** Inherited verbatim from EXP-0192.
- **`L` is *observed* legality, not true legality.** A value never dispatched is neither legal
  nor illegal here, so `L` is a lower bound. Direction is safe: it can only make a row *harder*
  to withhold (`L ≤ 1` → Case B → STANDS).
- **Index modal collapse** biases toward withholding. Measured at **zero effect** here (§4).
- **DEF-0178-1 (manufactured hangs).** No Case-C row in this run is withheld on hang-bearing
  evidence: the hard classes are `undecodable` (2), `fault` (128), and `no_draw` + `fault`
  (987 + 39). **`hang` appears in none of them.** Per-class counts are in
  `population_audit.json → verdicts.*.arms.*.hard_class_counts`.
- **The inherited criterion is target-blind.** `classify_row` takes the max `V` over *every*
  attributing arm regardless of which target that arm ran on. Scanning the Case-A set for rows
  whose only ≥2-payload arm comes from a different target family than the row's recorded target
  finds **two**: `ibfe.srcA` (target G17P, rescued only by M4/G16G arms) and `ilogic.outmod`
  (same shape). **This is reported as an observation and changes no verdict here** — resolving
  it would require a target conjunct the criterion does not have, and inventing one is exactly
  the eleventh-hour rule adjustment this chain exists to prevent. It is handed to the
  orchestrator as a question, not answered.
- **`moved` was not recomputed.** This experiment splits `collect_raw.py::sig_of`'s signature
  into `(hard-class, observation-hash)`; it does not re-derive the signature, `moved`, or the
  `STABLE-LIVE` bucket. A defect in those propagates into this analysis unchanged.
- **Scope.** Only fields carried by a `STABLE-LIVE` arm were scored. The 205 `audit.json` keys
  in other buckets, and the 332 `validation.json` fields with no `audit.json` record at all, are
  outside this population by construction — the criterion is about `STABLE-LIVE` promotions.
- **No ambiguous row.** Every one of the 503 rows landed in exactly one of A / B / C by the
  imported function's own arithmetic. Nothing required a judgement call, so nothing was
  resolved by one.

---

## 8. Verdict

**The criterion was applied to all 337 arms — 503 fields — and it fired three more times.**

- **STANDS:** 497 rows, including `irotate.b2` and `call.offset`, the two rows behind the three
  arms EXP-0191 flagged and nobody had examined.
- **STANDS (`legality-only`):** none — no row in the population has a trivial legal set.
- **WITHHOLD (new):** `frag_color_pack.fmt_class`, `ray_move_copy6.optype`,
  `vtx_coord_xform.operand` — each with exactly one distinct valid payload against 255, 191 and
  817 legal values respectively, and with `moved` accounted for entirely by hard-class cells.
- **The fault walls themselves remain first-class facts** and real legal-set bounds, in every
  case. What is withheld is the claim that an emitter can *choose* a value of these fields and
  get a documented behaviour.

**33 of 166 emittable, 546 of 1040 → 32 of 166 emittable, 543 of 1040.**

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json,
                  EXP-0190/analysis+work, EXP-0191/analysis, EXP-0192/analysis
Apple binary introspection: NONE. No shader compiled, no device contacted, no SSH.
Reproduction: python3 analysis/population_audit.py
Evidence: analysis/population_audit.json, analysis/reclassify.json,
          work/run01_stdout.txt, work/run02_stdout.txt
```

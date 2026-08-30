# EXP-0200 — reading `tools/agx-isa/wave_audit.py` against this experiment

Run: `python3 tools/agx-isa/wave_audit.py experiments/EXP-0200-cfrt-word-instruction-hw`

The audit is right to print what it prints. One of its lines (§2, `ALIASED`) is a
**keying artifact of this experiment's raw schema**, not a defect in the data;
one (§4) is a real and deliberate absence; the rest are genuine readings and §1
and §5 are the ones that matter. Each is reconciled below with the correctly-keyed
recomputation, which is in `analysis/field_verdicts.json` and reproducible from
`raw/` by `analysis/assemble_verdicts.py` and `analysis/scan200.py`.

Nothing in `raw/` was altered to make the audit read better. Raw is append-only.

---

## 1. `n4_rt_word.dst` — `cross-run agreement: 69.23 % (256/832 disagree)`

> **Note, 2026-08-30:** `wave_audit.py` was updated by the orchestrator while
> this experiment was running. It now keys cross-run agreement by **(arm, value)**
> and excludes volatile timing fields. This section is written against the
> **updated** tool. Against the earlier version the same row read `0.00 %`, which
> was a pure keying collision — four carriers sharing one `value` key, with the
> surviving record differing because the confirmation run used reversed arm order.

**Not an artifact, and it is exactly the carrier this experiment excludes.** All
256 disagreeing values are `rq_ccount`, whose **unmutated** baseline returned
`0.0` for the whole of the reversed run (14/14 baselines `silent_zero`). EXP-0187's
own frozen gate sets `baselines_ok = False` for it and drops it; the disagreement
is the carrier failing, not the field being unstable.

**The three carriers the verdict rests on agree 256/256 = 100.00 % each**
(`rq_mdist`, `rq_inst`, `rq_bbox`), recomputed per (carrier, value) by
`analysis/assemble_verdicts.py` and recorded in `field_verdicts.json` →
`n4_rt_word.dst.per_carrier.*.cross_run`.

## 2. `_instruction` rows — `ALIASED: fewer bytes than values`

**Artifact, and a deliberate schema choice.** For a fieldless `_instruction`
row there is no field value to sweep; the thing being varied is the **generated
encoding (the fill)**, dispatched at many different holes. `PRE_REGISTRATION.md`
§9 sets `value` to a **globally unique integer per (arm, fill)** precisely
*because* `wave_audit` pairs runs by `value` alone — a per-arm counter would
silently pair records from different arms. The cost of that choice is this line:
the same fill bytes recur at many holes, so distinct encodings (2, 12, 17) is
correctly smaller than distinct case ids.

**The aliasing check that actually applies** — *do nominally different cases
assemble to identical bytes within one arm?* — is
`analysis/contract200.py encodings`, which re-derives every byte constant from
the pinned descriptor's own `match` constraints and asserts all fills within an
arm are distinct: **74 arms, all fills distinct, 11/11 constants re-derived.**
And Gate A's ledger reports **736/736, 905/905, 1385/1385 requested == actual
dispatched bytes with 0 match-bit collisions** (`analysis/ledger.json`).

## 3. `_instruction` rows — cross-run agreement

**Resolved by the tool update.** Under the updated (arm, value) keying every
`_instruction` row reads **100.00 % (0 disagree)**: `n1_word` 15/15,
`n2_compact2` 18/18, `n3_word` 15/15, `n4_cf_word` 127/127, `n4_rt_word`
182/182, `rtq_pred` 47/47 — across a forward run and a reversed-order run.

Independently recomputed elsewhere in this experiment, and agreeing:

| pair | agreement |
|---|---|
| target-2 gated pair, 9 ruler arms × 38 fills | **100 %** at 7 arms, 97.4 % and 92.1 % at the other two |
| stop-scan pair, 905 shared offsets | **99.56 %** (901/905) |
| target-1 pair, per (carrier, value) | **100 %** on all three admitted carriers |

High agreement here proves **repeatability, not meaning** (Gate C). It is why the
ruler arm is still withdrawn as `carrier-undecidable`: its readings are perfectly
reproducible *and* confounded.

## 4. `n4_cf_word.b3` — `NO RAW RECORDS under either keying`

**Real, and correct.** No `b3` field sweep was run and **no `b3` verdict is
proposed.** The field carries a standing decline (EXP-0172 dispatched 256 values
and reported STILL-UNDERPOWERED; EXP-0184 declined re-litigating it), which the
coordinator restated mid-experiment. Eleven sampled `b3` values rode along as
`_instruction` fills and are recorded with `field: "_instruction"`, which is why
a `field: "b3"` query finds nothing. The row is retained only to carry the
*geometry* finding — that `b3` is byte +5 of a 6-byte `pop_reconverge` at all
three scanned sites — which changes what a future sweep should target.

## 5. What the audit shows that is NOT an artifact, and matters

* **`distinct oracles` is 4–13 on every row.** The host predictor varies across
  the fill space, so this is not the constant-oracle failure.
* **`V (distinct VALID payloads)` is 19–312 on every row**, so no row rests on an
  indistinguishable observable — *except* `n4_rt_word.dst` when computed **per
  carrier**, where it is **1**. That is the honest and load-bearing number:
  across all 1152 clean observations a carrier returns a single constant payload,
  so the field's movement is entirely its 64-value fault wall. It is a legality
  map, not a semantic, and `field_verdicts.json` says exactly that.
* **Hard outcomes are counted separately from valid payloads** (384 faults on
  `n4_rt_word.dst`, 1–6 elsewhere) and no verdict here counts a fault as
  movement.

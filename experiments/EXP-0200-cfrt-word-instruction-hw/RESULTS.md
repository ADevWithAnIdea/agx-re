# EXP-0200 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores,
macOS 26.6, Metal family Apple9). **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte dispatched is the compiled form of our
own MSL (`kernels/k_w200.metal`, `t1/kernels/k_rq187.metal`), overwritten with byte values we
chose, with every encoding re-derived from the pinned descriptors' own `match` constraints.
**No Apple binary was disassembled or introspected.**
**Gates:** `PRE_REGISTRATION.md` §8 as amended by A3 for
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md`, which is normative and overrides §8 where they
conflict.

---

## 0. Headline

**The six descriptors were blocked at `_instruction` because we could decode them but had
never shown the hardware does what they say. It turns out the hardware does something
else: at every site this experiment could measure, four of them are not instructions at
all.**

A `stop` — `_instruction: hardware-run`, whose 24-bit body is HW-proven free filler — was
written at 905 offsets across four carriers, twice, in opposite case order (99.56 %
agreement). A halt proves the offset is a boundary the hardware honours. The result:

| descriptor | sites stop-scanned | a hardware boundary | interior to a longer instruction |
|---|---:|---:|---|
| `n4_rt_word` `04 <dst> 20 80` | 3 | **0** | **+6 of a 10-byte instruction**, all 3 |
| `n4_cf_word` `04 01 00 00` | 3 natural + 1 | **1** (`cw_trans` +324, 4-byte span) | **+2 of a 6-byte `pop_reconverge`**, the other 3 |
| `rtq_pred` `06 c2 00 00` | 1 | **0** | **+6 of a 10-byte instruction** |

And the two results that stand on their own:

| item | result |
|---|---|
| **`n4_rt_word.dst` hazard wall** | **CONFIRMED as a gated pair** and extended to a third carrier. 64 of 256 values fault; the fault set is **exactly** `{v : (v & 0b110) == 0b100}` on `rq_mdist`, `rq_inst` **and `rq_bbox`**, in **both** runs. 6/6 carrier-runs, 384 fault and 1152 clean observations, zero exceptions, 100 % per-value agreement. |
| **…and what it is a wall *in*** | not a field of a compact word. The swept byte is **+7 of a 10-byte instruction** at all three sites. |
| `n4_rt_word.dst` semantics | **V = 1.** All 1152 clean observations return one constant payload per carrier. The movement is *entirely* the wall. Legality is mapped; the field's selection role is **UNKNOWN**. |
| six `_instruction` rows | **no label raised.** Real progress on the geometry dashboard; none on the semantic one. |
| Gate A | **736/736, 905/905, 1385/1385** requested == actual dispatched bytes; 0 match-bit collisions. Target 1 `reconstructed` grade: **1148/1148** decoded-from-bytes == requested. |
| Gate E | **NOT MET, for everyone.** Reported as `INCOMPLETE`, not worked around. |

---

## 1. Target 1 — EXP-0187's contract, honoured unchanged, and its gate passes

`t1/` is EXP-0187's apparatus carried in byte-for-byte. `harness/verify_remote200.py`
re-hashes all **27** blobs against EXP-0187's own `CAPTURE_CONTRACT.json` and refuses to
run on any difference: **27/27 match**, locally and on the device. Its verdict is computed
by its own frozen gate, `t1/analysis/verdicts.py`, unmodified.

Two gated runs: `g17p_20260830_t1run01` (1276 cases, 240 s, frozen order) and
`g17p_20260830_t1run02rev` (1276 cases, 282 s, **reversed** order via
`harness/arms187_reversed.json`, which asserts it is a permutation of the frozen arms and
refuses to write otherwise — Gate E's order requirement, met without touching the frozen
harness).

**Verdict under EXP-0187's own frozen gate: `n4_rt_word.dst` = LIVE, `hardware-run`**, moved
on 2 of the 3 arms with detection power.

### Observed

| carrier | dispatched | fault | ok | fault set == `(dst & 0b110) == 0b100` | distinct encodings | distinct valid payloads | cross-run agreement |
|---|---:|---:|---:|---|---:|---:|---:|
| `rq_mdist` | 256 ×2 | 64 ×2 | 192 ×2 | **yes, both runs** | 256 | **1** | 256/256 = 100 % |
| `rq_inst` | 256 ×2 | 64 ×2 | 192 ×2 | **yes, both runs** | 256 | **1** | 256/256 = 100 % |
| `rq_bbox` | 256 ×2 | 64 ×2 | 192 ×2 | **yes, both runs** | 256 | **1** | 256/256 = 100 % |
| `rq_ccount` | 256 ×2 | 0 | 256 / 0 | n/a | 256 | 1 / 0 | excluded |

`rq_bbox` is new: EXP-0187 never obtained a gated measurement there (start failure in one
run, hang-death in the other). It reproduces the wall exactly.

`rq_ccount` is **excluded by the frozen gate**, not by us: its *unmutated* baseline returned
`0.0` for the whole of the reversed run (`silent_zero`, 14/14 baselines), so
`baselines_ok = False`. A carrier-level failure, retained and reported.

### What this does and does not establish

* **Establishes (liveness):** 64 of 256 values of that byte are rejected by the hardware,
  reproducibly, on three carriers, in two runs in opposite order, with an exact predicate.
* **Establishes (semantics, bounded):** the predicate classifies 256/256 values correctly on
  3 carriers in both runs. That is a `bounded-map` **for legality**.
* **Does NOT establish:** any effect. **V = 1** — every one of the 192 accepted values on
  every carrier returns the same correct answer. Nothing selects anything. Under
  `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §2 that forbids `hardware-run` on the effect
  domain, and §9 requires both facts recorded: **the experiment passed its own frozen
  gate**, and **its evidence is insufficient for the current semantic gate**.
* **Does NOT establish (geometry) — and §3 shows it is misattributed:** the swept byte is
  not byte+1 of a 4-byte `n4_rt_word`.

---

## 2. Target 2, part one — the stop-ruler arm is CONFOUNDED, and its own data proves it

The ruler was pre-registered to read instruction length off a planted terminator, calibrated
by three words that already carry `_instruction: hardware-run` (`mov_imm` 2 B, `stop` 4 B,
`icmp_pred` 6 B). It is **withdrawn as `carrier-undecidable`**, in both directions — no
length is claimed and none is refuted.

**The refutation is internal.** Byte-identical 8-byte fills read oppositely at different
holes: `0a 00 0e 00 00 00 00 00` reads `not_written` at `cw_trans` +102 and +110 and `ok` at
+70 and +428, with 100 % cross-run agreement at each. No length property of an encoding can
do that. The cause is that `not_written` has **at least three** producers:

1. the planted terminator was honoured (what the arm intended to measure);
2. the result store was masked off — a fill that writes a predicate or pushes an execution
   scope suppresses it without halting anything;
3. the store's **address register was clobbered** — `mov_imm` writes r0, and if r0 carries
   part of the output pointer the store simply goes elsewhere.

That is a Gate B failure of my own design: the observable was not independent of the
mechanism. It is recorded rather than reinterpreted, and the gate in
`analysis/verdicts200.py` was corrected to detect exactly this signature — anchors that read
inconsistently across holes mean the instrument is not calibrated — and to return
`carrier-undecidable` rather than the `LENGTH-REFUTED` its first pass produced.

9 ruler holes × 38 fills × 2 runs are retained in `raw/g17p_20260830_t2run01` and
`…t2run02rev`. Cross-run agreement 100 % at 7 of 9 holes, 97.4 % and 92.1 % at the others.

---

## 3. Target 2, part two — the finding: these descriptors are shadowed, not merely undecoded

### 3.1 What the transparency arm saw

65 natural occurrences located by tokenizer walk or by signature + `decode_one` (amendment
A1). Into each, a `stop`. **The carrier returned its exact non-zero oracle at 60 of 65**;
only **2** halted; 3 gave a mixed reading. Both runs, reversed order.

At the *same* offset — `rq_mdist` +1306 — target 1 has an illegal `dst` faulting the command
buffer 64 times out of 256. **An illegal encoding is rejected where a terminator is
ignored.** Two models (`PRE_REGISTRATION.md` A5): the region is executed but masked (M1), or
the offset is not an instruction boundary and the bytes are an operand tail (M2).

### 3.2 The stop-scan settles it

Amendment A5, frozen before its first dispatch: write a `stop` at every offset on a 2-byte
grid in a ±32-byte window around each 4-byte occurrence, plus a 128-byte coarse grid across
the whole of `_agc.main`, on `rq_mdist`, `rq_inst`, `rq_bbox` and `cw_trans`. **A halt proves
the offset is a boundary the hardware honours and that the region is executed.** The claim is
one-sided on purpose; no-halt is reported as inconclusive.

905 shared offsets, **99.56 % cross-run agreement**, 75 offsets halting in both runs.
`rq_inst` failed to start in the first scan run and is a measured absence, not a result.

**M1 is refuted and M2 stands:** offsets *around* each occurrence halt while the occurrence
itself does not.

| descriptor | site | stop halts here | enclosing span (both runs) | occurrence at | enclosing bytes | our tokenizer says |
|---|---|---|---|---:|---|---|
| `n4_rt_word` | `rq_mdist` +1306 | **no** | `[1300, 1310)` = **10 B** | +6 | `b2 17 2d 73 82 2a 04 42 20 80` | `icmpsel`, len **14** |
| `n4_rt_word` | `rq_bbox` +1316 | **no** | `[1310, 1320)` = **10 B** | +6 | `b2 07 2d 6f 82 02 04 42 20 80` | `icmpsel`, len **14** |
| `n4_rt_word` | `rq_bbox` +6378 | **no** | `[6372, 6382)` = **10 B** | +6 | `e2 17 6d 6f 82 08 04 42 20 80` | *undecodable* |
| `n4_cf_word` | `rq_mdist` +1210 | **no** | `[1208, 1214)` = **6 B** | +2 | `0f 06 04 01 00 00` | `pop_reconverge`, len 6 |
| `n4_cf_word` | `rq_bbox` +1216 | **no** | `[1214, 1220)` = **6 B** | +2 | `0f 06 04 01 00 00` | `pop_reconverge`, len 6 |
| `n4_cf_word` | `cw_trans` +842 | **no** | `[840, 846)` = **6 B** | +2 | `0f 06 04 01 00 00` | `pop_reconverge`, len 6 |
| `rtq_pred` | `rq_bbox` +966 | **no** | `[960, 970)` = **10 B** | +6 | `2a 00 2b c0 06 00 06 c2 00 00` | `icmp_pred`, len 6 |
| `n4_cf_word` | `cw_trans` +324 | **YES** | `[324, 328)` = **4 B** | +0 | `04 01 00 00` | `n4_cf_word`, len 4 |

The consistency is the argument: three independent `n4_rt_word` sites in two carriers all
give a **10-byte** enclosing span with the signature at **+6**; three independent
`n4_cf_word` sites in three carriers all give a **6-byte** span with the signature at **+2**,
and the enclosing bytes are literally `0f 06 …`, which our own tokenizer already names
`pop_reconverge`. A store-address clobber does not produce a periodic pattern of halts 6 and
10 bytes apart.

`cw_trans` +324 is the exception that makes the rest legible: the local halt sequence is
320, 322, 324, 328, 334, 344, 352 — spans of **2, 2, 4, 6, 10, 8 bytes** — a plausible
instruction-length sequence, with `04 01 00 00` occupying a genuine 4-byte slot.

### 3.3 Consequences

* **`n4_cf_word` is not absent and not simply wrong — it is *shadowed*.** It exists as a real
  4-byte instruction (`cw_trans` +324) and its signature *also* matches the tail of a 6-byte
  `pop_reconverge`. This is the same shape EXP-0204 independently reported for
  `cubearray_coord_const` (decodes standalone and at a trailing boundary, `pad_operand` at an
  interior one). Two experiments, two descriptors, same failure mode, found on the same day
  by different methods.
* **This is the mechanical explanation of EXP-0172's `DEF-0172-4`** ("`n4_cf_word` has no
  observable effect at all, not merely `b3`"): its 256-value `b3` sweep was sweeping **byte +5
  of a `pop_reconverge`**, whose `reserved` body is already documented non-load-bearing. The
  right next experiment is not a bigger sweep; it is a different offset.
* **EXP-0187's `n4_rt_word.dst` result is not withdrawn — it is re-attributed.** The wall is
  real, reproducible and now confirmed on a third carrier. It is a property of **byte +7 of a
  10-byte instruction**, not of a compact word's destination selector.
* **A signature scan cross-checked with `decode_one` is not sufficient** to establish that an
  occurrence exists. **0 of the 7** signature-derived 4-byte occurrences the hardware scanned
  turned out to be boundaries. `decode_one` at an offset answers *"do these bytes match a
  descriptor"*, never *"does an instruction start here"*. Amendment A1 introduced that method
  in this experiment and this is its measured refutation.

### 3.4 The one clean generated-point

`cw_trans@n4_cf_word_324` is the single transparency arm that passed admission: `X_null` ok,
`X_reach` (a stop) halts, `X_over` (a 6-byte word in a 4-byte hole) breaks the program —
**two controls firing in opposite directions** — and the known-4-byte anchor `if_push`
substitutes cleanly. At that hardware-verified 4-byte boundary, **`06 c2 00 00` (`rtq_pred`)
and `04 42 20 80` (`n4_rt_word`), generated by us from the pinned descriptors' own `match`
constraints with no donor field, both execute with the carrier's exact oracle 12.5 intact**,
in both runs.

That is `generated-point` on the compiler-recipe axis for those two encodings. It is one
hole in one carrier, so it is **not** a length verdict and **not** `canonical-recipe-proven`.

---

## 4. The five gates

| gate | status |
|---|---|
| **A** ledger | **PASS.** Target 2: 736/736, 905/905, 1385/1385 requested == actual bytes sliced back out of the dispatched blob; 0 match-bit collisions in any arm. Target 1 (`reconstructed` grade — EXP-0187's harness predates Gate A and may not be edited): 1148/1148 decoded-from-actual == requested, 0 differ; the 128 n/a are fieldless match-byte probes. `analysis/ledger.json`. |
| **B** control | **PASS for the scan and the transparency arm** (a stop that halts, an over-length word that breaks, a same-length anchor that does not). **FAIL, self-declared, for the ruler arm** — the observable was not independent of the mechanism. That arm is `carrier-undecidable`. |
| **C** semantics | Predictions were pre-registered per fill and scored against a five-bucket observed classification. **The semantic domain here is instruction framing, not the micro-op's computational role**, which stays `unknown`. `sem_checked == 0` for that role, so **no row is raised to `hardware-run`**. |
| **D** recipe | Every candidate's bytes were re-derived from the pinned descriptors' `match` constraints (`contract200.py encodings`, 11/11) — **no instruction field came from a donor**. The surrounding program *is* a donor, so the axis reads `generated-point`, never `canonical-recipe-proven`. |
| **E** clean confirmation | **NOT MET.** Every pair ran with 8–9 concurrent sibling experiments. Both runs of every pair used **reversed case order**, and the concurrent-GPU process table is sampled into each `raw/*/env.json`, so "busy" is a measurement. **All six captures ran 19:16–19:48 UTC and none overlaps EXP-0204's declared 20:00–20:25 UTC hang window** (0 cases), so nothing is reclassified on that ground. Reproducibility is reported as `INCOMPLETE — Gate E not met`. |

---

## 5. Limitations, stated plainly

1. **The ruler arm failed as an instrument.** Reported, not reinterpreted (§2).
2. **`n1_word`, `n2_compact2`, `n3_word` are unmeasured.** The ruler is confounded and the
   fine stop-scan windows were centred on the 4-byte occurrences, so their offsets were not
   scanned at 2-byte granularity. One suggestive datum: at `cw_trans` +292 and +316 —
   walk-confirmed `n1_word` boundaries **inside** a finely scanned window — a stop did not
   halt while stops at +320/+322/+324 did. No-halt is not proof of interiority and **no
   verdict is drawn from it.**
3. **No-halt is inconclusive by construction.** Only the positive half of the scan is
   load-bearing. A boundary could exist inside a 6- or 10-byte span and fail to halt for an
   unrelated reason; the argument rests on the *consistency* of the spans across independent
   sites, not on any single one.
4. **`n2_compact2`'s ruler fill was self-aliasing** and the pre-registered token record caught
   it: `02 00` followed by the stop makes `02 00 0e …`, which satisfies `iminmax`'s match
   (byte+2 low 3 bits == 6) and decodes as a 6-byte `iminmax`. That arm never tested
   `n2_compact2`. It is exactly the aliasing hazard the dispatch warned about, in a place the
   design did not anticipate.
5. **`rq_inst` failed to start in the first scan run** — a measured absence; its scan results
   come from the reversed run only and are therefore excluded from the both-runs halt set.
6. **Gate E is unmet** and no promotion should follow until a serialized quiet window exists.
7. **`n4_cf_word.b3` was not swept** and no `b3` verdict is proposed (§4 of
   `analysis/wave_audit_notes.md`).

---

## 6. Reading `wave_audit.py` against this experiment

Several of its lines are keying artifacts of this raw schema — the 0.00 % cross-run
agreement on `n4_rt_word.dst` is four carriers colliding on one `value` key, and the
`ALIASED` flags are the deliberate globally-unique `value` required for correct cross-run
pairing. Each is reconciled against the correctly-keyed recomputation in
**`analysis/wave_audit_notes.md`**. Nothing in `raw/` was altered.

The audit's non-artifact readings are the important ones and they hold: `distinct oracles`
is 4–13 on every row (not a constant oracle), hard outcomes are counted separately from
valid payloads (384 faults never counted as movement), and `V` **computed per carrier** is
**1** for `n4_rt_word.dst` — which is the honest, load-bearing number and the reason no
semantic claim is made for it.

---

## 7. Recommended next

1. **Re-target `n4_rt_word`.** Sweep byte +7 of the 10-byte instruction at `rq_mdist` +1300
   *as that instruction's operand*, with the other nine bytes varied. The wall is real; what
   it is a wall in is now answerable.
2. **Fix the length rules, from hardware.** `icmpsel` at `b2 17 2d 73 82 2a …` is **10** bytes,
   not the 14 our tokenizer gives; `icmp_pred` at `rq_bbox` +960 is **10**, not 6. Both were
   measured, not inferred.
3. **Stop-scan first, sweep second.** The scan is cheap (905 offsets, 105 s) and it would have
   saved EXP-0172, EXP-0184 and EXP-0187 from sweeping operand tails. It belongs in
   `FIELD-SWEEP-PROTOCOL` §3 as a precondition on any new carrier.
4. **`n1_word` / `n2_compact2` / `n3_word` need a fine stop-scan** over `cw_trans` +60…+560,
   which this experiment did not run. ~250 offsets, under a minute.
5. **Do not re-sweep `n4_cf_word.b3`.** Sweep the `pop_reconverge` that contains it, or the
   genuine 4-byte occurrence at `cw_trans` +324.

---

## 8. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/k_w200.metal and t1/kernels/k_rq187.metal -- authored by us --
                       and the `_agc.main` bytes the public Metal runtime compiled from them,
                       overwritten with byte values we chose. Every candidate encoding is
                       re-derived from t1/pinned/db.json's own `match` constraints by
                       analysis/contract200.py (11/11 verified).
Apple binary introspection: NONE
Reproduction:          README.md
Evidence:              raw/t1_frozen0187/{g17p_20260830_t1run01, g17p_20260830_t1run02rev}
                       raw/{g17p_20260830_t2run01, g17p_20260830_t2run02rev}
                       raw/{g17p_20260830_t2scan01, g17p_20260830_t2scan02rev}
                       raw/prefreeze/{census200.json, census200.v2.json, holeprobe01/,
                                      CAPTURE_CONTRACT.v1..v7.json}
                       analysis/{field_verdicts.json, boundary_map.json, ledger.json,
                                 t2_verdicts.json, wave_audit_notes.md}
                       CAPTURE_CONTRACT.json (46 blobs, re-verified ON THE DEVICE, 46/46;
                       t1/ re-verified against EXP-0187's own contract, 27/27)
```

# EXP-0169 — RESULTS

**Status: PARTIAL.** §1 and §2 are complete and final (offline analysis over committed
evidence). §3–§6 are **PENDING the device**: EXP-0167 holds the machine and EXP-0163 (~88
deliberate device resets, so it runs alone) is queued ahead. Per the orchestrator's ruling
of 2026-08-30 (`CAPTURE_CONTRACT.json` `amendment_01`) the gated pair then runs **unlocked
and concurrently** with EXP-0168/0171/0172, with offline adjudication — the poison, both
sentinels and the 16-GPR dump — as the primary anti-contamination instrument and
`raw/<run>/03_procsample.jsonl` measuring what was actually running. The **DSTORE arm is
the one exception** (`amendment_03`): it stores through unbound binding slots, so it runs
last, in its own gated pair, with the other agents held off.

**Target:** Apple A18 Pro / G17P for §3–§6. §1–§2 are analysis over the committed corpus and
carry the target of whatever experiment supplied each record (stated per field).

---

## 1. OBSERVED (offline): 12 of the 144 are unauditable only because of a bad citation list

**This is not a hardware result. It is an auditability result, and it needs no device.**

`EXP-0164/analysis/audit.py::gather()` collects observations only from the experiments named
in a field's `evidence` array in `validation.json`:

```python
for eid in evidence:
    d = resolve(eid)
    if not d or key not in index.get(d, {}):
        continue
```

That is the right behaviour for auditing a *promotion* — the promotion really was made on
the cited evidence — but it means a field whose promotion cites `EXP-0016` is judged on
`EXP-0016`'s raw alone, even when a **later** experiment swept the identical db field, value
by value, with bit-exact attributable records.

`analysis/recitation.py` re-runs **EXP-0164's own gate** (`stable_live`; thresholds
`MIN_COMMON=2`, `MIN_AGREE_PCT=99.0`, `MOVED_OVER_DISAGREE=2.0` copied verbatim) over the
whole raw index instead of only the cited experiments:

| bucket | count |
|---|---|
| `RECOVERABLE-BY-CITATION` | **12** |
| `RECORDS-BUT-FAILS-GATE` | **3** |
| `NO-RECORDS-ANYWHERE` | **129** |

### The 12, with the uncited experiment that already clears the gate

| field | currently cites | already attributable in | that experiment's target |
|---|---|---|---|
| `falu2.opsel` | EXP-0005, EXP-0006 | **EXP-0153** (arm `uni\|B_modlo`, 64 common values, 100.0% agreement, 21/21 moved) | **G17P** |
| `falu2.srcA_reg` | EXP-0099/0105/0112/0119 | **EXP-0153** (32 common, 100.0%, 5/5 moved) | **G17P** |
| `falu2.srcB_reg` | EXP-0099/0112/0119 | **EXP-0153** (three arms; best 128 common, 100.0%, 68/68 moved) | **G17P** |
| `falu2.srcB_reg_top` | EXP-0099, EXP-0119 | **EXP-0153** (128 common, 100.0%, 63/63) and EXP-0138 (14 common, 100.0%, 6/6) | **G17P** / M4 |
| `falu_srcmod12b.ctrl` | EXP-0089, EXP-0119 | EXP-0138 (62 common, 100.0%, 32/12 moved) | M4 |
| `falu_srcmod12b.opsel` | EXP-0119 | EXP-0138 (7 common, 100.0%, 3/3) | M4 |
| `ibitcount.form` | EXP-M4-14 | EXP-0139 (8 common, 100.0%, 2/2) | M4 |
| `ibitcount.op_enable` | EXP-M4-14 | EXP-0139 (16 common, 100.0%, 8/8) | M4 |
| `ibitcount.srcdesc` | EXP-0129, EXP-M4-14 | EXP-0139 (256 common, 99.2%, 128/130) | M4 |
| `icmp_pred.dst_pred` | EXP-0104/0115/RT-ISA-FIX | EXP-0139 (16 common, 100.0%, 5/5) | M4 |
| `device_load.base_slot` | EXP-0010, EXP-0083 | EXP-0141 (16 common, 100.0%, 2/2) | M4 |
| `device_load.idx_off` | EXP-0082, EXP-0100 | EXP-0141 (14 common, 100.0%, 10/10) | M4 |

### THE CAVEAT I FOUND BY TRYING TO BREAK MY OWN FINDING

**`RECOVERABLE-BY-CITATION` means "clears EXP-0164's gate". It does NOT mean "meets the
`hardware-run` range bar."** EXP-0164's `stable_live` has **no coverage term at all** —
`THIN_COMMON = 8` exists in `audit.py` but is used only to set an informational
`thin_cross_run` flag and is never consulted by the gate (verified by reading `audit.py`
lines 28 and 188). `docs/evidence-classification.md` §2, by contrast, asks `hardware-run`
for "the full encodable range, at minimum its boundaries plus interior samples".

Measuring the passing arms against each field's encodable range:

| field | width | passing arm | values | coverage |
|---|---|---|---|---|
| `falu2.srcB_reg` | 6 | EXP-0153 `uni\|B_srcB_nongpr` / `D_falu2_srcB` | 64 | **100%** |
| `falu2.srcB_reg_top` | 1 | EXP-0153 / EXP-0138 | 2 | **100%** |
| `ibitcount.srcdesc` | 8 | EXP-0139 | 256 | **100%** |
| `icmp_pred.dst_pred` | 4 | EXP-0139 | 16 | **100%** |
| `falu_srcmod12b.opsel` | 3 | EXP-0138 | 7 | 87.5% |
| `falu_srcmod12b.ctrl` | 7 | EXP-0138 | 62 | 48.4% |
| `falu2.opsel` | 3 | EXP-0153 `uni\|B_modlo` | 2 | 25.0% |
| `device_load.base_slot` | 8 | EXP-0141 | 16 | 6.2% |
| `ibitcount.op_enable` | 8 | EXP-0139 | 16 | 6.2% |
| `falu2.srcA_reg` | 6 | EXP-0153 `uni\|B_modlo` | 2 | 3.1% |
| `ibitcount.form` | 8 | EXP-0139 | 8 | 3.1% |
| `device_load.idx_off` | 11 | EXP-0141 | 14 | 0.7% |

**Only 4 of the 12 clear the gate over the field's full encodable range.** For the other 8,
the citation fix repairs the **attribution** defect and leaves the **range** question open.
Three of the thin ones (`falu2.opsel` 2/8, `falu2.srcA_reg` 2/64, plus `falu2.srcB_reg`
which is already full) sit inside arms this experiment sweeps **densely** anyway — the
matrix sweeps every field of every target descriptor, not only the withheld ones — so
`falu2`, `ibitcount` and `icmp_pred` coverage closes on **G17P** as a by-product of the
device run. `falu_srcmod12b.*` and `device_load.*` are not in any arm here and keep an open
range question.

Reporting the 12 without this column would have overstated them. (Recorded as
`CAPTURE_CONTRACT.json` `amendment_04`.)

### INTERPRETATION, kept separate from the observation

* For these 12, **EXP-0164's `UNVERIFIABLE` verdict is an artefact of the citation list, not
  of missing evidence.** The remedy is an `evidence`-array fix in `validation.json`, which
  is the orchestrator's file.
* **Four of the twelve get *better* evidence out of the fix, not merely equal evidence:**
  `falu2.opsel`, `falu2.srcA_reg`, `falu2.srcB_reg`, `falu2.srcB_reg_top` are recoverable
  from **EXP-0153, which ran on G17P** — the documentation target — while they currently
  cite A18-era or M4 experiments.
* **Eight of the twelve would change `target` from A18 to M4**, because the uncited
  experiment ran on the M4. Under `docs/evidence-classification.md` §3.2 that is a real
  relabel, not a formality. **That call is the orchestrator's, not this experiment's.**
* This section is **not** a substitute for a fresh capture where the field is load-bearing.
  It is a statement about what the corpus already proves, made so the device window is spent
  on the 129 that genuinely need it.
* **The finding also exposes a method defect in EXP-0164 itself**, which the orchestrator has
  accepted: `gather()` asks "does the CITED evidence support this promotion?", which is the
  right question for auditing a promotion and the wrong one for "does evidence exist anywhere
  in the corpus?". The honest decomposition of the 144 is 12 / 3 / 129, not a flat 144.

### The 3 that have records but miss the gate

| field | why it misses |
|---|---|
| `icmp_pred.cond` | EXP-0139 `NAT:k_div@icmp_pred+0x0cc`, run01 vs run02: 256 common values, **250 agree = 97.66%**, below the 99.0% bar. 6 values disagree. Both runs moved (144 / 147). This is a *stability* miss under M4-era concurrency, not an attribution miss, so a fresh gated pair on G17P is the fix and it is in this experiment's device scope. The orchestrator's ruling was explicit: re-measure it, do not argue 97.66% past the bar. |
| `pixel_order.kind` | EXP-0162, one gated run only (256 values, 256 moved). Needs a second run. **EXP-0168 owns this field** (coordinator's "one-field-away" list). |
| `ray_move.b3` | EXP-0157 `rq_all\|B2`, two runs, **255 values, 0 moved in either**. Attributable and stable — but *inert*, on one arm. Under EXP-0164's own rule that is `INERT-SINGLE`, not `UNVERIFIABLE`; it needs a second, structurally different carrier, and an RT carrier is out of this experiment's scope. |

---

## 2. OBSERVED (offline): what the remaining 132 need, and what this experiment will do

129 `NO-RECORDS-ANYWHERE` + 3 `RECORDS-BUT-FAILS-GATE` = **132 fields need the device**.

**In scope here: 57** (`PRE_REGISTRATION.md` §1b) — `falu2` 8, `falu2i` 8, `falu2_uni` 1,
`half_alu` 4, `half_alu_ext8` 7, `half_alu_fma12` 2, `iunary` 2, `reg_move_{c0,c1,c2var,c9,cb}`
18, `bf_alu` 1, `icmp_pred.cond` 1, `get_sr` 2, `device_store` 3.

**Swept but not ruled on: `dst` on every descriptor** — EXP-0168 owns those verdicts
(coordinator directive 2026-08-30). The raw is captured and attributable regardless, because
*which register slot changed* is this experiment's primary detection instrument.

**Out of scope, named rather than half-done: 64 fields** needing a graphics / texture / RT /
control-flow / spill-frame harness — `tex_addr_setup` 11, `matrix_mac` 10,
`link_save_restore` 6, `tex_sample` 5, and 32 others (full list in `PRE_REGISTRATION.md`
§1b). Naming the bound is part of the result.

**Arithmetic of the debt, if everything lands:** 144 withheld → 12 recovered by citation
→ 57 re-recorded here → **75 addressed, 69 still open**, of which 64 are the named
out-of-scope set and 5 are EXP-0168's.

---

## 3. PENDING — the fresh capture

Will report: cases dispatched per gated run, cross-run agreement, per-field verdict class
(`LIVE` / `INERT-MULTI` / `INERT-SINGLE` / `UNSTABLE` / `NO-DETECTION-POWER` /
`SEMANTIC-ORACLE-FAILED`), and the label each maps to.

## 4. PENDING — fields whose original promotion does NOT reproduce

**Reported first and loudest when it exists.** A field that is exhaustively swept, cross-run
stable, on ≥2 carriers whose liveness ladder passed, and that shows no observable effect
while the corpus claims a live one — or that disagrees with the host-computed oracle at
value level — means the corpus has been carrying a wrong fact. `analysis/reproduction.json`.

## 5. PENDING — the three published `falu2` semantic claims, checked value by value

EXP-0138's source-class model and inline 8-bit minifloat immediate; EXP-0158's
negative-sign-at-`srcB_neg==0`; EXP-0158's operand-provenance-dependent `mod_hi`. The host
oracle and the C1/C2 provenance carriers are built specifically to test these
(`PRE_REGISTRATION.md` §2 H4, §6).

## 6. PENDING — the acceptance test

`analysis/reindex_check.py`: EXP-0164's own `collect_raw.py`, byte-identical
(sha256 `aa15cd24…`), run over this experiment's `raw/`, reporting bit-exact attribution per
field. **A field ruled on with no bit-exact attribution is a failure of this experiment**,
and is printed as one.

---

## Limitations already known

* §1 is an argument about **citation lists**, not new hardware evidence. It cannot promote
  anything by itself and it does not attempt to.
* §1's `RECOVERABLE` verdicts inherit the **target** of the uncited experiment; eight of the
  twelve are M4, not A18/G17P.
* §1's `RECOVERABLE` verdicts clear **EXP-0164's gate**, which has no coverage term. Only 4
  of the 12 also meet the `hardware-run` full-range bar. Eight carry an open range question
  that the citation fix does not touch.
* The device scope is 57 of 132, chosen by leverage (`falu2` first, then the EXP-M4-14
  citations that have no raw at all, then the `reg_move` family). The other 64 are bounded
  and named, not silently dropped.
* Tier-2 arms are ruled on by *difference from the unmutated anchor*, which detects change,
  not correctness. Only `falu2` and `falu2i` carry a Tier-1 host-computed oracle. §3 will
  state which tier each field was ruled on.

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE (device); analysis-only for sections 1-2
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the PUBLIC
  runtime API compiled from that source; committed raw/ trees of prior experiments in
  this repository; tools/{shdump,agxtest,agx-isa} READ-ONLY and unmodified.
Apple binary introspection: NONE.
Reproduction: README.md
Evidence: analysis/recitation_recovery.json, work/raw_index.json.gz,
          raw/ (pending)
```

---

# PART II — THE FRESH CAPTURE ON G17P (sections 3–6, filled in 2026-08-30)

**Target: Apple A18 Pro / G17P**, `AGXAcceleratorG17P`, `applegpu_g17p`, 5 cores,
macOS 26.6. Everything below is a **G17P** claim.

Gated pair, both runs 16,827 cases, `matrix_sha256`
`dfc41717034f52dd26dc0894ceac206966898ec27de6b1607f9dbcb66c82fff3` **identical in both**:

| run | order | cases | elapsed | fault | hang | sentinel_bad | baseline_fail | victim |
|---|---|---|---|---|---|---|---|---|
| `g17p_20260830_run01` | forward | 16827 | 189.9 s | 116 | 0 | 0 | 0 | 73 |
| `g17p_20260830_run02` | reverse | 16827 | 191.5 s | 115 | 0 | 0 | 0 | 17 |

**SCOPE RESTRICTION, stated up front.** This pair ran on the two `mov_imm`-seeded
carriers **C1_alu and C3_uni only**. `C2_load` and the `DSTORE` arm were held back —
`C2_load` because the pilot proved its seed path unsound (§7), `DSTORE` because
amendment_03 schedules it last, alone, after telling the orchestrator. Every field in
device scope is reachable on C1+C3, so the pair still rules on all of them; what the
restriction costs is the *second* carrier for several arms, which caps some rows at
`INERT-SINGLE`/`NO-DETECTION-POWER` instead of an inert claim.

## 3. OBSERVED — the fresh capture

100 rows emitted, **86 ruled on** (14 are `dst`/`get_sr.form` rows swept as the
detection instrument but handed to EXP-0168/EXP-0172 with no verdict):

| verdict class | n |
|---|---|
| `LIVE` (→ `hardware-run`) | 46 |
| `NO-DETECTION-POWER` (→ `untested`) | 34 |
| `INERT-SINGLE` (→ `untested`) | 3 |
| `SEMANTIC-ORACLE-FAILED` (→ adjudicated in §5) | 3 |

**Against EXP-0164's withheld 144: 58 fields are ruled on here, 30 of them `LIVE` over
the FULL encodable range** on 1–2 carriers with 100 % cross-run per-value agreement.

**Coverage is machine-auditable, which is the point.** Every one of the 100 rows carries
`values_dispatched`, `distinct_bytes`, `encodable_range`, `start`, `width`,
`coverage_pct`, `thin`, `under_covered` — **0 rows missing any key**. Only **2 rows are
THIN** (`bf_alu.tail`, `half_alu_fma12.ext`) and **0 rows are UNDER-COVERED**, i.e.
nowhere did the sweep dispatch a value it failed to actually encode.

## 4. OBSERVED — reproduction, and why NOTHING actually fails to reproduce

The raw verdict counts are `REPRODUCES` 40, `CONTRADICTS-INERT-CLAIM` 6,
`DOES-NOT-REPRODUCE` 2, `NEEDS-ADJUDICATION` 1, `INCONCLUSIVE` 37. **Adjudicated, all
nine flagged rows are artefacts of my own analysis, not corpus errors.** Reported loudly
because the pre-registration says failures come first — and the honest finding is that
**this experiment's machinery, not the corpus, was wrong.**

### 4a. The 6 `CONTRADICTS-INERT-CLAIM` rows are a regex false positive

`verdicts.INERT_WORDS` matches `inert` anywhere in the original `range`/`note` and
concludes the corpus called the field inert. But these ranges describe fields with
**mixed live and inert BITS**, and the field as a whole is live. E.g.:

  * `falu2.ctrl` — "bits0/1 are the 0x09-group instruction-LENGTH selector …, **bits2/3/4
    inert**, bits5/6 silent corruptors"
  * `falu2.mod_hi` — "bit44 at {0,1} (silent corrupt-to-zero) …; **bits45-47 … (no
    observable effect)**"
  * `falu2.opflags` — "19=release srcA, 20=release srcB, 21=destination publication" —
    an unambiguously LIVE description; the match came from the note.

Also `falu2.srcA_reg_top`, `falu2.srcB_reg_top`, `ibitcount.srcdesc`. My fresh verdict is
`LIVE` for all six, which **AGREES** with the original claim. **Correct reading:
`REPRODUCES` ×6.**

### 4b. The 3 `SEMANTIC-ORACLE-FAILED` rows are an oracle-SCOPE defect

`run.sem_oracle` models `falu2i` as `srcA (+|*) imm_decode(immediate)` but **never
requires `opflags == 0`**, so it mispredicts on every case where a source modifier is
active — and the case matrix's pre-registered *crossings* deliberately set `opflags` while
sweeping other fields. Partitioned per case from the committed `bytes` column:

| run | sem checks | mismatches | mismatches with `opflags != 0` | **residual** |
|---|---|---|---|---|
| run01 | 716 | 378 | 378 | **0** |
| run02 | 716 | 378 | 378 | **0** |

**Every single mismatch, in both runs, is explained. Zero unexplained.** On the 338
checks per run where the oracle is applicable (`opflags == 0`) the published claim matches
**100 %**. All three rows (`falu2i.ctrl_lo`, `falu2i.mods`, `falu2i.opflags`) are
`gate_live=True`, 100 % cross-run agreement, **full encodable range** (128/128, 256/256,
16/16). **Correct reading: `LIVE` → `hardware-run` → `REPRODUCES` ×3.**

**Corrected reproduction totals: `REPRODUCES` 49, `DOES-NOT-REPRODUCE` 0,
`INCONCLUSIVE` 37.** No field in this experiment's scope was found to contradict its
committed claim.

## 5. OBSERVED — the published `falu2` semantic claims, value by value

The host-computed oracle is independent of the GPU, so this is a real value-level test,
not a round trip.

  * **H4(a) EXP-0138's inline 8-bit minifloat immediate at `srcB_class==1`, `srcB_reg`
    64..127, and H4(b) EXP-0158's sign-negative-at-`srcB_neg==0`: BOTH REPRODUCE.**
    `falu2` — **0 mismatches out of 256 host-computed checks** (128 on C1_alu + 128 on
    C3_uni), in each of the two gated runs. Two structurally different carriers.
  * **EXP-0006's packed-minifloat `falu2i` immediate (`isadb.imm_decode`): REPRODUCES**
    on all 338 applicable checks per run (§4b).
  * **H4(c) `falu2.mod_hi` operand-provenance dependence: NOT TESTED.** It requires a
    LOAD-sourced operand, i.e. `C2_load`, which §7 withdraws. `falu2.mod_hi` is `LIVE`
    at full range (16/16) on C1_alu+C3_uni, but the *provenance* half of the claim is
    untested and stays `INFERRED`.

## 6. OBSERVED — the acceptance test PASSED

`analysis/reindex_check.py`, using a **byte-identical copy** of
`EXP-0164/analysis/collect_raw.py` (sha256 `aa15cd24d69d6ab5…`, asserted at run time):

    EXP-0169 keys in the index : 100
    fields ruled on            : 100
      bit-exact attributed     : 100
      NOT attributed           : 0
    arms per attributed field  : {1: 61, 2: 39}

**H1 holds; its refuter did not fire.** Every field ruled on here is bit-exactly
attributable to EXP-0169 by EXP-0164's own unmodified indexer — which is precisely what
the 144 withheld fields could not do. 4,536 cells, 4,917 groups, **no unparseable lines**.

## 7. OBSERVED — the instrument defect that withdrew the `C2_load` arm

Full detail in `PROGRESS.md` M8; the load-bearing facts:

  * **`device_load` on G17P is ASYNCHRONOUS and this harness issues no wait or scoreboard
    barrier anywhere.** Registers landed, as a function of filler instructions inserted
    between issue and use: **0, 0, 0, 0, 2, 5, 8, 8 of 8** for filler
    **0, 2, 4, 8, 16, 32, 64, 128**. Monotone, saturating. **HW-VALIDATED, G17P**
    (`raw/pilot03`).
  * **`device_load`'s `idx_off` unit is 1 WORD** — 23 of 23 landed entries have
    `word_index == idx_off` — **not the 4 words of `device_store`** (EXP-0090/0119).
    HW-VALIDATED, G17P. Frozen in `work/calib.json`.
  * **The same program gave different seeds at different times**: the smoke-S2 sequence
    landed 11 of 14 in `pilot01` (machine loaded, siblings dispatching) and **14 of 14 on
    five consecutive repeats** in `pilot03` (machine idle). The non-determinism is
    directly observed; contention as its cause is **INFERRED**.
  * **Why that is fatal for verdicts and not merely noisy:** `match` is digest equality
    against a baseline refreshed only every 250 cases, so a differently-seeded baseline
    records up to 250 cases as **movement — a FALSE `LIVE`**. The PRE/POST sentinels are
    `mov_imm`-materialised and always land, so they cannot detect it; and the retry loop
    breaks on the first non-fault attempt, so `majority_of: 3` never engages.
    C1_alu/C3_uni/C4_store are `mov_imm`-seeded and immune.

**This is a defect in MY harness, found by my own pilot before any gated dispatch, and it
is the reason the C2_load arm is withdrawn rather than published.**

### What the withdrawal costs, precisely

**14 of the 34 `NO-DETECTION-POWER` rows are recoverable by that arm alone** —
`half_alu_ext8` ×10 and `half_alu_fma12` ×4 — because their liveness ladder **FAILED on
C1_alu and PASSED on C2_load** in `pilot01`. That carrier asymmetry is **H3 confirmed**
(detection power is the real variable), and it means those 14 fields are untested for want
of a working carrier, not because the hardware is quiet.

## 8. OBSERVED — the liveness ladder, and the 34 rows with no detection power

20 of 30 (arm, carrier) ladders passed. The 10 failures are all on `mov_imm`-seeded
carriers, so they are **not** latency artefacts, and each is identical on both of its
carriers:

  * `RM_C0`, `RM_C2VAR`: `L_known_move` moves but **`L_src_reg` does not** — the
    instruction has an observable effect, yet changing which source register it names does
    not change it.
  * `RM_C1`, `RM_C9`: `L_dst` does not move either; `RM_C9`'s byte0 falsifier scored `ok`.
  * `RM_CB`: **passes all five steps on both carriers** — and its `b3`, `form`, `src` are
    `LIVE` at full 256/256 range.
  * `GET_SR`: `L_dst` moves, but **`L_form` and `L_sr_sel` do not** — every probed
    `sr_sel` returned the same value.

Consequence, per the pre-registered rule: 15 of the 18 `reg_move` fields and all 4
`get_sr` fields are `untested` / `NO-DETECTION-POWER`. **This is reported as a limit of
the carrier, NOT as "the field is inert"** — the `iter_at.loc` failure mode the
pre-registration named.

## 9. Three arms never resolved an anchor — reported, not patched around

`iunary` and `icmp_pred` appear in **none** of the 28 authored probe kernels' compiled
output. The 5 integer-unary probes compiled to `cvt_f2i`/`cvt_i2f`/`iadd2`/`ibitcount`,
and all four comparison probes to `isel10`/`isel8`/`isel10_c`/`isel_reg`.

**OBSERVATION, G17P: for these authored MSL patterns the compiler never selects
`icmp_pred`.** Consistent with EXP-0139 having had to construct it. `kernels/probes.metal`
is frozen, and adding a kernel to chase an anchor is exactly the post-hoc fitting the
freeze exists to prevent — so `iunary` ×2 and `icmp_pred.cond` have **no arm** and stay
`untested`.

**Also a DB gap:** `k_hchain` tokenizes as `get_sr@0 device_load@4 device_load@18
<unknown>@32` with **52 bytes leftover**, under both db versions — a half-precision chain
emits an instruction whose length rule `db.json` cannot resolve.

## 10. The recitation rows my own matrix closes

Of the **8 THIN** citation-recoverable rows (§1's caveat), the fresh G17P capture closes
**4** at full encodable range — **not 6**:

| row | old coverage | EXP-0169 |
|---|---|---|
| `falu2.opsel` | 2/8 | **8/8 LIVE — closed** |
| `falu2.srcA_reg` | 2/64 | **64/64 LIVE — closed** |
| `ibitcount.form` | 8/256 | **256/256 LIVE — closed** |
| `ibitcount.op_enable` | 16/256 | **256/256 LIVE — closed** |
| `falu_srcmod12b.opsel` | 7/8 | no arm — **still open** |
| `falu_srcmod12b.ctrl` | 62/128 | no arm — **still open** |
| `device_load.base_slot` | 16/256 | no arm — **still open** |
| `device_load.idx_off` | 14/2048 | no arm — **still open, most exposed** |

Of the **4 FULL-RANGE** rows, 3 are re-confirmed by fresh G17P capture
(`falu2.srcB_reg` 64/64, `falu2.srcB_reg_top` 2/2, `ibitcount.srcdesc` 256/256);
`icmp_pred.dst_pred` had no arm (§9).

## 11. EXP-0164's run-selection / hang-placeholder defect does NOT touch this set

Checked as asked. The 12 `RECOVERABLE-BY-CITATION` and 3 `RECORDS-BUT-FAILS-GATE` rows
draw their passing records from **EXP-0141, EXP-0153, EXP-0138 and EXP-0139 only —
EXP-0144 appears nowhere**, so the disowned-capture tie-break cannot have selected it
here. No row's verdict rests on a record carrying `outcome: "hang"`. And the
`collect_raw.py:42` defect *inflates* observation counts, whereas the 129
`NO-RECORDS-ANYWHERE` rows have **zero** records — an inflating defect cannot have
created that verdict. **No collisions to report.**

## 12. OBSERVED — the quiet window was MEASURED, and there wasn't one

`harness/procsample.py` sampled every 5 s for the duration of both gated runs
(`raw/<run>/03_procsample.jsonl`). **Neither run had a single quiet sample:** 41 of 41
and 47 of 47 samples recorded foreign GPU activity throughout — `EXP-0168`'s
`agxrun_persist` and `gfrun3`, `EXP-0171`'s `agxrun_persist`, plus `MTLCompilerService`
and Xcode `clang` invocations.

Both runs nevertheless produced **0 `sentinel_bad`, 0 `baseline_fail`, identical
`ok` counts (5305/5305), identical semantic-oracle counts (972 checked / 594 matched),
and 100 % per-value cross-run agreement** on every field examined; faults differed by one
(116 vs 115) and victims by the expected margin (73 vs 17).

Two conclusions, and they point in opposite directions:

  * **amendment_01 is vindicated for the `mov_imm`-seeded carriers.** Running unlocked
    alongside three sibling experiments cost this pair essentially nothing measurable.
  * **It sharpens §7 rather than softening it.** What is contention-fragile is
    specifically the **asynchronous `device_load` seed path**, not the harness in general.
    That is why the withdrawal is confined to `C2_load` and why the other three carriers
    are safe to run unlocked.

This also extends EXP-0167's one-directional finding. EXP-0167 showed contention can
*destroy* an observation but never fabricate a coherent one, measured over **outcome
classes** (`ok`/`fault`). A **diff-based movement oracle is different in kind**: if the
baseline and the mutant land their seeds differently, `obs != base` and contention
**fabricates apparent movement**. That failure mode is invisible to an outcome-class
audit, and it is the one §7 withdraws the arm over.

## 13. The assembler defect (EXP-0170 / `dc367a43`) does NOT touch this capture

This experiment pinned `work/frozen/isadb.py` at
`c97c2a22fe4eb3aaa2140ff716686dcdbbbb099dcd68d2af77f7f9054174dd36`, which is the
**pre-`dc367a43`** version — i.e. the gated pair ran *before* `assemble()` learned to
refuse match/field conflicts. Two independent reasons that is harmless here:

1. **Mutations are bit surgery, not `assemble()`.** A field under test is mutated by
   `set_field` on the lifted anchor bytes; `assemble()` only builds scaffolding
   (`mov_imm`, `device_load`, `device_store`, `get_sr`, `stop`), whose field values are
   fixed and legal. A conflicting-assemble defect cannot corrupt the instruction under
   test.
2. **There is direct machine-checkable evidence.** The `distinct_bytes` column exists
   precisely to catch this signature — a sweep that reports N values but produced fewer
   than N distinct encodings, because match-overlapping bits were stuck.
   **0 of 100 rows are UNDER-COVERED.** Every row dispatched at least as many distinct
   encodings as field values.

So this capture needs no re-run on that account, and the pinning is what makes the claim
checkable rather than merely plausible.

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

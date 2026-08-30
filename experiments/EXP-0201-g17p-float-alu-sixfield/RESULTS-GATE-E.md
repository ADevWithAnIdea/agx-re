# EXP-0201 — RESULTS ADDENDUM: Gate E satisfied

**Supersedes the promotion verdicts of `RESULTS.md` §0 only.** Everything else in `RESULTS.md`
stands: the hypotheses, the arms, the semantic maps, the three `db_defects`, and the busy-machine
measurements. Per `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §9 the superseded result is preserved —
`analysis/field_verdicts.json` is **not** overwritten, and the re-emitted verdicts live beside it
in **`analysis/field_verdicts_gateE.json`**.

## 1. What arrived, and how I checked it rather than trusting it

EXP-0210 ran a serialized quiet window on an idle device. Two things had to be true before any of
it could count as *this* experiment's confirmation, and both were verified from the captures
themselves:

| check | result |
|---|---|
| Ran **this experiment's frozen arms** | `arms_sha256 = 80b13594…de789d5` in both `env.json`s — **identical to `CAPTURE_CONTRACT.json`** |
| Ran **this experiment's pinned tokenizer/db** | `pinned_db_sha256 = 2412eac1…c7c6c4`, `pinned_isadb_sha256 = 500db91a…75aa9f` — both match the contract |
| Same harness build | `harness_sha256_16 = acb962471af37ad4` in both runs |
| Case count | **5831 sweep lines each**, identical to my own `a_run01` |
| Gate A ledger | **5634 of 5634 cases per run carry a ledger, 0 mismatches** (11,268 total) |
| Gate E order requirement | `run_order` is **`forward` in `g17p_quiet01` and `reverse` in `g17p_quiet02`** — verified from the records, not from the run id |

The captures are in this experiment's own `raw/g17p_quiet01` and `raw/g17p_quiet02`; EXP-0210's
`raw/e0201_q01|q02` hold its independent concurrency instrument. **Every number below is re-derived
from raw by `analysis/verdicts.py`'s own functions**, not copied from EXP-0210's summary.

## 2. My own quiet gate was broken, and it would have refused this window

`verdicts.quiet()` prints `dis=0, agree=100.00%` for all six fields and still concludes
**CONTAMINATED**, on **1 sample of 273** in `g17p_quiet02` holding a single `MTLCompilerService` at
**0.0 % CPU**. I reproduced that before fixing anything.

**The defect is structural, and it is the mirror of one this corpus already documents.**
`MTLCompilerService` is an **XPC service**: launchd spawns it, so it is *never* a descendant of the
sampler's process tree, and `gpuwatch.own_pids()` — which attributes by ppid — can **never** mark it
"ours". Meanwhile `run.py` compiles 21 carriers per run through `shdump`, so our own run
**necessarily** causes compiler-service processes to exist while it samples. The check could
therefore only ever move toward CONTAMINATED. Elsewhere in this corpus the recurring bug is a gate
that cannot doubt; this is a gate that cannot acquit. Same error, opposite sign.

**The correction is explicit, named, and scoped** — `verdicts.quiet_v2()`, AMENDMENT B. It counts
as contamination:

* any foreign **GPU dispatch runner** (`agxrun*`, `gfrun*`, `rendersweep`, `agxrender`,
  `renderpersist`) — the device-reset mechanism `FIELD-SWEEP-PROTOCOL.md` §7 names; and
* any foreign **`shdump`** — not because compiling perturbs the GPU, but because it is positive
  evidence another agent is active.

It does **not** count `MTLCompilerService`, on the stated ground above. **This is a loosening and it
is recorded as one.** `quiet_v1_strict` is still computed and reported on every run, and it is in
`field_verdicts_gateE.json` → `_meta` so a reviewer can apply either model.

| run | samples | any foreign | foreign **dispatch** | foreign `shdump` | unattributable XPC | v1 strict | **v2** |
|---|---:|---:|---:|---:|---:|---|---|
| `g17p_quiet01` | 273 | 0 | **0** | 0 | 0 | QUIET | **QUIET** |
| `g17p_quiet02` | 273 | 1 | **0** | 0 | 1 | *busy* | **QUIET** |

Corroborated by an instrument I did not write and that reads counters mine does not:
EXP-0210's `quietcheck.json` reports `max_foreign_runner 0`,
`max_foreign_legacy_incl_compiler_svc 0`, `busy_count 0`, `renderer_util 0`,
`Q2a_no_foreign_reset true`, over 274 samples spanning 554 s per run. It is cited as corroboration,
**not substituted** for my own measurement.

*One thing worth flagging back:* EXP-0210's own `Q2_recovery_stable` is **false** — the GPU
recovery counter advanced by **1065** during each of my two runs. `Q2a_no_foreign_reset` is true, so
these are not a sibling's resets; the most economical reading is that they are **mine**, caused by
the 355 contained faults my own sweep dispatches (§3). That is expected for this experiment and is
not contamination, but a quiet-window instrument that treats recovery-counter movement as a red flag
will trip on any fault-heavy sweep.

## 3. A quiet GPU fails harder — and it corrects one of my own claims

Re-derived from my raw over the 5272 target cases per run:

| | busy `a_run01` | busy `a_run02` | quiet `q01` | quiet `q02` |
|---|---:|---:|---:|---:|
| `ok` | 86 | 86 | **86** | **86** |
| `wrong_value` | 3896 | 3896 | 3861 | 3861 |
| `silent_zero` | 809 | 810 | 810 | 810 |
| `not_written` | 444 | 449 | **160** | **160** |
| `fault` | 37 | 31 | **355** | **355** |

**The ok/not-ok partition is unchanged: 0 differences over 5272 cases, in both orders.** `ok = 86`
in all four runs. What moves is *severity*: ~289 cases that reported `STATUS OK` and wrote nothing
on a busy machine report a **contained command-buffer fault** on an idle one.

The sharpest instance, and it **corrects `RESULTS.md` §2.2**: on `f3_fma#0`, the class
`(v & 7) == 7` was **32/32 `not_written`** on the busy pair and is **32/32 `fault`** on the quiet
pair, with the other 224 values byte-identical (140 `wrong_value`, 68 `silent_zero`, 16 `ok`).
`f3e_sat#0` behaves the same way: 8 fault + 24 not_written busy → **32/32 fault** quiet.

So `RESULTS.md` §2.1's adjudication was **right about the substance and wrong about which side was
the artefact**. I argued the fault ⟷ wrote-nothing flips were noise around a stable "produced no
result". They were — but the *busy* machine was the one mislabelling: it **masked contained faults
as OK-but-wrote-nothing**. The quiet device settles it: `(v & 7) == 7` is a **fault**, not a silent
no-op. For an emitter that is a materially different statement, and it is the stronger one.

**Every fault-class claim in this experiment is therefore scoped to the machine state it was
measured on**, and the labels say so. Accept sets are not so scoped: they are identical on both.

## 4. Re-emitted verdicts

Written to **`analysis/field_verdicts_gateE.json`**. Cross-run figures are over the quiet pair,
forward vs reversed, re-derived from raw.

| field | label | predictor confirmed | moved | disagree | agreement | gate |
|---|---|---|---:|---:|---|---|
| `falu3.op` | **`hardware-run`** | **48 of 256** | 88 | **0** | **100.0000 %** | PROMOTE |
| `falu3_ext.op` | **`hardware-run`** | **40 of 256** | 88 | **0** | **100.0000 %** | PROMOTE |
| `copysign.operands` | **`hardware-run`** | 4/4 accept **+ 128/128 inert-bit pairs** | 252 | **0** | **100.0000 %** | PROMOTE |
| `falu3_srcmod12.opsel` | `isolated-byte-diff` | 1 of 4 encodable | 2 | **0** | **100.0000 %** | PROMOTE (label held back, §5) |
| `falu3_srcmod12.ctrl` | `isolated-byte-diff` | 1 of 128 | 31 | **0** | **100.0000 %** | PROMOTE (label held back, §5) |
| `fspecial_est.srcA` | **`untested`** | 2 of 256, equivalence **refuted** at 1 pair | 1 | 0 | 100.0000 % | **NOT PROMOTED — gate B** |

### Why each label, under corrections §2

`hardware-run` requires semantic checks against an independent predictor **over the stated range**,
so every range below is the value set where the **pre-registered** predictor was confirmed **in both
quiet runs** (`analysis/sem_coverage.py`), never the dispatched domain, which is wider.

* **`falu3.op` — 48 of 256.** 16 values with `(v & 0xC0) == 0` and `(v & 7) ∈ {4,6}` compute `-b`
  and `a*b+c` bit-exactly; 32 values with `(v & 7) == 7` are contained faults, which the model
  predicted. The predictor was **refuted on 176** — including class 5, where it said "constant zero"
  and the hardware computes `0.0 * b`. DEF-0201-2's better model is a *post-hoc* hypothesis
  supported by adversarial confirmation on two input sets; it is **not** counted as pre-registered
  semantic confirmation. Outside the 48: `live; role unknown`.
* **`falu3_ext.op` — 40 of 256.** 8 values `(v & 0xC7) == 0x06` compute the saturating `a*b+c`
  bit-exactly; 32 fault-class values confirmed. Refuted on 184.
* **`copysign.operands` — the full range, in the form the model committed to.** The accept rule
  `(v & 0x7E) == 0x00` holds 4/4, all 252 other values fail as predicted, and the inert-bit
  equivalence `f(v) == f(v ^ 0x81)` holds **128/128 pairs on three arms in both quiet runs with zero
  violations**. That is a per-value prediction confirmed across all 256 values, which is why this is
  `hardware-run` and not `live; role unknown`. **The label licenses exactly one thing: emit `0x00`,
  `0x01`, `0x80` or `0x81`.** It licenses no inference about *which* operand or register the byte
  names — DEF-0201-3 shows the operand **role** is not in this byte at all, since two carriers
  differing only in role compile to byte-identical instructions. The semantics axis carries that
  split verbatim; **if the merge prefers a single axis value, `live; role unknown` is the honest
  reading of the role and nothing here contradicts it.**
* **`falu3_srcmod12.opsel` / `.ctrl` — `isolated-byte-diff`, deliberately below what my gate allows.**
  The mechanical gate returns PROMOTE for both, but the predictor was confirmed at **one point each**
  (`v = 6` and `v = 0x03`). One confirmed point with a swept-but-unpredicted remainder is
  `isolated-byte-diff`, not `hardware-run`. For `opsel` the load-bearing result is geometric anyway:
  **DEF-0201-1**, the field span overlaps its own `match` bit 17, so the encodable range is **4
  values `{2,3,6,7}`, not 8**.
* **`fspecial_est.srcA` — unchanged at `untested`.** Gate E was never its blocker. **Gate B fails on
  all five arms** and still does on the quiet pair: every positive control and every falsifier is
  dead. New from the quiet pair: the inert-bit equivalence `f(v) == f(v ^ 0x80)` is **refuted at
  exactly one pair** — the `0x81` effect — which independently corroborates that finding while
  leaving the field carrier-undecidable. Safe wording stands: *inert in this exact tested envelope;
  global role unknown.*

## 5. What has not changed

* **No hypothesis, arm, oracle, carrier or coverage was altered.** The quiet pair is my frozen
  harness, re-run.
* **Gate D is still not attempted.** `compiler_recipe: not-generated` for all six; `copysign`
  reaches `generated-point` only, and DEF-0201-3 says a canonical recipe must first explain how
  operand roles are established.
* **The three `db_defects` and the two observations are carried forward verbatim** into
  `field_verdicts_gateE.json`.
* `RESULTS.md`, `PRE_REGISTRATION.md`, `PRE_REGISTRATION-A.md` and `analysis/field_verdicts.json`
  are unmodified except for this addendum being referenced.

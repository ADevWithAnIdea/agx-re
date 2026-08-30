# EXP-0210 — RESULTS

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6 build 25G5043d, `Mac17,5`, Metal family Apple9, `192.168.170.254`). Every capture
below ran on **G17P**, from the source experiment's **own committed harness**, with only the
run id changed.

```text
Clean-room provenance: HW-PROBE (re-running our own committed harnesses) + black-box IOKit
                       property reads for the quiet measurement
Inputs inspected:      this repository's own committed harnesses, kernels and raw; IOKit
                       registry PROPERTY VALUES published by the driver (data, not code)
Apple binary introspection: NONE
```

---

## 0. Headline

*(filled in at the end — see §9)*

---

## 1. What "quiet" measured, and how it differs from the fan-out's measurement

The 2026-08-30 wave measured occupancy by process name and recorded, unanimously, that it
never had a quiet machine — EXP-0204's dedicated helper sampled **86 times without ever
seeing a quiet sample**, peak **17** concurrent foreign GPU processes. This experiment adds
two hardware-side signals to that same process-name metric, because
`FIELD-SWEEP-PROTOCOL` §7 records that *"`InnocentVictim` is not the only contamination
signature"* and that *"a contaminated dispatch can report `STATUS OK` and write nothing"*:

- **`recoveryCount`** — the `AGXAcceleratorG17P` cumulative **device-reset** counter. A reset
  is the event that discards other contexts' in-flight command buffers. Sampling its delta
  turns "was anyone resetting the GPU" from an inference into a reading.
- **`fLastSubmissionPID` / `fBusyCount`** — who last submitted, and whether the device is
  busy, independent of process names. A foreign submitter with an unfamiliar name is
  invisible to a name-matching sampler and visible here.

Reading IOKit registry **properties** is black-box data observation. No Apple binary was
disassembled, decompiled or introspected.

### 1.1 The instrument corrected itself twice, and once against its own author

Three amendments, each **frozen before the dispatch that used it**, each with the superseded
captures **retained and explicitly not re-scored**:

| | trigger | change |
|---|---|---|
| **A01** | `e0203_q41` scored 2 foreign processes: they were **our own** `MTLCompilerService` XPC helpers, whose parent is launchd, so a `ppid` walk cannot see them as ours | split `n_foreign_runner` (gating) from `n_compiler_svc` (reported) |
| **A02** | `e0205_q02` scored 1 foreign runner in 1 of 18 samples: a `(shdump)` **zombie**, ours, misattributed by a race between two separate `ps` calls | one `ps` snapshot for both the ownership walk and the row scan; ownership = ppid subtree **∪ session id** |
| **A03** | `e0202_q01` measured **775 device resets** with zero foreign runners and no foreign submitter — **we were resetting the device ourselves**, from EXP-0202's own pre-registered faulting encodings | Q2 as frozen is a gate **no fault-heavy experiment can ever pass**; split into Q2a (no reset attributable to a *foreign* context) and Q2b (delta reported; cascade tested in the pair's raw) |

A03 is a defect in my **own** frozen criterion, and it is the same failure class this corpus
keeps rediscovering — a check that cannot come out the other way (DEF-0190-1's inertness
verdict that cannot fail; the `moved >= 2*max(disagree,1)` trap that cannot promote a width-1
field). It is recorded as a refutation of my own pre-registered H1, not as a technicality.

### 1.2 The measured quiet windows

Every capture, with its own samples. `n_foreign_runner` is the fan-out's own metric,
recomputed; compare it with the 9-median/17-peak the wave recorded.

| capture | run id (new) | samples | span s | max foreign runners | recoveryCount first→last | submitters (Q3) | verdict |
|---|---|---:|---:|---:|---|---|---|
| `e0203_q43` | `EXP-0203/raw/g17p_q43` fwd | 36 | 71.1 | **0** | 12977 → 12977 | 328 idle + ours | **QUIET** |
| `e0203_q44` | `EXP-0203/raw/g17p_q44` rev | 36 | 71.1 | **0** | 12977 → 12977 | ours only | **QUIET** |
| `e0205_q03` | `EXP-0205/raw/g17p_quiet03` fwd | 18 | 34.6 | **0** | 12977 → 12977 | 328 idle + ours | **QUIET** |
| `e0205_q04` | `EXP-0205/raw/g17p_quiet04` rev | 18 | 34.5 | **0** | 12977 → 12977 | ours only | **QUIET** |
| `e0202_q01` | `EXP-0202/raw/g17p_quiet01` fwd | 401 | 811.5 | **0** | 12977 → **15096** | 328 idle + ours | **refuted by frozen Q2 — retained, supports no verdict** |

`analysis/q3_check.py` adjudicates every observed `fLastSubmissionPID` against that same
capture's own process rows: **0 foreign submitters in any capture**. The residual categories
are `idle_328_SecurityAgent` (the login-window process that was the GPU's last submitter on
the idle machine, and submits nothing while we run), `stale_ours_previous_capture`
(`fLastSubmissionPID` is a *last* value, so the first samples of a capture can still name our
own preceding capture's runner), and `absent_from_rows` (one of our own runners that lived
and died between two 2-second samples).

**Superseded captures, retained exactly as taken, cited by no verdict:**
`e0203_q41`/`q42` (A01), `e0205_q01`/`q02` + `EXP-0205/raw/g17p_quiet01`/`quiet02` (A02),
`e0202_q01` + `EXP-0202/raw/g17p_quiet01` (A03).

### 1.3 One operational fact worth carrying forward: a quiet machine is SLOWER

Per-dispatch GPU time, EXP-0202, `status == OK` cases only, same 9857 cases:

| run | median `gputime_ns` | mean | p90 |
|---|---:|---:|---:|
| `g17p_quiet01` (quiet) | **1874** | **3265** | **5375** |
| committed `run03` (busy) | 1500 | 1552 | 1750 |
| committed `run04` (busy) | 1500 | 1561 | 1750 |

An idle GPU sits in a low power state, so a serialized confirmation run is *slower* and much
more variable than the same sweep on a loaded machine. This is why `gputime_ns` must be
excluded from any cross-run agreement key — it is not merely noisy, it moves **systematically**
with machine occupancy, which is exactly the variable a confirmation changes. The
pooled-`gputime_ns` key that `wave_audit.py` used before its 2026-08-30 fix would therefore
have reported a *lower* agreement precisely because the machine got quieter.

---

## 2. EXP-0203 — `half_alu_fma12.dst`, `half_pack.dstlo`, `half_pack.b3`: **Gate E MET**

**Pair:** `raw/g17p_q43` (forward) / `raw/g17p_q44` (reverse), both measured QUIET, from
`harness/run.py --mode gated --order {forward,reverse}`, unchanged. `verify_remote.py`
exit 0, **19/19 blobs match the frozen contract**.

| | |
|---|---|
| dispatched | 8410 cases each |
| frozen matrix sha256 | `e8325420acc469…` — identical in both runs and in the committed `run31`/`run32` |
| **actual-byte ledger, pair** | **8410 / 8410 keys with byte-identical `actual_instr`**; `bytes_match` true 8410/8410 in **both** runs; `requested == decoded` **8256 / 8256** in both (the other 154 are instrument cases carrying no field value) |
| distinct actual encodings / arm | `F12_DST_*` 28 each · `HP_*` 513 each · `F12_EXT_*` 2053 each — unchanged from the committed runs |
| **cross-run agreement, keyed (arm, field, value, byte_index), volatile timing excluded** | **8410 / 8410 = 100.0000 %**, 0 hard flips, 0 soft disagreements |
| faults / hangs / `InnocentVictim` / measurement failures | **0 / 0 / 0 / 0** |
| own `analysis/verdicts.py` on the quiet pair | `half_alu_fma12.dst` moved 40, disagree 0, covered 16/16 · `half_pack.dstlo` moved 1016, disagree 0, covered 256/256 · `half_pack.b3` moved 1016, disagree 0, covered 256/256 — identical to the committed verdicts |

**What the quiet window changed.** Outcome counters, all four quiet captures (`q41`, `q42`,
`q43`, `q44`): `ok` 2152, `wrong_value` 6258, **0 faults, 0 hangs** — byte-identical. The
committed busy pair was **not** identical to itself: `run31` recorded **1 fault** and `run32`
recorded `ok` 3550 / `wrong_value` 4860, an inflation of ~1398 cases that EXP-0203's own
RESULTS §6 traced to an `InnocentVictim` on an arm anchor plus a `classify()` defect that
returns `ok` when the anchor is lost. **On the quiet machine that anchor is never lost and
the inflation does not occur.** The quiet pair therefore does not merely repeat the busy
pair's verdict; it removes the contamination the busy pair had to argue around.

**Gate E: MET** for all three fields — two clean runs in **reversed** case order, identical
actual-byte ledgers, no victim/cascade evidence, on a **measured-quiet** machine.
Gate E's extra clause ("for load-bearing inertness or a surprising semantic claim, a
genuinely different carrier or second method") does not bind here: none of the three is an
inertness claim, and each already runs on four arms with two disjoint readback plans.

**Not changed by this experiment:** `half_alu_fma12.ext` stays `untested` (2048 sampled of
2⁶⁴); Gate D stays `generated-point`; `emit_unsafe` stays on `half_alu_fma12`; the fp16
special-value gap (0 subnormal, 0 overflowing predictions) is untouched.

---

## 3. EXP-0205 — `simd_reduce.op`, `simd_reduce.dtype`, `simd_shuffle.dir`, `simd_shuffle.cache`: **Gate E MET**

**Pair:** `raw/g17p_quiet03` (forward) / `raw/g17p_quiet04` (`--reverse`), both measured
QUIET, from `run.py` with the committed `harness/arms205.json` (revision B, sha
`0b7742a879…`, the same arms hash recorded in the committed `runB01`/`runB02`).

| | |
|---|---|
| dispatched | 5245 records each (5092 field cases + 153 instrument/probe records) |
| **actual-byte ledger, pair** | **5245 / 5245 keys byte-identical**; `requested == decoded` **5092 / 5092** in both runs, and in both committed runs |
| **cross-run agreement, keyed (arm, field, value, carrier)** | **5233 / 5233 = 100.0000 %**, 0 hard flips, 0 soft disagreements; 12 cases hard in **both** runs (the same 12 keys, all `not_written` on `dst` *control* arms, not fields under test) |
| faults / hangs / `InnocentVictim` | **0 / 0 / 0** |

**What the quiet window changed, exactly.** The committed busy `runB01` carries **1 fault**
that `runB02` does not, on `sr_scan#simd_reduce.dtype` value 216, which EXP-0205 §7 scored as
*"contamination from a sibling experiment, not a hardware fault"* and declined to claim.
Comparing the quiet forward run against that committed busy run:

> `g17p_quiet03` vs committed `g17p_20260830_runB01`: **5245/5245 actual bytes identical**,
> agreement **5232 / 5233**, and the **single** disagreement is exactly that case — clean
> (`unpredicted`) on the quiet machine, `fault` on the busy one.

EXP-0205's inference is now a measurement. Its own `analysis/verdicts.py`, run unedited over
the quiet pair, reproduces **every committed verdict string** with one numeric improvement:

| field | committed (busy pair) | quiet pair |
|---|---|---|
| `simd_reduce.op` | moved 896/1024, disagree 0, faults+hangs 0, min agreement 100.000 %, ledger 2048/2048 | **identical** |
| `simd_reduce.dtype` | moved **847**/1024, disagree **1**, faults+hangs **1**, min agreement **99.609 %** | moved **848**, disagree **0**, faults+hangs **0**, min agreement **100.000 %** |
| `simd_shuffle.dir` | moved 5/10, disagree 0, sem 6/6, ledger 20/20 | **identical** |
| `simd_shuffle.cache` | moved 3/10, disagree 0, sem 7/10, ledger 20/20 | **identical** |

**Gate E: MET** for all four fields.

**An auditability defect found in EXP-0205 while re-running it, reported not fixed.** Its
`CAPTURE_CONTRACT.json` pins `harness/carriers205.py` at `97f90f51c8…`, which is also the
`carriers_sha256` its committed `runB01`/`runB02` recorded — but the **committed** file is
`924fa4ee6e…`. The file was edited after those runs and never re-frozen, so
`harness/verify_remote.py` **refuses** (21/25, three of the four mismatches are analysis
scripts, which §4 explicitly allows to change). The captures here therefore ran the
**committed** harness, verified `repo == neo` **44/44 blobs** by
`EXP-0210/harness/verify_repo_eq_neo.py`. The edit is immaterial to dispatch — the quiet run
produced **byte-identical actual instruction bytes on all 5245 keys** of the committed run —
but the contract should be re-frozen so the experiment can verify itself. I did not touch it.

## 4. EXP-0202 — `irotate.operands`, `ibitcount.cache`, `ibitcount.dst`, `cvt_f2i._instruction`

**Three captures, and only the last two are the pair.**

| capture | run id | order | result |
|---|---|---|---|
| `e0202_q01` | `g17p_quiet01` | forward | 10596 records, 807.7 s. Q1 = 0 foreign runners, Q3 = no foreign submitter — but **`recoveryCount` 12977 → 15096, +2119**. Frozen refuter **R1 fires**. Retained, never reused, **supports no verdict**; it is what forced AMENDMENT-03. |
| `e0202_q03` | `g17p_quiet03` | forward | 10596 records, 803.4 s, 397 samples. **QUIET** under A03 (Q1 0, Q2a pass, Q3 no foreign submitter, Q4 ok). Q2b **+2118**, all ours. |
| `e0202_q04` | `g17p_quiet04` | reverse | *(see table below)* |

### 4.1 The device-reset finding, which is the most useful thing this capture produced

> **A single EXP-0202 capture resets the G17P about 2100 times in roughly 13 minutes**, on an
> otherwise idle machine, deterministically: `g17p_quiet01` +2119 and `g17p_quiet03` +2118.

Those resets come from EXP-0202's own pre-registered fault regions — `ibitcount.dst` 192..255
and `irotate` byte+3 192..255, the two mapped hazard walls, plus the `(v & 7) == 7` class. The
fault counts are byte-for-byte reproducible: comparing the quiet forward capture against the
**committed busy** `run03`, the hard-outcome tallies are **exactly equal** — 706 `fault`,
2 `invalid_run`, 196 `not_written` in each — with **10590/10590 actual bytes identical** and
**9686/9686 = 100.00 %** payload agreement.

Two consequences, both worth carrying forward:

1. **EXP-0202's faults are hardware, not contamination.** They reproduce identically with no
   other GPU client on the machine.
2. **This family of sweeps is, by itself, a large reset source for everyone else.** Every
   device reset discards in-flight command buffers in other contexts — the documented
   mechanism behind `kIOGPUCommandBufferCallbackErrorInnocentVictim`. `recoveryCount` was not
   sampled during the 2026-08-30 fan-out, so this cannot be attributed retrospectively; but
   ~2100 resets per capture is a concrete reason the concurrent wave saw victim streaks, and
   a concrete reason to keep this experiment off a shared machine.

### 4.2 The pair, and one field that does not pass

| | `e0202_q03` / `g17p_quiet03` (forward) | `e0202_q04` / `g17p_quiet04` (reverse) |
|---|---|---|
| quiet verdict (A03) | **QUIET** | **QUIET** |
| max foreign dispatch runners | 0 of 397 samples | 0 of 397 samples |
| `recoveryCount` delta | +2118 (**ours**) | +2118 (**ours**) |
| foreign submitters (Q3) | none | none |
| records | 10596 | 10596 |
| duration | 803.4 s | 803.4 s |

**Ledger: 10590 / 10590 keys byte-identical**, 0 ledger differences on any field. Six keys are
duplicated (`cvt_f2i` `mode = 0` *control* records, present twice per arm); they are compared
as multisets, not first-record-wins.

**`InnocentVictim`, like for like:** committed busy `run03` **167**, `run04` **160**; quiet
`quiet03` **0**, `quiet04` **0**. `fault` (706) and `invalid_run` (2) are **identical in all
four runs** — this experiment's fault regions are deterministic hardware behaviour, not
contamination.

Per field, keyed (arm, field, value, carrier, instr), volatile timing and container hashes
excluded:

| field owed | comparable | agree | disagree | both-hard (counted separately) | ledger diffs | **Gate E** |
|---|---:|---:|---:|---:|---:|---|
| `irotate.operands` | 3054 | 3054 | 0 | 158 | 0 | **MET** |
| `ibitcount.dst` | 958 | 958 | 0 | 322 | 0 | **MET** |
| `cvt_f2i._instruction` (`b9` 1536 · `dst` 96 · `mode` 90 · `signflag` 256 · `_baseline` 401) | 2379 | 2379 | 0 | 0 | 0 | **MET** |
| **`ibitcount.cache`** | **20** | **19** | **1** | 0 | 0 | **NOT MET** |

**The one failure, in full.** Arm `PC/pc_two#0/cache`, value 0:

```
quiet03 (fwd)  wrong_value  vals_u32 = [68, 193, 464, 962, 2015, 4064, 8130, 16321]
quiet04 (rev)  wrong_value  vals_u32 = [4, 1, 16, 2, 31, 32, 2, 1]
quiet01 (fwd)  wrong_value  vals_u32 = [68, 193, 464, 962, 2015, 4064, 8130, 16321]
run03  (busy)  wrong_value  vals_u32 = [68, 193, 464, 962, 2015, 4064, 8130, 16321]
run04  (busy)  wrong_value  vals_u32 = [68, 193, 464, 962, 2015, 4064, 8130, 16321]
```

Both sides are `status OK` with the integrity sentinel written, no fault, no victim, and
byte-identical dispatched instruction bytes. Four of five captures agree; the **reverse-order
quiet** one does not. That is the signature of an **order- or state-dependent** result, not of
contamination — and note that the committed *busy* pair agreed here, so the quiet window made
this row look **worse**, not better. `ibitcount.cache` is a 1-bit field with 2 values on 10
arms, so a single case is 5 % of it.

**This is reported as a failure, not adjudicated away.** `PRE_REGISTRATION.md` §2 refuter R1
names exactly this: a cross-run disagreement that is not confined to a hard-outcome class.
`pc_two` is EXP-0202's two-occurrence carrier and its own note records that `cache` is
**asymmetric** — value 1 universally safe, value 0 context-dependent. The successor this asks
for is an isolated repeat of that single arm at both values under both orders, with the
preceding case pinned, which this experiment did not run.

### 4.3 EXP-0202's own gate on the quiet pair

Its `analysis/verdicts.py`, run unedited, reproduces **every one of its committed verdict
strings and axes** for the four owed rows. Its own quiet gate reads `{"A": false, "B": true}` —
and the reason A reads false is worth passing on, because it is the **same defect this
experiment's AMENDMENT-02 fixed in its own instrument**: 1 of 396 samples caught a process
named `(agxrun_persist)`, `etime 00:00`, `ppid 28834` — an **exiting** child of EXP-0202's own
`run2.py`. Its filter is `'agxrun' in comm and 'EXP-0202' not in comm`, and a zombie's comm is
the bare parenthesised name rather than the full path, so it classifies its own dying child as
foreign. For contrast the same gate reads the committed busy pair as **201/201** and
**209/209** samples carrying genuinely foreign `EXP-0200` and `EXP-0206` runners.

Also worth flagging, since it will mislead a reader: `_cross_run`, `_contamination` and
`innocent_victim_cases` in `field_verdicts.json` are **hardcoded prose about run03/run04**, not
recomputed from the runs actually passed in. They still say "run03 167, run04 160" when the
tool is pointed at the quiet pair.

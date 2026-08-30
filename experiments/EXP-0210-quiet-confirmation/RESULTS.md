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

**Gate E is now MET for 17 of the 22 named fields this experiment was asked to confirm**, on a
machine whose quietness is a measurement rather than a claim: **zero foreign GPU dispatch
runners in every sample of every scoring capture**, against the fan-out's median of 9 and peak
of **17**.

- **MET outright:** EXP-0203 (`half_alu_fma12.dst`, `half_pack.dstlo`, `half_pack.b3`),
  EXP-0205 (`simd_reduce.op`, `simd_reduce.dtype`, `simd_shuffle.dir`, `simd_shuffle.cache`),
  EXP-0201 (all five), EXP-0202 (`irotate.operands`, `ibitcount.dst`, `cvt_f2i._instruction`).
- **MET, bounded:** EXP-0199 (`frag_depth_store._instruction`, `sfu_marker._instruction`) —
  every residual cross-run disagreement is a fault⟷clean flip; 100.00 % on valid payloads.
- **MET from its own committed raw, re-derived:** EXP-0206's `run05`/`run07` pair really was
  quiet (every "foreign" process its own sampler counted was EXP-0206's own).
- **NOT MET:** `ibitcount.cache` — one measured disagreement, named exactly (§4.2); and all
  four EXP-0204 fields — both of its captures were stopped early by **its own** cascade guard
  and hang budget (§7).
- **NOT REACHED:** EXP-0206's `cf_nl2` / `cl_atomic` / `cl_leaf` / `cl_chain` arms — on a quiet
  machine those encodings **hang** where they faulted, and the sweep rate collapses from
  ~4.8 to ~0.2 cases/s (§8.2).

**Three results the quiet window produced that the busy wave could not:**

1. **`InnocentVictim` went to zero.** EXP-0202: 167 and 160 → **0 and 0**. EXP-0199: 4 and 16 →
   **0 and 0**. EXP-0205's single "probably contamination" fault is now measured as
   contamination: clean on the quiet machine, `fault` on the busy one, everything else in that
   run byte-identical.
2. **A quiet GPU fails harder** (§9). The same illegal encodings escalate from silent-no-write
   to contained fault (EXP-0201: 18 → 355) and from contained fault to **device hang**
   (EXP-0206), and EXP-0204's hang count goes 7/11 → 48/48. Every fault and hang label in the
   2026-08-30 wave was taken on a busy machine.
3. **A single EXP-0202 capture resets this device about 2100 times in 13 minutes** — a concrete
   reason the concurrent wave saw victim streaks, and a reason to keep that family off a
   shared machine.

**And one that should temper all of the above:** the wave's own quiet gates would have refused
this window. EXP-0201's `verdicts.py` reports `dis=0, agree=100.00%` on all six fields and
still prints `NOT PROMOTED — CONTAMINATED`, on the strength of **1 of 273** samples that caught
its own compiler helper (§5.2). Three independent instruments, mine included, had the same
bug.

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

Every capture, with its own samples. `max foreign runners` is the fan-out's own metric, recomputed; compare it with the median of 9 and peak of 17 the wave recorded. **Zero, in every sample of every capture.**

| capture | run id (new) | order | samples | span s | max foreign runners | recoveryCount delta (all ours) | verdict | ioreg errors |
|---|---|---|---:|---:|---:|---:|---|---:|
| `e0203_q43` | `EXP-0203/raw/g17p_q43` | forward | 36 | 71.1 | **0** | 0 | **QUIET** | 0 |
| `e0203_q44` | `EXP-0203/raw/g17p_q44` | reverse | 36 | 71.1 | **0** | 0 | **QUIET** | 0 |
| `e0205_q03` | `EXP-0205/raw/g17p_quiet03` | forward | 18 | 34.6 | **0** | 0 | **QUIET** | 0 |
| `e0205_q04` | `EXP-0205/raw/g17p_quiet04` | reverse | 18 | 34.5 | **0** | 0 | **QUIET** | 0 |
| `e0202_q03` | `EXP-0202/raw/g17p_quiet03` | forward | 397 | 803.4 | **0** | 2118 | **QUIET** | 0 |
| `e0202_q04` | `EXP-0202/raw/g17p_quiet04` | reverse | 397 | 803.4 | **0** | 2118 | **QUIET** | 0 |
| `e0201_q01` | `EXP-0201/raw/g17p_quiet01` | forward | 274 | 554.0 | **0** | 1065 | **QUIET** | 0 |
| `e0201_q02` | `EXP-0201/raw/g17p_quiet02` | reverse | 274 | 554.0 | **0** | 1065 | **QUIET** | 0 |
| `e0199_q01` | `EXP-0199/raw/g17p_quietconf01` | shuffle | 35 | 69.0 | **0** | 158 | **QUIET** | 0 |
| `e0199_q02` | `EXP-0199/raw/g17p_quietconf02` | reverse | 34 | 67.0 | **0** | 158 | **QUIET** | 0 |
| `e0204_c1` | `EXP-0204/raw/g17p_quiet_C1` | shuffle 11 | 12 | 22.5 | **0** | 7 | **QUIET** | 0 |
| `e0204_c2` | `EXP-0204/raw/g17p_quiet_C2` | reverse | 10 | 18.4 | **0** | 4 | **QUIET** | 0 |
| `e0204_d1` | `EXP-0204/raw/g17p_quiet_A2runD1` | forward | 56 | 113.5 | **0** | 144 | **QUIET** | 0 |
| `e0204_d2` | `EXP-0204/raw/g17p_quiet_A2runD2` | reverse | 56 | 113.5 | **0** | 144 | **QUIET** | 0 |
| `e0206_q01_PARTIAL` | `EXP-0206/raw/g17p_quiet01 (partial)` | forward | 122 | 245.5 | **0** | 0 | **QUIET** | 0 |
| `e0206_q02_PARTIAL` | `EXP-0206/raw/g17p_quiet02 (partial)` | forward | 110 | 221.1 | **0** | 57 | **QUIET** | 0 |

The `recoveryCount` deltas are all **our own** device resets, from each experiment's own pre-registered faulting encodings (`AMENDMENT-03`): Q1 = 0 foreign dispatch runners and Q3 = no foreign submitter in every sample means no other GPU client existed to cause one.

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

---

## 5. EXP-0201 — `falu3.op`, `falu3_ext.op`, `falu3_srcmod12.opsel`, `falu3_srcmod12.ctrl`, `copysign.operands`: **Gate E MET**

**Pair:** `raw/g17p_quiet01` (forward) / `raw/g17p_quiet02` (reverse), both measured QUIET, via
its own `harness/gated_run.sh`. This is the **only** one of the seven whose own
`verify_remote.py` exits 0: **23/23 blobs match its frozen contract**; `repo==neo` 34/34.

| | `e0201_q01` fwd | `e0201_q02` rev |
|---|---|---|
| quiet verdict | **QUIET** | **QUIET** |
| max foreign dispatch runners | 0 of 274 samples | 0 of 274 samples |
| `recoveryCount` delta | +1065 (ours) | +1065 (ours) |
| records | 5831 | 5831 |
| duration | 551 s | 554 s |

| | |
|---|---|
| **actual-byte ledger** | **5831 / 5831 keys byte-identical**; `requested == decoded` **5634 / 5634** in both |
| **agreement**, keyed (arm, field, value, carrier) | **5312 / 5312 = 100.0000 %**, 0 hard flips, 0 soft, 519 both-hard excluded |
| per owed field | `falu3.op` 896/896 · `falu3_ext.op` 992/992 · `falu3_srcmod12.opsel` 21/21 · `falu3_srcmod12.ctrl` 288/288 · `copysign.operands` 1280/1280 — **all 100.00 %**, 0 ledger differences |
| victims | 0 / 0 |

The committed **busy** pair (`a_run03`/`a_run04`) had **one** disagreement by the same measure
(`f3e_chain#0/falu3_ext.op` value 124, 99.9813 %). The quiet pair has none.

### 5.1 What the quiet window changed: a whole outcome class moved

| | `fault` | `not_written` |
|---|---:|---:|
| committed `a_run03` (busy, fwd) | 18 | 466 |
| committed `a_run04` (busy, rev) | **0** | 484 |
| quiet `g17p_quiet01` (fwd) | **355** | 164 |
| quiet `g17p_quiet02` (rev) | **355** | 164 |

The 355 faults sit at exactly the pre-registered `(v & 7) == 7` class — 32 values on each `op`
arm — and are **identical in both quiet runs and in both orders**. On the busy machine the
same encodings were mostly observed as a **silent no-write**, and the two busy runs did not
even agree with each other (18 vs 0). This does not touch the five field verdicts, because
hard outcomes are partitioned out of the payload set — but **EXP-0201's committed
hard-outcome accounting is not what a quiet machine produces.** See §8.

### 5.2 EXP-0201's own promotion gate still refuses — and the reason is an instrument bug

Run unedited on the quiet pair, `analysis/verdicts.py` prints

```
runs: g17p_quiet01(QUIET), g17p_quiet02(BUSY)
falu3.op   NOT PROMOTED  ... moved=92 dis=0 agree=100.00%
      - CONTAMINATED: quietness not established for a confirmation run
```

…for **all six** fields, every one of them at `dis=0, agree=100.00%`. The whole refusal rests
on **1 of 273 samples** in `g17p_quiet02`:

```
pid 35828  /Users/user/agxre/EXP-0201/work/bin/shdump          ours=true
pid 35829  .../MTLCompilerService.xpc/.../MTLCompilerService    ours=false
```

That is EXP-0201's **own** compiler XPC helper, spawned by its **own** `shdump`, one PID later,
and invisible to a `ppid` walk because launchd is its parent. It is precisely the case
`AMENDMENT-01` of this experiment identifies. EXP-0202's `quiet()` fails the same way on a
`(agxrun_persist)` **zombie** (`AMENDMENT-02`'s case), flagging 1 of 396 samples.

**Three independent instruments, built the same day, all misclassify their own helper
processes as foreign — and two of them gate a promotion on it.** The consequence matters more
than the bug: *the wave's own quiet gates would have refused a genuinely quiet window*, and a
reader of `field_verdicts.json` alone would conclude Gate E is still unmet when every
hardware-side signal says the machine had no other GPU client at all.

---

## 6. EXP-0199 — `frag_depth_store`, `sfu_marker`: **Gate E MET, with a stated bound**

**Pair:** `raw/g17p_quietconf01` (**shuffle**) / `raw/g17p_quietconf02` (**reverse**), both
measured QUIET, from `conf.py <run_id> <order>` unchanged. This experiment has no `sync.sh`;
the neo tree *is* its harness, verified byte-identical to the repo (`conf.py`, `run.py` 2/2;
`harness/{crun199.m,gfrun5.m,runner199.py}` == `harness2/*` 3/3).

| | |
|---|---|
| records | 6511 each, 65 s and 64 s, **`hangs={}` in both** |
| its own **Gate A** | **12932 ledger checks, 0 failures → PASS** |
| my ledger check | **6511 / 6511 actual bytes identical** |
| `InnocentVictim` strings | **0 and 0** (committed busy pair: **4** and **16**) |
| faults | **158 and 158** (committed busy pair: 154 and 174) |
| measurement failures | 0 |

**Before / after, on the same measure:**

| | committed busy `conf01`/`conf04` | quiet `quietconf01`/`quietconf02` |
|---|---|---|
| disagreements | **45** | **18** |
| agreement | 99.2925 % | **99.7168 %** |
| hard flips | 26 | 8 |

Per owed row:

| row | cases | disagreements | nature |
|---|---:|---:|---|
| `frag_depth_store` (`_baseline`, `_identity`, `_null`, `b3`, `b4`, `b5`, `byte1`, `byte2`) | 2306 | **3** (b5 2, byte1 1) | **all fault ⟷ clean hard flips** |
| `sfu_marker` (`_baseline`, `_identity`, `_insert2`, `match_byte0`, `match_byte1`) | 1033 | **2** (`match_byte1`) | **all fault ⟷ clean hard flips** |

With hard outcomes partitioned out — the corpus's own convention (EXP-0160's filter,
EXP-0201's lens) — both rows are **100.00 % on valid payloads**. Counted strictly, they are
2303/2306 and 1031/1033.

**`sfu_marker`'s headline reproduces exactly:** `_insert2` at all seven boundaries
(`@38,52,62,74,84,94,104`) is `ok`, moved 0, agreement 1.0 — **7 of 7**, as committed.
`frag_depth_store`'s bit rules reproduce exactly too: `b3` ok-set `(v & 0xfc) == 0x00` (4
values, exact), `b4` `(v & 0x1f) == 0x00` (8, exact), `b5` `(v & 0x02) == 0x02` (128, exact),
`byte1` `(v & 0x06) == 0x04` (64, exact), `byte2` inert over all 256.

**The bound.** The residual soft-disagreement block is `vary_store.out_slot`, 10 of 32 — but
that is EXP-0199's **Gate B positive control** for `vary_slot`, not an owed field, and its own
`gates.py` reports the same per-arm 0.625/0.875 agreement on the **committed** pair. It is
intrinsic to that control, not contamination, and it is unchanged by the quiet window.
`vary_slot` is not promoted by EXP-0199 anyway.

---

## 7. EXP-0204 — `tex_sample.mode`, `tex_write.amode`, `tex_write.rsv11`, `tex_deriv.dstsrc`: **Gate E NOT MET**

Run from EXP-0204's **own** `harness/quietconfirm.sh` recipe, verbatim except for the run ids:
`--mnem tex_sample,tex_write --order shuffle --seed 11 --deadline-s 900` and the same with
`--order reverse`; then the `tex_deriv` mapping pass at its frozen 8-hang budget in both
orders. `repo==neo` **36/36 blobs**. Its `CAPTURE_CONTRACT.json`'s latest freeze
(`source_hashes_at_amendment2`) matches 28/29, the one exception being `analysis/verdicts.py`.

All four captures measured **QUIET** (0 foreign dispatch runners, no foreign submitter). The
failure is not the machine.

### 7.1 `tex_sample` / `tex_write` — both captures were stopped by EXP-0204's own cascade guard

| | `g17p_quiet_C1` (shuffle 11) | `g17p_quiet_C2` (reverse) | committed `A2run01`/`A2run02` |
|---|---:|---:|---:|
| records | 9014 | **5242** | 9276 / 9276 |
| arm/field groups | 143 | **94** | 144 / 144 |
| elapsed | 22.5 s | 16.4 s | 137.7 s / 39.0 s |
| cascade aborts | `twdyn/1` truncated | **`[["tex_write@twdyn/0","amode",5240]]`** | none |

`C2`'s last record reads
`ARM STOPPED: unmutated carrier stopped reproducing its baseline on all 4 attempts`, and
`baseline_final_ok: false` for `tex_write@twdyn/0`. That is EXP-0204's own foreign-cascade
guard firing: **the unmutated carrier stopped reproducing its own baseline**, on a machine with
no other GPU client. `C1` hit the same thing one arm later (`twdyn/1`). Six whole `tex_write`
arms are therefore absent from `C2`.

Over the 5055 keys the two captures share:

| | |
|---|---|
| ledger | **5055 / 5055 actual bytes identical** (`requested == decoded` 8442/8442 in C1, 4858/4858 in C2) |
| agreement | 4873 / 5055 = **96.3996 %** — 2 hard flips, **180 soft** |
| `tex_write.amode` | 1274 / 1274 = **100.00 %** — but over ~5 arms, not the committed 12 |
| `tex_write.rsv11` | 1024 / 1024 = **100.00 %** — same caveat |
| `tex_sample.mode` | 2388 / 2560 = **93.28 %**, 172 soft disagreements across all 10 arms |
| faults / victims | 3 and 3 / 0 and 0 |

**Verdict: NOT MET for all three.** Gate E asks for two **clean** runs; these two aborted on
their own contamination guard, and the pair covers 5055 of 9276 keys. `tex_sample.mode`
additionally disagrees on 172 cases — the same order-dependent block EXP-0204 already reported
(it rested its bit rule only on the six arms that reached 256/256). And `amode`/`rsv11` are
**inertness** claims, for which Gate E requires *"a genuinely different carrier or second
method as well"* — not provided here, and now on **fewer** carriers than the committed run.

### 7.2 `tex_deriv.dstsrc` — the hang budget bites much harder on a quiet machine

| | `g17p_quiet_A2runD1` (fwd) | `g17p_quiet_A2runD2` (rev) | committed `A2run03` | committed `A2run04` |
|---|---:|---:|---:|---:|
| records | 468 | **246** | 156 | 122 |
| **hangs** | **48** | **48** | **7** | **11** |
| elapsed | 111.1 s | 110.6 s | 310.2 s | 188.5 s |

Over the 216 keys they share: **ledger identical 216/216**, agreement **168 / 168 = 100.00 %**,
48 cases hard in both, 0 disagreements, 0 victims. But 216 shared keys is far short of the
committed mapping pass's 65/65 values on both arms, because the frozen 8-hang-per-field budget
is exhausted **six times sooner** on a quiet machine.

**Verdict: NOT MET.** The pair is clean and agrees perfectly where it overlaps, and it is far
too small. `tex_deriv.dstsrc` also has `sem_checked = 0` by EXP-0204's own design, so Gate C
caps it at `live; role unknown` regardless.

**Confounder, disclosed.** These four captures ran after this session had already accumulated
about **22,000 device resets** (`recoveryCount` 12977 → 21778 before `C1` started), almost all
of them from EXP-0202's two sweeps. I cannot exclude that a heavily-reset device contributed
to `twdyn`'s baseline loss. A successor should take EXP-0204's pair **first** in a quiet
window, not last.

---

## 8. EXP-0206 — `run05`/`run07` already met Gate E; the rest is **NOT REACHED**, and the reason is a hardware measurement

### 8.1 The arms already covered: Gate E **MET**, re-derived from EXP-0206's own raw

The dispatch said to run "the arms NOT already covered by its quiet `run05`/`run07` pair". Before
running anything I checked that pair against my own criteria, from its **own committed**
`procs.jsonl`:

> Every process EXP-0206's sampler counted as "other" in `run05` and `run07` is **its own**
> `agxrun_persist` or its own `run.py`. **Zero foreign dispatch runners in either capture.**

| | |
|---|---|
| orders | `shuffled:206` vs `shuffled:407` — genuinely different |
| ledger | **1486 / 1486 actual bytes identical** |
| agreement | **1446 / 1446 = 100.0000 %**, 0 hard flips, 0 soft |
| hard outcomes | 28 `fault` + 12 `hang`, **the same 40 keys in both** |
| victims | 0 / 0 |

**Gate E is MET for the six arms those two captures cover** — `cf_nl3`, `cf_ifnl`, `cl_pure`,
`cl_ldret`, `cl_stacross` — including `pop_reconverge.reserved@cf_ifnl+184` and three of the
four `ret.scoreboard` ordering arms.

**One caveat EXP-0206 did not record:** `run07` spans **19:57:48 – 20:02:47Z**, so its last
~3 minutes fall **inside EXP-0204's declared 20:00–20:25 hang window**. EXP-0206 §1.3 checks
that window for `run03`, `run04` and `run05` and does not list `run07`. `recoveryCount` was not
sampled then, so a foreign reset in those three minutes cannot be excluded from the data.

### 8.2 The remaining arms: NOT REACHED, because on a quiet machine they hang instead of faulting

Two captures were taken and **deliberately stopped**, retained, never reused, never topped up:

| capture | carriers | quiet | records | outcome |
|---|---|---|---:|---|
| `raw/g17p_quiet01` | all nine, `--order forward` | **QUIET** (122 samples, 0 foreign) | **20** | stopped: 8 hangs in the first 16 cases |
| `raw/g17p_quiet02` | `cl_atomic,cl_leaf,cl_chain`, forward | **QUIET** (110 samples, 0 foreign) | **612** | stopped: 15 faults + **7 hangs**, rate collapsing |

The measurement, on `if_push.scope@cf_nl2._agc.main+106`, **same arm, same values**:

| value | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| committed `run03` (busy) | fault | fault | ok | ok | fault | fault | ok | ok | fault | fault | ok | ok | not_written | fault |
| quiet `g17p_quiet01` | **hang** | **hang** | ok | ok | **hang** | **hang** | ok | ok | **hang** | **hang** | ok | ok | **hang** | **hang** |

The `ok` set is identical — the bit rule is unchanged. What changes is the **severity of the
failure**: a contained fault on a loaded machine, a **device hang** on an idle one. And on
`cl_atomic`/`cl_leaf`/`cl_chain`, where the committed `run03` and `run04` recorded **601 faults
and ZERO hangs**, the quiet capture produced **7 hangs in its first 612 cases**.

Each hang costs a watchdog timeout, a device reset and a runner restart, so the sweep rate
fell from EXP-0206's committed **~4.8 cases/s** to about **0.2 cases/s**. A full quiet pair over
these four carriers would take several hours, and that is why it was not taken. Reported as
**NOT REACHED**, with the cost measured rather than guessed.

---

## 9. The cross-cutting hardware observation: a quiet GPU fails *harder*

Four independent observations, in three experiments, all in the same direction:

| experiment | same encodings, busy machine | same encodings, quiet machine |
|---|---|---|
| **EXP-0201** `(v & 7) == 7` class | `fault` **18** in `a_run03`, **0** in `a_run04`; the rest `not_written` (466 / 484) | `fault` **355** in *both* runs; `not_written` 164 / 164 |
| **EXP-0206** `if_push.scope@cf_nl2+106` | `fault` at v = 0,1,4,5,8,9,13,16… (126 of 256) | **`hang`** at the *same* values (9 of the first 17) |
| **EXP-0206** `cl_atomic`/`cl_leaf`/`cl_chain` | **601 faults, 0 hangs** over 2642 cases | **7 hangs** in the first 612 cases |
| **EXP-0204** `tex_deriv` mapping pass | **7** and **11** hangs | **48** and **48** hangs |

And one experiment that did **not** move, which is what keeps this from being a story about my
own instrument: **EXP-0202's hard outcomes are byte-identical busy and quiet** — 706 `fault`,
2 `invalid_run`, 196 `not_written` in *all four* of its captures.

**Observation.** For several illegal-encoding classes, the *ok/not-ok partition is unchanged*
— the bit rules reproduce exactly — but the **severity** of the not-ok outcome escalates when
the GPU is otherwise idle: silent-no-write → contained fault → device hang.

**Hypothesis, stated as one and not tested here.** On a loaded machine another context's error
recovery resets the device before *your* watchdog fires, so your stalled command buffer is
returned as a contained fault rather than reaching a hang. Two facts fit: EXP-0202's sweeps
alone reset this device about **2100 times per 13-minute capture**, so on 2026-08-30 a reset
was arriving constantly; and the effect appears in the experiments whose fault classes sit on
a stall boundary, not in EXP-0202, whose own faults are the resets. A second mechanism that
cannot be excluded is DVFS: an idle GPU is clocked down (measured, §1.3), which changes how
long the hardware stalls before a timeout.

**Why it matters.** Every `fault` / `hang` / `not_written` classification in the 2026-08-30
wave was taken on a busy machine. This experiment shows at least three of them are
load-dependent. The *field* verdicts are largely unaffected, because the corpus already
partitions hard outcomes out of the payload set — but any claim of the form "this encoding
faults" or "this encoding is safe to dispatch" should be re-taken quiet before it enters
`docs/`. It also sharpens `FIELD-SWEEP-PROTOCOL` §7's advice in an uncomfortable direction:
**running unlocked does not merely risk contamination, it can systematically understate how
badly an encoding fails.**

---

## 10. Gate E, per experiment and per field

Computed by `analysis/gate_e_summary.py` (whole-capture) and `analysis/per_field.py`
(per-field, which is the granularity below). "MET" means: both captures measured quiet,
opposite/shuffled case order, identical actual-byte ledgers, both runs complete, no
victim/cascade evidence, and no cross-run disagreement outside a hard-outcome class.

| experiment | field | Gate E | evidence |
|---|---|---|---|
| **EXP-0203** | `half_alu_fma12.dst` | **MET** | ledger 8410/8410 · agreement 8410/8410 = 100.0000 % · 0 faults/hangs/victims · moved 40, covered 16/16 |
| | `half_pack.dstlo` | **MET** | as above · moved 1016, covered 256/256 |
| | `half_pack.b3` | **MET** | as above · moved 1016, covered 256/256 |
| **EXP-0205** | `simd_reduce.op` | **MET** | ledger 5245/5245 · agreement 5233/5233 = 100.0000 % · moved 896/1024, ledger 2048/2048 |
| | `simd_reduce.dtype` | **MET** | as above · **moved 848 (was 847), disagree 0 (was 1), faults 0 (was 1), min agreement 100.000 % (was 99.609 %)** |
| | `simd_shuffle.dir` | **MET** | as above · moved 5/10, sem 6/6 |
| | `simd_shuffle.cache` | **MET** | as above · moved 3/10, sem 7/10 |
| **EXP-0202** | `irotate.operands` | **MET** | ledger 10590/10590 · 3054/3054 = 100.00 % · 158 both-hard |
| | `ibitcount.dst` | **MET** | 958/958 = 100.00 % · 322 both-hard |
| | `cvt_f2i._instruction` | **MET** | 2379/2379 = 100.00 % over `b9`+`dst`+`mode`+`signflag`+baselines |
| | **`ibitcount.cache`** | **NOT MET** | **19/20 = 95.0 %** — `PC/pc_two#0/cache` v=0 differs in the reverse-order quiet run alone (§4.2) |
| **EXP-0201** | `falu3.op` | **MET** | ledger 5831/5831 · 896/896 = 100.00 % |
| | `falu3_ext.op` | **MET** | 992/992 = 100.00 % |
| | `falu3_srcmod12.opsel` | **MET** | 21/21 = 100.00 % |
| | `falu3_srcmod12.ctrl` | **MET** | 288/288 = 100.00 % |
| | `copysign.operands` | **MET** | 1280/1280 = 100.00 % |
| **EXP-0199** | `frag_depth_store._instruction` | **MET, bounded** | its Gate A 12932/0 · ledger 6511/6511 · 2303/2306; **all 3 disagreements are fault⟷clean hard flips**, 100.00 % on valid payloads · victims 4+16 → **0+0** |
| | `sfu_marker._instruction` | **MET, bounded** | 1031/1033, both disagreements hard flips · **7 of 7 insertion boundaries `ok`** reproduced exactly |
| **EXP-0206** | `pop_reconverge.reserved`, `ret.scoreboard`, and the other `cf_nl3`/`cf_ifnl`/`cl_pure`/`cl_ldret`/`cl_stacross` arms | **MET** (from its **own** committed `run05`/`run07`) | zero foreign dispatch runners in either, re-derived from its own `procs.jsonl` · different shuffles · ledger 1486/1486 · 1446/1446 = 100.0000 % · same 40 hard keys. Caveat: `run07`'s last ~3 min overlap EXP-0204's 20:00–20:25 hang window |
| | the `cf_nl2` / `cl_atomic` / `cl_leaf` / `cl_chain` arms | **NOT REACHED** | on a quiet machine these encodings **hang** where they faulted; rate 4.8 → 0.2 cases/s; two partials retained (§8.2) |
| **EXP-0204** | `tex_sample.mode` | **NOT MET** | 2388/2560 = 93.28 %, 172 soft disagreements; both captures stopped by EXP-0204's own cascade guard |
| | `tex_write.amode` | **NOT MET** | 1274/1274 = 100 % but on ~5 of 12 arms; capture aborted; inertness needs a second method Gate E also asks for |
| | `tex_write.rsv11` | **NOT MET** | 1024/1024 = 100 % on a truncated arm set; same reasons |
| | `tex_deriv.dstsrc` | **NOT MET** | 168/168 = 100 % over only 216 shared keys; 48 hangs per capture exhausted the frozen budget six times sooner than on the busy machine |

**Totals over the 22 named fields: 17 MET — 15 outright (EXP-0203 3, EXP-0205 4, EXP-0201 5,
EXP-0202 3) and 2 bounded (EXP-0199) — 1 NOT MET on a measured disagreement
(`ibitcount.cache`), and 4 NOT MET on truncated captures (all of EXP-0204). Separately,
EXP-0206's `run05`/`run07` arms are MET from its own committed raw, and its remaining four
carriers are NOT REACHED.**

---

## 11. How this method could have failed to say "no"

1. **Agreement between two runs of the same program on the same machine is nearly guaranteed,
   so a high agreement number is weak evidence that quiet mattered.** The proof is inside this
   experiment: EXP-0202's *quiet* forward capture agrees with a *busy* committed capture
   **9686/9686 = 100.00 %**, with byte-identical hard-outcome counts. What actually moved when
   the machine went quiet was never the payload agreement — it was the **hard outcomes**
   (EXP-0203's 1398-case `ok` inflation from a lost anchor; EXP-0205's single sibling-induced
   fault). **If contamination had corrupted payloads rather than faults, my method would still
   have reported 100 % and I would have had no signal at all.** Everything here therefore
   establishes *"the confirmation was taken on a quiet machine"*; it does **not** establish
   *"quiet changed the answer"* except where a hard-outcome count changed, and those cases are
   named individually.

2. **The quiet metric samples at 2 s.** A foreign GPU client that starts, submits and exits
   between two samples is invisible to Q1 and to Q3. `recoveryCount` (Q2b) would catch it only
   if it caused a reset. The machine sat at the login screen with `SecurityAgent` as the last
   submitter, and the long EXP-0202 capture carried 401 samples, so the residual risk is small
   — but it is not zero, and it is a real hole rather than a hypothetical one.

3. **Cross-run agreement compares the `observed` payload only,** with timing stripped.
   Contamination expressed in a record field outside `observed`, or inside a stripped timing
   field, is invisible to it. Hard outcomes are counted separately and compared, which covers
   the failure mode the corpus has actually seen, but not every conceivable one.

4. **The pair key is not unique in every experiment.** EXP-0202 has **6** duplicate
   `(arm, field, value, carrier, instr, sub)` keys — all `cvt_f2i` `mode = 0` *control*
   records, present twice. The comparator compares the first record per key, so a disagreement
   confined to a duplicate would be masked. It is reported as `key_unique: false` in every
   comparison JSON rather than smoothed over.

5. **Reversing case order controls ordering artefacts, not carrier blind spots.** Two runs of
   the same harness on the same machine share every systematic error the harness has. Gate E's
   further clause — *"for load-bearing inertness or a surprising semantic claim, require a
   genuinely different carrier or second method as well"* — is **NOT satisfied by this
   experiment for any row**, and specifically not for the inert rows
   (`tex_write.amode`, `tex_write.rsv11`, EXP-0206's inert rows). This experiment can move
   those rows past the *quiet* clause and no further.

6. **All three amendments moved a criterion in the direction of "quiet".** Each was frozen
   before the dispatch that used it and each superseded capture is retained unrescored, but a
   reader should weigh that they all loosened or re-attributed a failing conjunct rather than
   tightening one. The strongest defence available is that A01 and A02 are demonstrable
   attribution bugs (an XPC parent, a two-`ps` race) and A03 is a gate that provably could not
   pass any fault-heavy experiment — but a reader who thinks I rationalised should look at
   `AMENDMENT-0{1,2,3}.md` and the retained captures and judge.

7. **Only Gate E was re-run.** Gates A, B, C and D are inherited from each source experiment
   unchanged and were **not** re-audited here. If one of those is wrong, a MET verdict from
   this experiment does not rescue it.

8. **`fLastSubmissionPID` is a *last* value,** so the first samples of a capture legitimately
   name the previous capture's runner, and one signal is degenerate on this host:
   `Device Utilization %` reads a constant 100 with an idle GPU, zero submitters and
   Renderer/Tiler at 0. Q3 is therefore weaker at the start of each capture than it looks, and
   the four-signal design is really a three-signal design.

9. **I did not kill the one orphan process on the machine** (EXP-0202's leftover `gpuwatch.py`
   sampler, PID 7480, ppid 1). It issues `ps` and does no GPU work, and it is disclosed in
   every sample — but it is a foreign process that ran throughout, and "the machine was
   completely idle" is therefore not literally true.

10. **The one that would embarrass me most.** My own frozen Q2 could not be satisfied by any
    fault-heavy experiment, and I only discovered that because EXP-0202 tripped it. If the
    cheapest experiment had happened to be a fault-heavy one I might have concluded "Gate E
    unmeetable" for the whole wave on the strength of a criterion I wrote badly. `AMENDMENT-03`
    is the record of that; the reader should weigh that I found it by running rather than by
    thinking.

---

## 12. What was covered, and what was not

**Covered, with a new quiet pair taken by this experiment:** EXP-0203, EXP-0205, EXP-0202,
EXP-0201, EXP-0199, EXP-0204 (`tex_sample`/`tex_write` and `tex_deriv`).
**Covered by re-deriving quietness from its own committed raw:** EXP-0206 `run05`/`run07`.
**Not reached:** EXP-0206's `cf_nl2`, `cl_atomic`, `cl_leaf` and `cl_chain` arms — measured
unaffordable, not skipped (§8.2).

**Captures taken, retained, never reused, supporting no verdict:**
`EXP-0203/raw/g17p_q41`, `g17p_q42` (superseded by AMENDMENT-01);
`EXP-0205/raw/g17p_quiet01`, `g17p_quiet02` (AMENDMENT-02);
`EXP-0202/raw/g17p_quiet01` (frozen refuter R1, then AMENDMENT-03);
`EXP-0206/raw/g17p_quiet01`, `g17p_quiet02` (deliberately stopped partials, which are
themselves the measurement in §8.2).
The index is `raw/SUPERSEDED.txt`.

## 13. Defects found in other people's tools, reported and NOT fixed

I was told not to touch `tools/agx-isa/`, `docs/`, `PROVENANCE.md`, or any other experiment's
files, so each of these is a report.

1. **`tools/agx-isa/wave_audit.py` — the cross-run key is still not unique.** It keys by
   `(arm, value)`, which collides for a **byte-indexed** sweep: `half_alu_fma12.ext` walks 8
   byte positions × 256 values, eight records share one key, and the dict keeps the last. In a
   **reverse-order** run a different `byte_index` is last, so the two runs compare different
   bytes. Over EXP-0203's six committed runs it read 100.00 %; adding the four quiet runs makes
   it read **2.08 % (752/768 disagree)** for `ext`. Keyed with `byte_index` included it is
   **8410/8410 = 100.00 %**. The three promotable EXP-0203 fields are unaffected (still
   100.00 % over all ten runs). **Fix: add `byte_index` and any other per-record identity key
   to the audit key.**
2. **EXP-0201 `analysis/verdicts.py` and EXP-0202 `analysis/verdicts.py` both misclassify their
   own helper processes as foreign, and gate promotion on it** (§5.2). EXP-0201 refuses all six
   of its fields on **1 of 273** samples that caught its own `MTLCompilerService`; EXP-0202
   marks a run busy on **1 of 396** samples that caught its own `(agxrun_persist)` zombie.
   **Fix: one `ps` snapshot; ownership by session id as well as ppid; and treat
   `MTLCompilerService` separately from dispatch runners.**
3. **EXP-0202 `analysis/field_verdicts.json` carries hardcoded prose about `run03`/`run04`**
   (`_cross_run`, `_contamination`, `innocent_victim_cases`) that is *not* recomputed from the
   runs passed in. Pointed at the quiet pair it still reports "run03 167, run04 160" when the
   actual counts are **0 and 0**.
4. **EXP-0205's `CAPTURE_CONTRACT.json` is stale against its own committed harness.** It pins
   `harness/carriers205.py` at `97f90f51…`, which is also what its committed `runB01`/`runB02`
   recorded, but the committed file is `924fa4ee…`; `verify_remote.py` therefore refuses
   (21/25). The edit is immaterial to dispatch — the quiet run reproduces byte-identical
   instruction bytes on all 5245 keys — but the contract should be re-frozen.
   EXP-0202 (30/31), EXP-0206 (21/22) and EXP-0204 (28/29) have the same shape, each with only
   analysis files drifting, which §4 of the corrections document explicitly permits.
   **EXP-0201 is the only one of the seven that verifies clean: 23/23.**
5. **EXP-0202's `harness/sync.sh pull` rsyncs the whole `raw/` tree** and will overwrite
   committed raw if anything on the neo has touched it. It did: an orphaned `gpuwatch.py` from
   a finished agent had been appending to `raw/g17p_20260830_run01/gpuwatch.jsonl` for two
   hours. Restored (the committed content was an exact prefix — pure append, nothing altered);
   orphan killed; disclosed in `PROGRESS.md`. **Pull per run directory, not per tree.**

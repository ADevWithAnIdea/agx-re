# EXP-0213 — RESULTS

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, `Mac17,5`, Metal family Apple9, `192.168.170.254`). Every capture below ran on
**G17P**, from the source experiment's **own committed harness**, with only the run id, the
harness's own selectors and the harness's own `--order` varied.

```text
Clean-room provenance: HW-PROBE (re-running our own committed harnesses over shaders we
                       compiled from our own MSL) + black-box IOKit registry PROPERTY reads
Inputs inspected:      this repository's own committed harnesses, kernels and raw; IOKit
                       registry property VALUES published by the driver (data, not code)
Apple binary introspection: NONE
```

*(This file is written incrementally as each phase's data lands. Sections are marked
PENDING until their captures complete.)*

---

## 0. Headline

**Gate E is now MET for 1 of EXP-0204's 4 named fields and for 17 of EXP-0206's 17 reachable
target arms, on a machine measured quiet in every sample of all 107 captures — and the three
EXP-0204 fields that stay NOT MET now fail for *measured* reasons instead of truncated
captures.**

| | |
|---|---|
| **MET** | `tex_write.rsv11` (3072/3072 = 100.0000 %, complete, three orders) · EXP-0206 stage 6A's 14 target arms on all four remaining carriers · EXP-0206 stage 6C's `ret_luse.linkmode` on `cl_atomic`, `cl_leaf` and `cl_chain` (256/256 each) |
| **NOT MET** | `tex_sample.mode` (2507/2560; 53 disagreements on 4 of 10 arms, all at values with bit 6 set; the other 6 arms are 1536/1536) · `tex_write.amode` (3041/3072; 31 disagreements on one arm, and the designated pair's `B1` is a singleton against 8 other captures) · `tex_deriv.dstsrc` (both captures stopped by the harness's own frozen 8-hang budget; 265/336 coverage; 2 disagreements) |
| **NOT REACHED** | EXP-0206's `if_push.scope` on `cf_nl2` — including the *safe* `+140` arm the `--only` selector cannot separate from the hazard arm |

**What changed the EXP-0204 picture: the truncation was never the machine.** EXP-0204's
`run.py` aborts its **entire arm loop** on a cascade, so one arm losing its baseline discards
every arm after it. Invoked **once per arm** through its own `--arms` selector — nothing
edited — it completed **66/66 captures, 102/102 field sweeps, 0 cascades, 0 baseline losses,
9276 records per order in three orders**, against EXP-0210's 5055-of-9276. And the arm EXP-0210
blamed, `tex_write@twdyn/0`, is clean in isolation while the full 22-arm run aborts at the
**identical case index 5240 in three independent orders** — it is accumulated in-process state,
not the carrier, not occupancy, and not the device's 22 000 accumulated resets.

**Three things this experiment measured that were not known:**

1. **A hang is two different things.** `ret_luse.linkmode` hangs are driver-recoverable —
   `recoveryCount` +225 over 37 hangs, no cascade, a periodic-mod-8 pattern holding across
   149 consecutive values and 149/149 partition agreement with the busy machine.
   `if_push.scope@cf_nl2+106` hangs reset **nothing** — `recoveryCount` frozen for 4509 s —
   and **accumulate**: after ~20 of them every value hangs, including values proven `ok` forty
   cases earlier. Only the second class makes a sweep impossible.
2. **A capture can contaminate the next capture on a completely idle machine.** Stage 6B left
   **58** `agxrun_persist` processes stuck in the exiting state holding **1.6 GB** and ~58 GPU
   contexts; the next capture's `carrier_open` hung, and a known-good arm could not render its
   unmutated baseline. The device cleared itself ~8 minutes later with three driver-initiated
   resets. No `macvdmtool`, and none needed.
3. **EXP-0210 §9's escalation claim, confirmed over full arms.** On all three call carriers,
   quiet vs busy: **256/256 same ok/not-ok partition, zero flips**, and exactly **64** values
   differing only in severity (`fault` → `hang`) at precisely `(v & 7) ∈ {4,5}`.

**And one thing that should temper all of it.** Gate E's further clause — a genuinely different
carrier or second method for a load-bearing inertness claim — is **not satisfied for any row
here**, and every MET row above except `tex_sample.mode`'s six clean arms is an inertness
claim. This experiment moves those rows past the *quiet* clause and no further.

---

## 1. What "quiet" measured

Every capture was wrapped in a 2 s-interval sampler (EXP-0210's `quietsample.py`, copied
byte-identical, sha256 `47e2829e6d99…`) and bracketed by a device-counter snapshot taken
immediately before and immediately after it.

`analysis/quiet_table.py` prints one row per capture. Across **all 107 captures** this
experiment took (106 evidence captures plus one `--smoke-only` pipeline test that writes
to `work/` and is not evidence):

* `max_foreign_runner_live` = **0** in every sample of every capture;
* `max_foreign_runner_strict` (including exiting/zombie rows) = **0** as well — the exiting-row
  distinction never had to be used;
* `n_compiler_svc` peaked at **79** in one capture, and under EXP-0201's and EXP-0202's own
  gate rule that alone would have marked the capture CONTAMINATED — the concrete case that
  correction 1 above exists for;
* `ioreg` errors = **0**; no foreign submitter in any capture;
* the only submitter PIDs seen are the known-idle login-window process (328), our own runners,
  and PIDs absent from the sampled rows (our own short-lived runners between two samples,
  reported as a named category, not scored).

`recoveryCount` (cumulative **device resets**) is **reported, not gated**, per
`PRE_REGISTRATION` §4.3: the frozen "recoveryCount unchanged" criterion EXP-0210 wrote can
never be met by a fault-heavy capture, because our own pre-registered illegal encodings reset
the device. Per-capture pre/post counters are in each `raw/<tag>/gpu.jsonl` and in the table.

**The device was NOT fresh, and this is the one confounder this experiment could not remove.**
`recoveryCount` stood at **22134** when the contract was frozen — EXP-0210's ~22 000
accumulated resets were still on it, because the machine had not rebooted and `macvdmtool` is
forbidden to this agent. The mitigation was ordering, not clearing: the two arms that failed
for EXP-0210 were dispatched **first**.

---

## 2. EXP-0204 `tex_sample` / `tex_write` — the truncation was the whole-run abort, not the machine

### 2.1 H1 confirmed: per-arm invocation completes every arm

66 captures (22 arms × 3 orders: forward, reverse, shuffle 213), each a separate invocation of
EXP-0204's **own** `run.py` through its **own** `--arms` selector, nothing edited.

| | |
|---|---|
| captures | **66**, every one measured QUIET |
| cascades | **0** |
| arms whose `baseline_final_ok` was not `true` | **0** |
| field-sweep groups | **102 / 102 complete** — every value of every field of every arm swept |
| records per order | **9276**, the same total as the committed busy full-set runs |
| `actual_bytes` identical on shared keys | **9009 / 9009** in all three pairings |
| `requested == decoded` | **8704 / 8704** in every order |
| faults / hangs / `InnocentVictim` / measurement failures | **0 / 0 / 0 / 0** |

EXP-0210's pair covered 5055 of 9276 keys. This one covers **9276 of 9276**, three times over.

Whole-capture outcome counters, this experiment's three orders against every earlier capture of
the same arm set:

| capture | ok | wrong_value | moved | inert | has_power | fault | foreign | victims |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| committed **busy** `A2run01` | 6736 | 2045 | 364 | 108 | 22 | 0 | **1** | **3** |
| committed **busy** `A2run02` | 6716 | 2066 | 365 | 107 | 22 | 0 | 0 | 0 |
| EXP-0210 quiet `C1` (truncated) | 6207 | 2310 | 368 | 104 | 22 | **3** | 0 | 0 |
| EXP-0210 quiet `C2` (truncated) | 2592 | 2313 | 242 | 77 | 15 | **3** | 0 | 0 |
| **e0213 B1** forward | 6687 | 2095 | 365 | 107 | 22 | **0** | **0** | **0** |
| **e0213 B2** reverse | 6728 | 2054 | 365 | 107 | 22 | **0** | **0** | **0** |
| **e0213 B3** shuffle 213 | 6720 | 2062 | 365 | 107 | 22 | **0** | **0** | **0** |

The Gate B detection counters (`moved` 365, `inert` 107, `has_power` 22) are **byte-identical
across all three orders** and match the committed `A2run02` exactly.

### 2.2 H2 refuted: `tex_write@twdyn` is not the destabiliser

`tex_write@twdyn/0` and `tex_write@twdyn/1` were dispatched **first in the session**, in
isolation. Both completed **256/256 on `amode` and 256/256 on `rsv11`**, with
`baseline_final_ok: true`, 0 hangs, 0 faults, and both periodic baseline re-checks passing
with `retries=0`. The same is true in all three orders.

So the carrier reproduces its own baseline perfectly when it is the only arm in the process.

### 2.3 …and the whole-run abort is deterministic

Phase 2 ran the full 22-arm set exactly as EXP-0210 did (`--mnem tex_sample,tex_write`):

| capture | order | records | arms | cascade | elapsed |
|---|---|---:|---:|---|---:|
| `g17p_e0213_A1_full` | forward | 5241 | 15 | `[["tex_write@twdyn/0","amode",5240]]` | 16.4 s |
| `g17p_e0213_A2_full` | reverse | 5241 | 15 | `[["tex_write@twdyn/0","amode",5240]]` | 16.4 s |
| EXP-0210 `g17p_quiet_C2` | reverse | 5241 | 15 | `[["tex_write@twdyn/0","amode",5240]]` | 16.4 s |

**Three independent captures abort at the identical case index, 5240.** In every one the
failing record is the periodic baseline re-check, which returns `status: OK` — it is not a
fault, a hang, or a victim; the unmutated carrier simply produces a **different observation**
from the one it produced 250 cases earlier in the same process. In isolation it does not.

**Observation, not interpretation:** the abort is a function of accumulated in-process state
(≈5000 preceding dispatches across 14 preceding arms), not of the `twdyn` encoding, not of
machine occupancy, and not of the device's accumulated reset count. `A1 × A2` over their
common 5050 keys: ledger **5050/5050 identical**, agreement **4998/5047 = 99.0291 %**, 0 hard
flips, 0 victims — the two truncated runs agree with each other to the same 99 % the full
per-arm runs do, and disagree on the same four `tex_sample` arms (§2.5).

### 2.4 `tex_write.rsv11` — clean

| pair (all quiet, complete, 12 arms) | shared | ledger identical | agree | soft | hard flip |
|---|---:|---:|---:|---:|---:|
| B1 forward × B2 reverse | 3072 | 3072 | **3072** | 0 | 0 |
| B1 forward × B3 shuffle 213 | 3072 | 3072 | **3072** | 0 | 0 |
| B2 reverse × B3 shuffle 213 | 3072 | 3072 | **3072** | 0 | 0 |
| B1 quiet × committed **busy** `A2run01` | 3072 | 3072 | **3072** | 0 | 0 |

**100.0000 % on 3072/3072 keys, in every pairing, including against the busy machine.**

### 2.5 `tex_sample.mode` — reproducible on 6 arms, NOT reproducible on 4

| pair | shared | agree | soft | pct |
|---|---:|---:|---:|---:|
| B1 × B2 (the designated Gate E pair) | 2560 | 2507 | **53** | 97.9297 % |
| B1 × B3 | 2560 | 2488 | 72 | 97.1875 % |
| B2 × B3 | 2560 | 2498 | 62 | 97.5781 % |
| B1 quiet × committed **busy** `A2run01` | 2560 | 2200 | 359 | 85.9375 % |

Distinct-payload count per `(arm, value)` across the three quiet orders
(`analysis/stability.py`):

| arm | keys | stable | unstable |
|---|---:|---:|---:|
| `mscmp/0`, `mscmp/1`, `msfilt/0`, `msfixl/0`, `msfixl/1`, `msgath/0` | 256 each | **256 each** | **0** |
| `mslodq/0` | 256 | 229 | 27 |
| `mslodq/1` | 256 | 236 | 20 |
| `msread/0` | 256 | 235 | 21 |
| `msread/1` | 256 | 234 | 22 |
| **total** | **2560** | **2470 (96.4844 %)** | **90** |

Adding the two committed **busy** runs to the same computation drops it to **2126 / 2560
(83.0469 %)**.

**Observed.** Every unstable value on the four `msread` / `mslodq` arms has **bit 6 set**
(e.g. `msread/0`: 64, 67, 80, 83, 96, 99, 112, 115, 192, 195, 208, 211, 224, 227, 240, 243).
The differing part of the record is the `probe` payload and its hash — never the outcome class
and never the instruction bytes. The six other arms are byte-stable over 256/256 values in
three orders.

**Where in the observation the disagreement sits.** For all 53 `mode` disagreements in
`B1 × B2` the differing values are spread across probe pixels 0, 1, 4 and 6 of `PIX0`
(50, 53, 50 and 51 cases) and touch channels **1, 2 and 3 only** — channel 0 never moves in any
disagreeing case. It is the sampled result that varies, not one edge pixel, so this is not a
rasterisation-coverage artefact confined to a triangle boundary.

**Comparator calibration.** Pointed at EXP-0210's own `C1 × C2` pair, `analysis/per_field.py`
reproduces EXP-0210's published figure exactly — `mode` **2388 / 2560 = 93.2812 %**, 172 soft
disagreements, `amode` 1274/1274, `rsv11` 1024/1024 — so the 97.93 % above is measured with
the *same* instrument on the *same* scale, not a different one. The improvement from 172 to 53
disagreements comes from complete sweeps on a device with 22 100 rather than 21 800
accumulated resets, and it also moves `msfixl/0` from 255/256 to a clean 256/256 in all three
of this experiment's orders.

**Interpretation, bounded.** A quiet machine roughly halves the instability (359 → 53
disagreements against the same reference) but does not remove it. What remains is a stable
property of four of the ten carriers, not of the machine and not of the capture length. This
is the same six-arms-good/four-arms-bad split EXP-0204 itself reported when it rested its bit
rule on "the six arms that reached 256/256"; it is now measured on a quiet machine with
**complete** sweeps in three orders instead of a truncated pair.

### 2.6 `tex_write.amode` — one arm, 31 values, and the outlier is the first capture of the session

| pair | shared | agree | soft | pct | disagreeing arm |
|---|---:|---:|---:|---:|---|
| B1 × B2 | 3072 | 3041 | 31 | 98.9909 % | `tex_write@twdyn/0` only |
| B1 × B3 | 3072 | 3041 | 31 | 98.9909 % | `tex_write@twdyn/0` only |
| **B2 × B3** | 3072 | **3072** | **0** | **100.0000 %** | — |
| B1 × committed busy `A2run01` | 3072 | 3041 | 31 | 98.9909 % | `tex_write@twdyn/0` only |

**Where in the observation the disagreement sits.** For all 31 `amode` disagreements the differing values sit **only** in the `TEXW` group at texel
slots **4 and 5** (24 and 7 cases) and never at slots 0–3 — consistent with a last-writer
ordering effect in the write carrier's own readback rather than with the swept field.

The other 11 arms are **2816 / 2816 = 100.0000 %** in every pairing. All 31 disagreements are
on `tex_write@twdyn/0`, at the same 31 `amode` values every time, and **B1 is the outlier**:
B2, B3 and the committed busy run all agree with each other and disagree with B1. B1's
`tex_write@twdyn/0` was the **first GPU capture this session took**, on a machine that had been
idle for four hours. Phase 5 repeats that one arm to characterise this (§5).

### 2.6b The inherited Gate B controls are themselves reproducible

Gate B is inherited, not re-audited — but its evidence lives in the same captures, so it can be
checked for free. Over the **472** `_detect` positive-control records shared by all three
orders:

| | |
|---|---|
| outcome-label (`moved` / `inert`) disagreements | **0 / 472** |
| payload-identical in all three orders | 466 / 472 |
| the 6 payload disagreements | `mslodq/0` (`comp_flags`, `result_sel`), `mslodq/1` (same two), `twdyn/0` (`wop`), `twmip/0` (`coord_pack`) |

The **verdict** Gate B rests on — whether a control in the field's own dimension moved the
observable — is 100 % reproducible across three orders on a quiet machine. The six payload
differences fall on carriers already identified as unstable in §2.5 and §2.6, plus one on
`twmip/0` whose own `amode`/`rsv11` sweeps are 256/256 stable.

### 2.7 The `tex_write@twdyn/0` `amode` outlier, characterised (phase 5)

Nine quiet captures of that one arm, each its own invocation, pairwise payload agreement on
`amode` over all 256 values:

```
             B1    B2    B3    R1    R2    R3    R4    R5  R6cold
     B1     256   225   225   225   225   225   225   225     225
     B2     225   256   256   256   256   256   256   256     256
     B3     225   256   256   256   256   256   256   256     256
     R1     225   256   256   256   256   256   256   256     256
     ...    (R2..R5 and R6cold identical: 256 against everything except B1)
```

**B1 is a singleton.** Eight quiet captures and the committed **busy** `A2run01` all agree with
one another on 256/256, and all nine of them disagree with B1 on the same 31 values. B1's
`tex_write@twdyn/0` was the **first GPU dispatch this session made**, on a machine that had
been idle for four hours (`recoveryCount` had not moved; loadavg 0.35; zero GPU processes).

**Phase 6, the cold-device refuter (AMENDMENT-02), came out negative.** The GPU was left
completely untouched for **38 minutes** (03:59:55Z → 04:38Z; `fLastSubmissionPID` back to the
idle 328, `In use system memory` 12 MB, zero runners, `recoveryCount` stable at 25400), and
`tex_write@twdyn/0` was then dispatched first, alone, in the same forward order as `B1`.

`R6cold` agrees with B2, B3 and R1–R5 on **256 / 256** and disagrees with `B1` on the **same 31
values**. Per the amendment's own stated reading, that means the cold-device hypothesis
**survives only for idle periods much longer than 38 minutes — it is NOT confirmed**, and B1
remains an unexplained singleton. This is weak evidence, and it is reported as weak: a
38-minute idle is not the four-hour idle that preceded B1, and nothing here excludes a longer
thermal/DVFS settling time. What it does establish is that the effect is **not** reproducible
at a 38-minute idle on this device.

**This is a characterisation, not a re-roll of the gate.** The Gate E pair was designated
`B1 × B2` in the frozen contract before any capture ran, and by that designation
`tex_write.amode` is **NOT MET** on 31 of 3072 keys. What phase 5 adds is that the
disagreement is a named, bounded, one-sided exception rather than an open instability.

---

## 3. EXP-0204 `tex_deriv.dstsrc` — the hazard family reproduces exactly; the field does not clear its own budget

Four orders (`forward`, `shuffle 213`, `reverse`, `shuffle 1213`), 6 arms each, all measured
QUIET. **Every capture in every order was stopped by EXP-0204's own frozen 8-hang-per-field
budget in every one of its six arms** — which was pre-registered as the expected outcome
(`PRE_REGISTRATION` §5.1: with 9 hazard values and a budget of 8, no order can sweep all 65).

| capture | order | per-arm values swept (of 65) | hangs |
|---|---|---|---:|
| `g17p_e0213_D_fwd` | forward | 64, 64, 64, 64, 64, 64 | 48 |
| `g17p_e0213_D_sh1` | shuffle 213 | 64, 56, 55, 55, 51, 38 | 48 |
| `g17p_e0213_D_rev` | reverse | 27, 27, 27, 27, 27, 27 | 48 |
| `g17p_e0213_D_sh2` | shuffle 1213 | 63, 53, 63, 40, 35, 51 | 48 |

### 3.1 The hazard family, confirmed on a quiet machine

In **all four orders**, the set of `dstsrc` values that produced a hard outcome is a **subset
of the nine already-named hazard values**, and the number of hard outcomes at any value
outside that set is **zero**:

`0x03FFFF, 0x07FFFF, 0x0FFFFF, 0x1FFFFF, 0x3FFFFF, 0x7FFFFF, 0xFBEEE7, 0xFFFFFE, 0xFFFFFF`

Every arm hit exactly its budget of 8, so which 8 of the 9 appear depends only on the order.
**Observed:** 4 orders × 6 arms = 24 arm-sweeps, 192 hard outcomes, **0 outside the named
family**. This is the strongest confirmation the family has: previously it rested on two busy
captures (7 and 11 hangs) plus EXP-0210's two quiet ones.

### 3.2 The designated Gate E pair

`D_fwd × D_sh1` (designated in `CAPTURE_CONTRACT.json` before any of the four ran):

| | |
|---|---|
| shared record keys | 373 |
| **`actual_bytes` identical** | **373 / 373** |
| whole-capture agreement | 323 / 325 = **99.3846 %**, 0 hard flips, 48 both-hard |
| **`dstsrc` field only** | **263 / 265 = 99.2453 %**, 2 soft disagreements, 0 hard flips |
| the 2 disagreements | `tex_deriv@deriv/1`, values **7** and **127**, both `wrong_value` in both runs; the differing part is the `probe` payload |
| coverage of the declared claim domain | **265 of 336** non-hazard (arm, value) keys = **78.87 %** |
| victims / measurement failures | 0 / 0 |

Over the **98** keys shared by all **four** orders, `dstsrc` payloads are **98/98 = 100.0000 %
stable**.

### 3.3 An inherited Gate A defect, reported not fixed

`dstsrc = 0x80` (128) produces `gate_a_ok: false` with `decoded_value: null` on **every one of
the six arms**, in `D_fwd` (6 cases), `D_sh1` (6) and `D_sh2` (5); `D_rev` never reached it.
The requested value is 128 and the value decoded back from the actual dispatched bytes is
`None`. This is EXP-0204's own Gate A firing, it is present in EXP-0210's captures too, and it
is not this experiment's to fix. It is reported so that any claim about `dstsrc = 0x80` is
known to rest on a case whose own ledger check failed.

---

## 4. EXP-0206 stages — the remaining carriers, with the hazard arms named and separated

### 4.1 Stage 6A: the four carriers minus the two named hazard keys

Excluded **by name, declared before the run**: key `if_push.scope` on `cf_nl2` (which the
`--only` selector cannot separate from the hazard arm at `+106`) and key `ret_luse.linkmode`
on `cl_atomic`, `cl_leaf`, `cl_chain`. Declared budget 60 hangs / 1800 s per capture.

| capture pair (S1 forward × S2 reversed) | records each | shared | `actual_bytes` identical | outcome-label agreement | payload agreement | hangs used |
|---|---:|---:|---:|---:|---:|---:|
| `cf_nl2` | 695 | 695 | **695 / 695** | **695 / 695** | **695 / 695** | 2 of 60 |
| `cl_atomic` | 705 | 705 | **705 / 705** | **705 / 705** | **705 / 705** | 0 of 60 |
| `cl_leaf` | 455 | 455 | **455 / 455** | **455 / 455** | 446 / 455 | 3 of 60 |
| `cl_chain` | 647 | 647 | **647 / 647** | **647 / 647** | **647 / 647** | 4 of 60 |

Per target arm, **every** arm under test agreed on **both** outcome label and payload on
**every** shared key:

| carrier | arm | keys | agreement |
|---|---|---:|---|
| `cf_nl2` | `pop_reconverge.scope@+216` | 256 | 256/256 |
| `cf_nl2` | `pop_reconverge.scope@+222` | 256 | 256/256 |
| `cf_nl2` | `pop_reconverge.reserved@+216` | 52 | 52/52 |
| `cf_nl2` | `stop.reserved@+268` | 73 | 73/73 |
| `cl_atomic` | `call.tail@+52` | 256 | 256/256 |
| `cl_atomic` | `pop_reconverge.scope@+66` | 256 | 256/256 |
| `cl_atomic` | `pop_reconverge.reserved@+66` | 52 | 52/52 |
| `cl_atomic` | `stop.reserved@+124` | 73 | 73/73 |
| `cl_leaf` | `call.tail@+54` | 256 | 256/256 |
| `cl_leaf` | `stop.reserved@+88` | 73 | 73/73 |
| `cl_leaf` | `stop.reserved@synth_mid@+50` | 74 | 74/74 |
| `cl_chain` | `call.tail@+54` | 256 | 256/256 |
| `cl_chain` | `ret.scoreboard@c_mid+104` | 256 | 256/256 |
| `cl_chain` | `stop.reserved@synth_mid@+50` | 74 | 74/74 |

**The one disagreement in the whole stage is on a Gate B CONTROL arm, not a field under
test:** `CTRL:b6@cl_leaf._agc.main+54`, 9 of its 16 values, all classified `wrong_value` in
**both** runs but with differing `probe` payloads. That is reported as a **weakening of
`cl_leaf`'s detection-power evidence in this pair**, not as a field disagreement, and it is
the reason `cl_leaf`'s payload column reads 446/455 while its outcome column reads 455/455.

**Cost, measured against the estimate.** The estimate in `PRE_REGISTRATION` §5.2 was
"≤30 hangs, ≤12 min per run" from a 24.07 s/hang model. Actual: **9 hangs across all eight
captures**, 4.7 minutes of device time for the whole stage, at ~11–13 s per hang. The hang
budget was never approached and the wall-clock cap was never hit.

### 4.2 Stage 6A scored by EXP-0206's OWN verdict program, unedited

`analysis/e0206_scorer/verdicts206.py` and `models206.py` are **byte-identical copies** of
EXP-0206's committed scorers (sha256 `3afc75dd4674…` and `fd5e2d91c85f…`). They are copied
rather than invoked in place for one reason: `verdicts206.py` writes its output next to
itself, so running it in EXP-0206's tree would **overwrite that experiment's committed
`analysis/gate206.json`**. Copied, it writes into this experiment's directory instead and
EXP-0206's evidence is untouched.

Pointed at the eight stage-6A captures, EXP-0206's own scorer reports, for **every** target
arm: `dis=0`, `agr=1.0000`, `hard={}`, ledger complete, and

| field | arms | ledger | agreement | surviving model | verdict |
|---|---:|---|---:|---|---|
| `call.tail` | 3 | 1536/1536 | 1.0 | `M1_inert` | accepted-inert in tested envelope |
| `pop_reconverge.scope` | 3 | 1536/1536 | 1.0 | `M3_inert` | accepted-inert in tested envelope |
| `pop_reconverge.reserved` | 2 | 208/208 | 1.0 | `M1_inert` | accepted-inert in tested envelope |
| `ret.scoreboard` | 1 | 512/512 | 1.0 | `M1_wait_mask`, `M2_inert` | accepted-inert in tested envelope |
| `stop.reserved` | 3 | 438/438 | 1.0 | `M1_inert` | accepted-inert in tested envelope |
| `stop.reserved@synth_mid` | 2 | 292/292 | 1.0 | `M1_inert` | accepted-inert in tested envelope |

Its own promotion rule still says `REFUSED / INERT` on every arm, because each has **V = 1**
distinct valid payload and its gate requires ≥ 2 — that is EXP-0206's own semantics gate
(Gate C), not Gate E, and this experiment does not touch it.

### 4.3 Stage 6B: **NOT REACHED**, and the reason is the most useful thing in this experiment

`H1` (`--carriers cf_nl2 --only if_push.scope --order forward`) ran for its full declared
4500 s cap and was killed by the external process-group cap (`__DRIVE_CAP_HIT`,
`__DRIVE_RC=142`). It reached **142 of 256** values on `if_push.scope@cf_nl2._agc.main+106`.
Under the frozen stop rule its pair partner `H2` was **not attempted**; it was stopped about a
minute in and its partial (1 record) is retained under its own id.

**Why it could not finish — the value-by-value record:**

```
 0:H  1:H  2:o  3:o  4:H  5:H  6:o  7:o  8:H  9:H 10:o 11:o 12:H 13:H 14:o 15:o
16:H 17:H 18:o 19:o 20:H 21:H 22:o 23:o 24:H 25:H 26:o 27:o 28:H 29:H 30:o 31:o
32:H 33:H 34:o 35:o 36:H 37:H 38:o 39:o
40:H 41:H 42:H 43:H 44:H 45:H ... 141:H            <- every value from 40 on
```

| window | hangs | ok/not-ok partition agreement with the committed busy `run03` |
|---|---:|---:|
| values 0–19 | 10 / 20 | 15 / 20 |
| values 20–39 | 10 / 20 | **18 / 20** |
| values 40–59 | **20 / 20** | 10 / 20 |
| values 60–79 | **20 / 20** | 10 / 20 |
| values 80–99 | **20 / 20** | 9 / 20 |
| values 100–119 | **20 / 20** | 10 / 20 |
| values 120–139 | **20 / 20** | 9 / 20 |

Values 0–39 reproduce the busy machine's rule exactly — `(v & 2) == 0` → not-ok, else ok, 20
hangs and 20 `ok`. From value **40** onward **everything** hangs, 102 consecutively, including
values proven `ok` forty cases earlier. Across the whole capture `recoveryCount` **never
moved**: 22868 before, 22868 after, over 2220 samples and 4509 s.

**This is a self-inflicted cascade, and it is exactly what `FIELD-SWEEP-PROTOCOL` §3c warns a
budget-free sweep will do.** EXP-0206's `run.py` deliberately has no abort path and no hang
budget. On a busy machine that was survivable, because a neighbour's error recovery reset the
device constantly. On a quiet machine nothing resets it, the damage accumulates, and after
about **20 hangs** the carrier stops producing a correct result for any value at all.

**Consequences, stated plainly.**

* Stage 6B is **NOT REACHED**. Neither `if_push.scope@cf_nl2+106` nor the safe
  `if_push.scope@cf_nl2+140` arm it shares a selector with was confirmed.
* Every `H1` record from value 40 on is **cascade-contaminated by construction** and is not a
  hardware outcome for those values. Only values 0–39 are usable, and they agree with the busy
  machine.
* EXP-0210 §9's claim that the ok/not-ok partition survives the busy→quiet transition is
  **confirmed for the first 40 values and refuted beyond them** — its own quiet capture stopped
  at 17 values, inside the clean region.

### 4.4 The degradation outlived the capture, and the device recovered on its own

The next capture attempted, stage 6C's `L1_cl_atomic`, recorded **`carrier_open` → `hang`**:
it could not open its carrier at all, before dispatching a single field value. A health probe
then failed too — `tex_sample@msfilt/0`, an arm measured 256/256 payload-stable in three
orders, could not render its **unmutated** baseline.

Measured device state at that point:

| | at session start | after the 6B cascade | ~8 min later |
|---|---:|---:|---:|
| `(agxrun_persist)` stuck in state `?Es` | 0 | **58** | **0** |
| `Alloc system memory` | 310 MB | **2.03 GB** | 201 MB |
| `In use system memory` | 112 MB | **1.61 GB** | 21 MB |
| `fLastSubmissionPID` | 328 (idle) | 51766 (one of the stuck runners) | 328 (idle) |
| `recoveryCount` | 22134 | 22868 (unmoved for 4509 s) | **22871** |

Killing a `run.py` whose `agxrun_persist` children are blocked on hung command buffers leaves
those children permanently in the **exiting** state, holding ~1.6 GB and ~58 GPU contexts the
driver will not release; new contexts then cannot complete. About eight minutes later the
driver reclaimed them with **three** device resets, and everything returned to the idle
baseline. **No `macvdmtool` was used and none was needed.**

Recovery was then **proven rather than assumed**: `HEALTH GATE 2` re-ran `tex_sample@msfilt/0`
and got **256/256 `mode` payloads byte-identical to all three B-series orders**, with
`baseline_final_ok: true` (`AMENDMENT-03`).

### 4.5 The threshold probe refuted my own stop decision — there are TWO hang classes

Having stopped stage 6C on the premise that its ~64 expected hangs exceeded the measured
~20-hang cascade onset, I ran one bounded probe (`AMENDMENT-04`, 900 s cap) to generalise the
threshold to a second arm family. It did the opposite.

`g17p_e0213_T1_cl_atomic_threshold`, `ret_luse.linkmode@cl_atomic.l__ZL4m_atPU9M+32`, quiet,
healthy device:

| | |
|---|---|
| values dispatched | **149** consecutive, 0 → 148 |
| hangs | **37** |
| cascade | **none** — the pattern is periodic mod 8 from value 0 to value 148 without one deviation |
| the rule | `ok` at `(v & 7) ∈ {2,6}` · `hang` at `(v & 7) ∈ {4,5}` · `fault` at `(v & 7) ∈ {0,1,3,7}` |
| partition agreement with the committed busy `run03` | **149 / 149** |
| `recoveryCount` | **22871 → 23096** — 225 device resets, ~6 per hang, recovered every time |
| device residue afterwards | **none**: 0 stuck runners, memory back to 337 MB / 137 MB |

Against stage 6B's `if_push.scope@cf_nl2+106`: **122 hangs, zero device resets in 4509 s.**

> **Two hang classes.** A hang the driver recognises and recovers from — `recoveryCount`
> increments, the device is reset, the runner restarts — is **survivable and repeatable**: 37
> of them left the ok/not-ok partition exactly as the busy machine measured it, over 149
> consecutive values. A hang the driver does **not** recover from — `recoveryCount` frozen —
> **accumulates**: after ~20 of them every dispatch on that carrier hangs, and the degraded
> state outlives the process by ~8 minutes.
>
> `hang` is one label for two very different hardware/driver behaviours, and only the second
> one is a reason a sweep cannot be run.

That refutation is why stage 6C was **re-captured** under new run ids (`AMENDMENT-05`); the
stopped `L1_cl_atomic` is retained, never topped up, and supports no verdict.

### 4.6 Stage 6C, re-captured: `ret_luse.linkmode` on all three call carriers — **clean**

Six captures under new run ids (`AMENDMENT-05`), pair-first, each after a passing health gate,
each completing inside its declared 2100 s cap (measured 1550.5–1550.6 s, hang budget 64 of the
80 declared):

| pair (L3 forward × L4 reversed) | records each | shared | `actual_bytes` identical | outcome-label agreement | payload agreement | hard outcomes (both runs) |
|---|---:|---:|---:|---:|---:|---|
| `cl_atomic` (`m_at`+32, the **real** compiler-emitted `ret_luse`) | 279 | 279 | **279 / 279** | **279 / 279** | **279 / 279** | 128 fault + 64 hang |
| `cl_leaf` (`lf_add`+30) | 281 | 281 | **281 / 281** | **281 / 281** | **281 / 281** | 128 fault + 64 hang |
| `cl_chain` (`c_mid`+104, non-leaf) | 281 | 281 | **281 / 281** | **281 / 281** | **281 / 281** | 128 fault + 64 hang |

`ret_luse.linkmode` itself is **256 / 256** on every carrier, the `CTRL:tail` control arm is
16/16, and every open/close/mid128 probe matches. **0 victims, 0 cascade, 0 measurement
failures, both captures of every pair measured QUIET.**

**Against the committed busy `run03`, per carrier: 256 / 256 same ok/not-ok partition, ZERO
partition flips, and exactly 64 values differing only in SEVERITY** — `fault` on the busy
machine, `hang` on the quiet one — at precisely `(v & 7) ∈ {4,5}`.

That is EXP-0210 §9's escalation claim confirmed over a **full 256-value arm on three
structurally different carriers**, instead of the 14 values it rested on:

| | busy `run03` | quiet L3 / L4 |
|---|---|---|
| `(v & 7) ∈ {2,6}` | `ok` 64 | `ok` 64 |
| `(v & 7) ∈ {0,1,3,7}` | `fault` 128 | `fault` 128 |
| `(v & 7) ∈ {4,5}` | **`fault` 64** | **`hang` 64** |

(`cl_chain` splits its `ok` set 32 `ok` / 32 `wrong_value`, identically in all three captures —
EXP-0206's own non-leaf link rule, unchanged.)

---

## 5. Instrument and device observations this experiment measured

### 5.1 An EXP-0206 "hang" costs exactly 24.1 s and does **not** necessarily reset the device

Measured on `if_push.scope@cf_nl2._agc.main+106` during stage 6B: consecutive record
timestamps show `dt = 24.1 s` for every `hang` and `dt = 0.0 s` for every `ok`. Over the first
three hangs, the driver's `recoveryCount` did **not** change (22868 → 22868).

That matters for how EXP-0210 §9's escalation should be read. EXP-0206's `hang` is a
**request timeout plus a runner restart** — the harness's own `REQ_TIMEOUT`-driven
classification — and is not, by itself, evidence of a device reset. EXP-0204's `tex_deriv`
hangs by contrast *do* reset the device (its four deriv captures moved `recoveryCount` by
exactly 144 each, 48 hangs × 3 confirmation trials). Two different mechanisms wear the same
label in two different harnesses; a claim of the form "this encoding hangs the GPU" needs to
say which one it means. §4.5 sharpens this into the load-bearing distinction: within EXP-0206
itself, `ret_luse.linkmode` hangs **do** reset the device (+225 over 37 hangs) while
`if_push.scope@cf_nl2+106` hangs reset nothing, and only the second class cascades.

### 5.2 The severity escalation is confirmed at the same values

`if_push.scope@cf_nl2._agc.main+106`, values 0–4, same arm, same harness:

| value | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| committed `run03` (busy) | fault | fault | ok | ok | fault |
| EXP-0210 `g17p_quiet01` (quiet) | hang | hang | ok | ok | hang |
| this experiment, `H1` (quiet) | **hang** | **hang** | **ok** | **ok** | **hang** |

The ok/not-ok partition is unchanged; the severity of the not-ok outcome is load-dependent.
This is an independent reproduction of EXP-0210 §9 on a different day and a different
session — but only over the first 40 values of this arm: §4.3 shows the partition itself
collapses beyond that, in a cascade. The full-arm confirmation of the escalation claim is
§4.6's, on the three call carriers, where 256/256 values keep their partition.

---

## 6. Gate E, per field

"MET" means: both captures of the **pre-designated** pair measured QUIET; neither was stopped
by a cascade guard, a hang budget or the external cap; the pair's `actual_bytes` are identical
on every shared key; the pair covers the field's declared value domain minus the named
exclusions; and no non-hard cross-run disagreement remains.

### EXP-0204 — the four fields the dispatch named

| field | Gate E | evidence |
|---|---|---|
| **`tex_write.rsv11`** | **MET** | designated pair `B1 × B2` (forward × reverse), both QUIET, both **complete** (12/12 arms, 256/256 values each), ledger **3072/3072** identical, agreement **3072/3072 = 100.0000 %**, 0 faults / hangs / victims / cascades / measurement failures. Also 100.0000 % against `B3` (shuffle 213) and against the committed **busy** `A2run01`. |
| **`tex_write.amode`** | **NOT MET** | designated pair `B1 × B2`: **3041 / 3072 = 98.9909 %**. All 31 disagreements are on `tex_write@twdyn/0`; the other 11 arms are 2816/2816 = 100.0000 %. `B2 × B3` is 3072/3072, and seven quiet captures plus the committed busy run agree 256/256 with one another — `B1`, the session's first GPU dispatch, is the singleton (§2.7). |
| **`tex_sample.mode`** | **NOT MET** | designated pair `B1 × B2`: **2507 / 2560 = 97.9297 %**, 53 disagreements confined to 4 of the 10 arms (`msread/0`, `msread/1`, `mslodq/0`, `mslodq/1`), every one at a value with **bit 6 set**. The other six arms are **1536 / 1536 = 100.0000 %** across three orders. Over three quiet orders 2470/2560 keys are payload-stable; adding the two busy runs drops that to 2126/2560. |
| **`tex_deriv.dstsrc`** | **NOT MET** | both captures of the designated pair `D_fwd × D_sh1` were stopped by EXP-0204's **own frozen 8-hang budget** in every one of six arms, so neither is a clean run. Coverage **265 / 336** of the declared non-hazard claim domain; ledger **373/373** identical; `dstsrc` agreement 263/265 = 99.2453 %, the two exceptions being values **7** and **127** on `tex_deriv@deriv/1`. Separately, the 9-value hazard family reproduced **exactly** in all four orders with **zero** hard outcomes outside it. |

### EXP-0206 — the four carriers EXP-0210 could not reach

| arms | Gate E | evidence |
|---|---|---|
| **stage 6A** — `call.tail`, `pop_reconverge.scope`, `pop_reconverge.reserved`, `ret.scoreboard`, `stop.reserved`, `stop.reserved@synth_mid` on `cf_nl2`, `cl_atomic`, `cl_leaf`, `cl_chain` (14 target arms) | **MET** | `S1 × S2` per carrier (forward × reversed), all QUIET, ledgers **695/695, 705/705, 455/455, 647/647** identical, and **every target arm 100 % on both outcome label and payload**. Scored independently by EXP-0206's own unedited `verdicts206.py`: `dis=0`, `agr=1.0000`, `hard={}` on every arm (§4.2). |
| **stage 6C** — `ret_luse.linkmode` on `cl_atomic`, `cl_leaf`, `cl_chain` | **MET** | `L3 × L4` per carrier: **279/279, 281/281, 281/281** shared keys, ledgers identical, **100 % on both outcome and payload**, `ret_luse.linkmode` itself **256/256** on each carrier, hard outcomes byte-identical (128 fault + 64 hang), 0 victims (§4.6). |
| **stage 6B** — `if_push.scope` on `cf_nl2` (both `+106` and `+140`) | **NOT REACHED** | `H1` hit its declared 4500 s cap after 142/256 values and, from value 40 on, is a **self-inflicted non-recoverable hang cascade** (§4.3). Its pair partner was not attempted, per the frozen stop rule. `if_push.scope@cf_nl2._agc.main+140` — 256 values, **zero** faults in every committed run — is unconfirmed **only** because EXP-0206's `--only` selector is keyed by field name and cannot separate it from the hazard arm at `+106`. |

**Caveat that binds every MET row above, and is not argued around:** Gate E's further clause —
*"for load-bearing inertness or a surprising semantic claim, require a genuinely different
carrier or second method as well"* — is **NOT satisfied by this experiment for any row**.
`tex_write.rsv11` and every EXP-0206 field are inertness claims (EXP-0206's own scorer calls
all six `accepted-inert in tested envelope`). This experiment moves them past the *quiet*
clause and no further.

## 7. What was covered, what was not, and what it cost

| | |
|---|---|
| captures taken | **107** (106 evidence + 1 `--smoke-only` pipeline test) |
| all measured QUIET | **yes**, zero live foreign dispatch runners in every sample of every one |
| pulled files verified byte-identical to the neo | **406 / 406** |
| tracked files modified in this repo | **0**, after reverting one line this experiment accidentally appended to the repo-root `PROGRESS.md` (§8.12). One unrelated tracked file, `experiments/EXP-0209-dashboards/ledger/dashboard_ledger.jsonl`, is modified in the working tree; this experiment never read or wrote anything under EXP-0209, and it is flagged for the orchestrator rather than touched. |
| device resets consumed | `recoveryCount` **22134 → 25401**, +3267 |
| device time | ≈ 5 h of the declared 6 h budget |
| `macvdmtool` | **not used**; the one degraded-device episode cleared on its own in ~8 minutes |

**Declared budgets vs actual:**

| budget | declared | actual |
|---|---|---|
| EXP-0204 hang budget | the harness's own frozen 2 / 8 / 10, unchanged | unchanged; `tex_deriv` hit 8 in every arm of every order, as pre-registered |
| EXP-0206 stage 6A | 60 hangs / 1800 s per capture | **9 hangs total across all eight captures**, 4.7 min for the stage |
| EXP-0206 stage 6B | 160 hangs / 4500 s | **cap hit** at 4500 s with 122 hangs and 142/256 values |
| EXP-0206 stage 6C | 80 hangs / 2100 s per capture | **64 hangs, 1550.5–1550.6 s** per capture; all six complete |
| threshold probe (AMENDMENT-04) | 900 s | cap hit at 900 s after 149 values / 37 hangs |

**Declared exclusions, and what became of them:**

* `tex_deriv.dstsrc`'s nine named hazard values — excluded from the agreement claim, and
  separately **confirmed** to be exactly the hard-outcome set in four orders (§3.1).
* `if_push.scope` on `cf_nl2` — excluded from stage 6A; stage 6B was supposed to recover it and
  **did not** (§4.3). Still open.
* `ret_luse.linkmode` on the three call carriers — excluded from stage 6A; stage 6C
  **recovered it in full** (§4.6).

**Captures retained, never topped up, never reused, supporting no verdict:**
`EXP-0206/raw/g17p_e0213_H1_cf_nl2` (capped, cascade-contaminated past value 39),
`g17p_e0213_H2_cf_nl2` (stopped ~1 min in under the frozen stop rule),
`g17p_e0213_L1_cl_atomic` (`carrier_open → hang` on a device degraded by H1),
`EXP-0204/raw/g17p_e0213_HEALTH1_tex_sample_msfilt_0` (health gate FAIL — the evidence that
the degradation was real).

---

## 8. How this method could have failed to say "no"

1. **Per-arm invocation is a real change of dispatch shape, and it is the intervention under
   test.** Every arm gets a fresh process, a fresh runner and a fresh baseline. That is
   exactly why it completes — and it means the per-arm captures cannot, by construction,
   reproduce the accumulated-state failure that the full-set captures show. Both shapes are
   therefore on record (phase 1 and phase 2) rather than only the one that succeeds. A reader
   who thinks the committed full-set shape is the one that matters should read §2.3 as the
   primary result and §2.1 as the workaround.

2. **Agreement between two runs of the same harness on the same machine is nearly
   guaranteed.** Where this experiment reports 100 %, that is weak evidence on its own; what
   makes it load-bearing here is that the *same* method reports 97 % and 99 % on other fields
   in the same captures. The instrument demonstrably can say no — it said no to
   `tex_sample.mode` on four arms, to `tex_write.amode` on one, to `tex_deriv.dstsrc` on two
   values, and to a `cl_leaf` control arm on nine.

3. **The quiet metric samples at 2 s.** A GPU client that starts, submits and exits between
   two samples is invisible to it. The machine sat at the login screen with `SecurityAgent` as
   its last submitter and zero GPU processes throughout, so the residual risk is small — but
   it is real, and it is the same hole EXP-0210 disclosed rather than a new argument.

4. **Cross-run agreement compares the `observed` payload only,** with timing and the
   whole-program hash stripped. Contamination expressed outside `observed`, or inside a
   stripped field, is invisible to it. Hard outcomes are counted separately and compared both
   ways.

5. **The comparator's key is not unique in every experiment.** For EXP-0204 the smallest
   unique-in-both key was `(field, value, carrier, instr)` and it is reported as
   `key_unique: false` — duplicates are compared as **multisets**, never first-record-wins, so
   a disagreement hiding in a duplicate is not masked, but the key is coarser than the
   `(arm, byte_index, value)` ideal because EXP-0204's records carry no `byte_index`.

6. **Reversing or shuffling case order controls ordering artefacts, not carrier blind spots.**
   Gate E's further clause — *"for load-bearing inertness or a surprising semantic claim,
   require a genuinely different carrier or second method as well"* — is **NOT satisfied by
   this experiment for any row**, and specifically not for the inertness rows
   (`tex_write.amode`, `tex_write.rsv11`, and every EXP-0206 field, all of which its own
   scorer calls `accepted-inert in tested envelope`). This experiment can move those rows past
   the *quiet* clause and no further.

7. **Only Gate E was re-run.** Gates A, B, C and D are inherited from each source experiment
   and were not re-audited. §3.3 shows one inherited Gate A failure (`dstsrc = 0x80`) that a
   Gate-E-only experiment surfaces but does not fix, and §4.1 shows one Gate B control arm
   whose own reproducibility is now in doubt.

8. **The device was not fresh and could not be made fresh.** ~22 100 accumulated resets were
   already on it. The `twdyn` result (§2.2, §2.3) bounds that confounder — the isolated arm is
   clean at the same accumulated count at which the full run aborts — but it does not remove
   it, and a successor with a genuinely rebooted device should re-take §2.3.

9. **The phase 5 repeat captures were designed after seeing that B1 was an outlier.** They are
   labelled characterisation and are excluded from the Gate E arithmetic, which uses the pair
   designated in the frozen contract. A reader who believes repeat-until-agreement is what
   happened should note that the *designated* pair still reads NOT MET for
   `tex_write.amode`, and that the extra captures were used to make the failure **more**
   precisely stated, not to erase it.

10. **I stopped a whole stage on a premise the next measurement refuted.** At 00:56Z I killed
    stage 6C, reasoning from stage 6B that ~64 expected hangs exceeded a ~20-hang cascade
    threshold. The AMENDMENT-04 probe — which I ran only to *generalise* that threshold —
    showed the threshold does not apply to that arm family at all, and stage 6C then completed
    cleanly on all three carriers well inside its declared budget. Had I not run the probe I
    would have shipped "stage 6C is unreachable" as a measured conclusion when six clean
    captures were 26 minutes each away. What saved it was running the generalisation check
    rather than trusting the generalisation.

11. **The health gate exists because a capture contaminated the next capture on a machine with
    no other GPU client at all.** The quiet gate cannot see that: the contaminating process was
    mine, and it was already dead. Any confirmation methodology that measures only *foreign*
    occupancy has this hole. Every capture after 00:58Z is preceded by a passing health gate;
    every capture **before** it is not, and the ones taken immediately after stage 6B — `H2`
    and `L1_cl_atomic` — are exactly the ones the gate would have refused.

12. **I wrote one line into a file that is not mine, and only `git status` caught it.** The
    command that launched stage 6C read
    `cd <expdir> && export SSHPASS=… && nohup python3 harness/drive.py … & echo launched; sleep 20; cat >> PROGRESS.md <<EOF`.
    The `&` backgrounds the **whole** `cd && export && nohup` list, so the `cd` applied only to
    the background subshell and the foreground `cat >> PROGRESS.md` ran in the session cwd — the
    repository root. It appended one line to the **repo-root** `PROGRESS.md`. It was found in
    the final verification pass, verified to differ from `HEAD` by exactly that one line, and
    reverted; the root file is byte-identical to `HEAD` again and the line is re-recorded in
    this experiment's own `PROGRESS.md`. This is the `SUBAGENT_BRIEF` `&&`/`&` hazard in a form
    that brief does not list: the danger is not only that a chained step silently does **not**
    run, it is that it runs **in the wrong directory**. The mechanical check —
    `git status --porcelain | grep -v '^??'` must be empty — is what caught it, and it is the
    check to keep.

13. **The thing that would embarrass me most.** My own wall-clock cap was broken when I wrote
    it: `perl -e 'alarm N; exec @ARGV' sh -c "<cmd>"` sends SIGALRM to the shell and orphans
    the `python3` child, so a capped stage would have kept sweeping the GPU while I recorded
    it as stopped. I found it by reasoning about the process tree before stage 6A, not by
    running — which means that if the phases had been ordered differently I would have shipped
    a `RESULTS.md` sentence ("the stage exceeded its cap and was stopped") that was false.
    `AMENDMENT-01` is the record.

---

## 9. Defects found in other people's tools — reported, NOT fixed

This experiment was told not to touch `tools/agx-isa/`, `docs/`, `PROVENANCE.md`, or any other
experiment's files. Each of these is therefore a report.

1. **EXP-0204 `analysis/verdicts.py` cannot score any successor's captures, and overwrites its
   own experiment's committed verdicts if run.** Its gated-run set is hardcoded:

   ```python
   def is_gated(rid):
       return ("A2run" in rid) or rid.endswith("_C1") or rid.endswith("_C2")
   ```

   Every run id this experiment produced (`g17p_e0213_*`) is therefore classified
   `discovery, not gated` and silently **excluded from every gate**, so pointing it at 66
   complete quiet captures reproduces the old verdicts unchanged. It also writes
   unconditionally to `EXP-0204/analysis/field_verdicts.json`. **It was not run.**
   *Fix: take the gated-run set from argv (as EXP-0206's `verdicts206.py` already does) and
   take the output path from argv too.*

2. **EXP-0206 `analysis/verdicts206.py` writes its output next to itself**
   (`os.path.dirname(__file__)/gate206.json`), so a successor cannot use it without
   overwriting EXP-0206's committed `gate206.json`. Worked around by running a **byte-identical
   copy** from this experiment's own directory (§4.2). *Fix: `--out`.*

3. **EXP-0204's `harness/sync.sh pull` still tars the entire `raw/` tree** and will overwrite
   committed raw. This is the same defect EXP-0210 disclosed after it actually overwrote a
   committed file. It was **not used**; `harness/pull_run.sh` here pulls one named directory
   and refuses if the local directory already exists.

4. **EXP-0204's `--order shuffle` is not reproducible across processes.** The per-field
   permutation is seeded with `args.seed ^ hash(arm["id"]) ^ hash(fname)`, and Python's `hash()`
   of a `str` is salted per process unless `PYTHONHASHSEED` is set. Two invocations with the
   same `--seed` therefore sweep different orders. It does not affect any verdict here —
   agreement is keyed by value, not position, and the actual order is recorded per record —
   but `--order shuffle --seed N` is not a reproducible description of a capture.
   *Fix: seed with a stable hash (e.g. `zlib.crc32` of the arm id) or pin `PYTHONHASHSEED`.*

5. **Gate A: `tex_deriv.dstsrc = 0x80` fails EXP-0204's own actual-byte ledger** on all six
   arms in every capture that reaches it (§3.3). Requested 128, decoded back `None`.

6. **`not_written` is counted as a hard outcome by EXP-0210's comparator**, which is right for
   most arms and wrong for EXP-0206's synthesized mid-program `stop`, where "the program
   terminates and all 32 value words stay poison" **is** the expected payload. 75 such keys per
   `cl_leaf` / `cl_chain` capture are therefore excluded from the agreement percentage rather
   than counted as agreeing. `analysis/arm_agreement.py` reports them explicitly instead, and
   they agree 74/74 and 74/74.


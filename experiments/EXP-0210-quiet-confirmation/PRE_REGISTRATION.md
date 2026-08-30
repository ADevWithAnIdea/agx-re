# EXP-0210 — PRE-REGISTRATION (frozen before the first dispatch)

**Frozen at** repo revision `1ea484d3c37dffc884cb12d92de597cbfefdc41b`, working tree clean
(`git status --porcelain` empty), 2026-08-30, before any capture was dispatched.

**Target:** Apple A18 Pro / G17P, `192.168.170.254`, `AGXAcceleratorG17P`,
`applegpu_g17p`, 5 GPU cores, macOS 26.6 (build 25G5043d), `Mac17,5`, Metal family Apple9.

---

## 1. What this experiment is, and what it is NOT

This experiment produces **no new hypothesis and no new field claim.** It re-runs
**confirmation captures that already exist**, using each source experiment's **own committed
harness and own frozen contract, unchanged**, on a machine that is measured quiet, in order
to decide a single question per field:

> Does `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` **Gate E** now hold?

Gate E, quoted:

> Discovery sweeps may run concurrently. Promotion/confirmation runs may not rely on a busy
> machine sweep. Require two clean G17P runs in reversed or shuffled case order, with
> identical actual-byte ledgers and no victim/cascade evidence. For load-bearing inertness or
> a surprising semantic claim, require a genuinely different carrier or second method as well.
> Fault, hang, silent-no-write, and finite-limit overflow claims must be repeated in
> isolation. A malformed runner response is `measurement_failure`, never a hardware outcome.

**Explicitly out of scope.** No sweep is redesigned, widened, narrowed, or "improved". No
case matrix is altered. No label, no file under `tools/agx-isa/`, `docs/`, or
`PROVENANCE.md` is touched. No existing raw, contract, or verdict file is edited. If a
harness cannot run unchanged, the experiment is **skipped and reported as skipped**, not
repaired.

**A NOT-MET verdict is a first-class result of this experiment** and will be reported as
such. This pre-registration commits to that in advance so that a failure to reach MET cannot
later be presented as an inconclusive run.

## 2. Hypothesis (falsifiable)

**H1.** With every sibling experiment finished and captures strictly serialized, a
confirmation pair for each listed field can be taken with **zero foreign GPU processes**
throughout and **zero device resets** during the pair, and the pair will reproduce the
already-committed partition.

**Refuter R1.** Any of: a foreign GPU process observed in any sample during a capture; a
`recoveryCount` increase across a capture; a `bytes_match`/ledger mismatch; a cross-run
disagreement on a (arm, value) key that is not confined to a hard-outcome class; a
`measurement_failure` (malformed runner response). Any one of these makes that pair
**NOT MET**, and it is reported.

**Refuter R2 (the one that would falsify my own method).** If the quiet pair reproduces the
busy pair *exactly*, that is consistent with H1 but also with "the busy measurement was never
contaminated in the first place". This experiment therefore reports the quiet measurement and
the ledger/agreement comparison **separately**, and does not claim that quiet caused the
agreement.

## 3. Independent variable

Machine occupancy only: **serialized, measured-quiet** instead of **concurrent fan-out**.
Every other variable — harness, kernels, frozen case matrix, arm set, case order policy,
timeouts, tool tree — is held at the source experiment's committed values.

## 4. What "quiet" means here — the measurement, frozen in advance

`harness/quietsample.py` samples every **2.0 s** for the whole of every capture and appends
to an append-only JSONL. A capture is **QUIET** only if ALL of the following hold over its
samples:

| # | criterion | signal |
|---|---|---|
| Q1 | `n_foreign == 0` in **every** sample | process table, patterns = union of the seven experiments' own pattern sets |
| Q2 | `recoveryCount` **unchanged** from first to last sample | `AGXAcceleratorG17P` IOKit property — a device reset is exactly what manufactures `InnocentVictim` and hang cascades in a neighbour's capture |
| Q3 | `fLastSubmissionPID` never becomes a PID outside our own subtree | `AGCInfo` IOKit property; catches a foreign submitter whose process name matches no pattern |
| Q4 | at least one sample per 10 s of wall clock (sampler did not die) | sample count vs. capture duration |

Q1 reproduces the metric the fan-out itself recorded, so the numbers are directly comparable
with the busy measurements those experiments committed. Q2 and Q3 are hardware-side and do
not depend on guessing process names — they are the answer to the known weakness that
"`InnocentVictim` is not the only contamination signature".

**"Device Utilization %" is recorded but NOT a criterion**: measured constant at 100 on this
host with an idle GPU, zero submitters and Renderer/Tiler at 0, so it does not discriminate.

**Known, disclosed exception.** One orphaned process is present at freeze time: PID 7480,
`harness/gpuwatch.py --run g17p_20260830_run01 --interval 2`, EXP-0202's own **process-table
sampler**, ppid 1, left behind by a finished agent. It issues `ps` and does **no GPU work**;
it matches none of the GPU-runner patterns in Q1 and is not the GPU submitter in Q3. It is
**left running and not killed** — another experiment's process is not mine to kill — and is
disclosed in every sample and in RESULTS. If it is ever observed as `fLastSubmissionPID`,
that observation is reported and the affected capture is NOT MET.

## 5. Per-capture protocol (identical for every experiment)

1. Push the source experiment's committed harness to its own remote directory and **verify
   separately** (compare remote hashes; never trust `&&`) — the EXP-0179 rule.
2. Record a pre-capture quiet sample and the `recoveryCount` baseline.
3. Start `quietsample.py` on the neo.
4. Run the source experiment's **own** capture command, unchanged apart from a **new run id**,
   under a hard alarm wrapper.
5. Stop the sampler; record a post-capture sample and the `recoveryCount` final value.
6. Pull the new run directory into the source experiment's own `raw/` under the **new id**.
   Nothing existing is touched.
7. Repeat for the second capture in the **opposite / shuffled** order, per that experiment's
   own order option.
8. Run that experiment's **own** committed analysis over the new pair.

**Serialization is absolute:** capture *n+1* is not started until capture *n* has completed,
been pulled, and its sampler has exited. Only one experiment is in flight at any moment.

## 6. Cross-run agreement — how it is computed

Keyed by **(arm, value)**, with volatile timing fields excluded, per
`tools/agx-isa/wave_audit.py` as fixed on 2026-08-30. The earlier pooled-across-arms,
`gputime_ns`-inclusive key is a known checker defect (EXP-0202 §3.1) and is not used.

Each experiment's own `analysis/verdicts*.py` is run unchanged as the primary computation;
`wave_audit.py` is run as the arrival gate. Neither is edited.

## 7. Ledger comparison

Gate E requires **identical actual-byte ledgers**. For each pair this experiment reports:

- per-case `requested == decoded from actual bytes` counts;
- the multiset of `(arm, value) -> actual_bytes` from run A vs run B, and the exact count of
  keys that differ;
- distinct actual encodings per arm.

A ledger difference is a hard NOT MET for that pair, whatever the agreement number says.

## 8. Stopping rule and time budget

Experiments are attempted in this order, cheapest-first, so that a time-out leaves the
maximum number of *complete* confirmations rather than a set of partial ones:

`EXP-0203` → `EXP-0205` → `EXP-0202` → `EXP-0201` → `EXP-0199` → `EXP-0206` → `EXP-0204`.

If a capture exceeds its alarm, it is recorded as an incomplete capture, **retained under its
own id, never topped up or reused**, and that experiment is reported NOT REACHED or PARTIAL.
Experiments not reached are named explicitly.

## 9. Recovery

If the neo stops answering: **STOP and report BLOCKED**. `macvdmtool` is forbidden to this
agent without exception.

## 10. Clean-room

```text
Clean-room provenance: HW-PROBE (re-running our own committed harnesses) + black-box
                       IOKit property reads for the quiet measurement
Inputs inspected: this repository's own committed harnesses, kernels and raw; IOKit
                  registry PROPERTY VALUES published by the driver (data, not code)
Apple binary introspection: NONE
```

No Apple binary is disassembled, decompiled, symbol-dumped or debugged anywhere in this
experiment. `ioreg` prints driver-published registry properties; that is the sanctioned
black-box data observation of CLAUDE.md allowed-technique 1, not code introspection.

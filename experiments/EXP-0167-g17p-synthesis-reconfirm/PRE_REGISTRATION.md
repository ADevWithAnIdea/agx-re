# PRE-REGISTRATION — EXP-0167, G17P generator-synthesis RE-CONFIRMATION under isolation

**Frozen 2026-08-30T07:52Z, before any device operation of this experiment.**
Target: **A18 Pro / G17P**, `users-MacBook-Neo.local` (`192.168.10.243`), macOS 26.6,
`Mac17,5`, `AGXAcceleratorG17P`, 5 GPU cores.

Repo revision at freeze: `47fd53f6afd3a2a51c5dbad1500e39cb8822b904` (8 files dirty —
sibling experiments in flight; **this experiment is NOT gated on live `HEAD`**, per
`SUBAGENT_BRIEF.md`: a capture is valid if the *authored blob hashes* in §8 match).

---

## 1. The question

`EXP-0158` reports that **233 of 237** generated programs containing **zero copied fields**
produced their exact host-computed oracle on G17P and never produced a wrong value. That is
the direct test of `CLAUDE.md`'s Definition-of-Done rules 1 and 6 — a value *generated*, not
decoded from a captured Apple template — and `EXP-0112`'s equivalent number was 0.

**But EXP-0158's own pre-registered cross-run gate FAILS.** Its `verify.py --captured`
(byte-identity of `01_results.jsonl` across the two gated runs) does not pass; its strict
"matched in every run" figure is **149**, not 233; 51 and 70 cases respectively returned
`kIOGPUCommandBufferCallbackErrorInnocentVictim` after five in-case retries; and its
witness-gated re-confirmation found **102 of 174** cases returning MIXED outcomes across five
runs of byte-identical programs. Its RESULTS.md §4 and §7 name the cause: **8–12 sibling GPU
experiments were running on the same device**, and it left the gate failing rather than
relaxing it.

Two independent experiments corroborate that the contamination is worse than `InnocentVictim`
alone. `EXP-0160` found a contaminated dispatch can report `STATUS OK` and write **nothing**
(25 observations with all 16 registers *and* both sentinels still poisoned, no
`InnocentVictim` string anywhere), and that re-running for confirmation *without* isolation
**manufactures** faults (`imad` v=186: `silent_zero` in both gated runs, `fault` 3/5 unlocked).

> **The question this experiment answers: re-measured on a quiet machine, does the 233 survive
> — and does the cross-run gate pass?**

This is a re-measurement of *conditions*, not of *artifacts*. Nothing about the programs
changes (§2).

## 2. What is held byte-identical, and the proof

The generator, the emitter, the case matrix, the carriers, and the pinned ISA snapshot are
copied from `EXP-0158` **byte for byte** (§8 hashes). The **only** semantic edit anywhere is
`run.py`'s two run-id strings (`g17p-20260830-run03/run04` → `g17p-20260830-iso01/iso02`) and
its accompanying comment, so this experiment cannot write into EXP-0158's append-only `raw/`.

Verified before freeze, by building the corpus in both trees and hashing it:

| | n | SHA-256 of the concatenated program hex |
|---|---|---|
| EXP-0158 | 289 | `f08d598832ea7bbb5ad90f32a9c52cd6cd9402d3bf9cf52ac6dc047f259e4e87` |
| EXP-0167 | 289 | `f08d598832ea7bbb5ad90f32a9c52cd6cd9402d3bf9cf52ac6dc047f259e4e87` |

**The 289 programs are the same 289 bytes-for-bytes.** Any difference in outcome is therefore
attributable to the machine, not to the corpus. `EXP-0158/` is not modified or re-run.

## 3. The metrics, defined before the run

All four are computed by `analysis/summarize.py` (copied byte-identical from EXP-0158, so the
definitions cannot drift) plus `analysis/compare.py`. `Z` = the **237** cases that carry zero
`COPIED` provenance fields and were pre-registered to match. `A` = the **28** cases
pre-registered to FAIL.

| id | metric | definition | EXP-0158's value |
|---|---|---|---|
| **M1** | STRICT-PAIR | cases in `Z` with `match == True` in **both** gated runs, no revalidation credit | **96** |
| **M2** | MATCHED-EVERYWHERE | EXP-0158's published strict figure: `summarize.py`'s `HEADLINE_N_zero_copied_and_correct` | **149** |
| **M3** | ATTRIBUTABLE | `summarize.py`'s `HEADLINE_ATTRIBUTABLE_N`: produced its exact oracle ≥ once, and NEVER a wrong value / silent zero / no-write | **233** |
| **M4** | CROSS-RUN GATE | `verify.py --captured`: `01_results.jsonl` **byte-identical** across the two gated runs | **FAIL** |

M1/M2/M3 are recomputed here by the identical code on this experiment's own runs; EXP-0158's
column above was recomputed from its committed `raw/` before freeze, not copied from prose.

## 4. Hypotheses and the committed numbers

**H1 (primary, committed).** On an isolated machine the STRICT-PAIR count **M1 ≥ 225** of 237.
*Refuter:* M1 < 225. EXP-0158's M1 is 96, so this predicts a ≥ 129-case improvement caused by
nothing but removing sibling load.

**H2 (committed).** **M2 ≥ 229** of 237.

**H3 (committed).** **M3 ∈ [229, 237]** — the attributable count reproduces within 4 of 233.
The 4-case allowance is not arbitrary: it is the number of cases (§6) whose EXP-0158
attributable verdict rests on a *single* `ok` observed only in a revalidation or
re-confirmation pass, and which isolation could therefore legitimately overturn.

**H4 (committed).** **M4 PASSES** — `verify.py --captured` reports `01_results.jsonl`
byte-identical across `iso01` and `iso02`.

**H5.** All **28** pre-registered-to-FAIL cases still fail, and the 4 known `IADD_SYNTH`
failures still fail. *Refuter:* any adversarial case matching, which would mean the match test
has stopped being able to detect a difference.

### 4.1 The honest-lower branch — pre-committed, not to be explained away

If **M3 < 225**, the conclusion is: **EXP-0158's 233 was contamination-inflated**, its
attributable rule was too permissive, and the defensible number for DRV-ISA-01 / P0.6 is this
experiment's, not EXP-0158's. That is a first-class result. It will be reported as the
headline, every program whose verdict changed will be named individually, and no post-hoc
metric will be introduced to recover a larger figure.

Symmetrically, if M1 stays low (**< 200**) *while* the sampler shows a quiet machine, then
contention was **not** the explanation for EXP-0158's failing gate, and the nondeterminism is
a property of this corpus or this harness. That too is reported as the headline, with the
fault-class strings and the sampler record as the evidence, and it would place a much larger
caveat on the 233 than EXP-0158 does.

### 4.2 Named watch list — the 20 programs most likely to flip

Derived from EXP-0158's committed `raw/` **before** this run. **19** cases in `Z` produced no
`ok` in *either* gated run and reach their attributable verdict only via a revalidation or
re-confirmation observation:

`dag_009_n11`, `dag_010_n12`, `dag_012_n14`, `dagi_016_n20`, `dagi_019_n26`, `dagi_023_n35`,
`regb_R000`, `regb_R031`, `regb_R047`, `regb_R063`, `regb_R063_poison_r63`,
`regb_R005_extlsb1`, `inl_k01`, `inl_k08`, `inl_k12` (the 15 with no wrong value anywhere),
plus the 4 known real failures `iaddsyn_A33_B44_N13_D9_sub`, `iaddsyn_A127_B1_N15_D10_add`,
`iaddsyn_A11_B22_N1_D95_add`, `iaddsyn_A7_B120_N4_D47_add`.

Plus one singled out: **`dag_040_n20`** — `ok` in run03, `victim` in run04, and **`fault` 5/5
in the witness-gated re-confirmation**. It is counted inside EXP-0158's 233 on the strength of
one `ok`. Under isolation it must resolve one way or the other, and either resolution is
informative.

*Pre-committed:* these 20 are named **now** so that a flip cannot later be presented as an
expected detail. Any of them changing verdict is reported individually in RESULTS.md.

## 5. Independent, controlled, and confounding variables

- **Independent variable: concurrent GPU load on the target.** Nothing else changes.
- **Controlled:** the 289 programs (byte-identical, §2); the emitter and pinned ISA snapshot;
  the carriers; the case order; the poisoned `0xDEADBEEF` read-back buffer; the integrity
  sentinel; the per-case fresh process; the 5-retry `InnocentVictim` policy; the cascade
  witness every 40 cases; the majority-of-3 revalidation pass; the same target machine, OS,
  and toolchain.
- **Confounder C1 — self-inflicted contamination.** The corpus deliberately contains cases
  that fault (`regb_R126_faultarm`, `regb_R127_faultarm`, `adv_iadd_dst_reg96`, and the
  `iadd2` r0 case). A genuine fault triggers a device reset that can make *our own* next case
  an `InnocentVictim`, which would break byte-identity even on a perfectly isolated machine.
  This is pre-registered as the leading alternative explanation if H4 fails; it is
  distinguished from sibling load by the sampler (§7) showing zero foreign harness processes,
  and by the victim positions clustering immediately after our own known-fault cases.
- **Confounder C2 — a neighbouring context's hang.** The orchestrator reports that EXP-0163
  hit a real `kIOGPUCommandBufferCallbackErrorHang` at ~00:42 from the encoding `iter_at` with
  `grp=0x50`. That is ~7 hours before this run and outside the window, but any reset observed
  without a matching foreign process in the sampler must be considered against it.
- **Confounder C3 — oracle-value ambiguity.** `classify_word` tests `got == expected` before
  the zero test, so a case whose oracle value is exactly `0.0` cannot distinguish "computed 0"
  from "silently zeroed". Measured before freeze: **3** of the 237 have an entirely-zero
  oracle. Inherited from EXP-0158 by design (the artifacts are held identical) and reported as
  a limitation, not fixed here.
- **Confounder C4 — thermal/DVFS state.** Not controlled; recorded only via load average.

## 6. Method (frozen)

1. **Sampler first.** `harness/gpuwatch.py` starts on the target **before** any device
   operation and runs continuously to the end (§7). A ≥ 3-minute pre-window baseline showing
   `n_foreign == 0` is a **precondition**: if any foreign `agxrun`/`shdump`/`agxtest`/
   `agxparse`/`persistrun` process, or any python under a non-`EXP-0167` `EXP-NNNN` path, is
   sampled before the start, the run does not start and the orchestrator is told.
2. **No lock is taken.** `~/agxre/gpulease.sh` is a neutralised pass-through shim as of
   2026-08-30 (`shift 2; [ "$1" = "--" ] && shift; exec "$@"`) and takes no lock —
   **EXP-0158's own run03/run04 went through that same shim**. Isolation is established by
   the orchestrator quiescing the other device agents and **verified** by the sampler. No new
   lock is built (orchestrator decision, 2026-08-30).
3. **Gates, then two gated runs, in EXP-0158's own contracted order:**
   `verify.py --selftest` → `--seqtest` → `--preflight` → `baseline.py` → smoke →
   `run.py --run-id g17p-20260830-iso01 --execute` → `verify.py --between-runs` →
   `run.py --run-id g17p-20260830-iso02 --execute` → `verify.py --captured`.
4. **Witness-gated re-confirmation** (`harness/reconfirm.py`, 5 reps, witness before every
   observation) over the scope fixed in §6.1.
5. `analysis/summarize.py` and `analysis/compare.py` produce M1–M4 and the per-program
   agreement table.

### 6.1 Re-confirmation scope — fixed now, so it cannot be chosen after seeing the data

The re-confirmation set is the **union**, in this order:

  (a) the **20 named watch cases** of §4.2 — unconditional;
  (b) **every case whose outcome in `iso01` or `iso02` is not `ok`**, whatever the reason;
  (c) if and only if time in the window permits, a **stratified top-up**: the first 20 cases
      of each of the 8 families in case-index order, to give a contention-free stability
      baseline on programs that already passed.

(a) and (b) are mandatory; (c) is optional and is reported separately, never merged into M1–M3.

### 6.2 Timeouts, watchdogs, budget

Unchanged from EXP-0158 (`CASE_TIMEOUT = 60 s` per case; 45 s inside `case_exec.py`; 20 s
`--run-timeout` inside `agxtest`; 300 s host build; 900 s per gate). Sampler `--max-seconds`
14400. Total window budget **90 minutes**; if it runs long the orchestrator is told rather
than the pass being cut short. **Every raw record is appended + `fflush` + `fsync` as it
completes** — a kill costs at most one case. `PROGRESS.md` is written after every milestone
and `raw/` is pulled back to the repo incrementally.

### 6.3 Stop conditions

- Any foreign harness process sampled during a gated run → the run is **retained**, flagged
  contaminated in `raw/`, and **not** used for M1–M4; a replacement takes a **new** run id.
- Two genuine hangs outside the known-fault cases → stop that arm, report PARTIAL.
- The target stops answering → **STOP and report BLOCKED**. No `macvdmtool`, no scanning.
- A pre-capture smoke defect → pre-capture stop, `raw/` never created (EXP-0158's own logic).

## 7. Isolation evidence (the deliverable EXP-0158 could not produce)

`harness/gpuwatch.py` samples the process table every **2.0 s** and appends one JSON object per
sample to `raw/isolation/*.jsonl`, recording: every `agxrun|agxrun_persist|shdump|agxtest|
agxparse|persistrun|MTLReplayer` process and every python process whose args name an
`EXP-NNNN` path, each classified **mine** vs **FOREIGN**; `MTLCompilerService` counted
separately with its `%cpu` (idle XPC instances are normal on this host and are **not**
contention); and the system load average. It reads `/bin/ps` and `sysctl` only — no GPU, and
no Apple binary introspection.

**Pre-committed claim:** RESULTS.md will state the number of samples taken, the number of
samples with `n_foreign > 0`, and the maximum concurrent foreign process count observed. If
that maximum is not 0, the isolation claim is withdrawn and the run is reported as a second
contaminated run — worth nothing, and said plainly.

## 8. Frozen artifact hashes (SHA-256)

```
ac589715343f8b86991aa5d0593e548a8651169406e0fd2c01805908c48118e5  synth.py
bf4d04b83aada377a6166ace9a3f26e5974bce7c10c7a4a3f21790e99e2b69e2  generator.py
06c924c14d908bc0ad61f49525c62f14981d4f8fff22f66e83e8d90a69141536  families.py
6f037600619a06cb15aa35341edd7d0674d1118303172c2c5b68ded50878eead  cf.py
07f1dd44a3d7d6daac089ed9be426ce95b5ee64b5c174688d61b17e5a8027c48  casematrix.py
64dbe829b4a561ebeb44f749051399236f6c6b85e0e9f7ba4381cfb4a6ad6957  frozen_pilot.py
904f0c40cb04963428a345ff3dd590b3f711100f064a31609ce3548d9f6c7fa4  baseline.py
f2514217f1d21a36da307e0d56205d42fa301744ef4235224fd2ce1769ec2a30  make_manifest.py
825c9c90a305ff92735f7740b844074a6d6b28a2e6ddb98095f005902b310539  run.py            (run ids ONLY)
2c6e883ff2c0cc8fd59bc387d121b3f2165df586d0f46e00a2cb9942a0956f98  verify.py
6280900408b5ec89e261b5e12916dc2de24eba732c3a5b3152d299d71badb933  harness/build.sh
a900e4eef361715c5dff8922b3d3fea09971d7e679b9a3e2ceeb43636eb321a1  harness/case_exec.py
a53877bfd7f407ad8f317f54726c199297694bd6fed7ae7f278ad91ffd253272  harness/reconfirm.py
fc5d8c4e80cc971882c1903ddae3a65cb51283b5544accc49a2e45107be96dba  harness/gpuwatch.py       (NEW in EXP-0167)
de0b0d76fabac18ef5689b46fc0531c7720cb21dfbc99771a814325c0c21a0ee  harness/recorded_fixture_case0.json
ed4b7bfef443a813d6e835efb0f34174e7d3c6e64f3e2e79db99630c089b08b4  kernels/carrier_dag.metal
49740e671e78c571ba8c8deaa9cf990dad1e2c96a7c63e2322f9e23a21477726  kernels/carrier_cf.metal
418d780ca2920a7235deb55878b4e5e82563f2370c6ce6f9fea7d05643e7c91f  work/isadb_pinned/db.json
1d60d36d2da7b681028c201013a510603d8fb7909bb59186e7534296e3b6e0d1  work/isadb_pinned/isadb.py
efbcaf28c2d9e581921bd3a6c567bb3a36d01f810cfdf6595e956c615e5cf55e  analysis/summarize.py
```

Every hash except `run.py`, `harness/gpuwatch.py` and (post-freeze) `analysis/compare.py` is
**identical to the corresponding file in `EXP-0158`**, checked before freeze.

## 9. What this experiment does NOT do

- It does **not** attempt to close the 24 donor-dependent cases (12 `CF`, 12 immediate-mode
  `iadd2`). That is a named follow-on and is only touched if the confirmation finishes early;
  it would be a **separate arm**, reported separately, never traded against the confirmation.
- It does **not** revisit EXP-0158's `ld_format`, `iadd2.srcA` or `falu2.mod_hi` corrections.
- It does **not** edit `docs/`, `PROVENANCE.md`, `tools/`, or anything under `EXP-0158-*`.
- It does **not** promote anything to `docs/`; the orchestrator owns that.

## 10. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: EXP-0158's own authored generator/emitter/harness code and carrier MSL,
  copied byte-identical (hashes in section 8); a PINNED, hash-recorded snapshot of this
  repository's own tools/agx-isa isadb; this experiment's own gpuwatch.py and compare.py;
  the target's own process table via /bin/ps.
Apple binary introspection: NONE.
Reproduction: README.md's command sequence.
Evidence: raw/g17p-20260830-iso01/, raw/g17p-20260830-iso02/, raw/isolation/,
  work/reconfirm/, analysis/.
```

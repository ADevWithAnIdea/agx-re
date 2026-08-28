# EXP-0144 progress log (append-only)

## 2026-08-27 — session 1 (killed by the account session limit, not by a failure)
- Built `work/bin/{shdump,agxrun_persist}` from the READ-ONLY repo tool sources
  (`harness/build.sh`). No tool source edited.
- Wrote `kernels/anchors.metal` (16 own-MSL entry points) and located the compiler's
  own encoding for 8 of the 9 target instructions by tokenizing our own compiled
  `_agc.main` with `tools/agx-isa`. **`packed_half2_hi` could not be provoked from MSL**
  at all (every packed-half2 shape tried yields `half_alu` + a 4-byte `0x18`-leader
  companion, never `byte+2==0x24`) -> it will be tested MODE A (synthesised).
- Learned and recorded: a **constant** buffer index makes the compiler hoist the whole
  body into the uniform datapath, leaving `_agc.main` with no convert at all. All
  carriers therefore index by `thread_position_in_grid`.
- Wrote `kernels/carriers.metal` (9 carriers), `harness/probe.py`, `harness/oracle.py`
  (self-test PASS), `harness/casematrix.py` (24,328 cases), `harness/run.py`.
- Validated every carrier's unspliced baseline against the host oracle on hardware.
- Pilot control (`work/pilot/control.log`): splicing genuinely reaches the hardware;
  `pack_convert` byte+9 0x82->0x42 switches unorm->snorm, byte+8 0x45->0x00 disables the
  conversion entirely. Throughput ~2400 dispatches/s.
- Smoke run `work/smoke/smoke01` (400 cases, NON-RECORDED): runner end-to-end OK.
- **Nothing was captured under `raw/`.** No partial capture exists to retain.

## 2026-08-28 — session 2 resume
- Re-oriented from disk (this file did not exist yet; written now as the first act).
  `raw/` empty, harness/kernels/work intact, repo at `5a9df52b`, my dir committed at
  `4fe49a1c`.
- Read the NEW `FIELD-SWEEP-PROTOCOL.md` sections 7-8 (concurrent-sweep contamination).
  Batch 2 = EXP-0140, EXP-0144 (this), EXP-0147.
- run03 analysis exposed TWO harness faults, both costly:
  (a) carriers ran in ALPHABETICAL order, so when the MODE-A `packed_half2_hi`
      arm cascaded the GPU the run stopped with `unpack_convert` -- the #1
      priority instrument -- entirely unrun (all 3,956 of its cases skipped);
  (b) a cascade set a GLOBAL stop instead of stopping just the sick carrier.
  Fixed: priority carrier order (c_pack, c_unpack first; the dangerous synthesised
  c_ph2 LAST) and a cascade now stops only that carrier -- which IS protocol 7.3's
  "resume in a fresh process", because every carrier gets its own runner child.
- run04 retained but unusable: launched immediately after run03's cascade, the GPU
  had not recovered and it cascaded at case 12105 after 57 s. Runs now get a
  settle gap. PARTIAL.md written.
- run05 launched with the corrected ordering.
- **2026-08-28 HOST EVENT.** run05 died at 8,412/22,237 cases. Sequence: a GPU
  wedge (watchdog fired, `no response within 8.0s`) during the
  `unpack_convert.convert_desc` whole-field arm -> persistrun killed and tried to
  restart its child -> the child could not start because
  `MTLCompilerService` was unreachable ("The process is unavailable because the
  compiler is no longer active. Latest invalidation reason: Connection init failed
  at lookup with error 141 - Reentrancy avoided").
  This is a HOST SERVICE failure, not (necessarily) a GPU wedge, and it is
  host-wide: a fresh `shdump` compile fails the same way, so EXP-0140 and EXP-0147
  are affected too. Three experiments were driving the Metal compiler concurrently.
  Per CLAUDE.md: NOT thrashing, NOT attempting any tool-based reboot, never
  macvdmtool. run05 is retained as a partial capture.
  State at the event: run03 COMPLETE (7 of 9 instruments measured, unpack_convert
  and most of packed_half2_hi lost to the alphabetical-order bug); run05 had
  completed pack_convert in full and unpack_convert up to its W arm.
- **Self-caught harness defect (documented, NOT patched mid-experiment).** The
  arm-C "baseline" case for the MODE-A target passes `splices={}` despite its own
  comment saying MODE-A baselines splice the synth. So `baseline_packed_half2_hi`
  measured the UNSPLICED carrier (`900405000020`), not the synthesised
  `packed_half2_hi` (`980424000020`). Patching `casematrix.py` now would change the
  frozen matrix hash and break comparability with run03/run05, so it is recorded as
  a defect for a successor. No information was lost: `sem_packed_half2_hi_00` runs
  the synth on the SAME fixed vector and is the real MODE-A positive control.
- That control is a genuine POSITIVE result: the synthesised `packed_half2_hi`
  EXECUTES and computes the packed-half2 multiply **for the high lane only**,
  leaving the low lane untouched (zero), reproducibly across all 4 semantic
  vectors. That matches the instruction's name and explains why the compiler emits
  `half_alu` (low half) plus a 4-byte 0x18-leader companion as a pair.
- Analysis pipeline complete: verdicts.py (gate + byte scans + format maps +
  dst-redirect detection), predicates.py (exact 1-3 bit predicate search),
  rules.py, field_verdicts.py. On run03+run05: **44 of the 51 blocking fields at
  emitter grade** (35 hardware-run, 9 isolated-byte-diff), 7 untested.
  Pending: the second capture that gates the cvt_* cluster and unpack_convert.

## 2026-08-28 — REVALIDATION (coordinator: run03/04/05 disagree, do not promote)
- Verified the host: MTLCompilerService recovered, carrier baseline reproduces the
  oracle 3/3.
- **Diagnosed the reported divergence.** The coordinator measured run03 vs run04
  outcome-diff = 12,943/22,237 (58.2%) and run03 vs run05 = 43.8%. Decomposed:
  * run03 vs run04: 12,861 of the 12,943 (99.4%) are cases where exactly ONE side
    was a never-dispatched SKIP PLACEHOLDER. Among cases both runs actually
    measured: **14 of 3,751 differ (0.37%)**.
  * run03 vs run05: 2,046 of 2,057 likewise; both-measured: **4 of 6,292 (0.06%)**.
  * run04 vs run05 share **zero** both-measured cases.
  Cause is MY schema defect: skipped cases were written with `outcome:"hang"`, so an
  outcome-only comparison sees catastrophic divergence. run04 is still genuinely
  contaminated (it cascaded 57 s in and skipped 18,486 cases) and stays unused.
- The 18 genuinely-disagreeing cases are ALL fault/hang boundary cases -- exactly
  what majority-of-N is for. Proceeding with the revalidation as instructed.
- Wrote `harness/revalidate.py`: majority-of-3, escalating to 5 when the reps
  disagree; per-attempt OS fault string; InnocentVictim attempts discarded and
  re-run; sentinel-absent attempts discarded and re-run; baseline re-validation
  every 100 cases (EXP-0141 cadence) with a cascade stopping the shard; verdict
  `indeterminate` when no majority exists. **Schema fixed**: a never-dispatched case
  now records `outcome: null`, `validity: "not_run"`.
- Smoke (250 cases, NON-RECORDED): 247 unanimous at 3 reps, 3 escalated to 5 and
  resolved by majority -- e.g. `f_pack_convert_b0_f7` voted fault 2 / silent_zero 3.
  A single observation would have called that value `fault` ~40% of the time.
- Launched `m4_20260828_rv01` as 9 per-instrument shards.

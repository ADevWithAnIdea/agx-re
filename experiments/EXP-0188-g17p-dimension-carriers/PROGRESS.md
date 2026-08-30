# EXP-0188 — PROGRESS

Append-only. One entry per milestone, so a kill costs at most one milestone.

## 2026-08-30 — M1: pre-registration frozen (before any build or device time)
- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`, `experiments/FIELD-SWEEP-PROTOCOL.md`
  (all of it, §3/§5/§7 included).
- Selected **4 of the 9** offered fields, by whether the dimension can actually be BUILT:
  `if_push.scope` (region kind), `iadd2.b2_fmt` (operand format/width),
  `simd_ballot.cache` + `simd_shuffle.cache` (execution-mask bank / divergence depth).
  Declined `iter.b9`, `imageblock_store.b4`, `frag_color_store.store_mode`, `vtx_out_pos.slot`
  (all need a render/vertex harness for a PIPELINE-STATE dimension) and `cvt_f2i.b9`
  (EXP-0184 spanned its dimension today). Reasons in `PRE_REGISTRATION.md` §2.
- Authored 18 carriers across 3 MSL files; host oracles simulate our own MSL and assert every
  expected value is NON-ZERO and never collides with the poison.
- `CAPTURE_CONTRACT.json` frozen, 21 blobs. Repo revision pinned `45d97d62`.
- Nothing has run on the device yet.

## 2026-08-30 — M2: census, pilot, hazard probe (all PRE-FREEZE calibration)
- Pushed, `verify_remote.py` run as its OWN step: **18/18 blobs match on the device**; built
  `shdump` + `agxrun_persist` on the neo.
- **Census: all 18 carriers compile and all 18 emit their target instruction — 0 dropped.**
  108 arms, 9734 cases.
- **`if_push` REACHED THE LOOP-ITERATION REGION KIND.** `scope_kind` spans **26 (0x1a loop_iter),
  33 (0x21), 37 (0x25), 41 (0x29)** across the six loop carriers — the dimension EXP-0184 named as
  the one thing that could overturn its verdict. `scope` itself takes **both 0x54 and 0x56** in
  `cf_nl2`, `cf_nlif`, `cf_wbrk`, `cf_lcont`: the compiler varies the field along this axis by
  itself, which is the strongest available proof that the carrier set can express it.
  **0x29 is not in `db.json`'s `scope_kind` enum** — recorded as a db defect candidate.
- `simd_shuffle` byte+2 takes **both `cache` = 0 and 1** in our own carriers (EXP-0163 saw 0x54
  only). `simd_ballot.cache` is 0x54 in all 15 occurrences. `iadd2.b2_fmt` is **21 (=0x54>>2) in
  every one of the seven operand formats**, including 16-bit, 64-bit, immediate-srcB and uniform.
- Pilot `raw/prefreeze/pilot01` (retained, partial, **killed on purpose**, never reused or topped
  up): CF oracles verified `ok` at baseline; found that off-baseline `scope` values on the first
  loop-iteration push FAULT or HANG.
- Hazard probe `raw/prefreeze/haz01` (88 cases, 33 s, req-timeout 1.0 s): **4 of 22 occurrences
  fault at `scope` 0x00 and 0x54 and run correctly at 0x56 and 0xFF** — i.e. the 0x02 bit is
  load-bearing there. 18 of 22 are clean at all four values. 0 hangs at a 1 s watchdog.
- **COURTESY NOTE (protocol §7):** the gated pair will dispatch ~512 known-hazardous `if_push`
  values, some of which hang and reset the device. EXP-0187 is running concurrently
  (`agxrun_persist_as` seen in the process table). Sweeps stay unlocked per §7; this is the
  advance warning that hangs from EXP-0188 are expected in the next ~30 minutes.
- Contract amended to **v2** (v1 retained in `raw/prefreeze/`); `verify_remote.py` re-run as its own
  step: **21/21 match**.

## 2026-08-30 — M3: the hazard measured, the gated pair re-scoped, pair started
- `raw/g17p_20260830_run01` — started, then **killed within seconds** because its console output
  had been redirected to a path outside the repo. Self-disclosed; the file (83 bytes, an SSH
  host-key warning, no evidence) was removed and the run id was **retired, not reused**.
- `raw/g17p_20260830_run02` — started at a 2 s watchdog and **killed after 71 s / 27 records**,
  which is the measurement that sized everything after it: **7 hangs and 6 faults in the first arm,
  ~8 s per hang case**. Retained as-is; never topped up.
- **The hazard is real and it is BIT 1.** Four `if_push` occurrences — the FIRST push of `cf_nl2`,
  `cf_nlif`, `cf_wbrk`, `cf_lcont`, every one of them a `scope_kind == 0x1a` **loop-iteration**
  region — fault or hang at `scope` values with **bit 1 clear** (0x00, 0x54) and run **correctly**
  at values with bit 1 set (0x56, 0xFF). The other 18 occurrences are clean at all four.
  This is `if_push.scope` MOVING, on exactly the region kind EXP-0184 could not reach.
- Amendments **A3/A4**: gated pair re-scoped to `harness/arms188_gated.json`, 62 arms / 4086 cases.
  **No hang budget is reinstated and there is still no abort path** (protocol 3c): one hazardous
  occurrence keeps the FULL dense 256-value map, the other three keep a four-value replication
  inside both gated runs, clean occurrences are reduced to five spanning all four observed
  `scope_kind` values, SIMD carriers to one occurrence each. Every dropped arm is listed with its
  reason in the file. `verify_remote.py` re-run as its own step: **24/24 match**.
- Gated pair `g17p_20260830_run04` / `run05` started sequentially at a **1.2 s** watchdog
  (recorded in each `env.json`).

## 2026-08-30 — M4: BLOCKED. The neo stopped responding mid-gated-pair.
- Timeline: `run06` (gated pair, A3 scope) sat at 0 scored cases for ~3 min, stuck in the FIRST
  carrier's `shdump` compile while three orphaned `agxrun_persist` children from earlier kills were
  still resident. Killed it, split the arm set into `arms188_cf.json` (18 arms / 1440 cases) and
  `arms188_rest.json` (44 arms / 2394 cases) so the control-flow result could land first, and started
  `run08`→`run09`→`run10`→`run11` sequentially. `run08` reached `carrier_ready` and then the host
  went away.
- **Confirmed unresponsive, not merely slow:** 3 × SSH connect timeout at 20 s, `ping` 3/3 lost
  (100 % packet loss), `users-MacBook-Neo.local` no longer resolving. The orchestrator independently
  confirmed the same plus **no ARP entry**.
- **`macvdmtool` was NOT run and no reconnection or address scan was attempted.** Per
  `SUBAGENT_BRIEF.md` this agent stopped and reported BLOCKED; recovery is the orchestrator's.
- **Run ids started, all now DEFECTIVE BY DEFINITION and none to be reused or topped up:**
  `prefreeze/pilot01` (killed on purpose), `prefreeze/haz01` (**complete**, 88 cases),
  `g17p_20260830_run01` (retired seconds in), `run02` (killed at 27 records), `run04` (killed),
  `run06` (0 scored cases), `run08` (in flight at the wedge). `run05`, `run07`, `run09`, `run10`,
  `run11` never started.
- **All of it is LOST**, not stranded: `raw/` was never pulled back, and the orchestrator has directed
  that nothing be retrieved. Inventory + regeneration commands: `raw/prefreeze/STRANDED_MANIFEST.md`.
  A console transcript of the census and hazard probe is committed as
  `raw/prefreeze/console_census_hazard.txt`, **explicitly labelled as a transcript, not primary raw**.
- **Cause NOT attributed.** EXP-0187 was sweeping deliberately-faulting `n4_rt_word.dst` values and
  recorded 187 `InnocentVictim` responses in one run; EXP-0188 was dispatching hanging `if_push`
  encodings with no abort path. Either or both. Recorded as unresolved.
- **No field is promoted.** All four targets keep `single-template-inference`.
  `analysis/field_verdicts_flat.json` says so per field, with what was and was not dispatched.

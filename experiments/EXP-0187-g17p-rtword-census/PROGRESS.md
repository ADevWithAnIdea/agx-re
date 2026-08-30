# EXP-0187 — PROGRESS

## M1 — pre-registration frozen, harness verified on the device (2026-08-30)

* Pinned `db.json`, `isadb.py`, `agxparse.py`, `persistrun.py`, the **upstreamed**
  `saferunner.py`, `shdump.m`, plus EXP-0135's `shdump_mesh.m` / `mesh_extract.py`
  into `pinned/`, resolved by absolute path with a hard exit if absent.
* Authored 8 intersection_query carriers (`kernels/k_rq187.metal`) and 26 census
  constructs (cube / divergent-CF / mesh).
* **Census (target 1), on the device:** all 8 carriers compile and all 8 emit
  `n4_rt_word` — **32 parcel-aligned occurrences**, 3–5 per carrier, two distinct
  compiled `dst` baselines (`0x42` on seven carriers, `0x22` on `rq_inst`), i.e.
  both selector values `db.json` records from the corpus. Each carrier also has
  14 aligned `rt_query_traverse` occurrences for the carrier-level control.
  **3 of 32** occurrences are followed by an `if_push` (`rq_inst`), giving a
  same-program-point control; that matches `db.json`'s own provenance for this op.
* **Tokenizer walk stops at 60–62 tokens on every RT carrier**, so `walk` hits
  for `n4_rt_word` are 0 — a tokenizer limitation on intersection_query programs
  (EXP-0157 measured the same), NOT evidence of absence. Recorded, not hidden.
* **Pilot (`raw/prefreeze/pilot01`, 371 cases, 4.1 s):** harness end-to-end OK —
  8 carriers ready, sentinel present, poison tail intact, 0 hangs, 0 malformed.
  It found one defect: **my `rq_multi` host oracle was wrong** (124 vs the 121 the
  unmutated program returns in all 37 baselines). Corrected pre-freeze and
  documented; the gate compares against the arm-open baseline, never the oracle.
* Arms frozen: **211 arms / 10 272 cases** — 32 dense 256-value target arms, 64
  whole-word liveness probes, 3 same-program-point controls, 112 carrier controls.
* `CAPTURE_CONTRACT.json` frozen (27 blobs); `harness/verify_remote.py` run as a
  SEPARATE unchained step: **25/25 blobs match on the device**.

## M2 — gated runs

* **run01** (pre-amendment 211-arm set) — killed by the DRIVING SESSION's 2-minute command timeout,
  not by the device; the remote process kept writing and reached 2284 records. **Retained, never
  paired**: it executed a different arm set from the frozen contract (EXP-0179's stale-harness
  failure). Its first 180 cases showed a 25 % fault rate and are the reason for the scope amendment.
* **Scope amendment** recorded in `analysis/gen_arms.py` (not applied silently): 4 carriers × 1
  occurrence, full dense 256 values each, controls trimmed to the occurrences the pilot measured as
  firing → 25 arms / 1276 cases. Contract re-frozen (v4); `verify_remote.py` re-run as a separate
  step: **25/25 blobs match**.
* **run02** — the one COMPLETE gated run: 961 cases, 248 s. `rq_bbox` `carrier_start_failed`;
  the other three carriers ran fully. **128 faults on `n4_rt_word.dst`, exact rule
  `(dst & 0b110) == 0b100`, identical on `rq_mdist#0` and `rq_inst#0`.**
* **run03** — died at `dst = 0x4c` on `rq_bbox#0` after three `ErrorHang` command-buffer errors.
  80 records, retained as a partial.
* A sibling experiment (**EXP-0188**) was dispatching on the device throughout, recorded as a
  measurement; 187 `InnocentVictim` responses in run02 alone.

## M3 — target-2 census complete

31 constructs compiled, 0 failures. `cubearray_coord_const` **0/31** (bounded negative);
`mesh_out_src` **EMITTED** for the first time (`mesh_wide` mesh stage, 1 walk-confirmed occurrence);
`n4_cf_word` signature-only in 8 constructs, 0 walk-confirmed.

## M4 — analysis and write-up

`analysis/field_verdicts.json` (flat, per FIELD-SWEEP-PROTOCOL §5) records
`n4_rt_word.dst` as **NOT-GATED / `untested`** — not rounded up, because one complete run is not two.
`analysis/census.json` carries target 2. `RESULTS.md` written. **0 instructions moved across the
emittable line.**

## M5 — the neo stopped answering (2026-08-30, after all evidence was pulled back)

Immediately after the final pull, `192.168.10.243` stopped responding: **100 % packet loss on ping
and SSH connect timeout**, twice, ~25 s apart. **STOPPED and reported BLOCKED per the dispatch;
`macvdmtool` was NOT run** — recovery is the orchestrator's job and the tool is forbidden to
subagents without exception.

**No evidence was lost.** `raw/` (all three runs plus the pre-freeze census and pilot),
`analysis/census.json`, `harness/arms187.json` and `work/` were all pulled back into this repo
before the host went silent, and `manifest.json` hashes all 46 files.

**Context for whoever recovers it, since a reproducible wedge is itself a hardware fact:** this
experiment's last device activity was a dense sweep of `n4_rt_word.dst` on the bounding-box
intersection-query carrier, where run03 had already died at `dst = 0x4c` after three consecutive
`ErrorHang` command-buffer errors, and a sibling experiment (**EXP-0188**) was dispatching
concurrently throughout. The 64-value hazard class `(dst & 0b110) == 0b100` produced 368 `ErrorHang`
classifications in run02 alone, all contained at the time. **Which of the two workloads wedged the
host is NOT established here** — both were live, and this experiment cannot separate them.

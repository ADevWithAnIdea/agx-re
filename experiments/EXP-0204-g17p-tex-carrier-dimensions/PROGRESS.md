# EXP-0204 progress log (append-only)

All times UTC. Target: A18 Pro / G17P at 192.168.170.254. Nothing runs on the M4.

- **11:52** experiment directory created; `tools/agx-isa/db.json`, `isadb.py`,
  `tools/shdump/agxparse.py` pinned into `pinned/` (db sha256 `2412eac1…`, 172 instructions /
  1040 fields).
- **11:56** 13 carriers authored in `kernels/` (6 for `tex_sample.mode` spanning the
  sample-operation class, 2 for `tex_deriv.dstsrc`, 5 for `tex_write.{amode,rsv11}` spanning
  address form and write-data format). `harness/gfrun4.m` forked from our own EXP-0172 `gfrun2.m`
  with five new surfaces (mipmapped sampled texture; mipmapped / cube / texture-buffer / R32 / RG32
  writable destinations). `harness/runner4.py` forked with the FIELD-SWEEP-PROTOCOL §3(d) per-child
  reader-thread fix.
- **12:01** `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` FROZEN (repo revision
  `f59821fe`, dirty flag recorded). No device run had happened.
- **12:04** built `work/gfrun4`, `work/shdump` on the neo.
- **12:06** pre-freeze census run1: `mscmp` failed to compile (Metal forbids `compare_func` with
  `coord::pixel`); four carriers reported no occurrence because forward tokenization stops early.
  Amendments A1–A3 (PRE_REGISTRATION §14).
- **12:12** pre-freeze census run2: **all 13 carriers build and every target instruction is
  located.** `tex_sample.mode` baselines are 0x10 / 0x00 / 0x20 across the carrier set — all three
  documented values appear as compiler choices. `tex_write.amode` baselines are 0x54 **and 0x55**.
  `tex_write.rsv11` is 0 on every occurrence including the 1- and 2-component destinations.
- **12:20** arm list generated and frozen: **28 arms** (10 `tex_sample`, 6 `tex_deriv`,
  12 `tex_write`) across all 13 carriers.
- **12:26** `work/smoke_smoke01` (calibration): 588 cases, 0 hangs, 7.3 s. All 28 arms have
  detection power AND a moved control in the target field's own dimension. Host-computed baseline
  oracle matches exactly on every sample and deriv arm; `checked=0` on the write arms → amendment A5.
- **12:33** `work/smoke_smoke02` (calibration): host baseline oracle now **52/52 channels on the
  four constant-destination write carriers and 28/28 on the two dynamic ones**.
- **COURTESY NOTICE (FIELD-SWEEP-PROTOCOL §7):** `tex_deriv.dstsrc` runs as a **named
  hang-tolerant MAPPING PASS** with a budget of **8 hangs per arm** instead of 2. EXP-0172
  reproduced device hangs at `dstsrc` = `0x3FFFF` and `0x7FFFF` and its budget of 2 stopped every
  arm at 39 of 65 values. Siblings seeing `InnocentVictim` during EXP-0204's `tex_deriv` arms
  should consider this experiment a likely cause.
- **19:13** gated `raw/g17p_20260830_run01` started under the ORIGINAL §8 gate. Killed by an SSH
  hang-up at **404 cases**, no run manifest. **RETAINED as a discovery sweep, never topped up,
  never reused, and excluded from every Amendment-2 gate.** It did complete `tex_deriv@deriv/0` at
  **65/65** values — the first full sweep of that value set (EXP-0172's budget of 2 stopped it at
  39/65) — and its hazard map is real evidence.
- **19:35** the user added `RE_EXPERIMENT_PROCESS_CORRECTIONS.md`. It is normative and wins.
  Redesign frozen as **Amendment 2** (`PRE_REGISTRATION.md` §15) BEFORE its first dispatch:
  Gate A actual-byte ledger in `gfrun4.m` (`ACTUAL` + `PROGHASH`, re-read from the dispatched
  file), Gate C independent semantic predictors in `oracle.py`, Gate E case-order control
  (`--order forward|reverse|shuffle`), six verdict axes.
- **19:52** `raw/g17p_20260830_A2run01` — tex_sample + tex_write, forward order: **9276 cases,
  0 hangs, 0 cascades, 0 runner restarts, 137.7 s.**
- **19:57** `raw/g17p_20260830_A2run02` — same arms, **reverse** order: **9276 cases, 0 hangs,
  0 cascades, 0 restarts, 39.0 s.**
- **20:05** `tex_sample.mode`: the pre-registered class model is **REFUTED** and replaced by an
  exact bit rule on the six 100 %-agreement arms (`analysis/mode_bits.py`).
- **COURTESY, and it happened:** `raw/g17p_20260830_A2run03_derivmapping` — the declared
  hang-tolerant mapping pass — produced **7 genuine device hangs** between roughly 20:00 and 20:12
  UTC while sweeping `tex_deriv.dstsrc`. Siblings seeing `InnocentVictim` in that window should
  consider EXP-0204 the likely cause. It completed **65/65 values on both arms** (`complete: true`),
  which the budget of 2 could never have done.
- **20:13** `raw/g17p_20260830_A2run04_derivmapping` launched, reverse order, same two arms.
- **MACHINE-QUIET MEASUREMENT: every run so far is BUSY.** `procs.jsonl` records 0 quiet samples in
  every run; EXP-0199, EXP-0200, EXP-0205 and EXP-0206 were dispatching throughout. **Gate E's
  clean-confirmation requirement is therefore NOT MET so far**, and no verdict in this experiment
  claims `independently-confirmed`.
- **20:20** `raw/g17p_20260830_A2run03_derivmapping` complete: **65/65 values on BOTH arms**
  (`complete: true`), 7 genuine hangs, 0 cascade. `raw/g17p_20260830_A2run04_derivmapping`
  (reverse order): `deriv/0` 65/65, `deriv2/0` stopped at 30/65 on the declared 8-hang budget
  (reverse order reaches the all-ones hazard family first). **73/73 cross-run agreement** on the
  comparable values, 72 moving.
- **20:25** `raw/cube_probe` complete, 512 hardware cases. `analysis/cube_decode.py` (offline)
  settles the orchestrator's open question about the descriptor: `f0 c0 04 <b3>` decodes as
  `cubearray_coord_const` standalone and at a trailing 4-byte boundary, but is **shadowed by
  `pad_operand`** at an interior one. **Neither probe site has detection power**, so `b3` stays
  UNRESOLVED exactly as pre-registered.
- **20:30** `analysis/verdicts.py`, `analysis/mode_bits.py`, `analysis/manifest.py` and
  `tools/agx-isa/wave_audit.py` all run; `analysis/wave_audit.txt` kept verbatim. Its self-test
  passes and none of its three warnings (constant oracle, V<=1, aliased encodings) fires.
- **GATE E: a quiet-window confirmation attempt is RUNNING** — `harness/quietconfirm.sh 1500 3`
  polls the device process table and fires `--run-id g17p_20260830_C1` (shuffled order) and
  `…_C2` (reverse order) **only** after three consecutive samples with zero foreign GPU
  processes; otherwise it exits non-zero and Gate E stays NOT MET. Foreign process count fell
  from 17 to 3 over the window but **never reached 0 in any of its 86 samples**. The attempt was
  then stopped so that the committed state matches `manifest.json` exactly, and its full log is
  retained as evidence at `raw/quietwindow/quietconfirm.log`. **GATE E IS NOT MET, and no field in
  this experiment is `independently-confirmed`.** If the orchestrator later gets a quiet window,
  `sh harness/quietconfirm.sh` fires the pair as `g17p_20260830_C1` / `_C2` and
  `python3 analysis/verdicts.py` picks them up automatically — the run-id filter already accepts
  those ids — and only then may any field move to `independently-confirmed`.

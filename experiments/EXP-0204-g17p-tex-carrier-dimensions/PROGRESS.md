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

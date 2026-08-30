# EXP-0160 — PROGRESS

Append-only milestone log. Times are host (M4) local, 2026-08-29/30.

| time | milestone |
|---|---|
| 23:22 | Dispatch read. Verified all eight target fields against `tools/agx-isa/{db.json,validation.json}`: none closed by a sibling. `falu2_ext.ctrl` and `falu2i.ctrl_lo` are `tokenization-only`; `imad.srcC_desc` and `half_pack.src` are `corpus-correlation`; the other four are `untested`. |
| 23:25 | Desk analysis of EXP-0154's committed raw (`analysis/prior_scan.py`) — six of the eight were already swept densely on G17P and still came back `untested`. |
| 23:30 | `analysis/design_check.py` (desk, no hardware): the failures are MODEL-CLASS and DENSITY failures, not data failures. Four fields have a 0-exception class table over ≤5 relevant bits; `falu3.op`/`falu3_ext.op` satisfy an exact mask `(v & 0xd7) == 0x16` and failed only density; `imad.srcC_desc` fits neither. |
| 23:33 | Authored `kernels/probes.metal` (8 kernels, incl. the new `k_addimm` for the falu2i anchor EXP-0154 never had) and `kernels/carrier_dag.metal`. |
| 23:36 | Harness written: two seed sets, poison-based framing detection, `confirm_faults.py` for §7A isolation, pinned toolchain copies. `PRE_REGISTRATION.md` frozen. |
| 23:37 | Pushed to `~/agxre/EXP-0160`; anchors extracted on G17P. All eight anchors resolve; `half_pack` anchor confirmed `18 03 18 05` and `falu2i` anchor `09 c9 14 01 80 c0`. |
| 23:38 | `CAPTURE_CONTRACT.json` frozen: 4064 cases, matrix sha256 `f2a2fec3…`. |
| 23:39 | Smoke capture `raw/g17p_20260830_smoke01` (40 cases, retained): harness correct — falsifier fires, `ctrl=0` produces a 9-word poison framing break exactly as predicted, and seed set 2's baseline `r0 = 0.625 = saturate(0.25+0.375)` matches the independent host oracle. **But 32 of 40 cases were `…ErrorInnocentVictim` discards and 4 real `…ErrorHang`s came from a sibling.** |
| 23:41 | Decision recorded: run BOTH gated sweeps under `~/agxre/gpulease.sh`. At an 80% victim rate an unlocked run would not survive the cross-run gate. Protocol default is unlocked; the measured contamination is the documented reason for the exception, and the smoke capture is the evidence. run01 launched, queued behind EXP-0158's lease. |
| 23:45 | `experiments/NEO-TARGET-BRIEF.md` and `FIELD-SWEEP-PROTOCOL.md` §7B updated on disk mid-experiment: **the GPU lease is removed**, and "a bulk sweep NEVER takes the lease". Killed the queued lease waiter (six agents were queued behind EXP-0158) and ran both gated sweeps unlocked, as the current protocol requires. |
| 23:47 | **run01 complete** — 4064 cases in ~2 min. `{ok 923, wrong_value 2366, silent_zero 521, fault 254, hang 0, victim 206, sentinel_bad 18}`. Pulled to `raw/g17p_20260830_run01/`. |
| 23:49 | **run02 complete** (reverse arm order) — 4064 cases. `{ok 924, wrong_value 2484, silent_zero 528, fault 128, hang 0, victim 92, sentinel_bad 7}`. Pulled to `raw/g17p_20260830_run02/`. Zero GPU hangs in either run; zero baseline failures. |
| 23:50 | §7A fault adjudication launched (`confirm_faults.py`, 5 reps per suspect case, unlocked per the new brief). |
| 23:52 | Preview analysis on the gated pair alone: **`falu2i.ctrl_lo`, `iminmax.srcB`, `isel8.cmp_mode`, `half_pack.src` already reach `hardware-run`**; the other four fail P2 (density) only because their fault-class values are still awaiting the isolated verdict. |
| 23:55 | **`half_pack` split probe settles DEF-0154-1.** `__split_at0and2` (both 2-byte halves replaced by our own `mov_imm`s) writes r6=77 AND r7=99 — the positive control proving the probe can see a difference. `__split_at2` alone is `ok` (the spliced `mov_imm` never executes). So bytes +2..+3 are CONSUMED by the instruction at +0: `half_pack` is a genuine 4-byte instruction, and H7 (two 2-byte half-lane instructions) is **REFUTED**. |
| 23:56 | **`imad.srcC_desc` mechanism found.** `r0 = m(v)·(srcA·srcB) + A(v)` explains **181/181** non-fault values with **0 exceptions** across both seed sets. `A(v)` is seed-independent and its recovered values are exactly the 16-bit halves of THE CARRIER'S OWN float constants (`0x3F800001` = 1.0000001f → 1 and 16256; `0xB3D6BF95` = −1e-7f → 49045 and 46038), not of the probe kernel's `+12345`. The addend is therefore **not an inline immediate**. |

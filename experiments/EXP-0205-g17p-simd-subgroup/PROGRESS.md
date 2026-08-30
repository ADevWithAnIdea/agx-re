# EXP-0205 progress log (append-only; one entry per milestone)

## 2026-08-30 ~11:55 UTC — dirs, kernels, harness authored (PRE-FREEZE)
Created `experiments/EXP-0205-g17p-simd-subgroup/`. Pinned `db.json`, `isadb.py`,
`agxparse.py`, `shdump.m`, `agxrun_persist.m`, `persistrun.py`, `saferunner.py`
into `pinned/` so a mid-run edit to a shared tool cannot change what this
experiment measured. Authored `kernels/k_ballot.metal`, `kernels/k_reduce.metal`,
`kernels/k_shuffle.metal`.

## 2026-08-30 ~11:59 UTC — pushed + built on the neo (192.168.170.254)
`shdump` and `agxrun_persist` built from the pinned sources under
`~/agxre/EXP-0205/work/bin`. Device answers as `Apple A18 Pro`.

## 2026-08-30 ~12:02 UTC — PRE-FREEZE CALIBRATION run (raw/prefreeze/)
`analysis/calibrate.py`, 11 carriers, all `STATUS OK`, all sentinels present,
all tails still poison. Results that CHANGE the design before the freeze:

1. **MEASURED SIMD WIDTH = 32** (`threads_per_simdgroup` read back per lane;
   lane ids 0..31, one simdgroup at tg=32). Recorded, not assumed.
2. **Every carrier contains EXACTLY ONE occurrence of its target descriptor**,
   parcel-aligned, and the pinned tokenizer agrees it is that instruction. No
   occurrence-selection ambiguity anywhere.
3. **`simd_ballot.pred` is 0 on BOTH the ballot-of-predicate carrier and the
   active-mask carrier.** db.json models byte+1 high nibble as
   `0x07 = active_mask/any/all` vs `0x17 = ballot(predicate)`; our own compiler
   emits byte+1 = 0x07 for BOTH forms on G17P. What differs is byte+5
   (`psrctype`, 0x00 vs 0x02) and the byte+7..9 tail (`58 22 12` vs
   `08 02 18`). The pre-calibration oracle "pred=1 -> ballot mask" is therefore
   REFUTED before any sweep and has been replaced; the sweep now tests the
   falsifiable H1 below instead.
4. **`simd_active_threads_mask()` inside a divergent `if` returned 0xFFFFFFFF**,
   not the divergent lane mask. Either the compiler predicated the region rather
   than diverging, or the mask reports resident rather than executing lanes.
   Recorded as an open question; the frozen oracle for that carrier is the
   calibrated all-ones value with the refutation stated.
5. **`simd_shuffle.cache` already has TWO baseline values from the compiler
   itself**: byte+2 = 0x56 (cache=1) on `sh_bc`/`sh_xor` and 0x54 (cache=0) on
   `sh_reuse`, and both produce the correct broadcast.
6. `simd_shuffle.dir` model CONFIRMED at both baselines before any splice:
   `sh_bc` (0x47) gives every lane lane-5's value, `sh_xor` (0xC7) gives lane t
   lane (t^5)'s value, and both matched the host oracle exactly.
7. `simd_reduce` opcls is 1 on the three int carriers and 0 on the float
   carrier, and the db enum's pair ordering is NOT opcls order (opcls=1 gives
   `isum` and `smax`, the FIRST names of their pairs; opcls=0 gives `f32sum`,
   the SECOND name of its pair). The oracle is anchored on the measured
   baselines and a named semantic catalogue instead of on the enum text.

Consequent design change (still pre-freeze): add `sb_ballot2`, a second ballot
carrier with a different predicate mask, so that any movement under `pred` can
be attributed — a result that still tracks the predicate is ballot-like, one
that is 0xFFFFFFFF on both masks is active-mask-like.

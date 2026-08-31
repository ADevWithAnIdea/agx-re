# EXP-0213 — AMENDMENT-02

**Frozen before phase 6's first dispatch. Designed AFTER seeing phase 1 and phase 5 data, and
therefore explicitly NOT Gate E evidence.**

## What is added

`work/plan_phase6.json`: one capture, `g17p_e0213_R6_cold_tex_write_twdyn_0`, taken after a
**declared ≥ 35-minute idle** with no GPU work of any kind.

## Why

`tex_write.amode` at `tex_write@twdyn/0` disagrees on 31 of 256 values between capture `B1`
and **eight** other captures (B2, B3, R1–R5, and the committed busy `A2run01`), which all agree
with each other 256/256. B1 was the **first GPU dispatch of the session**, on a machine that
had been idle for four hours. The only hypothesis left standing after phase 5 is a
**cold-device / first-dispatch effect** — a hypothesis I formed from the data, not before it.

Phase 6 is the cheapest available attempt to refute it: idle the GPU, then take the same arm
first, and see whether B1's payload comes back.

* **If R6 reproduces B1** on those 31 values → the effect is reproducible and the disagreement
  is attributable to device thermal/DVFS state at first dispatch, not to the encoding.
* **If R6 matches the other eight** → the hypothesis survives only for idle periods much
  longer than 35 minutes, i.e. it is **not confirmed**, and B1 stays an unexplained singleton.
  A 35-minute idle is not a four-hour idle, so this outcome is weak evidence, and it will be
  reported as weak.

## What this amendment does NOT do

It does not change the Gate E pair designation (`B1 × B2`, frozen before any capture ran), any
budget, any exclusion, the agreement key, or any verdict. `tex_write.amode` reads **NOT MET**
under the designated pair regardless of how phase 6 comes out.

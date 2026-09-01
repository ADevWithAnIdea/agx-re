# Progress

- 2026-08-31: experiment allocated and H1/H2/H3 frozen before any EXP-0224 hardware dispatch or
  fresh FMA compilation.
- 2026-08-31: disclosed pilot `g17p_e0224_pilot01` completed 22 dispatches. H3 was exact in 4/4;
  H1/H2 were rejected by complete-state source destruction; both refuters fired; zero faults,
  hangs, Gate-A errors, aliases, or donor fields. Work paused at user request before V2.
- 2026-09-01: work resumed. `AMENDMENT-01.md` freezes the H3 retained-source point and the V2
  promotion matrix before any V2 dispatch.
- 2026-09-01: formal run01 rejected V2: 136 exact positives and two firing refuters, but all 88
  cases built around multiple high-register operands were wrong-value. Zero faults, resets,
  Gate-A errors, aliases, donors, or sentinel failures. `AMENDMENT-02.md` freezes P2 to distinguish
  high-register encoding from pending-load/group timing before any P2 dispatch.
- 2026-09-01: P2 proved all 48 low-source cases exact. High-source behavior was mixed and not fixed
  by a 64-instruction gap. `AMENDMENT-03.md` freezes a 200-case V3 low-bank emitter contract; high
  values are staged through the separately proven `n3_mov` recipe.
- 2026-09-01: V3 formal run03/run04 passed: 198/198 positives exact and two refuters fired in each,
  zero cross-run differences, faults, resets, Gate-A errors, aliases, donors, sentinel failures,
  or foreign runners. Recovery count remained 27689. `RESULTS.md` publishes the recipe.
- 2026-09-01: EXP-0236 separated pending-load state from ordinary GPR reach and proved all three
  materialized sources direct r0..r63 with high descriptors aliasing modulo 64. `AMENDMENT-05.md`
  corrects the old r0..r15-only materialized-source claim without altering EXP-0224 raw evidence.

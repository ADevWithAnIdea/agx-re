# EXP-0146 progress log (append-only)

- **2026-08-28 M0** — Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`. Diffed
  `tools/agx-isa/validation.json` against `db.json` for the twelve dispatched mnemonics; read
  `EXP-0102-m4-int-pack-semantics/RESULTS.md` (INT-13/INT-14 carry chain) and the
  `APPLE9_RE_IMPLEMENTATION_GAPS.md` "P0 — 64-bit integer behavior" section (I64-01..06).
- **2026-08-28 M1** — Built `work/bin/{shdump,agxrun_persist,agxrun}` from the read-only tool
  sources. Authored 26 MSL carriers in `kernels/`. Ran the **non-mutating** compile+disassemble
  pilot (`work/pilot/disasm.py` -> `raw/pilot/carrier_disasm.txt`): carriers located for
  `carry_gen`, `ilogic`, `irotate`, `mov_zext16`, `shift_amt_move`, `n3_mov`, `n2_op6`,
  `n2_op8`, `n2_op10`, `sfu_marker` and the 64-bit `iadd2`. No own-MSL carrier found for
  `sr_read_wide` or `int_alu_ehi` (carrier search pre-registered).
- **2026-08-28 M2** — `PRE_REGISTRATION.md` frozen (rev `3efd06c6`).
- **2026-08-28 M3** — Harness smoke test: all 12 carrier baselines match their host oracles
  (`work/pilot/smoke.py`), ~0.8 ms/case. Splice efficacy PROVEN (`work/pilot/splicecheck.py`):
  `iadd2` byte0 `0x9f -> 0x1f` turns `a+b` into `b-a` on the real GPU, and `ilogic` byte0
  `0x0b -> 0x0a` faults the command buffer. A harness self-test run is retained at
  `raw/trial00/` (arm `K_sfu_marker` only) — it is NOT one of the two gated runs.
- **2026-08-28 M4** — **run01 complete: 18786 records, 0 hangs.** All 19 I64 functional
  baselines exact against host oracles.
- **2026-08-28 M5** — **Testbed non-determinism measured and disclosed**
  (`raw/pilot/testbed_flake_rate.txt`, `work/pilot/flakecheck.py`): 12 fresh runner processes x
  100 **identical, unmutated** baseline dispatches = 1200 dispatches, of which ~6 (~0.5%)
  returned a wrong result (usually all-zero, once a contained fault). Three of run01's twelve
  arm baselines hit exactly this. Consequence: **no single case may be promoted on one
  observation.** Mitigation: run02 is a byte-identical independent repeat, and a third
  adjudication pass (`run03`) re-tests every run01/run02 disagreement 5x.

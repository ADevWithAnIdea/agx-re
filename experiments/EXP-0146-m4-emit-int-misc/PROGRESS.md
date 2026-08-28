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
- **2026-08-28 M6 (post-resume)** — Re-oriented from `PROGRESS.md`, `PRE_REGISTRATION.md` and
  `raw/`: `run01` and `run02` were both complete (18787 records each). Applied the new binding
  `FIELD-SWEEP-PROTOCOL.md` §7 requirements: `harness/run_sweep.py` now records the OS
  command-buffer error string and a `fault_class` per case.
- **2026-08-28 M7** — **`run02` reclassified as CONTAMINATED** (it overlapped ~2400 of my own
  flake-check dispatches; passes 3-4 of `raw/pilot/testbed_flake_rate.txt` measured the effect at
  up to 22 wrong answers per 100 identical dispatches vs 0-6 per 1200 when idle). Retained
  append-only, excluded from the gate. **`run03` captured as the clean second gated run**
  (18787 records). Gate `run01` vs `run03`: 17924/18773 agreed (95.48%).
  Fault classes in run03: 689 `innocent_victim`, 369 `hang`, 194 `fault`, 2 other.
- **2026-08-28 M8** — **`run04` adjudication complete**: 1735 cases (all 849 disagreements plus
  every case either gated run scored `fault`/`hang`), 5 serial repetitions each, verdict taken
  from non-`innocent_victim` repetitions only, unmutated baseline re-validated 97 times with 17
  failures each forcing a fresh runner process. **0 unresolved cases remain.**
- **2026-08-28 M9** — **`run05` second-method probes.** P1: the native 64-bit ADD confirmed on a
  SECOND independent boundary input set, 5/5 repetitions — falsifier F3 resolved **positive**.
  P2: `carry_gen.dst` x `psel` (1536 combinations) found no alternative working pair, so
  "dst names a re-pointable predicate register" is NOT established. P3: the second `mov_zext16`
  carrier emitted no `mov_zext16` — arm void, question left open. P4: `sr_read_wide` FOUND in our
  own ray-query kernel; `int_alu_ehi` ABSENT again (EXP-M4-13's negative reproduced).
  **`run06`**: the ray-query carrier executes but returns all zeros (no acceleration structure
  can be bound), so `sr_read_wide` is not live on the output path and was NOT swept.
- **2026-08-28 M10** — Analysis and deliverables written: `analysis/field_verdicts.json`
  (94 entries + 10 `db_defects`), `analysis/ilogic_lut_table.md`, `analysis/I64_answers.md`,
  `analysis/field_maps.json`, `analysis/bit_rules.json`, `RESULTS.md`, `README.md`,
  `manifest.json`. **47 of the 60 db.json fields in the dispatched cluster are `hardware-run`;
  all six I64 items answered (I64-03 PARTIAL).** Note for the orchestrator: `raw/` totals ~29 MB
  of plain JSONL (three 9 MB gated captures); it is append-only evidence, so the retention
  decision is yours.
- **2026-08-28 M11** — Housekeeping: removed `__pycache__`, documented `work/` as regenerable
  scratch (`work/README.md`) and confirmed it contains only compiles of our own
  `kernels/*.metal` plus plain input buffers — no Apple binary, blob or precompiled shader.
  Verified with `git status` that **none** of `tools/`, `docs/`, `PROVENANCE.md`,
  `APPLE9_RE_IMPLEMENTATION_GAPS.md`, `CODEX.md`, `CLAUDE.md` or the protocol files were
  modified, and that **nothing was committed**.

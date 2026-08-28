# PROGRESS — EXP-0114 m4-texture-deferred

- T0 (pre-registration): read EXP-0106/EXP-0094/EXP-0095, CODEX/CLAUDE/SUBAGENT_BRIEF. Piloted
  (in `work/`, not committed as evidence) the TEX-15 texture-selector-field question: found the
  gap-doc's "0-127 selector" framing was based on a false premise (op+4 is a reused
  register-like slot, not a stable per-resource ID) via a sparse-declared-index own-shader-diff
  test. Piloted the gradient-operand differential with varying-routing (bias's proven technique)
  instead of buffer+tid addressing: 16 differing bytes (down from 116), 2 individually
  splice-causal offsets (+33/+63), reproduced at a second register assignment.
- T1: built `harness/texsplice.m` (compute+texture splice runner) and `harness/gradsplice.m`
  (render+mip-texture splice runner) — neither existing `tools/agxtest` runner supports texture
  binding. HW-validated both against hand-spliced pilots before freezing the contract.
- T2: froze `PRE_REGISTRATION.md`, generated `CAPTURE_CONTRACT.json` (49 cases: 8 diff, 31
  splice_tex, 10 splice_grad).
- T3: ran `verify.py --selftest` / `--seqtest` — see RESULTS.md for outcome.
- T4: captured `m4-20260828d-run01`, `m4-20260828d-run02` — all 49 cases correct, but
  `analysis/analyze.py` caught a missing `authored_sha256` key (`run.py`'s `env_record()` bug).
  Quarantined (`QUARANTINE-20260828d.md`), fixed, recaptured as `m4-20260828e-run01`/`-run02`.
- T5: wrote RESULTS.md against the `e`-run pair; discovered `gen_contract.py` had incorrectly
  hash-pinned `README.md`/`RESULTS.md`/`PROGRESS.md` into capture-time provenance (they're meant
  to be written/edited after capture). Quarantined the `e`-run pair
  (`QUARANTINE-20260828e.md`), fixed `gen_contract.py`, recaptured as `m4-20260828f-run01`/
  `-run02` — same 49/49 `ok`, `repeat_exact: true`, all 5 gates PASS.
- T6: RESULTS.md finalized against the promoted `f`-run pair. Experiment COMPLETE for its 3
  covered items (TEX-15, TEX-16 splice half, gradient-operand field); 8 items explicitly not
  exercised (RESULTS.md §5).

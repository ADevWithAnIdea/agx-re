# EXP-0210 progress log (append-only)

| UTC | milestone |
|---|---|
| 2026-08-30T20:05Z | Read RE_EXPERIMENT_PROCESS_CORRECTIONS (Gate E, §9), SUBAGENT_BRIEF, NEO-TARGET-BRIEF, FIELD-SWEEP-PROTOCOL. Device reachable, load 0.42, **one orphan**: pid 7480 = EXP-0202's `gpuwatch.py` process-table sampler, ppid 1, no GPU work. Left running, disclosed. |
| 2026-08-30T20:10Z | PRE_REGISTRATION.md frozen at repo rev `1ea484d3c37dffc884cb12d92de597cbfefdc41b`, tree clean. Quiet instrument built (process table + IOKit `AGXAcceleratorG17P` properties: recoveryCount / fBusyCount / fLastSubmissionPID). Smoke test QUIET. |
| 2026-08-30T20:14Z | **EXP-0203** pair `g17p_q41`/`q42` captured (68 s each). `q42` QUIET; `q41` scored `n_foreign=2` — the two are **our own** `MTLCompilerService` XPC helpers, invisible to a ppid walk. Retained, never reused, **not** used for a Gate E verdict. |
| 2026-08-30T20:17Z | **AMENDMENT-01 frozen** (split `n_foreign_runner` / `n_compiler_svc`; Q1 restated on dispatch runners) **before** re-dispatch. |
| 2026-08-30T20:19Z | **EXP-0203** pair `g17p_q43` (forward) / `g17p_q44` (reverse) captured under the amended instrument. Both **QUIET**. Ledger identical 8410/8410; agreement 8410/8410 = 100.00%; 0 faults, 0 hangs, 0 victims. **Gate E MET.** |
| 2026-08-30T20:25Z | **EXP-0205** pair `g17p_quiet01/02` captured. `quiet02` scored `n_foreign_runner=1` on **1 of 18** samples — a single `(shdump)` **zombie**, our own, misattributed by a two-`ps` race. Retained, never reused, not used for a verdict. |
| 2026-08-30T20:26Z | **AMENDMENT-02 frozen** (one `ps` snapshot; ownership = ppid subtree ∪ session id) **before** re-dispatch. |
| 2026-08-30T20:28Z | **EXP-0205** pair `g17p_quiet03`/`quiet04` under amended instrument. Both **QUIET**. Ledger identical 5245/5245; agreement 5233/5233 = 100.00%; **0 faults** (the committed busy `runB01` had 1). **Gate E MET.** |
| 2026-08-30T20:29Z | SELF-DISCLOSURE: `analysis/verdicts.py` of 0203 and 0205 **rewrite their own `analysis/field_verdicts*.json` in place**. I ran them and they modified four committed files. Generated copies preserved under `EXP-0210/analysis/out/`, originals restored with `git checkout --`, verified identical to rev `1ea484d3`. `harness/run_analysis.sh` now does preserve-and-restore automatically. |
| 2026-08-30T20:29Z | SELF-DISCLOSURE: one early command wrote a throwaway log to `/tmp/x` (outside the repo) and deleted it. Rule is absolute; all scratch since then is under `EXP-0210/work/`. |

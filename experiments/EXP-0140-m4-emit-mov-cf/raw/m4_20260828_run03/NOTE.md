# `m4_20260828_run03` is a PARTIAL capture — retained, not topped up, not reused

7365 of the frozen matrix's 7960 cases. It has **no `01_summary.json`** because the driver did
not reach the end: the host's `MTLCompilerService` became unavailable
(`Connection init failed at lookup with error 141 - Reentrancy avoided`) while the run was
inside `ret.linkmode@12`, so `agxrun_persist` could not be started for the next carrier and the
process raised. All 28 periodic baseline re-validations taken before that point passed.

Groups absent or incomplete here, and therefore covered by only ONE gated run:
`ret.linkmode@12` (partial), `ret.scoreboard@12`, `jump_cond.offset`,
`pop_reconverge.reserved@14`, `pop_reconverge.reserved@15`.

Per `SUBAGENT_BRIEF.md` this file is left exactly as the driver wrote it. The replacement
capture for the missing tail was attempted under a new id and is recorded as BLOCKED in
`../../PROGRESS.md` (M14): the compiler service stayed down for the rest of the session.

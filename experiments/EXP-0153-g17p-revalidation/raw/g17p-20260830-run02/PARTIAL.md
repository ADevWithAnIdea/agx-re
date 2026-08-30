# PARTIAL CAPTURE -- RETAINED, NOT REUSED

This run stopped at case 215/258 of arm D_iadd2_dst (1731 records) and was
killed by the operator at 2026-08-30T05:41Z after ~10 minutes with no new
record.

Cause (diagnosed, not guessed): the persistent runner CHILD process
(agxrun_persist) had exited, and tools/agxtest/persistrun.py::request() then
busy-looped forever -- its read loop treats a line as unrecognised rather than
as EOF, so a dead child produces an infinite stream of empty strings. The
parent was observed at 61.3 % CPU in state RN with no agxrun_persist child of
its own in ps, while three sibling experiments (EXP-0154/0155/0156) had live
runners.

Per SUBAGENT_BRIEF ("a partial capture is retained, never reused") these 1731
records are kept exactly as captured and are NOT used as the second gated run.
The replacement was captured under the NEW id g17p-20260830-run03 with a
harness-side guard (run.py::GuardedRunner) that converts child EOF into a
wedge so the runner restarts instead of spinning.

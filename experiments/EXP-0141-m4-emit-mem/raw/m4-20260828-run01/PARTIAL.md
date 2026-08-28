# PARTIAL CAPTURE — RETAINED, NOT REUSED, NOT EVIDENCE FOR ANY VERDICT

`m4-20260828-run01` was stopped by me at **3240 of 20529 cases**, part-way
through arm `L_index_reg`, because of a HARNESS defect (not a device problem and
not a result):

`harness/sweeprun.py`'s canary loop treated a **genuinely and reproducibly
faulting** case as a run whose integrity sentinel was missing — which it
trivially is, because a failed command buffer returns no output at all — and so
spent 4 canary attempts x 3 confirmation attempts x N innocent-victim retries
(>= 12 GPU submissions, each with error recovery) on every real fault, and
labelled it `invalid_run` instead of `fault`. `device_load.index_reg` >= 96
faults reproducibly (3/3 attempts, non-innocent class), which is the known
r95/r96 boundary, so the arm turned into a fault storm.

Per `experiments/SUBAGENT_BRIEF.md` ("a partial capture is retained, never
reused"), this directory is left exactly as it was written. It is **not** topped
up, **not** deleted, and its id is **not** reused. The successor captures are
`m4-20260828-run11` and `m4-20260828-run12`, made after the fix
(a confirmed `fault`/`hang` short-circuits the canary and the outer
majority loop, since `issue()` has already reproduced it >= 2 of 3).

Its 3240 records remain readable and are internally consistent for the arms that
completed; they are cited nowhere in `RESULTS.md` or `analysis/field_verdicts.json`.

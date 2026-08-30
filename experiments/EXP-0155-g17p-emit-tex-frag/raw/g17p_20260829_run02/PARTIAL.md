# g17p_20260829_run02 — PARTIAL, RETAINED, NOT REUSED, NOT USED FOR PROMOTION

Stopped by hand at ~12,800 cases (11 of 41 arms), ~9 minutes in, **not** because
of anything this capture observed. Mid-run the orchestrator relayed EXP-0153's
finding that `persistrun.py::_read_line` returned `readline()`'s raw result, so
an **exited child yields `""` — not `None` — forever**, matching none of the
caller's branches and spinning at 100 % CPU with no timeout. `harness/runner.py`
here is derived from the same design and carried the identical defect: a child
that died mid-sweep would have wedged this run silently and burned the shared
GPU for every other agent.

Rather than let the two gated runs differ in their runner, this capture was
stopped, the defect fixed (`_readline` now treats EOF as a wedge exactly as it
treats a timeout), and the gated pair re-captured under NEW ids
`g17p_20260829_run03` and `g17p_20260829_run04`. This directory is retained
append-only, never topped up, its id never reused, and it is not used to promote
any field.

It is still useful evidence for one thing: it independently reproduces run01's
`tex_sample.tex_type` behaviour on the `t_texops` gather occurrence, including
the hang region, from a completely fresh process.

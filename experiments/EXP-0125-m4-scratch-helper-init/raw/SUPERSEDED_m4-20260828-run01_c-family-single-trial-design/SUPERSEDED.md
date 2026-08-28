# SUPERSEDED — third `m4-20260828-run01` attempt (C-family design revision)

**Disclosure, not deletion.** This was a full, successful, non-aborted run
using the CODE-WINDOW-CORRECTED `harness/inittrace.c` (the I-family and
B-family data here are scientifically valid and were unaffected by what
follows — `i_checkpoints_sha256`/`i_summary_sha256`/`b_trials_sha256`/
`b_results_sha256` in this run's `01_summary.json` are byte-identical to the
prior corrected attempt, confirming the code-window fix changed nothing
else).

Reviewing this run's C-family results (single trial per `n_queues` level,
escalation-stop-on-first-non-`OK` design, as originally registered) showed
`n_queues=4` DEGRADED (1 execfail, 1 checksum-mismatch queue) while an
earlier attempt at the same `n_queues=4` had been clean `OK`. Follow-up
reconnaissance (documented in `PRE_REGISTRATION.md` addendum #2) confirmed
this is a genuine, low-frequency, INTERMITTENT failure mode, not a
reproducible fixed threshold — a single-trial ladder cannot honestly
characterize it (it either wrongly clears the hardware or wrongly halts the
escalation early, depending on whether the trial happened to land on a
flake). The C family was redesigned to run `C_REPEATS=6` independent trials
per level, unconditionally (no escalation-stop), reporting a failure RATE.

This entire run directory (including the still-valid I/B data) is
superseded together, for simplicity and auditability, rather than trying to
splice a corrected C-family capture onto an otherwise-complete run directory
— the final `raw/m4-20260828-run01/` (once captured under the revised
C-family code) is a clean, single, internally-consistent artifact. Nothing
here is deleted.

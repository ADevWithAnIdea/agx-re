# QUARANTINE — m4_20260828_run01

**Status: ABANDONED, not a complete or promotable capture. Never overwritten, never reused,
retained append-only exactly as the interrupted process left it.**

`00_inputs.json`, `02_gated.jsonl` (7 of 111 planned records), and `03_nongated.jsonl` are the
genuine, unedited output of a `harness/run.py --run m4_20260828_run01 --out
raw/m4_20260828_run01` invocation that started at `2026-08-28T04:24:08Z` and was interrupted by a
host/terminal problem partway through the matrix (the actual host uptime after resume showed a
fresh boot, i.e. the host restarted; this was not a `macvdmtool`-mediated or any other tool-based
reboot by this agent — recovery was external, and this agent's own tooling never issued a reboot
command). No case in this partial capture reported a fault, hang, or unexpected verdict before the
interruption; the interruption itself carries no positive or negative evidential content about the
tested hardware.

Per `experiments/SUBAGENT_BRIEF.md` (the `EXP-0085` precedent) and the standing gate set's "never
reuse a run id" rule, this run id is retired. The two official captures use fresh ids:
`m4_20260828_run01b` and `m4_20260828_run02b`, recorded in the amended `CAPTURE_CONTRACT.json`.

This directory's three files are otherwise untouched from what the interrupted process wrote.

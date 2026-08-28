# `work/` — scratch, NOT evidence

Everything in this directory is regenerable and none of it is cited by
`RESULTS.md` or `analysis/field_verdicts.json`. The gated evidence lives in
`raw/`, which is append-only.

Compiled binaries (`*.bin` Metal binary archives built from our own MSL, and the
locally built `shdump` / `agxrun` / `agxrun_persist` from `tools/`) have been
**deleted** rather than left for commit: they are binary blobs, they are
reproducible with `harness/build.sh` plus the commands in `README.md`, and
`CODEX.md` step 10 asks that a diff be free of accidental binaries.

What remains: the four gated-run console logs (`run11.log`, `run12.log`,
`run21.log`, `run22.log`), the disclosed pilot/smoke JSONL trees, and the pilot
scripts. The pilot trees are retained because `PRE_REGISTRATION.md` section 8
discloses the pilot and the harness defects it found; they are scratch, not
evidence.

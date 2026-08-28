# Quarantined capture attempt 3 (m4-20260828-run05, cross-run gate bug)

Retained, NOT reused. This is a COMPLETE, CLEAN capture (1548/1548 cases,
no STOP.json, run_manifest.json present) under the fully-corrected F3/
classification-fix harness -- its DATA is valid. It is quarantined only
because `run.py`'s cross-run preflight gate for the *second* run of the
pair had a bug that this repository's own standing rules exist specifically
to catch: `main()` compared BOTH `git_revision` AND `authored_sha256`
between the closed first run and the about-to-start second run, instead of
authored_sha256 alone. Two sibling experiments (EXP-0132, EXP-0134 per the
orchestrator) landed commits on `master` between this run's capture and the
second run's attempted start, moving `git_revision` (`5df9c4b5` ->
`e6bac78a`) with zero change to any file this experiment owns. Per
`SUBAGENT_BRIEF.md`: "Pin the revision at pre-registration; do not gate on
live HEAD... repo HEAD moving because a sibling experiment landed is not
contamination" -- exactly the EXP-0082 landmine that note describes, now
hit here too.

Fixed in `run.py` (the cross-run gate now compares only `authored_sha256`;
`git_revision`/`git_dirty` are still recorded per run for audit, just not
gated on). Because this fix changes `run.py`'s own byte content, and the
whole point of the `authored_sha256` comparison is to prove the harness
itself did not change between the two runs of a promoted pair, this run
(captured under the PRE-fix `run.py`) cannot be validly paired with a
run captured under the POST-fix `run.py` -- so it is retained as a single,
complete, valid-but-unpaired run, and BOTH runs of the final promoted pair
are recaptured fresh under the corrected, now-stable tooling. Run ids
retired again: `m4-20260828-run05`/`m4-20260828-run06` are never reused;
the promoted pair is `m4-20260828-run07`/`m4-20260828-run08`.

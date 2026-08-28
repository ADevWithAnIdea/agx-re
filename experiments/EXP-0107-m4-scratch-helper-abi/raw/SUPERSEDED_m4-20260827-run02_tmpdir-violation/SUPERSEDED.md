# SUPERSEDED — preflight abort, not a hardware/clean-room defect

This directory holds only `00_inputs.json` and an empty `dumps/` directory.
**No case ever ran under this attempt.** `run.py`'s own cross-run consistency
check (comparing `run02`'s authored-code hashes against `run01`'s recorded
values) correctly aborted before any device work began, because
`analysis/analyze.py` and `make_manifest.py` had been written (with real
content, replacing empty placeholder files) after the sibling `run01` attempt
recorded its own provenance hashes -- a genuine hash mismatch, correctly
caught, for files that do not affect what a capture measures.

Separately, and unrelated to that mismatch, this same code revision still
had the `/tmp`-containment defect described in the sibling
`SUPERSEDED_m4-20260827-run01_tmpdir-violation/SUPERSEDED.md`. Both are fixed
together: `analysis/analyze.py` and `make_manifest.py` were finalized before
any further capture attempt (so no authored-file hash can drift again between
run01 and run02), and all temp/build directories were relocated inside this
experiment's own `work/` subdirectory.

This directory is retained (never deleted) as a disclosed process record. A
fresh, complete `m4-20260827-run02` capture was performed after both fixes,
in a new `raw/m4-20260827-run02/` directory alongside this one, and is the
one reported in `RESULTS.md`.

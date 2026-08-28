# SUPERSEDED — process violation, not a hardware/clean-room defect

This directory is the retained (append-only, never deleted or repaired)
output of the first `m4-20260827-run01` capture attempt. **It is superseded
and must not be cited, promoted, or used as evidence.** A corrected capture
under the same contracted run id (`m4-20260827-run01`) was performed after
the fix below and is the one reported in `RESULTS.md`.

## What happened

`SUBAGENT_BRIEF.md` was updated mid-experiment (after this run completed) to
explicitly forbid writing to `/tmp` or any location outside the repository,
"not even briefly," citing two other agents (EXP-0098, EXP-0109) who had
already tripped on this. Auditing this experiment's own code against that
rule found:

- `run.py`'s `build_tools()` used `tempfile.mkdtemp(prefix="exp0107-work-")`
  with no `dir=` argument, placing the compiled `maptrace.dylib` and `probe`
  binaries under the system temp directory (`$TMPDIR`, outside the repo) for
  the duration of the run.
- `harness/metadata.py` used `tempfile.TemporaryDirectory(prefix="exp0107-")`
  with no `dir=` argument, placing the `shdump`-compiled archive under system
  temp for each of the 30 per-case metadata extractions in this run.
- The author's own pre-registration-stage reconnaissance (recorded, not
  evidence, in `PRE_REGISTRATION.md`) also used ad hoc `/tmp/*.metal` files
  and bare `mktemp -d` calls for the same reason.

**What was NOT affected:** every byte of actual evidence -- `raw/<run-id>/
02_cases.jsonl`, `03_timing.jsonl`, `05_raw_maps.jsonl`, `dumps/**/*.hex`,
`00_inputs.json`, `01_summary.json` -- was written directly under this
experiment's own `raw/` tree the entire time; only the *build tooling*
(compiled binaries of our own authored source, and the intermediate archive
files `shdump` produces from our own compiled shaders) transiently lived
outside the repo. No Apple binary, framework, kext, or firmware was read from
or written to any location, inside or outside the repo, at any point. This is
a **directory-containment process violation**, not a clean-room provenance
violation.

## Response

All stray temp files/directories this session created (`/tmp/*.metal`,
`/tmp/work_path.txt`, and every `$TMPDIR/tmp.*` / `$TMPDIR/exp0107-*`
directory from ad hoc reconnaissance and dry-run testing) were deleted.
`run.py`, `harness/metadata.py`, and `verify.py` were fixed to route every
temporary/build directory through this experiment's own `work/` subdirectory
(gitignored, transient, reproducible from committed source) via explicit
`dir=` arguments -- never system temp. Per `SUBAGENT_BRIEF.md`'s own guidance
("self-disclosed and relocated ... is the right response"), this run's output
is retained here as a disclosed, superseded artifact, and a fresh capture was
performed under the corrected code, under the same contracted run id, in a
new `raw/m4-20260827-run01/` directory alongside this one.

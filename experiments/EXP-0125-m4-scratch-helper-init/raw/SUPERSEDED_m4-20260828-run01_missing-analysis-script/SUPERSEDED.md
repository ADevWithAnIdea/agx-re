# SUPERSEDED — first `m4-20260828-run01` attempt

**Disclosure, not deletion**, per `SUBAGENT_BRIEF.md` ("a partial capture is
retained, never reused") and the precedent set by
`experiments/EXP-0107-m4-scratch-helper-abi/RESULTS.md`'s own "Process note".

## What happened

`run.py --run-id m4-20260828-run01 --execute` was invoked before
`analysis/analyze.py` existed on disk, even though `run.py`'s own
`AUTH_CODE` tuple (used to hash authored files into `00_inputs.json`'s
provenance block) already listed it. The five standing gates
(`verify.py --selftest`/`--seqtest`) and the NON-RECORDED smoke gate all
**passed** — those do not read `AUTH_CODE`. The crash happened immediately
afterward, inside `provenance()`, while computing `authored_code_sha256`,
**before** `00_inputs.json` (or any other raw file) was written:

```
FileNotFoundError: [Errno 2] No such file or directory:
  '.../EXP-0125-m4-scratch-helper-init/analysis/analyze.py'
```

## Evidentiary content of this directory: NONE

`raw/m4-20260828-run01/` (as originally created) contained exactly two empty
directories (itself and `dumps/`) and zero files — confirmed by `find
raw/m4-20260828-run01 -type f` returning nothing before this rename. No
`00_inputs.json`, no case/checkpoint/trial/level record, no hardware
observation of any kind was captured under this run id. This is a pure
software-authoring defect (a file listed in `run.py` before it was written),
not a hardware, capture, or process-quality defect, and not a "half-finished"
capture in the sense of partial evidence — there is no evidence here at all.

## Disposition

This directory is renamed (not deleted) to disclose the attempt, per policy.
`analysis/analyze.py` was then authored, and the real capture was run fresh
under the SAME originally-contracted run id `m4-20260828-run01` — following
`EXP-0107-m4-scratch-helper-abi`'s own established precedent for this exact
situation (its RESULTS.md "Process note" section renames a defective attempt
aside as `SUPERSEDED_...` and re-captures under the original contracted id,
rather than burning a new one for a zero-content pre-flight crash). The
CAPTURE_CONTRACT.json `run_ids` list is unchanged.

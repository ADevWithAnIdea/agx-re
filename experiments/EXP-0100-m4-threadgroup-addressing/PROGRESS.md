# EXP-0100 progress log

Successor of `../EXP-0096-m4-threadgroup-addressing` (see its `QUARANTINE.md`): one clean
run01 there (2900/2900 splice `OK`, 145 budget cases with the expected 109 `OK`/36
`PIPELINE_FAIL` split) but quarantined before run02 because of a narrow, pre-run02-detected
bug in `verify.py::_build_tree`'s synthetic-fixture generator (not in the runner, matrix,
kernels, or captured data). This experiment copies the identical kernels/matrix/baseline/
runner unchanged, applies the one-line `verify.py` fix BEFORE any capture, and starts a
fresh two-run promotion under a new PRE_REGISTRATION.md/CAPTURE_CONTRACT.json.

## 2026-08-28 -- authoring stage (near-instant; full design/validation done under EXP-0096)
Copied kernels/*.metal, harness/{build.sh,tgbudget.m}, casematrix.py, baseline.py, run.py,
verify.py (with the pre_gpu manifest-regeneration fix applied), analysis.py,
make_manifest.py from EXP-0096 verbatim (all `EXP-0096` string references replaced with
`EXP-0100`; no other content changes). Wrote fresh PRE_REGISTRATION.md (EXP-0096 successor
preamble added), README.md, RESULTS.md (placeholder), CAPTURE_CONTRACT.json (regenerated
programmatically from the schema constants, never hand-typed).

## Both runs captured; analysis complete; RESULTS.md written
run01: 2900/2900 splice STATUS OK, 145/145 budget (109 OK/36 PIPELINE_FAIL), 162.6s.
run02: 2900/2900 splice STATUS OK, 145/145 budget (109 OK/36 PIPELINE_FAIL), 160.9s.
`verify.py --selftest`/`--seqtest` PASS both between run01 and run02, and after run02.
`make_manifest.py --check` PASS throughout. `verify.py --preflight`/`--between-runs` PASS.

`analysis.py --write`: 0 hand-validation divergences (all 6 entries match); 1 issue --
`04_results.jsonl` (splice) is NOT byte-identical across runs. Root-caused precisely: 16 of
2900 splice cases (all `TGA-SRCSEL`, `tg_addr_compute` byte+1, exactly the 16 values where
`byte+1 & 0x17 == 0x04`) reproduce `STATUS OK` and near-total corruption magnitude
(252-254/256 differing) in BOTH runs but a DIFFERENT specific 256-value array each run --
diagnosed as a genuine hardware scheduling/ordering race (not a harness defect: 2884/2900
other splice cases AND 145/145 budget cases reproduced byte-exact in the SAME two runs).
`06_budget_results.jsonl` IS byte-identical across runs.

`verify.py --captured`: FAILS on exactly this one criterion ("FAIL byte-exact repeat
(splice)"). Per CODEX's "keep failed probes, they bound the hardware" and "prefer
UNKNOWN/PARTIAL to unjustified certainty," this is reported precisely rather than hidden
or forced to pass -- GLCS-A02 closes for 2884/2900 splice + 145/145 budget cases; the 16
racy TGA-SRCSEL byte+1 values are PARTIAL (their existence/magnitude/fault-freedom is
established and reproducible; their exact per-run corrupted content is not, and that IS
the closed finding for that subrange).

Rich secondary findings extracted from analysis.json and written into RESULTS.md: tga
byte0-hi collapses to 3 behavior classes (not 16, per the retention-flag-vs-index-bit
caution); threadgroup device_load idx_off is a hole-free 11-bit element-scaled (x4) field
0..2047 with a precisely characterized undecodable failure beyond; threadgroup
device_store idx_off is scaled x16 bytes/unit -- a genuine load/store UNIT ASYMMETRY, a
direct answer to GLCS-A02's "byte versus element units" question; elem_size (both load and
store) does not reuse EXP-0082's device-space code table and has a precisely
bit-characterized 64/256 hole (mask 0x18==0x10) on the load side; static threadgroup
memory hard-ceils at exactly 32768 B (pipeline-creation-time reject, 4B/16B rounding
granularities at two different API layers); dynamic+combined threadgroup memory shares a
SEPARATE, NOT-API-VALIDATED 65536 B ceiling regardless of the static/dynamic split, beyond
which data silently corrupts with no error.

RESULTS.md written with full OBSERVED/INTERPRETED separation, the finite-resource table,
the GLCS-A02 response block, and the clean-room attestation. No post-capture repair of any
hash-frozen file (run.py/verify.py/casematrix.py/baseline.py/analysis.py/make_manifest.py/
kernels/harness untouched since before run01). Task complete: two runs captured, gates
evaluated honestly (captured gate does not cleanly pass, for a diagnosed hardware reason),
RESULTS.md and QUARANTINE.md (in EXP-0096) both written.

## Reconciling a stale coordinator resume message
A later coordinator message described this task as still in the "RUN01_PRESENT" state
(citing "raw/m4-20260828-run01 ... 6090 record lines", which matches EXP-0096's run01 --
2900+2900+145+145=6090 lines across its 4 jsonl files -- captured BEFORE the verify.py
fixture bug was found). By the time this message arrived, EXP-0096 had already been
quarantined (QUARANTINE.md written there) and this successor (EXP-0100) had already
completed run01, run02, analysis, and RESULTS.md. No re-capture was performed; run01/run02
here were not overwritten or reused. The message's substantive new content -- EXP-0099
(commit de4e4a81) concluding that BOTH the naive DB register-index reading AND the
retention-flag reading are wrong for the ALU field it tested (6 bits load-bearing, top bit
HW-tested inert, role UNKNOWN) -- was incorporated into RESULTS.md's byte0-hi and
index_reg sections, replacing the earlier "pending EXP-0099" phrasing with the concluded
result and an explicit note that it does not transfer bit-for-bit to tg_addr_compute's own
fields (a different instruction), while confirming this experiment's own UNKNOWN-labeling
posture was correct throughout.

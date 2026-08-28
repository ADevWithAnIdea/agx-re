# QUARANTINE -- m4-20260828b-run01 (second attempt)

**Status: quarantined, retained untouched as append-only process history.** Not promoted
evidence. Corrected pair: `m4-20260828c-run01`/`m4-20260828c-run02`.

## What happened

All 97/97 cases ran with `STATUS OK`; 82 `MATCH_EXPECTED`, 15 `OBSERVED_NO_ORACLE` (the
pre-registered Inf/NaN/inverted-clamp/mip-view cases with no a-priori oracle), 0
`MISMATCH_EXPECTED`. This run's **case data is real, correct, and not itself in question** --
see `quarantine-m4-20260828b-run01/04_results.jsonl` for the full record; the specific values
(e.g. `regsplice_bias` A/B/spliced results, cube face selection, cube gradient LOD, the
bias/gradient NaN asymmetry) match what the corrected run below reproduces.

It is quarantined for a **process** reason: starting run02 (`--between-runs` gate) failed
because `verify.py`'s `static()` at the time required `RESULTS.md` to exist and contain a
finite-resource section for ANY `capture=True` state, but `RESULTS.md` (which synthesizes BOTH
runs) had not been written yet -- a design flaw discovered only when actually trying to walk the
contracted sequence for real (exactly the class of defect `--seqtest`'s synthetic fixtures did
not happen to construct, since the synthetic `_build_tree()` always pre-populates a stub
`RESULTS.md`, masking the gap).

## Fix applied for the successor

`verify.py`'s `static()` gained a `require_results` parameter, `True` only for `gate_captured()`
(the FINAL post-both-runs gate), `False` for `gate_between()` (the inter-run gate) -- so
`RESULTS.md` is required only once it can actually exist. This is a change to `verify.py`
itself, which is an `AUTH_CODE` file bound into `CAPTURE_CONTRACT.json` and into every run's
`00_inputs.json`; changing it after `m4-20260828b-run01` was already captured would break that
run's cross-run authored-hash binding for a would-be `m4-20260828b-run02` (`run.py`'s
`"run02 provenance differs from closed run01"` check, correctly, would refuse it) -- hence the
whole pair is quarantined rather than the fix being applied "underneath" an already-recorded
run.

## Evidence retained

`quarantine-m4-20260828b-run01/` (all 7 files byte-for-byte as produced). Nothing here is
edited. `QUARANTINE-run01-attempt1.md` documents the FIRST quarantined attempt
(`quarantine-m4-20260828-run01/`, a `regsplice_bias` harness fast-math mismatch); this is the
second, unrelated defect.

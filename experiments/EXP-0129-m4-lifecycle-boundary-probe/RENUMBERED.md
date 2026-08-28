# Renumbering record: directory EXP-0126 → EXP-0129

**Date:** 2026-08-28. **Performed by:** the orchestrator, after the agent finished writing.

## What happened

This experiment was **dispatched as EXP-0129** — the register-lifecycle remainder (bits 15/31,
bit-17 discrimination, and the A18↔M4 contradiction). The agent created its directory as
`EXP-0126-m4-lifecycle-boundary-probe`, colliding with `EXP-0126-m4-uapi-field-mapping`, which
was legitimately dispatched under 0126 and is committed at `b0a0a1b0`.

The agent noticed and reported the collision itself.

## What was changed — and deliberately what was NOT

**Changed:** the directory name only, `EXP-0126-m4-lifecycle-boundary-probe` →
`EXP-0129-m4-lifecycle-boundary-probe`. Every path inside the contract and the captures is
relative to this directory, so nothing else needed to move.

**NOT changed — and this is the important part:** the internal `EXP-0126` references in
`CAPTURE_CONTRACT.json`, `README.md`, `PRE_REGISTRATION.md`, `RESULTS.md` and `PROGRESS.md`
are left exactly as the agent wrote them.

`raw/m4-20260828-run01/00_env.json` records capture-time SHA-256 hashes for **18 authored
files**, and `CAPTURE_CONTRACT.json`, `PRE_REGISTRATION.md`, and `README.md` are among them:

```
CAPTURE_CONTRACT.json   PRE_REGISTRATION.md   README.md   analysis.py   baseline.py
casematrix.py   harness/build.sh   harness/case_exec.py   harness/fsrun.m
isa_helpers.py   kernels/carrier.metal   kernels/carrier_cf.metal
kernels/carrier_dag.metal   kernels/fs_adjacent.metal   kernels/iunary_popcount.metal
make_manifest.py   run.py   verify.py
```

Editing any of them post-capture — even to fix a cosmetic identifier — would break the
capture-time hash binding and put this experiment in the **EXP-0064 / EXP-0072 / EXP-0073
quarantine class**, where a post-capture repair invalidated an otherwise clean result. A
cosmetic label is not worth that.

So: **inside this directory, "EXP-0126" means this experiment.** That is a known, recorded
inconsistency, not a mistake to be silently repaired later. Do not "fix" it.

(For contrast, the sibling renumbering `EXP-0129-m4-bary-split-abi` → `EXP-0137-m4-bary-split-abi`
*did* rewrite its internal references — there, the contract was verified **not** hash-bound
into its captures, so no binding existed to break. The two cases were checked separately and
handled differently on purpose.)

## Verification after the rename

All five standing gates re-run by the orchestrator post-rename; results recorded in the
commit message. `raw/` untouched.

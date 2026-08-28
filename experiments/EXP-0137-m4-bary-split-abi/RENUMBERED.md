# Renumbering record: EXP-0129 → EXP-0137

**Date:** 2026-08-28. **Performed by:** the orchestrator, after the agent finished writing.

## What happened

This experiment was **dispatched as EXP-0137** (P0.8 / DRV-ABI-01, the last two open items:
the barycentric anomaly and the prolog/epilog linkage contract). The agent created its
directory as `EXP-0129-m4-bary-split-abi` instead.

`EXP-0129` was concurrently dispatched to a different agent — the register-lifecycle
remainder — which in turn created `EXP-0126-m4-lifecycle-boundary-probe`, colliding with the
legitimate `EXP-0126-m4-uapi-field-mapping`. Three-way numbering drift, all in one wave.

## What was changed

Only the **directory name**: `EXP-0129-m4-bary-split-abi` → `EXP-0137-m4-bary-split-abi`.
The single self-referential `"EXP-0129-m4-bary-split-abi"` string in `CAPTURE_CONTRACT.json`
and the corresponding references in the human-facing `README.md` / `RESULTS.md` /
`PRE_REGISTRATION.md` / `PROGRESS.md` are updated to match.

## Why this does not breach the frozen-contract rule

`CODEX.md` forbids post-capture repair of hash-frozen files. Verified before renaming:

- Every path inside `CAPTURE_CONTRACT.json` and `raw/*/00_inputs.json` is **relative to this
  directory**, so a directory rename changes none of them. No absolute path is embedded.
- `CAPTURE_CONTRACT.json` is **not itself hash-bound** into either capture — its SHA-256
  does not appear anywhere in `raw/*/00_inputs.json`.
- `raw/` is untouched. Both captures remain exactly as written, and the cross-run gate still
  passes over them after the rename.

The only mutation is an identifier label. No contract term, hypothesis, threshold, source
hash, or observation was altered.

## Verification after the rename

`verify.py --selftest` 11/11 PASS · `--seqtest` 3/3 PASS ·
`--crossrun raw/m4-20260828-run01 raw/m4-20260828-run02` → `"pass": true`, `mismatch_ids: []`.

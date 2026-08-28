# EXP-0096 QUARANTINE

**Status: QUARANTINED after one clean, complete run01 capture. No run02. Superseded by
`../EXP-0100-m4-threadgroup-addressing`.**

## What happened

run01 (`raw/m4-20260828-run01/`) completed cleanly and completely: 2900/2900 splice cases
`STATUS OK` (no faults, hangs, or timeouts), 145/145 budget cases (109 `OK`, 36
`PIPELINE_FAIL` — all in `BUDGET-STATIC-CAP`, exactly the cases expected to fail pipeline
creation above the static ceiling), 153.6 s wall time. This is real, complete, GPU-captured
evidence, preserved untouched below.

Before starting run02, `verify.py --selftest` was re-run (required by `run.py`'s own
pre-run gate, unconditionally, before every capture including run02) and FAILED with `FAIL
manifest`, inside its `clean_pregpu` synthetic fixture. Root cause, diagnosed and confirmed:

`verify.py::_build_tree`'s `pre_gpu=True` branch copies the CURRENT `manifest.json` from
the real experiment root (`_copy_authored`) and returns immediately, relying on that copy
already being correct for a PRE_GPU-state synthetic tree. That assumption held while the
real tree itself was PRE_GPU (before run01) but broke the instant run01 completed and the
real tree's own `manifest.json` moved to `CAPTURED` state (26 artifacts, including
`raw/m4-20260828-run01/*`) — the synthetic `clean_pregpu` fixture then had a `CAPTURED`
manifest.json copied into a tree with no `raw/` at all, and the fixture's own
freshly-computed expectation (state `PRE_GPU`) could never match it.

`../EXP-0082-m4-mem-offset-semantics/verify.py` (the methodology this experiment copied)
does NOT have this bug: its `_build_tree` unconditionally calls
`_put(root / "manifest.json", manifest_expected(not pre_gpu, root))` for BOTH the `pre_gpu`
and non-`pre_gpu` paths (line 716), always regenerating the synthetic root's OWN manifest
rather than trusting a copied one. EXP-0096's port of that pattern incompletely reproduced
it: the regeneration call exists only in the non-`pre_gpu` path (via the
`make_manifest.py --write` subprocess call at the end of the non-early-return branch), not
in the `pre_gpu` early return. A one-line fix (regenerate manifest.json inside the
`pre_gpu` branch too, exactly mirroring EXP-0082's unconditional call) was written,
syntax-checked, and — before it was reverted — visually confirmed to be the same fix that
made `--selftest`/`--seqtest` pass earlier in this experiment's authoring stage (this bug
did not exist yet at that point, because the real tree was still PRE_GPU; it activated the
instant `raw/m4-20260828-run01/` appeared).

## Why this experiment stops here rather than repairing in place

The fix changes `verify.py`'s bytes, hence its SHA-256, hence `CAPTURE_CONTRACT.json`'s
recorded `authored_sha256["verify.py"]` and `raw/m4-20260828-run01/00_inputs.json`'s
`authored_code_sha256["verify.py"]` would no longer match a freshly-computed hash of the
file on disk. `run.py`'s own run02 gate enforces exactly this equality
(`"run02 provenance differs from closed run01: " + k` for
`k in ("git_revision","git_dirty","authored_code_sha256","authored_doc_sha256")`) — editing
`verify.py` after run01 and before run02 would make run02 impossible under THIS
experiment's own frozen contract, or would require also patching
`run.py`'s cross-run check (a second, compounding post-capture repair) to look past it.
Per the standing rule ("no post-capture repair of hash-frozen files... if a frozen defect
blocks a gate, record it, write QUARANTINE.md naming a successor") this experiment is
quarantined here rather than either (a) silently editing a hash-frozen authored file to
unblock itself, or (b) leaving `run01`'s real evidence permanently stuck with no path to a
second run.

`verify.py` in this directory has been REVERTED to the exact bytes `run01` recorded
(`sha256 173e0a359832d16031c9367f158daf467d7f1374ddb6e7625288e78eb1e2679d`, confirmed equal
to both `CAPTURE_CONTRACT.json`'s recorded value and `raw/m4-20260828-run01/00_inputs.json`'s
recorded value) — the evidence chain in this directory is internally consistent and
honestly describes exactly what ran, at the cost of `--selftest` permanently failing here
from this point forward (a known, explained, non-semantic defect — never repaired in
place). `make_manifest.py --check` passes; `raw/m4-20260828-run01/` is untouched,
append-only, and remains available as process history.

## Scope of the defect (what is NOT at fault)

The bug is confined to `verify.py::_build_tree`'s synthetic-fixture generation for
`--selftest`. It does not touch, and there is no evidence it affected:

- `run.py` (the actual capture runner) — unmodified since before run01, its own hash
  matches across the contract/record chain, and its capture logic (splice mechanism,
  smoke gates, append-only writes, per-case fresh-process execution) is independent of
  `verify.py`'s fixture builder.
- `casematrix.py` (the frozen 2900+145-case matrix), `baseline.py` (probe locators/anchors),
  `kernels/*.metal`, `harness/build.sh`, `harness/tgbudget.m` — none reference or depend on
  `verify.py::_build_tree`.
- `raw/m4-20260828-run01/`'s actual captured data — a complete, internally self-consistent,
  hash-verified record of a real GPU capture on this M4 host.

## Successor

`../EXP-0100-m4-threadgroup-addressing` reuses the identical kernels, matrix, baseline
locator, and runner unchanged, with ONLY the one-line `verify.py::_build_tree` fix applied
BEFORE any capture (so it never becomes a frozen defect there), and fresh
`PRE_REGISTRATION.md` / `CAPTURE_CONTRACT.json` per the standing rule that a successor gets
a new experiment number and a fresh pre-registration rather than resuming a quarantined one
in place. EXP-0096's `raw/m4-20260828-run01/` is cited there as process history /
authoring-stage corroboration only (both its splice and budget status-count summaries
matched expectations exactly), never as promoted GLCS-A02 evidence — GLCS-A02 remains
`Open` until EXP-0100 completes its own two-run promotion gate.

Clean-room provenance: HW-PROBE / OWN-SHADER (unchanged from PRE_REGISTRATION.md)
Apple binary introspection: NONE

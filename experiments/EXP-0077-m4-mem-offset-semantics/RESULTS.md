# EXP-0077 results — M4 device_load/store memory-offset semantics (MEM-01..MEM-05)

**Status: TERMINAL PROCESS HISTORY — crashed at the in-run smoke gate before
any recorded observation. Successor: EXP-0080-m4-mem-offset-semantics.**

## What happened (2026-08-27, honest record)

All pre-capture gates passed (`verify.py --selftest` 19/19, the new
`verify.py --seqtest` gate-sequence state machine 14/14, `make_manifest.py
--check`, `verify.py --preflight`), plus three authorized non-recorded
plumbing validations (unspliced ld → `a[64] = 0x3CA50040` exactly;
spliced `idx_off=+1` → `a[65] = 0x3CA50041` — the M4 splice mechanism works;
unspliced st → `tgt[64] = 0x5A17C0DE`, all other words zero). No MEM-01..05
observation was recorded.

`run.py --execute --run-id m4-20260827-run01` then passed its gates and the
build/baseline phase, created `raw/m4-20260827-run01/` (00/01/02 written), and
crashed INSIDE the in-run smoke gate with an unhandled `KeyError: 'item'` —
`SMOKE_CASE` (the scratch case descriptor) lacked the `item` key that
`run_one_case` records. The single smoke dispatch (ld, `idx_off=+1`, idx=64 —
the same case as the already-authorized plumbing check) executed on the GPU;
its output was lost to the crash and is not evidence of anything beyond what
the plumbing check already established. No case of the 2164-case matrix was
executed; `04_results.jsonl` was never created.

## Why this is not repaired in place

The stub `raw/m4-20260827-run01/` exists (append-only; retained as process
history), and `00_inputs.json` binds the pre-crash SHA-256 of every authored
blob. Repairing `run.py` breaks that capture-time hash binding — the exact
EXP-0064/0072/0073 quarantine class. The runner also refuses any re-run under
an existing run id by design. Per `CODEX.md` the successor takes a NEW
experiment number and a fresh pre-registration.

## Disposition

- `raw/m4-20260827-run01/` stays append-only as process history; it is
  **non-evidence** (incomplete: no dispatch record, no results). The one
  unrecorded smoke dispatch is documented above and in `PROGRESS.md`.
- The complete frozen design (kernels, baseline anchors, 2164-case matrix,
  hand-validation set, contract grammar, verify gates) is adopted UNCHANGED by
  `../EXP-0080-m4-mem-offset-semantics/`, with three process fixes:
  1. `SMOKE_CASE` carries the full case-record keys (the crash cause);
  2. the non-recorded smoke gate runs BEFORE `raw/` is created, so any
     smoke-phase defect is a clean pre-capture stop with NO burned run id
     (EXP-0075's smoke-ordering lesson, now structural);
  3. an unexpected exception in the sweep writes `STOP.json`
     (phase `dispatch_loop`) instead of a bare traceback.
- The pre-capture plumbing result stands as a testbed fact only: splices into
  our own compiled archive execute on the local M4 (macOS 26.6.2), and a
  `+1` in the 11-bit immediate field moved a 4-byte-element load by exactly
  one element (4 bytes). This is a hypothesis-consistent datum for H-ELEM
  (MEM-02) but is NOT promoted as MEM evidence here; EXP-0080 re-establishes
  everything under its own registration.

## Target and scope label

M4 / G16G, local host, public Metal API only. No A18 (G17P) inference; A18
hands-off. No M5 evidence. `macvdmtool` never used.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER (testbed validation only; no recorded observation)
Inputs inspected: authored MSL (kernels/), authored harness/runner/verifier/analysis/matrix/
  baseline modules, and the compiled bytes of our own kernels only
Apple binary introspection: NONE
Reproduction: gates — python3 -B verify.py --selftest && python3 -B verify.py --seqtest
  (still pass); the crashed run is not reproducible by design (append-only stub)
Evidence: raw/m4-20260827-run01/ (incomplete stub, non-evidence), PROGRESS.md
Successor: ../EXP-0080-m4-mem-offset-semantics/
```

# EXP-0075 M4 typed-format conversion, batch 2

> **STATUS: STOPPED AFTER RUN 01 — contract unmeetable, nothing promotable.**
> Run 01 (`raw/m4-20260827-run01`) captured clean, complete, and verified, but
> the contracted second run is unreachable: the frozen `pre_second_run_gate`
> sequence (`verify.py --between-runs`, then `verify.py --selftest`) is
> self-contradictory, because `--selftest` is a PRE_GPU-only check that fails
> the moment `raw/` exists. Repairing the frozen `verify.py`/`run.py` after
> capture would break the capture-time hash binding (the EXP-0064/0073
> quarantine class), so no repair was made. See `RESULTS.md` for the full stop
> record and the successor (EXP-0076) fix list. **No DRV-FMT-01 claim may be
> promoted from this tree**; `RESULTS.md` carries single-run, repeat-unverified
> observations only.

Named successor to quarantined EXP-0072, delivering the third bounded increment
of DRV-FMT-01 (per-format capability and conversion table; P1.2) after EXP-0070
(batch 1, fragment-store path, six formats). Authored public-Metal M4
experiment bundle: an MSL matrix of 34 compute-store kernels over 14 pixel
formats, an owned-buffer in-bounds harness (compute store to a 1x1 texture,
then a typed compute read in the same command buffer), a deterministic
analyzer, a complete capture manifest, and a fail-closed verifier with a
pre-capture self-test. API-level rejections are preregistered as classification
data, not failures.

The two changes versus EXP-0072, both pinned by its QUARANTINE.md, **both
worked**:

1. **Harness process-exit discipline** — exactly one locked
   print-then-flush-then-exit path; `main()` blocks forever after both phase
   waits; completion is never signalled before the record is durable. All 34
   run-01 records are complete and untruncated.
2. **A contract-named pre-capture non-recorded smoke invocation** — one scratch
   case must produce one complete, self-consistent JSON record into
   `work/<run-id>/smoke/` before the append-only tree is created. It **caught a
   real defect on the first attempt** (a dropped MSL `#include`/`using` pair in
   the regenerated kernel header) and stopped the run before `raw/` existed;
   after the authorized pre-capture repair it passed.

Frozen audit commands and their outcome on the retained (final) tree:

```sh
python3 -B verify.py --preflight      # FAIL closed root (raw/ present: correctly refuses to re-arm)
python3 -B verify.py --selftest       # FAIL closed root (the contracted run02 gate; see stop record)
python3 -B verify.py --between-runs   # PASS  (run01 complete, closed, and fully verified)
python3 -B verify.py --captured       # FAIL derived analysis (run02 never captured)
python3 -B make_manifest.py --check   # PASS  (state=CAPTURED over the retained tree)
```

`raw/` is append-only evidence: one run, one fresh process per case, no
symlinks, no edits. `manifest.json` hashes every authored, raw, and derived
artifact except itself. The runner is opt-in (`--execute`) and never retries a
fault automatically; it must not be re-invoked on this tree (the run-01 ID is
consumed).

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL, harness, contract, and owned buffer readbacks only
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --between-runs`; `python3 -B make_manifest.py --check`; full two-run re-capture requires the successor
Evidence: `raw/m4-20260827-run01`, `manifest.json`, `RESULTS.md`, `PROGRESS.md`

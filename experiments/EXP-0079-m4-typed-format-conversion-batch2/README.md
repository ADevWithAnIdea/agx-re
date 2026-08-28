# EXP-0079 M4 typed-format conversion, batch 2

Named successor to quarantined EXP-0075, delivering the DRV-FMT-01 (P1.2)
batch-2 increment (per-format capability and conversion table; fourteen
public pixel formats, compute-store path) after EXP-0070 (batch 1,
fragment-store path, six formats). Authored public-Metal M4 experiment
bundle: an MSL matrix of 37 compute-store kernels over 14 pixel formats
(34 carried over from EXP-0075 plus three new discriminating cases), an
owned-buffer in-bounds harness (compute store to a 1x1 texture, then a
typed compute read in the same command buffer), a deterministic analyzer, a
complete capture manifest, and a fail-closed verifier with a pre-capture
self-test and a gate-sequence state-machine self-test.

## Why this experiment exists

EXP-0075 captured a clean, complete, fully-verified run01 (34/34 cases, zero
truncation — its two dispatched fixes, harness process-exit discipline and
a non-recorded pre-capture smoke gate, both worked exactly as designed) but
was quarantined because its frozen `pre_second_run_gate` sequence
(`verify.py --between-runs`, then `--selftest`) was self-contradictory:
`--selftest` was a PRE_GPU-only check that necessarily failed once
`raw/run01` existed. Run02 was structurally unreachable and no DRV-FMT-01
claim could be promoted. See
`../EXP-0075-m4-typed-format-conversion-batch2/QUARANTINE.md`.

EXP-0079 fixes exactly that, and only that, plus what its QUARANTINE.md
named as required:

1. **`verify.py --selftest` is now state-agnostic** — runnable and
   satisfiable in PRE_GPU, RUN01_PRESENT, and RUN02_PRESENT tree states.
2. **A new `verify.py --seqtest`** proves, via three isolated non-mutating
   fixture trees with synthetic (no-GPU) raw data, that every gate
   `CAPTURE_CONTRACT.json` contracts for a given tree state is both
   runnable and satisfiable *in that state* — a real, subprocess-executed
   proof, not source-text pattern matching. This is the check that would
   have caught EXP-0075's contradiction before any GPU work.
3. **The non-recorded pre-capture smoke gate is carried over unchanged**
   (EXP-0075 proved it catches real defects: it stopped a run
   pre-capture on a dropped MSL `#include` on its first invocation).
4. **No byte-compared record carries a timing/duration/address/pid field**
   (already true of EXP-0075's schema; re-verified here by inspection).

The 34-case/14-format matrix is re-registered with three corrected expected
values disclosed by EXP-0075 (`r32float_exact`, `rg11b10float_exact`,
`rg11b10float_mid` — arithmetic slips in the *frozen expectation*, not
hardware results) and EXP-0075's two candidate findings (snorm8 encode scale
H1; reduced-float truncation-vs-RNE H2) registered as named
hypotheses-to-falsify, never as new expectations. Three new cases
(`r8unorm_sep_a`/`r8unorm_sep_b`, half-even vs half-up separators;
`r16float_pos_trunc`, a positive-direction truncation probe) bring the case
count to 37 over the same 14 formats. Full rationale, independent
re-derivations, and exact predicted values for every hypothesis:
`PRE_REGISTRATION.md`.

Frozen audit commands:

```sh
python3 -B verify.py --preflight       # PRE_GPU contract (closed root, contract shape, kernel/harness structure)
python3 -B verify.py --selftest        # schema + smoke-gate self-test; state-agnostic
python3 -B verify.py --seqtest         # gate-sequence state-machine self-test (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT)
python3 -B run.py --run-id m4-20260828-run01 --execute   # capture run01 (opt-in; real GPU)
python3 -B verify.py --between-runs    # run01 closed/complete; run02 may begin
python3 -B run.py --run-id m4-20260828-run02 --execute   # capture run02 (opt-in; real GPU)
python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --captured        # final gate
```

`raw/` is append-only evidence: two runs, one fresh process per case, no
symlinks, no edits. `manifest.json` hashes every authored, raw, and derived
artifact except itself. The runner is opt-in (`--execute`) and never retries
a fault automatically.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL, harness, contract, and owned buffer readbacks; EXP-0075's RESULTS.md/PRE_REGISTRATION.md prose (disclosed slips and candidate findings only, never its raw bytes as evidence)
Apple binary introspection: NONE
Reproduction: see the frozen audit commands above
Evidence: `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `raw/` (once captured), `RESULTS.md`, `PROGRESS.md`

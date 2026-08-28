# EXP-0090 -- M4 hand-built program suite (DRV-ISA-01 acceptance test)

**Question.** Not tokenization, not round-trip, not a single-field splice into
someone else's program: can this repository's own tools (`tools/agx-isa`)
independently CONSTRUCT whole, non-trivial, multi-instruction-family AGX
programs -- checked against an independent exact Python oracle -- and have
them execute correctly on real M4 hardware?

**Method.** Build 4 candidate whole programs (P1 arithmetic dataflow chain,
P2 memory round trip, P3 control flow, P4 register-pressure/move), each as a
concatenation of `isa_helpers.py` instruction builders (each one a call to
`tools/agx-isa`'s own read-only `isadb.assemble()`), padded to an exact
measured carrier-kernel length, spliced whole into `_agc.main` at offset 0
via `tools/agxtest/agxtest.py`, run on the real M4, and compared byte-exactly
against a Python oracle computed from the program's own intended semantics
(never from a GPU run). Every program's design was shaped by ~30 informal,
single-purpose diagnostic probes run BEFORE freezing `PRE_REGISTRATION.md`
(see its "pilot diagnostics" section) -- several of which are decisive
findings in their own right (a corrected `falu2` liveness-field rule, a new
`device_store` `extmode` formula, and a documented negative result for
`reg_move` composability that excludes P4 from the formal capture).

**Result:** P1, P2, and P3 each match their oracle exactly, reproducibly, on
real M4 hardware (see RESULTS.md). P4 could not be made to work in the time
available and is reported as a first-class negative result.

**Clean-room provenance: OWN-SHADER + HW-PROBE.** Every byte executed is
either our own hand-assembled instruction sequence or the compiled form of
our own carrier MSL. No Apple binary is ever introspected.

## Reproduce

```sh
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B make_manifest.py --check
python3 -B verify.py --preflight
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B verify.py --captured
python3 -B analysis.py --write
python3 -B make_manifest.py --write
```

## Files

- `isa_helpers.py` -- instruction-construction wrappers over `isadb.assemble()`.
- `programs.py` -- `build_p1`/`build_p2`/`build_p3` (whole-program builders + oracles).
- `casematrix.py` -- the 24 frozen cases (field-matrix sweep) across P1/P2/P3.
- `kernels/carrier_p{1,2,3}.metal`, `kernels/pilot_immadd.metal` -- our own MSL carriers/anchor.
- `harness/build.sh`, `harness/case_exec.py` -- build the read-only tools; run one case.
- `run.py`, `verify.py`, `analysis.py`, `make_manifest.py` -- the standing gate set.
- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` -- frozen hypothesis/predictions/contract.
- `RESULTS.md` -- observations vs. interpretation, per-family verdicts, the P4 negative result.
- `PROGRESS.md` -- timestamped milestone log (including the full diagnostic trail).

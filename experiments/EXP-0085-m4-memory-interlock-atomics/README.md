# EXP-0085 M4 memory interlock + atomic operation set

Answers Part-II **MEM-13, MEM-14** and the **ATOM-01..06** cluster of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` ("P0 — Memory addressing and robustness" /
"P0 — Atomics and synchronization"). **ATOM-07..11 are explicitly deferred**
(fence/barrier instruction family, out of scope for this increment) — see
`PRE_REGISTRATION.md` "Scope" table for the full eleven-item accounting and
the successor recommendation (next available EXP-NNNN).

Method: mixture of (a) authored MSL exercising every covered atomic op
through the public Metal API with bit-exact readback of both returned and
stored values under real multi-lane contention (thread counts up to 65536),
gated on run-invariants (commutative combine / permutation / single-winner —
never raw per-lane order, which legitimately varies run to run); and (b)
read-only use of `tools/shdump` + `tools/agx-isa` to tokenize our own
M4-compiled kernel bytes and structurally confirm the interlock (no
wait/scoreboard instruction between producer and consumer) and the SIMD
pre-combine boundary (ATOM-05/06). Builds on, and re-validates on M4,
`EXP-0025-scoreboard` (A18 register-interlock claim) and
`EXP-0018-atomics-subgroup` (A18 atomic op-field table); extends
`EXP-0051-m4-synchronization-litmus`'s ordering-exposure finding to the
device-atomic-RMW call site.

Target: **local Apple M4 (G16G) only**, macOS 26.6.2 build 25G82, Metal 4.
No A18 Pro claim (hands-off per `CLAUDE.md`).

## Layout

- `PRE_REGISTRATION.md` — hypotheses, falsifiers, scope (covered vs
  deferred), contention invariants, confounders, frozen before capture.
- `CAPTURE_CONTRACT.json` — machine-readable frozen matrix/schema/hashes.
- `casematrix.py` — the single authoritative 56-case matrix + per-family
  result-record key sets + per-case order-sensitive-key declarations.
- `kernels/atomics.metal`, `kernels/atomics_ordering.metal`,
  `kernels/interlock.metal`, `kernels/interlock_tex.metal` — authored MSL.
- `harness/atomics_probe.m`, `harness/interlock_probe.m`,
  `harness/interlock_tex_probe.m` — authored single-case ObjC/Metal runners.
- `run.py` — capture orchestration (build, smoke gate, 56-case sweep, raw
  tree).
- `verify.py` — standing gate set (`--selftest`, `--seqtest`, `--preflight`,
  `--between-runs`, `--captured`).
- `analysis.py` — cross-run gate + per-case invariant recomputation +
  MEM-13/14 and per-ATOM-item verdicts → `analysis.json`.
- `RESULTS.md` — OBSERVED vs INTERPRETED, verdicts, clean-room attestation.
- `PROGRESS.md` — milestone log.

## Commands (in order)

```sh
python3 -B verify.py --selftest        # required before any build
python3 -B verify.py --seqtest         # required before any build
python3 -B verify.py --preflight       # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
python3 -B verify.py --captured
```

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources;
read-only `tools/shdump`, `tools/agx-isa` on our own compiled shader bytes
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260827-run01`, `raw/m4-20260827-run02`, `analysis.json`,
`work/*/tokenize_*.txt` (structural evidence captured alongside)

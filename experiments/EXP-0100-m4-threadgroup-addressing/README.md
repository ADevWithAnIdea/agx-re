# EXP-0100 M4 threadgroup addressing (GLCS-A02, addendum Bundle F)

Closes **GLCS-A02** ("threadgroup/shared-memory addressing and finite allocation
semantics", `APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`) on the **local M4 (G16G)** — the sole
test target per the standing directive (A18 Pro hands-off) — by splice-decoding the
`tg_addr_compute` (`0x1c`) instruction and the threadgroup-space form of
`device_load`/`device_store`, and by a public-Metal boundary sweep for maximum
threadgroup-shared bytes, allocation granularity, and the static+dynamic combination
rule. Successor methodology is `../EXP-0082-m4-mem-offset-semantics` (same splice-matrix /
smoke-gate / timing-isolation / cross-run-byte-exact design), reused near verbatim per the
dispatch's own instruction.

**GLCS-A01 is explicitly out of scope** (`work/ADDENDUM-TRIAGE-20260828.md` "Bundle F"
closes GLCS-A02 only) — see `PRE_REGISTRATION.md`'s scope note.

## Kernels

- `kernels/tga.metal` — reproduces the exact shape that emits `tg_addr_compute` (prior
  A18 evidence, own-MSL `k_thr.metal`/EXP-M4-14): a 256-element threadgroup `float` tile,
  one store per thread, a barrier, then two reads at compile-time-constant masked offsets.
  Splice target: the unique `tg_addr_compute` instruction. Runtime variation comes from
  per-thread ID and device input data (an authoring-stage finding: an `idxbuf`-controlled
  runtime offset makes the compiler NOT emit `tg_addr_compute` at all — see
  `PRE_REGISTRATION.md`).
- `kernels/tg_ld.metal` / `kernels/tg_st.metal` — mirror EXP-0082's `ld_bank.metal` /
  `st_bank.metal` methodology applied to threadgroup space: a single-thread dispatch reads
  or writes a runtime (`idxbuf`-controlled) index into an 8 KiB threadgroup array,
  populated/read back via a compiler-unrolled loop. Splice target: the unique
  threadgroup-space `device_load` / the unique threadgroup-space `device_store` occurring
  after the first barrier.

## Budget sweep

`harness/tgbudget.m` — a small, argv-parametrized, own-MSL public-Metal tool (NOT part of
the splice mechanism): compiles a fresh kernel per case declaring a `static-bytes`-sized
compile-time threadgroup array, a `dynamic-bytes`-sized `setThreadgroupMemoryLength:`
region, or both, and cooperatively fills+verifies every byte with a bit-mixing
(non-periodic) hash across `thread_position_in_threadgroup`-strided runtime loops (a v1→v2
correction recorded in `PRE_REGISTRATION.md`: a compile-time-constant-index canary was
optimized away by the compiler and a linear fill pattern was blind to a real periodic
aliasing effect).

## Commands (in order)

```sh
python3 -B verify.py --selftest        # required before any build (any state)
python3 -B verify.py --seqtest         # gate-order state-machine self-test
python3 -B make_manifest.py --check
python3 -B verify.py --preflight       # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260828-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260828-run02
python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --captured
```

## Files

`PRE_REGISTRATION.md` (question, hypotheses, authoring-stage findings, frozen method),
`CAPTURE_CONTRACT.json` (machine-checked frozen grammar), `casematrix.py` (2900 splice +
145 budget cases), `baseline.py` (probe locator/anchors), `run.py` (capture runner),
`verify.py` (fail-closed static/dynamic verifier + selftest/seqtest), `analysis.py`
(deterministic cross-run analysis), `make_manifest.py`, `kernels/*.metal`,
`harness/build.sh`, `harness/tgbudget.m`, `RESULTS.md`, `PROGRESS.md`.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources and the compiled
bytes of our own kernels (splice targets) and budget-sweep kernels (no splicing); public
reference material (`apple9_isa_explainer.md`, cross-checked for methodological caution
only, no unverified specific imported as fact)
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260828-run01`, `raw/m4-20260828-run02`, `analysis.json`, `manifest.json`

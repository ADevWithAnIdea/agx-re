# EXP-0047 — M4 floating-point boundary behavior

## Question

What live M4/G16G behavior do authored fp32/fp16 add, multiply, min/max, and rounding
source paths exhibit for subnormals, NaNs, infinities, and signed zero?

This advances P1.8 and the numerical-lowering portion of P0.6. It does not claim A18
validation and does not by itself prove Vulkan/GL conformance.

## Pre-registered competing hypotheses and falsifiers

1. fp32 may flush subnormal inputs/results while fp16 preserves them, matching the public
   driver capability expectation. A nonzero fp32 *arithmetic* subnormal result refutes
   fp32 result-FTZ; loss of the fp16 arithmetic cases refutes fp16 preservation. Raw-bit
   identity kernels control for buffer transport.
2. `fmin`/`fmax` may implement minNum/maxNum for one-NaN cases but select an operand on
   equal signed zeros. NaN propagation with one numeric operand, or order-independent IEEE
   signed-zero selection, refutes this combined hypothesis.
3. `rint` should use ties-to-even while `round` should use ties-away-from-zero. Any half-way
   case with a different result refutes the respective rule.

All values enter as raw integer bit patterns and leave as raw integer bit patterns, avoiding
CPU float formatting and preserving NaN payloads and signed zero.

## Authored probe

- `kernels/numeric.metal`: ten small kernels authored for this experiment.
- `run_probe.py`: builds the repository-authored `shdump` and `agxrun`, compiles only that
  MSL with no-fast-math, forces execution from the resulting own-shader archive, performs
  two fresh compile/run passes, and emits a normalized JSON report.

The temporary Metal archives are not committed. The report retains each own `_agc.main`
byte string, length, and SHA-256, plus exact input/output bits, status, target identity,
capture time, repository revision, compiler/SDK identity, and hashes of every authored
source/tool input.

`raw/m4-two-run.json` is the preserved initial matrix. Review found that its min/max
cases lacked ordinary unequal finite operands. `raw/m4-two-run-v2.json` is the preserved
finite-control extension. The canonical `raw/m4-two-run-v3.json` adds raw-bit identity
controls, rounding-neighbor/special-value controls, and self-contained provenance metadata.
The earlier captures are design-history evidence and are not the basis of the promoted result.

## Reproduction

```sh
python3 run_probe.py
```

Each process has a hard timeout. `verify.py` validates the committed result schema, target,
two-run equality, statuses, and artifact hashes without executing the GPU:

```sh
python3 verify.py
```

The raw captures are append-only. A fresh run prints a new complete JSON object to
standard output; compare it with the canonical capture rather than overwriting any file
under `raw/`.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: kernels/numeric.metal and its own compiled _agc.main bytes
Apple binary introspection: NONE
Reproduction: experiments/EXP-0047-m4-numerical-behavior/run_probe.py
Evidence: raw/m4-two-run-v3.json, manifest.json, RESULTS.md
```

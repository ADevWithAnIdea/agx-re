# EXP-0073 M4 FP32 division precision (OPT-02)

> **QUARANTINED / NON-EVIDENCE.** The frozen verifier contained an unsatisfiable
> dispatch-receipt check, so no capture can pass this experiment's own promotion
> gate; the single retained run is process history only. See `QUARANTINE.md`.
> The successor is `EXP-0074-m4-fp32-division-precision`.

Public-Metal behavioral probe answering Part-II questionnaire item **OPT-02** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md`: does precise FP32 division produce the
correctly rounded result for all tested normal, subnormal, zero, infinite, NaN,
overflow, and underflow cases?

Method: an authored MSL compute kernel divides `as_float(a) / as_float(b)` with
the plain `/` operator (no fast-path intrinsics, no `precise` qualifier),
compiled at runtime with `MTLCompileOptions.fastMathEnabled = NO` (and
`mathMode = MTLMathModeSafe`). Inputs are 75 frozen directed edge-case bit
patterns plus a frozen 4096-pair LCG block. The CPU harness uploads the pairs,
dispatches one compute thread per pair, and reads back raw result bits. A
two-method, hand-validated, exactly-rounded IEEE-754 binary32 reference
(roundTiesToEven, gradual underflow, no binary64 double rounding) computes the
expected result; NaN cases are compared by is-NaN only with payloads recorded
verbatim.

Scope: **this increment is public-Metal behavioral evidence on the local M4
(G16G) only.** No native-encoding or ISA claim, no Linux/UAPI claim, and no
A18 (G17P) inference.

Do not run anything in this directory. `verify.py --captured` can never pass by
construction (see `QUARANTINE.md`), and `raw/` holds one quarantined run only.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (quarantined; non-evidence)
Inputs inspected: authored MSL/harness/analysis sources
Apple binary introspection: NONE
Reproduction: not authorized; successor is `../EXP-0074-m4-fp32-division-precision/`
Evidence: `raw/m4-20260827-run01` (append-only process history)

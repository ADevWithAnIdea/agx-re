# EXP-0074 M4 FP32 division precision (OPT-02)

Successor of the quarantined `../EXP-0073-m4-fp32-division-precision`: identical
frozen design, repaired capture contract. See `../EXP-0073-m4-fp32-division-precision/QUARANTINE.md`
for why the predecessor's single retained run is non-evidence; it has not been
read, reused, cited, or compared against here.

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

What is different from EXP-0073 (the whole point of this experiment):

- `verify.py` defines **one** execution-record checker (`record()`) with one
  frozen key set per record slot — `REC_KEYS` for plain receipts and
  `REC_KEYS + {results_sha256, results_lines, summary}` for the dispatch record
  — with exact key-set equality everywhere. EXP-0073 was quarantined because
  two of its checks required contradictory key sets for that one record.
- `verify.py --selftest` is a **required pre-capture step** (first entry of
  `capture.preflight_sequence` in `CAPTURE_CONTRACT.json`, and enforced by
  `run.py`, which refuses to capture unless it has just passed). It drives
  fabricated synthetic captures through every schema gate, including the
  run-to-run comparison, and proves both that a clean capture can pass and that
  each broken shape fails for the right reason.
- Every hash in `CAPTURE_CONTRACT.json` is derived from this experiment's own
  blobs.

Scope: **this increment is public-Metal behavioral evidence on the local M4
(G16G) only.** No native-encoding or ISA claim, no Linux/UAPI claim, and no
A18 (G17P) inference — the A18 is hands-off for this work and nothing here was
run on it.

Commands (in order):

```sh
python3 -B verify.py --selftest        # required before any build
python3 -B make_manifest.py --check
python3 -B verify.py --preflight       # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B verify.py --captured
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
```

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260827-run01`, `raw/m4-20260827-run02`, `analysis.json`, `manifest.json`

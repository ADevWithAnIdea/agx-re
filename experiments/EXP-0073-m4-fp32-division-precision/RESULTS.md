# EXP-0073 results — M4 public-Metal FP32 division precision (OPT-02)

> **QUARANTINED / NON-EVIDENCE.** The between-runs verification gate failed on
> an unsatisfiable check inside the frozen verifier (dispatch-receipt key schema
> contradiction). All retained material is process history only and must not
> support any OPT-02 claim; see `QUARANTINE.md`. The successor with the verified
> contract is `EXP-0074-m4-fp32-division-precision`.

What happened, factually: preflight passed; run 01 captured 4171/4171 case lines
with command-buffer status 4 and all guard bytes intact on the local M4; run 02
was correctly refused by the gate; no fault, timeout, or device loss occurred.
The quarantined `raw/m4-20260827-run01` bits are not analyzed or interpreted
here.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (quarantined; non-evidence)
Inputs inspected: authored MSL, harness, contract; retained run-01 owned readbacks (non-evidence)
Apple binary introspection: NONE
Reproduction: not authorized; see QUARANTINE.md and EXP-0074
Evidence: raw/m4-20260827-run01 (append-only process history)
```

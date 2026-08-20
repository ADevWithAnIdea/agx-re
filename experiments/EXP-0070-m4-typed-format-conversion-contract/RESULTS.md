# EXP-0070 results

**PRE-GPU / NO RESULT.** No Metal compilation, allocation, command submission, or
GPU execution has been performed. P1.2 remains **OPEN**. This file records no
physical backing byte, typed readback, implementation behavior, or M4 fact.

If a future capture passes the frozen verifier, its direct observations must stay
separate from interpretation and remain limited to the exact cases and public API
path in `PRE_REGISTRATION.md`. A failed or incomplete capture is evidence of a
stop condition, not a license to fill in expected values.

Clean-room provenance: OWN-SHADER / PUBLIC API (pre-GPU tooling only)
Inputs inspected: authored MSL, harness, and contract
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`
Evidence: no raw observations exist

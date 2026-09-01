# EXP-0238 — canonical `cvt_f2i` register reach and lifecycle

Generated G17P validation of the complete source descriptor namespace and safe destination
descriptor namespace of the ten-byte FP32-to-signed-I32 `cvt_f2i` form. Inputs are explicitly
materialized before use; positive exact `trunc(N + 1.5)` provides an independent integer oracle.

Offline generation gate:

```sh
python3 harness/selftest238.py
```

Formal result: `RESULTS.md`. Machine gates: `analysis/formal_result.json` and
`analysis/gate_e_result.json`.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

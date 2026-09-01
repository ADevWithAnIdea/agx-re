# EXP-0237 — canonical `fspecial` register reach and lifecycle

Generated G17P validation of the complete source descriptor namespace and safe destination
descriptor namespace of the ten-byte FP32 direct-round `fspecial` form. Inputs are explicitly
materialized before use; `floor(N + 0.5)` provides an exact independent oracle.

Offline gate:

```sh
python3 harness/selftest237.py
```

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

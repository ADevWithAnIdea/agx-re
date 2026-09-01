# EXP-0239 — canonical `cvt_i2f` register reach and lifecycle

Generated G17P validation of the complete source descriptor namespace, safe destination descriptor
namespace, and isolated first-invalid destination of the eight-byte signed-I32-to-FP32 `cvt_i2f`
form. Inputs are explicitly materialized before use; small positive integers have exact binary32
oracles.

Offline generation gate:

```sh
python3 harness/selftest239.py
```

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

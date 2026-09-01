# EXP-0234 — canonical `isel10` register reach

Dense generated G17P validation of all four canonical 32-bit source roles, the four-bit destination
namespace, the widened ten-byte framing rule, and per-role first-invalid behavior.

Offline gate:

```sh
python3 harness/selftest234.py
```

Formal capture commands are frozen in `PRE_REGISTRATION.md` and the two capture scripts.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

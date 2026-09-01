# EXP-0234 — canonical `isel10` register reach

Dense generated G17P validation of all four canonical 32-bit source roles, the complete source-byte
descriptor namespace, the four-bit destination namespace, and the widened ten-byte framing rule.

`AMENDMENT-02.md` supersedes the original direct-r95/fault-boundary hypothesis after two sparse
opposite-order discovery runs showed direct r0..r63 plus high-bit aliasing.

Offline gate:

```sh
python3 harness/selftest234.py
```

Formal capture commands are frozen in `PRE_REGISTRATION.md` and the two capture scripts.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

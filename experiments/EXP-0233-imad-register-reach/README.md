# EXP-0233 — canonical low-32 `imad` register reach

Dense generated G17P validation of the canonical twelve-byte retained-source low-32 `imad` access
classes. This extends EXP-0225's r0..r23 validation without changing its arithmetic recipe.

Offline gate:

```sh
python3 harness/selftest233.py
```

Formal capture commands are frozen in `PRE_REGISTRATION.md` and the two capture scripts.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

# EXP-0232 — canonical `iadd2` register reach

Dense generated G17P validation of the canonical ten-byte b32 register-register `iadd2` access
classes: source A r0..r31, source B r0..r63, and destination r0..r94.

```sh
python3 harness/selftest232.py
sh harness/capture232.sh g17p_e0232_run01 canonical 23201 300
sh harness/capture232.sh g17p_e0232_run02 reverse 23202 300
python3 analysis/formal232.py raw/g17p_e0232_run01 raw/g17p_e0232_run02
```

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

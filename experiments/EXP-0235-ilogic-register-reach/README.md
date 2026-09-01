# EXP-0235 — canonical `ilogic` register reach

Generated G17P validation of both canonical XOR source roles, their dependency-derived release
targets, the complete source-byte namespace, and the destination nibble. `AMENDMENT-01.md` records
the sparse result and freezes the accepted formal confirmation contract.

Offline gate:

```sh
python3 harness/selftest235.py
```

Formal result: `RESULTS.md`. Machine gates: `analysis/formal_result.json` and
`analysis/gate_e_result.json`.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

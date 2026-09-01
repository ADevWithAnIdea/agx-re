# EXP-0236 — materialized canonical `falu3` register reach

Generated G17P validation of all three canonical retained-source FP32 FMA source roles and the
destination nibble after explicit first-handoff materialization. `AMENDMENT-01.md` records the
sparse result and freezes the accepted formal confirmation contract.

Offline gate:

```sh
python3 harness/selftest236.py
```

Formal result: `RESULTS.md`. Machine gates: `analysis/formal_result.json` and
`analysis/gate_e_result.json`.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

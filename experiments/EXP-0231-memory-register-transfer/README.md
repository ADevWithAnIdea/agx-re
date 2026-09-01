# EXP-0231 — memory-mediated register transfer on G17P

This experiment tests a completely generated `device_store` → bound memory → `device_load`
sequence across every low/middle/high GPR direction and four store-to-load gaps. It records the
scratch word, source/destination/alias registers, both index-register lifecycle results, complete
three-buffer state, actual dispatched bytes, and a provenance ledger.

Nothing in the generated program is copied from compiler output. `carrier231.metal` is our own
source and supplies only pipeline shape and bindings; the `_agc.main` region is fully replaced.

Offline gate:

```sh
python3 harness/selftest231.py
```

Formal capture on the Neo:

```sh
sh harness/capture231.sh g17p_e0231_run01 canonical 23101 300
sh harness/capture231.sh g17p_e0231_run02 reverse 23102 300
python3 analysis/formal231.py raw/g17p_e0231_run01 raw/g17p_e0231_run02
```

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

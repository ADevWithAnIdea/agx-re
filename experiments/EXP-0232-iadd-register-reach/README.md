# EXP-0232 — canonical `iadd2` register reach

Dense generated G17P validation of the canonical ten-byte b32 register-register `iadd2` access
classes: source A r0..r31, source B r0..r63, and destination r0..r95. The original inherited
destination-boundary hypothesis was refuted: r95 works on G17P, while r96 is the first invalid
destination and raises a contained command-buffer fault.

```sh
python3 harness/selftest232.py
sh harness/capture232.sh g17p_e0232_run01 canonical 23201 300
sh harness/capture232.sh g17p_e0232_run02 reverse 23202 300
python3 analysis/formal232.py raw/g17p_e0232_run01 raw/g17p_e0232_run02
sh harness/capture232_boundary2.sh g17p_e0232_boundary02 canonical 120
sh harness/capture232_boundary2.sh g17p_e0232_boundary03 reverse 120
python3 analysis/boundary232.py raw/g17p_e0232_boundary02 raw/g17p_e0232_boundary03
```

See `AMENDMENT-01.md` and `AMENDMENT-02.md` for the frozen boundary correction. The failed
Amendment-01 verifier is retained as evidence that the inherited M4/G16G r95 fault boundary does
not transfer to G17P.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

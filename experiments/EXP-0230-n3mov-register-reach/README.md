# EXP-0230 — `n3_mov` register reach on G17P

This experiment closes the carrier ambiguity left by EXP-0174. It initializes the architectural
r0..r95 file with distinct full-width codewords, executes generated four-byte half moves for every
encoded source S=0..127, and compares the result against direct-96, modulo-64, zero-high, and
modulo-96 models.

Nothing in the generated program is copied from compiler output. `carrier230.metal` is our own
source and supplies only pipeline shape/bindings; its machine-code region is fully replaced.

Formal capture on the Neo:

```sh
sh harness/capture230.sh g17p_e0230_run01 canonical 23001 300
sh harness/capture230.sh g17p_e0230_run02 reverse 23002 300
python3 analysis/formal230.py raw/g17p_e0230_run01 raw/g17p_e0230_run02
```

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.

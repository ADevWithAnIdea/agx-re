# AMENDMENT-02 — make the own-MSL differential main-resident

Frozen after compiling AMENDMENT-01's `add_dead`, `add_live`, and `sub_live`, before compiling the
revised sources.

Direct observation: all three produced the same 30-byte `_agc.main`:

```text
0b0801081b0a01082b0c0108e7005400010000001d00009000000e000000
```

There is no distinguishable `iadd2` token in that main. Constant indices allowed the compiler to
move or otherwise eliminate the intended arithmetic from the observed main. This is a carrier
failure, not evidence that lifecycle has no encoding.

Revise all three kernels to index input/output from `thread_position_in_grid`. The dynamic address
and per-thread values must keep the arithmetic main-resident. The intended semantic difference is
unchanged: operands dead after the sum versus separately reused after the sum. If the main still
lacks a comparable add/sub instruction, stop consulting compiler output and localize lifecycle by
hardware sweeps alone.


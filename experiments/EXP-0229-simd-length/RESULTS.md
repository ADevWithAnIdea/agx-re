# EXP-0229 Results

## Result

For every currently named `simd_shuffle` mode tested on G17P, the consumed
length is selected by byte `+1` (`mode`):

```text
mode == 0x06 ? 12 bytes : 10 bytes
```

The formal matrix covered modes `0x00`, `0x01`, `0x04`, `0x05`, `0x06`,
`0x08`, `0x10`, `0x14`, and `0x15`, both direction values, both observed
mode-`0x06` byte-`+9` bit-7 classes, and repeated-marker controls. Mode
`0x06` consistently missed the marker at `+10` and executed markers at `+12`
and `+14`; all other named modes executed the markers at `+10`, `+12`, and
`+14`.

This refutes the pre-registered hypothesis that byte `+9` bit 7 selects the
extension. In the tested valid forms, it does not affect consumed length.

## Formal acceptance

Both formal G17P captures passed the frozen analyzer:

- run 01: canonical order, 31 dispatches, zero hangs, 39 quiet samples;
- run 02: reverse order, 31 dispatches, zero hangs, 39 quiet samples;
- zero recovery-count delta, foreign-runner samples, donor fields, stray
  writes, hash errors, or cross-run mismatches;
- the wrong-marker control was rejected.

The machine-readable acceptance result is `analysis/formal_result.json`.
Raw append-only evidence is in `raw/g17p_e0229_run01` and
`raw/g17p_e0229_run02`. The first GPU-reaching pilot and its refutation are in
`raw/g17p_e0229_pilot03` and `AMENDMENT-03.md`.

## Scope

This closes framing for the currently named valid SIMD modes. It does not
claim operation semantics for mode `0x06`, nor validity or length for unnamed
mode values; those belong to later instruction-semantic work.

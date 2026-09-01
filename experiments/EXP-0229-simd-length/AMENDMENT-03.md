# EXP-0229 Amendment 03 — pilot refutes byte+9; mode 0x06 selects 12 bytes

`g17p_e0229_pilot03` was the first attempted capture to reach the GPU. It ran
17 dispatches (8 slot probes + 9 cases), with status OK throughout, zero hangs,
zero GPU recovery delta, and zero foreign-runner samples.

All eight generated SIMD cases produced the same unambiguous marker signature:

```text
miss(+10), hit(+12), hit(+14), post(+16) -> exactly 12 bytes consumed
```

This held for both directions, both byte+9 values `0x11` and `0x91`, and both
first-marker immediates 51 and 87. The first marker register instead retained
its distinct pre-seeded value 46 in every case. Thus the marker was consumed;
the candidate did not coincidentally reproduce either immediate.

The pre-registered model is refuted: byte+9 bit 7 does not distinguish ten
from twelve bytes in the tested mode-`0x06` family. The narrower result is:

```text
simd_shuffle mode 0x06 consumes exactly 12 bytes at the four tested
(direction, byte+9-bit7) points.
```

This also explains the earlier corpus anomaly: mode-`0x06` examples followed
by `02 00` or `03 00` carry those bytes as their extension rather than as
independent compact instructions.

## Revised hypothesis and matrix

The next test changes the candidate mode over every currently named valid
mode `{0,1,4,5,6,8,16,20,21}` in both directions. Mode `0x06` is predicted to
consume 12 bytes; every other named mode is predicted to consume 10. Mode 6
retains both tested byte+9 values and independent marker immediates. A wrong
marker-value model on a ten-byte mode must be rejected.

The program model is also corrected to mark only the candidate's documented
destination/source registers unknown. The pilot marked r15 unknown even though
the SIMD instruction cannot name it at this generated point; that made the
state-dump store addresses unmodelled and reported 96 bookkeeping `stray`
bytes. This did not affect the direct marker readback or length inference, but
the formal capture will require a clean full-state address model.

No fresh Apple output is inspected. The revised matrix, expected marker table,
hang bound, and safety stop are frozen before the next dispatch.

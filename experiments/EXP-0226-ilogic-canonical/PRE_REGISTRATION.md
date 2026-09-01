# EXP-0226 — generated integer LUT2 recipe

Frozen before the first EXP-0226 dispatch. Target: Apple A18 Pro / G17P.
Clean-room class: OWN-SHADER carrier + generated instructions + HW-PROBE. No
fresh Metal logic compilation or machine-code inspection is allowed until this
generated hypothesis has failed at least twice.

## Compiler question

Can a backend generate all 16 two-input 32-bit boolean functions, choose both
sources and a destination, and predict the complete register lifecycle without
copying a compiler token?

## H1 recipe

For desired semantic operands `A` and `B`, use the already hardware-derived
EXP-0146 selector row for the desired truth table, but account for
EXP-0154's proven table/descriptor label swap:

```text
dst=D
srcA=(B<<1)|1       # descriptor byte+1 receives table operand b
op_base=TABLE.base
srcB=(A<<1)|1       # descriptor byte+3 receives table operand a
lut_a_sel=TABLE.lut_a&3
lut_a_free=0
lut_a_z=0
lut_b=TABLE.lut_b
z6=0
outmod=0x80
z8=0
z9=0
```

H1 predicts both named sources are released to zero after all reads, matching
the only complete-state logic carrier currently committed. Destination
publication follows releases, so a destination/source alias holds the result.
This is a valid compiler recipe if the allocator marks both inputs killed; a
retained-source optimization is a separate follow-up question.

The pilot runs all 16 truth tables on asymmetric unique source words, relocates
four asymmetric functions, and tests destination/source and equal-source
aliases. Wrong-operand-order and wrong-function host refuters must mismatch.
All r0..r23 dump words, output poison, sentinel, field/byte round-trip,
whole-program framing, and provenance are checked. `COPIED` and `CARRIER` must
both be zero.


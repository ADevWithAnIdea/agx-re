# EXP-0225 — generated low-32 IMAD/IMUL recipe

Frozen before the first EXP-0225 dispatch.  Target: Apple A18 Pro / G17P.
Clean-room class: OWN-SHADER carrier + generated instructions + HW-PROBE.  No
fresh Metal IMAD/IMUL compilation or machine-code inspection is allowed until
the generated hypotheses below have failed at least twice.

## Compiler question

Can a backend generate, without a donor token, a complete-state-correct
register-register low-32 integer operation

```text
D = (X * Y + K) mod 2^32, K in [0, 255]
```

with independently chosen sources/destination and retained inputs?  `K=0` is
the compiler's IMUL form.

## Generated fields

Every instruction byte is assembled from the following formulas:

```text
b0bit7=1, lenbit=0, b1hi=0
b2_bit0=0, store_en=1, b2_fmt=0x15
dst=D<<1, opmode=0x02
srcC_lo=X<<2
srcB=Y<<3
srcC_desc=(K&31)<<3
mulsel=0xd0|(K>>5)
b11=0
```

The names `srcC_lo` and `srcB` are historical descriptor names; the hardware
hypothesis is simply that byte+5 and byte+6 select the two commutative
multiplicands using the formulas above.

Four fixed-control hypotheses are crossed with asymmetric arithmetic,
relocation, source/destination aliases, `K=0`, and `K=255`:

- H1: `b9=0x20, b10=0x0a`;
- H2: `b9=0x20, b10=0x0f`;
- H3: `b9=0x20, b10=0x1f`;
- H4: `b9=0x22, b10=0x0a`.

H1 is nominated by already-committed G17P raw evidence, not a new compiler
token: changing the old carrier's byte+9 to `0x20` produced `34*10+12=352`
while retaining its observable non-aliased source.  H2/H3 are independent
low-product candidates seen at the old destructive/fetch control point.  H4
separates byte+9 bit 1 from bit 3 on G17P and tests whether the literal/fetch
selector is indeed bit 3 as directly established on G16G.

The host oracle predicts both sources retained.  Releases happen after reads
if a hypothesis refutes that prediction; destination publication is expected
to win a destination/source alias.  A correct destination with an unexpected
source zero is not a pass.  Wrong-immediate and wrong-source host refuters must
mismatch.

## Gates and next phase

- Gate A checks requested fields, actual dispatched bytes, independent field
  decode, and whole-program instruction walk.
- Gate B poisons output, uses unique register seeds and a separate sentinel,
  and dumps r0..r23 after every case.
- Gate C compares against an independent modulo-2^32 host model and includes
  wrong-model refuters.
- Gate D requires `COPIED=0` and `CARRIER=0` for every emitted field.
- A pilot may write only below `work/pilot/`.  After a surviving point is
  frozen in an amendment, formal promotion requires two quiet G17P runs in
  different orders and covers register reach, loads, aliases, and 2..64-op
  generated DAGs.


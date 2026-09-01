# EXP-0225 — RESULTS

## Headline

G17P has a donor-free, compiler-emittable retained-source low-32 integer
multiply-add recipe:

```text
D = (X * Y + K) mod 2^32, 0 <= K <= 255

b0bit7   = 1
lenbit   = 0
b1hi     = 0
b2_bit0  = 0
store_en = 1
b2_fmt   = 0x15
dst      = D << 1
opmode   = 0x02
srcC_lo  = X << 2
srcB     = Y << 3
srcC_desc= (K & 31) << 3
mulsel   = 0xd0 | (K >> 5)
b9       = 0x20
b10      = 0x0a
b11      = 0
```

The descriptor names `srcC_lo` and `srcB` are historical. In this recipe they
are the two commutative multiplicand selectors. `K=0` is IMUL. Low-32 multiply
is sign-agnostic; signed and unsigned values use the same modulo operation.

## Formal result

Two quiet A18 Pro / G17P runs executed the frozen 442-case P2 matrix in
canonical and shuffled order:

| run | positive exact | refuters fired | faults/hangs/restarts | walk/Gate A/donor errors |
|---|---:|---:|---:|---:|
| `g17p_e0225_run01` | 440/440 | 2/2 | 0 | 0 |
| `g17p_e0225_run02` | 440/440 | 2/2 | 0 | 0 |

There are zero cross-run program, output, outcome, bucket, or instruction-byte
mismatches. Both runs have six uncontaminated process samples, and the GPU
recovery count remains 27689 before, throughout, and after both captures.

The positive matrix contains:

- X source r0..r23: 24/24 exact;
- Y source r0..r23: 24/24 exact;
- destination r0..r23: 24/24 exact;
- literal K=0..255: 256/256 exact;
- just-loaded X/Y at visibility gaps 0, 1, and 4: 6/6 exact;
- destination/source and equal-source aliases: 3/3 exact;
- negative-X, negative-Y, and overflowing modulo arithmetic: 3/3 exact;
- deterministic 2..64-operation IMAD DAGs: 100/100 exact.

Every instruction field is generated from a documented rule. The provenance
ledger contains zero `COPIED` and zero `CARRIER` fields. The two host refuters
deliberately predict the wrong immediate and wrong source; both mismatch in
both runs.

## Lifecycle controls

Complete register-state observation resolves byte+9's source releases:

```text
b9 bit 1 = release X (byte+5 selector) after all reads
b9 bit 2 = release Y (byte+6 selector) after all reads
```

`b9=0x20` retains both. `0x22` releases X, `0x24` releases Y, and `0x26`
releases both. Destination publication happens after the reads and releases,
so a destination/source alias holds the new result. The `0x22` test also
directly separates bit 1 from the previously established addend-source selector
at bit 3: setting bit 1 alone does not select the external scalar file.

At the retained `b9=0x20` point, `b10=0x0a`, `0x0f`, and `0x1f` all produced
the same complete state in the six-case pilot envelope. The formal recipe uses
`0x0a`; equivalence outside low-32 IMAD is not claimed.

## Scoreboard relevance

The exact gap-zero load cases show that this IMAD encoding can consume a
just-produced load in either multiplicand role without an intervening filler.
That is consistent with `APPLE9_SCOREBOARD_SLOTS.md`'s producer/consumer
handoff model. This experiment does not by itself identify which fixed IMAD
control bits carry the consumer-slot tag, nor does it count the number of
simultaneously live scoreboard slots.

## Reproduction

```sh
python3 experiments/EXP-0225-imad-canonical/analysis/verify225.py
```

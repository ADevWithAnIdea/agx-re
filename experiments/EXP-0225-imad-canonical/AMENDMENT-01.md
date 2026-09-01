# EXP-0225 amendment 01 — surviving recipe and byte+9 lifecycle split

Frozen after `g17p_e0225_pilot01` and before any L1 dispatch.

## Pilot observation

H1, H2, and H3 are complete-state exact in all 18 positive cases. H1 is the
promoted compiler candidate:

```text
b9=0x20, b10=0x0a
```

It computes the generated eight-bit-literal IMAD/IMUL formula, retains both
non-aliased multiplicands, relocates the destination, and obeys the tested
destination/source aliases. Both wrong host models refute. Gate A and donor
checks are clean and all command buffers complete normally.

H4 (`b9=0x22`) computes the same arithmetic but zeros source X after reading
it. Five cases differ from H1 at exactly X's dump word; `alias_x` is exact
because destination publication replaces that source after the read. Thus
byte+9 bit 1 is directly identified as the post-read release for the byte+5
(`X<<2`) multiplicand. This also separates it from byte+9 bit 3: bit 1 does
not select the external addend file on G17P.

## L1 generated hypotheses

Keep every other H1 field fixed and test:

- `b9=0x24`: release Y only;
- `b9=0x26`: release X and Y.

The model applies releases after both reads and publishes the destination last,
so an aliased destination wins. Each point runs a non-aliased case and both
destination/source aliases. This directly tests the natural hypothesis that
byte+9 bit 2 is Y's symmetric release control; it is not inferred from H4.

After L1, formal compiler promotion will use the retained H1 point regardless
of whether the bit-2 symmetry survives. Formal coverage must include source
and destination reach, loaded operands, aliases, all literal values, and
generated multi-operation DAGs.


# EXP-0226 amendment 01 — LUT dependency controls source lifetime

Frozen after `g17p_e0226_pilot01` and before any P1 dispatch.

All 23 H1 positive cases compute the intended destination value. Seventeen are
complete-state exact under the pre-registered "release both sources" model.
The other six differ only in source registers, with this exact partition:

- constant zero/one: neither source is released;
- `a` and `not_a`: A is released, B is retained;
- `b` and `not_b`: B is released, A is retained.

Every LUT function that semantically depends on both inputs releases both and
was already exact. Both asymmetric-output refuters fired, proving the operand
order and function selector remain observable.

## P1 lifecycle rule

The new oracle releases source A iff the chosen boolean function depends on A,
and releases B iff it depends on B. Releases happen after all reads and
destination publication follows, so a destination/source alias wins. P1
repeats all 16 functions, the relocations and aliases under that rule, plus the
same two output refuters.

This is a hardware semantic, not compiler dataflow analysis: changing only the
LUT selector changes whether a named register is destroyed. A backend can
therefore derive the kill set mechanically from its selected truth table.


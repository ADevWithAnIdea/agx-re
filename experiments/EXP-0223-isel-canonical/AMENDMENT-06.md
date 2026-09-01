# AMENDMENT-06 — load-mode reproduction and bounded classification

Frozen after `g17p_e0223_prov02` and `g17p_e0223_distance01`, before C1/C2 dispatch.

## Reproduction

The reverse-order P1 run reproduced the exact stable partition:

- canonical 0xc0/0xc8: 32/32 complete-state matches;
- all other high modes: 224/224 retain stale pre-load seeds in every explicitly loaded register.

The five r16..r18 collateral losses from the shuffled discovery run did not reproduce (0 in the
reverse run).  They are recorded as an unstable consequence of an unsafe mode, not included in the
canonical encoding rule.  Generated-program SHA-256 agrees by case across orders, and all canonical
complete-output hashes agree.

## Distance result

At each pre-consumer gap 0, 1, 2, 4, 8, and 16:

- 0xc0 and 0xc8 pass both predicate polarities (24/24 total);
- the other fourteen modes make the select consume stale A/B/T/F values (168/168 total).

At gaps 0..8, all four loaded registers also retain their old seeds in the later dump.  At gap 16,
the last-issued load to F/r4 has reached the register by the dump, but the select still returns the
old T/F seed; A/B/T remain stale.  This distinction matters: the bad mode does not necessarily
permanently suppress every load.  It fails to make the in-flight value available to this consumer,
and some writeback may become visible later.

Thus an independent instruction gap does not substitute for the high-mode control over the tested
0..16 range.  The bounded architectural description is **consumer-side load dependency/accept
mode**: `(flags & 0xe0) == 0xc0` permits the select to consume load-produced values immediately and
leaves them architecturally readable.  This does not claim the physical implementation or behavior
beyond gap 16.

## Current compiler-safe fixed point

For an ordinary signed 32-bit register select, use:

```text
flags = 0xc0
```

This means low comparison-mux selector 0, destination publication enabled (bit 4 clear), and the
load-accepting high mode.  Bit 3 remains semantically unidentified after mov, load, both predicate
polarities, every source position, every last-load position, and gaps through 16; keep it clear.

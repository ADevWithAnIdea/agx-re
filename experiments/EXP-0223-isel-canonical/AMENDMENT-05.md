# AMENDMENT-05 — load-accept mode and timing discriminator

Frozen after `g17p_e0223_prov01`, before any P2 or D1 dispatch.

## P1 result

The 256-case direct-load matrix partitions exactly by the upper three bits:

```text
(flags & 0xe0) == 0xc0     32/32 complete-state matches
all other upper modes       0/224 matches
```

Both 0xc0 and 0xc8 work for true and false comparisons; for each of A/B/T/F loaded alone; and with
all four loaded in every choice of final-load position.  Thus bit 3 is a bounded null in both the
mov and load carriers.  The canonical high mode is not a source-release mask: all four loaded
values remain readable after the select.

In every one of the 224 noncanonical cases, each explicitly loaded destination retains its prior
unique prologue seed.  The result is selected from those stale seeds.  Five shuffled cases also
zero r16..r18, which were older prologue loads.  There were no command faults, hangs, measurement
failures, byte-ledger disagreements, decoder aliases, donors, foreign retries, or sentinel failures.

The emitter-facing conclusion is already conservative and useful: emit 0xc0 (or 0xc8) when an
`isel10` may consume load-produced operands.  The architectural name remains open: the evidence is
consistent with a consumer-side accept/wait/writeback mode, but P1 alone does not distinguish a
latency interlock from permanent suppression caused by consuming an in-flight producer.

## P2: order reproduction

Repeat the exact 256 P1 semantic cases in reverse order.  Require:

- 0xc0/0xc8 remain 32/32 exact;
- all explicitly loaded destinations remain stale for the other 224 modes;
- record, but do not require reproduction of, the five collateral r16..r18 losses.  Their stability
  is the discriminator, not a condition for accepting the canonical rule.

## D1: pre-consumer distance

Load all A/B/T/F in fixed order, then insert 0, 1, 2, 4, 8, or 16 independent generated `mov_imm`
instructions before `isel10`.  Cross both predicate polarities and all 16 settings of bits 3,5,6,7
(192 cases).

- If noncanonical modes start seeing the loaded values after a finite gap, classify them as missing
  an in-flight-load wait/forward control in the zero-gap carrier.
- If they continue to select stale values even at gap 16, classify the observed effect as persistent
  suppression within the tested window; do not generalize beyond that window.
- The full dump must also report whether the loads become visible after the select.  Arithmetic-only
  matching is insufficient.

No Apple compiler output is consulted for P2 or D1.  Every instruction remains field-generated.

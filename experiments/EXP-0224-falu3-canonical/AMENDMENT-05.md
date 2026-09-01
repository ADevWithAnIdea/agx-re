# AMENDMENT-05 — materialized source reach corrected by EXP-0236

This is a post-result claim correction, not a change to EXP-0224's frozen experiments or raw data.
EXP-0236 separates ordinary register reach from pending-load acceptance by consuming every source
load through an accepting store before executing the same canonical retained FP32 FMA.

Two sparse and two exhaustive opposite-order G17P pairs establish:

- materialized source A, B, and C each directly read r0..r63;
- encoded source R=64..127 reads r`(R & 63)`;
- every source is retained;
- the destination remains r0..r15.

Thus EXP-0224's mixed r16..r23 P2 outcome is not a materialized-GPR addressability boundary. It is
a pending-producer/consumer-state result and remains relevant to the scoreboard protocol. The
canonical FMA's arithmetic and lifecycle findings are unchanged. Normative evidence and complete
raw captures are in EXP-0236.

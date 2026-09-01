# EXP-0225 amendment 03 — formal compiler envelope

Frozen after `g17p_e0225_pilot03` and before either formal capture.

P2 contains 442 generated cases: 440 positives and two wrong-model refuters.
Every positive is complete-state exact; both refuters mismatch. There are zero
faults, hangs, restarts, Gate-A failures, donor fields, sentinel failures, or
stray writes.

Directly covered by the surviving H1 recipe:

- X, Y, and destination each reach every dumped GPR r0..r23;
- all 256 literal values are exact;
- `K=0` is exact IMUL;
- negative operands and modulo-2^32 overflow are exact;
- destination/source and equal-source aliases obey read-before-write;
- a device-load result is consumed correctly in either source role with zero,
  one, or four intervening instructions;
- 100 deterministic, independently modelled DAGs of 2..64 IMADs are exact.

The formal contract repeats these same 442 cases twice in different orders on
a quiet G17P. Promotion requires 440/440 positive exact results and two fired
refuters in each run, byte-identical generated programs by case name, complete
Gate A/D integrity, zero invalid GPU state, and no cross-run output mismatch.


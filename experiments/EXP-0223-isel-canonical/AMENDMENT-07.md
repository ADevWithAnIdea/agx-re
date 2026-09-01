# AMENDMENT-07 — exhaustive condition and compare-mode discovery

Frozen before any C1/C2 dispatch and before compiling or inspecting any additional select shader.

The generated signed-LT/GT recipe and `flags=0xc0` load mode are now stable.  The next compiler
blocker is the complete integer condition/type map.  Derive it directly from hardware before asking
the Apple compiler for another nominee.

## C1: dense `cc` sweep

Hold `cmp_mode=0x02`, `flags=0xc0`, and every other R1 field fixed.  Sweep `cc=0x00..0xff` over five
input relations:

1. positive A < B;
2. positive A > B;
3. A == B in two separately named GPRs;
4. A = -1, B = +1 (signed less, unsigned greater);
5. A = +1, B = -1 (signed greater, unsigned less).

Negative integers are generated with the already proven no-donor EXP-0222 subtraction recipe, not
loaded from compiler output.  T and F are distinct.  Record the exact five-bit truth vector for
every accepted code, plus faults, no-write, source/collateral changes, and all integrity gates.

The truth vector can nominate signed/unsigned EQ/LT/GT and their complements.  It cannot by itself
name a code whose vector aliases another over these five relations; such collisions require a new
pre-registered discriminator.

## C2: dense `cmp_mode` sweep

Hold `cc=0x07`, `flags=0xc0`, and every other R1 field fixed.  Sweep `cmp_mode=0x00..0xff` over:

- the same five integer relations;
- float32 1.0 < 2.0, 2.0 > 1.0, 1.0 == 1.0, and NaN versus 1.0.

Float bit patterns come from the experiment's known input buffer and therefore exercise the proven
load-accept mode.  Partition each mode by its nine-bit truth vector and complete-state signature.
Do not call a mode integer/float merely because one relation matches; require the full vector.

## Gates and stopping

- All 256 values of each finite byte are dispatched unless the existing hang budget is exhausted.
- Requested fields must equal emitted bytes, archive reread, and independent decode.
- `COPIED=0`, `CARRIER=0`, donor lists empty; complete r0..r23 and all buffers are checked.
- No new Metal compile may be inspected until C1/C2 have been analyzed and at least two independent
  generated attempts at any remaining condition/type ambiguity fail.

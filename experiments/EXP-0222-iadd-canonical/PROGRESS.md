# Progress

- 2026-08-31: EXP-0222 allocated because `EXP-0221` already exists on the Neo. Pre-registration
  written before building or dispatching any EXP-0222 program.
- 2026-08-31: pilot01 dispatched H1. Addition destinations were correct; subtraction was reversed;
  both sources read zero after the op. No faults or hangs, Gate A clean, sentinel clean.
- 2026-08-31: pilot02 dispatched the two frozen alternatives. H2 pair packing produced wrong
  arithmetic. H3 swapped factor-of-four fields produced logical `A-B`, but both sources still read
  zero. AMENDMENT-01 freezes the source-release localization before a fresh own-MSL differential.
- 2026-08-31: AMENDMENT-01's constant-index own-MSL differential was carrier-undecidable: all three
  functions had an identical 30-byte main and no comparable iadd token. AMENDMENT-02 freezes a
  dynamic-thread-index revision; the null result is retained.

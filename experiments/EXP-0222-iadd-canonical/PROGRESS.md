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
- 2026-08-31: AMENDMENT-02's dynamic revision produced three clean 134-byte mains. The probable
  arithmetic tokens nominate five changed bits, but the source also confounds source liveness with
  result use count. AMENDMENT-03 freezes an exhaustive 32-combination generated hardware sweep;
  no compiler-emitted instruction byte is copied.
- 2026-08-31: pilot03 completed all 32 L1 combinations with no fault or hang. `opc_tail` bit 2
  independently zeroes the first physical source and bit 1 independently zeroes the second;
  `0x11` retains both. The other three nominated bits were null only in this bounded context.
  AMENDMENT-04 freezes the R1 recipe and its alias/consumer/64-op validation.
- 2026-08-31: pilot04 (reverse) and pilot05 (canonical) passed all 16 V1 cases. Per-case generated
  program SHA-256 and full-buffer output SHA-256 agree between runs, including the 64-op DAG.
  These remain disclosed pilots, not promoted captures. AMENDMENT-05 freezes load-provenance and
  r16..r23 tests before extending the claimed envelope.
- 2026-08-31: pilot06 passed all 11 P1 cases. Direct load-to-iadd consumption needs no provenance
  route change in either physical operand, and R1 works through r23. AMENDMENT-06 and the capture
  contract freeze 157 semantic cases plus the slot probe for two formal runs.
- 2026-08-31: formal run01 (canonical) and run02 (shuffle seed 222) completed. All 312 exact
  semantic observations match; both refuters fire; 0 per-case program/output disagreement, Gate-A
  mismatch, donor field, foreign runner, recovery, fault, hang, or sentinel failure. `RESULTS.md`
  promotes the bounded r0..r23 register-register recipe.

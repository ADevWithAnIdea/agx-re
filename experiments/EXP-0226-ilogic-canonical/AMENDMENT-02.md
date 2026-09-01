# EXP-0226 amendment 02 — corrected lifecycle pilot result

Frozen after `g17p_e0226_pilot02` and before any later EXP-0226 dispatch.

The amended P1 oracle from `AMENDMENT-01.md` passed on Apple A18 Pro / G17P:

- 23/23 positive cases were complete-state exact;
- 2/2 deliberately wrong host models were refuted;
- all 25 P1 cases had `status=OK`, zero restarts, zero Gate A errors, zero
  `COPIED` or `CARRIER` provenance, and intact sentinels;
- no positive case had an unpredicted register-state difference.

This confirms the tested rule: the selected LUT function releases exactly the
named source operands on which that function semantically depends. Constants
retain both inputs; single-input functions release only the used input; true
two-input functions release both. Destination publication follows those
releases in the tested aliases.

This is pilot evidence, not full EXP-0226 closure. In particular, the pilot does
not close the instruction's complete register-role reach, modifier space,
finite-field behavior, or every encoding bit.

Raw pilot artifacts are retained at:

```text
experiments/EXP-0226-ilogic-canonical/work/pilot/g17p_e0226_pilot02/
```

# EXP-0228 — pre-registration (frozen before first dispatch)

Target: Apple A18 Pro / G17P. Clean-room class: OWN-SHADER carrier +
GENERATED instructions + HW-PROBE. No fresh Metal output for this operation is
inspected.

## Question

Does the four-byte boundary proven at low-nibble-9 byte+2 `0x20`/`0x21` extend
across the selector-0/1 class, including off-natural upper mode bits?

## Hypothesis

For generated `09 01 XX 05`, every tested `XX` satisfying `XX & 7 in {0,1}`
consumes exactly four bytes. The low three bits select the compact form; upper
five bits do not extend its length.

This pilot tests 22 fixed `XX` values:

```text
compiler-observed / prior controls:
18 19 20 21 30 31 38 39

off-natural upper-bit coverage:
00 01 08 09 10 11 28 29 40 41 78 79 f8 f9
```

The off-natural set includes both selectors at upper-mode values 0, 1, 2, 5,
8, 15, and 31, reaching the maximum five-bit mode value. This is not yet the
full 64-value dense sweep; it is the bounded safety pilot that decides whether
that sweep is justified.

## Observation and controls

The candidate destination is r0. A generated `mov_imm r6,87` begins at +4,
followed by markers at +6/+8/+10 and a resynchronization marker at +12. Since
the candidate cannot publish to r6 under the established destination field,
r6=87 is the primary boundary witness. The complete r0..r23 state and all three
buffers are captured.

An identical `XX=0x20` program is scored against the deliberately wrong r6=88
model. It must be rejected while the hardware observation still infers length
4. Slot probes, exact archive reread, Gate A, donor ledger, poison, sentinel,
timeouts, hang budget 1, and measured quietness are inherited from EXP-0227.

## Outcomes

- All 22 status-OK cases uniquely infer `[4]`: authorize an amendment for the
  full 64-value sweep and two formal runs.
- A status-OK case produces another signature with the post marker intact:
  refute the class rule at that byte value and record the measured length.
- Fault/hang, missing post marker, slot mismatch, device recovery, foreign
  runner, Gate A error, or donor field: inconclusive/invalid for the affected
  claim; do not smooth it into a length result.
- Device unresponsiveness invokes the plan hard stop with no recovery attempt.

This pilot cannot close the class or Step 1.

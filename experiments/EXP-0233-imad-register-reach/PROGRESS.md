# EXP-0233 progress

- Pre-registered 192 dense per-role reach cases, two negative controls, and a repeated r95/r96/r127
  destination-boundary sequence before dispatch.
- Work-only edge pilots passed at X=r63, Y=r31, and destination r95.
- Main canonical/reverse runs pass: X r0..r63, Y r0..r31, and destination r0..r95 are exact in both
  runs; both wrong-oracle controls fire.
- Boundary01 and replacement reverse-order boundary03 pass: r95 is exact, while r96 and r127 raise
  contained command-buffer faults and do not wrap; exact controls pass after each recovery.
- Boundary02's shader records agree but its later-overwritten ancillary metadata is excluded under
  `AMENDMENT-01.md`. Capture wrappers now reject duplicate IDs before starting target sampling.
- All accepted runs pass target/provenance auditing with no foreign runner, hang, or restart.

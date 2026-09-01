# EXP-0236 progress

- Pre-registered 63 sparse source-role cases, 16 dense destination cases, and two controls.
- Two sparse opposite-order runs agree exactly: after explicit first-handoff materialization, all
  three source roles are direct through r63 and encoded r64..r127 alias modulo 64.
- `AMENDMENT-01.md` froze full confirmation over every encoded source value before formal runs.
- Both 410-dispatch formal runs pass the semantic and target-quietness gates with zero faults,
  hangs, recoveries, restarts, foreign activity, framing failures, donor fields, or carrier fields.

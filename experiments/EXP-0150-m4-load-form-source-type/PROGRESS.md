# PROGRESS — EXP-0150

Append-only. One entry per milestone (`SUBAGENT_BRIEF.md`: assume the host will
crash mid-run; re-orient from this file, not from memory).

## M0 — 2026-08-29T00:02:48Z — PRE-REGISTRATION FROZEN (before any code, before any run)

- `PRE_REGISTRATION.md` sha256
  `0acd69b3bab9540f1b3d5ef5a17ee5b6d4c91cb8a03ac0172f2c11dba32e1781`
- repo revision at freeze: `7faf0db77813ca4416d10b60e3424ee177215273` (dirty:
  sibling experiments' uncommitted work; per `SUBAGENT_BRIEF.md` the revision is
  *recorded*, not gated on, so a sibling landing does not abort this experiment).
- The predictions for the never-tested `01` / `10` cases are in §4 (H1) and were
  written before a single case was assembled. Nothing below may edit them.
- Predicted headline: **H1 REFUTED (H1-reg wins)** — `device_load.extmode[7:6]`
  is register-bit-5 plus a must-be-zero bit, not a form field; accepted set with a
  fixed consumer `{0x0E, 0x0F}`. **H4 CONFIRMED** — ALU-sourced operands are *not*
  indifferent; they require the complementary code `0x00`.

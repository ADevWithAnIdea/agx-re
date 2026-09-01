# EXP-0230 progress

- Pre-registered dense source-register and half-selection matrix before dispatch.
- Pre-registration committed as `40c87107` before hardware dispatch.
- Work-only Pilot01: eight low-source cases exact; seed and post-body witnesses passed.
- Work-only Pilot02: sources 123..127 selected the pre-registered `mod64` model; the H96 primary
  was preliminarily refuted and both wrong-oracle controls fired. No pilot is formal evidence.
- Amendment 01 freezes a model-neutral formal gate before either formal capture.
- Formal run01/run02 complete: 522 dispatches each, zero faults/hangs/victims, 47/49 quiet samples,
  zero foreign runners, zero recovery-count change.
- `mod64` is the unique zero-mismatch model. Formal gate remains red only because the independent
  seed witness failed for both halves of S=92..95 under both plans (16 cases); successor required.

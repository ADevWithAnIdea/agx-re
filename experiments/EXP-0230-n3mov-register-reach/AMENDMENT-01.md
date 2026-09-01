# EXP-0230 Amendment 01 — model-neutral formal gate

Frozen after the disclosed non-evidence pilots and before either formal capture.

The original `formal230.py` mistakenly made the experiment pass only if the pre-registered primary
model H96 won. That is not the contract in `PRE_REGISTRATION.md`: the experiment pre-registered four
competing models and says a clean observation may refute H96. A formal gate must therefore require
one unique zero-mismatch model, not one favored answer.

Pilot02 (work-only, never formal evidence) exercised encoded sources 123..127 first. Every observed
destination matched the `mod64` prediction and contradicted H96/H64Z/H96W; both wrong-oracle
controls fired. This is a disclosed pilot observation, not a promoted result. It motivated no new
hypothesis and changed no case, byte, seed, or hardware measurement. Amendment 01 changes only the
formal acceptance calculation:

- all four originally frozen models remain exactly the same;
- a pass requires exactly one model with zero mismatches over every semantically decidable main
  record in both runs;
- every other model must have at least one mismatch;
- Gate A, donor/copy, descriptor coverage, and control checks are made explicit;
- the selected model is reported mechanically rather than hard-coded.

This amendment is frozen before `g17p_e0230_run01` and `g17p_e0230_run02` exist.

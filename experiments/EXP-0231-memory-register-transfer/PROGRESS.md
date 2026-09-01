# EXP-0231 progress

- Pre-registered the 144-case source × destination × gap matrix and two negative controls before
  the first hardware dispatch.
- Offline generation/framing/provenance gate passes for all 146 non-slot-probe programs.
- Pre-registration committed as `bb97fcf1` before hardware dispatch.
- Two work-only post-freeze pilots passed: low→low at gap 0 and high→high at gap 16.
- Formal canonical/reverse runs complete: 144/144 main cases exact per run, two controls fired,
  exact is the unique zero-mismatch model, and all five gates pass.

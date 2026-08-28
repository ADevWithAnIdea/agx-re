# PROGRESS

- 2026-08-28T00:00Z pre-registration frozen: 138-format target matrix derived
  from public MTLPixelFormat.h; 858-case grammar (compute bundle x138,
  render-axis x690, conversion x13, layout x12, sparse x5). Pre-freeze
  exploration moved to provenance/pre_freeze/.
- run.py --run-id m4-20260828-run01 --execute: ran 131/858 cases cleanly,
  then correctly STOPped on cap_compute_00255_Depth24Unorm_Stencil8
  (SIGABRT, "invalid pixelFormat (255)" -- F3 in PRE_REGISTRATION.md, a real
  hardware/API fact, not a bug in what it measured). Partial capture
  retained (never reused) at provenance/quarantined_attempt1/. Harness fixed
  to full per-(format,axis) granularity (no bundling at all); full 138x11
  precheck at provenance/pre_freeze/precheck/ found exactly 2 device-
  unsupported formats (255, 262) plus the already-known render-ineligible
  family + a newly-confirmed integer-blendable restriction + one
  depth_stencil direct-attach restriction (X32_Stencil8). Contract
  regenerated: 1548 total cases. Run ids retired to m4-20260828-run03/run04
  (never reusing run01/run02).
- run.py --run-id m4-20260828-run03 --execute (corrected F3 grammar): ran
  1462/1548 cases cleanly, then correctly STOPped on
  cap_depth_stencil_00261_X32_Stencil8 (SIGABRT, "not depth renderable").
  Root cause: analysis/gen_formats.py misclassified X32_Stencil8/
  X24_Stencil8 as kind=float/family=depthstencil (same bucket as the real
  combined depth+stencil formats) instead of kind=uint/family=stencil_view.
  Partial capture retained at provenance/quarantined_attempt2/ (never
  reused). Fixed classifier; corrected contract; re-ran the full 138x11
  precheck (0 mismatches between predicted expect_may_abort and observed
  abort/ok across all 1518 capability cases) -- also refuted the initial
  assumption that X32_Stencil8 needs a texture view for direct stencil
  attachment (it works directly once correctly typed). Run ids retired
  again: real captures now m4-20260828-run05/run06.
- run.py --run-id m4-20260828-run05 --execute: COMPLETE, CLEAN, 1548/1548
  cases, no STOP. Attempting run06 failed the cross-run preflight gate:
  "run02 provenance differs from closed run01" -- run.py/verify.py both
  compared git_revision (not just authored_sha256) across runs, and two
  sibling experiments (EXP-0132, EXP-0134) landed commits on master in
  between, moving HEAD with zero change to this experiment's own files --
  the EXP-0082 landmine SUBAGENT_BRIEF.md already documents. Fixed both
  files (gate on authored_sha256 only; git_revision still recorded, not
  gated). run05 retained (complete, clean, valid data) but not promoted --
  provenance/quarantined_attempt3/ -- since pairing it with a run captured
  under different (bugfixed) run.py/verify.py bytes would violate the
  "harness identical across the pair" invariant the gate exists to prove.
  Run ids retired again: promoted pair is now m4-20260828-run07/run08.

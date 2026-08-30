# EXP-0142 — PROGRESS

- **Re-oriented** from the committed `raw/prefreeze/` calibration (treated as calibration,
  never as evidence). Read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`,
  `FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`.
- Blocking-field census confirmed against `tools/agx-isa/validation.json`: **46 fields**
  over `tex_sample`(9) `tex_coord_setup`(10) `tex_write`(13) `tex_deriv`(4)
  `imageblock_load`(5) `imageblock_store`(5).
- Rebuilt `texpersist` / `renderpersist` / `shdump`. Patched `renderpersist.m` to print
  `ERRDOM` (FIELD-SWEEP-PROTOCOL 7.2 needs the OS fault classification, not just STATUS).
- Pre-freeze calibration, all three carriers, **all matched their host oracle exactly**:
  A `tex_sample8` -> 1,102,203,304,405,506,607,708 + sentinel 12345;
  B `tex_write3` -> three texels written, all others still at the reset sentinel;
  C `frag_deriv` (rewritten pre-freeze: the committed version did not compile, and its
  cross-derivatives were 0, indistinguishable from the Apple9 silent zero) -> (1,2,4,11).
  Transcript: `raw/prefreeze/carrier_calibration_smoke.txt`.
- Found and recorded pre-freeze: the explicit-imageblock **fragment** form no longer
  compiles on macOS 26.6.2 / GPUCompiler 32023.886. The tile-pipeline route does compile
  and emits `imageblock_load`; Arm D is pre-registered as **conditional**.
- **PRE_REGISTRATION.md + CAPTURE_CONTRACT.json FROZEN** at repo rev `7faf0db7`,
  23,646 pre-registered cases.

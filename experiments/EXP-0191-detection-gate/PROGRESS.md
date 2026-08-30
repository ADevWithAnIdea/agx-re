# EXP-0191 — PROGRESS

- **2026-08-30 ~09:20** — read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`,
  `FIELD-SWEEP-PROTOCOL.md` §3/§5, EXP-0190's `RESULTS.md`, `collect_raw.py`, `audit.py`,
  `blind_arm_scan.py`, `classify_underscore.py`. Confirmed the live `validation.json`
  differs from EXP-0190's pinned snapshot in exactly 6 rows (the 5 withholdings +
  `falu2i.imm_flag`) → 550/1040 recomputed from the live file.
- **09:34** — `PRE_REGISTRATION.md` committed to disk at revision `cd2f05dd` (tree clean),
  **before** any verdict was computed: role table by intent, validity rule (incl. the
  error-payload exclusion), the gate, both join levels, the reclassification trigger, and
  the D1–D4 discrimination proof.
- **09:38** — `analysis/detection_gate.py` written and run. 725 raw files, 5,200,282 lines,
  ~24 s. 79 INERT fields, 83 arms: **51 pass / 32 fail** (strict). D1 PASS (0 of 8
  no-observation arms pass), D3 PASS. D2 136/138, D4 55/57 — both sets of exceptions
  investigated in raw and found to be the gate being stricter than the oracle, not broken.
- **09:40** — post-hoc sections added after D4 pointed at `sig_of()` counting a fault as
  movement: 7 of 337 STABLE-LIVE arms have <2 distinct valid payloads; 4 emitter-grade rows
  rest entirely on one. Written to `reclassify.json → post_hoc_candidates`, explicitly NOT
  a verdict of this experiment.
- **09:42** — `RESULTS.md`, `README.md`, `manifest.json` written. Re-run verified
  **byte-identical** (idempotent). Nothing outside `experiments/EXP-0191-detection-gate/`
  was created or modified. No `git commit`.

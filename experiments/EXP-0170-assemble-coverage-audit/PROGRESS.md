# EXP-0170 — PROGRESS

Append-only. Timestamps are local (M4 repo host).

- **2026-08-30 M0** — dispatch received. Read `CLAUDE.md`, `CODEX.md`,
  `experiments/SUBAGENT_BRIEF.md`, `experiments/FIELD-SWEEP-PROTOCOL.md`,
  `docs/evidence-classification.md`, `tools/agx-isa/isadb.py::assemble()`,
  `work/merge_verdicts.py`, `experiments/EXP-0164-inert-audit/analysis/collect_raw.py`,
  `experiments/EXP-0166-exp0146-recovery/RESULTS.md`. Repo rev `4b16d0b4`,
  `db.json` sha256 `07ad894d…`, `validation.json` sha256 `1fd62e55…`.
  Schema survey of `experiments/*/raw/**/*.jsonl` done (610 files; record shape
  varies per experiment — `bytes`/`value`/`field`/`instr`/`carrier`/`arm` are the
  common columns). **NO device work in this experiment; nothing was dispatched.**
- next: freeze `PRE_REGISTRATION.md` before any verdict is computed.
- **2026-08-30 M0b** — coordinator amendment received *before* any verdict was computed:
  extend scope with **Arm C**, a general audit of the *disassemble → re-assemble → compare*
  self-check idiom (symmetric-defect blind spot), reported separately from the coverage
  numbers. EXP-0167 owns the EXP-0158-specific ledger check; this experiment takes the
  general "who else shares the blind spot" question only. Folded into the pre-registration
  below before freezing.
- **2026-08-30 M1** — `PRE_REGISTRATION.md` frozen (three arms A/B/C, thresholds fixed).
  `db.json` and `validation.json` snapshotted into `work/`. No verdict computed yet.
- **2026-08-30 M2** — Arm A complete (`analysis/static_overlap.py` → `static_overlap.json`).
  **H1 CONFIRMED, F1 did not fire: 53 fields over 42 instructions overlap their own
  descriptor's `match`.** H2 CONFIRMED, F2 did not fire: the closed form
  `2^(w−popcount(match∩span))` reproduces all six of EXP-0166's tabulated numbers exactly.
  Reachable-fraction histogram 1/2:21, 1/4:18, 1/8:7, 1/16:3, 1/32:4. One field
  (`falu2_uni.uni_mode`) is fully pinned — 1 of its 2 encodings reachable. Zero field↔field
  span overlaps. **28 of the 53 are currently emitter-grade.**
- **2026-08-30 M3** — Arm B indexer complete (`analysis/coverage_index.py`): 4,677,940 raw
  lines parsed, 771,793 per-value field records, 0 unparseable; 4,354 sweep groups, 3,618
  informative, 5 degenerate, **37 collapsed groups in 4 experiments** (EXP-0138, EXP-0139,
  EXP-0146, EXP-0147). First classification pass: 617 emitter-grade fields → 435 FULL-RANGE,
  8 UNDER-COVERED, 174 UNKNOWN. **F3 FIRED (<25 UNDER-COVERED).**
- next: add per-field span unions + a dedicated audit of all 53 overlapping fields against
  observed span coverage, then Arm C.

# EXP-0181 — PROGRESS (append-only)

- 2026-08-30 M0: dispatch received. Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md,
  FIELD-SWEEP-PROTOCOL.md §3, docs/evidence-classification.md, validate_labels.py,
  match_overlap_report.py. Pure analysis; no device touched.
- M1: baseline captured. validate_labels exit 0 (WARN db_sha256 is the orchestrator's).
  52/166 emitter-relevant emittable, 617 emitter-grade fields, 1036 fields, 172 instrs.
  match_overlap: 34 overlapping rows, 0 zero-free-bit, 0 vacuous emitter-grade.
  The four EXP-0168 defects CONFIRMED still open in db.json a77f8cfa…:
    iter_at.grp (free 1), pixel_order.scope (free 6), reg_move_cb.form (free 4),
    shift_amt_move.kind (free 4).
- M2: read EXP-0168 §7, EXP-0175 §1-§7, EXP-0173 §1-§2, EXP-0167 §0-§1, EXP-0174 §1-§3.
  Generated-corpus mnemonics (EXP-0167 assemble_defect_check.json) = 18; of the weak-30
  only `mov_imm` is in it. EXP-0174 generated `n3_mov` (840 32-bit copies, 0 failures).

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
- M3: built three re-runnable instruments in analysis/:
  scan_dispatch_evidence.py (was every instruction DISPATCHED? -> dispatch_evidence.json),
  verify_dispatched_bytes.py (do the dispatched bytes decode BACK to the descriptor?
  -> dispatched_bytes_check.json), anchor_check.py (the unmutated anchor per experiment
  -> anchor_check.json), ab_gate.py (corpus gate, EXP-0175's subprocess-fixed copy).
  Baseline gate re-measured: clean=833/1080 leftover=388604 tokens=25419 roundtrip 302/0 ALL PASS.
  FINDING: all 30 weak instructions WERE dispatched on hardware. But five of them
  (bf_add_dst, bf_fma_dst, cvt_bf16, cvt_f2h_dst, hminmax) dispatched anchors that the
  COMMITTED descriptor+length rule does NOT decode.
- M4: TASK 2 db.json edits APPLIED and VERIFIED. db.json sha a77f8cfa... -> 1ada4e7b...
  Narrowed: iter_at.grp (bits0-7 -> bit7), reg_move_cb.form (16-23 -> 20-23),
  shift_amt_move.kind (16-23 -> 20-23, enum re-based to {1,3}).
  NOT narrowed: pixel_order.scope -- free bits non-contiguous AND the match is itself
  contradicted by EXP-0147's committed accept sets (DEF-0181-1, semantics note only).
  GATES: corpus 833/1080, 388604 leftover, 25419 tokens (IDENTICAL); roundtrip 302/0 ALL PASS;
  match_overlap 34 -> 31; validate_labels exit 0 (only the db_sha256 WARN). ZERO orphans.
  **db.json is STABLE from here unless a later check forces a fix.**
  NOTE: the orchestrator's EXP-0179 commit landed mid-session; the live headline is now
  53/166 emittable and 621 emitter-grade fields, not 52/617. My edit moved neither.

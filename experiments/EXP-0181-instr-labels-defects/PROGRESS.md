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
- M5: TASK 1 deliverable written. analysis/instruction_labels.json -- 30 rows.
  ALL 30 were dispatched on hardware (230,804 raw cases across 18 experiments).
  Recommended 18 hardware-run, 7 isolated-byte-diff, 5 STAY WEAK
  (frag_depth_store, frame_marker_compact, n2_op6, sfu_marker, vary_slot -- each with
  every field at emitter grade, which is exactly why the field-only rule is unsafe).
  Gate arithmetic: 53 now; 23 if gated on today's labels; 48 with these recommendations.
- M6: analysis/orphaned_validation_rows.json written -- 0 orphans, 0 created, 3 RE-SPANNED
  (iter_at.grp, reg_move_cb.form, shift_amt_move.kind) with re-scored recommended rows.
- M7: README.md, PRE_REGISTRATION.md, RESULTS.md, manifest.json written. Nothing committed.
- M8: FINAL re-verification after the orchestrator's commits 29fb7378 / e9080bfb landed
  (which also committed EXP-0181's db.json edit). Live state re-measured:
    db.json sha 1ada4e7b... (committed), 172 instructions / 1036 fields
    corpus 833/1080, 388604 leftover, 25419 tokens; roundtrip 302/0 ALL PASS
    match_overlap 31 rows, 0 zero-free-bit, 0 vacuous
    validate_labels exit 0; emittable 53/166; the DEF-0173-1 gap is still exactly the same 30
  instruction_labels.json and orphaned_validation_rows.json regenerated against the newest
  validation.json with no mismatch. EXPERIMENT COMPLETE. Nothing committed by me.

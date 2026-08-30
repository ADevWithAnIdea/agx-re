# EXP-0169 progress log (append-only)

## 2026-08-30 — M0: dispatch received, governing docs read
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, EXP-0164's `analysis/collect_raw.py` +
`analysis/audit.py` + `analysis/withhold_unverifiable.json`.
Device work is BLOCKED (EXP-0167 holds a quiet window, EXP-0168 queued).
Plan: all analysis + pre-registration offline first, then request the window.

## 2026-08-30 — M1: the 144 withheld fields characterised offline
144 fields, reasons: no-field-records 60, no-raw 47,
field-named-but-unstructured 24, raw-present-but-unattributable 13.
By descriptor: falu2 13, tex_addr_setup 11, matrix_mac 10, falu2i 9,
half_alu_ext8 7, link_save_restore 6, reg_move_* 23 (c0 5 / c1 4 / c2var 5 /
c9 5 / cb 4), tex_sample 5, half_alu 4, ... 
By citing experiment: EXP-M4-14 49, EXP-0140 20, EXP-0119 10, EXP-0112 10,
EXP-O2C 10, EXP-0090 8, ...

## 2026-08-30 — M2: 12 of the 144 need a CITATION FIX, not a device
Wrote `analysis/recitation.py`. EXP-0164's `audit.py::gather()` collects
observations ONLY from the experiments named in that field's `evidence` array,
so a field promoted on EXP-0016 is judged on EXP-0016's raw alone even when a
later experiment swept the same db field value-by-value with bit-exact records.
Re-running EXP-0164's OWN gate (`stable_live`, thresholds copied verbatim) over
the WHOLE raw index instead of only the cited experiments:

  RECOVERABLE-BY-CITATION   12
  RECORDS-BUT-FAILS-GATE     3   (icmp_pred.cond 97.66%, pixel_order.kind
                                  single run, ray_move.b3 255 values 0 moved)
  NO-RECORDS-ANYWHERE      129

The 12: device_load.base_slot, device_load.idx_off (EXP-0141);
falu2.opsel, falu2.srcA_reg, falu2.srcB_reg, falu2.srcB_reg_top (EXP-0153 —
G17P, i.e. BETTER than the cited M4/A18 evidence); falu2.srcB_reg_top also
EXP-0138; falu_srcmod12b.ctrl, falu_srcmod12b.opsel (EXP-0138);
ibitcount.form, ibitcount.op_enable, ibitcount.srcdesc (EXP-0139);
icmp_pred.dst_pred (EXP-0139).
NOTE: several of these move the field's `target` from A18 to M4, because the
uncited experiment ran on the M4. That is the orchestrator's call, not mine.

## 2026-08-30 — M3: scope split with EXP-0168 applied
Coordinator directive: EXP-0168 owns the field NAME `dst` on all 14 descriptors
that carry it, plus the 12 "one-field-away" fields (incl. `mov_imm.imm_top`,
`pixel_order.kind`, `stop.reserved`). Removed from my verdict scope:
falu2.dst, falu2i.dst, get_sr.dst, reg_move_{c0,c1,c2var,c9,cb}.dst,
mov_imm.imm_top, stop.reserved  (10 fields).
`dst` is still SWEPT here as the primary liveness-ladder instrument (which
register slot changed is my detection oracle) but NO VERDICT is emitted for any
`.dst` field — the raw is recorded and attributable, the verdict is EXP-0168's.
Open question for the orchestrator: is `get_sr.dst_hi` one of the 12?
My design already answers the coordinator's `uniform_mov.dst` hypothesis: the
oracle is the FULL 16-GPR dump, so "which register slot changed" is visible.

Device scope after the split: 57 fields.
  A falu2 family 17 : falu2 8, falu2i 8, falu2_uni 1
  B EXP-M4-14 ALU 15: half_alu 4, half_alu_ext8 7, half_alu_fma12 2, iunary 2
  C reg_move     18 : c0 4, c1 3, c2var 4, c9 4, cb 3
  D misc          7 : bf_alu.opsel, icmp_pred.cond, get_sr.{dst_hi,sr_sel},
                      device_store.{base_slot,idx_off,index_reg}
Out of scope, explicitly handed on (needs a graphics / texture / RT / control-
flow / spill-frame harness): tex_addr_setup 11, matrix_mac 10,
link_save_restore 6, tex_sample 5, frag_color_pack 3, frame_prologue 3,
rt_query_traverse 3, simd_shuffle 3, spill_frame_marker 3, frag_color_store 2,
iter 2, simd_reduce 2, vary_store 2, call 1, if_push_pred 1,
imageblock_load 1, imageblock_store 1, jump 1, ray_move 1, rt_intersect 1,
simd_ballot 1, tex_deriv 1  = 64 fields.

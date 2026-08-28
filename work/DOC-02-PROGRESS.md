# DOC-02 labelling — progress log

## 2026-08-28 M0: orientation
- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, docs/evidence-classification.md.
- db.json sha256 = eaca7256f0f2dcd79ec01aac9dd825f888ceb23f3b720b755ab384ad686e90af
- 170 instructions, 170 unique mnemonics, 1025 fields total.
- DESK TASK: no GPU work. Reading committed evidence only.
- Next: harvest EXP-NNNN citations out of db.json notes + experiment RESULTS.md corpus.

## 2026-08-28 M1: docs/isa/README.md read
- Harvested family-level evidence: falu2 opsel (256-value HW sweep, A18 EXP-0005), falu2 operand
  layout (EXP-0006 A18), minifloat imm (16 constants spliced, A18), iadd2 addsub polarity (RT-1a-FIX),
  device_load field map (EXP-0012 + RT-1a-FIX + EXP-M4-10 ISA-1), tex_sample slots (EXP-0016/0034),
  atomic op codes (EXP-0018), get_sr sr_sel (EXP-0031), matrix_mac operands (EXP-O2C splice),
  rt_intersect sub-fields = INERT/byte-diff only (RT-5/RT-10 retraction).
- Key retraction already in docs: 0x54/0x56 "cache bit" DOWNGRADED to UNKNOWN (EXP-0086).
- Next: read M4 ISA experiments 0086/0087/0089/0099/0101/0102/0103/0104/0105/0106/0111/0112/0113/0114/0115/0119.

## 2026-08-28 M2: M4 ISA experiment evidence harvested
- EXP-0099/0105/0112/0113/0119: falu2 family register/lifetime/ctrl fields fully characterized.
  * srcA_reg_top/srcB_reg_top (bit15/31): HW-tested INERT for addressing+retention, role UNKNOWN
    (0099 falu2; 0105 falu2i; 0119 falu2_ext both slots, falu3_srcmod12 both slots, 15-deep pressure).
  * opflags bit19/20 = source release (HW), bit21 = dst publication (attribution 0090/0099),
    bits22/23 = SILENT CORRUPTORS (0105).
  * ctrl bits0/1/5/6 corrupt, bits2/3/4 inert (0105 + 0113 = full 7-bit map).
  * mod_hi bit44 corrupts (0105).
  * register aliasing r(R mod 64) for R in [64,112]; FAULT at {126,127} (0112 dense 28-pt sweep).
- EXP-0101: device_load extmode = 2*target_reg (BLOCKER 1 resolved); EXP-M4-13 dst formula REFUTED.
  dst_lo/dst_ext9 must be copied VERBATIM -> single-template-inference.
  falu2i mods must be 0xC0 for load-sourced operand.
- EXP-0112: idx_off 0..2047 full range swept; iadd2 srcB_imm K 0..127 + wrap at 128.
- EXP-0114: tex_sample tex_slot (op+4) upper nibble 16/16 swept, 14 silent-zero holes,
  low nibble 12 values inert -> hardware-run.
- DISAGREEMENT FOUND: EXP-0090 finding_1 (falu2 opflags=2 fails / needs 3) vs EXP-0112
  (opflags 0..3 all correct on carrier_dag). Carrier-dependent. Report, do not resolve.
- Next: EXP-0104/0115 (CF/SIMD), EXP-0111 (FS), EXP-0092 (get_sr), EXP-M4-13/14 status.

## 2026-08-28 M3: evidence index complete
- Read db.json semantics/notes for all 170 instructions (work/_db_semantics.txt) — this is the
  richest per-field evidence index in the repo and carries all 2026-08-28 retractions.
- Additional per-field HW sweeps located:
  * EXP-0082: device_load idx_off FULL 0..2047 dense; elem_size codes {0..4}+23 raw values;
    ldform_hi11 bits2-7 swept 6 values, semantics UNKNOWN.
  * EXP-0083: device_load base_slot 0..255 EXHAUSTIVE (1..30 distinct, 31..127 zero, 128..255 mirror).
  * EXP-0092: get_sr sr_sel 0x00..0xff EXHAUSTIVE (256, zero faults); get_sr dst/dst_hi +
    device_store index_reg lockstep boundary sweep 0..127 (0-95 ok, >=96 fault, 112 NONDETERMINISTIC).
  * EXP-0100: threadgroup-space idx_off full 0..2047 dense.
  * EXP-0104/0115: icmp_pred dst_pred 0..15; if_push_pred pred 0..15 INERT; simd_shuffle lane OOB;
    jump offset 162 splice points (checkerboard + 13 nondeterministic).
  * EXP-0114: tex_sample tex_slot upper nibble 0..15 + 12 low-nibble values.
  * EXP-M4-14 (A18 splice): 56 field resolutions with per-field value sweeps.
- Convention decided: evidence ids are experiments/ directory names, so RT-* red-team A18 splice
  experiments are valid pointers alongside EXP-NNNN.
- Next: write work/gen_validation.py -> tools/agx-isa/validation.json.

## 2026-08-28 M4: DELIVERABLES COMPLETE
- tools/agx-isa/validation.json written (170 instructions, 1025 fields, 308 KB).
- tools/agx-isa/validate_labels.py written; passes on the artifact; 10 mutation tests all exit 1.
- work/DOC-02-LABELLING-REPORT.md written.
- work/gen_validation.py retained as the auditable, re-runnable generator.
- HEADLINE: emitter-grade fields = 166/1025 (16.2%). untested = 298 (29.1%).
  Emittable instructions = 5/170 (frame_prologue, link_save_restore, spill_frame_marker, stop,
  tex_addr_setup) — 4 of the 5 are A18-only.
- 9 experiment disagreements recorded (D1..D9); D1 (ibitcount.cache A18 vs M4 on identical bytes)
  is the spec's cited EXP-0119 A18<->M4 contradiction.
- NOT committed (orchestrator commits).

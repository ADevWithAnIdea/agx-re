# EXP-0186 docs-gap — PROGRESS

- 2026-08-30 T+0: dir created. Read CODEX.md, SUBAGENT_BRIEF.md, git log f517d1e8..HEAD (52 commits).
  PROVENANCE rows of interest: 182-200, 210, 219, 246-247, 265-276.
- Next: read those rows, then survey docs/ for each candidate fact.
- T+20: read PROVENANCE rows 270-276 in full; grepped docs/ for 15 keyword families.
  Confirmed gaps so far: half-ALU dst-nibble (absent), device_store unbound-slot silent drop
  (absent; docs/compiler-readiness.md:255 says the OPPOSITE for slot 128), rt_index no-fault
  (partial), instance_id/vertex_id base asymmetry (absent), ext8.saturate clamp (docs assert
  the REFUTED clamp at compiler-readiness.md:560), sr_sel vertex fault (docs assert
  "zero faults" at compiler-readiness.md:535 from the M4 COMPUTE carrier), frag_color_pack
  wall (absent), index_reg/extmode walls (absent), n3_mov (docs say nir_op_mov BLOCKED),
  call rules (absent), iter_at.loc (absent), vary_store.hint6 (absent), tex_sample.coord
  (docs say untested).
  EXP-0183/0184/0185 have NO RESULTS.md -> live, excluded from drafting.
- T+25: EXP-0180 RESULTS.md read in full and verified. Next: EXP-0169, EXP-0178.
- T+55: EXP-0169 §14/§15/§17, EXP-0178 §3/§5/§7, EXP-0179 §2/§3/arm N/arm O, EXP-0174 §3/§4/§5,
  EXP-0172 §1/§2.1, EXP-0163 §1/§2/§4 all read and verified against docs/.
- T+80: analysis/docs_gap.json written (20 facts, 4 paper-trail defects, 2 not-a-gap).
- T+105: analysis/drafted_docs.md written (20 drafted blocks across 5 destination files),
  then section A.0 inserted as the highest-leverage single edit (extending docs/isa/README.md's
  existing "silent zero, not a fault" list).
- T+115: README.md, RESULTS.md, manifest.json written. C.1 precision patch applied
  (840 decidable of 960 dispatched, not "840 covering all 240 pairs").
- FINDING OF RECORD (DEF-0186-1): PROVENANCE.md's EXP-0179 row states call.b6 INERT; the
  experiment's own RESULTS.md §3 says bit 1 MUST BE SET and carries an explicit warning that
  the inert reading was its withdrawn first version. Commit ordering explains it
  (955eb6c7 corrected before 384c16c1 appended the row). HIGH severity — reported, not patched.
- DONE. No git commit, per dispatch.

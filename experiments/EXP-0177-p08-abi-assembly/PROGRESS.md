# EXP-0177 PROGRESS

Pure-analysis assembly of committed evidence bearing on P0.8 (DRV-ABI-01).
No device, no SSH, no GPU. Read-only over committed artifacts.

## Log
- [M0] 2026-08-30 — dir created; read CLAUDE.md / CODEX.md / SUBAGENT_BRIEF.md / docs/P0-P1-CLOSURE.md.
  Confirmed P0.8 evidence cell reads literally "queued" and cites no experiment.
- [M1] Key structural finding: the two experiments most directly named for P0.8
  are BOTH QUARANTINED / NON-EVIDENCE:
    * EXP-0050-fragment-output-abi (false clean-room attestation; parser materialized
      out-of-allowlist bytes) — all verdicts non-citable.
    * EXP-0071-m4-vertex-fragment-abi-contract (pre-GPU scaffold, underspecified
      frozen matrix; no capture ever run).
  This partly explains why the P0.8 cell says "queued" — its two namesake
  experiments produce zero usable evidence.
- [M2] Read EXP-0109-m4-stage-abi (M4/G16G, 57 cases x2 runs, byte-identical).
  Richest single P0.8 source: VS fetch format/layout/OOB, FS interpolation qualifiers,
  FS MRT/dual-source/depth/stencil, CS dynamic tgmem + preamble, and the KEY negative
  linkage result: Metal never emits a third code region -> no separate prolog/epilog
  object; only ["_agc.main.constant_program","_agc.main"].
- [M3] Read EXP-0117-m4-stage-abi-remainder (M4/G16G, 148 cases x2 runs byte-identical).
  This is the epilog experiment: all 19 MTLBlendFactor + 5 MTLBlendOperation
  HW-VALIDATED against the standard formula; write-mask bit layout A=1,B=2,G=4,R=8;
  blend constant UNCLAMPED; sRGB blends in linear space; integer format + blend =
  fatal abort; alpha-to-coverage exact; NaN/Inf bit-exact; LOGIC OPS constructed
  in-shader 8/8 exact (tile_read + ALU + frag_color_store); MRT ceiling exactly 8;
  sample-mask width == N, bits >=N inert; [[stencil]] truncates & 0xFF; CALL byte+6
  uniformly 0x54 across 6 topologies; call depth 1..128 OK.
  Barycentric convention PARTIAL w/ disclosed anomaly. Split prolog/epilog DEFERRED.
- [M4] Read EXP-0092-m4-sysval-abi (M4/G16G, 300 cases x2; 299/300 byte-identical,
  reg_112 nondeterministic so the formal --captured gate does NOT pass).
  get_sr sr_sel bit7 discriminator (exhaustive 0x00-0xFF, no faults); GPR file hard
  ceiling at 96 (96..127 fault, 112 flaky); base_vertex 0x88 / base_instance 0x8a
  upgraded (inferred)->HW-VALIDATED; vertex_id/instance_id base-inclusive + uint32 wrap;
  threadgroups_per_grid direct==indirect exact to UINT32_MAX. draw-ID UNKNOWN (no Metal
  multidraw surface) -> must be a userspace-supplied per-draw uniform.
- [M5] Read EXP-0137-m4-bary-split-abi (M4/G16G, 29 cases x2, byte-identical).
  NOTE: its RESULTS.md is mis-titled "EXP-0129 Results" (dir is EXP-0137). Resolves
  the EXP-0117 barycentric anomaly: trigger is CONSUMING [[position]]; without it the
  MSL compiler emits an INCOMPLETE lowering (2 iter, 0 fspecial, Model B =
  perspective-numerator + sum-to-one complement). Convention: b.x/.y/.z = vertices in
  emission order; correct semantics are perspective-correct (Model C). A clean-room
  backend must ALWAYS emit the full W-denominator+rcp+normalize sequence.
  Also CONSTRUCTS the split prolog/epilog seam: Metal DOES emit a 3rd Mach-O region
  with real call/frame_marker/pop_reconverge for a vertex fetch helper and a 2-call-site
  compute helper -> REFINES EXP-0109's "no third region ever appears". Args land in
  r10..r14 (5 args confirmed); multi-component return register numbering UNRESOLVED.
  [[color(0)]] on a non-entry helper param is accepted but semantically INERT.
  EXP-0137 claims all nine DRV-ABI-01 sub-items are "addressed" -- but ALL of the
  0109/0117/0137 chain is M4/G16G, and closure is measured against full G17P.
- [M6] Read EXP-0155-g17p-emit-tex-frag. THIS IS THE ONLY LARGE G17P-TARGET P0.8-relevant
  body of evidence. 99,526 swept cases over 2 gated runs on G17P.
  EMITTABLE on G17P: vary_slot, iter, iter_at, iter_flat, frag_color_store,
  frag_color_pack, frag_tile_setup, frag_depth_store, imageblock_store (+tex_*, simd_*).
  vary_store emitter-grade at field level but its db.json descriptor is WRONG (0x57
  collision resolved: byte+1&7==6 -> 8-byte vertex varying store; ==4,5 -> 6-byte
  fragment kill/target-mask op; byte+2 is a DON'T-CARE across 4 programs).
  imageblock_load NOT ATTEMPTED - no compilable carrier (5 fields still untested).
  GPR>=96 in 7 dst fields HANGS the GPU (not silent zero).
  Silent-zero traps named: frag_color_store.mask bit0, frag_color_pack.src_desc,
  imageblock_store.b6 bit0, frag_depth_store.b4.
  frag_tile_setup: 3 of 4 fields inert; only b1 live.
- [M7] Read EXP-0163 (G17P, PROVISIONAL - ONE gated run), EXP-0172 (G17P, 2 runs),
  EXP-0168 (compute arm 2 runs; render arm PROVISIONAL one run, second BLOCKED),
  EXP-0147 (M4 only), EXP-0173 (audit).
- [M8] MAJOR AUDIT FINDING: PROVENANCE.md has NO row of its own for EXP-0109,
  EXP-0111, EXP-0117 or EXP-0108. EXP-0109 (57 cases) and EXP-0117 (148 cases) are
  the two largest P0.8 experiments and neither is in the clean-room paper trail.
  Closure rule 3 is therefore NOT met for the bulk of P0.8's evidence.
  (EXP-0173 independently recorded "P0.8 cites no experiment at all" under rule 2.)
- [M9] Extracted the P0.8 instruction status from tools/agx-isa/validation.json
  (generated 2026-08-28; note EXP-0175 is actively editing db.json).
  NOT emittable and directly P0.8-blocking: vary_store, iter, iter_at,
  frag_color_store, frag_color_pack, frag_tile_setup, tile_read, tile_read_mrt,
  imageblock_store, imageblock_load, vtx_out_pos, mesh_out_src, n3_sample_read,
  get_sr, call, ret.
  get_sr.sr_sel is `untested` on G17P -> NO system value can be emitted.
  call has 4 of 5 fields `tokenization-only` -> the CALL ABI that EXP-0137's split
  prolog/epilog contract depends on cannot be emitted.
- [M10] BG/EOT cluster extracted (EXP-0130, EXP-0108, EXP-0048, EXP-0118), all M4/G16G
  except EXP-0118 which claims G17P in README only, has NO gates/raw/label/run count
  and is committed as "append-only process history" -> NOT usable as P0.8 evidence.
  EXP-0130: tile_read (67 0e 54) + frag_color_store (e7 06 54) reproduced on M4 and a
  read/ALU/write EOT core CONSTRUCTED and HW-VALIDATED 4/4; pure passthrough is ELIDED
  by the compiler (a driver cannot validate the path with an identity shader).
  EXP-0108: NO BG/EOT *program* record locatable in a 40-case matrix -> "there is no
  register file, calling convention, or instruction-level tilebuffer-load/store ABI to
  characterize from this experiment's evidence".
  usc low-bit tag, rsrc_spec Apple9 bit layout, and the fused EOT store op remain UNKNOWN.
- [M11] docs/ audit: EXP-0109 and EXP-0117 are cited in docs/ ONLY in passing inside
  other experiments' entries. The whole EXP-0117 body (19 blend factors, 5 ops,
  write-mask bit layout, sRGB-linear blending, [[stencil]] truncation, MRT ceiling 8,
  sample-mask width, call depth 128) is NOT in the normative docs. Closure rule 4
  therefore fails alongside rule 3.
  docs/mesa-userspace-requirements.md:181 ("Fast-link prolog/epilog") is the P0.8 doc
  row and still reads "partial" with an unresolved pending list.
- [M12] Scratch/calls cluster extracted (EXP-0041, EXP-0107, EXP-0125, EXP-0057, EXP-0035).
  EXP-0057 is QUARANTINED / NON-EVIDENCE (metadata harness breached its own boundary).
  Scratch: three independent negatives (EXP-0041 narrow allowlist 208-576 B; EXP-0107
  wide-content dispatch-time to 261,728 B at 454x pressure; EXP-0125 init-time lifecycle,
  byte-identical BO inventory spill vs no-spill at all 6 checkpoints). Two positives:
  the exact stage-uniform compile ceiling K=65,431 = 261,740 B declared per-thread scratch
  (first failure 261,744 B, clean nil + "Compute function exceeds available stack space"),
  and a concurrent-pressure SILENT CHECKSUM CORRUPTION failure mode above n_queues=4.
  EXP-0125's own words: the mechanism "is not observable from userspace's own IOKit
  resource-map boundary on macOS" and "most likely need[s] to be constructed from first
  principles against the hardware's actual behavior ... not decoded from a macOS capture".
  Calls: EXP-0035 is the ONLY A18/G17P experiment in the whole P0.8 set. It predates the
  gated-capture regime -- NO run count, NO cross-run gate, no PRE_REGISTRATION. Its
  non-leaf frame (0x6f prologue + 0x07 link save/restore + 8f 12 ret) is explicitly
  "byte-diff (NOT HW-isolated)"; the indirect-call 0x0f 0x80 operand fields are TBD.
  NAMING CAVEAT: link_save_restore / frame_prologue / spill_frame_marker / ret_luse appear
  in NO P0.8 RESULTS.md -- they are db.json names assigned later.
- [M13] FS-semantics cluster extracted (EXP-0091, EXP-0111, EXP-0097, EXP-0029, EXP-0031).
  Target split is clean and consequential: EXP-0029 and EXP-0031 are A18/G17P-only
  (2026-07-07, PREDATING the two-run gate regime); EXP-0091/0097/0111 are M4-only with
  A18 explicitly INFERRED-by-family. NO experiment in the set ran the same probe on both.
  EXP-0091's kill op (6-byte `57 <B1> 54 <B3> <B4> <B5>` + companion `07 02 54 01 ..`)
  is the SAME 0x57 descriptor collision EXP-0155 later resolved on G17P -- a genuine
  M4->G17P convergence worth recording.
  EXP-0111: interpolate_at_offset does NOT follow the MSL spec; a driver must transform
  (dx,dy) -> (dx+0.5, 0.5-dy). Dynamic RT routing = ONE frag_color_store, mechanism UNKNOWN.
  EXP-0097: 124 user varying scalar components (post-link liveness, per scalar, width-
  independent), clip-distance 8 INDEPENDENT, cull_distance not an MSL attribute at all,
  provoking vertex FIXED to the first-fetched vertex per primitive with no Metal control.
- [M14] Writing deliverables: analysis/p08_evidence.json, analysis/p08_gaps.md,
  analysis/p08_closure_cell_draft.md, RESULTS.md.
- [M15] All deliverables written:
    README.md, PRE_REGISTRATION.md, RESULTS.md, manifest.json,
    analysis/isa_status.py + isa_status.json,
    analysis/provenance_check.py + provenance_check.json,
    analysis/p08_evidence.json (10 sub-areas, 72 established + 60 not-established entries),
    analysis/p08_gaps.md (19 ranked gaps + boundaries + non-evidence),
    analysis/p08_closure_cell_draft.md (DRAFTED, NOT APPLIED).
  HEADLINE (computed, reproducible): 28 stage-ABI instructions, 12 emittable (42.9%),
  7 of those with a sub-emitter-grade `_instruction` label (EXP-0173 sec.7.2 defect),
  so 5 of 28 clear both bars -- frame_prologue, link_save_restore, pixel_order,
  pop_reconverge, spill_frame_marker. NONE is an input/output/sysval/interpolation/
  tilebuffer instruction; two are compromised in their own right.
  24 non-quarantined experiments supply evidence; 4 experiments named for this row are
  non-evidence (EXP-0050, EXP-0071, EXP-0057 quarantined; EXP-0118 ungated).
  Closure rules 1, 3, 4 and 6 all fail; rule 2 partial; rule 5 mixed.
- [M16] Nothing outside experiments/EXP-0177-p08-abi-assembly/ was written or modified.
  docs/, PROVENANCE.md, db.json, validation.json untouched. No git commit. No device.
- [M17] Reproducibility check: isa_status.json is byte-reproducible. provenance_check.json
  differed between two runs because the orchestrator committed a PROVENANCE.md table-rendering
  repair (54691d21, "57% of rows were outside it") in between. The ownership SUMMARY is
  byte-identical before and after, and the four no-row experiments were re-verified by hand
  against the repaired file: EXP-0109 appears only inside EXP-0137's row, EXP-0117 only inside
  EXP-0130's, EXP-0108 only inside EXP-0132's, EXP-0111 not at all. Finding stands.
- [M18] DONE.

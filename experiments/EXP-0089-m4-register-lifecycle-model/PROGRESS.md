# PROGRESS — EXP-0089

- 2026-08-28T01:47Z  Task received (goal task 2: "get to the bottom of the register
  lifecycle thing"). Read CLAUDE.md/CODEX.md/experiments/SUBAGENT_BRIEF.md,
  docs/isa/register-move-and-liveness.md, and EXP-0086 in full (PRE_REGISTRATION.md,
  RESULTS.md, PROGRESS.md, QUARANTINE-run02-attempt1.md, casematrix.py, kernels/,
  raw/m4-20260828-run01). Confirmed EXP-0086's own account: run01 complete/gate-passing,
  run02 quarantined at 113/135 (host interruption, not experiment logic), 113/113 lines
  byte-identical to run01 informally but the formal two-run gate is NOT met.
- 2026-08-28T01:50Z  Built tools/shdump + tools/agxtest locally into scratchpad bin.
  Pilot (non-experiment-dir) OWN-SHADER compiles to find a family where instruction
  bit 17 is genuinely free (not opcode-determining). Checked tools/agx-isa/db.json's
  own `match` tables for falu_acc/ret/ret_luse/if_push_pred/unpack_convert/cvt_i2f:
  falu_acc's match FIXES bits 17-20 (bit17 is opcode there too, a NEW finding EXP-0086
  never checked structurally); ret/ret_luse's byte+2 selects the MNEMONIC, not a free
  bit; unpack_convert's match leaves ONLY bit17 free in byte+2 (textbook match to the
  literal claim); cvt_i2f's byte+2 (mode) is entirely unconstrained by match.
  Pilot-compiled two-different-builtin kernels (unpack_unorm/snorm2x16_to_float(p);
  float(v)+float((uint)v)) to defeat CSE -- both produced two separate instructions
  reading the SAME source register with the doc's claimed 0x56(first)/0x54(second)
  natural polarity. Informal (non-gated) real-GPU pilot dispatch: flipping c1's literal
  bit17 corrupted BOTH the flipped instruction's own result AND the later instruction's
  result to a "reads zero" pattern in BOTH families; flipping only c2 was a no-op in
  both; flip_both showed family-dependent asymmetry (recorded honestly in
  PRE_REGISTRATION.md, to be re-tested under the gated protocol).
  Also pilot-compiled a 3-reader kernel (discrim3: v+10/v+20/v+30) for the
  producer/consumer discriminator -- found a genuine, non-simplified compiler
  scheduling quirk (opflags naturally 0,0,1 not the simple 0,1 alternation from
  EXP-0086's 2-reader kernel), recorded as-is.
  Re-verified ALL 7 of EXP-0086's kernel anchors byte-identical on this session's
  fresh compile (0 diffs) before deciding to carry them over verbatim.
- 2026-08-28T02:10Z  Created experiments/EXP-0089-m4-register-lifecycle-model/. Copied
  EXP-0086's 7 kernels verbatim; added lit17_unpack.metal/lit17_cvt.metal/discrim3.metal.
  Wrote casematrix.py (ANCHORS/DISCRIM_ANCHORS, INPUTS/OUT_N/EXPECTED for 10 kernels,
  make_cases/make_discrim_cases, _splice_raw new primitive, 549 cases/run: 168 from the
  7 original kernels x 24 templates [baseline+3 CAND_A+3 CAND_B+positive_control_c2+16
  ctrl_sweep], 10 from 2 lit17 kernels x 5 templates, 5 from discrim3 x 5 templates).
  Adapted run.py/verify.py/baseline.py/make_manifest.py/harness/build.sh from EXP-0086's
  standing-gate architecture; corrected the cross-run gate per SUBAGENT_BRIEF's
  pinned-revision lesson (git_revision is informational only, NOT gated between runs --
  only authored source hashes are pinned) and added a selftest case proving it.
  Wrote PRE_REGISTRATION.md + README.md + RESULTS.md placeholder BEFORE any GPU capture
  in this experiment directory.
- 2026-08-28T02:12Z  verify.py --preflight, --selftest (16/16), --seqtest (14/14) all PASS on
  the PRE_GPU tree. Ran raw/m4-lifecycle-20260828-run01 (--execute, real GPU): 549/549 cases,
  ~224s wall time, status_counts {CMDBUF_ERROR:53, NO_STATUS:3, OK:493} (NO_STATUS=3 are a
  genuine, contained GPU HANG on loop_boundary/ctrl_sweep_c1_b04, each ate the full 60s
  case_process timeout -- new failure class vs EXP-0086's fast CMDBUF_ERRORs, itself relevant
  to item 4). verify.py --between-runs PASS live immediately after capture.
- 2026-08-28T02:03Z  Ran raw/m4-lifecycle-20260828-run02 (--execute, real GPU): 549/549 cases,
  ~253s wall time, status_counts {CMDBUF_ERROR:57, NO_STATUS:3, OK:489}. analysis.py --write:
  cross_run_n_diffs=8, ALL 8 confined to the CTRL_SWEEP item (mask 0x01/0x02, adjacent/
  if_boundary only) -- ZERO diffs in CAND_A/CAND_B/BASELINE/CONTROL/LIT17/DISCRIM (541/549
  lines byte-identical, 3/3 in-run repeats identical for every one of those). 3/112 ctrl_sweep
  case-groups show genuine WITHIN-run01 intermittency (repeats disagree), confirmed by direct
  verify.py static()/one_run() diagnostics run standalone: verify.py --captured correctly and
  honestly FAILS ("byte-exact gated repeat") -- not forced, not the contract edited after the
  fact. Confirmed via ad-hoc diagnostic that this is the ONLY failing check (provenance/schema/
  structural checks all pass for both runs individually).
- 2026-08-28T02:15Z  Extracted full findings from analysis.json for all 5 dispatch items:
  (1) two-run gate CLOSED for the decisive 541/549 lines, NOT closed for the 8 ctrl_sweep
  lines (reported, not hidden); (2) literal bit 17 HW-VALIDATED corrupting in TWO independent
  families (unpack_convert, cvt_i2f) -- new signature (self-corruption of the flipped
  instruction's own result, not seen for opflags-bit0), family-asymmetric flip_both behavior,
  falu_acc confirmed match-table-fixed at bit17; (3) CAND_B universal-but-condition-dependent:
  6/7 kernels replicate EXP-0086 exactly, loop_boundary (12-byte extended form, real loop)
  corrupts a THIRD value (accumulator) and uniquely makes the consumer's own bit matter;
  (4) ctrl/ctrl_lo: bits 2/4 safe in 13/14 compact-form contexts, bits 0/1/3/5/6 load-bearing,
  12-byte extended form 0/8 safe including a genuine hang, bits 0/1 show real cross-process
  non-determinism (the only non-deterministic field in ~1200 total case executions across
  EXP-0086+EXP-0089); (5) discrim3 gives a decisive discriminator: no backward/earlier-reader
  effect ever observed (H5 confirmed), and corruption reaches a THIRD, independent later
  reader (not just the immediate next one), directly favoring a persistent producer-side
  writeback-suppression model over a one-shot bypass-cache model. lit17 kernels' positive
  controls both FAILED to detect (7/9 overall) -- downgraded their own null (flip_c2) results
  to UNKNOWN, does not affect the flip_c1 corruption findings.
- 2026-08-28T02:20Z  Wrote RESULTS.md (full OBSERVED/INTERPRETED separation, verdict on all
  5 items, exact proposed docs/isa/README.md + db.json + register-move-and-liveness.md
  correction text, limitations, clean-room attestation). Regenerated manifest.json (CAPTURED,
  37 artifacts). Re-ran verify.py --captured for final confirmation: FAILs on exactly the
  pre-characterized "byte-exact gated repeat" cause, nothing else. Task complete for this
  session; no git commit per instructions (orchestrator owns commits). Reporting to
  coordinator now.

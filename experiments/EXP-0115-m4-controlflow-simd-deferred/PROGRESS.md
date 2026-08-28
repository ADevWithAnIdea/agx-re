# PROGRESS -- EXP-0115

- 2026-08-28T07:20Z: tools/bin built (shdump, agxrun, agxrender, agxparse.py) into
  work/bin/, pinned revision 0cd13aee7f38c06743793c6f3e8f9e9610ec62ab at that point.
- 2026-08-28T07:20-07:33Z: reconnaissance (work/pilot/, non-recorded) for all 7
  items: item3's dst_pred/if_push_pred 25-point matrix decisively resolved
  (if_push_pred.pred is inert); item1's branch-reach checkerboard mapped via
  bisect_reach.py; item2's Clang bracket-depth ceiling found via bisect_bracket.py
  (ifnest 254/255, loopnest1 255/256); item4's static-shuffle hard-zero-vs-dynamic
  finding confirmed via direct lane-byte splice; item5's discard-specificity
  (vs generic divergent CF) confirmed via f_ballot_onereturn control, plus
  count/location independence and simd_all/simd_any inclusion; item6's fragment
  width=32 constant confirmed 1x1 through 33x33; item7's adversarial kernel set
  authored.
- 2026-08-28T07:33Z: PRE_REGISTRATION.md + CAPTURE_CONTRACT.json frozen, pinned
  revision updated to 87d02c34f56357734f448695cf62d37ab555fcb0 (HEAD moved from
  sibling-experiment commits, not contamination per SUBAGENT_BRIEF).
- 2026-08-28T07:34Z: harness/{lib.py,run.py,matrix.py,verify.py,fixtures.py} +
  kernels/{reach,cf_pred,shuf_static,vote_frag,width_frag,sgbar_adv}.metal +
  kernels/deep/*.metal (27 generated files) written. matrix.py: 308 cases across
  7 items. --selftest 321/321 PASS (PRE_GPU, no raw/ needed). --smoke PASS
  (non-recorded, raw/ confirmed empty immediately after). --seqtest 5/5 PASS at
  PRE_GPU.
- (next milestones appended as the two capture runs complete)
- 2026-08-28T07:39Z: run01 (m4_20260828_run01) COMPLETE, 308/308 cases, 309-line
  gated JSONL + nongated companion. Console: ok=18 mismatch=9 fault=128 hang=12
  other=141 (the large "other" bucket is a cosmetic artifact of run.py's summary
  counter treating locate_splice's verdict=status="OK" string as neither None nor
  "MATCH" -- not a data-quality issue; every locate_splice case's actual STATUS is
  correctly recorded). Zero HOST_TIMEOUT / DRIVER_EXCEPTION. All 12 branch-reach
  HANGs contained by the 8s run_timeout, host unaffected, next case proceeded
  normally every time.
- 2026-08-28T07:40Z: DISCOVERED AND ROOT-CAUSED a design defect in this
  experiment's OWN loopnestD2 host oracle (harness/matrix.py:oracle_loopnestD2),
  NOT a hardware anomaly: all 9 deep_loopnestD2_* cases show verdict=MISMATCH.
  Root cause: the kernel's accumulation statement (`acc += 1`) sits inside ALL N
  nested for-loops (at the innermost point only), so it executes
  trip_1*trip_2*...*trip_N times (multiplicative, standard nested-loop
  semantics) -- exactly the same exponential-blowup shape this design was meant
  to AVOID (per PRE_REGISTRATION.md's stated rationale for replacing EXP-0104's
  loopnestD). The oracle wrongly assumed additive (sum of trip counts) growth.
  Verified by hand: real output is EXACTLY reproduced by
  acc = PRODUCT_{j=1..depth} (1 + bit((j-1)%32)(v)), confirmed for all 9 depths
  and all 8 input values (bufs are small, [0..7], so even the multiplicative
  form never exceeds 2^24 -- no runaway execution time occurred; GPU wall time
  did rise with depth, up to 12.5s at depth 255, but every case still completed
  well inside its timeout and returned STATUS=OK).
  DECISION (per CODEX -- raw JSONL is immutable, already-captured; no post-capture
  repair): run02 will use the SAME unmodified harness/matrix.py (bug included) so
  the cross-run gate stays meaningful (both runs must reproduce byte-identical
  MISMATCH verdicts against the same fixed, if wrong, oracle formula -- itself a
  determinism check, not swept under the rug). RESULTS.md will report
  loopnestD2's ACTUAL (multiplicative) semantics honestly, credit STATUS=OK at
  every tested depth (no fault/hang, the load-bearing CF-03 fact) as valid, and
  flag the additive-growth design INTENT as unmet (a genuine, disclosed defect,
  not hidden). ifnest2 and loopnest1b (the other two CF-03 families) have
  correct oracles and 100% MATCH -- item 2's core toolchain-ceiling finding does
  not depend on loopnestD2's oracle being right.
- 2026-08-28T07:41Z: launching run02 (m4_20260828_run02) with the unmodified
  frozen matrix, per the decision above.
- 2026-08-28T07:45Z: run02 (m4_20260828_run02) COMPLETE, 308/308 cases. Console:
  ok=18 mismatch=9 fault=126 hang=17 other=138.
- 2026-08-28T07:46Z: --selftest 321/321 PASS, --seqtest 5/5 PASS (RUN02_PRESENT),
  --captured m4_20260828_run01 m4_20260828_run02: cases compared=308,
  gated-field issues=13 (cross_run_gate_pass=False -- EXPECTED, see below), all
  13 confined to the "branch-reach" item (8% of its 162 cases); the other 6
  items' 146 cases are 100% byte-identical across runs. nongated gputime_ns
  differs in 156/308 (nondeterminism-split proof CONFIRMED, as designed).
  MAJOR FINDING (not a harness defect): the branch-reach mixed/checkerboard
  zone shows GENUINE run-to-run non-determinism. Verified the compiled
  `_agc.main` bytes are IDENTICAL between run01's and run02's independently
  compiled archives (only unrelated archive metadata/timestamps differ,
  confirmed via `cmp`+`agxparse.py --extract-hex` diff), ruling out
  compile-time byte differences as the cause -- the same splice at the same
  byte offset, executing byte-identical code, produces DIFFERENT outcomes
  (e.g. reach_fwd_10: OK/silent-zero in run01, HANG in run02; several
  "CMDBUF_ERROR-in-both" cases actually carry DIFFERENT underlying GPU error
  codes -- PageFault vs Hang vs InnocentVictim -- between runs). The
  "clean" region (correct baseline, the -2 alias hole, the small ±1-9B fault
  zone, and MOST checkerboard OK-zero points e.g. +1024/+4096/+16384) remains
  perfectly reproducible; only 13 specific deltas (all involving re-entry at a
  REAL mid-function instruction boundary or specific checkerboard points) are
  affected. Reported in RESULTS.md as a first-class, disclosed finding, not
  hidden or forced into false consistency.
- 2026-08-28T07:50Z: pulled full per-item data tables (branch-reach status
  matrix both directions, CF-03 depth ladder x3 families, 25-point
  dst_pred x if_push_pred matrix, static-shuffle raw-byte sweep x3 families,
  vote-family pixel table, fragment-width pixel table, sgbar structural hex
  diffs + tokenize). sgbar_loop/sgbar_ifdiv structural diffs show the
  no-barrier twin gets FULLY OPTIMIZED to a closed-form/dead-code-eliminated
  form by the compiler while the barrier-present twin retains a REAL loop /
  real if_push+pop_reconverge -- confirms simdgroup_barrier is NOT always a
  no-op (a genuine, disclosed correction/extension of EXP-0104's finding),
  with the honest caveat that the byte-length delta is partly attributable to
  the barrier acting as an optimization barrier (preventing loop-to-closed-form
  / dead-code-elimination) rather than proof the barrier itself is a discrete
  emitted opcode.
- 2026-08-28T07:52Z: writing RESULTS.md.
- 2026-08-28T08:05Z: RESULTS.md written (all 7 response blocks, finite-resource
  table, hangs/faults safety record, gate results including the honest
  cross_run_gate_pass=False with full explanation, clean-room attestation).
  Fixed one numeric copy-paste error (run02's "other" count) after a self-review
  pass. Experiment COMPLETE. Final state: PRE_REGISTRATION.md, CAPTURE_CONTRACT.json,
  manifest.json, README.md, RESULTS.md, harness/*, kernels/*, raw/m4_20260828_run0{1,2}
  {,.nongated}.jsonl, analysis/report.py + summary_run0{1,2}.json all present.
  No git commit made (orchestrator owns commits per SUBAGENT_BRIEF). Nothing
  written outside this experiment directory at any point (verified).

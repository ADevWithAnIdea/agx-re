# PROGRESS — EXP-0086

- 2026-08-28T01:09:44Z  Task received. Read CLAUDE.md/CODEX.md/SUBAGENT_BRIEF.md. Read docs/isa/README.md:770
  claim and its sole evidence RT-1a-FIX/RESULTS.md (confirmed: that test re-read the SAME
  instruction's own result, never a later read -- exactly the gap the dispatch describes).
- 2026-08-28T01:09:44Z  Built tools/shdump + tools/agxtest locally (M4, macOS 26.6.2) into scratchpad bin.
  Pilot (non-experiment-dir) compiles of ~12 MSL variants to locate a splice-testable
  candidate bit. Found CAND_A: top bit of the 7-bit register-select field in the
  falu2i/falu2/falu_srcmod12b float-ALU family tracks first-vs-second read of a shared
  register across 7 independent compiles, confirmed by an immediate-value A/B swap
  (tracks temporal schedule order, not the specific operand value). Confirmed bit 17
  (the literal claim's bit position) is part of the OPCODE select in this family, so the
  literal claim cannot be tested verbatim here -- testing the generalized analog instead.
  Could not reproduce the literal falu_acc compact form in a shared-read-twice scenario
  after 3 honest attempts; recorded as a scope limitation.
- 2026-08-28T01:09:44Z  Created experiments/EXP-0086-m4-register-liveness-bits/. Finalized 7 kernels
  (adjacent/near/far4/far16/pressure/if_boundary/loop_boundary), all confirmed CLEAN
  tokenization via tools/agx-isa. Wrote casematrix.py (frozen anchors + independent
  float32 oracle + 45 case templates x REPEAT_N=3 = 135 cases/run), baseline.py
  (host-only anchor-freshness gate), run.py (capture runner, gated/non-gated record
  split for the no-nondeterminism gate), verify.py (--selftest/--seqtest/--preflight/
  --between-runs/--captured), analysis.py, make_manifest.py, harness/build.sh.
- 2026-08-28T01:09:44Z  Wrote PRE_REGISTRATION.md (H1 inert vs H2 liveness, asymmetric-corruption
  prediction, confirm/falsify criteria, frozen matrix) + CAPTURE_CONTRACT.json + README.md
  + RESULTS.md placeholder, BEFORE any splice/GPU capture.
- 2026-08-28T01:16:19Z  SESSION INTERRUPTED (host reboot, unrelated) after run01 was launched. Re-orientation on
  resume: raw/m4-20260828-run01 was found COMPLETE and VALID on disk (03_dispatch.json/
  05_run_manifest.json both present, 135/135 result lines in both 04_results.jsonl and
  04_results_raw.jsonl, manifest.json already regenerated to CAPTURED by run.py's own tail
  call). Verified: verify.py --selftest (16/16), --seqtest (14/14), make_manifest.py --check,
  verify.py --between-runs all PASS against the on-disk run01 tree -- no repair, no re-run,
  run01 id retained as-is per the resume directive. run01 raw counts: status_counts
  {CMDBUF_ERROR: 12, OK: 123}, verdict_counts {FAULT: 12, MATCH_EXPECTED: 87,
  MISMATCH_EXPECTED: 36} (36 mismatches against the independent oracle -- includes the
  EXPECTED positive_control_c2/candB cases per the pilot dry run; full breakdown pending
  analysis.py). Proceeding to run02 under its own id (never reusing/overwriting run01).
- 2026-08-28T01:26:07Z  SESSION KILLED A SECOND TIME (terminal-emulator issue, user's side, mid-run02).
  Re-orientation on resume #2: raw/m4-20260828-run01 confirmed complete+valid (unchanged
  from prior entry). raw/m4-20260828-run02 found INCOMPLETE: 113/135 lines in
  04_results.jsonl and 04_results_raw.jsonl, NO 03_dispatch.json, NO 05_run_manifest.json,
  work/m4-20260828-run02/ left uncleaned. Direct comparison: run02's 113 completed lines are
  BYTE-IDENTICAL to run01's corresponding lines (0 diffs). Per the resume directive: did NOT
  delete/retry under the run02 id (append-only + hash-frozen-file rules), did NOT edit run.py's
  RUNS tuple (would break run01's already-captured provenance hash). Wrote
  QUARANTINE-run02-attempt1.md documenting the partial capture as non-evidence, retained
  as-is. Ran analysis.py --run-a run01 --run-b run02 --write: wrote analysis.json using
  run01 as the full dataset (cross-run gate correctly FAILS given run02 incompleteness --
  expected, documented, not forced). Confirmed verify.py --between-runs / --captured now
  correctly FAIL on the current (quarantine-note-containing) tree; run01's OWN
  --between-runs PASS was already logged live at capture time (prior entry) before the tree
  was touched further -- that verification stands as historical record.
- 2026-08-28T01:26:07Z  RESULTS.md written from analysis.json (run01, 135/135 cases, 45 case-groups, 0
  intermittent). Headline: CAND_A (register-select-field top bit, the closest analog to the
  literal docs/isa/README.md:770 claim reachable given bit17 is opcode-determining in every
  compilable instance) null in ALL 7 kernels/conditions (adjacent/near/far4/far16/pressure/
  if_boundary/loop_boundary), with a 7/7 positive-control detection-capability proof. CAND_B
  (opflags bit0, adjacent kernel only) DID corrupt: candB_flip_c1/candB_flip_both
  deterministically (3/3 reps, cross-confirmed by run02's partial re-run) changed x2 from
  27.5 to 20 (reads zero instead of v) when the EARLIER/producer instruction's bit is
  flipped; candB_flip_c2 (consumer's own bit) alone is null -- producer-side bit dominates,
  no symmetric agreement requirement observed. Verdict on docs/isa/README.md:770: REFUTED
  as a general "NOT an op change" principle / REFINED to UNKNOWN-pending-retest for the
  literal 0x54/0x56/0x18/0x38 fields (never directly re-tested here; bit17 itself is
  opcode, not a free bit, in every reachable instance). falu_acc's own literal descriptor
  remains untested (3 honest reproduction attempts failed to trigger it in a shared-read
  scenario) -- reported as an open scope limitation, not a result. Exact doc/db.json
  correction text proposed in RESULTS.md (not applied -- orchestrator owns docs/).
- 2026-08-28T01:26:07Z  Task complete for this session: PRE_REGISTRATION.md, CAPTURE_CONTRACT.json,
  casematrix.py/baseline.py/run.py/verify.py/analysis.py/make_manifest.py, 7 kernels,
  raw/m4-20260828-run01 (valid, gate-passing), raw/m4-20260828-run02 (quarantined partial),
  QUARANTINE-run02-attempt1.md, analysis.json, RESULTS.md all committed to disk (no git
  commit per instructions). Reporting to coordinator now.

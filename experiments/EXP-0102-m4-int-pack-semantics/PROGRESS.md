# PROGRESS — EXP-0102 M4 INT-*/PACK-* semantics

Timestamped milestones. Append-only (per standing rule: a kill costs at most
one milestone; never edit a prior entry).

- 2026-08-28T06:20:00Z pilot: read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md,
  docs/isa/register-move-and-liveness.md, APPLE9_RE_IMPLEMENTATION_GAPS.md
  (Part II INT-*/PACK-*), EXP-0033/EXP-0013/EXP-0038 prior results.
  Confirmed target host is the M4 (10 cores, macOS 26.6.2/25G82, Metal 4).
- 2026-08-28T06:25:00Z pilot: built tools/shdump, tools/agxtest/agxrun fresh
  in a scratch work/ dir; end-to-end smoke dispatch (uint add) OK.
- 2026-08-28T06:30:00Z pilot: wrote analysis/oracle.py (pure-Python host
  oracle for all 25 items). Self-tested against hand-worked values and
  against Python's own struct 'e' binary16 codec: 0 mismatches over 62000
  random values incl. subnormal range + explicit overflow-to-inf handling.
- 2026-08-28T06:35:00Z pilot: found and fixed a real bug in
  f16_encode_exact's exponent search (was seeded from -14 instead of 0,
  corrupting every normal-range encode by a ~14-exponent offset) BEFORE any
  hardware contact -- caught by the struct cross-check, not by GPU data.
- 2026-08-28T06:40:00Z pilot: wrote kernels/gen_kernels.py (51 kernel
  functions across 22 .metal files) covering all 14 INT-* and 11 PACK-*
  items. Compile-smoke-tested every function individually via shdump: 51/51
  compiled with zero failures on this M4, including PACK-07/08's
  pack_float_to_{unorm,snorm}4x8 / unpack_{unorm,snorm}4x8_to_float (not
  previously exercised in this repo) and PACK-03/04's
  pack_float_to_snorm2x16 / unpack_snorm2x16_to_float.
- 2026-08-28T06:45:00Z pilot: wrote analysis/casematrix.py (51 cases) and
  harness/case_exec.py; first informal dry run of case 0
  (int0102_extract_unsigned) surfaced a genuine unmodeled HARDWARE boundary
  behavior at cnt==32 (offset bypassed entirely, full value returned
  verbatim) that neither of the two originally-recorded models
  (offset-masked-mod-32, offset-literal-unmasked) predicted.
- 2026-08-28T06:50:00Z pilot: added disambiguating rows (cnt in {31,33,40}
  crossed with the full offset boundary list) and a third oracle model
  (ubfe_model_d_width32_bypasses_offset). First attempt at the model was
  WRONG (treated cnt>=32 as bypassing, not cnt==32 exactly) -- refuted by
  the cnt=33/40 rows returning ordinary clamped-width literal-offset
  results, not verbatim-bypass. Refined model fits 122/122 (extract) and
  256/256 (insert, same pattern) on the pilot data.
- 2026-08-28T06:55:00Z pilot: ran ALL 51 cases once (informal). Found +
  fixed three host-side harness bugs (none hardware findings): (1) a
  tuple-vs-list equality bug in the comparator, (2) a NaN != NaN equality
  bug (NaN==NaN must count as a match -- the question is "is this a NaN",
  not numeric equality), (3) an `--out` word-count unit bug for
  f32x2/f32x4/u64 output kinds (agxtest.py's --out unit is 4-byte words
  regardless of logical element width) that silently truncated readback
  for 6 cases. All three caught by the pilot's own dry run before any gate
  was frozen.
- 2026-08-28T07:00:00Z pilot: found + fixed a methodology issue in the
  PACK-05 exact-tie test: a tie fraction (N+0.5)/65535 constructed in
  float64 does not reliably survive float64->float32 truncation as an
  exact half-integer once multiplied back by 65535 (off by ~1e-9 in the
  EXACT rational sense) -- this had produced 2 spurious "rounding rule"
  mismatches that were actually just ordinary (non-tie) correctly-rounded
  results. Fixed by computing the pack oracle over the EXACT Fraction value
  of the float32-snapped input (oracle.py::f32_exact_fraction,
  _pack_norm_exact). All 10/10 pack0506_pack_unorm2x16_edge rows now match,
  including the one genuine exact tie (N=32767) rounding to its even
  neighbor (32768) -- consistent with round-to-nearest-even.
- 2026-08-28T07:05:00Z pilot: added a 7th rotate-immediate case (K=1) to
  make the "K=33 encodes identically to K=1" structural claim (INT-04) a
  direct byte comparison rather than an inference. Re-ran full 51-case
  (now 51->51, same count after the +1 kernel/-0 net since imm1 replaces
  no existing case) sweep clean: every case's PRIMARY/refined oracle model
  now matches 100% of its rows. Full pilot sweep (51 cases) completes in
  ~11s wall-clock on this host.
- 2026-08-28T07:15:00Z pilot COMPLETE. Wrote PRE_REGISTRATION.md,
  CAPTURE_CONTRACT.json (pinned revision 0f1af7fa1d3e21a9996c3b49d7d91f6377427225),
  authored_hashes.json (30 files), verify.py (5 standing gates), run.py
  (capture orchestrator). --selftest and --seqtest both PASS in PRE_GPU
  phase. Proceeding to the two-run gated capture.
- 2026-08-28T06:37:41Z [m4-20260828T063741Z-run01] seqtest phase=RUN01_PRESENT ok=False
- 2026-08-28T06:37:42Z [m4-20260828T063741Z-run01] built tools into /Users/user/asahi_re/public/agx-re/experiments/EXP-0102-m4-int-pack-semantics/work/m4-20260828T063741Z-run01/bin
- 2026-08-28T06:37:42Z [m4-20260828T063741Z-run01] preflight smoke gate: PASS
- 2026-08-28T06:37:44Z [m4-20260828T063741Z-run01] case 10/51 id=int04_rotate_imm64 status=OK
- 2026-08-28T06:37:46Z [m4-20260828T063741Z-run01] case 20/51 id=int12_logic03 status=OK
- 2026-08-28T06:37:48Z [m4-20260828T063741Z-run01] case 30/51 id=int12_logic13 status=OK
- 2026-08-28T06:37:50Z [m4-20260828T063741Z-run01] case 40/51 id=pack0506_unpack_unorm2x16_exhaustive status=OK
- 2026-08-28T06:37:52Z [m4-20260828T063741Z-run01] case 50/51 id=pack11_short2_mul status=OK
- 2026-08-28T06:37:52Z [m4-20260828T063741Z-run01] case 51/51 id=pack11_short2_and status=OK
- 2026-08-28T06:37:52Z [m4-20260828T063741Z-run01] CAPTURE COMPLETE: 51 cases, status_counts={'OK': 51}, results_sha256=2644982cc9ba495e...
- 2026-08-28T06:37:52Z [m4-20260828T063741Z-run01] post-capture --captured check: PASS
- 2026-08-28T06:38:00Z DISCLOSED ISSUE (self-caught, not user-reported): the
  just-completed capture's `harness/case_exec.py` wrote each case's scratch
  build directory under `raw/<run>/work/<case>/`, i.e. INSIDE raw/, which
  must be text/JSON-only. Quarantined that run directory
  (raw/m4-20260828T063741Z-run01/QUARANTINE.md), fixed case_exec.py to take
  an explicit --work-dir OUTSIDE raw/ (work/<run-id>/cases/), regenerated
  authored_hashes.json, updated CAPTURE_CONTRACT.json's note. No recorded
  DATA was affected (results.jsonl/timing.jsonl/env/dispatch were already
  schema-correct and untouched) -- only the extraneous scratch-artifact
  location.
- 2026-08-28T06:39:20Z OFFICIAL run01 (m4-20260828T063920Z-run01) captured
  with the fixed harness: 51/51 cases status=OK, raw/ contains ONLY the
  declared text/JSON schema (verified: 0 .bin files under this run's raw/
  tree), post-capture --captured check PASS.
- 2026-08-28T06:39:36Z OFFICIAL run02 (m4-20260828T063935Z-run02) captured
  after a fresh --between-runs smoke gate: 51/51 cases status=OK,
  post-capture --captured check PASS.
- 2026-08-28T06:39:50Z Cross-run comparison
  (`verify.py --captured --compare run01 run02`): 51/51 GATED records
  BYTE-IDENTICAL across the two independent captures. Two-run gate MET.
- 2026-08-28T06:42:00Z DISCLOSED ISSUE #2 (self-caught, after noticing
  SUBAGENT_BRIEF.md was updated on disk mid-session to explicitly forbid
  ANY write outside the repo, even transient/temp): `verify.py::run_smoke`
  used `tempfile.TemporaryDirectory()`, which resolves to
  `/var/folders/.../T` on this host -- outside the repo. This was used only
  for the four NON-RECORDED smoke-gate calls in this session (one ad hoc
  manual check, one inside each of the two --preflight/--between-runs gate
  calls that preceded the two OFFICIAL captures above) -- it never touched
  any raw/ evidence or gated case data, and Python's TemporaryDirectory
  auto-deletes its contents on context exit, so nothing persisted outside
  the repo afterward either. Fixed immediately: run_smoke now uses
  `work/smoke/smoke-<ms>/` inside this experiment directory, with an
  explicit `shutil.rmtree` cleanup. Verified the fix (SMOKE PASS, work/smoke/
  empty after the call). Regenerated authored_hashes.json again. The two
  OFFICIAL captures' GATED data (01_results.jsonl) is entirely unaffected
  by this fix (the smoke gate is non-recorded and produces no data that
  feeds into 01_results.jsonl), so they were NOT recaptured.

- 2026-08-28T06:39:20Z [m4-20260828T063920Z-run01] seqtest phase=RUN01_PRESENT ok=True
- 2026-08-28T06:39:20Z [m4-20260828T063920Z-run01] built tools into /Users/user/asahi_re/public/agx-re/experiments/EXP-0102-m4-int-pack-semantics/work/m4-20260828T063920Z-run01/bin
- 2026-08-28T06:39:20Z [m4-20260828T063920Z-run01] preflight smoke gate: PASS
- 2026-08-28T06:39:22Z [m4-20260828T063920Z-run01] case 10/51 id=int04_rotate_imm64 status=OK
- 2026-08-28T06:39:24Z [m4-20260828T063920Z-run01] case 20/51 id=int12_logic03 status=OK
- 2026-08-28T06:39:25Z [m4-20260828T063920Z-run01] case 30/51 id=int12_logic13 status=OK
- 2026-08-28T06:39:27Z [m4-20260828T063920Z-run01] case 40/51 id=pack0506_unpack_unorm2x16_exhaustive status=OK
- 2026-08-28T06:39:29Z [m4-20260828T063920Z-run01] case 50/51 id=pack11_short2_mul status=OK
- 2026-08-28T06:39:29Z [m4-20260828T063920Z-run01] case 51/51 id=pack11_short2_and status=OK
- 2026-08-28T06:39:29Z [m4-20260828T063920Z-run01] CAPTURE COMPLETE: 51 cases, status_counts={'OK': 51}, results_sha256=8b9645eceb6ae8ff...
- 2026-08-28T06:39:29Z [m4-20260828T063920Z-run01] post-capture --captured check: PASS
- 2026-08-28T06:39:35Z [m4-20260828T063935Z-run02] seqtest phase=RUN02_PRESENT ok=False
- 2026-08-28T06:39:36Z [m4-20260828T063935Z-run02] built tools into /Users/user/asahi_re/public/agx-re/experiments/EXP-0102-m4-int-pack-semantics/work/m4-20260828T063935Z-run02/bin
- 2026-08-28T06:39:36Z [m4-20260828T063935Z-run02] between-runs smoke gate: PASS
- 2026-08-28T06:39:38Z [m4-20260828T063935Z-run02] case 10/51 id=int04_rotate_imm64 status=OK
- 2026-08-28T06:39:40Z [m4-20260828T063935Z-run02] case 20/51 id=int12_logic03 status=OK
- 2026-08-28T06:39:41Z [m4-20260828T063935Z-run02] case 30/51 id=int12_logic13 status=OK
- 2026-08-28T06:39:43Z [m4-20260828T063935Z-run02] case 40/51 id=pack0506_unpack_unorm2x16_exhaustive status=OK
- 2026-08-28T06:39:45Z [m4-20260828T063935Z-run02] case 50/51 id=pack11_short2_mul status=OK
- 2026-08-28T06:39:45Z [m4-20260828T063935Z-run02] case 51/51 id=pack11_short2_and status=OK
- 2026-08-28T06:39:45Z [m4-20260828T063935Z-run02] CAPTURE COMPLETE: 51 cases, status_counts={'OK': 51}, results_sha256=44648d54aa530a7a...
- 2026-08-28T06:39:45Z [m4-20260828T063935Z-run02] post-capture --captured check: PASS
- 2026-08-28T06:45:00Z Ran analysis/structural.py against the promoted run01
  (tools/agx-isa isadb.disassemble() tokenization, READ-ONLY, no new
  hardware contact). Wrote analysis/structural_report.json.
- 2026-08-28T06:55:00Z Drafted RESULTS.md (OBSERVED/INTERPRETED, finite-
  resource table, 25 required-format response blocks). While drafting, made
  a FIRST-DRAFT claim that int11_insert_bits compiles to "a single dedicated
  ibfins instruction" (i.e. that it CONTRADICTS EXP-0033's A18 3-op
  finding). Before finalizing, spot-checked the raw tokenized data directly
  and found this claim WRONG: the actual body has THREE `ibfins`-family
  instances (distinct `form` field values 0/16/32) plus two `b_alu10_loe`
  helper ops -- i.e. it CONFIRMS, not contradicts, EXP-0033's multi-
  instruction finding, just with refined naming. Corrected before this was
  ever presented as a finding. Also spot-checked int0102_extract_unsigned's
  structural claim and found a second, more substantive nuance: with
  RUNTIME off/cnt (the shape this experiment needed to probe the boundary),
  extract compiles to `ibfe` PLUS three more instructions (ibfins,
  b_alu10_loe, n2_op6), NOT the single-ibfe-op shape EXP-0033 reported for
  COMPILE-TIME-CONSTANT off/cnt. This means the cnt==32-bypass "MODEL D"
  characterization is established at the Metal-compiler-output tier, not
  independently isolated to the raw ibfe/ibfins instruction alone --
  revised RESULTS.md's INT-01/02/11 OBSERVED/INTERPRETED sections and the
  INT-02 response block to state this precisely, and added it to the
  Deferred/Partial summary table and CAPTURE_CONTRACT.json's
  items_partial_or_deferred. No case's oracle, buffer, or gated data was
  touched by this correction -- it is purely an analysis-writing fix caught
  before RESULTS.md was finalized, same spirit as the pilot-phase self-
  catches (extract cnt==32 model, NaN equality, out-word-count, exact-tie
  fractions).
- 2026-08-28T07:05:00Z Wrote README.md, manifest.json. Final directory
  check: raw/ contains only the declared text/JSON schema for both promoted
  runs (0 binary files); work/ (scratch, not evidence) holds compiled
  archives and build byproducts only. EXPERIMENT COMPLETE. All 25 items
  (14 INT-*, 11 PACK-*) have a required-format response block in
  RESULTS.md; none silently dropped. 5/5 standing gates implemented and
  passing. Two-run byte-identity gate MET. Two disclosed-and-fixed process
  issues (raw/ binary leakage, out-of-repo temp dir) fully documented.
  No git commit made (per dispatch instructions).

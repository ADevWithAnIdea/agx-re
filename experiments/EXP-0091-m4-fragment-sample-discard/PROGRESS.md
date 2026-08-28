# EXP-0091 PROGRESS (timestamped, append-only)

## 2026-08-27T18:52Z (host-local; see manifest for authoritative UTC timestamps)
- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, work/ADDENDUM-TRIAGE-20260828.md
  (Bundle A spec), APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md (GLFS-A01/02/03/05/06/07 exact
  wording), APPLE9_RE_IMPLEMENTATION_GAPS.md (OPT-09, required response block format,
  finite-resource mandate), docs/isa/register-move-and-liveness.md (EXP-0086 later-read
  warning), experiments/EXP-0029-fragment-isa/RESULTS.md (fragment ISA baseline),
  experiments/EXP-0050-fragment-output-abi/QUARANTINE.md (render-archive parsing hazard
  precedent -- lesson: only ever use agxparse.py --locate's returned (offset,length) for
  in-place byte patching, never materialize/print/commit any other region).
- Created experiments/EXP-0091-m4-fragment-sample-discard/ skeleton.
- PILOT (host-side OWN-SHADER compiles via tools/shdump, NO GPU dispatch yet): built a
  localization battery (kernels/loc_*.metal) differentially compiling
  discard_fragment()/[[sample_mask]] combinations against branch-only and no-branch
  controls. FINDING: a 6-byte op (byte0=0x57, byte2=0x54; "57 14 54 00 00 01" register-
  sourced form, or "57 1c 54 00 00 01" straight-line form) + a 6-byte companion
  (byte0=0x07, byte1=0x02, byte2=0x54, byte3=0x01) appear ONLY when the fragment shader
  calls discard_fragment() or writes [[sample_mask]] with ANY value (constant or
  runtime), and NEVER in a plain shader or one with an unrelated divergent branch
  (loc_if_nodiscard decodes CLEAN via tools/agx-isa with 0 leftover and 0 occurrences of
  this byte pattern). db.json currently mis-tokenizes this as an 8-byte "vary_store"
  (a vertex-stage op), an opcode-byte collision analogous to the "9f 11 54" collision
  EXP-0029 already fixed for compute vs fragment. Immediate-mask cases (loc_mask_const_A
  vs loc_mask_const_full) isolate mask_value<<1 in an earlier ALU immediate, confirming
  the submission op itself never carries the mask value literally -- it's register-
  sourced.
- Wrote harness/fsrun.m (authored render+readback tool, superset of the read-only
  tools/agxtest/agxrender.m: MSAA sampleCount, depth attachment+compare+write, occlusion
  query, N device buffers with fill/readback, checker texture, and the same
  archive+FailOnBinaryArchiveMiss splice technique for forced-execution validation).
  Built clean, smoke-tested: plain color readback, depth gradient readback, atomic
  buffer readback, occlusion query, MSAA multisample-resolve fractional readback all
  confirmed working against known-expected values.
- MSAA sample-count width sweep (PLAIN mode, no splice, s=1/2/4, resolve-fraction
  technique): sample_mask is masked to the low N=sampleCount bits with NO fault/alias on
  excess high bits (tested up to 0xFFFFFFFF and 0x80000000 at N=4) -- clean, decisive,
  matches EXP-M4-09's independently-established "8x MSAA is Metal-rejected" ceiling (so
  N in {1,2,4} is the complete legal range).
- HW SPLICE validation (kernels/s_kill_probe.metal, archive+FailOnBinaryArchiveMiss,
  triple-channel readback: color + fixed-function depth + occlusion count, sampleCount=1,
  depth-compare=Always so occlusion/depth are gated purely by the kill mechanism):
  baseline (unspliced archive) reproduces the plain-compiled behavior exactly (mask=1
  survives all 3 channels; mask=0 killed on all 3). Byte-level sweep of the candidate
  op's byte+4 (offset 13802, "57 14 54 00 [B4] 01"): B4=0x00 survives; B4 in
  {0x01,0x02,0x04,0x08,0x10,0xFE,0xFF} kills; B4 in {0x20,0x40,0x80} survives (matches
  baseline) -- consistent with bits[4:0] being a 5-bit source-register-select field
  (0=the register the compiler routed the real mask into; any other value reads a
  different, apparently-zero/uninitialized register) and bits[7:5] not affecting this
  test. Positive control (corrupting a frag_color_pack byte) confirms the harness CAN
  detect a change; several other byte positions (own byte+1, own byte+3, companion
  byte+3/+4/+5) were null in this test -- recorded as genuine negative results, not
  re-tried blindly.
- ORCHESTRATOR NOTE received mid-task: do not gate the two-run cross-run check on live
  git HEAD being unchanged (sibling experiments land continuously); pin the git revision
  at pre-registration time and compare against that recorded value only. Will apply this
  in CAPTURE_CONTRACT.json / verify.py.
- NEXT: freeze PRE_REGISTRATION.md + CAPTURE_CONTRACT.json capturing all pilot findings
  above as the basis for hypotheses (matching EXP-0086's precedent of allowing
  no-GPU-dispatch pilot compiles before the frozen contract); then GLFS-A02/A03 (demote/
  helper), A05 (depth ordering), A06 (suppression matrix), A07 (sample shading) probe
  groups (kernels already authored: d_*, e_*, g6_*, f_*); then verify.py gates; then two
  capture runs; then RESULTS.md.

## 2026-08-28T02:10-03:10Z (approx; host-local)
- Fixed a real OOB-buffer-write bug found in the pilot trial (demote-group and
  depth-ordering-group `Rec`-sized buffers were undersized -- 64B/256B instead of the
  required 256B/1024B for the actual W*H*sizeof(Rec) footprint; fixed in run.py before
  freezing the pre-registration). Also fixed a vertex-shader depth-gradient bug in
  analysis/gen_e_kernels.py (clamping z at the oversized "big triangle" vertices halved
  the visible-region depth range; switched to unclamped z, verified against hand-
  computed expected depth values before freezing).
- Froze PRE_REGISTRATION.md + CAPTURE_CONTRACT.json (78-case matrix, hashes of 34
  authored files, environment, timeouts, gate classes). Applied the orchestrator's
  mid-pilot note: git HEAD is recorded for provenance only and is explicitly NOT a
  cross-run gate condition.
- Implemented verify.py (schema.py-driven selftest/seqtest/smoke/crossrun). Fixed a bug
  in my own seqtest harness (smoke()'s internal check() calls were polluting the global
  FAIL list even when the outer assertion `not smoke(...)` was itself the intended,
  correctly-passing check) by adding a `record=` parameter.
- Ran `verify.py --smoke` (PASS, before any raw/ artifact existed), then `run.py --run
  run01` and `run.py --run run02` (78/78 cases each, all STATUS OK/SCANNED, zero
  faults/hangs across both runs and all pilot exploration -- well over 150 total GPU
  dispatches this session, no wedge, no reboot). `verify.py --crossrun` -> PASS, all 78
  gated records byte-identical. `verify.py --selftest` -> PASS (10/10).
  `verify.py --seqtest` -> PASS (8/8).
- Added ONE supplementary, explicitly-flagged single-run probe (kernels/
  d_helper_relay.metal, quad-shuffle relay of a demoted lane's own is_helper status,
  needed because the frozen matrix's own GLFS-A06 finding showed a demoted lane's
  direct buffer write is suppressed) AFTER the frozen two-run capture completed --
  captured twice informally (byte-identical modulo GPUTIME_NS), stored under
  raw/supplementary_single_run/, clearly labeled as not part of the cross-run gate.
- Wrote RESULTS.md (full per-item response blocks for GLFS-A01/02/03/05/06/07 + OPT-09,
  exact numbers, finite-resource table, clean-room attestation), README.md,
  manifest.json.
- FINAL STATUS: all six addendum items + OPT-09 have a response block in RESULTS.md.
  GLFS-A01/A02/A05/A06 are CLOSED for their tested scope with HW-VALIDATED or
  behaviorally-decisive evidence. GLFS-A03 and GLFS-A07 are PARTIAL, with explicit,
  honest, reproducible open anomalies flagged for follow-up rather than papered over.
  No host wedge, no BLOCKED state, no A18/M5 contact. Ready for orchestrator review.

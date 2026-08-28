# PROGRESS — EXP-0126-m4-uapi-field-mapping

- 2026-08-28T01:20Z: Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md, docs/P0-P1-CLOSURE.md row
  P0.3, APPLE9_RE_IMPLEMENTATION_GAPS.md DRV-UAPI-03, EXP-0044/EXP-0045, and
  mesa/include/drm-uapi/asahi_drm.h in full. Confirmed mesa/ is materialized at
  3c4d3e46d19f2f4e951f3ae059543b03592f7944 with the full src/asahi tree present (not just
  the UAPI header) — usable as PUBLIC shape reference per CLAUDE.md.
- 2026-08-28T01:22Z: Mined mesa/src/asahi/vulkan/hk_queue.c, hk_cmd_draw.c,
  mesa/src/asahi/genxml/cmdbuf.xml, mesa/src/asahi/layout/layout.h for the userspace
  derivation shape of nearly every render/compute UAPI field (PPP Control, ZLS Control, ISP
  ZLS Pixels, Counts/rsrc_spec, Scissor/Depth-bias descriptor records, depth/stencil
  stride-in-pages formula, ppp_multisamplectl packing function, isp_bgobjvals constant,
  helper cfg/data derivation). Cross-referenced against this repo's own M4/A18 evidence
  (EXP-0054/0055 depth-bias-enable byte candidate now identified as PPP "Fragment
  control.Depth bias enable" bit17, matching EXP-0110's newly-observed bit18 "Stencil test
  enable").
- 2026-08-28T01:24Z: Set up experiment skeleton. Designed two new M4 hardware probes:
  (A) exhaustive sample-position grid + off-grid rounding-rule + boundary probe (extends
  RT-4/RT-11/EXP-M4-03's DATA-TRACE method to M4-native rounding confirmation, which no
  prior M4 experiment had done), (B) render.samples valid-range boundary probe.
- 2026-08-28T01:23-01:30Z: Built and iterated harness/sampcov.m (coverage-mask
  hardware-consumer probe) — found a dispatch-grid bug (fixed) and then an unresolved
  discrepancy in reference-sample coverage that did not resolve within budget. Abandoned in
  favor of the proven DATA-TRACE method; kept as authored process history (not part of the
  frozen matrix). See PRE_REGISTRATION.md "Superseded exploratory probe".
- 2026-08-28T01:31-01:40Z: Built harness/sampos126.m (DATA-TRACE, extends sp11.m/RT-11
  pattern), harness/sampcount.m (HW-PROBE), harness/casematrix.py (59 frozen cases),
  harness/hexparse.py, harness/run.py, harness/verify.py. Piloted the full 59-case matrix
  end-to-end in work/pilot_full (non-recorded). Found: exact grid reproduction (16/16 exact
  on X, 8/8 on Y), exact round-half-up tie rule at 1/32 and 3/32 boundaries, top-boundary
  behavior (0.94->0.9375 clamp-like, 0.99->1.0 no ceiling clamp — a genuine unclamped
  round(x*16)/16 result outside the nominal grid), Metal API hard range [0,1) enforced by a
  process-terminating assertion (not a catchable NSError), render.samples capability query
  exactly {1,2,4} supported on this M4 with the same abort-on-invalid behavior.
- 2026-08-28T01:41Z: Regenerated fixtures/recorded_reality.json from the pilot run's own
  output (10 real records, not hand-typed). `verify.py --selftest` PASS (0 issues),
  `--seqtest` PASS (6/6 checks).
- 2026-08-28T01:42Z: Froze CAPTURE_CONTRACT.json (source hashes, matrix, gates, pinned
  revision cf544b4dd1fb37047c7cfee6a70a0d1a87628666) and PRE_REGISTRATION.md. Noted a
  numbering collision with experiments/EXP-0126-m4-lifecycle-boundary-probe/ (concurrent
  orchestrator activity) for the orchestrator to resolve.
- (next) Execute official run01/run02 into raw/, run --captured gate, write RESULTS.md field
  table for all 65 UAPI leaves.
- 2026-08-28T01:50Z: Executed official captures m4_20260828_run01 and m4_20260828_run02
  (59 cases each). All gates PASS: --selftest (0 issues), --seqtest (6/6), non-recorded
  smoke gate (both runs, work/*_smoke.json precede raw/ creation), --captured (0 issues,
  gated-field byte-identity across both runs).
- 2026-08-28T01:55Z: Wrote RESULTS.md with the full 65-leaf field table (7 MAPPED / 58
  PARTIAL / 0 UNDETERMINABLE-FROM-USERSPACE within the 65; command_timestamp_frequency_hz
  flagged as the one genuinely undeterminable item outside the 65-leaf matrix), README.md,
  manifest.json. DONE.

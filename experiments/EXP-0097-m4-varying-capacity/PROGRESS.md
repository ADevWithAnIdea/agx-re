# PROGRESS — EXP-0097 M4 varying capacity + pre-raster special outputs

- `2026-08-28T00:00Z` (approx, first work in this session) — Read CLAUDE.md, CODEX.md,
  experiments/SUBAGENT_BRIEF.md, work/ADDENDUM-TRIAGE-20260828.md "Bundle G",
  APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md GLIO-A01/GLPRE-A03, EXP-G1a-usc-sysval-uvs,
  EXP-0029-fragment-isa, docs/cmdstream/README.md geometry-output sections,
  docs/isa/register-move-and-liveness.md. Studied EXP-0093 as the standing-gate-set template
  (schema.py/casematrix.py/run.py/verify.py/fixtures pattern).
- Built `harness/capacityprobe.m` (compile+pipeline-creation-only probe) and
  `harness/renderprobe.m` (compile+pipeline+draw+readback probe, 4 modes: render/point/layer/
  viewport). Both build cleanly with `clang -fobjc-arc -framework Metal -framework Foundation`.
- Interactive build-time pilot probing (scratch + real harness dispatch functions) established
  every numeric boundary recorded in PRE_REGISTRATION.md §3: varying-component ceiling=124 (two
  distinct failure modes either side: clean named-limit message at 125/126, XPC compiler-service
  crash at >=127), clip-distance ceiling=8, per-component (not per-slot) accounting confirmed
  across float/float2/float3/float4/half, DCE-sensitivity confirmed (declared-but-unread varyings
  are free), independent clip+varying budgets confirmed, cull_distance confirmed Metal-unreachable,
  point-size 511 clamp ceiling (incl. NaN/+Inf) + anomalous negative-magnitude behavior, layer/
  viewport OOB clamp-to-0 (not wrap, not clamp-to-max), provoking-vertex = first-fetched-vertex
  (list + strip + reversed-index).
- Built `harness/genkernels.py` (12 MSL generator functions, pure string templating) and
  `harness/casematrix.py` (140 frozen cases across 11 families).
- Built `harness/schema.py`, `harness/run.py` (7 dispatch kinds), `harness/verify.py`
  (--selftest/--seqtest/--preflight/--between-runs/--captured).
- Smoke-tested every dispatch kind against 19 representative case IDs directly (not through the
  full matrix) -- all 19 PASS, confirming the harness logic before committing to a full run.
- Built `harness/fixtures/recorded_reality.json` from 9 REAL M4 GPU calls through run.py's own
  dispatch functions (standing gate (e)).
- `verify.py --selftest`: 15/15 PASS (clean tree, zero raw/ captures). `verify.py --seqtest`:
  7/7 PASS. `verify.py --preflight`: PASS (raw/ empty).
- **Mid-session coordinator message** reported this directory as "scaffolding only, nothing lost" --
  that report was stale; the actual on-disk state at that point already contained the complete,
  pilot-tested harness described above. Verified via `find`/`git status` immediately after the
  message; no rework needed, no evidence lost. Read `work/COMPILER-EXPLAINER-INTERACTION-20260828.md`
  per the coordinator's request: confirms a db.json ALU-operand-decoding bug (falu2/falu2i
  srcA_reg/srcB_reg top bits are retention flags, not register bits) that is **not applicable** to
  this experiment (no native-instruction decoding or splicing anywhere in EXP-0097); stated
  explicitly in PRE_REGISTRATION.md rather than left implicit.
- Wrote `PRE_REGISTRATION.md` (pinned revision `92acd2ee3c013cfcdd55fcb9bbb6e92b8829a9e1`, 0 tracked
  dirty) and `CAPTURE_CONTRACT.json` (authored-file SHA-256 hashes, frozen matrix summary, gates).
- **Next milestone: execute run01, then run02, then `verify.py --captured`.**
- `run01` executed: 140/140 PASS, 0 FAIL/TIMEOUT, ~8.6s wall. Smoke gate passed first
  (`work/m4_20260828_run01_smoke.json`), written before `raw/m4_20260828_run01/` was created.
- `run02` executed: 140/140 PASS, 0 FAIL/TIMEOUT, ~4.4s wall. Smoke gate passed first
  (`work/m4_20260828_run02_smoke.json`).
- `verify.py --captured m4_20260828_run01 m4_20260828_run02`: `cross_run_gate_pass: true,
  issues_total: 0`. `02_gated.jsonl` SHA-256 is byte-identical between the two runs
  (`46b39fec...`, see `manifest.json`) -- independent confirmation beyond the gate logic itself.
- `verify.py --selftest` and `--seqtest` re-run clean after both captures exist (no interference).
- Pulled and cross-checked every family's key boundary/anomaly records directly from
  `raw/m4_20260828_run01/02_gated.jsonl` before writing RESULTS.md (varying 122..128 window +
  three widths + half; clip 7..10; cull; DCE 6 cases; combo 5 cases; all 14 position_special;
  key point_size boundary/clamp/anomalous points; all layer/viewport OOB; all 3 provoking; all 4
  vary_render_confirm checksums) -- all matched the pre-registered `expect_*` fields, hence 140/140
  PASS.
- Wrote `RESULTS.md` (per-item verdicts, OBSERVED/INTERPRETED split, finite-resource table, gate
  results, Metal-exposure/emulation summary, open items), `README.md`, top-level `manifest.json`
  (hashes of the two runs' raw artifacts).
- **DONE.** Both GLIO-A01 and GLPRE-A03 CLOSED per `RESULTS.md` §1. No git commit made (orchestrator
  owns commits per `experiments/SUBAGENT_BRIEF.md`). `tools/*` untouched (read-only, as required).

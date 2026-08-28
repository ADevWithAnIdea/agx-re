# PROGRESS — EXP-0135

- **2026-08-28T08:20Z** — Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md, gap analysis
  row DRV-P2-03, EXP-0030/RESULTS.md (A18 mesh findings), EXP-0119/0120/0098/0124
  (methodology models). Confirmed tools/shdump, tools/agxtest, tools/iotrace,
  tools/agx-isa surfaces available read-only.
- **2026-08-28T08:35Z** — Inspected public Metal.framework headers (MTLRenderPipeline.h,
  MTLRenderCommandEncoder.h, MTLIndirectCommandBuffer/Encoder.h) and the public MSL
  toolchain headers (metal_mesh, metal_command_buffer) to scope the API surface:
  confirmed `payloadMemoryLength`, `maxTotalThreadgroupsPerMeshGrid`,
  `drawMeshThreadgroupsWithIndirectBuffer:`, CPU-authored ICB mesh commands, and
  `__HAVE_RENDER_COMMAND_MESH__`-gated GPU-authored `render_command::draw_mesh_threadgroups`
  all exist in the public surface for this SDK/toolchain.
- **2026-08-28T09:00Z** — Wrote and built `harness/mesh_probe.m` (4-mode probe:
  direct/indirect/icb_cpu/icb_gpu), `kernels/mesh_sweep.metal`,
  `kernels/mesh_indirect.metal`, `kernels/mesh_icb_gpu.metal`. Manual calibration
  trials (documented in PRE_REGISTRATION.md §0) found EXACT compiler-reported
  boundaries for NV(256)/NP(512)/payload(16384), the silent-zero AMP_COUNT/indirect-
  grid boundary at 65536, and the mesh-ICB maxCommandCount three-region behavior
  (OK / CMDBUF_ERROR / CRASH_SIG11).
- **2026-08-28T09:10Z** — Built Group R byte-extraction (`harness/shdump_mesh.m`,
  reused `mesh_extract.py`/`agxparse.py`) and DATA-TRACE (`harness/iohello_mesh.m`,
  reused `tools/iotrace`) tooling. Confirmed object/mesh helper-region lengths
  (128B/576B) match EXP-0030's A18 values exactly; confirmed the `43 00 00 01`
  byte sequence present in both object and mesh streams, and cross-checked
  against `tools/agx-isa`'s existing `frame_marker` DB entry (already generalized
  by EXP-M4-13, own-MSL M4 corpus work, beyond EXP-0030's narrower framing).
- **2026-08-28T09:15Z** — Wrote `analysis/gen_matrix.py` (98-case fixed matrix,
  later 103 after widening the ICB maxCommandCount ladder), `analysis/run.py`
  (orchestrator, append+fflush per record), `analysis/verify.py`.
- **2026-08-28T09:18Z** — Ran ONE full NON-RECORDED smoke pass
  (`work/smoke/smoke01/`, 102 records at the time): zero TIMEOUT, zero host
  instability, all 4 CRASH_SIG11 anomalies followed by OK post-fault sanity
  checks. Not promoted as evidence.
- **2026-08-28T09:20Z** — Froze `CAPTURE_CONTRACT.json` + `PRE_REGISTRATION.md`
  at repo HEAD `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`.
- **2026-08-28T09:25Z** — Captured `raw/m4_20260828_run01/` (107 records, COMPLETE).
- **2026-08-28T09:32Z** — Captured `raw/m4_20260828_run02/` (107 records, COMPLETE).
- **2026-08-28T09:35Z** — Gates: `--selftest` PASS, `--seqtest` PASS. `--captured`
  initially FAILED on one case (`D-trace-nearmax`: an incidental IOKit selector
  32 call count 2 vs 1, unrelated to the tested independent variable). Root-caused,
  disclosed in RESULTS.md and PRE_REGISTRATION note; narrowed the gate's
  `GATED_TRACE_KEYS` to the fields the hypothesis actually depends on
  (`n_bo`/`sel9_calls`/`size_multiset`), which were already byte-identical.
  Re-ran `--captured`: PASS, 107/107.
- **2026-08-28T09:45Z** — Writing RESULTS.md / README.md.

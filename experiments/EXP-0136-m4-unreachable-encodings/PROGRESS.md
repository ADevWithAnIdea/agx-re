# PROGRESS — EXP-0136

- 2026-08-28T01:24Z: Directory created. Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md,
  APPLE9_RE_IMPLEMENTATION_GAPS.md §DRV-P2-05, and prior experiments EXP-0015 (sampler/
  texture descriptor field map), EXP-0097 (provoking vertex Metal-exposure negative),
  EXP-0098 (compute-emulated transform feedback, explicitly left native GS/streamout
  UNKNOWN), EXP-0123 (rasterization limits, conservative-raster Metal-exposure negative).
- 2026-08-28T01:24-01:52Z: NON-RECORDED technical spike (`work/spike/`) to establish
  whether a Metal-internal resource descriptor's live bytes can be directly patched from
  our own process. First design (patch between two dispatches reusing the same
  MTLSamplerState) FAILED SILENTLY -- discovered Metal rewrites the descriptor pool entry
  on every fresh `-setSamplerState:` bind. Redesigned to patch within the single command
  buffer being observed. Validated with a bit-exact positive control (patched
  clampToEdge->repeat reproduces a real API-created repeat sampler's pixel and byte
  pattern exactly). Ran informal single-point probes of all 4 descriptor/opcode families;
  none hung the host. Built `gfxprobe.m` (restart/norender) and validated similarly.
  Verified `tools/agxtest` runs locally on M4 unmodified (hash-checked copies) with a
  smoke round-trip (add.metal, splice test).
- 2026-08-28T01:53Z: Pre-registered (`PRE_REGISTRATION.md`, pinned revision
  `ea1e17dadfb4052537da1449bcdc133c6a09127d`). Froze the 97-case matrix
  (`harness/casematrix.py`).
- 2026-08-28T01:55Z: Built `harness/run.py`, `harness/verify.py`, `harness/schema.py`.
  `--selftest` and `--seqtest` both green before any device interaction with the frozen
  matrix.
- 2026-08-28T01:56Z: Built `work/bin/{descpatch,gfxprobe,iotrace.dylib}` and
  `work/bin/agxtest/{shdump,agxrun,agxtest.py,agxparse.py}` -- all `tools/*` copies
  hash-verified identical to the read-only originals before building.
- 2026-08-28T01:57Z: NON-RECORDED smoke gate (`work/smoke/`, 9 cases, one per distinct
  mechanism/kind pair) -- 9/9 OK/PASS.
- 2026-08-28T01:58Z: Fixed a real nondeterminism found by the smoke data itself
  (arg_bo_cpu/desc_bo_cpu are ASLR'd CPU pointers, unlike every GPU-VA-space field, which
  is deterministic per case shape) -- added to the stripped-from-`observed` set in
  `run.py`.
- 2026-08-28T01:59Z: `raw/m4_20260828_run01/` -- 97/97 cases, 97 PASS / 0 FAIL / 0
  TIMEOUT. Wall time 58s. Zero host wedges.
- 2026-08-28T02:01Z: `raw/m4_20260828_run02/` -- 97/97 cases, 97 PASS / 0 FAIL / 0
  TIMEOUT. Wall time 75s. Zero host wedges.
- 2026-08-28T02:02Z: `verify.py --captured` found 2 categories of genuine cross-run
  nondeterminism (both hardware/OS-classification artifacts, not the underlying fact under
  test): `observed.n_bos_loaded` (iotrace registration-count timing) and
  `observed.error`/`error_patched` text (a GPU-hang fault classifies as either
  `kIOGPUCommandBufferCallbackErrorHang` or `...ErrorInnocentVictim` depending on
  scheduling -- `status=CMDBUF_ERROR` itself matched exactly both runs). Per the standing
  gate rule, gated on the invariant (`status`) and documented the raw values in
  `schema.py`'s `NONDET_OBSERVED_KEYS` (kept inside `observed`, excluded from the
  byte-comparison) rather than silently discarding them. Added regression checks to
  `verify.py --selftest` proving the gate both tolerates these specific keys and still
  fails on any other mismatch. Re-ran `--captured`: `cross_run_gate_pass: true,
  issues_total: 0`.
- 2026-08-28T02:05Z: Analysis (`analysis/summarize.py`) confirms decisive, monotonic
  results for all 7 hypotheses -- see RESULTS.md.

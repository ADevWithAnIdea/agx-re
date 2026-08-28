# EXP-0109 PROGRESS

- **M1 — harness scaffolding + toolchain check.** `tools/shdump` builds and round-trips
  on this M4 host (own compile → extract → decode). `experiments/EXP-0109-m4-stage-abi/`
  created; prior-art reviewed (EXP-0031, EXP-0092, EXP-0029, EXP-0097, EXP-0091,
  `docs/isa/register-move-and-liveness.md`, `docs/isa/README.md`).
- **M2 — structural harness (`vfetch_extract.m`, `mrt_extract.m`).** Built and smoke-
  tested against ad hoc `work/` output (never `raw/`). Found and fixed two MSL
  authoring bugs (calling a `[[vertex]]`-qualified function from another vertex
  function is illegal; pull-model interpolation needs the fragment-side `interpolant<>`
  wrapper type, not a plain member). Discovered during this prototyping that MSL's
  `[[stencil]]` fragment-output attribute compiles cleanly, contradicting the
  pre-registration's working negative hypothesis (disclosed as a confounder in
  `PRE_REGISTRATION.md`).
- **M3 — HW-PROBE harness (`render_probe.m`, `compute_probe.m`).** Built and smoke-
  tested. Found and fixed a vertex-buffer stride bug in the `vsfetch` mode (wrong
  stride caused reads to land on unintended buffer offsets) before any official
  capture — caught by an immediately-inspected ad hoc single-case run, not by the
  official two-run gate.
- **M4 — casematrix.py frozen (57 cases), PRE_REGISTRATION.md + CAPTURE_CONTRACT.json
  written and frozen (state PRE_GPU).** `harness/fixtures/recorded_reality.json` built
  from 6 real GPU/compiler calls made during harness development (before either
  official run).
- **M5 — standing gates implemented and passing pre-capture.** `verify.py --selftest`
  9/9 PASS, `verify.py --seqtest` 3/3 PASS, `run.py --smoke-only` (non-recorded,
  writes to `work/`, not `raw/`) both real probe cases OK. Full 57-case dry run into
  `work/dryrun1/` (not `raw/`) completed cleanly (56 OK, 1 expected negative-control
  FAIL) before spending an official run id.
- **M6 — official captures.** `raw/m4-20260828-run01/` (57/57 cases, 56 OK + 1 expected
  FAIL) and `raw/m4-20260828-run02/` (same), each a separate `run.py` process
  invocation. `verify.py --crossrun` → **57/57 byte-identical, 0 mismatches.**
  `CAPTURE_CONTRACT.json` state updated to `RUN02_PRESENT`. `--selftest`/`--seqtest`
  re-run post-capture, still PASS.
- **M7 — analysis.** `analysis/decode.py` (pure arithmetic over the already-captured
  run01 JSONL, no new GPU calls) decodes half-float readbacks and diffs structural
  byte lengths; `analysis/summary.json` written. One supplementary, single-run,
  **non-frozen** ad hoc probe (`/tmp/render_probe_src0test.m`, a one-line blend-factor
  variant) was run to correctly interpret the dual-source blend arithmetic (explained
  in RESULTS.md §FS-OUT dual-source) — explicitly flagged as outside the two-run gate,
  mirroring EXP-0091's `d_helper_relay` precedent.
- **M8 — RESULTS.md written.** Final deliverable.

No faults, hangs, `CMDBUF_ERROR`s, or host instability observed anywhere in this
experiment. No reboot. No BLOCKED state entered.

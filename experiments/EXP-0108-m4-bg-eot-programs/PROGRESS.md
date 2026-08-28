# PROGRESS — EXP-0108

- 2026-08-27T23:xx local: repo scaffolding created; exploratory (non-evidence) probing under
  `dev/` established the broadened-tracer technique, the color-descriptor relocation trigger
  (MRT>=2 OR MSAA OR memoryless, confirming `docs/pipeline/README.md`), the code-window
  invariance across 8 exploratory configs, and a candidate depth/stencil-specific extra state
  region -- all superseded by the frozen harness below; `dev/` is scratch, not evidence.
- Milestone M1: harness frozen (`harness/wtrace.c`, `harness/probe.m`, `harness/casematrix.py`
  — 40 cases / 11 axes), `run.py`/`verify.py`/`analysis.py`/`make_manifest.py` written. Full
  40-case dry run (informal, `work/`, not `raw/`) completed cleanly: all 40 cases `status=OK`,
  ~23s wall time total. VA-arithmetic depth/stencil-candidate heuristic tried and DROPPED
  (allocator-order-sensitive across two harness revisions); replaced with the VA-free
  size+hash region-count-delta signal, validated on a1/d1/b2/i1: format-only change gives
  zero delta (clean negative control), depth-only and stencil-only each give exactly +1
  region of size 0x20000, combined depth+stencil gives +2 (additive, isolated from MRT/format
  noise).
- Milestone M2: `verify.py --selftest`/`--seqtest` PASS; official gated capture executed as
  `m4-20260828-run01`/`m4-20260828-run02`, 40/40 `OK` in both. `analysis.py` cross-run check
  then FAILED: several named roles' WHOLE-region SHA-256 (mrt-attachment-descriptors,
  single-rt-color-descriptor, clear-color-arena, sparse-tiler-param-header, and tiling-state
  for the two 200000-instance partial cases only) differ run-to-run even though every trusted
  field-level window (rts, k_load/k_store, first64_hex, unnamed_regions SIZE multiset) is
  byte-identical across all 40 cases -- confirming exactly the noise PRE_REGISTRATION.md
  section 5 flagged in advance (vertex-buffer-alias and similar incidental bytes outside the
  trusted offsets). One case (e3-msaa4-resolve) additionally showed a `content_captured`
  flip for `mrt-attachment-descriptors` between runs -- a SIGUSR1-snapshot read-timing flake
  in the harness, not a hardware property. `run_one_case()`'s data-collection logic was NOT
  changed; added `run.reproducible_projection()` (drops exactly the fields now known
  non-deterministic) as the actual cross-run gate, with a dedicated unit test
  (`projection_self_check`) and a full-pipeline mutator
  (`m_run02_named_sha256_only_diverges`) proving the gate still passes when ONLY those fields
  differ and still fails on any real semantic change. `verify.py --selftest`/`--seqtest`
  re-PASS under the fix. The original m4-20260828-run01/run02 pair is preserved untouched at
  `raw_superseded/` (never edited, never reused); the officially gated pair is
  `m4-20260828-run03`/`m4-20260828-run04`, captured fresh under the frozen fix.
- Also corrected `run.py`'s `AUTH_DOC` to exclude `RESULTS.md`/`PROGRESS.md` from the
  frozen/hashed authored set (matching `EXP-0100`'s convention): those are living documents
  written/extended after capture based on `analysis.json` and must not be required to
  byte-match a pre-capture snapshot; they remain required to exist and are tracked by
  `make_manifest.py`. Only `README.md`/`PRE_REGISTRATION.md` (method, not findings) are
  frozen-hashed.
- Milestone M3: recaptured under the AUTH_DOC fix as `m4-20260828-run03`/`m4-20260828-run04`
  (40/40 `OK` both). `analysis.py` still failed byte-exactness: ONE case
  (g2-depth-write) had `mrt-attachment-descriptors` content successfully read in run03 but
  `content_captured=False` in run04, with role/size otherwise identical -- a second,
  narrower SIGUSR1-snapshot read-timing race (distinct from the whole-region-hash noise
  M2 fixed). Added `run.records_reproducibly_equal()` (pairwise, tolerates exactly this
  content-capture-success asymmetry for a role present+same-size in both runs, with a
  <=5-flake budget across the 40-case matrix; a real field-level content mismatch, or any
  other field, still fails), a dedicated unit test (`flake_tolerance_self_check`), and
  reused the existing full-pipeline mutator pattern. `run_one_case()`'s data-collection
  logic was again NOT changed. run01-run04 are all preserved untouched in
  `raw_superseded/`. The officially gated pair is `m4-20260828-run05`/`m4-20260828-run06`.
  Interesting by-product of the flake: run03 (only) captured a POPULATED k=1 record inside
  `mrt-attachment-descriptors` for a single-color-attachment depth case -- see RESULTS.md
  (reported as a single-run, uncorroborated INFERRED lead, not a validated fact).

# PROGRESS -- EXP-0123 M4 rasterization limits

- 2026-08-28T00:00Z Directory scaffolded. Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md,
  APPLE9_RE_IMPLEMENTATION_GAPS.md DRV-RASTER-01, docs/P0-P1-CLOSURE.md row P1.8.
  Reviewed EXP-0047, EXP-0091, EXP-0097 (adjacent/prior evidence, not to be redone).
- 2026-08-28T01:00Z Built harness/rasterprobe.m (render/multiattach/texcreate/
  bufferindex/bytesconst/bufferalign/texturebind ops) and harness/computeprobe.m
  (dispatch op). Both compile clean with `-fobjc-arc -framework Metal -framework
  Foundation` under Apple clang 21.0.0.
- 2026-08-28T02:00Z Exploratory hardware calibration (own-shader + HW-probe, ad hoc,
  under harness/work -- never committed as normative evidence) to locate REAL
  boundaries before freezing the matrix, per CLAUDE.md's "extrapolate, then test"
  mandate: line rasterization rule, point-size rounding, polygon fill modes, depth
  clip/clamp, conservative-raster negative, coverage/early-late, and every limit in
  the finite-resource table. Findings summarized in PRE_REGISTRATION.md section 0.
- 2026-08-28T02:30Z One clean-room boundary question surfaced during calibration
  (an ObjC selector matching `setLineWidth:` responds via `respondsToSelector:` but
  is ABSENT from the public Metal SDK headers) was deliberately NOT resolved
  unilaterally: excluded from the matrix, not promoted anywhere, flagged to the
  coordinator in the final report. See RESULTS.md section "Flagged, non-promoted
  observation" and `work/gen/probe_selectors.m` / `probe_linewidth.m` (scratch).
- 2026-08-28T03:00Z Froze `harness/casematrix.py` (98 cases, 18 families),
  `harness/genkernels.py` (deterministic MSL generation), `harness/run.py`
  (subprocess-per-case driver, hard 25s timeout, append+fflush+fsync per record),
  `harness/schema.py`, `harness/verify.py` (5 standing gates).
- 2026-08-28T03:15Z NON-RECORDED smoke/pilot run (`work/pilot_run/`, run id
  `pilot1`) BEFORE touching raw/: 98/98 PASS on first full pass after two bug fixes
  (multiattach n=9 crash-prediction; bytesconst functional-check shader). Pinned
  `harness/fixtures/recorded_reality.json` from this real pilot capture.
- 2026-08-28T03:30Z `verify.py --selftest`: 22/22 PASS. `verify.py --seqtest`: 7/7
  PASS.
- 2026-08-28T03:35Z Wrote PRE_REGISTRATION.md + CAPTURE_CONTRACT.json, pinned
  revision 6a8d588678a94eedafa215f9ac57bceb7fd4e36e.
- 2026-08-28T03:40Z Official run01 (`raw/m4_20260828_run01/`): 98/98 PASS.
- 2026-08-28T03:45Z Official run02 (`raw/m4_20260828_run02/`): 98/98 PASS.
  `verify.py --captured run01 run02`: cross_run_gate_pass=true, issues_total=0.
- 2026-08-28T04:00Z Wrote analysis/report.py + analysis/report.json (repeatable
  derived summary from raw/).
- 2026-08-28T04:30Z Wrote RESULTS.md, README.md, manifest.json. Experiment complete.
  Zero host wedges, zero out-of-process faults across ~250 total subprocess
  invocations (pilot + run01 + run02 + ad hoc calibration).

# EXP-0111 — M4 fragment semantics (FS-01..FS-12)

Closes the **FS-\*** cluster (12 items) of Part II in `APPLE9_RE_IMPLEMENTATION_GAPS.md`
(lines 1038-1075), and resolves two open anomalies flagged by
`experiments/EXP-0091-m4-fragment-sample-discard`: (a) the spatially non-uniform
pre-discard helper-status read (GLFS-A03 §3) and (b) the deterministic but spatially
non-uniform per-sample-ID discard suppression pattern (GLFS-A07 §6).

**Question:** how does Apple9 address interpolation coefficients per qualifier; what do
derivative operations (dfdx/dfdy/fwidth) require of the hardware 2×2 quad and of
helper/discarded/out-of-coverage lanes; are all Vulkan/GL interpolation modes
independently usable; is a convergent interpolated input safe to fold into a flat load;
can dynamically-indexed fragment inputs/outputs be lowered without an unsupported
hardware feature; and does `discard_fragment()` suppress every fragment-side-effect
channel (including sample-mask, and — to the extent MSL can even express it —
stencil)?

**Method:** authored MSL fragment shaders rendered to a small owned target with pixel/
buffer readback against a host-computed oracle (own-shader differential compile +
hardware splice where MSL cannot express the needed encoding directly). Render testbed:
`harness/fsrun.m`, derived from EXP-0091's own prior authored `fsrun.m` (itself a
superset of the read-only `tools/agxtest/agxrender.m`) plus one new capability
(`--rt-count`, up to 3 render targets) added here for the FS-11 dynamic-output probe.
`tools/shdump`, `tools/agx-isa`, `tools/agxtest` used strictly read-only, exactly as
documented in their own READMEs.

**Clean-room category:** OWN-SHADER (every inspected/spliced byte is our own compiled
MSL) + HW-PROBE (device execution/readback) + PUBLIC (MSL-surface-absence findings for
FS-03's sample-position query, FS-05's coarse-derivative mode, and FS-12's stencil
output — none exist in the surveyed Metal Shading Language surface).

## Layout

```
PRE_REGISTRATION.md   frozen hypotheses (H1-H12), exact FS-01..FS-12 wording quoted,
                       per-item coverage/deferral decision, pilot findings that informed
                       the freeze, case matrix reference
CAPTURE_CONTRACT.json  machine-readable freeze: hashes, schema, gate classes, timeouts
RESULTS.md              per-item response blocks (FS-01..FS-12 + both anomaly
                       resolutions), exact numbers, finite-resource table, deferred-item
                       list, clean-room attestation
PROGRESS.md              timestamped milestones, incl. a self-disclosed /tmp compliance
                       correction (see below)
schema.py                ONE shared gated/non-gated record key-set (imported by run.py
                       and verify.py -- never restated)
run.py                    the frozen 56-case matrix + runner (compile_scan, gpu_render,
                       compile_attempt case kinds)
verify.py                 --selftest / --seqtest / --smoke / --crossrun (standing gate
                       set); all scratch I/O confined to work/scratch/
harness/fsrun.m           authored render+readback tool (plain compile OR archive+splice
                       modes; MSAA/depth/occlusion/buffers/textures/up-to-3 render
                       targets)
kernels/*.metal           28 authored MSL probes (poscoord_*, deriv_*, interp_*,
                       dynidx_*, fs12_*, anomaly_*, helper_orig_relay)
raw/m4_20260828_run01/    first frozen capture (56 gated+56 nongated JSON records)
raw/m4_20260828_run02/    second frozen capture (byte-identical gated records, verified)
work/                     regeneratable build scratch: work/bin (compiled shdump/fsrun),
                       work/archives (*.bin Metal binary archives -- compiled outputs of
                       our own MSL, regeneratable, not evidence in the usual convention),
                       work/scratch (throwaway pilot/diagnostic output -- see the
                       compliance note in PROGRESS.md), work/trial/ (pilot capture used
                       by verify.py's load_pilot_shapes() as the gate-class-(e) "recorded
                       reality" fixture source; do not delete)
```

## Reproduce

```sh
cd experiments/EXP-0111-m4-fragment-semantics
xcrun clang -fobjc-arc -o work/bin/shdump ../../tools/shdump/shdump.m -framework Metal -framework Foundation
xcrun clang -fobjc-arc -o work/bin/fsrun harness/fsrun.m -framework Metal -framework Foundation
python3 verify.py --smoke                                    # before any raw/ exists
python3 run.py --run run01 --out raw/m4_<date>_run01
python3 run.py --run run02 --out raw/m4_<date>_run02
python3 verify.py --crossrun raw/m4_<date>_run01 raw/m4_<date>_run02
python3 verify.py --selftest
python3 verify.py --seqtest
```

## Headline findings (see RESULTS.md for full response blocks and evidence)

- **FS-01/02/03:** `get_sr 0xa0`/`0xa1` deliver the integer fragment pixel X/Y
  (HW-splice-swap-confirmed specifically in the fragment stage — elevates EXP-0031's
  "inferred" claim to `HW-VALIDATED`); `[[position]] == (px+0.5, py+0.5)`, stable across
  samples and helper invocations; origin is upper-left, y down (HW-confirmed).
- **FS-04/06/07:** derivatives are strictly hardware-2×2-quad-local (a step exactly at a
  quad-pair boundary is invisible to `dfdx`/`dfdy` on both sides); both demoted and
  never-covered-original helper lanes correctly participate; every derivative instance
  is scalar (one op per component, `scalarize_ddx=true`) — plus a genuine, unresolved
  axis-byte labeling anomaly reported for the docs owner.
- **FS-05:** no MSL-reachable coarse-derivative mode exists (`PUBLIC` absence); ISA-level
  presence of an unreached coarse bit is `UNKNOWN`, explicitly deferred.
- **FS-08/09:** centroid interpolation measurably differs from (unclamped) center
  extrapolation under partial coverage. **Significant finding:** `interpolate_at_offset`
  does NOT implement its own documented "signed offset from pixel center" contract on
  this M4/toolchain — it behaves as an absolute, pixel-top-left-corner-relative, y-down
  window coordinate instead (no clamp/fault up to ±2.0 pixel-widths). Convergent
  (all-vertices-equal) interpolation is demonstrably NOT bit-identical to flat in 3 of 5
  tested configurations (no-perspective path) — `nir_io_always_interpolate_convergent_
  fs_inputs` is justified.
- **FS-10/11:** dynamic fragment-INPUT indexing lowers safely (read every candidate via
  ordinary fixed-slot interpolation, select via ALU — HW-confirmed correct). Dynamic
  fragment-OUTPUT indexing has no direct MSL syntax at all (compile-rejected); the
  branch-unrolled workaround is both necessary and HW-confirmed correct even for a
  genuinely per-fragment-divergent selector — with one open, flagged sub-finding (the
  compiled encoding is structurally richer than a naive "two branches, two stores"
  model, not fully bit-decoded).
- **FS-12:** sample-mask output from a demoted lane is suppressed exactly as completely
  as color/depth/buffer/atomic (EXP-0091, extended here); stencil is undecidable via MSL
  (no shader-driven stencil output exists at all) — `PARTIAL`, `INFERRED`-by-analogy only.
- **Both EXP-0091 anomalies resolved:** neither reproduces under an independent
  measurement method (direct pre-discard write instead of quad-shuffle relay for
  anomaly (a); resolve-fraction instead of an atomic counter for anomaly (b)) — both are
  now attributed to the ORIGINAL measurement techniques, not to genuine hardware
  non-uniformity; the underlying GLFS-A03/GLFS-A07 claims are strengthened to two
  independent HW-VALIDATED confirmations each.

All findings are M4/G16G only; A18 Pro/G17P is `INFERRED`-by-family per target
discipline, not independently validated.

## Compliance note

A mid-session update to `experiments/SUBAGENT_BRIEF.md` prohibited any file I/O outside
the repository (including `/tmp`), which several early pilot commands in this session had
already done before the update was read. All such files were identified and deleted
immediately upon reading the update; every finding derived from them was independently
reproduced through the frozen kernels/harness before being relied on in RESULTS.md. See
`PROGRESS.md` for the full self-disclosure.

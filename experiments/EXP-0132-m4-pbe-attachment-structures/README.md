# EXP-0132: M4 PBE / render-target attachment-descriptor field mapping

- **Gap:** `APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-PBE-01 / `docs/P0-P1-CLOSURE.md`
  row P1.1 (Complete PBE and render-attachment structures) — the only P1.1 dispatch
  this wave.
- **Clean-room categories:** HW-PROBE / DATA-TRACE / OWN-SHADER.
- **Target:** local Apple M4 / G16G, this host, macOS 26.6.2 (25G82), Metal 4. M4-only;
  no A18 evidence collected (A18 hands-off).
- **Prior work built on:** `experiments/EXP-0048-bg-eot-pbe/` (six PBE format/control
  record variants, four fixed allowlisted state BOs, empty-tile behavior).
  `experiments/EXP-0108-m4-bg-eot-programs/` (broadened per-process BO inventory; the
  region-count-delta method; the depth/stencil k-slot-reuse finding this experiment's
  priority 1 exists to confirm or refute under a fixed, race-free harness — EXP-0108's
  own RESULTS.md flags it as "doubly-corroborated... NOT byte-exact-gated" and names the
  read-timing race as the reason). `experiments/EXP-G1b-pbe-rt-descriptor/` (A18; the
  32-byte PBE descriptor field map, the 3-segment LOAD/RENDER/STORE attachment chain, the
  MRT 0x20-byte-stride k-array). `experiments/EXP-0095-m4-texture-image-matrix/` and
  `experiments/EXP-0117-m4-stage-abi-remainder/` (M4; boundary-probe method and PROCESS_ABORT
  subprocess-isolation pattern reused here; EXP-0117 already `HW-VALIDATED` the
  color-attachment-index-8 ceiling, cited rather than re-probed). `docs/descriptors/README.md`
  and `format-table.md`, `docs/pipeline/README.md` (existing field maps this experiment
  extends/re-verifies, never contradicts without saying so explicitly).

See `PRE_REGISTRATION.md` for the full falsifiable hypotheses (H1–H5), the disclosed
pre-capture diagnostic phase (three harness bugs and two methodological/reliability
findings, all found and fixed before any `raw/` capture — see also `PROGRESS.md`), confounders,
frozen raw-record schema, and address-normalization policy. See `RESULTS.md` for the
officially gated observations/interpretation once captured.

## What this experiment does

1. Forks `harness/wtrace.c` from EXP-0108's interposer (same public-API-only IOKit
   technique, same known-role table) and removes its documented SIGUSR1 read race by
   construction: the probe calls an exported `wtrace_snapshot_now()` directly, in-process,
   synchronously, right after `waitUntilCompleted`, instead of posting an async signal a
   separate thread picks up nondeterministically.
2. Forks `harness/probe.m` from EXP-0108's JSON-config-driven render harness and extends
   it with array-layer (`arrayLength`/`slice`) and mip-level (`mipCount`/`level`) support
   for color attachment 0, with every (slice,level) pre-filled with a distinct canary byte
   pattern and read back via `getBytes` after the render — the alias/clamp/silent-zero
   boundary detector required by this experiment's priority 3 (finite-field boundaries).
3. Renders a 16-case matrix (`harness/casematrix.py`): 7 depth/stencil-reverify cases
   (priority 1), 3 array + 1 array-boundary case (priority 3 / DRV-PBE-01 "array
   selection"), 2 mip + 1 mip-boundary case (priority 3 / "mip... selection"), and 2 MSAA
   store+resolve cases (priority 2, resolve-descriptor field detail).
4. Extracts, per case, the masked k-indexed `mrt-attachment-descriptors` window
   (k=0..7 LOAD/STORE plus the arena's own two header words, surface-address subfield
   masked) and a masked `clear-color-arena` window, plus presence/size/capture-success
   for every other named role (including `attachment-slot-b`, priority 3's third target —
   see H5).

## Reproduction

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0132-m4-pbe-attachment-structures
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B verify.py --preflight
python3 -B run.py --execute --run-id m4-20260828-run01
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260828-run02
python3 -B verify.py --seqtest
python3 -B verify.py --captured
python3 -B analysis.py --write
python3 -B make_manifest.py --write
python3 -B make_manifest.py --check
```

Run IDs are burned on first use (`run.py` refuses to reuse a run directory); a new capture
needs new IDs and a fresh pre-registration addendum, per `experiments/SUBAGENT_BRIEF.md`.

## Evidence map

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`: frozen hypotheses, falsifiers, disclosed
  pre-capture diagnostic findings, schema, address-normalization policy, authored-file hashes.
- `PROGRESS.md`: milestone log, including the three harness bugs and two
  methodological/reliability findings caught before any `raw/` capture.
- `harness/wtrace.c`: the race-fixed interposer (own code, public API only, forked from
  EXP-0108).
- `harness/probe.m`: the authored, JSON-config-driven Metal render harness (all MSL
  generated inline from authored templates; forked/extended from EXP-0108).
- `harness/casematrix.py`: the 16-case, 8-axis matrix (single source of truth).
- `harness/fixtures/`: real recorded-reality inventory/descriptor excerpts from this
  experiment's own pre-capture diagnostic phase, used by `verify.py --selftest`.
- `run.py`: capture orchestration (build, standing gates, per-case subprocess,
  append+fflush+fsync).
- `verify.py`: the five standing gates.
- `analysis.py`: cross-run comparison + H1–H5 hypothesis evaluation → `analysis.json`.
- `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`: immutable captures.
- `RESULTS.md`: observations vs. interpretation, exact tested matrix, remaining P1.1 gaps.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Apple binary introspection: NONE
Reproduction: commands above
Evidence: raw/, analysis.json, manifest.json
```

# EXP-0108: M4 BG/EOT program-record ABI matrix

- **Gap:** `APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-UAPI-04 / `docs/P0-P1-CLOSURE.md` P0.4
  (BG/EOT/partial-BG/partial-EOT programs).
- **Clean-room categories:** HW-PROBE / DATA-TRACE / OWN-SHADER.
- **Target:** local Apple M4 / G16G, this host, macOS 26.6.2, Metal 4. M4-only; no A18 evidence.
- **Prior work:** `experiments/EXP-0048-bg-eot-pbe/` (empty-tile Clear/Store and Load/Store
  behavior, six PBE format/control record variants, four fixed allowlisted state BOs; explicitly
  does not locate a program/tag/resource-spec/ABI). `experiments/EXP-0091-m4-fragment-sample-discard/`
  and `EXP-0093-m4-fence-barrier-interlock` (the ordinary fragment-program epilog bracket, a
  different thing from a BG/EOT program). `docs/pipeline/README.md` (tile size, imageblock,
  render-target attachment descriptor field map, MSAA, memoryless, load/store actions).

See `PRE_REGISTRATION.md` for the full falsifiable hypotheses, confounders, content-capture
policy, and frozen schema. See `RESULTS.md` for observations/interpretation once captured.

## What this experiment does

1. Widens EXP-0048's fixed four-BO allowlist to a full per-process registered-resource
   inventory (`harness/wtrace.c`, a from-scratch DYLD interposer over the public IOKit
   `IOServiceOpen`/`IOConnectCallMethod` user-client selectors — same technique as
   `tools/iotrace` and EXP-0048's `harness/allowtrace.c`, independently reimplemented here with
   a broader, explicitly documented content-capture policy; see `PRE_REGISTRATION.md` §6).
2. Renders a 40-case, 11-axis matrix (`harness/casematrix.py`) of render-pass configurations:
   load/store action, MRT count, mixed-format MRT, per-format sweep (7 formats), MSAA
   sample-count + resolve, memoryless color, depth (with/without an enabled depth-write
   pipeline state), stencil (with/without an enabled stencil-write state), combined
   depth+stencil, empty-tile boundary repeats, and a partial-render probe that isolates
   target size from instance/primitive count.
3. Compares captured state across cases using a VA-free structural signal (size+SHA-256
   multiset of every "unnamed" captured/hashed region) to find configuration-correlated new
   records without relying on fragile GPU-address arithmetic (see `PRE_REGISTRATION.md` §5 for
   why VA-based identification was tried and dropped).
4. Extracts field-level content (masked to exclude the surface-address subfield) only for the
   two already-established color-descriptor roles, using the correct per-role segment layout
   (`run.py` `ROLE_WINDOW`) for each.

## Reproduction

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0108-m4-bg-eot-programs
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B make_manifest.py --check
python3 -B verify.py --preflight
python3 -B run.py --execute --run-id m4-20260828-run01
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B make_manifest.py --check
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260828-run02
python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write
python3 -B make_manifest.py --write
python3 -B make_manifest.py --check
python3 -B verify.py --captured
```

Run IDs are burned on first use (`run.py` refuses to reuse a run directory); a new capture
needs new IDs and a fresh pre-registration addendum, per `experiments/SUBAGENT_BRIEF.md`.

## Evidence map

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`: frozen hypotheses, falsifiers, schema,
  content-capture policy, authored-file hashes.
- `harness/wtrace.c`: the broadened DATA-TRACE interposer (own code, public API only).
- `harness/probe.m`: the authored, JSON-config-driven Metal render harness (all MSL generated
  inline from authored templates).
- `harness/casematrix.py`: the 40-case, 11-axis matrix (single source of truth).
- `run.py`: capture orchestration (build, standing gates, per-case subprocess, append+fflush).
- `verify.py`: the five standing gates (`--selftest`, `--seqtest`, smoke gate wired into
  `run.py`, address-normalization/no-nondeterministic-field checks, fixtures from recorded
  reality).
- `analysis.py`: cross-run comparison + derived structural findings -> `analysis.json`.
- `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`: immutable captures.
- `RESULTS.md`: observations vs. interpretation, exact tested matrix, remaining P0.4 gaps.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Apple binary introspection: NONE
Reproduction: commands above
Evidence: raw/, analysis.json, manifest.json
```

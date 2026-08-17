# EXP-0042 — graphics code selection and live code-container structure

- Date: 2026-08-17
- Target actually tested: local Apple M4 / G16G, macOS 26.6.2 (25G82)
- Gap scope: `AGX_RE_INFORMATION_GAPS.md` P0.2 and the entry/extent/container/resource
  parts of P0.7
- Evidence: HW-PROBE + DATA-TRACE + OWN-SHADER

## Question and acceptance relevance

How does one queue select among several live VS/FS pipelines without a per-render
code-BO-base field, and which live code-BO fields describe an authored program's entry,
extent, and adjacent metadata? The unchanged Asahi UAPI has a queue-wide
`usc_exec_base`, so the important distinction is between a queue/window-relative value,
a per-draw selector, and macOS-private bookkeeping. This experiment does not assume that
a macOS field maps to the Linux UAPI merely because the shapes look compatible.

## Pre-registered hypotheses and falsifiers

1. If graphics selection is solely a firmware walk with no per-draw selection, A/B/A/B
   switches should not create a pipeline-correlated VDM or PPP field. A stable field that
   follows the selected pipeline refutes that hypothesis.
2. If a candidate is an address or code offset, changing pipeline creation order should
   move it with the authored code record. If it instead follows ordinal creation order,
   it is a handle/token, not a code address.
3. If `0x58000+0x08` is merely an FS byte size (the earlier interpretation), two
   equal-extent fragment programs cannot produce distinct values there. Equal machine-code
   bodies with distinct output and distinct values refute the size interpretation.
4. If ordinary client allocation determines the code base, allocating 17 live BOs before
   pipeline creation should move it. An unchanged base and byte-identical code BO refute
   that hypothesis for the tested range.
5. A sized live record is only structurally established until a live mutation proves who
   consumes it. Correlation alone cannot distinguish a HW/FW ABI field from Metal
   userspace bookkeeping.

Known confounders were compiler dead-code elimination, pipeline caching/deduplication,
allocator movement, first-submit initialization, and unknown driver-generated programs.
The probes use runtime buffer values to keep the large paths live, repeat the final matrix,
and analyze only bytes proven to come from our authored MSL. Unknown programs are retained
as raw DATA-TRACE evidence but are not decoded.

## Authored probes

- `kernels/pipeline_a.metal` and `pipeline_b.metal`: independent VS/FS pipelines with
  different extents and red/green readbacks.
- `harness/multipipe.m`: compiles both in one process, keeps them alive on one command
  queue, and submits `A,B,AB,BA,ABAB,BABA,ABBA,BAAB`.
- `kernels/stage_matrix.metal` and `harness/stage_matrix.m`: small/large VS x FS matrix,
  plus `fs_equal_a`/`fs_equal_b`. The equal pair has byte-identical `_agc.main` code but
  different authored constant programs and output.
- `analysis/capture.py`: builds the authored harnesses and the repository's clean-room
  `tools/iotrace/iotrace.c`, then captures per-submit BO snapshots.
- `analysis/extract_own_shaders.py`: serializes only pipelines compiled from the committed
  MSL and uses the repository's own public-container parser to extract their code.
- `analysis/analyze.py`: reconstructs the tables in `raw/derived/analysis_summary.txt`.

Every harness has a 150-second process alarm. Every build/compile/run has a 30–180 second
parent-process timeout. A timeout exits 124; the recovery action is to stop that isolated
process and retain its partial output, never to reuse a partially written raw directory.
The capture runner refuses to overwrite an existing raw capture.

## Capture matrix

Authoritative captures:

| directory | one changed factor | submits |
|---|---|---:|
| `raw/run_ab_p0` | baseline, A compiled before B | 8 |
| `raw/run_ba_p0` | compile order only: B before A | 8 |
| `raw/run_ab_p17` | 17 live client BOs allocated first | 8 |
| `raw/run_stage_equal` | VS-only, FS-only, equal-main FS variants; full repeat | 12 |

All 36 authoritative submits completed and matched the expected final A/B or small/large
fragment readback. `raw/run_stage_matrix` and `raw/run_stage_matrix_repeat` are preserved
pilots. They are not used as evidence because the pilot source revision was not hashed
before it was refined; preserving that provenance failure is part of the process record.

The first analysis draft also performed a generic aligned-pointer scan over every BO in
three dumps. Root audit rejected that input scope because it was broader than the explicit
command/state/code BO allowlist, even though the scan did not decode code and produced only
a negative result. The output and its pre-audit hashes are preserved under
`raw/quarantine/`; no conclusion or authoritative analysis consumes it.

The complete map snapshots remain under `raw/run_*/maps/` in this workspace. They total
about 700 MiB and are gitignored. `raw_manifest.sha256` records the relative path, byte
size, and SHA-256 of every retained raw file; `manifest.json` provides aggregate hashes.
The compact stdout, trace logs, own-shader hex, and derived table remain commit-sized.

## Reproduce and verify

Run new append-only captures with unused labels:

```sh
cd experiments/EXP-0042-graphics-code-selection
python3 analysis/capture.py --label repro_ab_p0 --order AB --prealloc 0
python3 analysis/capture.py --label repro_ba_p0 --order BA --prealloc 0
python3 analysis/capture.py --label repro_ab_p17 --order AB --prealloc 17
python3 analysis/capture.py --label repro_stage_equal --matrix
```

Re-extract the authored shader bytes without touching an Apple binary:

```sh
python3 analysis/extract_own_shaders.py --output build/own_shader_repro
```

Reproduce the derived table and verify all retained evidence hashes:

```sh
python3 analysis/analyze.py > build/analysis_summary.repro.txt
cmp build/analysis_summary.repro.txt raw/derived/analysis_summary.txt
python3 analysis/make_manifest.py
shasum -a 256 -c <(awk '{print $1 "  " $3}' raw_manifest.sha256)
```

See `RESULTS.md` for the evidence-qualified verdict. P0.2 and P0.7 remain open: this
experiment materially narrows them but does not provide an end-to-end Linux
`usc_exec_base` test or a complete resource-spec/container writer.

## Clean-room attestation

Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER

Inputs inspected: the MSL and Objective-C source in this directory; code bytes compiled
from that MSL through the public Metal API; IOKit boundary data and BO contents emitted by
our own process; public Mach-O/container structure parsed by our own tool.

Apple binary introspection: NONE

Reproduction: the commands above, all with hard timeouts in the checked-in runners.

Evidence: `raw/`, `raw_manifest.sha256`, `manifest.json`, and
`raw/derived/analysis_summary.txt`. `raw/quarantine/` is process evidence only.

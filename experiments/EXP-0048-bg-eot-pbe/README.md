# EXP-0048: M4 BG/EOT/PBE load-store and format probe

- **Date:** 2026-08-17
- **Gaps:** `AGX_RE_INFORMATION_GAPS.md` P0.4 and P1.1
- **Clean-room categories:** HW-PROBE / DATA-TRACE / OWN-SHADER /
  PUBLIC-hypothesis-only
- **Target:** local Mac16,10, Apple M4 / G16G, macOS 26.6.2 (25G82)
- **Scope:** M4 observation only. This does not validate A18 Pro.

## Why this experiment exists

P0.4 requires userspace background/end-of-tile programs and their tagged
address/resource specification, while P1.1 requires complete PBE state. The
bounded question here is smaller: what can be established about load/clear and
store behavior, per-format LOAD/PBE records, blending, and a fragment atomic by
running authored render workloads and observing only process-boundary state?

The process is as important as the outcome. `PRE_REGISTRATION.md` was frozen at
SHA-256 `872ea37e256cc196d4e62e41a48d77f14eb9303c4fa7cc9509e63298941ffa78`
before the first live run. `CONTROL_PRE_REGISTRATION.md` was frozen at
`588ccdf3a234c790e12311d99bf142d7b476a9663506409bf0bda66117bd35d1`
before two same-draw blend controls. Every raw run has its own pre-run hash
record and rejects an existing output directory.

## Absolute clean-room boundary

This experiment never inspects, scans, disassembles, dereferences, or follows a
pointer into an Apple binary, framework, kernel collection, firmware image,
generated helper program, or auxiliary program. It does not even dump our
compiled shader bytes; the complete generated MSL inputs are retained instead.

`harness/allowtrace.c` has a compile-time allowlist and is incapable of dumping
an unknown BO:

| exact mapping start GPU VA | previously live-correlated role | cap |
| --- | --- | ---: |
| `0x18000` | VDM command/state | `0x10000` |
| `0x58000` | fixed-function render state | `0x10000` |
| `0x68000` | tiling state | `0x10000` |
| `0x10000018200` | MRT attachment descriptors | `0x1000` |

The tracer compares exact allocation-start VAs only. It logs other allocation
metadata but reads none of their bytes. It does not select by contents, inspect
a pointer-like value, or follow any value from an allowed dump. The analyzer
rejects any binary dump name outside the same four-item allowlist and reads only
fixed descriptor offsets or computes bytewise differences within one allowed
state BO.

The public Mesa revision `3c4d3e46d19f2f4e951f3ae059543b03592f7944`
only motivated the falsifiable BG/EOT tagged-address/resource-spec question. No
Mesa bit definition is promoted to an Apple9 fact by this experiment.

## Authored workload

`harness/probe.m` runtime-compiles only the MSL embedded in that source. Every
case uses two buffer-backed 32 x 32 render targets with 256-byte row stride and
fixed initialized bytes. The two attachments force the previously correlated
MRT LOAD array (`+0x20+k*0x20`) and STORE/PBE array
(`+0x220+k*0x20`). The matrix is:

| case family | controlled variable |
| --- | --- |
| RGBA8 Clear/Store draw | baseline |
| RGBA8 Clear/Store empty | background clear of an empty tile |
| RGBA8 Load/Store empty | load and store of initialized bytes |
| RGBA8 DontCare/Store draw | fully covered load-dont-care |
| RGBA8 Clear/StoreDontCare draw | omitted store |
| BGRA8, RGBA8_sRGB, R32Float, R32Uint | target format/type |
| RGBA8 + R32Float | per-attachment mixed format |
| RGBA8 Load/Store blend | destination load plus alpha blend |
| RGBA8 Clear/Store atomic | one fragment atomic per sample |

`harness/blend_control.m` adds a separately pre-registered Load/Store draw with
the exact same authored fragment outputs and blending disabled. It isolates the
blend-state delta without altering the completed primary matrix.

## Raw process and retained failure

`run.py` and `control_run.py` build each authored harness, enforce hard
subprocess timeouts, retain exact generated MSL, stdout/stderr, IOKit map logs,
four state dumps plus per-dump metadata, and per-run SHA-256 inventories.
`raw/preflight_failures.md` preserves both an initially rejected cleanup command
and a compiler-name collision. It also preserves a useful negative baseline:
a small user allocation occupied GPU VA `0x10000018200`, demonstrating that VA
alone is not a role guarantee under arbitrary allocation schedules. The final
harness uses the same 0x4000 allocation class as the earlier MRT correlation;
all formal runs then contain the expected descriptor records at that VA.

No timeout, GPU error, device loss, reboot, or recovery occurred in the formal
runs. All 24 primary cases and both controls completed.

## Reproduction

Use new append-only run IDs:

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0048-bg-eot-pbe
python3 run.py --run-id NEW_M4_RUN_01
python3 run.py --run-id NEW_M4_RUN_02
python3 control_run.py --run-id NEW_BLEND_CONTROL_01
python3 control_run.py --run-id NEW_BLEND_CONTROL_02
python3 analysis/analyze.py \
  --run-a raw/NEW_M4_RUN_01 --run-b raw/NEW_M4_RUN_02 \
  --control-a raw/NEW_BLEND_CONTROL_01 --control-b raw/NEW_BLEND_CONTROL_02 \
  --json analysis/NEW_summary.json --report analysis/NEW_report.txt
python3 make_manifest.py
python3 verify.py
```

The retained repetitions are `raw/m4_20260817_run01`,
`raw/m4_20260817_run02`, `raw/m4_20260817_blend_control01`, and
`raw/m4_20260817_blend_control02`.

## Evidence map

- `PRE_REGISTRATION.md`, `CONTROL_PRE_REGISTRATION.md`: immutable hypotheses,
  falsifiers, boundaries, and control rationale.
- `harness/`: complete authored Metal/MSL harness and fixed allowlist tracer.
- `raw/*/run*.json`: commands, timeout, exit, stdout/stderr, first-pixel bytes,
  full active-area uniformity/FNV checks, and counter result. Full surface bytes
  are checked live by the authored harness but are not retained as raw files.
- `raw/*/source*.metal`: exact authored MSL presented to the compiler.
- `raw/*/trace*.log`: allocation/call metadata; no non-allowlisted contents.
- `raw/*/state_*`: only the four permitted command/state mappings.
- `analysis/summary.json`, `analysis/report.txt`: reproducible derived facts.
- `RESULTS.md`: observations, structural interpretations, and remaining gaps.
- `manifest.json`: experiment metadata and SHA-256 of every retained artifact.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER / PUBLIC-hypothesis-only
Inputs inspected: complete authored MSL; authored RT/counter bytes; IOKit boundary
  metadata; four pre-established command/state BO roles
Apple binary introspection: NONE
Apple auxiliary/helper program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Reproduction: commands above
Evidence: raw/, analysis/, manifest.json
```

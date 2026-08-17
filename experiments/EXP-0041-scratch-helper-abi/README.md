# EXP-0041: M4 scratch/helper ABI boundary probe

- **Date:** 2026-08-17
- **Gap:** `AGX_RE_INFORMATION_GAPS.md` P0.1
- **Target:** local Mac16,10, Apple M4 / G16G, 10-core GPU, macOS 26.6.2
- **Scope qualification:** M4 observations only. This experiment does not validate A18 Pro.

## Question and driver decision

When an authored VS, FS, or CS crosses from no scratch to a nonzero per-thread
scratch requirement, what changes at the live hardware/process boundary? In
particular, can a controlled differential locate a userspace scratch BO, helper
program record (`binary`, `cfg`, `data`), helper input/output, scratch geometry,
or a special-register/doorbell protocol without inspecting Apple software?

The driver decision is whether the existing `drm_asahi_helper_program` fields
and userspace scratch allocator can be populated from established Apple9 facts.
A negative result is load-bearing: it prevents guessing that macOS's private
path is equivalent to the unchanged Linux UAPI.

## Pre-registered hypotheses and falsifiers

1. **H1: spill-correlated boundary record.** A no-spill/spill minimal pair will
   change a command/state record or add/grow a mapped BO. It is falsified over a
   tested pair if compiled metadata proves scratch changes while the ordered
   mapping sequence and allowlisted command/state bytes do not.
2. **H2: stage-specific helper state.** CS, VS, and FS spill will alter distinct
   state. It is falsified for an inspected state BO if that BO is byte-identical
   between a proven no-spill/spill pair.
3. **H3: lazy scratch growth.** A small dispatch may fit preallocated backing;
   65,536 spilling threads or a 256-thread threadgroup will force an allocation
   difference. It is falsified at the boundary if an equal-user-allocation
   no-spill control and the spilling cases have identical ordered resource-map
   sequences.
4. **H4: exact `60 00 00 00` main-program marker is universal for compiler
   spill.** It is falsified by any `_agc.main` whose own metadata reports
   nonzero scratch but whose exact authored-code capture lacks the word.

Public Mesa at pinned revision `3c4d3e46d19f2f4e951f3ae059543b03592f7944`
was used only to shape falsifiable questions: address shift 8, groups of 32,
8-dword spill units, per-core headers/block lists, up to four mapped blocks, and
doorbell numbers 32/48/49 are **PUBLIC hypotheses, not Apple9 facts**. This
experiment does not promote any of those values.

## Authored probes

`kernels/generate.py` retains nine complete MSL inputs:

| case | stage under pressure | observed GPRs | observed scratch bytes |
|---|---|---:|---:|
| `cs_nospill_k72` | CS | 76 | 0 |
| `cs_spill_k80` | CS | 84 | **0** |
| `cs_spill_k96` | CS | 96 | 208 |
| `cs_spill_k112` | CS | 95 | 352 |
| `cs_spill_k160` | CS | 94 | 576 |
| `vs_nospill_k72` | VS | 77 | 0 |
| `vs_spill_k112` | VS | 96 | 352 |
| `fs_nospill_k72` | FS | 75 | 0 |
| `fs_spill_k112` | FS | 96 | 336 |

The name `cs_spill_k80` records the pre-run hypothesis. Metadata falsified the
name: this source did **not** spill on this compiler/target. It is intentionally
preserved rather than renamed after seeing the result.

`harness/probe.m` compiles those exact sources through the public Metal API,
runs them on the GPU, waits for completion, and checks finite compute output or
a render-target checksum. `harness/metadata.py` serializes only our pipeline,
reads only its own `__GPU_METADATA`, and optionally retains only the
`_agc.main` symbol compiled from our source.

`harness/maptrace.c` records IOKit boundary metadata and selector-9 resource-map
geometry. It reads no mapped BO by default. Its explicit allowlist contains only
BO roles already established by clean experiments EXP-0011, EXP-0014, and
EXP-M4-03: `0x18000`, `0x58000`, `0x68000`, and `0x100000b0000`. It never
follows any value found in them. No target program BO, helper program, firmware,
framework, dylib, kext, or system shader cache is opened or inspected.

## Reproduction

Every subprocess has a hard timeout (20–100 seconds). Run IDs are append-only;
an existing raw directory is rejected.

```sh
cd /Users/user/asahi_re/public/agx-re
python3 experiments/EXP-0041-scratch-helper-abi/run.py --run-id NEW_PRIMARY_RUN
python3 experiments/EXP-0041-scratch-helper-abi/capture_owned_code.py \
  --run-dir experiments/EXP-0041-scratch-helper-abi/raw/NEW_PRIMARY_RUN
python3 experiments/EXP-0041-scratch-helper-abi/analysis/analyze.py \
  --run-dir experiments/EXP-0041-scratch-helper-abi/raw/NEW_PRIMARY_RUN

python3 experiments/EXP-0041-scratch-helper-abi/scale_run.py --run-id NEW_SCALE_RUN
python3 experiments/EXP-0041-scratch-helper-abi/scale_controlled_run.py \
  --run-id NEW_CONTROLLED_SCALE_RUN
```

The two complete retained repetitions are `m4_20260817_run01` and
`m4_20260817_run02`. `analysis/m4_20260817_repeatability.txt` compares their
semantic observations and raw command BOs. `m4_20260817_scale_control01` is the
equal-40-MiB-user-buffer high-occupancy control.

If a GPU fault or timeout occurs, stop the sweep, retain the failing log, and
reboot the Mac if command submission does not recover. No fault, timeout, or
reboot occurred in the retained live runs. Preflight tooling/parser failures
and their recovery are retained in `raw/preflight_failures.txt`.

## Evidence layout

- `raw/m4_20260817_run{01,02}/`: full build, metadata, IOKit mapping, run logs,
  and narrowly allowlisted command/state hex.
- `raw/m4_20260817_run01/code_*/`: only `_agc.main` compiled from the matching
  complete source in `kernels/`; no Apple-authored helper code.
- `raw/m4_20260817_scale*`: scaling and equal-allocation raw logs.
- `analysis/*.txt`: repeatable derived comparisons; `analysis/*.py`: derivation.
- `manifest.json`: target/tool/revision metadata plus hashes of every artifact.

See `RESULTS.md` for observations, interpretations, limitations, and verdict.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER / PUBLIC-hypothesis-only
Inputs inspected: complete authored MSL in kernels/; its own metadata and _agc.main;
  IOKit resource-map metadata; allowlisted command/state BO data
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE
Reproduction: commands above
Evidence: raw/, analysis/, and hashes in manifest.json
```

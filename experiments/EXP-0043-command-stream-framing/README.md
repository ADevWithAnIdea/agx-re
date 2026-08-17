# EXP-0043: Apple9 command-stream framing and repetition

## Question and driver relevance

What record boundaries, length rules, legal ordering, termination, chaining,
relocation behavior, and repeated-record behavior are visible when an authored
Metal process emits multiple compute and graphics commands on Apple M4?

This experiment addresses the command-framing portion of
`AGX_RE_INFORMATION_GAPS.md` P0.3 and P0.5. It is deliberately narrower than a
complete VDM/CDM/PPP/USC schema: it tests stream construction under repetition,
pipeline/state changes, encoder/pass boundaries, allocation movement, mixed
compute/render order, multiple queues, and segment pressure.

Primary project target is A18 Pro/G17P. This run is local M4 only because the
A18 Pro host is unavailable. An M4 observation is never promoted here to an A18
fact; possible transfer is labelled `INFERRED`.

## Pre-registered hypotheses

These hypotheses were written before the first DATA-TRACE capture.

1. A same-encoder compute sequence produces one fixed-size CDM launch record per
   authored dispatch, in API order, followed by a stable terminating record.
   Two different authored pipelines should alter per-record shader selection but
   not record length.
2. A same-pass graphics sequence produces one VDM draw record per authored draw,
   in API order. Alternating vertex counts 3/6 should occur in that order, while
   alternating pipeline, fragment constants, and viewport state should introduce
   state records without changing the draw packet's count fields.
3. Ending/restarting a compute encoder or render pass changes framing and/or
   state emission around otherwise equivalent command records. It must not
   reorder the authored dispatches/draws.
4. Padding allocations move some resource or shader VAs. Fields that track moved
   VAs are relocation candidates; packet opcodes, lengths, and literal workload
   dimensions/counts should stay structurally stable.
5. A long stream that exceeds a small control segment exposes either a link/
   chain record, a second control BO/segment, a larger allocation, or an explicit
   rejection. A single fixed template cannot silently contain an unbounded list.
6. `compute-render` and `render-compute` in one command buffer preserve the public
   encoder order. If engine streams are stored separately, an outer control/state
   structure must still distinguish the two orderings.
7. Separate queues have distinct queue/control context but reuse the same
   hardware packet grammars.

## Falsifiers

- The number/order of CDM candidates does not track authored dispatches, or the
  six exact `(grid,tg)=(64,1,1;32,1,1)` fields are absent.
- VDM draw candidates do not reproduce the authored `3,6,3,6...` vertex-count
  sequence or are missing under pipeline/state changes.
- A supposedly fixed-size repeated record changes stride without an identified
  state/encoder boundary.
- Padding changes supposedly literal opcode/dimension/count fields, or a claimed
  relocation does not track a captured BO window.
- Long streams fit only by truncating commands (readback/status failure), or no
  retained capture distinguishes allocation growth from links/chaining.
- Mixed-order captures are byte-identical across all non-output control/state
  data despite successful, order-sensitive execution.

## Controlled variables and confounders

- All dispatches use 64 threads and 32 threads/threadgroup. Each dispatch writes
  a sequence/pipeline-dependent value to a shared output buffer.
- All draws use one buffer-backed 64x64 BGRA8 target. Vertex counts alternate 3/6,
  fragment constants are asymmetric, and the two pipelines contain different
  authored fragment functions.
- `--pad` creates authored shared buffers before pipeline/resource setup.
- Pipeline compilation, allocator behavior, macOS private bookkeeping, firmware
  rewriting, separate engine streams, and snapshot timing can all create changes
  unrelated to hardware packet semantics.
- Address-stable cross-process captures can prove layout correlation but cannot
  alone prove a field is hardware-consumed.
- Captures may contain runtime auxiliary programs not authored by this project.
  They are retained as raw boundary data but are **not inspected, decoded,
  disassembled, scanned, or used as evidence**. Analysis is restricted to
  command/state/descriptor bytes and our exact authored shader inputs.

## Authored probe matrix

| Label | Workload |
|---|---|
| `compute_1`, `_2`, `_8` | 1/2/8 dispatches in one compute encoder |
| `compute_split_2` | two dispatches in separate encoders, one command buffer |
| `compute_pad_2` | two dispatches after seven padding allocations |
| `compute_1024` | long compute stream / segment-pressure case |
| `render_1`, `_2`, `_8` | 1/2/8 draws in one render pass |
| `render_split_2` | two render passes in one command buffer |
| `render_pad_2` | two draws after seven padding allocations |
| `render_384` | long graphics stream / segment-pressure case |
| `compute_render_2` | alternating compute then render encoders |
| `render_compute_2` | alternating render then compute encoders |
| `two_queues_2` | compute on queue 0 and render on queue 1 |
| `repeat_compute_3` | same two-dispatch workload, three command buffers/snapshots |

## Reproduction

From this directory on an Apple M4 Mac with Xcode command-line tools:

```sh
./run.sh
```

Every compiler invocation and GPU process is wrapped by
`analysis/hard_timeout.py`. The script is append-only: it creates a new
`raw/runs/<UTC timestamp>/` and refuses to overwrite an existing run. Set a
stable identifier when desired:

```sh
RUN_ID=reproduction-01 ./run.sh
```

Inspect or regenerate structural reports:

```sh
python3 analysis/safe_framing.py --kind cdm \
  raw/runs/RUN/cases/compute_2/dumps/dump00/bo_*_va100000b8000_*.hex
python3 analysis/safe_framing.py --kind vdm \
  raw/runs/RUN/cases/render_2/dumps/dump00/bo_*_va18000_*.hex
python3 analysis/safe_fields.py \
  raw/runs/RUN/cases/compute_2/dumps/dump00/bo_*_va100000e8000_*.hex \
  --u64 0x14a0 0x14c0
```

The analyzer inputs are explicit, pre-classified command/state/descriptor BO
files. Never pass an unclassified BO. The safe tools do not accept a dump
directory and never follow an encoded pointer. See `QUARANTINE.md` for the
preserved and excluded first-generation generic reports.

Run the exact rollover falsification matrix with:

```sh
RUN_ID=reproduction-boundaries ./run-boundaries.sh
```

## Evidence policy

Raw trace logs, full BO/map snapshots, stdout, stderr, exit status, build logs,
sanitized target identity, derived reports, and SHA-256 hashes are retained.
Failures and timeouts are results and are not deleted. Snapshot completeness is
reported per BO by checking `size == read == parsed_bytes`.

The 273 MiB `raw/runs/*/cases/*/dumps/` trees remain append-only in this
workspace and are intentionally gitignored. `manifest.json` records every
retained file's relative path, byte size, and SHA-256. Commit-sized trace logs,
commands, readbacks, clean derived reports, exact authored source, and the
quarantine record are checked in.

`analysis/verify_clean_evidence.py` checks that every artifact on the evidence
allowlist is present in `manifest.json` and that neither the allowlist nor this
experiment's conclusions depend on a quarantined generic scan. It additionally
rejects any allowlisted BO snapshot whose filename is not one of the eight
explicitly correlated command/state/resource VAs used by this experiment.

No conclusion from this experiment alone closes all of P0.3 or P0.5. Hardware
versus macOS-private classification requires independent mutation/replay or a
Linux producer/consumer test. A18 transfer requires a fresh G17P run.

## Clean-room attestation

```text
Clean-room provenance: DATA-TRACE / OWN-SHADER / HW-PROBE
Inputs inspected: harness/framing.m; IOKit boundary payloads and mapped BO data
                  emitted by that authored process; public Metal API status and readback
Apple binary introspection: NONE
Reproduction: ./run.sh
Evidence: raw/runs/<run-id>/ and manifest.json (SHA-256)
```

No Apple executable, dylib, framework, driver, kext, firmware, system shader
cache, or Apple-authored code was disassembled or otherwise introspected.

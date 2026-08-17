# EXP-0051: M4 synchronization litmus

- **Date:** 2026-08-17
- **Gap:** `AGX_RE_INFORMATION_GAPS.md` P1.4
- **Target:** local Mac16,10, Apple M4 / G16G, macOS 26.6.2 (25G82)
- **Clean-room categories:** HW-PROBE / OWN-SHADER
- **Qualification:** M4 Metal-path observation only; no A18 Pro validation

## Question

Which synchronization relationships can be observed through authored MSL and
public Metal command submission on this M4, and which remain unestablished for
native Apple9 instructions, Linux UAPI barriers, or Vulkan/GL correctness?

The experiment separates six levels that are easy to conflate:

1. threadgroup execution barriers and memory-class flags;
2. MSL atomic/fence language exposure;
3. same- and cross-threadgroup publication behavior;
4. dispatch and compute-encoder boundaries;
5. command-buffer, queue, and shared-event order; and
6. shared-storage CPU/GPU visibility at completion boundaries.

## Process and pre-registration

The process is part of the result. `PRE_REGISTRATION.md` was frozen before the
first EXP-0051 source compilation or hardware execution at SHA-256
`941eb45f744f6a08b19037cfd147810954fb7365466355f50e1ad652da0d2cec`.
It defines competing explanations and prevents a passing racy control from
being promoted to a memory-model guarantee.

Each append-only run records, before building:

- the frozen pre-registration hash;
- exact SHA-256 of the runner, main MSL, five isolated compile-probe sources,
  and run script;
- target/OS/compiler environment and clean-room declaration; and
- after building, exact runner-binary size and SHA-256.

Both retained runs used byte-identical authored inputs and the same 70,392-byte
runner (`839fb7ae55cce23b7768e016cfd58a2e07c59f4fa4385013678c9ed675ba4f2e`).

## Absolute clean-room boundary

This experiment invokes the documented Metal API as a black box and inspects
only source authored here, compilation acceptance/diagnostics returned for that
source, command completion, and bytes in buffers allocated by the harness.

It does not trace or dump a command buffer or BO, scan memory, follow pointers,
or inspect compiled shader bytes. It never opens, scans, disassembles, extracts
symbols from, or otherwise introspects an Apple binary, framework
implementation, compiler executable, firmware, helper, or auxiliary program.
Compiler diagnostics are retained exactly as public-API outputs; no path named
by a diagnostic was opened or inspected.

## Authored probes

`kernels/litmus.metal` contains:

- threadgroup and simdgroup barrier cases over threadgroup or device memory;
- bounded producer/consumer mailboxes with four asymmetric payload words and
  separate atomic ready/ack counters;
- relaxed publication and seq-cst device-fence variants at threadgroup and
  cross-threadgroup topology; and
- producer/consumer kernels used by encoder, queue, and CPU tests.

`kernels/compile_probes/` isolates relaxed RMW, acquire-release RMW,
acquire-load/release-store, seq-cst device fence, and release device fence.
Compile rejection is retained as evidence instead of silently deleting the
case. An accepted probe must also create a pipeline and run two live threads.

`harness/litmus.m` runs the fixed matrix:

- 1,024 workgroups × 64 threads for each barrier case;
- 64 same-threadgroup mailboxes × 256 messages and 8,192 messages across two
  distinct threadgroups;
- 4,096 asymmetric words × 128 epochs for each encoder/queue/CPU case; and
- 1,000,000-spin bounds on every GPU wait loop.

The host runner has a 180-second hard timeout. It records all command errors and
continues through result mismatches where safe. No formal run timed out, faulted,
or required recovery.

## Reproduction

Use fresh append-only IDs:

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0051-m4-synchronization-litmus
python3 run.py --run-id NEW_M4_SYNC_RUN_01
python3 run.py --run-id NEW_M4_SYNC_RUN_02
python3 analysis/analyze.py \
  --run-a raw/NEW_M4_SYNC_RUN_01 --run-b raw/NEW_M4_SYNC_RUN_02 \
  --json analysis/NEW_summary.json --report analysis/NEW_report.txt
python3 make_manifest.py
python3 verify.py
```

The retained runs are `raw/m4_20260817_run01` and
`raw/m4_20260817_run02`. Defaults analyze those two runs.

## Evidence map

- `PRE_REGISTRATION.md`: frozen hypotheses, falsifiers, scopes, and safety.
- `kernels/`: complete authored MSL, including rejected sources.
- `harness/litmus.m`: complete authored public-API runner.
- `raw/*/00_preflight.json`: exact source/runner hashes before hardware.
- `raw/*/04_build.json`, `05_runner_hash.json`: exact build output and binary
  identity.
- `raw/*/06_suite.json`: complete live stdout/stderr, compile rejections,
  counters, sentinels, and command status.
- `raw/*/SHA256SUMS`: per-run immutable evidence inventory.
- `analysis/summary.json`, `analysis/report.txt`: repeatable semantic reduction.
- `RESULTS.md`: observations, interpretations, and explicit remaining gaps.
- `manifest.json`: SHA-256 of every committed evidence artifact. Rebuildable
  authored runner binaries remain ignored under `work/`; their exact size and
  SHA-256 are retained in each raw run.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: complete authored MSL and runner; public-API compile diagnostics;
  live completion status and bytes from buffers owned by the authored process
Apple binary introspection: NONE
Apple auxiliary/helper code inspection: NONE
Command/BO scan or pointer following: NONE
Compiled shader bytes inspected: NONE
Reproduction: commands above
Evidence: PRE_REGISTRATION.md, raw/, analysis/, manifest.json
```

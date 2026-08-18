# EXP-0050: M4 fragment-output compiler ABI

> **QUARANTINED — NOT EVIDENCE.** The v1 runs and derived claims below are
> retained as process-failure history only. The v1 extractor selected the
> fragment result only after materializing other stage and constant-program
> regions, contrary to its clean-room attestation. Nothing under `raw/`, the v1
> `analysis/`, `RESULTS.md`, or `manifest.json` may be cited as hardware
> evidence. See `QUARANTINE.md`. No clean-v2 pre-registration exists: the draft
> locator cannot prove the exact `_agc.main` extent. Only a future independently
> audited, Git-anchored method and new runs may restore evidence status.

## Historical v1 narrative — quarantined and not normative

Everything below is preserved v1 process history. Present-tense claims and
clean-room attestations below were written before the violation was found and
are false as evidence statements; `QUARANTINE.md` supersedes them.

- **Date:** 2026-08-17
- **Gap:** `AGX_RE_INFORMATION_GAPS.md` P0.8
- **Target:** local Mac16,10, Apple M4 / G16G, macOS 26.6.2 (25G82)
- **Evidence:** HW-PROBE / OWN-SHADER-DIFF / one bounded HW splice
- **Scope:** M4 only. No A18 Pro or complete fragment-ABI claim.

## Question and process

This experiment asks how compiler-emitted fragment `_agc.main` and live authored
readbacks change across asymmetric MRT indices/order, shader depth, sample-mask,
discard, and device-atomic side effects. The process is part of the result:
`PRE_REGISTRATION.md` was frozen at SHA-256
`99cd47d7c75687c1ce816826c57507b73a9d827f0deed56243a1122d2959748f`
before either hardware run. It specifies the matrix, competing expectations,
falsifiers, the only permitted splice, and stop conditions.

The complete executable MSL is `kernels/output_matrix.metal`. The authored
`harness/render_probe.m` compiles it with fast math disabled, builds a selected
render pipeline, serializes that own pipeline to a temporary binary archive,
reloads the archive, and forces pipeline creation with
`MTLPipelineOptionFailOnBinaryArchiveMiss`. It then draws four pixels and emits
the complete color/depth readback bytes and counter value.

`run.py` applies hard timeouts, preserves every subprocess record, uses the
repository-authored `tools/shdump/agxparse.py` to extract only the fragment
`_agc.main` attributable to our selected source function, and retains its exact
hex, size, and SHA-256. Every normal case starts in a fresh process/archive. The
entire matrix is repeated in a second append-only directory.

## Strict clean-room boundary

No Apple binary, framework code, compiler code, system cache, firmware, helper,
auxiliary program, command/state BO, or unknown BO was inspected. No compiled
constant program was inspected. Only the complete authored MSL, its exact
fragment `_agc.main`, authored target/counter readbacks, and public process/tool
identity were read.

Temporary archives contain only the selected own pipeline but remain ignored in
`work/`; they are not committed because only the precisely attributed own main
is needed. Each normalized case records the archive size, SHA-256, and local work
path. Its historical `archive_retained=false` field means “not retained in the
committable raw evidence”; ignored local work copies may still exist.

The single splice is narrowly pre-registered. It runs only if intact
`mrt3-decl012` contains exactly one known fragment color-store signature with
selector byte `0x02`. The runner changes only that byte to `0x04`, records the
one-byte diff and both archive hashes, then forces the mutated own archive with a
60-second timeout. All three destination attachments are valid.

## Matrix

The 21 intact cases cover:

- isolated `[[color(0)]]`, `[[color(1)]]`, and `[[color(2)]]`;
- sparse RT0+RT2 and contiguous RT0/1/2 with reversed declaration orders;
- asymmetric value routing between RT1 and RT2;
- color+depth in both declaration orders, depth-only, and fixed-depth control;
- four-sample masks `0xf`, `0x5`, `0xa`, zero, and a mask-first declaration;
- half-screen discard;
- atomic increment without discard, before discard, and after discard.

The checked splice is the 22nd execution per run. Exact values, hypotheses, and
falsifiers are in the frozen pre-registration; outcomes are in `RESULTS.md`.

## Reproduction

Use new append-only run IDs; never overwrite the retained runs:

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0050-fragment-output-abi
python3 run.py --run-id NEW_M4_RUN_01
python3 run.py --run-id NEW_M4_RUN_02
python3 analysis/analyze.py \
  --json analysis/NEW_summary.json --report analysis/NEW_report.txt
python3 make_manifest.py
python3 verify.py
```

The retained runs are `raw/m4_20260817_run01` and
`raw/m4_20260817_run02`. Each contains complete command/stdout/stderr records,
the exact MSL input, exact own-main hex, normalized full readbacks, failures,
mutation metadata, environment/tool identity, and a complete `SHA256SUMS`.

## Evidence map

- `PRE_REGISTRATION.md`: immutable questions, matrix, hypotheses, falsifiers.
- `kernels/output_matrix.metal`: complete authored shader source.
- `harness/render_probe.m`, `run.py`: authored compile/archive/render runner.
- `raw/*/run_*.json`: exact subprocess commands, timeouts, output, and errors.
- `raw/*/own_*.fragment.main.hex`: exact permitted own fragment mains.
- `raw/*/case_*.json`: normalized main hashes and complete readbacks.
- `raw/*/mutation_*.json`: guarded one-byte splice record.
- `analysis/summary.json`, `analysis/report.txt`: reproducible observations.
- `RESULTS.md`: observation/interpretation split and remaining gap.
- `manifest.json`: target, revisions, policy, and complete artifact hashes.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER-DIFF / bounded HW splice
Inputs inspected: kernels/output_matrix.metal; exact selected fragment _agc.main;
  authored color/depth/counter readbacks; public target/tool identity
Apple binary introspection: NONE
Apple auxiliary/helper program inspection: NONE
Unknown BO inspection: NONE
Command/state BO inspection: NONE
Compiled constant-program inspection: NONE
Reproduction: commands above
Evidence: raw/, analysis/, manifest.json
```

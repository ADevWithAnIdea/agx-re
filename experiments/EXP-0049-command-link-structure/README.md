# EXP-0049: M4 command-link structural controls

- **Date:** 2026-08-17
- **Gap:** `AGX_RE_INFORMATION_GAPS.md` P0.5
- **Target:** local Apple M4 / G16G, macOS 26.6.2 (25G82)
- **Scope:** public-API authored workloads and fixed command-BO allowlist only;
  structural observations, no mutation/replay, and no A18 Pro claim

## Question

EXP-0043 observed direct CDM and VDM first-segment rollover links. This
experiment tests whether the first known boundary/link changes with indirect
compute shape, compute encoder restarts, graphics state frequency, render-pass
boundaries, and controlled client allocation padding.

The process is part of the result. A changed-shape stream that leaves the exact
EXP-0043 allowlist is reported as a bounded unknown; the experiment never finds
a new target by scanning or pointer following.

## Frozen plans

`PRE_REGISTRATION.md` was frozen before the first build or live run at SHA-256:

```text
217063a4dad9831ece3d4fe974876d9d50b4216451c3cd281ae284382f3bc808
```

The main fixed-upper-bound runs exposed a pre-registered stop: three altered
shapes allocated the known second BO but did not contain the exact EXP-0043
source-link pair. Before further hardware work,
`REFINEMENT_PRE_REGISTRATION.md` froze a below-to-above approach at:

```text
e8e41a3989f1b18c015cc5a55dbf60ca64376d89a9510f4922f03355e9b8a4f1
```

The two main and two refinement runs are all retained. None was overwritten.

## Exact clean-room allowlist

`harness/allowtrace.c` can remember or read only allocations whose starting GPU
VA exactly matches:

| GPU VA | Preclassified EXP-0043 role | Cap |
| --- | --- | ---: |
| `0x100000b8000` | CDM segment 0 | `0x10000` |
| `0x10000158000` | CDM segment 1 | `0x10000` |
| `0x18000` | VDM segment 0 | `0x10000` |
| `0x88000` | VDM segment 1 | `0x10000` |

Other allocation metadata is logged, but the tracer never retains a CPU
mapping for it and cannot read its bytes. The analyzer rejects every filename
outside this set and verifies the embedded fixed-allowlist, no-pointer-follow,
and no-mutation metadata before reading an allowed payload.

The second segment is independently allowlisted. It is not opened by decoding
or following a value from the first. The only link sequences matched are the
two exact pairs already observed by EXP-0043.

### Exact prior-classification provenance

The four roles and the two comparison pairs come specifically from
`EXP-0043-command-stream-framing` artifact commit
`94bd70083678469867500ba87a22074dde79983e`. That experiment's manifest records
`45854670843e0f35573afc0546995826547cab94` as its pre-artifact base revision;
the two roles must not be conflated. The evidence is anchored by its manifest
(SHA-256 `f801b0f516c227fca5e3baa1c588df42dcf1b40f30b091d7aa982a01c0007e88`)
and these non-quarantined clean-analysis records:

- `compute_732-cdm.txt` — `ae174d3d772968a9187cbc34b89134eab847fb4364e421037d07c045a69bc727`;
- `compute_733-cdm-segment0.txt` — `2bdcc4bbc1589ddcabed1fcf58505334e93d0d3887f016dca131e5ace9c19faf`;
- `compute_733-cdm-segment1.txt` — `f053469de6efecb6462daf93d54c9366d591e89c72d5cfbc1125cd5475af6327`;
- `render_328-vdm.txt` — `9cc5a078c639b6b5c563b21dff5b36aee2c8a2850b7ab72e6223f93ced46a7ef`;
- `render_329-vdm-segment0.txt` — `f2df1a69be6ae521e231ac21348da865af3fcb3541717bd7505be0b629690354`;
- `render_329-vdm-segment1.txt` — `dbc065dcf9346cafb81396b8ca9addf2cbff2bd2da04590a4b115d922003f075`.

All six live under
`experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/`.
EXP-0049 never opens EXP-0043 payloads; these text records and their manifest
hashes are the provenance bridge for the fixed allowlist.

## Authored probe and safety

- `harness/probe.m` contains every MSL source used by the eight workload
  variants and validates the final compute words or render pixel itself.
- `harness/allowtrace.c` is the fixed DATA-TRACE interposer.
- `run.py` performs the frozen main searches; `refine.py` performs the later
  frozen approach-from-below controls.
- Every build has a 60-second timeout and every fresh GPU process has a
  45-second timeout.
- All snapshots happen after public Metal completion and readback.
- No command byte is changed and no captured stream is replayed.

The formal run trees contain 226 successful authored GPU processes. Expected
strict-analysis stops are retained in `failures.json`; they are not GPU errors.
There were no GPU errors, process timeouts, device losses, or reboots.

The raw runs retain exact authored source hashes plus every build and process
command. They did not record the built interposer/probe binaries' sizes or
SHA-256 values. Those rebuildable products remain ignored under `work/`; no
after-the-fact binary identity is inferred. This limits executable provenance
to the frozen source hashes, successful build records, exact invocation paths,
and live output retained in raw.

## Reproduction

Use new append-only IDs:

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0049-command-link-structure
python3 run.py --run-id NEW_MAIN_01
python3 run.py --run-id NEW_MAIN_02
python3 refine.py --run-id NEW_REFINE_01
python3 refine.py --run-id NEW_REFINE_02
python3 analysis/summarize.py \
  --json analysis/NEW_summary.json --report analysis/NEW_report.txt
python3 make_manifest.py
python3 verify.py
```

The retained `run.py` and `refine.py` invocations intentionally return status 1
because the changed-shape variants hit their frozen strict-analysis stop
conditions. Inspect their `failures.json`; the individual authored GPU
processes still exit zero and pass readback, as checked by `verify.py`.

The retained runs are:

- `raw/m4-20260817-run01`
- `raw/m4-20260817-run02`
- `raw/m4-20260817-refine01`
- `raw/m4-20260817-refine02`

Each raw run has a complete `SHA256SUMS`, input hashes captured before its first
build/hardware operation, per-trial commands/stdout/stderr/timeouts, trace
metadata, allowed BO metadata/payloads, derived trial records where permitted,
summary, and preserved stop records.

## Evidence map

- `PRE_REGISTRATION.md`, `REFINEMENT_PRE_REGISTRATION.md`: frozen hypotheses,
  falsifiers, algorithms, and stop rules.
- `harness/`, `run.py`, `refine.py`: authored execution/capture sources.
- `raw/`: immutable full process evidence and failures.
- `analysis/analyze_trial.py`: exact-VA per-trial analyzer.
- `analysis/summarize.py`: four-run aggregation.
- `analysis/summary.json`, `analysis/report.txt`: reproducible conclusions.
- `RESULTS.md`: observations, interpretation, and limitations.
- `manifest.json`, `verify.py`: complete artifact integrity and clean-boundary
  checks, including globally exact allowed `.bin`/`.meta` placement, raw-summary
  reconciliation to individual trials, and the exact EXP-0043 provenance bridge.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: complete authored MSL; authored input/output buffers; public
  Metal status/readback; four exact EXP-0043-preclassified command BO mappings
Apple binary introspection: NONE
Apple auxiliary/helper program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Executing command-memory mutation or replay: NONE
Reproduction: commands above
Evidence: raw/, analysis/, manifest.json
```

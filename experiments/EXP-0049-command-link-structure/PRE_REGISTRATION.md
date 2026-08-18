# EXP-0049 pre-registration: M4 command-link structure

Date: 2026-08-17

Target: local Apple M4 / G16G only. No result from this experiment is an
Apple A18 Pro / G17P fact.

This file is frozen before the first build or live-hardware run. It defines the
question, variants, falsifiers, capture allowlist, search algorithm, and stop
conditions. Later results must not edit it.

## Question and bounded purpose

EXP-0043 observed first-segment rollover links for one direct CDM record shape
and one alternating VDM state shape. This experiment asks how the first observed
rollover threshold, link offset, and link destination correlate with:

1. direct versus indirect compute dispatch record shape;
2. compute encoder boundaries;
3. graphics state-change frequency;
4. render-pass boundaries; and
5. controlled client allocation padding.

Only structural correlation is in scope. This experiment does not alter command
memory, construct a command packet, replay a captured stream, or claim that an
observed link is hardware-consumed.

## Absolute clean-room boundary

Allowed inputs are public Metal APIs, complete MSL authored in this experiment,
authored input/output buffers, public command completion/readback, IOKit boundary
allocation metadata, and four exact command BO mapping starts already classified
by EXP-0043 on this same local M4 workload family.

The only mappings whose bytes may be captured or analyzed are:

| Exact allocation-start GPU VA | EXP-0043 role | Maximum read |
| --- | --- | ---: |
| `0x100000b8000` | first CDM command segment | `0x10000` |
| `0x10000158000` | second CDM command segment | `0x10000` |
| `0x18000` | first VDM command segment | `0x10000` |
| `0x88000` | second VDM command segment | `0x10000` |

The tracer must compare exact allocation-start VAs and must be incapable of
dumping any other mapping. Non-allowlisted allocation metadata may be logged,
but none of its bytes may be read. The analyzer must accept only exact filenames
and metadata for these four VAs. It may compare the two exact link-word pairs
already observed by EXP-0043:

- CDM: `0x20000100 0x00158000`;
- VDM: `0x80000000 0x00088000`.

The second segment is independently allowlisted; it is never opened by decoding
or following the link value. No pointer-like value is dereferenced or followed.

Forbidden: Apple binaries, frameworks, executable sections, kernel/firmware
images, runtime auxiliary/helper programs, shader code BOs, compiled shader
bytes, generic BO scans, non-allowlisted payloads, or any mutation of executing
command memory. No Apple code may be disassembled, decompiled, strings-scanned,
debugged, traced, or otherwise introspected.

## Authored variants

All compute variants dispatch an authored kernel whose final write contains the
last sequence tag. All render variants draw an oversized triangle into an
authored 64 x 64 buffer-backed BGRA8 target and retain a final pixel/FNV readback.
The harness creates the same compute and graphics pipelines and core resources
for every process before command encoding.

| Variant | Independent variable |
| --- | --- |
| `cdm-direct` | direct `dispatchThreads`, stable pipeline, one encoder |
| `cdm-indirect` | authored indirect threadgroup arguments, pipeline changes every dispatch |
| `cdm-encoder1` | direct dispatch, end/restart compute encoder after every dispatch |
| `cdm-pad7` | `cdm-direct` plus seven authored `0x3000` client allocations |
| `vdm-state1` | one pass; pipeline/color/viewport state submitted every draw |
| `vdm-stable` | one pass; stable pipeline/color/viewport state submitted only at pass start |
| `vdm-pass1` | one draw per render pass; later passes load the authored target |
| `vdm-pad7` | `vdm-state1` plus seven authored `0x3000` client allocations |

Direct draw vertex counts alternate 3 and 6 so retained state can be tied to
the authored API order. The vertex shader intentionally maps `vertex_id % 3`,
making both counts valid with the same three authored positions.

## Hypotheses and falsifiers

H1: `cdm-direct` reproduces EXP-0043's 732/733 first rollover boundary and
exact known CDM link words/destination.

- Support: 732 has no second CDM segment and 733 has the exact link plus a
  separately captured `0x10000158000` segment, with both readbacks correct.
- Falsifier: different boundary, missing/changed link words, missing known
  target, failed readback, or run-to-run disagreement.

H2: indirect dispatch changes the command-record shape and may therefore change
the first rollover threshold or link offset, while retaining the same known
link destination if the command-pool layout is unchanged.

- Support: a repeatable threshold/offset difference with correct final output.
- Falsifier: no structural change, an unrecognized target, or unsuccessful
  output. No difference is a valid negative result.

H3: compute encoder restart after every dispatch is either coalesced like the
two-dispatch EXP-0043 case or introduces repeatable framing overhead.

- Support for coalescing: same threshold and link offset as `cdm-direct`.
- Support for overhead: lower repeatable threshold or different link offset.
- Falsifier: inconsistent results or failed workload.

H4: reducing graphics state submission from every draw to pass-start-only
increases first-segment draw capacity; one-pass-per-draw decreases it.

- Support: repeatable thresholds ordered `vdm-stable > vdm-state1 > vdm-pass1`.
- Falsifier: any different ordering. The observation remains structural even if
  supported.

H5: seven `0x3000` authored client allocations do not change the fixed command
pool link destinations observed in EXP-0043. They may change unrelated resource
addresses, which are out of this experiment's byte-analysis scope.

- Support: padded and unpadded variants use identical known link words/targets.
- Falsifier: changed/unrecognized link words, absent known target, or different
  threshold. On falsification, do not locate or inspect any new target.

## Boundary-search algorithm and repetitions

For each variant, the runner uses fresh processes and append-only case
directories:

1. confirm count 1 has no known second segment;
2. use a fixed upper bound of 2048 commands for CDM and 4096 draws for VDM;
3. require the upper bound to contain the exact known link words and separately
   captured known target segment;
4. binary-search the first count satisfying that condition;
5. run the discovered `threshold-1` and `threshold` cases again in fresh
   processes as the second boundary repetition.

Every trial is retained. Monotonicity of the observed known-link predicate is
checked over all trials. A fresh run never overwrites an existing directory.

## Safety and stop conditions

- Each build and GPU process has a hard timeout. The harness waits for public
  Metal completion before requesting a snapshot.
- Stop one variant on timeout, GPU error, target readback mismatch, missing
  first-segment dump, allowlist violation, an unrecognized link-word target,
  failure to find the known link by the fixed upper bound, or non-monotonic
  search observations.
- Preserve stdout, stderr, exit status, timeout status, trace metadata, partial
  allowed dumps, and the failure record. Do not broaden capture to diagnose.
- No mutation or replay is permitted on this M4 host.

## Interpretation limit

Successful correlations are at most `DATA-TRACE-VALIDATED` for thresholds and
`STRUCTURAL` for link framing. They do not establish hardware consumption,
general relocation packing, legal arbitrary targets, call/return behavior, or
an A18 Pro rule.

## Pre-run clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs permitted: authored MSL and buffers; public Metal status/readback;
  exact EXP-0043-preclassified CDM/VDM BO mappings only
Apple binary introspection: NONE
Apple auxiliary/helper/shader code inspection: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Executing command-memory mutation: NONE
```

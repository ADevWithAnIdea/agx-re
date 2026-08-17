# EXP-0041 results: scratch works, but the helper ABI remains hidden

## Verdict

**PARTIAL / strong negative. P0.1 is not closed.** On this M4/G16G, authored
CS, VS, and FS programs with 208–576 bytes of compiler-declared per-thread
scratch executed successfully. However, scratch demand caused no separately
observable helper record or scratch BO at the traced process boundary, no
compute launch-descriptor change, no FS command/state change, and no allocation
change in an equal-user-allocation 65,536-thread stress control.

This is evidence against deriving the unchanged Asahi helper ABI by merely
diffing ordinary macOS Metal submissions. It is not evidence that helpers are
unnecessary, kernel-owned under the Linux UAPI, or identical on A18 Pro.

## Direct observations

### 1. Stage metadata and live execution

The figures below were read from the `__GPU_METADATA` attached to pipelines
compiled from the retained MSL. Every case then completed on the live M4 GPU.

| case | pressured stage | GPR field 0 | scratch field 41/14 | live result |
|---|---|---:|---:|---|
| CS K72 | compute | 76 | 0 | completed, checksum 573.36303 |
| CS K80 | compute | 84 | 0 | completed, checksum 637.570032 |
| CS K96 | compute | 96 | 208 | completed, checksum 766.284034 |
| CS K112 | compute | 95 | 352 | completed, checksum 895.398032 |
| CS K160 | compute | 94 | 576 | completed, checksum 1285.14005 |
| VS K72 | vertex | 77 | 0 | completed, checksum 28608 |
| VS K112 | vertex | 96 | 352 | completed, checksum 28608 |
| FS K72 | fragment | 75 | 0 | completed, checksum 28608 |
| FS K112 | fragment | 96 | 336 | completed, checksum 28608 |

The `cs_spill_k80` filename's assumption was false: it had zero scratch. The
first spilling compute source in this exact set was K96. This is compiler/source
specific and is not promoted as a universal threshold.

Both full process runs reproduced identical metadata, results, resource maps,
and command/state BO bytes. See `analysis/m4_20260817_repeatability.txt`.

### 2. Boundary allocations

For CS scratch 0, 208, and 352 bytes, all 29 resource-map entries were
identical. K160/576 bytes enlarged `gpu_va 0x10000080000` from 0x8000 to 0xc000;
the same BO tracks authored program size, so this is a code-size allocation,
not proof of scratch backing.

The VS pair differed only in a CPU-provided resource VA by 0x200 while retaining
the same 0x20000 allocation size. That shift matches the larger authored input
buffer and cannot identify scratch. The FS pair's resource maps were identical.

The decisive allocation control held the user input allocation at 40 MiB and
dispatched 65,536 threads:

| case | scratch | TG | resource maps |
|---|---:|---:|---|
| CS K72 | 0 | 32 | 29 entries |
| CS K160 | 576 | 32 | same ordered 29 entries |
| CS K160 | 576 | 256 | same ordered 29 entries |

The ordered `(client class, GPU VA, size)` sequence was exactly identical, not
only the allocation-size multiset. All three dispatches completed. Thus no
separate or lazily grown host-visible scratch BO was observed across this range.

### 3. Allowlisted command/state data

- Compute launch BO `0x100000b0000` was byte-identical for CS scratch 0, 208,
  352, and 576 bytes. All five files share SHA-256
  `c35020473aed1b4642cd726cad727b63fff2824ad68cedd7ffb73c7cbd890479`.
- FS VDM `0x18000`, fixed-function state `0x58000`, and geometry state
  `0x68000` were each byte-identical between scratch 0 and 336.
- VS `0x58000` and `0x68000` were identical. `0x18000 + 0x11` changed
  `0x08 -> 0x09`. This one-byte state/extent change is correlated with the much
  larger VS as well as scratch and is therefore **not identified as helper or
  scratch state**.

No pointer value was followed. No program BO named by command data was read.
No `binary/cfg/data` triplet can be identified from these negative/ambiguous
diffs.

### 4. Authored main-program bytes

For run01, a second clean compilation retained only each stage's `_agc.main`
symbol from the complete matching MSL. This is lawful OWN-SHADER evidence.
Exact byte pattern `60 00 00 00`, previously described as a spill/frame marker,
occurred zero times in every captured main, including CS/VS/FS programs whose
metadata proved 208–576 bytes of scratch.

Observation only: the exact marker is not universal for these compiler-emitted
spilling main programs. It does not disprove other `0x60` forms or a marker in a
different region. The current ISA tokenizer leaves large suffixes of these
pressure programs undecoded, so EXP-0041 does not claim a complete spill/fill
instruction decode or absence of other scratch operations.

### 5. Failures and safety

The initial shell watchdog attempt failed because macOS lacks GNU `timeout`.
The harness uses explicit `subprocess.run(..., timeout=...)` watchdogs instead.
The first metadata parser attempt stopped at an `MTLB` wrapper; it was corrected
to skip non-Mach-O archive entries, matching the established parser behavior.
Both failures precede hardware execution and remain recorded verbatim in
`raw/preflight_failures.txt`.

Live runs: no compile rejection, GPU fault, timeout, hang, device loss, reboot,
or recovery action.

## Interpretation

Within the tested macOS path, per-thread scratch demand is carried in the
authored pipeline metadata and serviced without a spill-correlated change in
the inspected launch/state records or resource mappings. Plausible alternatives
not excluded are a fixed preallocated pool, firmware/private-runtime state not
mapped through the traced selector, an implicit instruction ABI, or state in an
uninspected BO. The experiment deliberately does not choose among them.

The public Mesa geometry and doorbell values remain hypotheses only. None of
address shift 8, 32 threads/group, 8-dword units, block-list/header layout,
four block registers, maximum subgroup/core counts, doorbells 32/48/49, or
helper operation numbers was observed here.

## P0.1 items still unknown

- helper program source/machine code that userspace can lawfully generate;
- helper `data` input SRs and output/acknowledgement ABI;
- NEXT/ACK/NACK doorbell encodings and semantics;
- `binary` address tags and every `cfg` bit for VS/FS/CS/main/preamble;
- scratch header, per-core list, block descriptor, alignment/address shift,
  block count/bucket, maximum active subgroups, and maximum block size/count;
- topology/core-mask to helper-core mapping;
- reset, growth, concurrency, allocation failure, and device-loss behavior;
- proof that G16/G17 consume existing `drm_asahi_helper_program` fields.

The safe driver fallback is to reject/avoid shaders and preambles requiring
scratch. Guessing helper values or declaring the fields kernel-owned would not
satisfy the unchanged UAPI.

## Target and evidence limits

All hardware observations are from the local Apple M4 / G16G only. Similarity
to A18 Pro is a research hypothesis, not validation. No A18 claim is made.

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER / PUBLIC-hypothesis-only
Inputs inspected: authored MSL and its own metadata/_agc.main; resource-map metadata;
  four pre-established command/state BO roles
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE
Reproduction: README.md commands
Evidence: raw/, analysis/, manifest.json
```

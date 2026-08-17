# EXP-0043 results: M4 command-stream framing

## Verdict

This experiment closes a bounded part of P0.5 on the tested Apple M4/macOS
26.6.2 path: it establishes repeated-record framing, termination, and segment
links for direct compute and non-indexed graphics workloads, including exact
rollover behavior for the tested record/state shapes. It also establishes how
adjacent versus interleaved encoder/pass boundaries affect termination and
shows concrete absolute resource-pointer relocation under allocator movement.

It does **not** close all of P0.3 or P0.5. Link packets are `STRUCTURAL`, not yet
mutation/replay validated. Call/return, explicit barrier/cache-control packets,
indirect modes, full PPP/USC/ZLS schemas, arbitrary reserved bits, and a general
command-pool capacity formula remain unknown. Results are M4-only; A18 Pro/G17P
transfer is `INFERRED` until a direct run.

## Target and evidence integrity

- Target: Apple M4 Mac mini, 10 GPU cores, Metal 4.
- OS: macOS 26.6.2 (25G82); Darwin 25.6.0.
- Toolchain: Apple clang 21.0.0; Python 3.14.6.
- Repository revision recorded at capture: `7a4a4f384dee374b8cdb7a6a0491714680ae6dac`.
- Runs: `raw/runs/m4-20260817-a/` and
  `raw/runs/m4-20260817-boundaries-a/`.
- All 22 traced cases completed with Metal status 4 and expected final
  readback. No GPU fault, timeout, reboot, or retry occurred.
- Across both runs, every retained BO/map snapshot reports a full read
  (`size == read`). See `raw/evidence-audit.txt`.
- The boundary run retains byte-exact safe inputs under
  `raw/runs/m4-20260817-boundaries-a/inputs/`. Each case retains its exact
  command, and the unchanged authored harness is `harness/framing.m`.
- A post-capture audit quarantined the first generic, directory-wide derived
  analysis because it could mechanically scan unclassified auxiliary-program
  BO bytes. No quarantined report is evidence for this file. All cited derived
  evidence was regenerated from explicit pre-classified command/state/
  descriptor snapshot files, without dereferencing encoded addresses. Run
  `python3 analysis/verify_clean_evidence.py .` to verify the separation.

The untraced preflight initially delivered `SIGUSR1` without the interposer and
therefore exited by signal after successful GPU completion/readback. That
failure is retained under `raw/preflight/`; the harness was corrected before
the first DATA-TRACE capture by requiring explicit `--dump`.

## Direct observations

### 1. CDM records, termination, and link

For one, two, eight, 732, 733, and 1024 authored dispatches, the structural
scanner found exactly one CDM candidate per dispatch. Each candidate contains
the exact authored public launch dimensions `(grid 64,1,1; tg 32,1,1)` and is
exactly **0x2c bytes**. Within a segment, candidates are contiguous and in API
order.

The tested first 0x8000-byte CDM BO at `0x100000b8000` holds 732 records:

```text
first record:  +0x0000
last record:   +0x7da4
next control:  +0x7dd0
```

- With exactly 732 dispatches, `+0x7dd0 = 0x40000000`, followed only by zero
  bytes. This is the observed CDM terminator.
- With 733 or 1024 dispatches, the word at `+0x7dd0` is replaced by two words:
  `0x20000100, 0x00158000`. Interpreted structurally as opcode/high-address and
  low-address portions, they name the captured BO `0x10000158000`.
- The target begins immediately with the next 0x2c-byte record. The one-record
  733 case terminates at target `+0x2c` with `0x40000000`; the 1024 case holds
  292 target records and terminates at target `+0x3230`.

The boundary pair is decisive: 732 and 733 have identical successful workload
shape except for the additional dispatch, and the exact terminator location is
what changes to the link. Evidence:

- `raw/clean-analysis/m4-20260817-boundaries-a/compute_732-cdm.txt`
- `raw/clean-analysis/m4-20260817-boundaries-a/compute_733-cdm-segment0.txt`
- `raw/clean-analysis/m4-20260817-boundaries-a/compute_733-cdm-segment1.txt`
- `raw/clean-analysis/m4-20260817-a/compute_1024-cdm-segment0.txt`
- `raw/clean-analysis/m4-20260817-a/compute_1024-cdm-segment1.txt`
- the corresponding complete BO snapshots and stdout readbacks.

Evidence strength: `DATA-TRACE-VALIDATED` for record repetition/termination and
the threshold under this workload; `STRUCTURAL` for link opcode/address packing.

### 2. VDM draw/state repetition, termination, and link

For one, two, eight, 328, 329, and 384 authored draws, the scanner found exactly
one non-indexed draw command per draw. The recorded vertex counts reproduce the
authored `3,6,3,6...` order exactly, and all final render readbacks succeeded.

Each draw command itself is four dwords (opcode/primitive, vertex count,
instance count, observed zero). It is preceded by a state prefix beginning with
the stable observed word `0x4000002e`. The prefix is not fixed length:

- first draw: header-to-draw distance 0x64;
- later pipeline/state A draws: 0x4c;
- later pipeline/state B draws: 0x54;
- resulting post-first draw-to-draw strides alternate 0x5c and 0x64.

Therefore a packer must not model the entire per-draw region as a fixed-size
record. The four-dword draw packet is fixed for this direct non-indexed shape;
the preceding state emission is variable.

The first tested 0x8000-byte VDM BO at `0x18000` holds 328 alternating draws:

```text
first draw:    +0x0064
last draw:     +0x7b08
next control:  +0x7b18
```

- With exactly 328 draws, `+0x7b18 = 0xc0000000`, followed only by zero bytes.
  This is the observed VDM terminator.
- With 329 or 384 draws, that word becomes the two-word link
  `0x80000000, 0x00088000`, naming captured low-VA BO `0x88000`.
- The target begins with the next state header. The 329 case draws at target
  `+0x4c` and terminates at `+0x5c`; the 384 case holds 56 target draws and
  terminates at target `+0x1500`.

Evidence:

- `raw/clean-analysis/m4-20260817-boundaries-a/render_328-vdm.txt`
- `raw/clean-analysis/m4-20260817-boundaries-a/render_329-vdm-segment0.txt`
- `raw/clean-analysis/m4-20260817-boundaries-a/render_329-vdm-segment1.txt`
- `raw/clean-analysis/m4-20260817-a/render_384-vdm-segment0.txt`
- `raw/clean-analysis/m4-20260817-a/render_384-vdm-segment1.txt`
- the corresponding complete BO snapshots and stdout readbacks.

Evidence strength: `DATA-TRACE-VALIDATED` for draw/state repetition,
termination, order, and threshold under this exact state shape; `STRUCTURAL`
for link opcode/address packing.

### 3. Encoder, pass, mixed-engine, and queue boundaries

- Two adjacent compute encoders in one command buffer produced a CDM BO
  byte-identical to two dispatches in one compute encoder: two contiguous
  0x2c-byte records and one final `0x40000000`. On this case, Metal coalesced the
  encoder boundary at this command-stream level.
- Two draws in one render pass had no terminator between them: the next state
  header occupies the position where the one-draw terminator appeared.
- Two separate render passes in one command buffer each ended with
  `0xc0000000`; the second state header followed the first terminator.
- When compute and render encoders alternated, every single-record CDM substream
  ended with `0x40000000` and every one-draw VDM substream ended with
  `0xc0000000`. CDM record starts were 0x30 apart (0x2c record + 4-byte
  terminator). VDM draw starts were 0x78 apart for the tested one-draw passes.
- A compute workload on queue 0 plus render on queue 1 retained the same CDM
  fixed record/terminator grammar and VDM draw/terminator grammar. This does not
  prove queue-context fields because the workloads also used different engines.

The mixed workloads used independent output resources. They prove the accepted
API sequence changes stream subdivision, but they do **not** independently prove
cross-engine execution order or reveal the outer scheduling/barrier record.

Evidence:

- `raw/clean-analysis/m4-20260817-a/compare-compute-same-vs-split.txt`
- `raw/clean-analysis/m4-20260817-a/compute_split_2-cdm.txt`
- `raw/clean-analysis/m4-20260817-a/render_split_2-vdm.txt`
- `raw/clean-analysis/m4-20260817-a/compute_render_2-cdm.txt`
- `raw/clean-analysis/m4-20260817-a/compute_render_2-vdm.txt`
- `raw/clean-analysis/m4-20260817-a/two_queues_2-cdm.txt`
- `raw/clean-analysis/m4-20260817-a/two_queues_2-vdm.txt`.

Evidence strength: `DATA-TRACE-VALIDATED` for subdivision and retained order;
`UNKNOWN` for an explicit hardware barrier/cache-control encoding.

### 4. Repeated command buffers

Three successive two-dispatch command buffers on one queue produced the same two
CDM records byte-for-byte at the same offsets in all three snapshots. The two
authored per-submit tag values changed in the associated argument/uniform data
(`0x10000088000 +0xb0/+0xe0`), and readback advanced from tags 0/1 to 2/3 to
4/5. This shows command-memory reuse after completion for the tested case; it is
not a safe in-flight reuse rule.

Evidence: `raw/clean-analysis/m4-20260817-a/compare-repeat-0-vs-1.txt`,
`compare-repeat-1-vs-2.txt`, `repeat_compute_3-dump00-argument-fields.txt`,
`repeat_compute_3-dump01-argument-fields.txt`,
`repeat_compute_3-dump02-argument-fields.txt`, and the corresponding
stdout/readback files under the retained run.

### 5. Relocations observed under allocator movement

Seven 0x3000-byte padding allocations moved authored resources while preserving
successful execution:

- compute output `0x10000030200 -> 0x1000002d200`;
- vertex buffer `0x10000030300 -> 0x1000002d300`.

Absolute 64-bit pointer slots tracked those movements:

- compute resource table `0x100000e8000 +0x14a0/+0x14c0` tracked the compute
  output VA exactly;
- graphics resource table `0x10000100000 +0xa0/+0xc0` tracked the vertex VA
  exactly.

The CDM and VDM segment-link targets did **not** move under this padding method.
Consequently the observed split high/low address reading is plausible but not a
general relocation formula. High-address width, tag/reserved bits, address
alignment requirements beyond the observed 0x8000-aligned targets, and whether
macOS patches these fields remain unproven.

Evidence: `raw/clean-analysis/m4-20260817-a/compute_2-resource-fields.txt`,
`compute_pad_2-resource-fields.txt`, `render_2-resource-fields.txt`,
`render_pad_2-resource-fields.txt`, and paired stdout/captures.

## Observed alignment and zero tails

All identified record starts, links, and terminators are four-byte aligned. Both
link targets are 0x8000-aligned BO bases. Every byte after the terminal or link
in the source/target command BO was zero in the exact 732/733 and 328/329
boundary cases. This is an observation about these macOS allocations, not proof
that all reserved tail bytes are hardware-required zero.

## What remains unknown / safe implementation stance

- Whether CDM `0x20000000` and VDM `0x80000000` link records are directly
  hardware-consumed or macOS/firmware bookkeeping. Do not mark them
  `HW-VALIDATED` without an independently generated or mutated link executing.
- General address packing and relocation. Only targets `0x10000158000` and
  `0x88000` were observed; padding did not move them.
- A general segment-capacity rule. 732 is exact only for contiguous 0x2c CDM
  records in this workload. 328 is exact only for this alternating VDM state
  shape; different state prefixes change byte consumption.
- CDM/VDM call/return forms, explicit barriers, cache/coherency controls, fault
  behavior for malformed links, legal link depth, cycles, and command-pool
  recovery.
- Which stable control words are required hardware fields versus Metal private
  values. No field is promoted solely because it is repeatable.
- Cross-engine dependency and CPU-visibility semantics; the mixed outputs were
  independent.
- Any A18 Pro/G17P conclusion. The experiment should be rerun there before
  transfer; until then commonality is `INFERRED` only.

Safe current guidance is to preserve these findings as a structural Apple9/M4
grammar seed, not as a complete packer schema. A future clean-room link mutation
probe should generate a second segment at a deliberately moved VA, patch only
the captured link address in command/state data, execute with a watchdog, and
verify all 733/329 operations. That is the shortest route from `STRUCTURAL` to
`HW-VALIDATED`.

## Clean-room attestation

```text
Clean-room provenance: DATA-TRACE / OWN-SHADER / HW-PROBE
Inputs inspected: harness/framing.m; authored MSL embedded there; IOKit boundary
                  payloads; command/state/descriptor BO data; public API status/readback
Apple binary introspection: NONE
Reproduction: ./run.sh and ./run-boundaries.sh
Evidence: raw/runs/m4-20260817-a/, raw/runs/m4-20260817-boundaries-a/,
          raw/clean-analysis/, clean-evidence.json, manifest.json
```

No Apple binary, executable section, framework code, driver code, kernel code,
firmware, system shader cache, or Apple-authored shader was inspected,
disassembled, decompiled, strings-scanned, debugged, or used as evidence.
Captured auxiliary code bytes were retained only as raw boundary data and were
not analyzed.

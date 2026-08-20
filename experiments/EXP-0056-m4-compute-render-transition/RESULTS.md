# EXP-0056 results — M4 compute-to-render transition framing

## Verdict

**STOPPED BEFORE PAYLOAD CAPTURE. P0.5 remains open.** The first append-only
M4 process completed its public Metal command buffer, but the authored
compute-only readback falsified the probe before the requested transition
matrix could begin. No allowlisted command-BO payload was retained or opened.

This is a process result, not a hardware conclusion. The frozen probe defined a
CPU `Scene` struct with a 24-byte `float2[3]` prefix, while its authored MSL
`Scene` has 16-byte alignment for its succeeding `float4`. The MSL write is
observed at the aligned location, but the CPU check read the unpadded location:
`READBACK scene=0,0,0.25`. The expected first color component was `0.25`.
Therefore the process exited 6 even though Metal reported status 4 and no
error. This layout defect invalidates its public readback acceptance gate.

The metadata-only trace also contains no exact EXP-0043 command mapping start:
none of `0x100000b8000`, `0x10000158000`, `0x18000`, or `0x88000` was mapped.
No alternative mapping was selected; all observed `RESOURCE_MAP` entries remain
metadata only. The post-completion signal produced no `.bin`/`.meta` files.

## Retained evidence

- `raw/m4-20260819-transition01/00_inputs.json` binds the frozen source inputs
  and pre-registration hash before the build.
- `02_build_allowtrace.json` and `03_build_probe.json` retain successful source
  builds; no compiled executable is inspected.
- `trials/plain_compute-only/run.json` retains the status/readback failure.
- `trials/plain_compute-only/trace.log` retains only boundary metadata. It is
  not a byte dump and is never treated as command-packing evidence.

The runner intentionally stopped after that first failed process. There are no
retries, rewritten raw files, partial payloads, or discarded failures.

## Successor rule

EXP-0058 is a separately preregistered successor. It must correct the authored
layout before its first build and retain the same exact four-VA fixed allowlist.
It must not amend EXP-0056, infer an alternative command mapping, or treat this
failure as an Apple9 packing observation.

Clean-room provenance: HW-PROBE / DATA-TRACE metadata only / OWN-SHADER source.
Apple binary introspection: NONE. Apple auxiliary/helper byte inspection: NONE.

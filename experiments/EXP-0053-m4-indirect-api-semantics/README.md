# EXP-0053 — M4 indirect-command API semantics

## Question

How do public Metal indirect compute/draw arguments and indirect command buffers
behave on the local M4 for zero/nonzero work, argument update timing, execution
ranges, reset/re-encode, and optimization?

This bounds P1.7 at the public API/source-path layer. It does not inspect or
infer private VDM/CDM streams, ICB storage, helper programs, Linux UAPI fields,
or A18 Pro behavior.

## Process

`PRE_REGISTRATION.md` was committed as `3dea789d` before the first source compile
or GPU run, with SHA-256
`4773ea2764b1fd3479ec2f52881ff7dcb2b1cfe0fa2e1f592db37b57db8bd34f`.
The authored Objective-C harness uses only public Metal/Foundation APIs and
runtime-compiled embedded MSL. It retains exact authored readbacks, counters,
guards, commands, errors, target/tool identity, source hashes, and hard timeout
records in append-only run directories.

The first formal attempt is a preserved compile rejection: this SDK does not
provide the authored `supportsIndirectCommandBuffers` convenience property.
The second attempt compiled and completed the indirect argument cases, then the
first ICB execution faulted because the authored render pipeline omitted the
public `supportIndirectCommandBuffers` opt-in; later submissions in that process
were explicitly ignored. Runs 03 and 04 added the required descriptor flag and
passed, but retained compute/guard bytes only as exact FNV and aggregate checks,
short of the pre-registered full-byte retention. They remain successful design
history, not canonical evidence. Runs 05 and 06 add complete argument, counter,
output, guard, and texture bytes and are the canonical repetitions. No raw capture
was edited or discarded, and no reboot was needed between fresh processes.

`verify.py` reconstructs all four harness versions in memory and matches their
hashes to all six environment records. Runs 05/06 bind directly to the retained
final source. The deterministic analyzer enforces a closed
authored-output grammar and exact case sequence/results.

## Authored matrix

- zero-group indirect compute;
- indirect compute encoded with one group then changed to three before commit;
- GPU-produced four-group arguments in a prior encoder of the same command;
- zero- and three-vertex indirect draws with guarded argument storage;
- four-command ICB full, prefix, suffix, middle, and empty execution ranges;
- reset of the middle two ICB commands and re-encoding of one reset slot; and
- full-range ICB execution after public blit-encoder optimization.

Canonical compute outputs retain every byte of the asymmetric per-thread words,
atomic counter, arguments, and prefix/suffix sentinels. Render outputs retain
the complete arguments and 4x1 RGBA8 row.

## Reproduction

Always choose new append-only run IDs:

```sh
python3 run.py --run-id m4_YYYYMMDD_runNN
python3 analysis/analyze.py
python3 verify.py
```

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source
Inputs inspected: authored Objective-C/MSL; public command status/errors; bytes
  in buffers/textures allocated by the authored process
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/BO payload tracing: NONE
Pointer following: NONE
Mutation/splice: NONE
Evidence: raw/, analysis/, RESULTS.md, manifest.json
```

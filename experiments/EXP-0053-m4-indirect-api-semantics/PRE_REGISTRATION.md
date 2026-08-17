# EXP-0053 pre-registration — M4 indirect-command API semantics

Date: 2026-08-17

Target: local Apple M4 / G16G only. A18 Pro remains the primary project target
and must receive a later direct replication.

## Question

Which externally visible behaviors of Metal indirect argument buffers and
indirect command buffers can bound P1.7 without inspecting private command
streams or implementation code?

This experiment is deliberately API-semantic. It will not infer VDM/CDM words,
helper programs, private ICB storage, Linux UAPI fields, or hardware-consumed
packet formats from public results.

## Pre-registered hypotheses and falsifiers

H1 — indirect compute arguments are consumed at execution rather than copied
when the dispatch is encoded.

- Test: encode an indirect dispatch, change shared argument words before commit,
  and separately generate the argument words on the GPU in an earlier encoder of
  the same command buffer. Use asymmetric per-thread output and exact counters.
- Support: the executed grid matches the last value visible before the indirect
  dispatch in each explicitly ordered case.
- Falsifier: execution follows the encode-time value, or GPU-produced arguments
  remain stale despite a successful ordered producer/consumer command.

H2 — `executeCommandsInBuffer:withRange:` restricts execution to the requested
ICB command indices, including nonzero starts, rather than executing every
encoded command.

- Test: encode four draws with disjoint scissored pixels/asymmetric colors and
  execute full, prefix, suffix, middle, empty, and one-element ranges.
- Falsifier: any command outside the requested range changes its guarded pixel,
  or a command inside a valid range fails without a reported command error.

H3 — resetting an ICB range invalidates only that range, and re-encoding one
reset slot restores only that command.

- Test: execute the same four-command buffer before reset, after resetting a
  middle range, and after re-encoding one reset command. Clear targets between
  executions and retain full authored readbacks.
- Falsifier: commands outside the reset range disappear/change, reset commands
  continue to execute, or re-encoding affects another slot.

H4 — zero-sized indirect draw/dispatch arguments produce no authored writes,
while bounded nonzero arguments produce exactly the expected writes without
touching guard regions.

- Test: zero and asymmetric nonzero grids/counts with sentinel guards around
  every authored output and argument allocation.
- Falsifier: a zero case writes output, a nonzero case has an incorrect exact
  count, or any guard changes.

H5 — public ICB optimization preserves externally visible command behavior.

- Test: compare fresh, otherwise identical ICBs executed with and without
  `optimizeIndirectCommandBuffer:withRange:`.
- Falsifier: outputs or command completion differ.

Passing H1–H5 will establish only the tested public Metal/runtime source paths.
It will not establish native packet syntax, arbitrary concurrency ordering,
security validation, robustness for invalid inputs, or Vulkan device-generated
command conformance.

## Matrix and repetitions

The authored harness will use public Metal/Foundation APIs and embedded or
committed authored MSL only. It will retain:

1. direct controls beside zero/nonzero indirect draw and compute cases;
2. CPU-before-commit and GPU-producer indirect-argument cases;
3. four-command ICB range/reset/re-encode/optimization cases;
4. exact full output bytes, counters, guards, command status/errors, API support,
   target identity, source/tool hashes, and hard timeout records; and
5. two fresh process repetitions with append-only raw directories.

Invalid ranges, deliberately malformed private records, byte splices, and
fault-oriented cases are out of scope on this non-reboot-controlled local host.

## Process and stop rules

- This file must be committed before any EXP-0053 source compilation or hardware
  execution. Every run records this SHA-256 and the pre-run repository revision.
- Compile and GPU processes receive hard timeouts. Failures and rejected API
  paths are retained, never overwritten.
- No generic memory scan, command/BO trace, pointer following, binary archive,
  shader extraction, or compiled-byte inspection is permitted.
- If required public ICB functionality is unsupported, record the rejection and
  stop that branch rather than substituting private APIs.

## Clean-room boundary

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source
Inputs permitted: this pre-registration; authored Objective-C/MSL; public Metal
  command completion and bytes in resources allocated by the authored process
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
IOKit/BO payload tracing: NONE
Pointer following: NONE
Mutation/splice: NONE
```


# EXP-0051 results: bounded M4 synchronization behavior

## Verdict

**PARTIAL. P1.4 is not closed.** The local M4 Metal path reproducibly satisfies
the correctly scoped threadgroup, device-fence, encoder, queue-event, and host
completion litmus cases below. It also exposes only relaxed atomics and a
seq-cst fence from the tested MSL spellings; acquire/release identifiers are
rejected by this language environment.

These are compiler + Metal runtime + command processor + cache/scheduler
observations. They are not isolated native fence-instruction semantics, a
Vulkan/GL memory-model mapping, a decode of `cdm_barrier`/`vdm_barrier`, or an
A18 Pro fact.

## Direct observations

### 1. Reproduction identity

Two fresh suite processes used identical hashes for the pre-registration,
runner source, main MSL, five compile probes, and run script. Both compiled the
same 70,392-byte runner with SHA-256
`839fb7ae55cce23b7768e016cfd58a2e07c59f4fa4385013678c9ed675ba4f2e`.
All deterministic semantic outputs reproduced exactly. Neither run had a Metal
command error, pipeline failure, timeout, GPU fault, or recovery action.

### 2. Threadgroup barriers and memory-class controls

Every case checked 65,536 asymmetric peer values per run:

| authored case | topology/memory | mismatches run01/run02 |
| --- | --- | ---: |
| `threadgroup_barrier(mem_threadgroup)` | cross-simdgroup threadgroup memory | 0 / 0 |
| `threadgroup_barrier(mem_none)` | cross-simdgroup threadgroup memory | 0 / 0 |
| `simdgroup_barrier(mem_threadgroup)` | peers within one 32-lane simdgroup | 0 / 0 |
| `threadgroup_barrier(mem_device)` | cross-simdgroup device memory | 0 / 0 |
| `threadgroup_barrier(mem_threadgroup)` | device memory, deliberately wrong class | 0 / 0 |
| `threadgroup_barrier(mem_device|mem_threadgroup)` | cross-simdgroup device memory | 0 / 0 |

Observation: correctly flagged barriers passed the tested width and memory
patterns. The `mem_none` and wrong-memory-class cases also happened to pass.
Those negative controls contain a race under the intended API reasoning; their
success can result from execution rendezvous, coherent storage, compiler
behavior, or scheduling. It does **not** prove that the memory flags are
interchangeable or unnecessary.

The compiled pipeline reports a thread execution width of 32, so the
63-minus-lane peer in the 64-thread cases crosses simdgroups as intended.

### 3. Atomic and fence language exposure

Isolated source results were identical in both runs:

| authored operation | compile | live pipeline |
| --- | --- | --- |
| relaxed `atomic_fetch_add_explicit` | accepted | executed; final counter 2, return values 0 and 1 |
| acquire-release atomic RMW | rejected: identifier unavailable | not created |
| acquire atomic load + release atomic store | rejected: identifiers unavailable | not created |
| device-scope seq-cst `atomic_thread_fence(mem_device, ...)` | accepted | executed; two authored outputs and counter 2 |
| device-scope release fence | rejected: identifier unavailable | not created |

This establishes the tested macOS 26.6.2 Metal language/runtime exposure on M4.
It does not establish that Apple9 hardware lacks acquire/release bits or
instructions. No compiler binary or internal header was opened; the complete
diagnostics in raw are outputs returned for the authored source.

### 4. Same- and cross-threadgroup publication

Each mailbox carries four asymmetric non-atomic payload words and atomic
ready/ack counters. Every atomic flag operation is relaxed; fence cases add an
authored seq-cst `mem_device` fence before publication and after observation.

| topology/case | messages per run | timeouts | mismatched payload words |
| --- | ---: | ---: | ---: |
| same threadgroup, relaxed | 16,384 | 0 / 0 | 0 / 0 |
| same threadgroup, device-scope fence | 16,384 | 0 / 0 | 0 / 0 |
| same threadgroup, threadgroup-scope device fence | 16,384 | 0 / 0 | 0 / 0 |
| two threadgroups, relaxed | 8,192 | 0 / 0 | 0 / 0 |
| two threadgroups, device-scope fence | 8,192 | 0 / 0 | 0 / 0 |

The fenced hypotheses pass. Relaxed publication also passes this bounded M4
run, so the differential does not isolate fence necessity. A relaxed pass is
not a formal acquire/release guarantee. The two-group completion also shows
forward progress for this tiny resident topology only; it does not establish a
grid-wide barrier or arbitrary-workgroup scheduling guarantee.

### 5. Dispatch, encoder, command-buffer, and CPU boundaries

Each row performed 128 epochs × 4,096 words = 524,288 comparisons per run.

| producer/consumer relationship | run01 | run02 |
| --- | ---: | ---: |
| same compute encoder, no explicit barrier | 128/128 exact | 128/128 exact |
| same encoder, `MTLBarrierScopeBuffers` | 128/128 exact | 128/128 exact |
| adjacent compute encoders, one command buffer | 128/128 exact | 128/128 exact |
| two command buffers, same queue, no CPU wait | 128/128 exact | 128/128 exact |
| two command buffers, same queue, CPU wait | 128/128 exact | 128/128 exact |
| two queues, CPU wait between producer/consumer | 128/128 exact | 128/128 exact |
| two queues, shared-event wait/signal | 128/128 exact | 128/128 exact |
| CPU shared-buffer write before GPU submit; wait after | 128/128 exact | 128/128 exact |
| GPU shared-buffer write; CPU read after completion | 128/128 exact | 128/128 exact |

The same-encoder no-explicit-barrier case is an observation, not a general API
guarantee for every resource/access kind. The explicit buffer barrier, encoder
boundary, same-queue order, CPU wait, and shared event each pass this buffer
producer/consumer test.

### 6. Unsynchronized two-queue control

The consumer was deliberately committed first on queue 2 and the producer then
committed independently on queue 1:

| run | exact epochs | stale epochs | stale words |
| --- | ---: | ---: | ---: |
| run01 | 0 | 128 | 524,288 |
| run02 | 1 | 127 | 520,192 |

Every stale word was the asymmetric initial source sentinel, not unexplained
corruption. The one exact epoch in run02 demonstrates scheduling variability.
This is direct evidence that independent queue commit order supplies no
deterministic producer/consumer order in this test; explicit event or host
coordination is required.

### 7. CPU visibility

For shared storage, CPU writes performed before GPU submission were visible to
the consumer for all 1,048,576 checked words across both runs. GPU writes were
visible to the CPU after command-buffer completion for the same number of
words. No result is claimed for CPU access before completion, concurrent CPU/GPU
access, managed/private storage, external sharing, or cache maintenance without
the public runtime boundary.

## Hypothesis outcomes

- **H1 supported for correctly scoped cases; negative controls inconclusive.**
  All correct and deliberately under-scoped cases passed, so flag necessity was
  not isolated.
- **H2 supported as a non-exposure result.** Relaxed atomic and seq-cst fence
  compile and execute; acquire/release identifiers reproducibly do not compile.
- **H3 supported for the fenced cases but not differentiated from relaxed.**
  Both same- and cross-threadgroup publication complete without mismatches.
- **H4 supported for the explicit/API ordering boundaries.** The no-explicit
  same-encoder case also passes but remains a bounded observation.
- **H5 supported for shared storage at the tested completion boundaries.**

## Remaining P1.4 gaps and safe boundary

Still unknown:

- native Apple9 fence/barrier opcode semantics, bit fields, and cache operations;
- mapping of device/workgroup/subgroup/invocation scopes and relaxed,
  acquire/release, acq-rel, and seq-cst to native operations;
- texture, image, PBE, tile-memory, tiler, render/compute, depth/stencil, and host
  cache-domain transitions;
- width/type/address-space atomic availability beyond the tested 32-bit device
  counter, and atomic ordering for textures or threadgroup memory;
- Linux UAPI `cdm_barrier`/`vdm_barrier`, control-stream barriers, in-submit and
  cross-queue interactions, and firmware cache maintenance;
- arbitrary cross-workgroup progress, larger grids, simultaneous queues, fault
  behavior, and A18 Pro validation.

A driver must not substitute “relaxed happened to pass” for an API memory model.
Until native/UAPI transitions are live-validated, use conservative documented
barriers and explicit queue synchronization in supported paths, or leave the
affected concurrency capability unexposed.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: complete authored MSL and runner; compile results returned for
  authored sources; live status and process-owned buffer bytes
Apple binary introspection: NONE
Apple auxiliary/helper code inspection: NONE
Command/BO scan or pointer following: NONE
Compiled shader bytes inspected: NONE
Target qualification: local M4/G16G only; no A18 Pro claim
Evidence: README.md reproduction, raw/, analysis/, manifest.json
```

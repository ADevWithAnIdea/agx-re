# EXP-0009: IOKit/IOGPU data-tracing harness bring-up + submission-model determination

- **Date:** 2026-07-06
- **Clean-room category:** DATA-TRACE (+ OWN-SHADER for the traced programs)
- **Phase / question:** ROADMAP **0.5** (`tools/iotrace`); resolves the Open Question
  "Modern submission path: per-`IOConnectCallMethod` per draw vs IOGPU shared-memory
  rings + doorbell" — the deciding risk for Phase 2.
- **Device state:** Apple A18 Pro, SoC T8140, **G17P**, macOS 26.6 (25G5043d),
  Metal 4 / Apple9. SIP disabled. No boot-args changed (our harness is unsigned, so
  `DYLD_INSERT_LIBRARIES` injects without AMFI changes).

## Hypothesis

macOS 26 Metal no longer submits GPU work via a per-submit `IOConnectCallMethod`
(as Alyssa Rosenzweig's 2021 M1 trace showed: `SUBMIT_COMMAND_BUFFERS=0x1E` with a
40-byte struct, once per submit). We expect a firmware-style model: the command /
control stream is written into **shared GPU memory** and submitted with a
lightweight **doorbell**, so the per-submit userspace↔kernel traffic is minimal or
absent. We test by counting IOKit calls as a function of submit count, and by
capturing the shared memory and correlating it to our own resources.

## Method (and why it is clean-room legal)

DATA-TRACE: a `DYLD_INTERPOSE` interposer (`tools/iotrace/iotrace.c`) over the
public IOKit user-client surface (`IOServiceOpen`, `IOConnectCall*`,
`IOConnectMapMemory64`) logs only the **data** crossing the boundary — call
selectors, struct payload bytes, and the contents of GPU buffer objects. Command
buffers, descriptors and register values are non-copyrightable per the Asahi
clean-room policy. The traced programs are **our own** minimal Metal (OWN-SHADER):
a trivial compute dispatch and a trivial triangle draw. Nothing disassembles or
introspects the **code** of Metal/AGX/IOGPU. Reference for the *technique* only:
the public MIT+APSL Asahi `gpu_knowledge/asahi_linux/gpu_re/wrap/wrap.c` — this is
our own independent implementation.

## Procedure (reproducible)

On the device (`~/cleanroom_work/exp0009/`, Command Line Tools only):

```sh
sh build.sh            # iotrace.dylib, iohello_compute, iohello_draw

# 1. Trace-only: the full IOKit call sequence around a compute dispatch / a draw.
IOTRACE_LOG=compute_trace2.log IOTRACE_DUMP_DIR=comp_maps \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_compute --iters 1 --dump
IOTRACE_LOG=draw_trace.log IOTRACE_DUMP_DIR=draw_maps \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_draw --iters 1 --dump

# 2. Submission model: does the IOKit call count scale with submit count?
for N in 1 3 5; do IOTRACE_LOG=cmp_iter$N.log \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_compute --iters $N; done
for N in 1 3 5; do IOTRACE_LOG=d$N.log \
  DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_draw --iters $N; done
```

On the host, correlate the captured BOs with our own resource VAs:

```sh
python3 tools/iotrace/dumpscan.py raw/comp_maps --list
python3 tools/iotrace/dumpscan.py raw/comp_maps \
  --u64 0x10000030000 0x10000030100 0x10000030200 --u32 64 32
```

## Raw results

In `raw/`:
- `compute_trace2.log`, `draw_trace.log` — full annotated IOKit call sequences.
- `cmp_iter{1,3,5}.log`, `d{1,3,5}.log` — the submit-count differential (constant).
- `compute_BO_manifest.txt`, `draw_BO_manifest.txt` — every registered BO
  (GPU VA, CPU addr, size, non-zero byte count).
- `comp_maps/`, `draw_maps/` — the structurally interesting BO snapshots as hex
  (argument buffer, launch descriptor, shader code, control streams). Redundant
  128 KiB heap-alias dumps and giant sparse framebuffer/tiler dumps were pruned to
  keep the tree small; re-run to regenerate the full set.

Key observations are summarized inline in `RESULTS.md`.

## Analysis

See `RESULTS.md`. Headline: **submission is shared-memory + doorbell, not a
per-submit ioctl** (call count invariant under submit count), and the command /
control stream lives in ordinary userspace VM registered into the GPU VM via
selector 9 — located and correlated to our own shader, argument buffer and
dispatch dimensions.

## Established facts → docs

Deferred to the orchestrator (this experiment does not edit `docs/`). Candidate
rows for `docs/cmdstream/` + `PROVENANCE.md`:
- Submission model on G17P/macOS 26 = shared-BO + doorbell (evidence: EXP-0009
  call-count invariance).
- AGX resource-map call = `AGXAcceleratorG17P` selector 9 (in@0x38 CPU / in@0x48
  size / out@0x00 GPU VA).

## Follow-ups (Phase 2 seed)

- Pinpoint the **doorbell / ring**: interpose the 32-bit `IOConnectMapMemory` and
  `mach_make_memory_entry_64`/`vm_map`, and parse the notification-queue setup
  (sel 0x11) and the 1040-byte sel-7 setup struct, to find where the submit ring
  and completion queue are mapped.
- Decode the **CDM launch descriptor** and **argument buffer** layouts (change-one
  -parameter diffing: vary grid/tg, buffer count, buffer index).
- Byte-diff the **shader BO** against a `shdump` extraction of the same kernel to
  confirm the exact shader-code VA and any loader-applied fixups.

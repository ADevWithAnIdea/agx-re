# EXP-O2G: shader printf, mesh-into-ICB, compression × mipmap/NPOT

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + DATA-TRACE + HW-PROBE (no Apple binary disassembled)
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Metal 4 / Apple9. SIP off.
- **Phase / question:** objective-2 closure — the last 3 Metal-exposed capabilities not yet HW-exercised.

## Hypotheses
1. **Shader printf.** MSL logging lowers to records the shader emits into a bound "log buffer";
   determine the buffer (user-bound? special resource?), the record format (format-id + packed
   args?), and how the shader emits a record; classify driver/runtime-managed vs shader-emitted.
2. **Mesh-into-ICB.** `MTLIndirectCommandTypeDrawMeshThreadgroups` + `-[MTLIndirectRenderCommand
   drawMeshThreadgroups:…]` are API-exposed; the G17P HW/driver may or may not accept a mesh draw
   inside an `MTLIndirectCommandBuffer`. If accepted, the ICB command should lower to the EXP-0030
   mesh-grid-dispatch record `0x70000600`; if rejected, that is the answer.
3. **Compression × mipmap / NPOT.** Extends `docs/tiling` §3+§4: does the lossless-compression aux
   buffer cover all mip levels (per-level? aux size vs total image), and what is the exact NPOT /
   small-size compression threshold?

## Method (all clean-room)
- **printf (`pf.m`, `shdump_log.m`):** compile our own MSL that calls `os_log_default.log_info(…)`
  (macOS 26 exposes shader logging as `os_log` via `<metal_logging>`; C `printf` is not declared),
  with `MTLCompileOptions.enableLogging = YES` (else it is a no-op). Attach a `MTLLogState`
  (bufferSize), run under the read-only `tools/iotrace` interposer, and **race the completion
  drain**: the kernel logs then spins while we SIGUSR1-spam per-signal BO snapshots, catching the
  log buffer mid-flight (before the runtime consumes it). Byte-diff our own compiled shader
  (`shdump_log` = local `tools/shdump` copy with `enableLogging`) to see the emit lowering.
  *OWN-SHADER + DATA-TRACE.*
- **mesh-in-ICB (`micb.m`):** build a mesh render pipeline with `supportIndirectCommandBuffers`,
  encode `drawMeshThreadgroups`/`drawMeshThreads` into an ICB, `executeCommandsInBuffer:` in a
  render pass; each step guarded so any rejection is captured. Capture under `iotrace`; scan for
  `0x70000600` vs `0x61c4`/`0x6404`. *OWN-SHADER + DATA-TRACE + HW-PROBE (real render).*
- **compression (`cmip.m`, `texdesc.py`):** create batches of compression-eligible textures
  (`ShaderRead|RenderTarget`, no ShaderWrite/PixelFormatView), bind all into one arg buffer, dump,
  and decode every 32-byte texture descriptor (word1 bit26 mip / bit27 compression-aux, word3 bit31,
  word4/word5 aux VA) + match each base VA to its backing BO size. *HW-PROBE + DATA-TRACE.*

## Procedure
`sh run.sh` on the device (`~/cleanroom_work/exp_o2g/`). Builds `iotrace.dylib`, `pf`, `micb`,
`cmip`, `shdump_log`; runs the three parts; writes `raw/`. Host analyzers: `texdesc.py` (descriptor
+ allocation), `pflog.py` (log-buffer records), `imgloc.py` (AIR vs AGX image). See `RESULTS.md`.

## Raw results
`raw/part1_*` (log-buffer records + shader lowering + decoded strings), `raw/part2_meshicb_records.txt`
(0x70000600 scan + count-word diff), `raw/part3_*.desc.txt` (descriptor tables), `raw/caps_curated/`.

## Established facts → docs
See `RESULTS.md` §"Established facts". Targets: `docs/pipeline/` (printf/log buffer — new),
`docs/cmdstream/` (mesh-in-ICB — extends EXP-0027/0030), `docs/tiling/` §3/§4 (compression×mip/NPOT).
Orchestrator owns `docs/`/`PROVENANCE.md`.

# EXP-0011: Decode the COMPUTE submission control structures (CDM launch descriptor, argument buffer, shader BO, ring)

- **Date:** 2026-07-06
- **Clean-room category:** DATA-TRACE (+ OWN-SHADER for the shdump byte-validation)
- **Phase / question:** ROADMAP Phase 2 (control/command stream). Follows EXP-0009,
  which located but did not decode the compute launch descriptor / argument buffer /
  shader BO and did not pinpoint the ring/doorbell.
- **Device state:** Apple A18 Pro / G17P (T8140), macOS 26.6, SIP disabled. No nvram
  changes. Unsigned DYLD interposer (`iotrace.dylib`), AMFI unchanged.

## Hypothesis
Each compute submission control structure is a fixed-layout table whose fields can be
localised by the change-one-Metal-parameter method: change exactly one dispatch
parameter (grid dim, threadgroup dim, buffer count, bound shader, texture/sampler),
re-capture every GPU buffer object registered into the GPU VM, and byte-diff the
snapshots. The shader-code pointer and argument-buffer pointer should resolve to GPU
VAs iotrace already reports. Submission is ring+doorbell (EXP-0009); the ring should be
visible as a per-submit-incrementing index in shared memory.

## Method (all clean-room DATA-TRACE)
`tools/iotrace/` interposes the IOKit user-client boundary of **our own** minimal Metal
compute program (`cvar.m`, a parametric extension of `iohello_compute`) and snapshots
the CPU-side bytes of every BO registered via `AGXAcceleratorG17P` selector 9, plus (new
here) the sel-5 shared pages. Command buffers / descriptors / register values are
non-copyrightable hardware data per the Asahi clean-room policy. No Apple binary is
disassembled. The only machine code inspected is our **own** compiled shader
(`shdump` extraction of `_agc.main`), compared byte-for-byte against the captured code BO.

Analysis is pure data correlation:
- `tools/iotrace/bograph.py` — reconstructs the pointer graph among captured BOs.
- `tools/iotrace/bodiff.py`  — word-diffs paired BOs across two captures.
- `tools/iotrace/dumpscan.py` — byte-search for our resource VAs (existing).

## Procedure
On the device, under `~/cleanroom_work/exp0011/`:
```sh
sh run.sh          # builds cvar + iotrace, runs the capture matrix + on-device analysis
```
`run.sh` captures a matrix of one-parameter-changed dispatches into `caps/<label>/`:
- launch descriptor: `gx128 gx256 gy2 gz2 tgx64 tg8x4 groups2 heavy` vs `base`
- argument buffer:   `buf1 buf2 buf4 buf8 tex tgmem` vs `base`
- ring/doorbell:     `ring` (3–4 submits, `IOTRACE_DUMP_PERSIG=1` per-submit snapshots)

Extra targeted captures (documented in RESULTS):
```sh
# shader-pointer confirmation: two DIFFERENT pipelines in one command buffer
./cvar --kernel add3 --k2 heavy --dump
# ring/doorbell: per-submit snapshots incl. sel-5 shared pages, vmmap wrap
IOTRACE_DUMP_PERSIG=1 IOTRACE_WRAP_VMMAP=1 ./cvar --iters 4 --dumpall
# shader byte-validation
./shdump -o add3.bin add3.metal ; python3 agxparse.py add3.bin --stage compute --extract-hex
```

## Raw results
See `raw/`:
- `launch_descriptor.txt` — base + two-dispatch launch descriptor bytes.
- `launch_desc_diffs.txt`  — every one-parameter diff of the launch descriptor.
- `argbuffer.txt`          — argument-buffer content for buf1/2/4/8/base/tgmem/tex.
- `shader_validation.txt`  — captured live code BO vs shdump `_agc.main` + constant_program.
- `ring_doorbell.txt`      — per-submit ring producer index, selector histogram, sel-5/sel-7, map-syscall counts.
- `pointer_graph_base.txt`, `bo_manifest_base.txt` — baseline pointer graph + BO list.

## Analysis
See `RESULTS.md`. Every field mapped by a one-parameter diff is **HW-validated**; the
shader-pointer encoding is **HW-validated** by the two-pipeline capture; the config-word
and pointer high-bits are **inferred** (byte-pattern only).

## Established facts → docs
- CDM launch descriptor field map → `../../docs/cmdstream/` (compute launch).
- Tier-2 argument-buffer layout → `../../docs/descriptors/` + `../../docs/cmdstream/`.
- Shader-code pointer encoding (VA>>6) → `../../docs/cmdstream/`.
- Submission ring producer index + completion writeback → `../../docs/cmdstream/`.
(Orchestrator owns docs/ + PROVENANCE.md.)

## Follow-ups
- Full decode of the config/register-sizing word (launch desc +0x00) and the launch
  record's constant words (0x01000000, 0x40000001, 0x60000160).
- Threadgroup-memory size location (NOT in the launch descriptor; candidate: arg-buffer
  +0x14c0 or control BO 0x80000).
- Texture/sampler descriptor bit layout (the 32-byte texture descriptor + sampler descriptor
  captured in the `tex` arg buffer) — a `docs/descriptors/` item.
- Isolate the actual CPU→GPU doorbell store (ring producer index is located; the exact
  kick write is still not pinned — likely a store to a firmware-shared page + barrier).
- The big graphics follow-up: VDM/tiler/fragment command stream via `iohello_draw`.

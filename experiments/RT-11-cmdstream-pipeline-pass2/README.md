# RT-11 — cmdstream + pipeline: independent 2nd red-team pass

**Role:** 2nd-overlapping-pass red-team verifier. RT-2a (cmdstream) and RT-4 (pipeline)
already corrected `docs/cmdstream/README.md` + `docs/pipeline/README.md`. This pass
**independently re-derives the corrected facts with DIFFERENT programs** and hunts for
anything still wrong.

- Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), T8140. SIP off.
- Method: change-one-Metal-parameter **DATA-TRACE** (`tools/iotrace`, built `-arch arm64e`)
  + byte-diff of registered GPU BOs, and **HW-PROBE** (device capability + pipeline gates).
- Clean-room category: **OWN-SHADER + DATA-TRACE + HW-PROBE**. All shaders are our own MSL
  compiled at runtime; we log only non-copyrightable command-buffer/descriptor **data**. No
  Apple binary disassembled.

## Harnesses (all NEW programs, distinct from RT-2a/RT-4)
| file | probes | claim |
|---|---|---|
| `idx11.m` | non-indexed + indexed draws, full baseVertex/baseInstance/vertexStart, u16/u32 | indexed VDM record shift |
| `smp11.m` | graphics draw, sweep N textures × M samplers (distinct samplers) | USC sampler stride 0x20 |
| `sp11.m` | 2×/4× MSAA, default vs custom sample positions (exact 1/16-grid values) | sample positions userspace @+0x40 + kernel-route falsification |
| `mrt11.m` | 1..8 attachments, bgra8/rgba16f/rgba32f | 32 KiB-not-a-MRT-cap + per-attachment stride |
| `cdm11.m` | compute launch: threadgroup sweep + dynamic tgmem | CDM effective-tg mapping + tgmem field |
| `tgcap11.m` | static `[[threadgroup]]` pipeline-creation gate | 32 KiB = explicit threadgroup budget |
| `state11.m` | depth/stencil/raster/blend/tile-size/memoryless/occlusion/timestamp | regression re-check |

## Reproduce
```sh
# on device ~/cleanroom_work/rt11:
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
for p in idx11 smp11 sp11 mrt11 cdm11 state11 tgcap11; do
  clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o $p $p.m; done
sh run_rt11.sh          # captures + diffs, writes analysis/ hex/ evidence/
./tgcap11               # static threadgroup-memory pipeline gate
```

`raw/evidence/` holds the decoded tables; `raw/analysis/` the byte-diffs; `raw/hex/` +
`raw/bohex/` curated BO snapshots (text). See `RESULTS.md`.

**Note:** the GPU allocator placed some BOs at different VAs than RT-2a/RT-4 this run
(compute CDM at `0x100001b8000`, shader BO at `0x10000198000`); the *structure/offsets*
are identical — only the base VA shifted, as expected for a deterministic-per-run allocator.

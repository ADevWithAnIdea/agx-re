# EXP-O2B: sparse / PBE-renderable / 32-bit-float-filtering / bindless sampler-heap

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + OWN-SHADER + HW-PROBE (no Apple binary disassembled)
- **Phase / question:** objective-2 cluster O2-B — exercise & decode the Metal-exposed resource
  features `MTLHeap type=sparse`, `sparseTileSizeInBytes`, `MTLTextureUsageRenderTarget` (PBE),
  `supports32BitFloatFiltering`, `maxArgumentBufferSamplerCount` (bindless sampler heap).
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d, xnu T8140), Command Line Tools,
  runtime MSL compilation. Device workspace `~/cleanroom_work/exp_o2b/`.

## Hypothesis
Each feature is expressed somewhere in the userspace-visible descriptor/argument-buffer stream,
OR it is kernel/firmware-managed (page tables, global tables). Specifically: sparse textures carry
a tier flag and (maybe) a mapping-table pointer; render-target usability is a descriptor bit;
32-bit-float filtering needs a special descriptor/sampler flag; a large sampler heap extends the
Tier-2 argument buffer (EXP-0011/0015).

## Method
Change-one-Metal-parameter DATA-TRACE, identical in spirit to EXP-0015. One tiny **OWN** compute
kernel (`rvar.m`) binds a texture + sampler + output buffer into the Metal-generated Tier-2
argument buffer and samples the texture. Every knob (pixelFormat, `MTLTextureUsage`, heap type
none/automatic/placement/sparse, sparse tile map/unmap, sampler filter, storage) is a CLI flag.
Each dispatch is captured under the read-only `tools/iotrace` interposer; `argx.py` auto-locates
the Tier-2 argument buffer (the BO whose `+0x14a0` word self-points to the appended texture
descriptor — robust to the arg-BO VA shifting when heaps are allocated) and dumps the 32-byte
texture descriptor + 8-byte sampler descriptor, which are byte-diffed. A second **OWN** program
(`heaparg.m`) builds an explicit argument buffer holding an array of K sampler states, hexdumps it
directly (Shared, CPU-visible), and runs a dispatch that indexes `heap.samps[j]` with a
shader-computed index to HW-validate bindless sampler selection.

Clean-room legality: our MSL, our resources (whose GPU VAs / resourceIDs we print for
correlation), public Metal API, read-only IOKit data tracing. No Apple binary is disassembled,
decompiled, or introspected. See `../../CLAUDE.md`.

## Procedure (device, Command Line Tools only)
```sh
sh run.sh              # builds iotrace.dylib + rvar + heaparg + probe, runs the full matrix
./probe                # capability baseline (sparse tile sizes, caps)
./heaparg --k 8        # bindless sampler-heap layout + HW indexing validation
```
Pull back `analysis/` (byte-diffs) and `raw/` (descriptor dumps, heaparg/probe stdout, text only).

## Files
| file | role |
|---|---|
| `probe.m` | capability + sparse/placement/automatic-heap creation smoke test |
| `rvar.m` | parametric texture/sampler descriptor harness (usage / heap / sparse / filter) |
| `heaparg.m` | bindless sampler-heap (argument buffer of samplers) layout + HW index validation |
| `argx.py` | auto-locates the Tier-2 arg buffer, extracts texture+sampler descriptors |
| `run.sh` | full capture+diff driver (device) |
| `iotrace.c`, `descx.py` | read-only copies from `tools/iotrace` (unmodified) |
| `analysis/` | `diff_usage.txt`, `diff_sparse_heap.txt`, `diff_floatfilter.txt`, `hex_*.txt` |
| `raw/` | `desc_*.txt`, `key_descriptors.txt`, `heaparg_k{4,8,64}.txt`, `probe.txt` |

## Raw results & Analysis
See `RESULTS.md`. All four brief items answered; every finding marked **HW-validated** vs
**inferred**. Zero GPU wedges / reboots across the whole matrix.

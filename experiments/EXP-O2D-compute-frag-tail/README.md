# EXP-O2D: compute/fragment ISA tail (objective-2 clusters O2-D / O2-E)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (compile our own MSL → extract/splice/run) + DATA-TRACE (iotrace, read-only) + PUBLIC (tools/agx-isa DB read-only)
- **Device:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9. Workspace `~/cleanroom_work/exp_o2d/`.
- **Governing law:** `../../CLAUDE.md` + `../SUBAGENT_BRIEF.md`. No Apple binary was disassembled.

## Hypotheses / questions
1. **Atomic memory-ordering + fence bits.** Which bits of the `0x67` atomic op / `0x07` fence encode `memory_order` (relaxed vs seq_cst) and `thread_scope` (device/threadgroup)? Extends EXP-0018/0025.
2. **64-bit atomic min/max.** Decode the width field distinguishing 32- vs 64-bit `atomic<ulong>` min/max.
3. **bfloat general (non-matrix) ALU.** Does `bfloat` add/mul/fma/convert reuse the fp16 `0x10` group with a type bit, a distinct group, or lower to fp32?
4. **Subgroup tail.** New op-selects in `0x47`/`0xbf` for `simd_shuffle_and_fill_up/down` (+ modulo/rotate), `simd_is_helper_thread`, `simd_prefix_exclusive/inclusive_product`.
5. **Tile shader / imageblock.** Explicit `imageblock<T>` write + slice addressing (fragment/tile), and how a tile shader (`dispatchThreadsPerTile`) is submitted in the cmdstream (mid-render compute record?).

## Method (clean-room)
- Write MSL ourselves → `shdump` compiles → `agxparse.py` carves `_agc.main` → byte-diff variants (`bytediff`/local diff scripts) → splice a candidate byte and run on the real GPU (`agxtest.py` / `persistrun.py`), observe outputs = HW-validation.
- Tile kernels need a **tile render pipeline** (they fail compute-pipeline creation with "unlowered air.load.implicit_imageblock"), so `scripts/shdump_tile.m` builds a `MTLTileRenderPipelineState` and serializes its binary archive; `agxparse.py --stage compute` extracts the tile function bytes.
- Tile-dispatch submission traced with the **read-only** `iotrace` interposer over our own `scripts/iotile.m` (draw + `dispatchThreadsPerTile`), diffing draw-only vs draw+dispatch (`scripts/tilediff.py`).
- All compile-legality questions answered by isolated single-function compiles (one MSL rejection does not mask others).

## Procedure (reproducible)
On device under `~/cleanroom_work/exp_o2d/` (tools copied from `exp0038` + `agxrender`):
```
./extract.sh atomics_order atomic64 bfloat_alu subgroup_tail subgroup_disambig bfaddu cvt   # compile+carve
./fenceprobe.sh          # atomic_thread_fence flags x order x scope -> raw/fenceprobe.txt
./probe64.sh             # 64-bit atomic ops in isolation -> raw/probe64.txt
python3 fencediff.py     # localize the 0x07 fence bytes (needs raw/fenceprobe.txt)
# HW splice-validation (bfloat 0x11 add<->mul ; float simd_product<->sum): see raw/validation.txt
python3 agxtest.py --source kernels/bfaddu.metal --function bfaddu --grid 8 --tg 8 --int \
  --buf 1=16256,... --buf 2=16384,... --out 0=8 --splice _agc.main@0x22=1d
python3 agxtest.py --source kernels/subgroup_disambig.metal --function rf_prod --grid 32 --tg 32 \
  --buf 1=1,...(32) --out 0=32 --splice _agc.main@0x12=3f
# tile shader + imageblock + cmdstream trace
clang -fobjc-arc -framework Metal -framework Foundation -o shdump_tile scripts/shdump_tile.m
./shdump_tile -o out/tile_tk_write.bin -f tk_write kernels/ib_tile.metal
clang -fobjc-arc -framework Metal -framework Foundation -o iotile scripts/iotile.m && ./iotile   # HW validate
IOTRACE_DUMP_DIR=maps_tile   DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iotile --dump
IOTRACE_DUMP_DIR=maps_notile DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iotile --no-tile --dump
python3 tilediff.py maps_notile maps_tile
```

## Raw results
`raw/mains.txt` (all compute mains + compile-rejections), `raw/fenceprobe.txt`, `raw/probe64.txt`,
`raw/tile_mains.txt` (tile-kernel imageblock ops), `raw/tile_cmdstream_diff.txt` (tile-dispatch cmdstream delta),
`raw/validation.txt` (the HW splice + end-to-end results). See `RESULTS.md` for the analysis and
`new_descriptors.json` for the machine-readable encodings (orchestrator merges into `tools/agx-isa/db.json`).

## Clean-room note
Every inspected byte is the compiled form of MSL we wrote. `iotrace` logs only *data* (IOKit selectors +
mapped BO bytes) from our own process. `tools/agx-isa`, `tools/iotrace`, docs are READ-ONLY here; we did not
edit them or commit. Validated descriptors are staged in `new_descriptors.json` for the orchestrator.

# EXP-0019: Graphics fixed-function state packets + USC bind grammar

- **Date:** 2026-07-06/07
- **Clean-room category:** DATA-TRACE + OWN-SHADER (public Metal API only)
- **Phase / question:** Phase 2 cmdstream decode, graphics side. Follows EXP-0014
  (which located the `0x58000` FF-state pool, the `0x18000` VDM stream, and the
  `0x10000130000` USC program, but deferred per-packet bit decode and the graphics
  shader-entry word). Answers EXP-0014 §7 open items 1, 2 and the raster/depth/blend
  bit decode.
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores,
  Metal 4 / Apple9. Command Line Tools only; runtime MSL compilation.

## Hypothesis

The `0x58000` 3D fixed-function state pool holds bit-packed depth/stencil, blend and
rasterizer packets whose fields can be mapped by the change-one-Metal-parameter method
(the EXP-0011/0014 workflow). The graphics shaders are bound through the USC program in
`0x10000130000` (there is no compute-style `shaderVA>>6` word in the VDM draw command),
and that USC program carries a shader-entry encoding analogous to compute's.

## Method (why it is clean-room legal)

DATA-TRACE + OWN-SHADER. `svar.m` is our own parametric Metal draw (own MSL vertex +
fragment shaders, compiled at runtime) whose every depth/stencil, blend, and rasterizer
state parameter is a CLI flag. We reuse `tools/iotrace` **read-only** (copied to the
device) to snapshot the GPU buffer objects Metal registers into the GPU VM, then
byte-diff two snapshots that differ in exactly one Metal state parameter. Command-buffer
and state-packet bytes are non-copyrightable hardware data (Asahi clean-room policy). No
Apple binary was disassembled. Where blend turned out to be lowered into a
Metal-compiler-generated fragment/blend microprogram, we **only located** that program
(which BO it lives in); we did **not** disassemble it (CLAUDE.md rule 5).

## Procedure

On the device under `~/cleanroom_work/exp0019/` (see `run.sh`):
1. Build `iotrace.dylib` + `svar` **`-arch arm64e`** (required — macOS 26 rejects an
   arm64 interposer inserted into the arm64e Metal process: "incompatible architecture
   ... need arm64e"; captures silently fail otherwise).
2. Capture ~100 one-parameter-changed draws under the interposer (`--dump` snapshots
   every registered BO after `waitUntilCompleted`).
3. `bodiff.py` (dir-vs-dir, pairs BOs by deterministic `gpu_va`) diffs each variant vs
   its group reference. `summarize.py` (this dir) extracts the per-BO single-word diffs.

Reproduce a single field, e.g. depth compare:
```sh
sh run.sh                                   # full matrix + on-device diffs -> analysis/
python3 summarize.py 0x58000 dcmp_never,dcmp_less,dcmp_equal,dcmp_always
```

## Raw results

`raw/analysis/` — per-variant `bodiff` outputs; `raw/analysis2/` — shader-entry &
active-stencil-mask follow-ups; `raw/hex/` + `raw/hex2/` — trimmed hexdumps of the key
control BOs for the reference configs. Determinism/noise floor is **0 words** across the
38 paired control BOs (`raw/analysis/diff_base2.txt`); the only base-vs-base diffs are
the known `gpu_va=0x0` pseudo-BO alias and the `0x10000130000+0x534` per-run counter,
both excluded everywhere.

## Analysis

See `RESULTS.md` for the full field maps and code tables. Headlines:
- **Depth/stencil** is a clean bit-packed packet in `0x58000` (per-face front/back
  blocks); compare and stencil-op code tables fully mapped and HW-validated.
- **Blend factors/ops are programmable — compiled into the fragment shader
  (`0x10000000000`), not a fixed-function LUT.** Only coarse blend-class/write-mask bits
  sit in `0x58000`. Dual-source blend works; framebuffer logic ops are emulatable in the
  same shader path (no dedicated ROP needed).
- **Rasterizer** (cull/winding/clip) is a bit-packed word at `0x58000+0x70`; depth clamp
  is a native 2-bit field; depth-bias values are 3 floats in the tiler-param region.
- **Shader binding** is entirely through the USC program (`0x10000130000`, 3 stage
  sub-blocks); no `shaderVA>>6` in the VDM. Shader-entry word located; exact pointer
  encoding within the USC instruction is inferred/opaque.

## Established facts → docs
- Depth/stencil/raster packet field maps + compare/op tables, blend architecture,
  USC bind grammar → `docs/cmdstream/` (graphics section) → `PROVENANCE.md`
  (DATA-TRACE, EXP-0019). Capability-probe rows → `docs/hypotheses.md` (proposed rows in
  `RESULTS.md` §6 for the orchestrator to merge).

## Follow-ups
See `RESULTS.md` §7 (opaque bits): USC shader-entry pointer bit-encoding + control-word
nibble semantics; depth-word `+0x39=0x0f` constant; full write-mask isolation;
provoking-vertex probe; MRT / independent-blend; the depth-bias tiler-param BO location.

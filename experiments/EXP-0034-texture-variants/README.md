# EXP-0034: Texture-variant instruction completeness (capability backlog #14)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (+ PUBLIC for the ISA DB / Mach-O format)
- **Phase / question:** Phase 1 shader ISA — extend the EXP-0016 texture family to the
  variants a real driver needs: depth compare (shadow/PCF), gather / gather_compare /
  offset-gather, explicit-LOD/bias/grad placement, LOD query, texture atomics, and the
  array/cube/3D/MSAA coordinate operands.
- **Device:** A18 Pro / G17P, macOS 26.6. Command Line Tools only, runtime
  `newLibraryWithSource:`. Device workspace `~/cleanroom_work/exp0034/`.

## Hypothesis
The EXP-0016 sample bundle (4-byte companion `05 80 0c CC` + 10-byte sampler op
`0xb0`/`0x90`) generalizes to all texture variants via a small set of fields: a
variant/dimension/LOD/compare byte (op+2), a result descriptor (companion +3), an
access-mode byte (op+6), and register operands (coord + compare-ref + LOD/bias/grad +
extra-index) set up by preceding ALU. Depth compare uses the sampler descriptor's
compare-function field (EXP-0015 sense bit39 + test [40:42]).

## Method (clean-room: OWN-SHADER)
1. **Provoke** — our own MSL batteries (`kernels/tv_comp.metal`, `kernels/tv_frag.metal`,
   `kernels/tv_atomic*.metal`) each force exactly one variant (gather component x/y/z/w,
   offset gather, sample/gather_compare, explicit LOD/bias/grad, LOD query, array/cube/3D/
   MSAA, texture atomics).
2. **Extract** — `shdump` → `agxparse.py` carves `_agc.main`; `extract.sh` → `raw/mains.txt`.
3. **Byte-diff** — align the one-op-apart shaders to localize each field (`raw/field_map.txt`).
4. **HW-validate** — new harness `tvcmp.m` binds a **depth texture + a configurable compare
   sampler** (shadow/PCF, LOD query) and reads back scalars; `atomtex.m` binds an **r32uint
   atomic texture**; the EXP-0016 `texcomp` runs gather over an rgba grid. All force our own
   archived (spliced) machine code via `MTLPipelineOptionFailOnBinaryArchiveMiss`
   (`PIPELINE_SOURCE archive`). `hwval.sh` → `raw/hw_validation.txt`.

Every byte inspected is the compiled form of our own MSL. No Apple binary was disassembled.

## Procedure
```sh
# device ~/cleanroom_work/exp0034 (tools copied from exp0016):
clang -fobjc-arc -framework Metal -framework Foundation -o tvcmp   tvcmp.m
clang -fobjc-arc -framework Metal -framework Foundation -o atomtex atomtex.m
bash extract.sh      # compile+carve every variant -> raw/mains.txt, raw/atomics.txt
bash hwval.sh        # all HW validations -> raw/hw_validation.txt
```

## Raw results
- `raw/mains.txt` — `_agc.main` hex of 22 compute + 7 fragment texture-variant kernels.
- `raw/field_map.txt` — the aligned sample-bundle field table (byte-diff).
- `raw/hw_validation.txt` — shadow/PCF, gather, offset, LOD-query, texture-atomic HW runs.
- `raw/atomics.txt` — texture-atomic `_agc.main` bytes (lower to the 0x67 device atomic).

See `RESULTS.md` for the decode. DB refinements in `new_descriptors.json` (schema-compatible
with `tools/agx-isa/db.json`; orchestrator merges — this experiment does **not** edit
`tools/agx-isa/`).

## Follow-ups
- Fragment-context LOD-query numeric values (derivatives present); fine/coarse.
- Full op+3 extra-coordinate register bit decode (array/cube/3D/MSAA index packing).
- op+5 offset sub-bit widths for the full [-8,7]² Metal range (negative-y spill).
- Depth-array / cube shadow (`depthcube`, `depth2d_array` sample_compare).

# EXP-M5-08 — M5 capability census (OBJECTIVE 2)

**Goal:** enumerate EVERY hardware capability the M5 GPU exposes (Metal/MSL surface + Apple-advertised
Family-10 features) and classify how each is realized — so an empty-context reviewer finds no missing
Metal-exposed functionality. **Method:** M5 = G17g sibling of A18 (G17P/Apple9), so inherit each A18
classification and **downgrade to NYC wherever a known G17g delta touches the encoding and hasn't been
re-characterized on M5**; re-establish presence on M5 via the EXP-M5-04 device probe + an own-MSL
compile-only acceptance probe (no GPU dispatch).

## Deliverables
- `docs/capability-matrix-m5.md` — full census, 164 rows (§1–§15). Each capability → native / emulated /
  kernel-managed / NYC for the M5, with HW representation + evidence tag (M5-measured / M5-delta / inherit✓
  / splice-TODO / open-record).
- `docs/capability-completeness-m5.md` — OBJ-2 tracker: §A encoding-characterized-on-M5, §B confirmed-present-
  but-encoding-NOT-mapped (the backlog), §C emulation flags, §D honestly-excluded microarch/kernel, §E scorecard.
- `raw/mslprobe.m`, `raw/mslprobe2.m`, `raw/msl_acceptance.txt` — reproducible own-MSL acceptance probe + output.

## Tallies (164 rows)
- ✅ **native 65** — present + M5 encoding available (measured EXP-M5-05/06 or inherited & round-trip-green)
- ❓ **NYC 72** — present but M5 encoding not yet mapped ← **the OBJ-2 backlog**
- ⛔ **emulated 15** — absent → software-emulate
- 🔥 **kernel-managed 5** — firmware/submit (M5 submission model identical to A18)
- ⚙ **microarch-only 7** — no emittable encoding (counters only)

## OBJ-2 backlog (confirmed-present, encoding-uncharacterized) — directs the splice + cmdstream waves
72 NYC = **~46 ISA field-semantics splice-TODO** (G17g-delta families, leaders/lengths fixed + round-trip-green,
field maps not splice-validated on M5) + **~26 open cmdstream/descriptor records**:
1. Memory load/store `0x18`/`0x41` (#1 delta) + atomics (incl. float-add), image/imageblock/tile stores,
   vertex-varying store, mesh emit.
2. Texture sample/gather/read/LOD-query/sample_compare (`0x78`/`0x58`/`0x50`).
3. **Matrix MAC `0xcf` + Apple10 Neural Accelerator / `MTLTensor` path (marquee):** unresolved whether M5
   keeps A18's all-to-`0xcf` lowering or adds a dedicated neural/tensor instruction (`<metal_tensor>` compiles,
   `newTensorWithDescriptor:`=YES → surface present, ISA realization unmapped).
4. Ray tracing — `rt_intersect`/`rt_as_load`/`ray_data`, traversal, inline query, RT-from-render, motion blur, IFT.
5. Function calls / indirect / dylibs / recursion / spill frame (`0xef`/`0xff`).
6. Barriers & fences (`0x07`) — tg barrier, atomic fences, ROV pixel-order.
7. Subgroup reduce / prefix-scan (`0x3f`/`0xbf`).
+ cmdstream/descriptor data-trace: FF-pool depth/stencil/blend/raster enums, attachment/PBE/storage-image,
  tess/mesh/indirect records, TBDR render-control (sample positions, MSAA, tile size, imageblock, tile shaders),
  occlusion, tiling/compression/sparse.

## Absent on M5 that Metal wants → emulation flags (re-confirmed on M5)
Float atomic min/max; **all 64-bit atomics** (every add/min/max spelling); int8/int32 cooperative matrix;
packed depth24-stencil8; sampleCount 16. Inherited-from-A18 absences: fp64, arbitrary sampler border color,
polygon-point fill, cull distance, custom primitive-restart index, geometry shaders, transform feedback.

## Present on M5 (own-MSL compile probe)
coopmat fp16/fp32/**bf16**, int atomics + **float-add**, bfloat ALU, RT intersector + inline query,
subgroup/quad, `<metal_tensor>`. Absent: coopmat int8/int32, float atomic min/max, all 64-bit atomics.

## OBJ-2 gate status
**Not yet passing, but clean in the way that matters:** presence 100% enumerated + confirmed on M5; **no
Metal-exposed capability unaccounted for** — every gap is "encoding not yet mapped on M5," never "missing
hardware." Closing the backlog = the ISA-semantics splice wave (EXP-M5-07) + a cmdstream/descriptor data-trace wave.

## Clean-room attestation
All M5 presence facts are the driver's/compiler's responses to OUR OWN programs, or bytes our own process
observed at the IOKit boundary; every classification measured on M5 or inherited from a cited A18 `docs/` finding.
MSL probe is compile-only (`newLibraryWithSource:`), no GPU dispatch. No Apple binary disassembled/introspected.

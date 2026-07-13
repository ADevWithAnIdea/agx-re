# M5 (Apple10 / G17g) Mesa Userspace Porting Guide

How to implement Apple **M5** userspace GPU support in Mesa (`src/asahi`-style). The M5 GPU
(`MTLGPUFamilyApple10`, arch `applegpu_g17g`, SoC T8142, 8 GPU cores) is a **G17-family sibling of
the A18 Pro (G17P / Apple9)**. Across every subsystem it is **the A18 spec plus a bounded set of
precise deltas** — so this guide is delta-form: **start from `porting-guide.md` (A18) and apply the
deltas below.** Each section points to the authoritative M5 delta doc + its A18 base.

## 0. How to read this guide
For each Mesa module, read the A18 base doc (complete, self-contained bit tables) **then** the M5
delta doc (`docs/*/README-M5-deltas.md`, "same as A18 except…"). The machine-readable ISA is
`tools/agx-isa-m5/db.json` (rendered to `docs/isa/encoding-tables-m5.md`). Status board:
`docs/ROADMAP-M5.md`. Provenance: every M5 fact is HW-measured on the device (own-shader
compile→extract→disassemble, splice-and-observe, and own-process IOKit data-trace) — see the
`experiments/EXP-M5-*` reports.

### Framing facts that change the whole port vs the A18
1. **It's a sibling, not a clone or a rewrite.** ~84% of M5 instruction bytes decode with the
   unmodified A18 ISA DB; the cmdstream/descriptor/tiling/TBDR models are the A18 models with
   offsets moved. Budget for *delta* work, not a fresh port.
2. **The ISA has real, localized deltas** (below) — the compiler back-end must target G17g encodings,
   not G17P, for the memory / matrix / atomics / subgroup / texture / call families.
3. **8 GPU cores (vs A18's 5) changes nothing userspace-visible** — tile size stays 32×32, no
   core-mask field appears in any userspace BO (tiler is firmware-managed).
4. **SIP-off is not required** for RE, and nothing here depends on it for the driver.

## 1. Compiler backend (NIR → AGX) — `docs/isa/README-M5.md` + `encoding-tables-m5.md`
Base: `docs/isa/README.md` + `encoding-tables.md` (A18). M5 deltas (all HW-validated, EXP-M5-05/07/09):
- **Length rules** diverge in the low-nibble byte0 families `_6 _e _0 _f _7` (the `0xNe` column is a
  generational format change). The M5 DB (`tools/agx-isa-m5`) fixes these — tokenization 96.6% (own) /
  98.0% (third-party) byte coverage, round-trip identity.
- **Memory access is SPLIT** (vs A18's monolithic `device_load`/`store`): an ADDRESS-GEN op
  (`?f <slot<<2> 03 <idx>`, 4B) + a LOAD (`0x18/38/58/78` = 1–4 component) + a STORE
  (`0x01/21/41/61` = 1–4 component). Emit all three.
- **Matrix path splits** — `simdgroup_matrix` MAC → tile family (`?f ..07..`) + `2f 00 05` MAC (no
  `0xcf`); only MPP tensor keeps `0xcf`. **There is no dedicated neural opcode** — the Apple10 Neural
  Accelerator rides the matrix family.
- **Atomics + subgroup/quad** share a reduction selector `2f 00 <scope> 0a 27 80 <OP>` (byte+6 op:
  and/or/xor/add/min/max/float-add; scope byte+2; reduce/scan byte+9). **Texture** sample family =
  byte0 low-nibble `0xf` + byte+2 (`0x12` sample / `0x1a` read). **RT** `rt_intersect` transfers unchanged.
- *(Integration status: the M5 field maps for these are being finalized into `db.json` — see
  `docs/ROADMAP-M5.md` §1.3 and the EXP-M5-11 report for the current state and any residual opens.)*

## 2. Command / control stream — `docs/cmdstream/README-M5-deltas.md`
Base: `docs/cmdstream/README.md`. **Submission model identical to A18** (shared-mem + doorbell, client
`AGXAcceleratorG17G`, same IOKit call counts). Deltas: compute config `+0x00` **bit19 base dropped**
(bit23 tier kept); **tgmem MOVED +0x40→+0x38** (segmented encoding `0x0c00000f|(fine<<11)|(coarse<<19)`);
draw opcodes **+0x0800** (`0x69c4`/`0x69f2`), indirect draw `0x6c04`/`0x6c32`; **viewport +0x9d0**;
FF-state pool `0x58000` **relocated** (`+0x134..+0x1a8`) but **bit-identical** (depth/stencil/raster
enums = A18; all 8 compares + 8 stencil-ops HW-validated); **blend PROGRAMMABLE** (compiled into FS);
**USC bind grammar byte-identical** (relocated); **PPP output-select `+0x158`** (clip[7:0], point_size
bit18, viewport_array_index bit19, **render_target_array_index/layer bit20**; layered-render enable =
VDM `0x18000+0x20` bit6); **mesh** `0x70000600` (unshifted), **tessellation NATIVE**; occlusion HW-validated.

## 3. Resource descriptors — `docs/descriptors/README-M5-deltas.md`
Base: `docs/descriptors/README.md` + `format-table.md`. **Sampler (8B) + buffer byte-identical to A18.**
Texture (32B): one delta — **width/height bit split shifted +1 bit** (width−1 = word0[28:31]‖word1[0:10],
height−1 = word1[11:24]); type/format/swizzle/baseVA/arrayLen unchanged. PBE/storage-image + attachment
format word transfer (**format code byte+0x21**). Format-code table = A18.

## 4. Texture / image memory layout — `docs/tiling/README-M5-deltas.md`
Base: `docs/tiling/README.md`. The A18 twiddle + lossless-compression **allocation model transfers
byte-for-byte** (HW-validated over 6 formats × 8 dims via Metal `allocatedSize`): per-bpp tile edge
(bpp1→128, bpp2/4→64, bpp8/16→32), even-column page granule, mult-of-T padding, compression threshold
15→no/16→yes, aux = numTexels/32. (Open: intra-tile Morton byte order not byte-verified on M5 —
inherited from A18, allocation-consistent.)

## 5. TBDR pipeline — `docs/pipeline/README-M5-deltas.md`
Base: `docs/pipeline/README.md`. **Tile size = 32×32 confirmed on the 8-core M5**
(`0x68000+0x9c4/+0x9c8`); **programmable sample positions userspace-emittable** (BO `0x100000d8000+0x40`);
MSAA **1×/2×/4×** (8× rejected — do not offer); memoryless (poison `0x0eeee000`); occlusion (mode
`0x58000+0x1c4` bit14, offset `+0x1d8`).

## 6. Kernel interface — `docs/kernel-interface.md`
**Identical to A18** (submission = shared-mem + doorbell, no per-submit ioctl; same VA-space table and
firmware-managed items). The M5 client is `AGXAcceleratorG17G`; DYLD interposition of our own process
works with SIP on (irrelevant to the driver, relevant to tracing).

## 7. Capabilities — native vs emulate — `docs/capability-matrix-m5.md` + `capability-completeness-m5.md`
170 rows: **84 native / 61 NYC (encoding-unmapped, present) / 13 emulated / 7 kernel-managed / 5 microarch.**
**Must software-emulate on M5** (Metal wants / Vulkan-GL needs, absent HW): fp64; **all 64-bit atomics**;
float atomic min/max; int8/integer `simdgroup_matrix`; packed depth24-stencil8; sampleCount 16;
arbitrary sampler border color; geometry shaders; transform feedback; cull distance; wide/polygon-point
fill; conservative rasterization; pipeline-statistics queries. **Native (present + encoded):** RT
(intersect/inline-query/IFT/motion-blur/RT-from-render), mesh/object + tessellation, programmable blend,
layered rendering + multi-viewport, fragment depth-out + sample-mask, subgroup/quad + float-add atomic,
bf16/int64, argument buffers Tier-2, function pointers/dynamic libs, sparse. The Apple10 Neural
Accelerator / `MTLTensor` (incl. int8 matmul) is **present but NYC** — no dedicated opcode; rides the
matrix family.

## 8. Gaps a driver author must know (honestly-open — with the fallback for each)
- **Texture sample/gather/read/compare/LOD-query encoding** (`0x0f/0x1f` + byte+2 `0x12`/`0x1a` on M5, distinct
  from the A18 `0x5` `tex_sample` which is **superseded on M5**) — leaders identified, the per-variant length rule
  is in active integration (EXP-M5-16); until it lands, the coordinate/sampler/LOD operand fields ride the
  memory-load family. **This blocks textured fragment shaders — the highest-priority residual item.** Fallback:
  EXP-M5-09 `hex_extractions.txt` has the leaders + example bytes; `db.json` carries the shipped detail once integrated.
- **Divergent-address device atomics** (`atomic_fetch_add(&buf[gid],x)`) — the A18 per-lane `0x67` path is gone on
  M5; only uniform-address atomics migrated to `m5_reduce`. Divergent form being integrated (EXP-M5-16).
- **`simdgroup_matrix` cooperative-matrix MAC** (`2f 00 05`, EXP-M5-16), **function-call ABI** (`0xef`/`0xff` —
  needs a pipeline-`linkedFunctions` extraction; intra-shader control flow is fully green), **RT
  acceleration-structure load** (migrated off `0xdf` — needs an AS-bound splice testbed): documented-open with
  the leader/prose in `docs/isa` + EXP-M5-09/11; a driver can gate coop-matrix / function-pointers / RT until mapped.
- **Mesh vertex-amplification + payload-heavy records + full ICB**, USC buffer slots >2, user-varying-reorder HW
  proof — measured minimally; extend via the EXP-M5-13 harness.
- **Intra-tile Morton byte order** not byte-verified on M5 (allocation-consistent with A18); **M5 GPR machine
  model** (count/width, Dynamic Caching) inherited from A18, not re-confirmed (affects register allocation).
- The residual NYC capability rows are **present hardware whose exact encoding isn't mapped yet** — a driver
  can gate those features until mapped; none is a "missing hardware" surprise. **Retained A18 descriptors that
  the M5 supersedes** (`tex_sample`0x5, `matrix_mac`0xcf-for-simdgroup, `call`, `rt_as_load`0xdf, `atomic`0x67
  divergent-form) are flagged "superseded-on-M5" in the DB/ISA doc — do not emit them for M5 shaders.

## Provenance
Every M5 fact is HW-measured on `user@192.168.170.253` (Apple M5 / T8142): own-shader
compile→extract→disassemble + splice-and-observe (ISA), own-process IOKit data-trace + change-one-param
(cmdstream/descriptors/TBDR), own-MSL compile probes + `MTLDevice` queries (capabilities). No Apple
binary was disassembled or introspected. See `experiments/EXP-M5-*` and the git history for the full trail.

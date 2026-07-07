# EXP-0030 Results — hardware mesh shading (A18 Pro / G17P / Apple9)

**Verdict: STRUCTURALLY HARDWARE, NOT DEDICATED-OPCODE.** Apple9 mesh shading on G17P is a real
hardware pipeline — a mesh draw is a first-class **graphics submit that reuses the tiler (TA/VDM) +
3D path** with a distinct **mesh-grid-dispatch VDM record**, and there are dedicated compiler-generated
mesh helper subroutines (`_agc.object.write_childcount`, `_agc.mesh.write_uvb`). **But the vertex/
primitive EMIT itself uses NO new opcode:** `set_vertex` / `set_index` / `set_primitive` /
`set_primitive_count` all lower to the **ordinary memory-store family** (`0xe7` device store, `0xd7`
memory-store, `0x67` load) — the *same* opcodes a plain compute kernel writing the same data emits.
The **only** opcode group unique to the object/mesh stages is a 4-byte control marker `0x43`.
End-to-end **HW-validated**: our object+mesh+fragment pipeline renders the correct green triangle.

Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Metal 4 / Apple9. No faults, no reboots.

---

## 1. Dedicated mesh HW or emulated? — the deciding evidence

Compiled our own object+mesh+fragment pipeline (`kernels/mesh_tri.metal`) and a hand-written **compute
control** (`kernels/compute_emul.metal`) that manually writes the same 3 vertices + index triple +
primitive count to device buffers. Carved each stage's `_agc.main` and compared opcode inventories
(`raw/mains.txt`, `raw/mtok.txt`, `raw/walk.txt`).

**The mesh-stage vertex emit is a run of ordinary device stores.** The `set_vertex` block in
`mesh _agc.main` is nine consecutive 14-byte `0xe7` stores:
```
e7 02 54 0c 00 14 00 00  44 03 01 30 02 00      # position.x
e7 02 54 06 00 14 00 00  44 83 01 30 02 00      # position.y
e7 02 54 00 00 14 00 00  44 02 02 30 02 00      # position.z
e7 02 54 02 00 14 00 00  44 82 02 30 02 00      # position.w
e7 02 54 00 00 14 00 00  44 02 03 30 02 00      # color.r
e7 02 54 02 00 14 00 00  44 82 03 30 02 00      # color.g
e7 02 54 00 00 14 00 00  44 02 04 30 02 00      # color.b
e7 02 54 02 00 14 00 00  44 82 04 30 02 00      # color.a
e7 02 54 0a 00 14 00 00  84 02 00 10 02 00      # (index / w)
```
`0xe7` (byte+2 `0x54`) is the **exact device-store opcode** documented in EXP-0012 and present in the
compute control (`ctrl/emul` census: `0xe7 ×3`). There is **no** mesh analogue of the matrix `0xcf`
(EXP-0022) or the ray-intersect `0xea` (EXP-0023).

| stream | bytes | vertex/prim EMIT opcodes | novel emit opcode? |
|---|---|---|---|
| `mesh _agc.main` (emit triangle) | 306 | `0xe7`/`0xd7` stores + int-ALU + control-flow | **none** |
| `mesh _agc.main` (emit nothing) | 98 | — (208 B of emit stores removed) | — |
| `_agc.mesh.write_uvb` helper | 576 | 8× `0xd7` stores + `0x67` loads + `0x9f/0xa7` addr math | **none** |
| `object _agc.main` | 110 | `0xe7` stores (payload + child count) | **none** |
| **compute control** `emul_main` | 184 | `0xe7 ×3` device stores | (baseline) |

**Deciding facts:**
1. **No dedicated emit opcode.** The mesh output is memory stores into a buffer — identical opcode
   family to the compute control. This is the *opposite* of EXP-0022/0023, where a novel opcode present
   in the HW path and absent from the hand-written control proved dedicated silicon.
2. **The acceleration is structural, and real.** Two things are genuinely hardware: (a) the object→mesh
   **grid amplification** is a real fixed-function dispatch (there are dedicated compiler helpers
   `_agc.object.write_childcount` and `_agc.mesh.write_uvb`, and a mesh-dispatch VDM record §3), and
   (b) the mesh-output buffer (UVB) feeds the **rasterizer/fragment stage** through the fixed-function
   tiler path (§3, §4) — no second draw, no compute pre-pass.
3. **One object/mesh-unique opcode: `0x43`** (4 bytes, `43 00 00 01`) — a stage control/marker, **not**
   a data-emit op (it is byte-identical whether the mesh emits a triangle or nothing).

So the honest classification for `docs/capability-completeness.md`: **mesh shading = HW pipeline
(dispatch amplification + output→raster) driving compute-like object/mesh shader stages whose emit is
memory stores.** The emit is *compute-emulated in the ISA sense*; the *pipeline* is hardware. (Directly
analogous to how a vertex shader's varying output is stores while the tiler around it is fixed-function.)

## 2. Mesh/object ISA — how vertices/primitives are emitted, and the payload

All HW-validated by byte-diff of single-change variants (`kernels/mesh_variants.metal`, `raw/variants.txt`):

- **`set_vertex(i, v)`** → a run of `0xe7` device stores, one per struct word, into the mesh-output
  buffer at the vertex slot. **HW-validated:** changing the vertex COLOUR green→red moved exactly two
  store SOURCE-immediate bytes (`mesh _agc.main` +187 `00→02`, +201 `02→00`) — `float4(0,1,0,1)` vs
  `float4(1,0,0,1)`, the R/G immediates swapping — with the store opcodes unchanged. The store
  `<field_off>` byte (`0c/06/00/02…`) is the per-component byte offset within the vertex's UVB slot.
- **`set_index(i, x)`** → the index value is computed in registers then stored (and the connectivity
  appears as the 8× `0xd7` stores `d7 06 54 <slot> 16 00` in `write_uvb`). **HW-validated:** reversing
  `set_index(lane)`→`set_index(2-lane)` added a single 10-byte `0x1f/0x9f` int-subtract (306 B→316 B),
  leaving the store path intact — the value is data, not opcode.
- **`set_primitive(i, p)`** → stores of the per-primitive struct, predicated under `if(lane==0)`
  (`0f05`/`0f06` execution-mask push/pop, EXP-0010).
- **`set_primitive_count(n)`** → a **predicated (lane==0) device store of the count**, *not* an opcode.
  **HW-validated:** `emit0` (count 0) vs `base` (count 1) differ only in the stored value; the `0x43`
  marker is byte-identical → `0x43` is not the count writer.
- **Object payload (`object_data`)** → written by ordinary stores in the object stage. **HW-validated:**
  payload `scale` 1.0 vs 2.0 changed 2 constant bytes (`object _agc.main` +11 `3e→40`, +15 `0c→00`).
- **`_agc.mesh.write_uvb`** (576 B, INVARIANT across all emit variants) = generic helper that computes
  the UVB base + per-lane slot address (`0x67` loads of the UVB pointer, `0x9f`/`0xa7` int-ALU) and does
  the trailing `0xd7` index/connectivity stores. **`_agc.object.write_childcount`** (128 B, byte-
  IDENTICAL between grid=(1,1,1) and grid=(2,1,1)) = generic helper that writes the mesh-grid **child
  count** it is handed.
- **Grid amplification (`set_threadgroups_per_grid`)** → the count is computed in `object _agc.main`
  (grid (1,1,1) vs (2,1,1) moved bytes +16..+25) and passed to `write_childcount`. **HW-validated diff.**
- **`0x43` obj/mesh control marker** — the only object/mesh-exclusive opcode group (§1). 4 bytes,
  `43 00 00 01` at instruction boundaries in both object and mesh `_agc.main`; `43 00 06 xx` at the head
  of the helper regions. Role: amplification-stage control / output setup. **Inferred** (byte-diff),
  role not splice-validated. Added to `new_descriptors.json` as `obj_mesh_ctrl`.

The **fragment stage of a mesh pipeline is an ordinary fragment shader** (`frag _agc.main` tokenizes
0-leftover under the existing fragment length rule: `0x2f/0xaf` interpolation + `0xe7` colour store).

## 3. Mesh cmdstream submission — NOT a new work type (DATA-TRACE, `raw/iotrace_summary.txt`, `raw/cmdstream.txt`)

A mesh draw reuses the **same graphics submission path as an ordinary `drawPrimitives`**:

- **Same user clients, same selectors.** IOSurfaceRoot + AGXAcceleratorG17P; **39 `sel-9` (resource-map)
  calls — identical to a draw**. IOKit call count: **mesh 59 ≈ draw 58 ≫ compute 49** (the +1 vs draw is
  one IOSurface bookkeeping call). Shared-memory + doorbell model (no per-submit ioctl, no new "submit"
  or work-queue selector).
- **Single unified graphics submit — NOT compute+draw.** There is **no CDM (compute) launch-descriptor
  BO** in the mesh capture (compute registers one at `0x…b0000`; mesh registers none). So Metal does
  *not* emulate mesh as a compute pre-pass feeding a draw — the object+mesh stages run inside the tiler
  (TA) phase of one graphics submit.
- **Distinct mesh-dispatch VDM record in the tiler stream.** Both mesh and draw build the VDM/tiler
  command stream at fw-ctx `gpu_va 0x18000`. A **draw** ends with the `0x61c4` draw-primitive opcode
  (`…0006 c461 03000000 01000000` = op `0x61c4`, vertexCount 3, instanceCount 1, EXP-0014). A **mesh**
  draw replaces it with a **mesh-grid-dispatch record** (`…00060070` followed by a run of `01000000`
  words = the object/mesh grid dimensions). 3D fixed-function state (`0x58000`) and viewport
  (`0x68000`) are bound exactly as for a draw.
- **Extra intermediate BOs.** Mesh registers a few more tiler-heap BOs (`0x10000018000..0x1000001c500`)
  and a **mesh-specific dispatch-descriptor BO `0x100000f8000`** (carries the object/mesh threadgroup
  dims + setup floats) that a plain draw does not.

## 4. Output-buffer layout — the "UVB" (mesh analogue of the vertex UVS/varying buffer)

- The mesh-output buffer, which the `_agc.mesh.write_uvb` helper calls **UVB**, is where `set_vertex`/
  `set_primitive`/`set_index` stores land. It is a **driver/firmware-allocated intermediate** (the
  tiler-heap cluster `0x10000018000…` + the mesh dispatch-descriptor `0x100000f8000`), **not a
  user-visible buffer**; its base reaches the shader through the **USC/uniform binding** (a `0x67` load
  of a preloaded slot), exactly like a vertex shader's varying (UVS) buffer.
- **Per-vertex layout** (from the `0xe7` store `<field_off>` bytes): the vertex struct is written
  word-by-word at consecutive offsets within the vertex's slot (position float4 then colour float4 in
  our shader), then the fixed-function tiler consumes the UVB + the index/primitive connectivity
  (`0xd7` stores) and rasterizes into the fragment stage.
- **Driver/kernel-interface note:** the UVB and object-payload buffers are **firmware/driver-sized and
  -allocated** (like the tiler parameter buffer, the vertex UVS, and the RT BVH — EXP-0014/0023). A
  Mesa driver hands down the object/mesh grid + the compiled stages; the intermediate buffer allocation
  and the UVB→rasterizer wiring are a **kernel/firmware coordination item**, not a client descriptor
  the shader emits.

## 5. HW validation (`raw/hwval_render.txt`)

`agxrender_mesh` forced the **archived** object+mesh+fragment machine code to run
(`PIPELINE_SOURCE archive`, `MTLPipelineOptionFailOnBinaryArchiveMiss`) and rendered our triangle
`(-0.5,-0.5),(0.5,-0.5),(0.0,0.5)` colour `float4(0,1,0,1)` into a 16×16 BGRA8 target:
```
COVERED 32 of 256          (apex-up triangle, matching the emitted vertices)
ROW  5 .......##.......     ROW  8 ......####......     ROW 11 ....########....
CENTER 8 8 bgra=00ff00ff rgba_unorm=0.000,1.000,0.000,1.000   → exact green
STATUS OK
```
The full HW mesh pipeline (object grid amplification → mesh vertex/primitive emit → rasterize →
fragment) produces the geometrically-correct green triangle from our own archived mesh machine code.

## 6. Capability notes (for the survey / `docs/capability-completeness.md`, `docs/hypotheses.md`)

- **Mesh shading is a genuine HW pipeline but NOT dedicated emit silicon.** Classify **native (pipeline)
  + emulated (emit-via-stores)**: a Vulkan/Mesa mesh-shader implementation must (a) compile object/mesh
  stages as compute-like kernels that **store** vertices/indices/primitives into the mesh-output (UVB)
  buffer (no magic emit op to call), (b) emit the mesh-grid child-count write (amplification), and (c)
  drive the **existing tiler (TA/VDM) path** with a **mesh-dispatch VDM record** (not `0x61c4`, not a
  CDM record) + the same 3D/viewport state as a draw.
- **`0x43`** is the only new opcode group — an object/mesh stage control marker; document it, but the
  driver's emit path is ordinary stores.
- **The UVB / object-payload buffers are firmware-managed** (allocation + rasterizer wiring) — a
  kernel-interface item, like the tiler param buffer, vertex UVS, and RT BVH.
- Mesh primitive topologies (`topology::triangle/line/point`), `max_total_threads_per_threadgroup`, and
  the payload/`mesh_grid_properties` amplification all compile and run on-device.

## 7. Tooling / clean-room / faults

- **Extractor extended (in this experiment dir, not the shared tool):** `harness/shdump_mesh.m`
  (MTLMeshRenderPipelineDescriptor → archive), `harness/mesh_extract.py` (adds `__object`/`__mesh` to
  agxparse's STAGE_SECTIONS), `harness/agxrender_mesh.m` (mesh render round-trip via
  `drawMeshThreadgroups`), `harness/iohello_mesh.m` (iotrace mesh-draw harness). The AppleGPU image's
  `__TEXT,__object` / `__TEXT,__mesh` sections carve exactly like `__vertex`/`__fragment`.
- **`tools/agx-isa/` NOT edited** (per dispatch). New descriptor `obj_mesh_ctrl` (`0x43`) + the
  stage-map/length-rule/emit-lowering/cmdstream facts are in `new_descriptors.json` for the orchestrator.
- **No faults, no reboots.** Every dispatch/draw returned cleanly; the device was stable throughout.

## 8. Follow-ups
- Full bit-decode of the `0x43` marker operand and the mesh-dispatch VDM record opcode (needs a
  mesh-stage splice testbed — extend `agxtest` to a mesh pipeline).
- The exact UVB slot stride / per-primitive region layout (vary vertex/primitive struct sizes) and how
  per-primitive `[[flat]]` data reaches the fragment stage.
- Multi-threadgroup amplification (grid>1) and larger meshes (max verts/prims) — confirm the store loop
  and child-count scale as inferred.
- Mesh-from-object payload sizing limits; `topology::line`/`point`; and whether the mesh output buffer
  size is declared in a descriptor a driver must emit or is firmware-derived from the pipeline.

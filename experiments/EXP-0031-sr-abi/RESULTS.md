# EXP-0031 Results — special-register enum + preloaded-register ABI

Clean-room: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the agx-isa DB schema). Every byte
inspected/spliced/executed is the compiled form of MSL **we wrote**. No Apple binary was
disassembled or introspected. Device: Apple A18 Pro / G17P, macOS 26.6, Metal 4 / Apple9.
**Reboots: 0** (all splices/renders completed; the only non-OK was one expected
compile error for a deliberately-invalid duplicate-attribute kernel).

---

## TL;DR
1. **`get_sr` SR number = BYTE1** (instruction bits [8:16]), **HW-validated** by splicing
   byte1 in a dispatched `out[gid]=builtin` kernel and watching the output become that
   SR's value. **This corrects EXP-0010**, which called byte0's *high nibble* the
   `sr_sel` — that nibble is the **destination GPR**, not the SR select.
2. Full **SR-number → meaning** table for compute + graphics below (§1), each marked
   get_sr / preloaded / computed / folded / interpolated.
3. A **2-byte `mov_imm`** (byte0 low-nibble `0xc`, byte1 = imm8) shares the byte0 nibble
   with the 4-byte `get_sr`; the compiler uses it to constant-fold built-ins
   (`threads_per_simdgroup = 32`). HW-validated (splice 0x20→0x21/0x40/0x11 → 33/64/17).
4. **Vertex `[[stage_in]]` attribute fetch is in-shader software fetch** — Metal lowers the
   `MTLVertexDescriptor` into the VS prologue (`device_load` + format-convert ALU per
   attribute, addressed by `index×stride+offset`). Proven by varying stride/offset/format/
   step and watching the VS code change (§4).
5. Entry ABI per stage, FS epilog, and interpolation contract in §2/§3.

---

## 1. SR-number → meaning table (`get_sr`, byte0 low-nibble `0xC`/`0x4`, 4 bytes)

Encoding (LE 32-bit word): `[b0.lo3=0b100 group][b0.bit3=form][b0.hi4=dst GPR][b1=SR number][b2:b3=suffix]`.
- **SR number = byte1** — **HW-VALIDATED** (splice; see §5 / `raw/splice_validation_compute.txt`).
- **dst = byte0 high nibble** — HW-confirmed (kernels with two get_sr's put each SR in the
  reg the store then reads).
- byte0 low-nibble is `0xc` or `0x4`; **bit3 is a form/width modifier that does NOT change
  which SR is read** (HW-proven: a 0xc-form SR spliced into a 0x4-form slot read correctly).
- suffix `b2:b3` = `0x1006` for a plain 32-bit GPR dst; varies (`1106/1026/0927/0827`) with
  dst-high/type/datapath — full decode is a follow-up.

### Compute (all **HW-validated**: mechanism by splice; specific numbers 0x82/0x85/0x98/0x9c/0xa0/0xa4 splice-confirmed)
| built-in | SR (byte1) | delivery |
|---|---|---|
| `thread_position_in_grid` .x/.y/.z | `0xa0`/`0xa1`/`0xa2` | **get_sr** |
| `thread_position_in_threadgroup` .x/.y/.z | `0xa4`/`0xa5`/`0xa6` | **get_sr** |
| `thread_index_in_threadgroup` | `0xa7` | **get_sr** |
| `threadgroup_position_in_grid` .x/.y/.z | `0x9c`/`0x9d`/`0x9e` | **get_sr** |
| `threads_per_threadgroup` .x/.y/.z | `0x98`/`0x99`/`0x9a` | **get_sr** |
| `threadgroups_per_grid` .x/.y/.z | `0xa8`/`0xa9`/`0xaa` | **get_sr** |
| `thread_index_in_simdgroup` (simd_lane_id) | `0x82` | **get_sr** |
| `simdgroup_index_in_threadgroup` (simd_group_id) | `0x85` | **get_sr** |
| `threads_per_simdgroup` | — | **folded** to `mov_imm 0x20` (=32, Apple9 SIMD width) |
| `simdgroups_per_threadgroup` | — | **computed** = ceil(threads_per_threadgroup/32) from SR 0x98–0x9a |
| `thread_index_in_quadgroup` | — | **computed** = `simd_lane_id(0x82) & 3` |
| `quadgroup_index_in_threadgroup` | — | **computed** from lane(0x82) & simd_group(0x85) |

**The SR space is laid out in dimension-quads** (x,y,z,[flat]): `0x98–0x9a`=threads_per_tg,
`0x9c–0x9e`=threadgroup_pos, `0xa0–0xa2`=thread_pos_in_grid, `0xa4–0xa7`=thread_pos_in_tg
(+ `0xa7`=flat tg index), `0xa8–0xaa`=threadgroups_per_grid.

### Vertex (SR numbers byte-diff-derived; get_sr mechanism HW-validated in compute)
| built-in | SR | delivery |
|---|---|---|
| `vertex_id` | `0xdd` | **get_sr** in `_agc.main` (per-vertex/divergent) |
| `instance_id` | `0xd8` | **get_sr** in `_agc.main` (per-vertex/divergent) |
| `base_vertex` | `0x88` | **get_sr in the uniform/constant program** (draw-uniform) — inferred |
| `base_instance` | `0x8a` | **get_sr in the uniform/constant program** (draw-uniform) — inferred |

### Fragment
| built-in | SR / path | delivery |
|---|---|---|
| `[[position]]` .x/.y | `0xa0`/`0xa1` (pixel x/y) | **get_sr** (z=depth, w=1/w computed/interpolated) |
| `front_facing` | `0xc5` | **get_sr** — **HW-validated both windings** |
| `sample_id` | — | 0x97 path; **folds to 0** on 1-sample target → NOT-YET-CHARACTERIZED (needs MSAA) |
| `point_coord` | — | **interpolated** (0x2f family), not get_sr |
| `barycentric_coord` | — | **interpolated** (0x2f/0x97) — **HW-validated** (gradient) |
| `primitive_id` | — | **flat load** from tiler output (0x1f/0xa7/0x07), not get_sr |

Note: FS `[[position]]` reuses the *same SR numbers* 0xa0/0xa1 as compute grid-position —
the SR namespace is stage-contextual (0xa0/0xa1 = "position x/y" for the running stage).

---

## 2. Preloaded-register ABI per stage (entry-state contract)

**Compute.** *Nothing* holds the thread IDs in a GPR at entry — the shader **must emit
`get_sr`** to materialize each ID/dimension into a GPR (every compute `_agc.main` that uses
`gid` begins with `get_sr`). The only things "preloaded" are in the **uniform register
file**: **buffer base pointers** (selected by `device_load` byte+4 `base_slot`, EXP-0010) and
scalar `constant T&` uniforms; thread-invariant uniform math runs in the `constant_program`
(EXP-0020). So the compute entry contract = *{uniform slots hold buffer bases + scalar
uniforms; IDs via get_sr; no GPR preload}*.

**Vertex.** Same shape: `vertex_id`(0xdd)/`instance_id`(0xd8) via **get_sr in `_agc.main`**;
`base_vertex`(0x88)/`base_instance`(0x8a) via **get_sr in the uniform program** (they are
draw-uniform). The **vertex-buffer base pointer** is **preloaded into a uniform slot**
(`device_load` byte+4 = `base_slot 0x03` in the fetch loads), supplied by the command stream
(EXP-0014 vertex-attribute table @ `gpu_va 0x10000100000` → vtxBuf `+0xa0`). There is **no
GPR preloaded with vertex_id / the attribute base**; the shader reads them (get_sr) and
computes the fetch itself (§4).

**Fragment.** Interpolated varyings and `[[color]]`/`[[stage_in]]` inputs arrive via the
**interpolation datapath** (0x2f/0xaf ops reading per-primitive plane-equation coefficients
loaded by 0x97 from the tiler output), **not** as preloaded GPRs. `[[position]]` (get_sr
0xa0/0xa1) and `front_facing` (get_sr 0xc5) are read on demand. `primitive_id`/`sample_id`
come from the 0x07/0x97/0xa7 memory-varying path. So the FS entry contract = *{no GPR
preload; varyings via interpolation ops; position/front_facing via get_sr; flat inputs via
tiler-output loads}*.

---

## 3. FS input / interpolation / epilog contract (ties to EXP-0029 — coordinated, not duplicated)

- **Varying interpolation** = the low-nibble-`f` family: `0x2f`/`0xaf` (10 B) perform the
  interpolation; a `0x97 04 54 …` (low-nibble-7 memory op) loads the varying's plane-equation
  coefficients from the tiler/geometry output; the `0x2f` ops evaluate it at the fragment's
  barycentric position. `point_coord` and `barycentric_coord` ride this same path.
  HW-validated: `f_bary` produced a smooth 3-channel barycentric gradient (`raw/render_validation.txt`).
- **`[[position]]`**: `get_sr` SR `0xa0` (x), `0xa1` (y) for pixel coords; z/w computed.
- **FS color return (epilog)** — every fragment ends with the **same color-output store**:
  `87 02 54 0c 08 00 | e7 06 54 00 00 00 01 4e 00 00 00 00 | 07 02 54 0c 02 00 | 0e 00 00 00`.
  The `0xe7 06 54 …` is the tilebuffer/color store; the `0x87…`/`0x07…` are the fragment
  output framing. (Full bit-decode of the color-output store is **EXP-0029's** deliverable —
  we only locate the epilog and confirm it is shared across all our fragments.)

---

## 4. VS attribute fetch mechanism (task 4) — **in-shader, shader-specialized**

`attrdump.m` compiled our `VIn{float3 pos[[attribute(0)]]; float4 col[[attribute(1)]];}`
through a real `MTLVertexDescriptor`; the extracted VS prologue is:
```
0c dd 10 06                              get_sr vertex_id (SR 0xdd) -> index
9f 10 54 06 02 00 [80 00] 70 2a 02 00    imad  index * stride  (stride imm here 0x0080)
67 00 54 00 03 00 00 00 5d 01 00 40 22 00   device_load attr0 (base_slot byte+4 = 0x03), 3x32b (float3)
67 00 44 06 03 00 00 00 11 04 02 40 22 00   device_load attr1 (base_slot 0x03), 4x32b (float4) at offset
0b/1b/2b 2f …                            format-convert ALU (per attribute)
… 57 26 54 …                             varying stores (position + color out)
```
Changing one vertex-layout knob changes exactly the expected shader bytes — **proving the
fetch is compiled into the shader** (not fixed-function):

| change | VS delta |
|---|---|
| stride 32→64 | imad immediate `80 00`→`00 01` |
| attr1 offset 16→12 | 2nd load `11 04`→`11 84` |
| attr0 float3→uchar4Normalized | load width `5d 01`→`61 01` (32b→8b) + shift + `1b 00 26` int→float normalize |
| attr1 float4→half4 | load `5d 01`→`09 04` (half) + half→float converts |
| stepFunction perVertex→perInstance | index get_sr `0c dd`(vertex_id)→`0c d8`(instance_id) |

**Conclusion:** on G17P, **vertex fetch = software fetch in the VS prologue**. The compiler
lowers the `MTLVertexDescriptor` into: for each attribute, a `device_load` (0x67, EXP-0012
layout) from a **preloaded vertex-buffer base pointer (uniform `base_slot 0x03`)** at
`address = index × stride + offset`, followed by format-conversion ALU; `index` = get_sr
`vertex_id`(0xdd) or `instance_id`(0xd8) per the step function. **stride/offset/format live
in the compiled shader; the attribute table `0x10000100000` (EXP-0014) supplies the base
pointer.** A driver must therefore either compile fetch into the VS (as Metal does) or set
up an equivalent prologue — there is no fixed-function attribute-fetch descriptor.

---

## 5. HW-validated vs inferred

**HW-validated (splice/observe or render readback):**
- SR number = get_sr **byte1** — splice on `hw_tidx` (grid=64/tg=64): `0x82`→lane[0..31,0..31],
  `0x85`→simd_group[0×32,1×32], `0x98`→threads_per_tg[64], `0x9c`→threadgroup_pos[0×64],
  `0xa4`→pos_in_tg, `0xa0`→pos_in_grid. All exact matches.
- byte0 hi-nibble = dst GPR; byte0 bit3 = form (does not change SR).
- `mov_imm` (2-byte, byte1=imm): `0x20`→32, `0x21`→33, `0x40`→64, `0x11`→17.
- `front_facing` = get_sr `0xc5`: CCW triangle→red 0 (back), CW→red 1 (front).
- `barycentric_coord` interpolation: HW gradient.
- Vertex attribute fetch is shader-specialized: 5 independent layout knobs each move the
  expected VS bytes; per-instance switches the index SR.

**Inferred (byte-diff only, mechanism HW-validated in compute):**
- The graphics SR *numbers* (`vertex_id 0xdd`, `instance_id 0xd8`, `base_vertex 0x88`,
  `base_instance 0x8a`, FS `position 0xa0/0xa1`) — from isolation byte-diffs; the get_sr
  mechanism itself is HW-proven (compute). `base_vertex`/`base_instance` compiled to
  identical code in our (non-indexed, zero-base) draw — the 0x88/0x8a split is byte-diff
  from the uniform-program get_sr's and should be re-confirmed with a base-offset draw.
- get_sr suffix (`b2:b3`) full field decode; the byte0 bit3 form semantics.
- `sample_id` path (folded to 0 on a 1-sample target — needs an MSAA pipeline).

## 6. Recommended next
1. **MSAA pipeline** to characterize `sample_id` (and per-sample interpolation) — currently folds to 0.
2. Confirm `base_vertex`/`base_instance` (0x88/0x8a) with an **indexed draw + baseVertex/baseInstance** so the values are nonzero and distinguishable end-to-end.
3. Full **get_sr suffix decode** (dst-high bits + the 0xc/0x4 form bit) and the **uniform-program get_sr** encoding (vertex base params).
4. Decode the **FS interpolation `0x2f`/`0x97`** ops (perspective/no-perspective/flat/centroid/sample qualifiers) — coordinate with EXP-0029.
5. Attribute-table **bit layout** (`0x10000100000`: which slot supplies the base, per-buffer stride/step) — a cmdstream DATA-TRACE (coordinate with EXP-0014).

## 7. Clean-room status
Clean. Only our own MSL was compiled; only our own compiled bytes were inspected/spliced/
executed. Tools: our `gen_kernels.py`/`run_extract*.py`/`analyze.py`/`harness/attrdump.m`,
reused OWN-SHADER tools `shdump`/`agxparse.py`/`agxrun`/`agxtest.py`/`agxrender` (copied, not
edited). The only third-party input is the public agx-isa DB *schema*. `raw/` holds text/JSON
logs only; `.bin` archives stayed on the device under `~/cleanroom_work/exp0031/`. Per the
parallelism constraint, `tools/agx-isa/` was **not** edited — refined descriptors are staged
in `new_descriptors.json` for the orchestrator to merge.

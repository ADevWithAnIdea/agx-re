# EXP-O2C Results — RT completion tail + tensor ops (A18 Pro / G17P / Apple9)

**Verdict:** Six open follow-ups from EXP-0022/EXP-0023 closed. The `0xcf` matrix
operand selectors are now **HW-splice-validated** (were "inferred"); **RT-from-render**
and **primitive motion blur** are **HW-validated end-to-end**; all MPP tensor ops
lower to the **same** `0xcf`; the `ray_data` payload ABI, the `0x5f` companion op,
the ray-move ops, and the intersector-tag/motion field decodes are established by
byte-diff. Device stable throughout: **no faults, no reboots.**

Capabilities (raw/caps.txt): `supportsRaytracing=1`, **`supportsRaytracingFromRender=1`**,
**`supportsPrimitiveMotionBlur=1`**, `supportsFunctionPointers(FromRender)=1`, Apple9=1.

---

## PART A — Tensor / matrix (O2-F)

### A1. Full `0xcf` operand decode — HW-VALIDATED (task 6)

Spliced each field of the single `0xcf` in `mad_f32` (`r = A·B + C`, distinct known
A,B,C over one 32-lane simdgroup) and classified the read-back against every
candidate product (raw/cf_decode.txt):

```
0xcf @ main+186:  cf 02 56 02 00 04 08 09 d4 43 24 01
                  +0 +1 +2 +3 +4 +5 +6 +7 +8 +9 +10 +11
```

| splice | result | conclusion |
|---|---|---|
| baseline | **A·B+C** | reference |
| +5 `04→08` | **B·B+C** | **byte+5 = A (left) operand register** |
| +6 `08→04` | **A·A+C** | **byte+6 = B (right) operand register** |
| +5/+6 swap | **B·A+C** | confirms +5=A,+6=B (matmul non-commutative) |
| +7 `09→00`/`→04` | garbage accumulate | **byte+7 = C accumulator source reg** (re-confirms EXP-0022) |
| +8 `d4→00`/`→d6` | garbage / relocated | **byte+8 = destination register** |
| +3 `02→00`/`→04` | **zero** | **byte+3 = A-operand sub-descriptor** (load-bearing) |
| +10 `24→00` | **C** (passthrough) | **byte+10 = op-enable marker `0x24`** |
| +11 `01→00` | **A·B** | **byte+11 bit0 = accumulate-enable** (re-confirms) |
| +1 `02→00` | garbage (A) | **byte+1 = dtype** (0x02 f32 → 0x00 f16 mis-reads) |
| +2 `56→54` | **zero** | **byte+2 = mode**; tiled `0x54` on a standalone op zeroes → **semantic, not a liveness hint** |
| +4, +9 | no change | padding / don't-care |

This closes EXP-0022's two follow-ups: the A/B/dst selectors (+5/+6/+8) and the
`0x54`-vs-`0x56` mode question (mode is a semantic accumulator-source change: tiled
mode sources its accumulator from the MPP tile context, so a standalone op forced to
`0x54` produces zero).

Byte-diff corroboration: `mad_ba` (source `b*a`) vs `mad_f32` (`a*b`) differ in
**exactly bytes +5 and +6** (04/08 ↔ 08/04) — independent confirmation that +5/+6
are the two multiply operands (raw/mains.txt).

### A2. MPP tensor ops beyond matmul2d — all lower to `0xcf` (task 5)

`0xcf` counts + move-op inventory across 7 `mpp::tensor_ops::matmul2d` kernels
(raw/structural.txt):

| kernel | shape / variant | `0xcf` | notes |
|---|---|---|---|
| `mm_mul` | 32³ multiply | 255 | reference |
| `mm_mac` | 32³ **multiply_accumulate** | 255 | accumulate adds **no** ops (sets +11 bit) |
| `mm_f32` | 32³ float×float→float | 250 | float path, same op |
| `mm_16` | **16³** multiply | 32 | vs 256 for 32³ → pure `(dim)^3` tiling of 8×8×8 |
| `mm_tl` | 32³ **transpose_left** | 256 | **+35** 4-byte data-move ops |
| `mm_tr` | 32³ **transpose_right** | 256 | **+38** data-move ops |
| `mm_2sg` | 32³ `execution_simdgroups<2>` | 128 | half the tiles per simdgroup |

**No new tensor opcode exists** beyond `matmul2d`'s `0xcf`. Transpose is extra
4-byte data-movement (`ray_move`-family) around the tile loads/stores, not a new op.
`8×8×8` `matmul2d` is rejected at compile (`static_assert`: M or N must be a multiple
of 16) — the MPP tile granularity is ≥16, tiled down to the 8×8×8 HW primitive.

### A3. Matrix load / store / transpose (task 5)

- `simdgroup_load` / `simdgroup_store`, incl. `transpose=true`, = ordinary `0x67`/`0xe7`
  memory ops + moves; the MAC kernel still contains **exactly one** `0xcf`
  (`ls_f32_t`, `mad_at` all → 0 or 1 `0xcf`, transpose in the address/move code).
- There is **no** dedicated matrix-load / matrix-store / matrix-transpose opcode.
  Only the MAC (`0xcf`) is dedicated silicon (confirms + extends EXP-0022 §3).

---

## PART B — Ray tracing tail (O2-C)

### B1. `ray_data` payload copy-in/out ABI (task 1)

Memory-op inventory across payload sizes (caller kernel `_agc.main`;
raw/structural.txt):

| kernel | payload | dev_st | dev_ld | **tg ops** | **calls** | `0x5f` |
|---|---|---|---|---|---|---|
| `call_pnone` | none | 1 | 4 | 0 | 0 | 12 |
| `call_p2` | `float2` | 1 | 4 | 0 | 0 | 13 |
| `call_pbig` | 8×`float` | 1 | 4 | 0 | 0 | 15 |
| `call_pin` | `float2` read-only | 0 | 4 | 0 | 0 | 12 |

- **`ray_data` is a distinct address space backed by RT scratch**, not device or
  threadgroup memory: **zero threadgroup ops**, and the only device store is the
  kernel's own output (`dev_st=1`). The payload copy-in/out rides the **`0x5f`
  RT ray-data memory path**, whose count scales with payload size (12→13→15).
- The custom intersection function is invoked **by the traversal machinery via the
  `intersection_function_table`** (resolved at pipeline-build): the caller emits **no**
  shader CALL (`0x0f`/`0x8f`), `calls=0`. It is a separately-compiled library function
  (not inlined) — EXP-0023's finding, reconfirmed.
- Minimal payloads are cheapest (fewest `0x5f`) — matches WWDC guidance.
- *(Inferred/structural: not splice-validated — the intersection-function payload path
  needs full AS + function-table state.)*

### B2. RT-from-render — HW-VALIDATED end-to-end (task 2)

`rtrender.m`: a **fragment** shader traces a ray (inline `intersection_query`) with
the AS bound via `setFragmentAccelerationStructure:atBufferIndex:`, rendering the
per-pixel hit distance into an 8×8 R32Float target (raw/rtrender.txt):

```
 -1.00 -1.00 -1.00 -1.00 -1.00 -1.00 -1.00 -1.00
 -1.00 -1.00 -1.00  3.00  3.00 -1.00 -1.00 -1.00
 -1.00 -1.00 -1.00  3.00  3.00 -1.00 -1.00 -1.00
 -1.00 -1.00  3.00  3.00  3.00  3.00 -1.00 -1.00
 -1.00 -1.00  3.00  3.00  3.00  3.00 -1.00 -1.00
 -1.00  3.00  3.00  3.00  3.00  3.00  3.00 -1.00
 -1.00  3.00  3.00  3.00  3.00  3.00  3.00 -1.00
  3.00  3.00  3.00  3.00  3.00  3.00  3.00  3.00
```

The exact triangle silhouette (`t=3.00` hit inside the known z=3 triangle, `−1.00`
miss outside). **RT-from-render works.**

- **Lowering is identical to compute RT:** the intersector-object fragment
  (`f_rt_isect`, 1448 B) = 2× `rt_intersect` + 15× `0xdf` + 13× `0x5f` + one −88-byte
  traversal back-edge — structurally the same as the compute intersector (~1530 B).
  The inline-query fragment (`f_rt`, 9654 B, 14 back-edges) mirrors compute
  `intersection_query`. The vertex stage carries **no** RT ops.
- **Difference from compute:** the AS binds to the **fragment argument buffer** and RT
  runs per-fragment; there is **no** fragment-specific RT opcode.

### B3. Primitive motion blur — HW-VALIDATED end-to-end (task 3)

`mbval.m`: a real 2-keyframe motion AS (triangle z=3 @ t=0 → z=5 @ t=1), traced at
5 times (raw/mbval.txt):

| time | hit t | expected |
|---|---|---|
| 0.00 | 3.0000 | 3.0 ✅ |
| 0.25 | 3.5000 | 3.5 ✅ |
| 0.50 | 4.0000 | 4.0 ✅ |
| 0.75 | 4.5000 | 4.5 ✅ |
| 1.00 | 5.0000 | 5.0 ✅ |

The `intersect()` **time parameter drives hardware linear motion interpolation** (exact).
**No new opcode, no new field.** How motion is encoded in `rt_intersect` op#1
(raw/rt_ops.txt):

```
tag_tri   d4 ea 90 a6 8b 00 00 00   const-origin, primitive AS
mb_prim   e4 ea 10 46 bb 00 00 00   MOTION, device time  (byte+2 0x10, +3 0x46, +4 0xbb)
mb_const  e4 ea 10 26 bb 00 00 00   MOTION, const time   (byte+3 0x26)
mb_inst   e4 ea 90 26 1b 00 00 00   INSTANCE motion (instance AS byte+4 0x1b)
```

- **byte+4 = AS-type selector:** `0x8b` primitive · `0x1b` instance · **`0xbb`
  primitive-motion AS** (new).
- **byte+2 = `0x10`** (the dynamic/time-parameterised form) for motion even with a
  const origin.
- **byte+3 = the ray-parameter register carrying TIME:** device-loaded `0x46` vs
  folded-constant `0x26`.
- Motion adds ~5 extra `0xdf` AS-data loads (20–22 vs 15) for the time-interpolated
  vertex fetch.

### B4. Intersector tags / custom primitive + `0x5f`/ray-move decode (task 4)

**Primitive tag does NOT change the intersect op** (raw/rt_ops.txt):

| tag | op#1 | note |
|---|---|---|
| triangle | `d4 ea 90 a6 8b 00 00 00` | reference |
| **bounding_box** | `d4 ea 90 a6 8b 00 00 00` | **byte-identical to triangle** |
| **curve** | `e4 ea 90 a6 8b 00 00 00` | differs only in byte0-hi (dst reg) |
| force_opacity(opaque) | `d4 ea 90 a6 8b 00 00 00` | identical |
| world_space (instance) | `e4 ea 90 a6 1b 00 00 00` | instance AS (byte+4 `0x1b`) |

Discrimination lives in the **AS + intersection-function-table**, not the opcode
(bounding_box compiles + lowers identically; curve is supported and differs only in
the result-read op#2 that extracts `curve_parameter`).

**`0x5f` companion op** (14 B, memory-family, byte+2 `0x54`): the store/spill sibling
of the `0xdf` AS-load; 12–28 per intersector (28 in instance-motion); carries ray/
traversal-stack state + the `ray_data` payload. Decoded as a memory-family op; field
bit-packing inferred. **`rt_transform_test`** (`0x?2`, byte+2 `0x27`, 10 B): the
ray-vs-node transform / AABB slab-test ALU inside traversal (~4–5/kernel).
**`ray_move`** (`0x?b`, byte+2 `0x80`/`0x81`, 4 B): marshals the ray struct
(origin/dir/tmin/tmax + payload) into the register block `rt_intersect` consumes
(`0x80`=zero-init a const component, `0x81`=copy a computed reg); reused 35–38× for
matmul2d transpose data movement.

---

## HW-validated vs inferred

| finding | status |
|---|---|
| `0xcf` +5=A, +6=B, +7=C, +8=dst, +3=A-subfield, +10=op-enable, +11=accumulate, +1=dtype, +2=mode(semantic) | **HW-validated** (splice) |
| MPP tensor ops → same `0xcf`; transpose/load/store = memory+moves | **HW-observed** (op-count diff; MAC itself HW-validated EXP-0022) |
| RT-from-render works + identical lowering | **HW-validated** (end-to-end render) |
| Primitive motion blur: time → linear interpolation | **HW-validated** (end-to-end) |
| motion `rt_intersect` fields (byte+4 `0xbb`, byte+2 `0x10`, byte+3 time) | inferred (byte-diff) + corroborated by the HW interpolation |
| `ray_data` = distinct address space via `0x5f` RT scratch; no CALL/threadgroup | inferred (structural byte-diff) |
| primitive-tag independence of the intersect op | inferred (byte-diff; bbox byte-identical) |
| `0x5f` / `rt_transform_test` / `ray_move` field bit-packing | inferred (byte-diff) |

## Recommended next

1. Extend `agxtest` to build+bind an AS so the RT ops (`0x5f`, `rt_transform_test`,
   `ray_move`, `rt_intersect` operands) can be **splice-validated** like `0xcf`.
2. HW-validate the **curve** hit and the **custom bounding-box intersection function
   + payload** end-to-end (curve-geometry + `intersection_function_table` harnesses).
3. Decode the `0xcf` intra-byte register encoding (is `a_reg = (reg<<1)|size`?).
4. Chase the WWDC RT "reorder/sort" stage — still not a single visible opcode
   (likely scheduler/coherency, out of the shader ISA).

## Tooling / faults

- `new_descriptors.json` (schema-validated) updates `matrix_mac` + `rt_intersect`
  and adds `rt_ray_mem` (`0x5f`), `rt_transform_test`, `ray_move`, with length-rule
  additions — for the orchestrator to merge into `tools/agx-isa/`.
- **No faults, no reboots.** Every dispatch (37 extractions, the `0xcf` splice sweep,
  the AS builds + trace/render) returned cleanly; device stable throughout.

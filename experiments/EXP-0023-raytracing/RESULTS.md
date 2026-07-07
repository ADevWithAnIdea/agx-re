# EXP-0023 Results — hardware ray tracing (A18 Pro / G17P / Apple9)

**Verdict: HYBRID — dedicated hardware ray-intersection instructions driving a
compiler-generated (software) BVH-traversal loop.** `raytracing::` shaders emit
**novel opcode groups** that a hand-written software ray/triangle loop never
produces (proving dedicated RT silicon), but the traversal itself is shader code
(a back-edge loop), **not** a single fire-and-forget "trace ray" instruction.
The end-to-end trace is **HW-validated** (a known ray vs a known triangle in a
real `MTLAccelerationStructure` returns the correct hit).

Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / Apple9.
`supportsRaytracing = YES`. SIP off. No faults, no reboots.

---

## 1. Dedicated HW vs software traversal — the deciding evidence

Compiled our own `raytracing::` kernels (`kernels/rt.metal`: intersector object,
intersection_query, instancing, function-table) and a hand-written **software**
Möller-Trumbore ray/triangle loop (`kernels/hand.metal`), carved `_agc.main`, and
compared opcode inventories (`raw/mains.txt`, `raw/intersect_diff.txt`, `raw/rtops.txt`).

| kernel | bytes | dedicated intersect op (`X4/ea`) | AS-data load `0xdf` | traversal loops (back-edges) |
|---|---|---|---|---|
| `isect_dist` (intersector) | 1530 | **2** | 15 | **1** (−88) |
| `isect_trace` (reads t+prim+bary) | 1506 | **2** | 16 | 1 (−88) |
| `isect_anyhit` (accept_any) | 1516 | **2** | 15 | 1 (−88) |
| `isect_instance` (instance AS) | 1862 | **2** | 17 | 1 (−88) |
| `isect_dynray` (dynamic ray) | 1608 | **2** | 14 | 1 (−88) |
| `rq_trace` (intersection_query) | 9500 | **2** | 37 | **15** |
| `trace_custom` (+ fn-table) | 1586 | **2** | — | 1 (−88) |
| **`hand_trace` (SW Möller-Trumbore loop)** | 514 | **0** | **0** | 1 (its own tri loop) |
| **`hand_one` (SW single triangle)** | 248 | **0** | **0** | 0 |

**Deciding facts:**
1. **Novel opcode groups exist and are RT-exclusive.** Every `raytracing::` kernel
   emits a dedicated **ray-intersect op** (byte0 low-nibble `0x4`, byte+1 `0xea`) and
   dedicated **acceleration-structure/ray-data loads** (byte0 `0xdf`). The hand-written
   software ray/triangle loop — *exactly the code a software lowering would produce* —
   contains **zero** of either. ⟹ **dedicated ray-tracing hardware instructions.**
   (Same style of proof as EXP-0022's matrix `0xcf`: a novel group present in the HW
   path and absent from the hand-written control.)
2. **But traversal is shader software, not one instruction.** The intersector kernels
   are ~1530 B (vs the ~250 B a single trace instruction would need) and each contains
   **one BVH-traversal back-edge loop** (offset −88); its body holds a `0xdf` AS-node
   load + a `0x0a` compare-predicate (the loop condition) + RT ops. `intersection_query`
   (the inline API) is 9500 B with **15** loops. The dedicated intersect op appears only
   **twice** (setup + result-read), *outside* the loop — it does **not** iterate per node.
   ⟹ Apple9 RT = **hardware ray/box/triangle intersection primitives + shader-driven
   BVH traversal**, not autonomous hardware traversal.

## 2. The dedicated ray-intersect instruction (`rt_intersect`, byte0 low-nibble `0x4`, 8 bytes)

Signature: **byte0 low-nibble `0x4`** (byte0 HIGH nibble = result register),
**byte+1 == `0xea`** (constant intersect sub-opcode). Emitted **exactly twice** per
RT kernel. Byte-diff of op#1 across provocations (`raw/intersect_diff.txt`):

```
kernel            b0 b1 b2 b3 b4 b5 b6 b7   provocation
isect_dist        d4 ea 90 a6 8b 00 00 00   origin=0, dir=devload, primitive AS  (baseline)
isect_anyhit      d4 ea 90 a6 8b 00 00 00   + accept_any_intersection(true)   [IDENTICAL]
isect_trace       94 ea 90 86 8b 00 00 00   different result registers
isect_instance    e4 ea 90 a6 1b 00 00 00   instance AS + instancing tag  (byte+4 8b->1b)
isect_dynray      a4 ea 10 46 cb 00 00 00   origin/dir/tmin/tmax all device-loaded
rq_trace          f4 ea 10 66 6b 00 00 00   intersection_query (inline)
trace_custom      24 ea d0 a6 ab 00 80 00   + intersection_function_table (byte+2 0xd0, byte+6 0x80)
```

| byte | field | meaning | status |
|---|---|---|---|
| +0 lo | group | `0x4` = ray-intersect group | ✅ (present iff RT) |
| **+0 hi** | **dst** | result/destination register (r2,r9,r13,r14,r15…) | inferred (byte-diff) |
| **+1** | subop | `0xea` = intersect (constant across all RT kernels) | ✅ constant |
| **+2** | **mode** | `0x90` origin-const · `0x10` dynamic origin · `0xd0` origin-const **+ fn-table** (bit7=const-origin, bit6=fn-table, bit4 base) | inferred |
| +3 | opA | ray operand register (direction) | inferred |
| **+4** | opB | ray/AS operand register — **instance AS flips `0x8b`→`0x1b`** | inferred |
| +5 | — | `0x00` observed | — |
| **+6 bit7** | fn-table | set when an `intersection_function_table` is bound (`trace_custom` only) | inferred |
| +7 | — | `0x00` observed | — |

- **op#2** (`X4 ea 10/11 ..`, trailing `26 9f`) = read/commit the intersection result;
  the `26 9f` tail feeds an integer-ALU (`0x9f`) result unpack.
- `accept_any_intersection` does **not** change the intersect op (isect_dist ≡ isect_anyhit
  byte-for-byte) — it is handled elsewhere in the traversal logic.
- **Companion RT opcodes** (present in RT, absent from the SW control): `0xdf` 14-byte
  **AS/ray-data load** (memory-family sibling of `0x67`/`0xe7`, byte+2 `0x54`), a `0x5f`
  14-byte memory sibling, RT-specific 4-byte moves in the `0x?b` group (byte+2 `0x81`/`0x80`
  — ray-register marshalling, distinct from the `0x01` uniform-mov), and a 10-byte
  `0x?2` transform/test op (byte+2 `0x27`). These are documented as follow-ups; `rt_intersect`
  and `rt_as_load` are added to `tools/agx-isa`.

Field semantics are **inferred (byte-diff)**, not splice-validated: splicing an RT op in
isolation would require reproducing the full acceleration-structure + traversal state, which
our `agxrun_persist` compute testbed does not set up. The op's *role* (dedicated intersect)
and end-to-end correctness are HW-validated (§5).

## 3. Acceleration-structure referencing + what is firmware/kernel-managed

Captured with `tools/iotrace` (read-only) over our own `rtval` harness building a real AS
(`raw/asref.txt`, `raw/iotrace_summary.txt`):

- **The AS is referenced from the shader by its 8-byte GPU virtual address**, written into
  the **Tier-2 argument buffer** — but in a **distinct descriptor region** from plain buffers.
  In our capture the bound buffers (indices 1/2/3) sit at arg-buffer offsets `0x1550/0x1558/0x1560`
  (inline 8-byte VAs, as EXP-0011 found), while the acceleration-structure VA (`0x1000005c000`)
  sits at `0x1620` and is also registered in the GPU **residency/resource tables**. So an AS
  binds like a resource-by-VA, in its own arg-buffer slot; the shader's opening `0x67` loads
  fetch the AS header/root from that VA before entering the traversal loop.
- **The AS *build* is GPU/firmware-managed — flag for the kernel team.** `buildAccelerationStructure`
  goes through an `MTLAccelerationStructureCommandEncoder` → a GPU command buffer (same
  shared-memory ring as compute; **61 IOKit calls**, BO registration via `AGXAcceleratorG17P`
  selector 9). Userspace supplies only the **vertex buffer + a build descriptor**; the GPU/firmware
  writes the BVH into the AS BO. The captured AS BO (`0x1000005c000`) contains a **GPU-authored**
  node structure with the triangle vertices embedded as floats (`bf800000`=−1.0, `40400000`=3.0
  visible in the header) in a layout **userspace never constructs**. ⟹ The BVH node format is
  **not userspace-visible/emitted**; document only that userspace hands down geometry + a build
  command and references the finished AS by VA.

## 4. Intersection functions & `ray_data` payload

`kernels/isectfn.metal` (`[[intersection(bounding_box, triangle_data)]]` + `ray_data` payload,
invoked via `isect.intersect(r, accel, ftab, payload)`) compiles on-device:

- The custom intersection function (`sphereIsect`) is a **separately-compiled callable
  function** — it appears in the library's function list **alongside** the kernel and is **not**
  inlined into the traversal kernel (`shdump: functions = sphereIsect trace_custom`).
- It is referenced through an **`intersection_function_table` bound as an argument-buffer slot**
  (here `[[buffer(1)]]`) — the **same function-table binding model as `visible_function_table`**
  (the USC/function-pointer binding, feature-map A11). The bound table sets **byte+2 `0xd0`** and
  **byte+6 bit7** in the `rt_intersect` op (§2), so the intersect op itself carries a "call the
  bound intersection function" flag.
- The `ray_data` payload is a distinct address space threaded into the intersection function
  (copy-in/out around the call); minimal payloads are cheapest (WWDC best practice).

## 5. HW validation — known ray vs known triangle (`raw/hwval.txt`)

`rtval.m` builds a real primitive AS with triangle `v0(-1,-1,3) v1(1,-1,3) v2(0,1,3)`, traces
known rays on the GPU, reads back `t / primitive_id / barycentrics`. **All correct** — the
barycentrics reconstruct the exact hit point `hit = (1-u-v)·v0 + u·v1 + v·v2`:

| ray origin (dir +z) | t | prim | bary (u,v) | reconstructed hit | ✓ |
|---|---|---|---|---|---|
| (0,0,0) | 3.000 | 0 | (0.250,0.500) | (0,0,3) | ✅ |
| (0.3,−0.3,0) | 3.000 | 0 | (0.475,0.350) | (0.3,−0.3,3) | ✅ |
| (−0.3,−0.3,0) | 3.000 | 0 | (0.175,0.350) | (−0.3,−0.3,3) | ✅ |
| (0,−0.5,0) | 3.000 | 0 | (0.375,0.250) | (0,−0.5,3) | ✅ |
| (0,0.5,0) | 3.000 | 0 | (0.125,0.750) | (0,0.5,3) | ✅ |
| (0,3,0) [above apex] | −1 (miss) | — | — | correct MISS | ✅ |

This proves the full lowering is semantically correct: dedicated intersect ops + software
traversal produce the exact ray/triangle intersection, distance, primitive id and barycentrics.

## 6. Capability notes (for the survey / `docs/hypotheses.md`)

- **Apple9 has dedicated ray-tracing HW instructions** (a driver must emit the `0x4/0xea`
  intersect op + `0xdf` AS-data loads, not a pure-ALU BVH walk), **but traversal is a
  shader loop** — a Vulkan/Mesa RT implementation must generate the traversal loop + stack in
  the shader and call the intersect/box/triangle-test ops, not expect an autonomous "trace" op.
- **The BVH build is GPU/firmware-managed and its node format is opaque to userspace.** A
  driver hands geometry + a build command to the GPU and references the finished AS by GPU VA;
  it does not author BVH nodes (**coordinate with the kernel/firmware team** on the builder).
- **Both APIs are shader-traversal:** the `intersector` object and `intersection_query` both
  lower to the same dedicated ops; `intersection_query` (inline) is far larger (9500 B, 15 loops)
  — WWDC's advice to prefer the intersector on Apple9 is borne out by code size.
- **Intersection functions bind via `intersection_function_table` at an argument-buffer slot**
  (function-table / USC model), and set a flag in the intersect op.
- `supportsRaytracingFromRender` / `supportsPrimitiveMotionBlur` are YES (not exercised here;
  follow-ups).

## 7. Tooling / round-trip / faults

- `tools/agx-isa/`: added two descriptors — **`rt_intersect`** (byte0 low-nibble `0x4` +
  byte+1 `0xea`, 8 B) and **`rt_as_load`** (`0xdf`, 14 B) — with the length-rule entries and
  `byte0_table` notes; `db.json` regenerated (**38 descriptors**). `roundtrip_test.py` extended
  with 5 real RT instructions + 2 synthesized — **ALL PASS (188/188)**.
- **No faults, no reboots.** Every dispatch (incl. the AS build + trace) returned cleanly; the
  device was stable throughout.

## 8. Follow-ups

- Full field bit-decode of `rt_intersect` operands (ray origin/dir/tmin/tmax register packing)
  and op#2's result layout — needs an AS-aware splice testbed (extend `agxtest` to build an AS).
- Decode the companion RT groups: `0x5f` memory sibling, the `0x?2`/`0x27` transform/test op,
  the `0x?b` (byte+2 `0x81`/`0x80`) ray-register moves.
- The "reorder/sort stage" WWDC mentions is not visible as a single instruction here — determine
  whether it is a scheduler/coherency feature (out of the shader ISA) or a separate opcode.
- `supportsRaytracingFromRender` (RT in a fragment shader) and `primitive_motion` / `instance_motion`
  motion-blur lowering.
- BVH node format (firmware-produced) — for the kernel team, not userspace.

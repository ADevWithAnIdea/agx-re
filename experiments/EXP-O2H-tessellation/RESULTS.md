# EXP-O2H Results — tessellation on A18 Pro / G17P / Apple9

**Verdict: NATIVE GRAPHICS/TILER-PATH STAGE — NOT compute-emulated, NOT the mesh record.** On A18/G17P,
`drawPatches` is a **single unified graphics submit** whose tessellation runs inside the tiler (TA) phase.
With CPU-written tessellation factors (no user compute encoder), a `drawPatches` submit registers the
**same set of buffer objects as a plain `drawPrimitives`** — critically, **no CDM (compute) launch
descriptor and no mesh dispatch-descriptor**. It drives a **distinct VDM patch-dispatch record** (opcode
high-byte `0x40`, vs draw `0x61c4`, vs mesh `0x70000600`) that carries the patch **domain type**
(`+0x8c`: triangle=1 / quad=2) and a packed **config word** (`+0x68`: control-point count + partition
mode). Tessellation factors are **IEEE half-floats** (`MTL*TessellationFactorsHalf` layout). The
post-tessellation vertex function compiles to an **ordinary vertex shader** (no novel opcode). End-to-end
**HW-validated**: our tessellated triangle and quad render correctly, and a level-dependent bulge proves
the hardware actually subdivided the patch.

This **revises `docs/capability-matrix.md` §2**, which assumed tessellation is "emulate" (the M1/M2
default). A18 has a native tessellation path, structurally in the **same class as mesh shading**
(EXP-0030): a fixed-function/firmware amplification stage feeding compute-like shader stages, driven by a
tiler-stream dispatch record — no compute pre-pass.

Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Metal 4 / Apple9. **No faults, no reboots**; every
submit returned `status=4` (completed), 16× `STATUS OK`.

---

## 1. Does tessellation render correctly on A18? (HW-validated)

Our own compute-writes-factors → `drawPatches` pipeline (`kernels/tess.metal`, `harness/tess.m`) renders
the expected geometry (`raw/stdout/`):

| variant | expected | COVERED | status |
|---|---|---|---|
| triangle patch, level 8, 48×48 | apex-up triangle | 722 / 2304, center non-black | OK (4) |
| triangle patch, `--cpu-factors` | identical to above | 722 / 2304 | OK (4) |
| quad patch, level 8, 48×48 | full quad | 1444 / 2304 | OK (4) |
| quad patch, `--cpu-factors` | identical | 1444 / 2304 | OK (4) |

**Subdivision proof (HW-validated).** With a domain-coordinate **bulge** whose displacement is zero at
the patch corners and peaks on the interior/edges, the rendered silhouette can only change if the
hardware generates interior/edge domain points — i.e. actually subdivides. Coverage grows **monotonically**
with the tessellation level (triangle patch, bulge 0.25, 96×96):

| level | 1 | 2 | 4 | 8 | 16 |
|---|---|---|---|---|---|
| COVERED | 2888 | 3294 | 3334 | 3354 | 3362 |

Level 1 = the flat triangle (only the 3 corner points, no bulge); higher levels sample the bulged edges
progressively more finely, converging to the smooth curved silhouette. The tessellator ran on hardware.

## 2. Native HW / mesh-path / compute-emulated? — the deciding evidence

### 2.1 The BO inventory: `drawPatches` (cpu-factors) == a plain draw; a compute dispatch is a distinct cluster
`raw/analysis/bo_inventory.txt` / `bo_vaset.txt`. Registered-BO clusters per capture:

| capture | has compute cluster `0x100000a0000..e0000`? | has mesh dispatch-desc `0x100000f8000`? | VDM patch record? |
|---|---|---|---|
| `draw` (plain `drawPrimitives`) | **no** | no | `0x61c4` draw |
| `compute` (`dispatchThreads`) | **yes** (a0000/b0000/e0000, CDM launch desc) | no | — (CDM only) |
| **`tess_cpu`** (`drawPatches`, CPU factors, **no compute encoder**) | **no** | **no** | **`0x40…` patch** |
| `tess_comp` (`drawPatches` + our factor kernel) | **yes** (our kernel's CDM reappears) | no | `0x40…` patch |
| `tess_q_cpu` (quad, CPU factors) | **no** | **no** | `0x40…` patch |

The compute-launch-descriptor cluster (`0x100000a0000..0x100000e0000` — a CDM record BO) is present **iff
there is a compute dispatch**: it appears for `compute` and for `tess_comp` (our explicit factor kernel),
and is **absent** for `draw` and for **`tess_cpu`**. So `drawPatches` **by itself dispatches no compute** —
the tessellator is not a Metal compute pre-pass. `tess_cpu` registers the identical BO layout to a plain
draw (code BO, tiler-heap cluster `0x10000018xxx`, tiler-param `0x80000`, USC/attachment BOs, fw-ctx
`0x18000/0x58000/0x68000`). This is the same discriminator EXP-0030 used for mesh (mesh had "no CDM"), but
tessellation adds **neither** a CDM **nor** a mesh dispatch-descriptor — it is even closer to a plain draw.

IOKit call counts (`raw/analysis/callcounts.txt`): `draw` 58, `compute` 49, **`tess_cpu` 62**, `tess_comp`
66, `tess_q_cpu` 62. `tess_cpu`'s +4 vs `draw` are the 4 extra `sel-9` resource maps for our factor /
control-point / level / bulge buffers — **not** a second (compute) submit. Invariant across factor source.

**Where the tessellation work lives instead of a CDM:** the differences between `tess_cpu` and `draw` are
in **content**, not BO set — the tiler-parameter buffer `0x10000080000` jumps from **640 → 3511** nonzero
bytes, and the code BO `0x10000000000` grows (post-tess VS + tessellator setup). The domain-point
generation is folded into the **tiler (TA) phase** (firmware/fixed-function), exactly as mesh's grid
amplification is — no user-visible generated-vertex buffer; the post-tess VS writes varyings into the same
tiler-heap/UVS mechanism a normal vertex shader uses.

### 2.2 The VDM patch-dispatch record (`0x18000`) — a distinct opcode, in the tiler stream (HW-correlated)
`raw/hex/{draw,tess_cpu}_18000.hex`, `raw/analysis/vdm_*`. The patch record sits at the **same offset in
the same tiler/VDM stream** (`0x18000`) where the draw record (`0x61c4`, EXP-0014) and the mesh
grid-dispatch record (`0x70000600`, EXP-0030) live — a single graphics command stream.

```
plain draw   +0x64:  00 06 c4 61   03 00 00 00   01 00 00 00     op 0x61c4, prim=tri(0x06), vtx=3, inst=1
tess (tri)   +0x64:  90 00 00 40   00 00 a0 47   00 3c 00 00     op high-byte 0x40 (distinct patch record)
             +0x70:  00 0c f0 b2   00 83 01 00   01 00 00 00 ...
             +0x88:  .. .. .. ..   01 00 00 00   01 00 00 00     (+0x8c domain=1, +0x90 patchCount=1)
```

HW-correlated fields (single-parameter diffs, `raw/analysis/vdm_tri_v_quad.txt`, `part_full_*`):

| field | meaning | evidence | status |
|---|---|---|---|
| `+0x67` high-byte `0x40` | **patch-dispatch opcode** (≠ draw `0x61c4`, ≠ mesh `0x70`) | draw↔tess diff | **HW-validated** |
| **`+0x8c`** = 1 / 2 | **patch DOMAIN type: triangle=1, quad=2** | tri↔quad flips exactly this word | **HW-validated** |
| `+0x68` packed dword | **control-point count + partition mode** (packed config) | tri↔quad & partition diffs | HW-correlated (packed) |
| `+0x90` = 1 | patch count (=1 patch drawn) | constant here | inferred |
| `+0x6c` = `0x00003c00` | half `1.0` — tess factor scale (`scaleEnabled=NO`) | constant | inferred |
| `+0x74` = `0x00018300` | low bits of our factor-buffer VA `0x10000018300` | VA overlap | inferred |
| `+0x0c` (record header) | state-size/length word (grows w/ compute) | cpu↔comp diff | HW-validated (per EXP-0024) |

The `+0x68` packed config word (control-point count **and** partition mode share it):

| variant | `+0x68` dword | note |
|---|---|---|
| triangle, integer partition | `0x47a00000` | baseline |
| quad, integer partition | `0x47b00000` | cp-count 3→4 : bit ~20 (byte `+0x6a` 0xa0→0xb0) |
| triangle, pow2 partition | `0x07a00000` | partition: bit30 cleared |
| triangle, fractional-odd | `0x87200000` | partition: high nibble + `+0x6a` 0xa0→0x20 |

Bit-level separation of cp-count / partition / winding inside `+0x68` needs a fuller single-variable
matrix (follow-up); the two **cleanly isolated** fields are the opcode (`+0x67`=0x40) and the domain type
(`+0x8c`). **Partition mode is NOT in the `0x58000` fixed-function state pool** — the `0x58000` diff across
integer/pow2/fractional-odd/fractional-even is **byte-identical** (`raw/analysis/part_58k_*`, 0 differing
words); it lives in this VDM patch record (`+0x68`) and/or the tiler-param buffer.

### 2.3 The post-tessellation vertex function is an ordinary vertex shader (OWN-SHADER)
`raw/code/tess_tri_report.txt`, `*_vertex.hex`. The tessellation render-pipeline archive carries a
`__TEXT,__vertex` + `__TEXT,__fragment` section — the post-tess VS is compiled as a **normal vertex
stage**, *not* a special stage section (mesh had `__object`/`__mesh`). Byte census of our own compiled
bytes (`raw/code`): **zero** occurrences of any known novel opcode — no `0x43` (mesh/obj marker), no
`0xcf` (matrix), no `0xea` (rt-intersect), no `0x70`. The top opcodes are ordinary vertex-shader ops
including **`0x57` varying-stores** (×8 in the triangle VS — the UVS varying store, EXP-0037/G1a). So the
domain shader is a plain vertex shader that reads control points + the domain coordinate
(`[[position_in_patch]]`) and writes varyings; there is **no dedicated tessellation ISA op**. (How
`[[position_in_patch]]` is delivered — `get_sr` vs a firmware-buffer load — is a follow-up needing the
vertex-stage tokenizer.) This mirrors mesh (EXP-0030): the *pipeline* is hardware; the *shader* is
ordinary.

## 3. What a Mesa driver must do; tessellation-factor format

### 3.1 Tessellation-factor buffer format (HW-validated)
`raw/analysis/factorbuf.txt`, `factordiff_*`. Our factor buffer (VA `0x10000018300`) holds the half-float
factors we wrote; varying `--level` moves exactly the packed halfs and the render responds:

| level | factor bytes (first dword) | half value |
|---|---|---|
| 1 | `0x3c003c00` | `0x3c00` = **1.0** |
| 4 | `0x44004400` | `0x4400` = **4.0** |
| 16 | `0x4c004c00` | `0x4c00` = **16.0** |

So the format is **IEEE binary16 (half) factors, packed contiguously, one per edge then the inside
factor(s)** — exactly `MTLTriangleTessellationFactorsHalf` (edge[3] + inside = **4 halfs = 8 B**) and
`MTLQuadTessellationFactorsHalf` (edge[4] + insideX + insideY = **6 halfs = 12 B**). The buffer is an
ordinary user `MTLBuffer` bound via `setTessellationFactorBuffer:` and referenced from the graphics
stream (its VA low bits appear in the VDM patch record, §2.2). `MTLTessellationFactorFormatHalf` is what
Metal exposes; the `.float` variant was not exercised (follow-up).

### 3.2 Driver guidance (revises `capability-matrix.md` §2 tessellation = "emulate")
A18 has a **native tessellation path**; a Mesa/Vulkan driver has two options, and this experiment
establishes that emulation is now **optional**, not mandatory:

- **Native path (new; what Apple's Metal does):** compile the post-tessellation vertex function as an
  ordinary vertex shader; supply the tessellation factors as a half-float `MTLBuffer` (§3.1); and drive
  the **tiler-stream VDM patch-dispatch record** (opcode `+0x67`=0x40; domain type `+0x8c`=1/2; packed
  control-point-count + partition `+0x68`) instead of a `0x61c4` draw — **no compute pre-pass, no CDM**.
  The domain-point generator (tessellator) and the generated-domain/UVS buffers are **firmware-managed**
  (like mesh's grid amplification + UVB, and the tiler param buffer): a **kernel-interface item**, not a
  client descriptor the driver hand-assembles. This retires the D3D11-reference compute tessellator on A18
  *if* the kernel/firmware exposes the patch-dispatch path (the same dependency mesh has).
- **Compute emulation (portable fallback, unchanged):** the existing `libagx` D3D11-reference tessellator
  (VS→TCS→compute tessellator→draw) still works and needs no firmware tessellation support. Keep it as the
  generation-agnostic path; on A18 the native tiler path is the faster option once the kernel supports it.

Either way the **tessellation-factor format (half) and the Metal-level pipeline shape are identical** — the
choice is only *how the domain points are generated* (firmware tiler stage vs a compute kernel).

## 4. HW-validated vs inferred; kernel/firmware pieces; recommended next

**HW-validated (a dispatch/draw confirmed it):**
- Tessellation renders correctly (triangle + quad); subdivision is real (level-dependent bulge coverage).
- `drawPatches` (cpu-factors) is a **single graphics submit with no CDM / no compute cluster** — the same
  BO set as a plain draw (the compute cluster appears iff a compute dispatch is present). → **native
  tiler-path, not compute-emulated.**
- Distinct VDM patch record opcode (`+0x67`=0x40) in the tiler stream `0x18000`; **domain type `+0x8c`
  triangle=1/quad=2**; partition mode is **not** in the `0x58000` state pool.
- Tessellation-factor format = IEEE half, `MTL*TessellationFactorsHalf` layout (level 1/4/16 → 1.0/4.0/16.0).
- Post-tess VS = ordinary vertex shader, **no novel opcode** (OWN-SHADER census).

**Inferred (byte-diff / VA-overlap, not splice-validated):**
- The `+0x68` packed word's exact sub-bit split (cp-count vs partition vs winding); the factor-buffer
  pointer field (`+0x74` overlaps our factor VA low bits); `+0x6c` half-1.0 = factor scale; `+0x90` = patch
  count.

**Kernel/firmware-managed (below the userspace boundary — flag for the kernel team, like mesh's UVB/tiler
param):**
- The **tessellator (domain-point generator)** itself and the **generated-domain / UVS buffers** — folded
  into the tiler (TA) phase, sized/allocated by firmware; the bulk of tessellation state lands in the
  firmware-managed tiler-parameter buffer `0x10000080000` (640→3511 nonzero). Whether the generator is
  hardened silicon or firmware microcode is not userspace-visible and does not change the driver contract.

**Recommended next:**
1. Fully decompose the `+0x68` packed patch-config word (single-variable matrix over cp-count × partition ×
   winding × `maxTessellationFactor`), and confirm the factor-buffer pointer field by moving the buffer.
2. Isoline domain (`[[patch(...)]]` isolines), `drawIndexedPatches` (+ control-point index buffer),
   `tessellationFactorStepFunction perPatch/perInstance` + `instanceStride`, and the `.float` factor format.
3. Decode how `[[position_in_patch]]` reaches the post-tess VS (needs the vertex-stage tokenizer; shared
   with the mesh `set_vertex`/UVB follow-ups).
4. Coordinate with the kernel team on the tessellator + generated-domain buffer contract (shares the mesh
   UVB / tiler-param kernel-interface items).

## 5. Clean-room / tooling / provenance
- **Clean-room: DATA-TRACE + OWN-SHADER.** Our own MSL (`kernels/tess.metal`), our own draws; we logged
  non-copyrightable command-buffer/descriptor bytes and inspected only **our own** compiled shader bytes.
  Metal's tessellator/domain setup code was **located, never disassembled** (CLAUDE.md rule 5). No Apple
  binary was introspected.
- New harness (this dir): `harness/tess.m` (compute-or-cpu factors + `drawPatches` + readback + VA print),
  `harness/shdump_tess.m` (serialize a tessellation render pipeline → archive for own-shader extraction),
  `kernels/tess.metal`, `run.sh`. Reused **verbatim** from `tools/` (copied at runtime, not committed
  here): `iotrace.c`, `bodiff.py`, `bograph.py`, `dumpscan.py`, `iohello_draw.m`, `iohello_compute.m`
  (`tools/iotrace/`), `agxparse.py` (`tools/shdump/`). `tools/agx-isa/` **not edited**.
- No faults, no reboots; all captures `status=4` / `STATUS OK`.

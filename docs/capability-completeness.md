# A18 Pro (G17P / Apple9) — Capability Completeness Census

The **master capability census** for the secondary goal in `../CLAUDE.md` ("understand *everything*
the hardware can do"). It enumerates every capability the A18 Pro GPU is *capable of*, driven by two
sources, and maps each to its **hardware representation** and current **RE status**. This is the
tracker the roadmap's "Capability census" axis (`ROADMAP.md` → SECONDARY GOAL) grades against, and the
place the **NOT-YET-CHARACTERIZED** backlog lives.

> **Status: synthesis (host-only, no new RE) — re-synced against findings through the objective-1 (G1)
> and objective-2 (O2) experiments.** Every classification is taken from an already-established finding
> in `docs/` (cited inline) or is an honest **NOT-YET-CHARACTERIZED** mark for a Metal/MSL/WWDC-advertised
> capability whose A18 hardware representation is **not yet shown** in `docs/`. The previous sync stood at
> **native 160 · emulated 9 · kernel 6 · NYC 39** (through EXP-0038); the objective-1/objective-2
> experiments have since closed almost all of the remaining Metal-exposed backlog and their statuses are
> now folded in: **O2-A** geometry-output (multi-viewport, clip-distance mask, `[[point_size]]`,
> primitive-restart, alpha-to-coverage/alpha-to-one); **O2-B** sparse-tier descriptor / PBE-renderable /
> 32-bit-float-filtering / bindless sampler-heap; **O2-C/O2-F** RT tail (`ray_data` payload `0x5f`,
> RT-from-render, primitive/instance motion blur, `rt_transform_test`/`ray_move`, bbox/curve custom
> primitives) + full tensor / `0xcf` operand decode (all tensor ops → `0xcf`); **O2-D/O2-E** atomic-ordering
> fences + bfloat ALU (`0x11`) + subgroup tail (`simd_shuffle_and_fill`, `simd_is_helper_thread`) +
> imageblock / tile-shader dispatch (and the **64-bit-atomic correction**: 64-bit atomics are *entirely*
> absent from MSL → emulate, not NYC); and the G1 grammar experiments **G1-a** USC/resource bind grammar,
> **G1-b** PBE / render-target-attachment descriptor, **G1-c** sysval-negative (no sysval→uniform table),
> **G1-e** UVS VS→FS varying linkage. (Earlier closures already folded in: EXP-0025 async HW-interlock,
> 0026 transcendentals, 0027 indirect/occlusion/timestamp, 0028 formats+twiddle, 0029 fragment
> interp/output/tilebuffer/ROG, 0030 mesh, 0031 SR/preload ABI, 0033 int/bitfield incl. 64-bit, 0034
> texture variants, 0035 function/dylib ABI, 0037 vertex varying-store, 0038 half-pack/carry/frame.)
> No Apple binary was introspected; this file reads only our own `docs/`, the public MSL spec / Metal
> feature tables (via `docs/isa/msl-feature-map.md`, our clean index into them), the public WWDC/Tech-Talk
> material in `gpu_knowledge/apple_official/wwdc/`, and the `MTLDevice` capability probe in
> `hardware-overview.md` §3.

## How to read this

Two source columns drive the census, per `../CLAUDE.md`:
- **(a) Metal/MSL surface** — MSL constructs (`docs/isa/msl-feature-map.md` families A1–A21 / B1–B8),
  Metal feature-set entries, and the `MTLDevice` capability values (`hardware-overview.md` §3).
- **(b) Apple-advertised** — WWDC / Tech-Talk Family-9 hardware claims (Dynamic Caching, HW ray
  tracing + reorder stage, HW mesh shading, 2× ALU, flexible on-chip memory, programmable blending, …).

**Status vocabulary** (one per row):
- **native-decoded** — the hardware does it and we have **decoded its HW representation** (instruction
  encoding / descriptor field / cmdstream field), HW-validated where noted. A trailing *(partial)*
  means the capability is proven native and its principal encoding is decoded, but some sub-fields are
  still ⏳ byte-diff-inferred (see the cited doc). A trailing *(lowered)* means the MSL construct has no
  dedicated silicon but the compiler expansion into native ops is decoded & HW-validated — it is
  characterized (not a Vulkan-must-emulate absence).
- **emulated** — the hardware **lacks** it (or Metal exposes no path and none is proven) → a Vulkan/GL
  driver must software-emulate. Includes HW-validated absences and classically-Apple-absent stages.
- **kernel-managed** — real hardware state, but **firmware/register-managed** → routed through the
  kernel submit, not emitted by userspace (`kernel-interface.md`).
- **NOT-YET-CHARACTERIZED** (NYC) — Metal/MSL exposes it, or Apple advertises it, but the **A18 HW
  representation is not yet provoked/decoded** in `docs/`. These are the completeness backlog (§16).

**HW-representation classes:** `instruction` (AGX opcode), `descriptor` (texture/sampler/buffer bits),
`cmdstream` (VDM/CDM/PPP/USC field), `kernel-managed` (firmware register / submit param), `compiler`
(compile-time, no runtime HW encoding), `microarch` (a behavior with no single emittable encoding —
observed via output/counters), `UNKNOWN` (not yet located).

Honesty rule (`../CLAUDE.md`): a capability is only **native-decoded** if `docs/` actually shows the
encoding AND `PROVENANCE.md` shows it was HW-exercised. "Metal accepts it" or "a doc mentions it" is
**not** decoded — those are NYC.

---

## 1. Shader data types & scalar ALU

| Capability | Source (MSL / Metal / WWDC) | HW representation | Status | Ref |
|---|---|---|---|---|
| 32-bit int ALU (add/sub/mul/mad) | MSL §6.3 (A1) | instruction `0x9f/0x1f` iadd/isub, `0x9f` 12B imul/imad | native-decoded | `isa` "Integer ALU" EXP-0007 |
| 32-bit float ALU (add/sub/mul) | MSL §3.1/§6.5 (A1) | instruction `0x09` falu2, op-select bits[16:19] | native-decoded | `isa` EXP-0005/0006 |
| Fused multiply-add (fma / contraction) | MSL §6.5, §1.6.3 (A2) | instruction `0x09` 8-byte form (srcC byte+5) | native-decoded | `isa` "Scalar ALU completion" EXP-0013 |
| 16-bit (`half`) ALU, 2 halves/GPR | MSL §2.1 (A1); WWDC "FP16 peak throughput" | instruction `0x10`/`0x11` half-ALU (`0x1c` hadd/`0x1d` hmul; `half2` packs both lanes); half-pack `0x18` | native-decoded | `isa` EXP-0033/0038 |
| Free FP16↔FP32 convert | WWDC "conversion costs nothing"; MSL §8.6 | `0x11` (f32→f16); f16→f32 = falu2 16-bit srcA; `as_type` = no op | native-decoded | `isa` EXP-0013 |
| int↔float convert (RTZ f→i) | MSL §8.6 (A6) | instruction `0x27` (f→i, RTZ), `0xa7` (i→f); sign byte+7 bit6 | native-decoded | `isa` EXP-0013 |
| int↔uint / bit-reinterpret | MSL §2.22 (A6) | no instruction (free) | native-decoded | `isa` EXP-0013 |
| min/max (int & float) | MSL §6.3/§6.5 (A3) | instruction `0x02` (int), `0x12` (float); A18/M4 source paths return numeric for tested one-qNaN; A18 `fmax` and M4 `fmin`/`fmax` select operand B on tested signed-zero ties; M4 also tested both-qNaN/subnormal ties | native-decoded; edge semantics partial | `isa` EXP-0007/0013; EXP-0047 M4 source-path controls |
| Float round modes (floor/ceil/trunc/rint) | GL/Vulkan; MSL §6.5 | instruction `0x2f/0xaf` round-mode field byte+8 (0/2/4/6); M4 source paths test `rint` ties-even and compiled `round` ties-away | native-decoded; conformance semantics partial | `isa` EXP-0013; `hypotheses` #2; EXP-0047 |
| exp2 / log2 | MSL §6.5 (A5) | instruction `0x2f/0xaf` SFU single op | native-decoded | `isa` EXP-0013/0026 |
| Typed compare (float/sint/uint) → select | MSL §6.4 (A8) | instruction `0x12` icmpsel, type bits[1:3] byte+6 | native-decoded | `isa` EXP-0013; `hypotheses` #3 |
| select / ternary / csel | MSL §6.4 (A8) | instruction `0x05`/`0x16` (4B) select | native-decoded | `isa` "Control flow" EXP-0010 |
| Boolean logic / **all 16 logic ops** | Vulkan logic-op; MSL §3.1 | instruction `0x0b` ilogic = full 2-input LUT | native-decoded | `isa` EXP-0013; `hypotheses` #1 |
| Shifts (`<<`, arithmetic/logical `>>`, imm) | MSL §6.3 (A9) | instruction `0x9f` (`<<`), `0xa7` (`>>`, bfe) | native-decoded | `isa` EXP-0013 |
| `extract_bits` | MSL §6.3 (A9) | instruction `0xa7` 12-byte extract (signed = +sign-ext shift) | native-decoded | `isa` EXP-0013/0033 |
| popcount | MSL §6.3 (A9) | instruction `0x27 05 56` (8B, single op) | native-decoded | `isa` EXP-0007/0033 |
| `insert_bits` | MSL §6.3 (A9) | no dedicated op — lowered (mask `0x0b` + shift `0x2b` + combine `0x9f`) | native-decoded (lowered) | `isa` EXP-0033 |
| `clz` / `ctz` (count leading/trailing zero) | MSL §6.3 (A9) | find-MSB native (`a7 05 56`); clz/ctz = multi-instr lowering (ctz adds `0x2b`) | native-decoded (lowered) | `isa` EXP-0033; `hypotheses` #23 |
| `reverse_bits` | MSL §6.3 (A9) | instruction `a7 04 56` (8B, single op) | native-decoded | `isa` EXP-0033 |
| `rotate` / funnel shift | MSL §6.3 (A9) | rotate-imm = single `0x27` 12B funnel (byte+1=`0x01`); by-register = multi-instr | native-decoded | `isa` EXP-0033 |
| Packed float immediate (8-bit minifloat) | (encoding fact) | instruction srcB minifloat, 4exp/3mant bias-11 | native-decoded | `isa` EXP-0006 |
| reciprocal / rsqrt / sqrt (estimate+refine) | MSL §6.5 (A4/A5) | SFU single-op `0x2f/0xaf`; precise = `0x29` seed (~8-bit) + 2 NR iters (0 ULP) | native-decoded | `isa` EXP-0026; `hypotheses` #19 |
| sin / cos / tan / exp / log / pow | MSL §6.5 (A5) | range-reduce (`0x2b`) + poly; `pow=exp2(b·log2 a)`; `a/b=a·rcp(b)` (composed, HW-validated) | native-decoded | `isa` EXP-0026; `hypotheses` #20 (large-arg trig → SW Payne-Hanek) |
| min3 / max3 / median3 (3-source) | MSL §6.3 (A3) | no dedicated silicon — lowered to 2-input `0x02` int min/max | native-decoded (lowered) | `isa` EXP-0033 |
| pack/unpack normalized (`unpack_unorm4x8`, `snorm10a2` new-in-Metal4) | MSL §6.14 (A7) | `pack_unorm2x16` = single `0x97`, unpack = single `0x17`; `as_type` free (4× variants ⏳) | native-decoded (partial) | `isa` EXP-0033 |
| `bfloat` general ALU | MSL §2.1 (Metal 3.1+); WWDC | instruction: **distinct group `0x11`** (opsel byte+2 `0x1c/1d/1e` add/mul/fma; byte+1 scalar `0x02`/`bfloat2` `0x04`) — NOT fp32-lowered, NOT the `0x10` fp16 group; splice-proven, HW-validated | native-decoded | `isa` EXP-O2D |
| 64-bit (`long`/`ulong`) integer ALU | MSL §2.1 | native single-op 64-bit add/sub (`0x1f`, HW carry-out; `0x32` carry-gen); 32×32→64 mul = one `0x9f`; shift/compare multi-instr | native-decoded | `isa` EXP-0033/0038; `hypotheses` #24 |
| **2× parallel FP16/FP32/int ALU pipelines** | WWDC "up to 2× ALU" | microarch (dual-issue) — observable via throughput microbench / counters | NOT-YET-CHARACTERIZED | WWDC §1.3 |
| Double precision (fp64) | (absent) | not exposed by MSL on Apple GPUs | emulated | premise (`ROADMAP` "Known premises") |
| Vector/matrix arithmetic (`float4`, `float4x4`) | MSL §2.2/§2.3 | composed of scalar/packed ALU + vector load/store (`count`) | native-decoded | `isa` EXP-0012 (vector load) |

Section tally: native-decoded 28 · emulated 1 · NYC 1.

---

## 2. Control flow & functions

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| if/else / predication (SIMD divergence) | MSL §5.11 (A10) | instruction: compare `0x0a`/`0x02` → exec-mask → masked op | native-decoded | `isa` EXP-0010 |
| Loops (data-dependent back-edge) | MSL §5.11 (A10) | instruction `0x0f 00 54 <off6>` signed back-edge | native-decoded | `isa` EXP-0010 |
| Exec-mask push / else / pop / reconverge | (structured CF) | instruction `0x0f` sub-ops (byte+1: 00/05/01/06) | native-decoded (partial) | `isa` EXP-0010 |
| Early return | MSL §5.11 (A10) | predication + program end (out-of-band length) | native-decoded | `isa` EXP-0010 |
| Program termination | (structure) | out-of-band (section/pipeline metadata); last store is last effective op | native-decoded | `isa` EXP-0003/0010 |
| `while`/`break` (loop CF forms) | Mesa `agx_compile.c`; MSL §5.11 | no distinct op — predication + backward jump `0x0f`; whole corpus tokenizes to 0 leftover bytes (no undecoded CF op) | native-decoded | `isa` EXP-0010/0036 |
| Function calls / `[[visible]]` / call-return ABI | MSL §5.1.4/§2.15 (A11); `supportsFunctionPointers=YES` | CALL `0f 05 54…8f` (target=call+4+off40); RETURN `8f` (HW link reg); args r10+, ret r10; non-leaf frame `0x6f`+`0x07` link save/restore | native-decoded | `isa` EXP-0035/0038 |
| Indirect call / `visible_function_table` | MSL §2.15 (A11) | `visible_function_table` = flat array of 8B code VAs (Tier-2 slot); indirect call `0f 80` | native-decoded | `isa` EXP-0035 |
| Recursion (compute, Metal 2.4+) | MSL §1.5.4 | lowered to loop (tail); statically bounded; non-leaf frame to per-thread scratch | native-decoded | `isa` EXP-0035/0038 |
| Function constants (uber-shader specialization) | WWDC 111373; MSL §5.8 | compiler (compile-time fold, no runtime HW encoding) | native-decoded (n/a HW) | WWDC 111373 §1 |
| Function groups (indirect-call optimization) | WWDC 111373 | compiler (linkage hint) | native-decoded (n/a HW) | WWDC 111373 §1 |
| Dynamic libraries / render dynamic libraries | `supportsDynamicLibraries=YES` | Mach-O `MH_DYLIB` (filetype 14) with AGX code; symbol resolved at pipeline-build (loader = kernel item) | native-decoded | `isa` EXP-0035 |
| Stack / scratch spill (fill) | MSL §4.3 (A13); WWDC Dynamic Caching | behavior proven (>96 GPR spills); non-leaf frame link save/restore = `0x07` (EXP-0038); scratch-base ABI ⏳ | native-decoded (partial) | `isa` EXP-0020/0035/0038 |
| Shader `printf` / `os_log` | MSL §6.17 | cmdstream: macOS 26 uses `os_log` into a driver-allocated `MTLLogState` buffer (self-describing records; shader calls helper `l___air_impl_os_log`) — no MSL printf | native-decoded | `cmdstream` EXP-O2G |

Section tally: native-decoded 14.

---

## 3. Memory, address spaces & barriers

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| `device` load/store (RW), vectorized | MSL §4.1 (A12) | instruction `0x67`/`0xe7` 14B (space/base_slot/count/width/elem_size) | native-decoded | `isa` "Memory access" EXP-0012 |
| `constant` address space | MSL §4.2 (A12) | instruction: byte-identical to device load (distinction is in binding) | native-decoded | `isa` EXP-0012 |
| `threadgroup` load/store | MSL §4.4 (A12) | instruction `0x67`/`0xe7` byte+1 bit1 = threadgroup, base_slot 0x08 | native-decoded | `isa` EXP-0012 |
| Element addressing (no in-instruction offset) | (model) | address = index_GPR × elem_size; offset via prior iadd | native-decoded | `isa` EXP-0012 |
| Sign/zero-extend sub-32-bit loads | MSL §8.6 | zero-extend load variant byte+3 bit1; signed = following `0xa7` shift | native-decoded | `isa` EXP-0012 |
| Buffer base-pointer preload (binding→register) | (ABI) | cmdstream/USC: `device_load` byte+4 = preloaded base slot | native-decoded | `isa` EXP-0010 |
| Scalar-uniform preload (`constant T&`) | MSL §4.2 | uniform register file (read directly by ALU); `uniform_mov` | native-decoded (partial) | `isa` EXP-0010/0020 |
| **Async completion = HW register interlock** (no scoreboard) | (model; vs G13 scoreboard) | microarch: consumer of pending dst stalls in HW; no `wait` op | native-decoded | `isa` "Async completion" EXP-0025 |
| `threadgroup_barrier` (mem-scope) | MSL §6.9.1 | instruction `0x07` 6B, byte+3 = fenced scope (`0x61` tg / `0x85` device) | native-decoded | `isa` EXP-0025 |
| `simdgroup_barrier` | MSL §6.9.1 | no op (lockstep SIMD) | native-decoded | `isa` EXP-0025 |
| Fragment / tilebuffer ordering (`wait_pix`/`signal_pix`) | Mesa; MSL §5.2 | `pixel_order` = `0x07` fence family (acquire `07 14 54 50 06` / release `07 04 54 d0 06`) | native-decoded (partial) | `isa` EXP-0029 |
| Memory order / `coherent(device)` / fence bits | MSL §4.8 | instruction: ordering = **fence presence** (not a field on the RMW). `atomic_thread_fence` = `0x07` fence family — device `07 04 54 84 0a` (byte+3 `0x84` device / byte+4 `0x0a`), texture pair `07 04 54 50/d0 06` (byte+3 bit7 acquire/release); relaxed/thread/simd/tg scope → no fence. MSL accepts only `relaxed` on `atomic_*_explicit` | native-decoded | `isa` EXP-O2D |
| Flexible on-chip memory (unified cache: reg/tg/tile/stack/buffer) | WWDC §1.2 | microarch (unified L1) — observable via cache-hit counters | NOT-YET-CHARACTERIZED | WWDC §1.2 |

Section tally: native-decoded 12 · NYC 1.

---

## 4. Atomics

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| Int atomic add/sub/and/or/xor/min/max (signed & unsigned) | MSL §6.15 (A14) | instruction `0x67` memory-family, op at byte+12 | native-decoded | `isa` "Atomics" EXP-0018 |
| Atomic exchange / store / load | MSL §6.15 | instruction op `0x3c` (xchg/store) | native-decoded | `isa` EXP-0018 |
| Atomic compare-exchange | MSL §6.15 | instruction op `0x24` + following `icmp` (no CAS loop) | native-decoded | `isa` EXP-0018 |
| **Float atomic add** | MSL §6.15.4.5 (device only) | instruction op `0x26` (fadd) | native-decoded | `isa` EXP-0018 |
| Atomic scope: device vs threadgroup | MSL §6.15 | instruction byte+1 bit1 | native-decoded | `isa` EXP-0018 |
| SIMD-reduced atomic to uniform address (opt) | (optimization) | SIMD-reduce → one-lane RMW → broadcast | native-decoded | `isa` EXP-0018 |
| Texture / image atomics (Metal 3.1+, cube in Metal 4) | MSL §6.12 | native — lower to memory-family device atomic `0x67`, texel addr in-shader (texture2d byte+1 `0x11`, op `|0x40`) | native-decoded | `isa` EXP-0034; `hypotheses` #25 |
| **Float atomic min / max** | Vulkan wants; MSL rejects | (no MSL path; absent) | emulated | `isa` EXP-0018; `hypotheses` #9 |
| **64-bit atomic add** | Vulkan wants; MSL rejects | **entirely absent from MSL** (all `atomic<ulong/long/uint64_t>` ops rejected — corrects EXP-0018) → no reachable HW path | emulated | `isa` EXP-O2D (corrects EXP-0018); `hypotheses` #9 |
| **64-bit atomic min/max** | Vulkan wants; MSL §6.15.4.6 | **entirely absent from MSL** (corrects EXP-0018's "min/max only"); no reachable op ⇒ no width field | emulated | `isa` EXP-O2D (corrects EXP-0018) |

Section tally: native-decoded 7 · emulated 3.

---

## 5. Textures & samplers

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| Sample (implicit-LOD, from derivatives) | MSL §6.12 (A15) | instruction `0xb0/0x90` sampler op, op+2 `0x00` | native-decoded | `isa` "Texture / sample" EXP-0016 |
| Sample bias / explicit level / gradient | MSL §6.12 (A15) | instruction op+2 `0x07`/`0x09`/`0x04`; op+7 bit2 = explicit-LOD/bias present | native-decoded | `isa` EXP-0016/0034 |
| Gather (2×2) | MSL §6.12.3 (A15) | instruction op+6 `0x00` + companion+3 component field (bit2=gather, bits[3:5]=RGBA) | native-decoded | `isa` EXP-0016/0034 |
| Image read (load) | MSL §6.12 (A15) | instruction sampler op, mode op+2 `0x17/0x79/0x97/0x80` | native-decoded | `isa` EXP-0016 |
| Image write (store) | MSL §6.12 (A15) | instruction `0xd7` 16B (memory-family store, not sampler) | native-decoded | `isa` EXP-0016; `hypotheses` #7 |
| Read-write textures (Tier 2) | `readWriteTextureSupport=Tier 2` | instruction: `0xd7` write path + native image atomics; `mem_texture` fence ⏳ | native-decoded (partial) | `hw-overview` §3; `isa` EXP-0016/0034 |
| MSAA sample-indexed read | MSL §6.12.8 (A15) | instruction op+2 `0x80` | native-decoded | `isa` EXP-0016 |
| Derivatives dfdx/dfdy/fwidth | MSL §6.10.1 (A18) | instruction `0x37` 10B, axis byte+6 | native-decoded | `isa` EXP-0016 |
| Texture queries (get_width/height/mips/samples/array) | MSL §6.12 (A15) | no instruction (preloaded-uniform read from descriptor) | native-decoded | `isa` EXP-0016 |
| Texture types 2D/2DArray/2DMS/3D/Cube | MSL §2.9 | descriptor type code (2/3/4/5/6); ISA modes | native-decoded | `descriptors` EXP-0015; `isa` EXP-0016 |
| Sampler: address modes / filters / mip / LOD clamp | MSL §2.10 (A16) | descriptor 8B: addr[29:37], mag/min/mip filters, LOD clamps | native-decoded | `descriptors` §Sampler EXP-0015 |
| Sampler compare (all 8 funcs, PCF) | MSL §2.10 | descriptor sense bit39 + test[40:42] | native-decoded | `descriptors` §4b EXP-0015 |
| Unnormalized coordinates | MSL §2.10 | descriptor bit38 | native-decoded | `descriptors` §4 EXP-0015 |
| Anisotropy ≤16× | MSL §2.10 | descriptor `maxAnisotropy` log2 [20:22] | native-decoded | `descriptors` §4 EXP-0015 |
| `sample_compare` (depth PCF) ISA path | MSL §6.12.10 | instruction op+2 bit5 (`0x20`) = depth-compare (`sample_compare(level)`=`0x29`); ref = register operand; sampler `compareFunc` drives it; native 2×2 PCF (8 funcs) | native-decoded | `isa` EXP-0034 |
| `gather_compare` / gather texel-offset variants | MSL §6.12.10 | instruction: gather_compare = gather + op+2 `0x20`; constant offset packs op+5 | native-decoded | `isa` EXP-0034; `hypotheses` #8 |
| Texture LOD query (`calculate_clamped_lod`) | `supportsQueryTextureLOD=YES` | instruction: real texture op, op+6 `0x20` (clamped/unclamped in companion+3) | native-decoded | `hw-overview` §3; `isa` EXP-0034 |
| Texture types 1D / 1DArray / CubeArray / 2DMSArray | MSL §2.9 | descriptor type field 4-bit: 1D=0, 1DArray=1, CubeArray=7, 2DMSArray=8; twiddle HW-validated | native-decoded | `descriptors/format-table` §1; `tiling` §1.6 EXP-0028 |
| **Arbitrary sampler border color** (Vulkan custom) | Vulkan; MSL border presets | descriptor: only 2-bit **3-preset** field (transparent/black/white) | emulated | `descriptors` §4c EXP-0015; `hypotheses` #4 |
| array/3D/cube/MSAA index-operand ISA bit positions | MSL §6.12 | instruction: dim in op+2 (cube `0x13`/3D `0x39`/cube-array `0x53`); extra index (slice/face/z/sample/ref) via op+3 (⏳ byte-diff) | native-decoded (partial) | `isa` EXP-0016/0034 |
| Anisotropy >16× | probe (field encodes 128×) | descriptor field can encode; **untested on HW** | NOT-YET-CHARACTERIZED | `descriptors` §4; `hypotheses` #5 |

Section tally: native-decoded 19 · emulated 1 · NYC 1.

---

## 6. Subgroup / SIMD-group & quad ops

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| SIMD width = 32 | probe `threads_per_simdgroup` | microarch constant (validated) | native-decoded | `isa` EXP-0018 |
| Broadcast / broadcast_first | MSL §6.9.2 (A20) | instruction `0x47`/`0xc7` shuffle group | native-decoded | `isa` EXP-0018 |
| Shuffle (xor / up / down / rotate) | MSL §6.9.2 (A20) | instruction `0x47`/`0xc7`, byte+1 mode, byte+6 lane | native-decoded | `isa` EXP-0018 |
| Reduce: sum/product/min/max/and/or/xor | MSL §6.9.2 (A20) | instruction `0xbf`/`0x3f` simd_reduce, byte+7 dtype | native-decoded | `isa` EXP-0018 |
| **Prefix scan (inclusive/exclusive)** | MSL §6.9.2 (A20) | instruction `simd_reduce` byte+7 `0x09`/`0x0b` (native, not shuffle-tree) | native-decoded | `isa` EXP-0018; `hypotheses` #10 |
| Ballot / vote / all / any / is_first | MSL §6.9.2 (A20) | instruction `0x17` 10B ballot | native-decoded | `isa` EXP-0018 |
| Quad ops (broadcast/shuffle/reduce, width 4) | MSL §6.9.3 (A21) | instruction: same groups at width 4 (`0xb7`/`0x37`; byte+1=00) | native-decoded | `isa` EXP-0018 |
| `simd_shuffle_and_fill_up/down` | MSL §6.9.2 (A20) | instruction: `0x47/0xc7` byte+1 `0x06` (fill variant of the shuffle group). Also `simd_product` = `0xbf` byte+1 `0x06`; integer product/prefix-product lowered (`0x47` shuffle + `0x9f` mul tree) | native-decoded | `isa` EXP-O2D |
| `simd_is_helper_thread` (fragment) | MSL §6.9.2 | instruction: `get_sr` SR byte1 `0x84` | native-decoded | `isa` EXP-O2D |

Section tally: native-decoded 9.

---

## 7. Matrix / cooperative / tensor

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| `simdgroup_matrix` 8×8×8 MAC | MSL §6.7 (B5) | instruction **`0xcf`** 12B, dedicated MAC array (512 MACs); full operand decode (byte+5 A / +6 B / +7 C / +8 dst / +10 op-enable `0x24` / +11 bit0 accum) | native-decoded | `isa` "Dedicated matrix unit" EXP-0022/O2C; `hypotheses` #16 |
| Matrix dtypes fp16 / fp32 / bfloat / mixed→fp32 | MSL §6.7 | instruction `0xcf` byte+1 dtype | native-decoded | `isa` EXP-0022 |
| Matrix accumulate-enable (`+c`) | MSL §6.7 | instruction `0xcf` byte+11 bit0; C src byte+7 | native-decoded | `isa` EXP-0022 |
| `simdgroup_load` / `store` / `make_filled` | MSL §6.7 | instruction `0x67`/`0xe7` (load/store), `0x2c`/`0x3c` splat | native-decoded | `isa` EXP-0022 |
| MPP `tensor_ops::matmul2d` (32×32×32) | MSL §7.2.1 (B6) | instruction: lowers to 259× tiled `0xcf` | native-decoded | `isa` EXP-0022 |
| **int8 / integer cooperative matrix** | Vulkan; MSL rejects int | (all integer types rejected by Metal) | emulated | `isa` EXP-0022 |
| Matrix `transpose_matrix` / `elements_per_row` load variants | MSL §6.7 | instruction: transpose/load/store = ordinary memory (`0x67`/`0xe7`) + 4B moves — the MAC (`0xcf`) is the only dedicated silicon | native-decoded | `isa` EXP-O2C |
| Matrix A/B/dst operand-selector full bit decode | MSL §6.7 | instruction `0xcf` byte+3 A sub-descriptor, byte+1 dtype, **byte+2 = mode (SEMANTIC: tiled `0x54` sources accum from MPP tile ctx)**; HW-validated via splice | native-decoded | `isa` EXP-O2C (resolves EXP-0022) |
| MPP cooperative tensor / convolution / other tensor ops | MSL §2.21/§7 (B6) | instruction: **all tensor ops lower to `0xcf`** (no dedicated tensor opcode beyond the MAC) | native-decoded | `isa` EXP-O2C |

Section tally: native-decoded 8 · emulated 1.

---

## 8. Ray tracing

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| HW ray/box/triangle intersect | `supportsRaytracing=YES`; MSL §6.18 (B1) | instruction **`rt_intersect`** (low-nibble `0x4`, byte+1 `0xea`) | native-decoded (partial) | `isa` "HW ray tracing" EXP-0023; `hypotheses` #17 |
| Acceleration-structure / ray-data node loads | MSL §6.18 | instruction **`rt_as_load`** `0xdf` 14B | native-decoded (partial) | `isa` EXP-0023 |
| Intersector object API (traversal loop) | MSL §2.17.6 (B1) | instruction: shader BVH-traversal loop (back-edge + `0xdf` + compare) | native-decoded (partial) | `isa` EXP-0023 |
| AS referenced by 8-byte VA | MSL §2.17 | descriptor: 8-byte GPU VA in Tier-2 arg buffer | native-decoded | `isa` EXP-0023 |
| `intersection_query` (inline ray_query) | MSL §2.17.8 (B2) | instruction: same intersect ops, inline (disables reorder) | native-decoded (partial) | `isa` EXP-0023 |
| **BVH build + node format** | MSL AS build | kernel-managed (GPU/firmware builds; node format not userspace-visible) | kernel-managed | `isa` EXP-0023; `kernel-interface` §4.1 |
| Intersection functions / `intersection_function_table` | MSL §5.1.6 (B3) | instruction: bound as Tier-2 slot (flat array of 8B code VAs); call/return ABI decoded (same as `visible_function_table`) | native-decoded (partial) | `isa` EXP-0023/0035 |
| `ray_data` payload address space (copy-in/out) | MSL §4.6 (B3) | instruction **`0x5f`** 14B (byte+2 `0x54`, sibling of `0xdf`) = ray-data payload path (distinct address space in RT scratch; count scales with payload size) | native-decoded | `isa` EXP-O2C |
| **RT reorder stage** (groups intersection calls) | WWDC §2 "Reorder Stage" | microarch/firmware — observable via RT-scratch counters (Xcode) | NOT-YET-CHARACTERIZED | WWDC §2; `isa` EXP-0023 follow-up |
| Ray tracing from render | `supportsRaytracingFromRender=YES` | instruction: lowers **identically to compute RT** (2×`rt_intersect` + `0xdf` loads + `0x5f` + traversal loop); only the bind stage differs (`setFragmentAccelerationStructure:`) — HW-validated | native-decoded | `hw-overview` §3; `isa` EXP-O2C |
| Primitive / instance motion blur | `supportsPrimitiveMotionBlur=YES` | instruction: no new opcode — `rt_intersect` byte+2 `0x10` (time form), motion-AS byte+4 `0xbb` (vs `0x8b` prim / `0x1b` instance), time byte+3 — HW-validated | native-decoded | `hw-overview` §3; `isa` EXP-O2C |
| Intersection tags (instancing / world_space / max_levels) | MSL §2.17.1 | instruction: AS-select byte+4 (`0x8b` primitive / `0x1b` instance / `0xbb` motion) HW-validated; world_space / max_levels sub-tags ⏳ | native-decoded (partial) | `isa` EXP-O2C |
| Bounding-box / curve custom primitives | MSL §5.1.6 | instruction: primitive tag (bbox/curve/opacity) does **not** change the intersect op — discrimination is in the AS + `intersection_function_table` (decoded, HW-exercised) | native-decoded (mechanism) | `isa` EXP-O2C/0023/0035 |
| RT companion ops (`0x5f`, ray-move) | (ISA census) | instruction: `0x5f` ray-data mem op; `rt_transform_test` (`0x?2`, byte+2 `0x27`, traversal slab-test); `ray_move` (`0x?b`, byte+2 `0x80/81`, 4B ray-register marshal) | native-decoded | `isa` EXP-O2C |

Section tally: native-decoded 12 · kernel-managed 1 · NYC 1.

---

## 9. Mesh / geometry pipeline

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| **Hardware mesh shading** (object + mesh stages) | WWDC §3 "HW-accelerated mesh shading"; MSL §2.20 (B4) | HW pipeline; vertex/prim emit = compute-style `0xe7` stores into firmware UVB (no dedicated emit op); no truly mesh-unique opcode; HW-validated (triangle rendered) | native-decoded | `isa`/`cmdstream` EXP-0030 |
| Object→mesh amplification grid (`set_threadgroups_per_grid`) | MSL §2.20.1 (B4) | object `main` computes fixed-function amplification; mesh-grid-dispatch record `0x70000600` | native-decoded | `isa`/`cmdstream` EXP-0030 |
| `object_data` payload (16 KB) | MSL §4.7 (B4) | ordinary `0xe7` device stores (object payload) | native-decoded | `isa` EXP-0030 |
| Mesh vertex/primitive/index export buffer layout | MSL §5.1.8 (B4) | emit = runs of `0xe7` stores into UVB; UVB buffer sizing/layout firmware-managed (kernel item) | native-decoded | `isa`/`cmdstream` EXP-0030; `kernel-interface` |
| Mesh threadgroups per grid 1M+ | WWDC §3 | cmdstream: mesh-grid-dispatch record `0x70000600` + grid dims; reuses graphics TA/VDM (no CDM) | native-decoded | `cmdstream` EXP-0030 |
| Geometry shaders | Vulkan/GL; classically Apple-absent | (no HW GS stage) → compute-emulated (VS→GS, 4 sub-programs) | emulated | `capability-matrix` §2; `mesa-req` §2g |
| Tessellation (compute-emulation fallback) | Vulkan/GL | `libagx` VS→TCS→D3D11-reference tessellator as compute — now an **OPTIONAL** portable fallback (A18 has a **native** HW tessellator, see the resolved re-probe row below) | emulated | `capability-matrix` §1/§2; `mesa-req` §4 |
| Transform feedback / streamout | Vulkan/GL; Metal no path | (no streamout unit) → compute-emulated | emulated | `capability-matrix` §2; `mesa-req` §2g |
| **Tessellation — A18 NATIVE HW (re-probe RESOLVED, EXP-O2H)** | Vulkan/GL; `drawPatches` (Apple9) | cmdstream: `drawPatches` → native VDM patch-dispatch record **`0x40`**, half-float factor buffer (`MTLTessellationFactorsHalf`), ordinary post-tess `__vertex` shader; domain generator firmware-managed. **NOT compute-emulated.** (GS + transform feedback re-probe → confirmed still Metal-unexposed → emulate.) | native-decoded | `cmdstream` "Tessellation — NATIVE hardware stage" EXP-O2H |

> **Note.** Mesh shading is decoded (EXP-0030): a **genuine HW graphics pipeline** whose emit lowers to
> ordinary stores into a firmware-managed UVB. **Tessellation is also NATIVE HW on A18 (EXP-O2H)** —
> `drawPatches` drives a native VDM patch-dispatch record `0x40` (no compute pre-pass); the `libagx`
> compute-tessellation stack is retained only as an **optional** portable fallback (still counted once in
> the emulated column as that fallback capability). **Geometry shaders and transform feedback** remain
> classically-absent stages (emulate) and were **not** found to have any native A18 path.

Section tally: native-decoded 6 · emulated 3.

---

## 10. Fixed-function raster / blend / depth-stencil

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| Depth/stencil compare (8 funcs) + stencil ops (8) | Vulkan/GL; MSL render state | cmdstream `0x58000` depth `+0x38` / stencil `+0x3c` packets | native-decoded | `cmdstream` "Depth/stencil packet" EXP-0019 |
| **Depth clamp vs clip** (`depthClampEnable`) | Vulkan | cmdstream raster packet bits [11:10] (native 2-bit) | native-decoded | `cmdstream` EXP-0019; `hypotheses` #11 |
| Face cull / winding order | Vulkan/GL | cmdstream raster cull[1:0], winding bit16 | native-decoded | `cmdstream` EXP-0019 |
| **Polygon line fill** (`POLYGON_MODE_LINE`) | Vulkan/GL | cmdstream raster nibble `0x5` + flags bit26 | native-decoded | `cmdstream` EXP-0019; `hypotheses` #13 |
| Depth bias (constant/slope/clamp) | Vulkan/GL | cmdstream enable flags `+0x34` bit17 + 3 floats in tiler-param | native-decoded | `cmdstream` EXP-0019 |
| **Programmable blend** (any factor/op) | WWDC programmable blending; TBDR | instruction: **compiled into fragment shader** blend microprogram (not FF LUT) | native-decoded (mechanism) | `cmdstream` "Blend is programmable" EXP-0019; `hypotheses` #12 |
| **Dual-source blend** | Vulkan/GL | instruction: via programmable-blend FS epilog (`index(i)` output) | native-decoded (mechanism) | `cmdstream` EXP-0019 |
| **Framebuffer logic ops** (16) | Vulkan/GL | instruction: 16-func LUT `0x0b` through the FS path | native-decoded | `isa` EXP-0013; `cmdstream` EXP-0019 |
| Color write mask | Vulkan/GL | cmdstream `0x58000` (R=bit0…A=bit3) | native-decoded | `cmdstream` EXP-0019 |
| Viewport transform + depth range | Vulkan/GL | cmdstream `0x68000+0x910` (4 floats + depth) | native-decoded | `cmdstream` EXP-0014; `pipeline` |
| Indexed draw + index-buffer VA | Vulkan/GL | cmdstream VDM opcode `0x61f2`, index VA `+0x70` | native-decoded | `cmdstream` EXP-0014 |
| Primitive type (point/line/tri/strip) | Vulkan/GL | cmdstream VDM primitive `+0x65` | native-decoded | `cmdstream` EXP-0014 |
| Provoking vertex / flat-shading convention | Vulkan/GL; MSL `[[flat]]` | instruction: `[[flat]]` = `iter_flat` `0x1f` (provoking-vertex load, no interp); first/last convention ⏳ | native-decoded (partial) | `isa` EXP-0029 |
| Polygon **point** fill | Vulkan/GL | **Metal-unreachable** (fill/lines only; HW nibble not proven for point) → SW emulate | emulated | `cmdstream` EXP-O2A; `hypotheses` #13 |
| Alpha-to-coverage / alpha-to-one | Vulkan/GL; Metal render state | cmdstream+shader: alpha-to-coverage = FS epilog + FF bits `0x58000+0x18` bit0 (MSAA-only) / `+0x50` bits[30,26]; alpha-to-one = FS epilog only (no FF field) | native-decoded | `cmdstream` EXP-O2A |
| Primitive restart | Vulkan/GL | cmdstream: cut/restart index at `0x18000+0x68` = all-ones of the index width (no separate enable); *custom* restart index Metal-unreachable | native-decoded | `cmdstream` EXP-O2A |
| Point size (`[[point_size]]`) | Vulkan/GL | cmdstream: PPP output-select `0x58000+0x20` bit18 = point_size live; value is shader-driven (no descriptor field) | native-decoded | `cmdstream` EXP-O2A |
| Wide / smooth lines | Vulkan/GL (Bresenham-only in Mesa) | UNKNOWN (Metal line width fixed → extrapolate-and-test) | NOT-YET-CHARACTERIZED | `mesa-req` §4 |
| Multiple viewports / scissor rects (16) | Vulkan/GL | cmdstream: viewport array `0x68000+0x900 = ((count-1)<<12)\|0x0C00` (max 16), output-select `0x58000+0x20` bit19 = viewport_array_index; multi-**scissor** rect array is **kernel-managed** (`isp_scissor`, no client BO) | native-decoded | `cmdstream` EXP-O2A; `kernel-interface` §6.1 |
| Clip / cull distances (16 planes) | Vulkan/GL | cmdstream: PPP output-select `0x58000+0x20` bits[7:0] = clip-distance plane mask (max 8) + shader-output varying; **cull** distance Metal-unreachable (MSL has clip only) → emulate | native-decoded | `cmdstream` EXP-O2A |
| Conditional rendering | Vulkan/GL (CPU-emulated in Mesa) | UNKNOWN (likely emulate) | NOT-YET-CHARACTERIZED | `mesa-req` §4 |
| Scissor test (`isp_scissor`) | Vulkan/GL | kernel-managed submit param (`isp_scissor_base`) | kernel-managed | `kernel-interface` §6.1 |
| Packed depth24-stencil8 | Vulkan/GL | (absent — `depth24Stencil8=NO`; Z/S separate resources) | emulated | `hw-overview` §3; `descriptors/format-table` §269 (unsupported); `mesa-req` §4 |

Section tally: native-decoded 18 · emulated 2 · kernel-managed 1 · NYC 2.

---

## 11. Interpolation / varyings / fragment built-ins

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| Varying interpolation (perspective / no-persp / flat / centroid / sample) | MSL §5.4 (A17) | instruction `iter` `0x2f` (byte+5 varying-slot, byte+6 mode center/centroid/persp-denom); `[[flat]]`=`iter_flat` `0x1f`; perspective = multi-instr (linear iters + W-denom + rcp + fmul). VS→FS linkage: VS UVS slots (pos 0–3, varying #k = 4+4k), cross-stage-compacted, linker matches VS-slot↔FS-coef (no byte-addressable remap); count `0x58000+0x2c = 4+4·nvary` — reorder-proven on HW | native-decoded | `isa` "Fragment ISA" EXP-0029; `cmdstream` EXP-G1e |
| Pull-model interpolation (`interpolate_at_*`) | `supportsPullModelInterpolation=YES`; MSL §6.11 (A17) | instruction: `interpolate_at_*` == the matching `[[*_perspective]]`/`iter_at` qualifier | native-decoded | `hw-overview` §3; `isa` EXP-0029 |
| Barycentric-coord built-in | `supportsShaderBarycentricCoordinates=YES`; MSL §5.2.3.4 (A19) | instruction: interpolated via `0x2f` family | native-decoded | `hw-overview` §3; `isa` EXP-0031 |
| Fragment built-ins (primitive_id / sample_id / position / front-facing …) | MSL §5.2.3 | instruction `get_sr` SR#=byte1 (front_facing `0xc5`, `[[position]]` `0xa0/a1`); primitive_id = flat tiler-output load; sample_id folds to 0 on 1-sample | native-decoded | `isa` EXP-0031 |
| Sample-rate shading (`[[sample_perspective]]`) | Vulkan/GL; MSL §5.4 | instruction: `iter` mode `0x02` + `iter_at` setup (byte+7 `0x03` sample) | native-decoded (partial) | `isa` EXP-0029 |
| `discard_fragment()` | MSL §6.10 | instruction: HW-proven (killed fragments write nothing) | native-decoded | `isa` EXP-0029 |
| Vertex varying store | (vtx stage) | instruction `0x57` store (byte+3 src, byte+4 slot=index<<5; position slots 0-3, varyings 4+) | native-decoded | `isa` EXP-0037 |

Section tally: native-decoded 7.

---

## 12. TBDR / imageblock / tile

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| Tile size **32×32 fixed** (does not shrink with bpp) | (delta vs G13/G14) | cmdstream `0x68000+0x904/+0x908` tile counts | native-decoded | `pipeline` "Tile size" EXP-0021; `hypotheses` #14 |
| Tile-memory budget (32 KiB, Σ area·bpp·samples) | `maxThreadgroupMemoryLength=32768` | cmdstream per-attachment 0x20-byte tiler-heap record (stride 0x1000) | native-decoded | `pipeline` "Imageblock/tile memory" EXP-0021 |
| Memoryless render targets | MSL storage mode; WWDC TBDR | cmdstream `+0x24` bit27 clear + poison surface addr | native-decoded | `pipeline` "Memoryless" EXP-0021 |
| Load/store actions (load/clear/dontCare, store/resolve) | Metal render pass | cmdstream 0x300-byte load/render/store segments | native-decoded (partial) | `pipeline` "Load/store" EXP-0021 |
| Hidden Surface Removal (HSR) | WWDC TBDR | microarch (automatic; no userspace encoding beyond normal draw) | native-decoded (implicit) | WWDC NOTES TBDR |
| MSAA sample count (2×/4×) | `supports32BitMSAA=YES` | cmdstream attachment `+0x24` (bit24 count LSB, bit27 store) | native-decoded | `pipeline` "MSAA" EXP-0021 |
| **Programmable MSAA sample positions** | `programmableSamplePositionsSupported=YES` | cmdstream: **userspace-emittable** — written to a **client BO** (`0x100000e8000` 4× / `0x100000e0000` 2×) at **+0x40**, N `(x,y)` f32 pairs on a 1/16 grid; **NOT kernel-managed** (RT-4 corrects EXP-0021, which diffed the wrong BOs) | native-decoded | `pipeline` EXP-0021/RT-4; `kernel-interface` §4.2/§5; `hypotheses` #15 |
| Imageblocks (explicit/implicit layout, `[[color(n)]]` slots) | WWDC (A11+); MSL §2.11 (B7) | instruction: read = `0x67` load, write = `0xe7` store (fragment/tile variant byte+1 ∈ {`0x06`,`0x16`,`0x0e`}); **slice addressing byte+5 = field-byte-offset within imageblock >> 1** (vs MRT `rt<<1`); byte+7 = format | native-decoded | `isa` EXP-0029/O2D |
| Tile shaders (mid-render compute) | WWDC (A11+); MSL §5.1.9 (B7) | cmdstream: tile dispatch (`dispatchThreadsPerTile`) is appended **inline** to the render control stream (`0x58000`/`0x18000`) — byte-identical IOKit, no separate submission; HW-validated (tile kernel overwrote an RGBA16F attachment) | native-decoded | `isa` EXP-O2D |
| Programmable-blend `[[color(m)]]` input (tile read) | MSL §5.2.3.4 (B8) | instruction: `tile_read` `0x67/0e` (in-shader blend HW-proven: `out=src*0.5+clear*0.5`) | native-decoded | `isa` EXP-0029 |
| **Raster order groups** (frag interlock) | `rasterOrderGroupsSupported=YES`; MSL §5.2.1.2 (B8) | instruction: `pixel_order` = `0x07` fence family (acquire/release; ⏳ byte-diff) | native-decoded (partial) | `hw-overview` §3; `isa` EXP-0029 |
| Threadgroup imageblock (`threadgroup_imageblock`) | MSL §4.5 (B7) | instruction: same imageblock `0x67`/`0xe7` slice addressing (byte+5 field-offset>>1) in a tile kernel; HW-validated end-to-end | native-decoded | `isa` EXP-O2D |
| Depth store-action / ZLS | (render-pass control) | kernel-managed (`zls_ctrl`; not in any userspace BO) | kernel-managed | `pipeline` EXP-0021; `kernel-interface` §4.3 |
| Partial-render / tiler-param overflow trigger | (TBDR) | kernel-managed (firmware detects overflow; `partial_bg`/`partial_eot`) | kernel-managed | `pipeline` EXP-0021; `kernel-interface` §4.4 |
| Occlusion / visibility queries | Vulkan/GL; native HW mechanism | cmdstream: result ptr `@0x10000100000`; mode bit14 `@0x58000+0x8c` (bool/count); offset `@+0xa0`=byteOff<<14; per-tile summation firmware | native-decoded | `cmdstream` EXP-0027 |
| Timestamps / GPU counters | `counter sets: timestamp` | Public Metal stage samples are 64-bit and nanosecond-valued in the tested paths; EXP-0052 (`cad2132b`, M4 only) establishes within-pass order but falsifies strict cross-pass non-overlap. Immediate post-commit/pre-wait availability was not status-qualified; Linux frequency/object layout and A18 semantics remain open | partial | `cmdstream` EXP-0027; EXP-0052 `analysis/summary.json` / `analysis/report.txt` |

Section tally: native-decoded 13 · partial 1 · kernel-managed 2.

---

## 13. Compute dispatch

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| Direct dispatch (grid + threadgroup in threads) | Metal compute | cmdstream CDM 0x2c-byte record (grid `+0x10`, tg `+0x1c`) | native-decoded | `cmdstream` "Compute launch" EXP-0011 |
| Non-uniform grid (`dispatchThreads`) | Metal | cmdstream: grid is in threads (not threadgroups) | native-decoded | `cmdstream` EXP-0011 |
| Threadgroup (shared) memory size | `maxThreadgroupMemoryLength=32768` | cmdstream shader BO field `(bytes<<2)\|0x80` | native-decoded | `cmdstream` EXP-0024 |
| Max threads/threadgroup 1024 | `maxThreadsPerThreadgroup=(1024³)` | limit | native-decoded | `hw-overview` §3 |
| Occupancy tier (register pressure) | (Dynamic Caching surface) | cmdstream CDM config word `+0x00` bit23 | native-decoded | `cmdstream` EXP-0024; `isa` EXP-0020 |
| Shader-code pointer (compute) | (bind) | cmdstream CDM `+0x08 = shaderVA>>6` | native-decoded | `cmdstream` EXP-0011 |
| Indirect dispatch (`dispatchThreadgroupsWithIndirectBuffer`) | Metal; Vulkan | cmdstream: 2nd CDM + grid-setup helper shader (multiply threadgroups×tpg); args VA `0x10000080000+0xb0` | native-decoded | `cmdstream` EXP-0027 |
| Indirect command buffers / device-generated commands | WWDC GPU-driven; Metal ICB | cmdstream: indirect draw VDM `0x61c4→0x6404` (idx `0x6432`) + args ptr; full ICB = inline state-block+draw, header `+0x04` = count. EXP-0053 (`e31dfb46`) separately establishes tested M4 public argument timing, ICB ranges, reset/re-encode and one optimization-equivalence case; it does not establish writable native grammar, Linux mapping, or A18 behavior | native-decoded | `cmdstream` EXP-0027; EXP-0053 canonical full-byte runs 05/06 (03/04 downgraded; failures 01/02 retained) |
| Draw mesh commands into ICB | WWDC §3 | cmdstream: `MTLIndirectCommandTypeDrawMeshThreadgroups` lowers to the **same mesh-grid-dispatch record `0x70000600`** (EXP-0030) in the tiler stream — no new work type; command-count `@0x18000+0x04` | native-decoded | `cmdstream` EXP-O2G |

Section tally: native-decoded 9.

---

## 14. Format support & texture memory layout

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| 31 color/int/float formats (r8…rgba32f, packed 10a2/11b10/9e5) | MSL / Metal formats | descriptor `(byte1<<8)\|byte0` code table | native-decoded | `descriptors/format-table` §2 EXP-0015 |
| Format / swizzle / sRGB / numeric-type orthogonality | Vulkan-shaped | descriptor: independent fields | native-decoded | `descriptors` "Capability notes" EXP-0015; `hypotheses` #6 |
| Full channel swizzle (R/G/B/A/0/1) | Vulkan/GL | descriptor word0 [16:27] 4×3-bit | native-decoded | `descriptors/format-table` §3 |
| Morton / Z-order twiddle (optimal layout) | (HW layout) | tiling: **row-major grid of Morton tiles (cols=round_up(ceil(W/T),G) 16KiB-row granule — RT-9/EXP-M4-06)** (RT-3), tile edge **T = largest pow2 with T²·bpp≤16KiB** (bpp1→**128**, bpp2/4→64, bpp8/16→32; EXP-M4-06), **cols = round_up(ceil(W/T), G)**, G=0x4000/(T²·bpp); `element = (ty·cols+tx)·T² + morton_D(x&(T−1), y&(T−1))` — supersedes the earlier "pow2-padded full-texture Morton, morton(x,y)·bpp, bpp-independent" model | native-decoded | `tiling` §1.1 EXP-0017/RT-3 |
| Linear (buffer-backed) layout + stride | Metal buffer textures | descriptor `bytesPerRow=(word3[14:]+1)×16` | native-decoded | `tiling` §2 EXP-0017 |
| Mip-tree packing | Metal mipmaps | tiling: consecutive pow2-padded Morton planes, 0x80 min slot | native-decoded | `tiling` §3 EXP-0017 |
| Lossless compression aux (placement + flags) | (bandwidth opt) | descriptor word1 bit27 / word3 bit31 / secondary VA; aux = **numTexels/32** (= image/128 only at bpp4; EXP-M4-07) | native-decoded | `tiling` §4 EXP-0017 |
| Block-compressed BC / ASTC / ETC | `supportsBCTextureCompression=YES` | descriptor sizeclass codes `0x14-0x1e` captured; twiddle = Morton-of-blocks (blockBytes) HW-validated (BC1/BC7/ASTC-4×4/8×8) | native-decoded | `descriptors/format-table` §269; `tiling` §1.5 EXP-0028 |
| depth16unorm / stencil8 / x24s8 / x32s8 | Metal depth formats | depth16unorm=r16unorm, stencil8=r8uint (reuse color codes); depth24s8/x24s8 unsupported (Z/S separate); depth32f_s8 stencil-aspect ⏳ | native-decoded (partial) | `descriptors/format-table` §269 EXP-0028 |
| Extended-range / wide-gamut / YUV formats | Metal | numtype 5 = XR (bgr10_xr/bgra10_xr); HDR-ASTC = float; YUV/video ⏳ untested | native-decoded (partial) | `descriptors/format-table` §269 EXP-0028 |
| 16-bit snorm/unorm variants (r16snorm, rg16, rgba16snorm) | Metal | descriptor = base code + snorm/unorm numtype (orthogonal; HW-validated r8/r16/r32/rgba8) | native-decoded | `descriptors/format-table` §2a EXP-0015/0028 |
| `depth32float` | Metal | descriptor = r32float code | native-decoded | `descriptors/format-table` §2 |
| 3D / cube / array / MSAA twiddle layout | Metal | tiling: 3D = stacked 2D-Morton planes; array/cube = Morton planes linear-stacked; 1DArray = linear rows (HW-validated) | native-decoded | `tiling` §1.6 EXP-0028 |
| MSAA sample interleave in memory | Metal MSAA | tiling: sample-major, offset=(N·morton+sample)·bps (N=2,4; 8× unsupported) | native-decoded | `tiling` §1.6 EXP-0028 |
| Lossless compression **block codec** | (HW) | tiling: state bytes decoded; **codec/bit-layout opaque** | NOT-YET-CHARACTERIZED | `tiling` §4.5 EXP-0017 |
| Sparse / tile textures | `sparseTileSizeInBytes=16384` | descriptor: **sparse-tier flag** (byte0 hi-nibble `(byte0 & ~0x20)\|0x10`; word1 bits[28:29]); **tile residency is NOT in the descriptor** — it lives in the GPU page table (kernel/firmware-managed); sparse tile = 16 KiB | native-decoded | `descriptors` EXP-O2B; `tiling` §4 |
| Compression × mipmap interaction; NPOT small thresholds | (corner cases) | tiling: one **contiguous aux buffer covering all mip levels**; NPOT compression threshold = **W ≥ 16 ∧ H ≥ 16** texels (unpadded, bpp-independent) | native-decoded | `tiling` EXP-O2G |
| 32-bit float texture filtering | `supports32BitFloatFiltering=YES` | descriptor: **unconditional on Apple9** — no "filterable" flag; nearest vs linear is only the sampler filter field (HW-validated) | native-decoded | `descriptors` EXP-O2B |
| Per-format renderable / PBE-renderable flags | Metal | descriptor: render-target is **not a per-texture bit** (byte-identical sampled desc; structural via the attachment). Storage-image (`access::write`/`read_write`) = distinct 32B **PBE descriptor** (W-1 word0[24:31]‖word1[0:5], H-1 word1[6:19], no compression aux); HW-validated | native-decoded | `descriptors` EXP-O2B/G1b |

Section tally: native-decoded 18 · NYC 1.

---

## 15. Machine model / Dynamic Caching / binding

| Capability | Source | HW representation | Status | Ref |
|---|---|---|---|---|
| 96 addressable 32-bit GPRs; 2 halves/GPR | (register file) | microarch/instruction (footprint in `__GPU_METADATA`) | native-decoded | `isa` "Machine model" EXP-0020 |
| Uniform register file + uniform program (constant_program) | (ABI) | instruction: per-source GPR-vs-uniform mode bit; `uniform_mov` | native-decoded (partial) | `isa` EXP-0010/0020 |
| Occupancy 2-level tier (config bit23) | (Dynamic Caching surface) | cmdstream CDM `+0x00` bit23 | native-decoded | `isa` EXP-0020; `cmdstream` EXP-0024 |
| Spill to per-thread scratch above 96 GPRs | (Dynamic Caching) | behavior proven; frame link save/restore `0x07`/`0x6f` decoded; scratch base ⏳ | native-decoded (partial) | `isa` EXP-0020/0038 |
| **Dynamic Caching** (register file as cache; dynamic alloc/dealloc; occupancy vs live-set) | WWDC §1.1 | microarch — observable via GPR-pressure-vs-occupancy microbench + Xcode counters | NOT-YET-CHARACTERIZED | WWDC §1.1; `isa` EXP-0020 (static model only) |
| Argument buffers Tier 2 / bindless | `argumentBuffersSupport=Tier 2` | cmdstream Tier-2 arg buffer (8B/slot, table `+0x14a0`) | native-decoded | `cmdstream` "Argument buffer" EXP-0011; `hw-overview` §3 |
| Buffer / texture / sampler binding via arg buffer | (binding model) | descriptor: buffers inline VA; tex/samp = pointer to descriptor block | native-decoded | `descriptors` EXP-0015 |
| Sampler heap (large count) | `maxArgumentBufferSamplerCount=500000` | descriptor: bindless sampler in an arg buffer = **8-byte little-endian `gpuResourceID`** = index into a 500k device-global sampler table (stride 8); samplers are not `MTLResource`s (no residency). Arg-buffer tex/samp block @`0x10000248000` (2-ptr header, count=ptr-delta/0x20) | native-decoded | `descriptors` EXP-O2B; `cmdstream` EXP-G1a |
| Full halfregs→max-threads occupancy curve | perf | microarch (per-op latency/throughput) — not measured | NOT-YET-CHARACTERIZED | `mesa-req` §2a |
| Special-register (SR) enum + preload ABI | (ABI) | instruction: `get_sr` SR#=byte1 (full table decoded); no GPR ID preload; **sysvals NOT in uniform registers** (`vertex_id`/`instance_id`/`[[position]]`/`front_facing` = `get_sr` on demand — no sysval→uniform table to build); buffer/uniform bases in uniform file (vtx base=slot `0x03`) | native-decoded | `isa` EXP-0031; `cmdstream` EXP-G1c |
| **Graphics code-window / stage selectors** | (draw dispatch) | M4: VDM VS token + 32-bit FS window-relative selector; exact queue `usc_exec_base`, general token, consumer and A18 mapping open | NOT-YET-CHARACTERIZED (partial) | `cmdstream` EXP-0042; `kernel-interface` §4.5 |

Section tally: native-decoded 8 · NYC 3.

---

## 16. Prioritized NOT-YET-CHARACTERIZED backlog (the completeness backlog)

### Closed since the last sync (O2-A/B/C/D + G1-a/b/c/e)

The objective-1/objective-2 experiments **retired** almost the entire remaining backlog (moved to
native-decoded above unless noted):
- **O2-A** geometry-output: multi-viewport array, clip-distance plane mask, `[[point_size]]`,
  primitive-restart cut index, alpha-to-coverage/alpha-to-one (§10). *Also found Metal-unreachable →*
  ***emulate***: polygon-point fill (moved NYC → emulated), cull distance, custom restart index.
- **O2-B** sparse-tier descriptor flag, 32-bit-float filtering (unconditional), render-target/PBE-renderable
  (structural, not a per-texture bit), bindless sampler-heap `gpuResourceID` (§14/§15).
- **O2-C/O2-F** RT tail: `ray_data` payload `0x5f`, RT-from-render, primitive/instance motion blur,
  `rt_transform_test`/`ray_move`, bbox/curve custom primitives (mechanism) (§8); full tensor / `0xcf`
  operand decode incl. transpose/load variants and all MPP tensor ops (§7).
- **O2-D/O2-E** compute/fragment tail: atomic-ordering fences (§3), bfloat ALU group `0x11` (§1),
  subgroup tail `simd_shuffle_and_fill`/`simd_is_helper_thread` (§6), imageblock slice addressing +
  `threadgroup_imageblock` + tile-shader inline dispatch (§12). **64-bit-atomic correction:** 64-bit
  atomics are *entirely* absent from MSL → **64-bit atomic min/max moved NYC → emulated** (§4).
- **G1-a** USC/resource bind grammar, **G1-b** PBE/render-target-attachment descriptor, **G1-c**
  sysval-negative (no sysval→uniform table), **G1-e** UVS VS→FS varying linkage (§10/§11/§15).

The NYC backlog previously fell from **39 → 9** (two rows reclassified NYC → emulated: polygon-point fill,
64-bit atomic min/max; then **O2-G** closed printf / mesh-ICB / comp×mip → native, **O2-H** closed
tessellation → native, and **RT-4** moved sample positions kernel → native). EXP-0042 then
reopened graphics code-window/stage-selector integration, making the current total **10**.

### (a) Metal-exposed capabilities still NOT hardware-exercised — objective-2 residue (prioritized)

**Metal-exposed residue is 1:** graphics code-window/stage-selector integration (§15). The three
former residue rows below remain closed by EXP-O2G, and tessellation remains closed by EXP-O2H;
they are retained here as a closed-item log.

| # | (former) NYC capability | Resolution | Method |
|---|---|---|---|
| 1 | **Shader `printf`** (§2) — printf buffer ABI | **CLOSED by EXP-O2G (native-decoded):** macOS 26 uses `os_log` (not MSL printf), logging into a driver-allocated `MTLLogState` buffer with self-describing records; shader calls helper `l___air_impl_os_log`. See `cmdstream/README.md`. | compiled a kernel with `os_log`, captured the log buffer, decoded the record/format encoding. |
| 2 | **Draw-mesh-into-ICB** (§13) | **CLOSED by EXP-O2G (native-decoded):** `MTLIndirectCommandTypeDrawMeshThreadgroups` lowers to the **same mesh-grid-dispatch record `0x70000600`** — no new work type; command-count `@0x18000+0x04`. | encoded `drawMeshThreadgroups` into an ICB; diffed the ICB inline-command record vs the standalone mesh-grid-dispatch record. |
| 3 | **Compression × mipmap interaction; NPOT small thresholds** (§14) | **CLOSED by EXP-O2G (native-decoded):** one **contiguous aux buffer covers all mip levels**; NPOT compression threshold = **W ≥ 16 ∧ H ≥ 16** texels (unpadded, bpp-independent). | swept compressed mipmapped NPOT textures near the size thresholds; read back the aux/state layout. |
| 4 | **Tessellation** (§9) — `drawPatches` (Apple9) | **CLOSED by EXP-O2H (native-decoded):** native VDM patch-dispatch record `0x40`, half-float factor buffer, ordinary post-tess `__vertex` shader; NOT compute-emulated. | `drawPatches` with CPU factors → no-CDM BO inventory + subdivision + half-factor readback. |

### (b) Honestly excluded from objective 2 (kernel-managed + microarch-only)

These are **not** objective-2 blockers: they are either firmware/register state routed through the
kernel submit (userspace never emits an ISA/cmdstream encoding for them) or microarchitectural behaviors
with **no single emittable encoding** (observable only via throughput/occupancy microbenchmarks + Xcode
performance counters). Listed for completeness with a one-line reason each.

**Microarch-only (no emittable descriptor/instruction; counters/microbench only):**
- **Dynamic Caching dynamic behavior** (§15) — register-file-as-cache alloc/dealloc curve; we have the *static* model (96 GPRs, spill, occupancy tier) but not the dynamic allocation curve Apple markets.
- **Flexible unified on-chip memory** (§3) — unified L1 sharing reg/tg/tile/stack/buffer; observable only via cache-hit/eviction counters.
- **2× ALU (dual-issue FP16/FP32/int)** (§1) — a throughput property, not an opcode; observable via a dual-issue throughput microbench.
- **Full occupancy / latency-throughput curve** (§15) — per-op latency & the halfregs→max-threads occupancy curve; a perf measurement, not an encoding.
- **RT reorder stage** (§8) — firmware/microarch stage that groups intersection calls; observable only via Xcode RT-scratch counters.
- **Lossless compression block codec** (§14) — the 8×4-block codec bit-layout is a HW-internal, per-generation-revised format, **not** a Metal-exposed capability; a documented disable-fallback exists (allocate + wire aux flags, or clear them). Treated as opaque, not an objective-2 gate.

**Kernel-managed (real HW state routed via the kernel submit — `kernel-interface.md`):**
- **RT BVH build + node format** (§8) — GPU/firmware builds the BVH; node format not userspace-visible (userspace supplies vertices + build descriptor).
- **Depth store-action / ZLS** (§12) — `ZLS_CTRL`; firmware-programmed at render-pass granularity.
- **Partial-render / tiler-param overflow trigger** (§12) — firmware detects overflow; no userspace knob.
- **Scissor test** (§10) — `isp_scissor_base` submit param.
- **Graphics code-window / stage-selector mapping** (§15) — M4 selectors are partial; queue-base mapping and A18 validation remain open.

### (c) Extrapolate-and-test probes (mostly Vulkan/GL wants that Metal does NOT expose)
> **Correction (EXP-O2H):** **tessellation** is **NATIVE HW** on Apple9 — `drawPatches` → native VDM patch-dispatch record `0x40`, half-float factor buffer, ordinary post-tess vertex fn; **NOT compute-emulated**. It is now classified **native-decoded** (§9), no longer a residue. Geometry shaders and transform feedback genuinely have no Metal path → emulate.

Not strict objective-2 blockers (Metal exposes no path), but tracked on the `hypotheses.md`
extrapolate-and-test backlog because each is a native-or-emulate decision for a Vulkan/GL driver. Still
NYC (3): **anisotropy >16×** (§5, field encodes 128× but Metal caps 16×), **wide/smooth lines** (§10,
Metal line width fixed), and **conditional rendering** (§10, CPU-emulated in Mesa). *(The GS/tess/XFB
A18-native re-probe is now RESOLVED — §9: **tessellation is NATIVE** (EXP-O2H); GS + transform-feedback
confirmed still Metal-unexposed → emulate.)*

EXP-O2A resolved three more of these to a definitive **Metal-unreachable → emulate** (no proven native
path via Metal): **polygon-point fill** (now classified emulated in §10 — Metal exposes fill/lines only),
**cull distance** (MSL exposes clip only; the clip half is native), and a **custom primitive-restart
index** (the HW field at `0x18000+0x68` exists but Metal always writes all-ones). A Vulkan/GL driver that
needs point-fill or cull-distance must emulate.

---

## 17. Summary counts

Total enumerated capabilities: **214** rows across §1–§15 (some rows bundle a family of related
sub-ops; the per-section tallies below sum the row counts).

| Status | Count | What it means |
|---|---|---|
| **native-decoded** | **189** | HW representation decoded in `docs/` (many HW-validated; *(partial)* = principal encoding decoded, sub-fields ⏳; *(lowered)* = no dedicated silicon but the compiler expansion into native ops is decoded & HW-validated; *(mechanism)* = realized through an already-decoded path, no new opcode). Includes **sample positions** (RT-4, userspace-emittable @+0x40), **native tessellation** (EXP-O2H), and the O2-G closures (printf/os_log, mesh-in-ICB, compression×mip). |
| **emulated** | **11** | HW-absent or no proven Metal path → Vulkan/GL must software-emulate. 5 HW-validated absences (float atomic min/max, **64-bit atomic add + min/max** — 64-bit atomics entirely absent from MSL, arbitrary border color, int8 coopmat) + fp64 + no-D24S8 + **polygon-point fill** (Metal-unreachable, EXP-O2A) + **geometry shaders** + **transform feedback** (classically-absent, not re-probed on A18) + the **compute-tessellation fallback** (A18 tessellation is NATIVE, §9, but the `libagx` compute path is retained as an optional fallback capability). |
| **kernel-managed** | **4** | Firmware/register state routed via the kernel submit (RT BVH build, ZLS/depth store, partial-render trigger, scissor). Graphics selection is not proven kernel-owned. **(Sample positions moved OUT — RT-4: userspace-emittable, native.)** |
| **NOT-YET-CHARACTERIZED** | **10** | Nine earlier backlog rows plus the Metal-exposed graphics code-window/stage-selector mapping reopened by EXP-0042. The other nine remain 6 microarch-only + 3 Metal-unreachable. |

Per-section tallies (native-decoded / emulated / kernel / NYC):
§1 ALU 28/1/0/1 · §2 CF 14/0/0/0 · §3 mem 12/0/0/1 · §4 atomics 7/3/0/0 · §5 tex/samp 19/1/0/1 ·
§6 subgroup 9/0/0/0 · §7 matrix 8/1/0/0 · §8 RT 12/0/1/1 · §9 mesh/geo 6/3/0/0 ·
§10 raster/blend 18/2/1/2 · §11 interp 7/0/0/0 · §12 TBDR 14/0/2/0 · §13 dispatch 9/0/0/0 ·
§14 format/tiling 18/0/0/1 · §15 machine-model 8/0/0/3.
**Totals: native-decoded 189 · emulated 11 · kernel-managed 4 · NYC 10.** (189+11+4+10 = 214 rows.) EXP-0042 reopens one Metal-exposed integration item: graphics code-window/stage-selector mapping. The other 9 NYC rows remain 6 microarch-only + 3 Metal-unreachable.

### Apple-advertised features and their observability

Every WWDC/Tech-Talk Family-9 hardware claim maps to at least one observable — none is unmappable:

| Apple-advertised (WWDC) | Mapped to | Status |
|---|---|---|
| Hardware ray tracing (fixed-function traversal) | `rt_intersect`/`rt_as_load`/`0x5f` ray-data; RT-from-render + primitive/instance motion blur now decoded (§8) | native-decoded |
| RT **reorder stage** | microarch/firmware; RT-scratch counters | NOT-YET-CHARACTERIZED (§8; §16b) |
| Hardware mesh shading | object/mesh HW pipeline + store-based emit + `0x70000600` dispatch (§9) | native-decoded (EXP-0030) |
| Dynamic Caching (register file as cache) | static footprint model native; dynamic behavior microarch (§15) | NOT-YET-CHARACTERIZED (§16b) |
| Flexible on-chip memory (unified cache) | microarch; cache/eviction counters (§3) | NOT-YET-CHARACTERIZED (§16b) |
| 2× ALU (parallel FP16/FP32/int) | microarch; throughput microbench (§1) | NOT-YET-CHARACTERIZED (§16b) |
| Free FP16↔FP32 conversion | `0x11` / free size-bit / `as_type` (§1) | native-decoded |
| Programmable blending (TBDR) | blend compiled into FS (§10) | native-decoded (mechanism) |
| Mesh threadgroups 1M+ / ICB mesh draws | mesh-grid-dispatch `0x70000600` native (§9); ICB-mesh draw path still NYC (§13) | native-decoded (dispatch) / NYC (ICB) |

> The three "no-single-encoding" microarchitectural claims — **Dynamic Caching dynamic behavior**,
> **flexible unified on-chip memory**, and **2× ALU** — have **no emittable descriptor/instruction**;
> they are only observable indirectly (throughput/occupancy microbenchmarks + Xcode performance
> counters). They are honestly marked NYC rather than native (§16b): we have the *static* register model
> (96 GPRs, spill, occupancy tier) but not the *dynamic* allocation curve Apple markets.

---

## Provenance

Synthesis of `docs/isa/README.md` (EXP-0001/0003/0005/0006/0007/0010/0012/0013/0016/0018/0020/0022/
0023/0025/0026/0029/0030/0031/0033/0034/0035/0037/0038 + O2-C/O2-D) and `docs/isa/encoding-tables.md`
(EXP-0036/0039/0040), `docs/isa/msl-feature-map.md` (MSL surface index A1–A21 / B1–B8 into the public MSL
spec), `docs/cmdstream/README.md` (EXP-0009/0011/0014/0019/0024/0027/0030 + O2-A + G1-a/c/e),
`docs/descriptors/README.md` + `format-table.md` (EXP-0015/0017/0028 + O2-B + G1-b), `docs/tiling/README.md`
(EXP-0017/0028), `docs/pipeline/README.md` (EXP-0021 + G1-b), `docs/capability-matrix.md`,
`docs/hypotheses.md` (#1–#25), `docs/kernel-interface.md`,
`docs/mesa-userspace-requirements.md`, `docs/hardware-overview.md` (§3 `MTLDevice` capability probe,
EXP-0002), `PROVENANCE.md` (authoritative HW-validation log), and the public WWDC/Tech-Talk material in
`gpu_knowledge/apple_official/wwdc/` (Family-9 GPU advancements: Dynamic Caching, HW ray tracing +
reorder stage, HW mesh shading, 2× ALU, flexible on-chip memory). No new experiment; no Apple binary
introspected.

## Historical update (EXP-O2G / O2-H / RT-4), superseded for graphics integration by EXP-0042
The three O2-G items, tessellation, and programmable sample positions remain closed as recorded.
However, EXP-0042 falsified the claimed graphics positional-walk/FS-size model, so graphics
code-window/stage-selector integration is again Metal-exposed and open. Current reconciled counts
are native 189 / emulated 11 / kernel 4 / NOT-YET 10 (=214).

## Update (EXP-M4-12): instruction census COMPLETE — G-13 fully met
The **instruction-census** axis of the secondary goal (`../CLAUDE.md` G-13: "every opcode the compiler
emits must be decoded; ~0 undecoded byte0 groups over a broad corpus") is now **exactly 0**: the
broad OWN-SHADER corpus tokenizes at **100.0% byte coverage — 0 undecoded resync regions, 0 byte0
groups the DB cannot decode** (was 97.4%). EXP-M4-12 closed the final 2.6% with 4 parallel
investigation subagents that isolated each residue op in a single-op shader; **every residue was a
length-rule gap or a 2-byte over-read, not an unknown opcode** (the only genuinely-new instruction was
the half `0x39` combine op). This confirms — at the strongest granularity — that **no unknown
instruction family exists** in the A18/M4 (Apple9) compiler output. Round-trip ALL PASS (whole-program
walk, 0 leftover bytes). Operand sub-fields of the SFU range-reduction words remain deliberately
undecoded (clean-room rule 5: decoding them would transcribe a compiler sequence); they are
family-labeled, not unknown. See `experiments/EXP-M4-12-isa-residue-closure/`.

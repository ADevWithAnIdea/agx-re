# A18 Pro GPU Userspace — Documentation Roadmap

Status board for the clean-room documentation effort. Read `../CLAUDE.md` first for the rules.

Target: **Apple A18 Pro, SoC T8140, macOS 26.6, Metal feature family Apple9, 5 GPU cores.**
Baseline for comparison: Mesa's existing M1 (Apple7 / G13) and M2 (Apple8 / G14) support in `../mesa/src/asahi`.

Legend: ☐ not started · ◐ in progress · ☑ documented & provenance-cited · ⚠ blocked

**Cross-cutting thread — capability probing (extrapolate & test):** running through every
phase, not a separate phase. For each subsystem, beyond documenting what Metal exercises, we
hypothesize hardware capabilities Metal doesn't expose (esp. Vulkan/GL-shaped ones) and test
them on hardware, logging every attempt — pass or fail — in `hypotheses.md`. See `../CLAUDE.md`
→ Methodology.

**Master completeness checklist:** `mesa-userspace-requirements.md` — a 52-row coverage matrix
mapping every A18-hardware-specific dependency in Mesa's userspace to an owning `docs/` area,
with a prioritized gap list. This is the concrete target the acceptance gate grades against;
keep its Status column current as phases complete.

---

## Phase 0 — Foundations & clean-room tooling
Goal: prove every clean-room technique works end-to-end before doing real RE.

- ☑ **0.1 Environment recon** — chip/OS/toolchain/SIP/sudo/reboot path, GPU codename from device tree (`ioreg` `compatible`/`gpu-core-count` — hardware documentation, safe). *Done: EXP-0002 (`experiments/EXP-0002-hw-identity-recon/`) → `docs/hardware-overview.md`. GPU codename **G17P**; device-tree `sgx@70000000` / `compatible="gpu,t8140"`; **6-core die, 5 active** (core #1 fused); Apple9 / Metal 4; interface via `AGXDeviceUserClient` over IOGPUFamily 130.16.3 / AGXG17P 353.10. Also confirmed in bring-up: CLT-only/SIP off/FileVault off.*
- ☑ **0.2 Own-shader compile+extract tool** (`tools/shdump`) — *Done: EXP-0001.* MSL → `MTLBinaryArchive` → our parser extracts `_agc.main` from the AppleGPU (cputype 0x1000013) image. Deterministic; confirmed machine code (not AIR). → `docs/isa/README.md`.
- ☑ **0.3 (Dis)assembler scaffolding & method** — *Done: EXP-0005.* `tools/agx-isa/` is a working machine-readable DB driving asm+disasm with a passing round-trip test; differential compilation + persistent sweep runner established as the method. Phase 1 now grows this DB.
- ☑ **0.4 Hardware testbed (the round-trip engine)** — *Done: EXP-0003.* `tools/agxtest/` splices arbitrary bytes into our own compiled shader and runs on the real GPU (Metal runs tampered code, no integrity check, via bound `MTLBinaryArchive` + `FailOnBinaryArchiveMiss`). First HW-validated fact: op-select `1c=fadd/1d=fmul`. Faults are contained (0 reboots). **The extrapolate-and-test loop is live.**
- ☑ **0.5 IOKit/IOGPU data-tracing harness** (`tools/iotrace`) — *Done: EXP-0009.* DYLD interposer captures our own Metal process's IOKit traffic + BO contents. Found: submission = shared-mem+doorbell (not per-call ioctl); `AGXAcceleratorG17P` sel 9 = map-resource→GPU-VA; argument buffer / launch descriptor / shader BO located. → `docs/cmdstream/README.md`. **Phase 2 foundation set.**

## Phase 1 — Full A18 Pro AGX (dis)assembler + ISA spec  ⟵ PRIMARY TOOL DELIVERABLE
Build a **complete, hardware-validated, machine-readable AGX instruction database that both
disassembles AND assembles** A18 Pro shaders — the A18 counterpart to dougallj/applegpu. The
assembler is not optional: it is the engine of the extrapolate-and-test loop (to test whether
an instruction/modifier exists, we must be able to *encode* it, run it via the 0.4 testbed, and
observe). Correctness bar: **round-trip identity** — `disassemble(assemble(x)) == x` and
`assemble(disassemble(bytes)) == bytes` across the whole validated corpus.

- ◐ **Opcode map** — *float + integer arithmetic mapped (EXP-0005/6/7):* length rules for float & integer groups; float ALU (fadd/fmul) + integer (iadd/isub/imul/imad, imin/imax) HW-validated. Byte0 groups so far: `0x09` float-ALU, `0x0b` float-unary/bitwise, `0x12` fmin/max & int-cmp, `0x67/e7` load/store, `0x9f/0x1f` int-arith, `0x02` int-min/max, `0xa7` shift/bfe, `0x27` popcnt, `0x0c` preamble, `0x0e` stop; **vtx/frag-only (pending decode):** `0x2f/3f/af` ALU-f, `0x07/87/97` mem, `0x05/06/57` varying-store, sample `0x18/b0`, deriv `0x37/38/39/90/92`. Remaining: fma/unary/minmax float ops, bitwise/shift/cmp detail, memory, control-flow, texture, atomic, subgroup, RT/mesh.
- ◐ **Per-instruction spec** — *float ALU 2-src fully mapped & HW-validated (EXP-0005/0006):* op-select, dst/srcA/srcB register fields (`(reg<<1)|is32`), srcB negate (bit43), srcB imm-mode (bit39), 8-bit-minifloat immediate. Register model preliminary (64 GPRs). **Next: integer ALU (0x9f), fma/3-src & float-unary & fmin/max, memory addressing, control flow, textures, atomics, subgroup, RT/mesh** — plus confirm register model (uniforms, dst width, Dynamic Caching).
- ☑ **Machine model** — *EXP-0020: 96 GPRs, halves 2/GPR, uniform register file + uniform program (constant_program), footprint in __GPU_METADATA, spill to scratch >96 (Dynamic Caching).* → `docs/isa/README.md`.
- ◐ **New instruction families** — ✅ atomics/subgroup/quad (0018), texture (0016), **matrix `0xcf` 8×8×8 (0022)**. Remaining: **ray-tracing intrinsics, mesh shading** (exotic Apple9, biggest gaps).
- ☐ **Extrapolate & test** — sweep undocumented opcode/modifier space; log every probe (works/no-op/faults) in `hypotheses.md`.
- Deliverables: `../tools/agx-isa/` (the assembler+disassembler, round-trip-tested) **and** `isa/` (prose + encoding tables). The tool is the executable form of the documentation.

## Phase 2 — Control / command stream & state
- ☐ VDM (draw) / CDM (compute) / tiler / fragment command lists.
- ☐ USC binding words (shaders, textures, samplers, uniforms).
- ◐ State packets — *EXP-0019: depth/stencil + rasterizer packets decoded; blend is PROGRAMMABLE (lowered into fragment shader, not a packet); USC bind template mapped.* → `docs/cmdstream/README.md`.
- Method: black-box trace + change-one-Metal-parameter diffing. Deliverable: `cmdstream/`.

## Phase 3 — Resource descriptors & texture layout
- ☐ Texture / sampler / buffer descriptor bit layouts; bindless/argument-buffer model.
- ☐ Tiling/swizzle order + lossless compression per format.
- Deliverables: `descriptors/`, `tiling/`.

## Phase 4 — TBDR & compute specifics
- ☑ Tile size (32×32 fixed), imageblock/tile-memory budget, MSAA sample count, memoryless, load/store segments, tiler param buffer — *EXP-0021 → `docs/pipeline/README.md`*. (Programmable sample positions + depth/ZLS store are firmware-managed → kernel.) OPEN: sample-position firmware path.
- Deliverable: `pipeline/`. ✅

## Phase 5 — Synthesis & handoff, and the ACCEPTANCE GATE
- ☐ "Mesa A18 Pro userspace porting guide": per `src/asahi` module, what changes, with experiment citations.
- ☐ Completeness cross-check against Mesa's M1/M2 module list.
- ☐ **Acceptance gate (defines "done" — see `../CLAUDE.md` → Definition of Done):** a dedicated
  reviewer subagent, given ONLY `docs/`, must conclude it could implement A18 Pro Mesa userspace
  from scratch with **nothing else needed**. Run it early and often as a **gap-finder** to steer
  the work; the project is complete when it returns clean. Every gap it reports → new work item.

---

## Experiment log & queue (orchestration tracker — resume point)
Done (committed, provenance-cited): **0001** shader byte extraction · **0002** HW identity/interface ·
**0003** hardware testbed + first opcode · **0005** ISA DB + length rule + float op-select ·
**0006** float ALU operands + minifloat imm · **0007** integer ALU family · **0008** vtx/frag
extraction + render testbed · **0009** iotrace: submission model + interface + cmdstream structs located ·
**0010** control flow: predication+jumps+program-structure+uniform/base-slot ·
**0011** compute cmdstream: CDM launch descriptor + Tier-2 arg buffer + ring located ·
**0012** memory · **0014** graphics cmdstream first pass (VDM record + TA/3D split + viewport/attachment) · **0013** scalar ALU complete (conversions/fma/unary/transcendental/bitwise-LUT/shift/compare) · **0015** descriptors: texture(32B)+sampler(8B)+buffer layouts · **0016** texture-ISA: sample/read/write/query/derivative · **0018** atomics+subgroup/quad · **0019** state packets + programmable-blend + USC grammar · **0020** machine model (96 GPRs, uniforms, spill) · **0021** TBDR pipeline · **0022** matrix unit · REVIEW-01 gap-analysis · **0023** ray tracing (hybrid) · **0024** cmdstream G-3/G-7/G-8 · SYNTH kernel-interface+capability-matrix (G-10/11/12) · **0025** async model = HW interlock (G-1) · **0017** tiling: Morton twiddle + mip packing + compression aux (codec open). *(Survey: mesa-userspace-requirements, msl-feature-map.)*

**Next queue (ISA, Phase 1):** control-flow + program structure/termination + preamble/uniform-load;
float fma/3-src + funary(0x0b) + fmin/max(0x12) detail; bitwise/shift/bitfield/cmp-select validate;
memory addressing (device/threadgroup/constant load-store forms); conversions (fp16/fp32/int);
texture sample/gather + samplers; interpolation/derivatives (fragment); atomics; subgroup/quad;
register-model confirm (uniforms, dst width, Dynamic Caching); then exotic Apple9 (RT, mesh, matrix).
**Next queue (Phase 2+):** cmdstream decode (post-0009); descriptors; tiling; TBDR/pipeline.

**Orchestration policy:** ≤2 parallel device experiments, on **disjoint files** (e.g. one editing
`tools/agx-isa`, one editing `tools/iotrace`); faults are contained (0 reboots so far). Orchestrator
owns `docs/`, `ROADMAP.md`, `PROVENANCE.md` and serializes edits to any shared tool file.

## FINAL PUSH — gap queue from REVIEW-01 (acceptance gap-analysis, FAIL verdict)
Full report: `reviews/GAP-ANALYSIS-01.md`. Close these to pass the acceptance gate. Priority order:

**CRITICAL (blocks any real shader/draw):**
- ☑ **G-1 Async model** — *EXP-0025 (INVERTS premise): HW register interlock, NO software scoreboard/wait (unlike G13). Compiler must NOT emit G13 waits. Only ordering op = threadgroup_barrier 0x07 (byte+3 mem-scope); splice-proven silent-corruption surface. Fragment tilebuffer ordering = follow-up.*
- ☐ **G-2 Transcendental sequences** rcp/rsqrt/sqrt/sin/cos (0x29 seed + Newton-Raphson refinement). [ISA]
- ☑ **G-3 Graphics shader binding** — *EXP-0024: NO shaderVA>>N in userspace; code BO = self-describing sized-block walk + USC uniform-preamble programs; code-base→fw handoff = kernel item.*
- ☐ **G-4 Fragment varying interpolation** — iter/ldcf coefficient model for interpolated FS inputs. [ISA/frag]
- ☐ **G-5 Special-register enum + preload ABI** — SR-number table; preloaded-reg ABI (vtx/instance id, VS attrib base, FS epilog contract). NEW `docs/abi/`. [ISA/ABI]

**STRUCTURAL (self-containment — the gate reads ONLY docs/):**
- ☐ **G-6 Encoding tables IN docs/** — render the instruction DB into `docs/isa/encoding-tables.md` (stop deferring to tools/db.json); move the per-format Channels/sizeclass table into `docs/descriptors/`; validate the ⏳ operand widths (int src regs, bitwise/shift/cmp).

**HIGH:**
- ☑ **G-7 PPP header** — *EXP-0024: length word (not present-mask) + per-packet enable bits.*
- ☑ **G-8 tgmem size + CDM config** — *EXP-0024: tgmem=(bytes<<2)|0x80 in shader BO; config bit23=occupancy tier.*
- ◐ **G-9 RT ✅ (EXP-0023: hybrid — HW intersect ops + shader BVH loop; build firmware-managed) + mesh shading (TODO)** hardware docs. [ISA]
- ☑ **G-10 Native-vs-emulated capability matrix** → `docs/capability-matrix.md` (13 native / 7 emulate / 5 kernel-managed / 6 unknown).
- ☑ **G-11 Contradiction reconciled** → `docs/kernel-interface.md`: userspace *computes* value, kernel *writes register* as submit-ioctl param (not in command stream). Both docs right at different layers.
- ☑ **G-12 Kernel-interface contract** → `docs/kernel-interface.md` (submission model, VA-space table, 5 firmware-managed items, what kernel must provide).

**MEDIUM:** programmable-blend epilog ABI; BC/ASTC + 3D/cube/array/MSAA twiddle; MSAA sample-interleave + occlusion query; explain magic values (CDM/USC config word 0x00880000, store-prog 0x6f, VDM 0x61c4/0x61f2, 0x300-seg grammar, num_gps/num_frags/is_sksm).

## Known premises (given, not to be re-questioned)
- **The A18 Pro AGX ISA is a completely new instruction set vs M1/M2 (G13/G14).** Opcodes are
  entirely different. Do not spend effort "measuring the delta" against applegpu — build the
  A18 instruction table from scratch by differential compilation + hardware validation.
- The GPU is designed for Metal (+ a narrow GL subset). Expect Vulkan/GL features that the HW
  lacks (→ must be emulated) and HW capabilities Metal never exposes (→ probe for them).

## Tooling backlog (needed to unblock coverage)
- ☑ **Vertex & fragment extraction + render testbed** — *Done: EXP-0008.* `shdump --render` +
  `agxparse --stage {compute,vertex,fragment}`; `tools/agxtest/agxrender.m` runs modified fragment
  code and reads back pixels. Fragment-only families are now reachable.
- Consider a `newLibraryWithURL:`-per-request **persistent render runner** for fast fragment sweeps
  (mirror `persistrun.py`), when fragment decode experiments start.

## Open questions / risks
- **Modern submission path:** macOS 26 Metal likely submits via IOGPU shared-memory rings, not one `IOConnectCallMethod` per draw (unlike Alyssa's 2021 approach). 0.4 must confirm how to capture it. → the deciding risk for Phase 2.
- **Does A18 Pro differ from A17 Pro/M3 (both Apple9) at the encoding level?** Empirical — Phase 1/2 answer it.
- **AMFI/injection:** our own harness is unsigned → `DYLD_INSERT_LIBRARIES` should work without boot-args. Only tracing *Apple's own* processes would need `amfi_get_out_of_my_way`; deferred until/unless needed.

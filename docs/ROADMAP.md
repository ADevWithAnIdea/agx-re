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
**0012** memory · **0014** graphics cmdstream first pass (VDM record + TA/3D split + viewport/attachment) · **0013** scalar ALU complete (conversions/fma/unary/transcendental/bitwise-LUT/shift/compare) · **0015** descriptors: texture(32B)+sampler(8B)+buffer layouts · **0016** texture-ISA: sample/read/write/query/derivative · **0018** atomics+subgroup/quad · **0019** state packets + programmable-blend + USC grammar · **0020** machine model (96 GPRs, uniforms, spill) · **0021** TBDR pipeline · **0022** matrix unit · REVIEW-01 gap-analysis · **0023** ray tracing (hybrid) · **0024** cmdstream G-3/G-7/G-8 · SYNTH · **0025** async model = HW interlock (G-1) · **0026** transcendentals (G-2) · SYNTH capability-census · **0027** indirect/occlusion/timestamp · **0028** format codes+twiddle · **0030** mesh · **0029** fragment ISA (G-4) · **0031** SR/ABI (G-5) · **0033** int/bitfield (#12) · **0034** texture variants (#14) · **0035** function/pointer/dylib ABI (#13; 0x43=call marker) · **0017** tiling: Morton twiddle + mip packing + compression aux (codec open). *(Survey: mesa-userspace-requirements, msl-feature-map.)*

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
- ☑ **G-2 Transcendentals** — *EXP-0026: SFU 0x2f/0xaf single-op + 0x29 estimate+NR precise; pow/div/sin/cos composites. Driver gap: large-arg trig needs SW range reduction.*
- ☑ **G-3 Graphics shader binding** — *EXP-0024: NO shaderVA>>N in userspace; code BO = self-describing sized-block walk + USC uniform-preamble programs; code-base→fw handoff = kernel item.*
- ☐ **G-4 Fragment varying interpolation** — iter/ldcf coefficient model for interpolated FS inputs. [ISA/frag]
- ☑ **G-5 SR enum + shader ABI** — *EXP-0031: get_sr SR#=byte1 + full table; no ID preload (get_sr on demand); VS attribute fetch = in-shader software (driver generates from vertex format). → `docs/isa/README.md`.*

**STRUCTURAL (self-containment — the gate reads ONLY docs/):**
- ☐ **G-6 Encoding tables IN docs/** — render the instruction DB into `docs/isa/encoding-tables.md` (stop deferring to tools/db.json); move the per-format Channels/sizeclass table into `docs/descriptors/`; validate the ⏳ operand widths (int src regs, bitwise/shift/cmp).

**HIGH:**
- ☑ **G-7 PPP header** — *EXP-0024: length word (not present-mask) + per-packet enable bits.*
- ☑ **G-8 tgmem size + CDM config** — *EXP-0024: tgmem=(bytes<<2)|0x80 in shader BO; config bit23=occupancy tier.*
- ☑ **G-4 fragment interpolation ✅ (EXP-0029).** **G-9 RT ✅ (EXP-0023 hybrid) + mesh shading ✅ (EXP-0030: HW pipeline, compute-store emit, 0x43 marker, graphics-path submission; UVB firmware-managed)**. [ISA]
- ☑ **G-10 Native-vs-emulated capability matrix** → `docs/capability-matrix.md` (13 native / 7 emulate / 5 kernel-managed / 6 unknown).
- ☑ **G-11 Contradiction reconciled** → `docs/kernel-interface.md`: userspace *computes* value, kernel *writes register* as submit-ioctl param (not in command stream). Both docs right at different layers.
- ☑ **G-12 Kernel-interface contract** → `docs/kernel-interface.md` (submission model, VA-space table, 5 firmware-managed items, what kernel must provide).

**MEDIUM:** programmable-blend epilog ABI; BC/ASTC + 3D/cube/array/MSAA twiddle; MSAA sample-interleave + occlusion query; explain magic values (CDM/USC config word 0x00880000, store-prog 0x6f, VDM 0x61c4/0x61f2, 0x300-seg grammar, num_gps/num_frags/is_sksm).

**SECONDARY GOAL — CAPABILITY COMPLETENESS (understand everything the HW can do).** Two census axes,
tracked in `docs/capability-completeness.md` (see `../CLAUDE.md` → Secondary goal):
- **Instruction census** = G-13 below (every opcode decoded; ~0 undecoded byte0 groups).
- **Capability census** = enumerate every Metal/MSL feature + every Apple-advertised (WWDC Family-9)
  feature → map to HW representation → classify native/emulated/kernel/NOT-YET-CHARACTERIZED → drive
  the NOT-YET list to 0.
  **STATUS (`docs/capability-completeness.md`, 214 rows): native 110 · emulated 9 · kernel 6 · NOT-YET 89.**
  Top backlog: mesh shading, fragment interpolation(G-4), transcendentals(G-2), SR/preload ABI(G-5),
  imageblock/tile-shader/raster-order ISA, compression codec, wait_pix/signal_pix, RT completion,
  format codes+3D/cube/array/MSAA twiddle, indirect/ICB, bitfield/int completeness (clz/ctz/insert/
  reverse/rotate/pack/64-bit), function-call/pointer ABI, sample_compare/gather variants. Microarch
  items (Dynamic-Caching dynamic behavior, 2× ALU) observable only via counters — lower priority.

**G-13 — INSTRUCTION-FAMILY COMPLETENESS (calibration: dougallj/applegpu M1 ≈ 124 instruction
classes; we have 40 family-heads ≈ ~70-90 logical — several whole families still missing).** Decode
the byte0 groups seen in real shaders but not yet decoded:
- ☑ **Fragment varying interpolation** — *EXP-0029: `iter` 0x2f (byte+5 slot, byte+6 mode); flat=iter_flat 0x1f; perspective=multi-instr.*
- ◐ **Varying / tilebuffer / imageblock** — *EXP-0029: frag output `frag_color_store` 0xe7/06, tilebuffer read `tile_read` 0x67/0e. Remaining: vertex varying-store 0x05/06/57, imageblock.*
- ☑ **Pixel ordering (ROG)** — *EXP-0029: no dedicated op; 0x07 fence family acquire/release.*
- ☐ **Control-flow exec-mask sub-ops** — `0x0f` beyond `jump`: `else`/`while`/`break`/`pop`/
  `reconverge`/`jmp_exec` variants (push/else/pop noted, not decoded).
- ☐ **Stack spill/fill** — scratch load/store (EXP-0020 saw the behavior, not the ops).
- ◐ **Pack/unpack + int/bitfield ✅ (EXP-0033)**; register-shift-prep `0x2b/0x3b/0x5b/0x8b` family still ⏳.
- ☐ **Special-function estimates** — rcp/rsqrt/exp2/log2 estimate + refine [= G-2, EXP-0026 in progress].
- ☐ **RT companions** — `0x5f`, ray-move ops (EXP-0023 follow-up).
- ☑ **Texture variants ✅ (EXP-0034)** — sample_compare (native PCF), gather+offset, LOD-query, image atomics native, array/cube/3D dims.
- ☐ **Misc** — `nop`, fence/barrier scope variants, device-scope barrier (`0x85`).
Target: iterate until a byte0-group census of a broad shader corpus shows ~0 undecoded groups.

**G-14 — coverage-matrix not-started rows (EXP-descriptors/matrix sync: done 5 / partial 39 / not-started 8):**
- ☐ Fragment-only ISA ops (iter/ldcf/ld_tile/st_tile/zs_emit/sample_mask) [overlaps G-13].
- ☑ Device-generated **indirect** draw/dispatch + ICB — *EXP-0027: opcode switch + args-struct ptr; indirect dispatch needs driver grid-setup multiply.*
- ☑ **MSAA / occlusion / timestamps** — *EXP-0027 + EXP-0028: occlusion+timestamps decoded; MSAA sample interleave = sample-major (offset=(N*morton+sample)*bps, 2x/4x).*
- ☐ **UVS / varyings** linkage (vertex↔fragment interface); NIR-lowering HW-workaround facts.
- ☐ **Sparse** page-table / folio geometry (kernel-adjacent).

**G-6 core still owed:** render `tools/agx-isa/db.json` into `docs/isa/encoding-tables.md` so the ISA's
authoritative opcode table is IN `docs/` (do LAST, once the DB is final). The descriptor tables are now
self-contained (`docs/descriptors/format-table.md`).

**Final ISA-consolidation pass (deferred, do once ISA experiments finish):** merge these staged files into
`isadb.py`, regenerate `db.json`, ensure round-trip passes, THEN generate `docs/isa/encoding-tables.md` (G-6 core):
- `experiments/EXP-0030-mesh/new_descriptors.json` (obj_mesh_ctrl 0x43, stage-map __object/__mesh)
- `experiments/EXP-0031-sr-abi/new_descriptors.json` (get_sr byte1 SR#, mov_imm, sr_number_table)
- `experiments/EXP-0033-int-bitfield/new_descriptors.json` (ibitcount/irotate/half_alu/pack + **6 length-rule corrections**)
- `experiments/EXP-0034-texture-variants/new_descriptors.json` (tex_sample refine + tex_atomic)
- `experiments/EXP-0035-function-abi/new_descriptors.json` (pending EXP-0035)
Prose docs already carry each experiment's facts, so `docs/` stays complete meanwhile. THEN: byte0-group
census (instruction-census metric) + re-run acceptance reviewer (REVIEW-02).

**Mesa-schema `agx3.xml` deliverable (data, not code — within our doc mandate):** after the census is clean,
mechanically render `db.json` into Mesa's `src/asahi/isa/AGX2.xml` schema (`<group>`/`<ins>`/`<enum>`/`<exact>`/
`<src>/<dest>/<immediate>/<modifier>`) as `docs/isa/agx3.xml`, so the impl team can drop it into `src/asahi/isa/`
and generate the G17P disassembler. Still-inferred operand sub-fields → reserved/`<zero>` bits (as Mesa itself does),
tightened as they're decoded.

## ENDGAME (unattended) — wrap-up, then red-team. Do NOT stop until the red-team passes clean.

### Phase W — WRAP-UP (finish the original goal)
- ☑ **W1** EXP-0036: DB 61 descriptors (round-trip 237 OK), `encoding-tables.md` (G-6 done), census ~82% bytes decoded.
- ☑ **W2** *(EXP-0037/0038 merged via EXP-0039)* — DB 68 descriptors, round-trip green, census 87.9%, NO whole undecoded family remains. Closed: **vertex/mesh varying-store `0x05/06/57`; half pack/unpack `0x18/0x30/0x38`; u64 carry-gen `0x32`; texture addr/interp math `0x2e/0xb0/0x92/0x26`; non-leaf frame prologue `0x6f`; simd/unpack `0x54`-cache variants.** Per-experiment files → merge.
- ☐ **W3** Emit `docs/isa/agx3.xml` (Mesa schema) + finalize `docs/isa/encoding-tables.md`.
- ☐ **W4** Phase-5 synthesis: `docs/porting-guide.md` (per `src/asahi` module) + re-run acceptance reviewer
  (REVIEW-02, read-based); close whatever it flags. Goal: reviewer returns clean.

### OBJECTIVE-2 WORK QUEUE (Metal-exposed but NOT yet HW-exercised — close all before the obj-2 audit)
From the re-synced `capability-completeness.md` (39 NOT-YET; these ~10 clusters are the Metal-exposed blockers):
- ☑ **O2-A geometry-output pipeline** (EXP-O2A) [cmdstream]: multi-viewport/scissor (16), clip/cull distances (16),
  `[[point_size]]`, primitive restart, alpha-to-coverage/one, polygon-point fill.
- ☑ **O2-B sparse/PBE/filtering/sampler-heap** (EXP-O2B) [descriptor/tiling]: sparse/tile textures, PBE-renderable flags,
  32-bit float texture filtering, bindless sampler-heap (500k) layout.
- ☑ **O2-C RT completion tail** (EXP-O2C) [ISA]: `ray_data` payload, RT-from-render, motion blur, intersection tags,
  bbox/curve custom primitives, RT companion `0x5f`.
- ☑ **O2-D tile shaders + imageblock** (EXP-O2D; printf=long-tail) [ISA/cmdstream]: mid-render compute dispatch encoding.
- ☑ **O2-E ISA tail (atomics-order/bfloat/subgroup)** (EXP-O2D) [ISA]: atomic memory-ordering/fence bits + 64-bit atomic min/max width; bfloat general ALU;
  subgroup tail (`simd_shuffle_and_fill_up/down`, modulo, `simd_is_helper_thread`).
- ☑ **O2-F tensor ops** (EXP-O2C) [ISA]: MPP cooperative-tensor/convolution beyond matmul2d; matrix transpose/load variants;
  full `0xcf` operand-selector decode.
Honestly EXCLUDED from obj-2 (microarch/kernel; document, don't gate): Dynamic-Caching dynamics, flexible on-chip
memory, 2× ALU dual-issue, occupancy curve, RT reorder stage, compression codec; RT BVH build, sample positions,
ZLS, partial-render, scissor register, shader-entry bind.

### Phase R — RED-TEAM (adversarial verification; the user's explicit finishing directive)
Assume EVERY finding was produced by an unreliable agent. Big structure (families/opcodes) is likely right;
**subtle field/attribute errors are the target.** Fan out critical subagents that **RUN falsification tests**
(assemble/splice/observe, trace, probe) designed to BREAK each claim — not confirm it. **Record every test as
an experiment** (a passing test strengthens the finding). **Fix any issue found**, then re-test. Explicitly
include **large & unorthodox Metal programs and edge-case inputs** (huge shaders, deep control flow, high
register pressure/spill, exotic types, recursion, MRT, all texture dims, indirect/ICB, mesh, RT, dynamic libs).
- Rule: red-team subagents **do NOT edit `tools/agx-isa`/`docs`** — they report discrepancies with evidence;
  the orchestrator applies fixes centrally (keeps the DB coherent + round-trip green).
- Coverage checklist (every finding cluster must get an adversarial pass):
  ISA arithmetic/logic/convert/compare · control-flow/predication/loops/calls · memory/atomics/interlock/barrier ·
  textures/samplers/gather/PCF · subgroup/quad/matrix/RT · fragment interp/output/tilebuffer/ROG · machine model
  (96 GPR/uniform/spill) · SR/ABI/vertex-fetch · cmdstream compute+graphics+state+USC+indirect/occlusion/timestamp ·
  descriptors+format table · tiling/twiddle/compression/MSAA · TBDR pipeline · kernel-interface · capability matrix.
### COMPLETION CRITERIA (formal goal — mark complete only when all three hold)
1. **Implementable-from-docs:** a *separate* acceptance-reviewer subagent, given ONLY `docs/`, confirms it
   has enough to write a full GPU userspace from scratch (nothing else needed). [objective 1]
2. **All Metal-exposed HW exercised:** a *separate* capability-coverage auditor confirms every capability
   Metal exposes has been actually **provoked & tested on hardware** (`capability-completeness.md`
   NOT-YET-CHARACTERIZED for Metal-exposed features -> 0; kernel-managed/microarch honestly excluded). [objective 2]
3. **Overlapping verification, no holes:** every finding cluster checked by **multiple independent (overlapping)
   red-team subagents that RAN falsification tests** and found no issues; all discrepancies fixed & re-tested;
   round-trip green; byte0-census ~0 undecoded. [objective 3]

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

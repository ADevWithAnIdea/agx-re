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
- ☐ **0.5 IOKit/IOGPU data-tracing harness** (`tools/iotrace`) — DYLD interposer over the Metal↔kernel submission path (IOConnectCall* family + IOGPU shared-memory rings) in *our own* Metal process; capture a triangle draw and a compute dispatch.

## Phase 1 — Full A18 Pro AGX (dis)assembler + ISA spec  ⟵ PRIMARY TOOL DELIVERABLE
Build a **complete, hardware-validated, machine-readable AGX instruction database that both
disassembles AND assembles** A18 Pro shaders — the A18 counterpart to dougallj/applegpu. The
assembler is not optional: it is the engine of the extrapolate-and-test loop (to test whether
an instruction/modifier exists, we must be able to *encode* it, run it via the 0.4 testbed, and
observe). Correctness bar: **round-trip identity** — `disassemble(assemble(x)) == x` and
`assemble(disassemble(bytes)) == bytes` across the whole validated corpus.

- ◐ **Opcode map** — *started (EXP-0005):* instruction-length rule solved for float groups; float ALU 2-src op-select (fadd/fmul) HW-validated. Groups identified by byte0: `0x09` float-ALU, `0x0b` float-unary, `0x12` fmin/max, `0x67/e7` load/store, `0x9f` integer-ALU (unsolved), `0x0c` preamble, `0x0e` stop. Remaining: enumerate every group's ops.
- ◐ **Per-instruction spec** — *float ALU 2-src partially mapped (EXP-0005):* op-select field done; **next: operand/register fields, modifiers (neg/abs), packed float immediate.** Then integer ALU, memory addressing, control flow, textures, atomics, subgroup, RT/mesh.
- ☐ **Machine model** — register file (GPRs/16-bit halves), uniform regs, immediates, addressing modes, and **Dynamic-Caching** implications for a compiler backend.
- ☐ **New instruction families** — ray-tracing intrinsics, mesh shading, matrix/cooperative ops, subgroup/quad ops, atomics, texture/image ops; whatever Apple9 added.
- ☐ **Extrapolate & test** — sweep undocumented opcode/modifier space; log every probe (works/no-op/faults) in `hypotheses.md`.
- Deliverables: `../tools/agx-isa/` (the assembler+disassembler, round-trip-tested) **and** `isa/` (prose + encoding tables). The tool is the executable form of the documentation.

## Phase 2 — Control / command stream & state
- ☐ VDM (draw) / CDM (compute) / tiler / fragment command lists.
- ☐ USC binding words (shaders, textures, samplers, uniforms).
- ☐ State packets (depth/stencil, blend, raster, viewport, …).
- Method: black-box trace + change-one-Metal-parameter diffing. Deliverable: `cmdstream/`.

## Phase 3 — Resource descriptors & texture layout
- ☐ Texture / sampler / buffer descriptor bit layouts; bindless/argument-buffer model.
- ☐ Tiling/swizzle order + lossless compression per format.
- Deliverables: `descriptors/`, `tiling/`.

## Phase 4 — TBDR & compute specifics
- ☐ Tile size, imageblock/threadgroup memory, sample positions, partial render, memoryless targets, dispatch encoding — especially Dynamic-Caching-driven changes.
- Deliverable: `pipeline/`.

## Phase 5 — Synthesis & handoff, and the ACCEPTANCE GATE
- ☐ "Mesa A18 Pro userspace porting guide": per `src/asahi` module, what changes, with experiment citations.
- ☐ Completeness cross-check against Mesa's M1/M2 module list.
- ☐ **Acceptance gate (defines "done" — see `../CLAUDE.md` → Definition of Done):** a dedicated
  reviewer subagent, given ONLY `docs/`, must conclude it could implement A18 Pro Mesa userspace
  from scratch with **nothing else needed**. Run it early and often as a **gap-finder** to steer
  the work; the project is complete when it returns clean. Every gap it reports → new work item.

---

## Known premises (given, not to be re-questioned)
- **The A18 Pro AGX ISA is a completely new instruction set vs M1/M2 (G13/G14).** Opcodes are
  entirely different. Do not spend effort "measuring the delta" against applegpu — build the
  A18 instruction table from scratch by differential compilation + hardware validation.
- The GPU is designed for Metal (+ a narrow GL subset). Expect Vulkan/GL features that the HW
  lacks (→ must be emulated) and HW capabilities Metal never exposes (→ probe for them).

## Tooling backlog (needed to unblock coverage)
- **Extend `shdump`/`agxparse` to vertex & fragment stages.** It currently extracts only the
  `__compute` image. Fragment-only families — interpolation/pull-model, derivatives, barycentrics,
  programmable blending, raster-order-groups, imageblock writes, implicit-LOD sampling — plus
  mesh/object, cannot be characterized until we can extract non-compute shader code. High priority
  (blocks a large slice of Phase 1 + Phase 4). See `docs/isa/msl-feature-map.md` "requires non-compute stage".
- Persistent runner exists (`tools/agxtest/persistrun.py`); consider a render-pipeline variant for
  fragment probes (dispatch a draw, read back a render target).

## Open questions / risks
- **Modern submission path:** macOS 26 Metal likely submits via IOGPU shared-memory rings, not one `IOConnectCallMethod` per draw (unlike Alyssa's 2021 approach). 0.4 must confirm how to capture it. → the deciding risk for Phase 2.
- **Does A18 Pro differ from A17 Pro/M3 (both Apple9) at the encoding level?** Empirical — Phase 1/2 answer it.
- **AMFI/injection:** our own harness is unsigned → `DYLD_INSERT_LIBRARIES` should work without boot-args. Only tracing *Apple's own* processes would need `amfi_get_out_of_my_way`; deferred until/unless needed.

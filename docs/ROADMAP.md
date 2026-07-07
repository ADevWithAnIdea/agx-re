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

---

## Phase 0 — Foundations & clean-room tooling
Goal: prove every clean-room technique works end-to-end before doing real RE.

- ☐ **0.1 Environment recon** — chip/OS/toolchain/SIP/sudo/reboot path, GPU codename from device tree (`ioreg` `compatible`/`gpu-core-count` — hardware documentation, safe). *(partly done in bring-up: A18 Pro/T8140/macOS 26.6/CLT-only/SIP off/FileVault off confirmed.)*
- ☐ **0.2 Own-shader compile+extract tool** (`tools/shdump`) — MSL source → runtime `MTLLibrary` → `MTLBinaryArchive` serialize → parse the archive *with our own parser* → isolate the raw AGX machine-code bytes. (Confirmed: runtime compile works.)
- ☐ **0.3 (Dis)assembler bring-up** — fork the public **dougallj/applegpu** (+ Mesa `src/asahi/isa`) as the G13/G14 baseline; run it over an A18 shader corpus; measure decoded-vs-unknown to **size the ISA delta**. This becomes the seed of the Phase 1 tool.
- ☐ **0.4 Hardware testbed (the round-trip engine)** — assemble arbitrary AGX bytes → splice into *our own* metallib/pipeline → dispatch compute → read back results (ref: applegpu `hwtestbed/`, `metallib_replacer.py`, all public/MIT). This is what makes **assemble → run → observe** possible; without it there is no extrapolate-and-test.
- ☐ **0.5 IOKit/IOGPU data-tracing harness** (`tools/iotrace`) — DYLD interposer over the Metal↔kernel submission path (IOConnectCall* family + IOGPU shared-memory rings) in *our own* Metal process; capture a triangle draw and a compute dispatch.

## Phase 1 — Full A18 Pro AGX (dis)assembler + ISA spec  ⟵ PRIMARY TOOL DELIVERABLE
Build a **complete, hardware-validated, machine-readable AGX instruction database that both
disassembles AND assembles** A18 Pro shaders — the A18 counterpart to dougallj/applegpu. The
assembler is not optional: it is the engine of the extrapolate-and-test loop (to test whether
an instruction/modifier exists, we must be able to *encode* it, run it via the 0.4 testbed, and
observe). Correctness bar: **round-trip identity** — `disassemble(assemble(x)) == x` and
`assemble(disassemble(bytes)) == bytes` across the whole validated corpus.

- ☐ **Opcode map** — every instruction classified vs G13/G14: unchanged / changed-encoding / new / removed.
- ☐ **Per-instruction spec** — bit-field encoding, operands, free modifiers (sat/neg/abs, fp16↔fp32, etc.), and **semantics**, each **validated by hardware round-trip** on the 0.4 testbed.
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

## Phase 5 — Synthesis & handoff
- ☐ "Mesa A18 Pro userspace porting guide": per `src/asahi` module, what changes, with experiment citations.
- ☐ Completeness cross-check against Mesa's M1/M2 module list.

---

## Open questions / risks
- **Modern submission path:** macOS 26 Metal likely submits via IOGPU shared-memory rings, not one `IOConnectCallMethod` per draw (unlike Alyssa's 2021 approach). 0.4 must confirm how to capture it. → the deciding risk for Phase 2.
- **Does A18 Pro differ from A17 Pro/M3 (both Apple9) at the encoding level?** Empirical — Phase 1/2 answer it.
- **AMFI/injection:** our own harness is unsigned → `DYLD_INSERT_LIBRARIES` should work without boot-args. Only tracing *Apple's own* processes would need `amfi_get_out_of_my_way`; deferred until/unless needed.

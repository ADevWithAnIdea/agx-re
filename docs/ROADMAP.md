# A18 Pro GPU Userspace — Documentation Roadmap

Status board for the clean-room documentation effort. Read `../CLAUDE.md` first for the rules.

Target: **Apple A18 Pro, SoC T8140, macOS 26.6, Metal feature family Apple9, 5 GPU cores.**
Baseline for comparison: Mesa's existing M1 (Apple7 / G13) and M2 (Apple8 / G14) support in `../mesa/src/asahi`.

Legend: ☐ not started · ◐ in progress · ☑ documented & provenance-cited · ⚠ blocked

---

## Phase 0 — Foundations & clean-room tooling
Goal: prove every clean-room technique works end-to-end before doing real RE.

- ☐ **0.1 Environment recon** — chip/OS/toolchain/SIP/sudo/reboot path, GPU codename from device tree (`ioreg` `compatible`/`gpu-core-count` — hardware documentation, safe). *(partly done in bring-up: A18 Pro/T8140/macOS 26.6/CLT-only/SIP off/FileVault off confirmed.)*
- ☐ **0.2 Own-shader compile+extract tool** — MSL source → runtime `MTLLibrary` → `MTLBinaryArchive` serialize → parse the archive *with our own parser* → isolate the raw AGX machine-code bytes. (Confirmed: runtime compile works.)
- ☐ **0.3 Disassembler bring-up** — run dougallj/applegpu + Mesa's disasm on A18 shader bytes; measure decoded-vs-unknown to size the ISA delta.
- ☐ **0.4 IOKit/IOGPU tracing harness** — DYLD interposer over the Metal↔kernel submission path (IOConnectCall* family + IOGPU shared-memory rings) in *our own* Metal process; capture a triangle draw and a compute dispatch.
- ☐ **0.5 Hardware probe harness** — compute-shader test rig (known pattern in → read back) for tiling and instruction-behavior probing.

## Phase 1 — Shader ISA (largest target)
- ☐ Encoding delta vs G13/G14: opcodes unchanged / changed / new.
- ☐ Register file & Dynamic-Caching implications for a compiler backend.
- ☐ New instruction families: ray tracing, mesh shading, matrix/cooperative ops, texture/atomic changes.
- ☐ Validate each encoding by hardware round-trip (modify instruction → run → observe).
- Deliverable: `isa/`.

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

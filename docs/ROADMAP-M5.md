# M5 GPU Userspace — Documentation Roadmap

Status board for the clean-room documentation effort on the **Apple M5**. Read `../CLAUDE.md`
first for the rules. The A18 Pro roadmap (`ROADMAP.md`) and its `docs/`, `tools/agx-isa` DB, and
`EXP-M4-*`/`EXP-0xxx` experiments are the **prior phase** — valid for the A18 and used here as
**starting scaffolding**, never as M5 truth.

Target: **Apple M5, SoC T8142, macOS 27.0 (26A5368g), 8 GPU cores, Metal 4, SIMD width 32.**
GPU feature family (Apple9 vs Apple10) — **being probed (EXP-M5-04).** SIP **enabled** on this box.
Baseline for comparison: the A18 Pro (**G17P / Apple9**) DB, and Mesa's M1 (Apple7/G13) / M2 (Apple8/G14).

Legend: ☐ not started · ◐ in progress · ☑ documented & provenance-cited · ⚠ blocked

## The goal — three acceptance gates (mark complete only when ALL hold)

1. **OBJ-1 — driver-from-docs-alone.** `docs/` (M5 content) is sufficient to implement a full M5
   userspace GPU driver with no further probing. **Gate:** a dedicated reviewer subagent with an
   empty context, told to hunt for holes blocking a userspace implementation, finds nothing.
2. **OBJ-2 — full hardware capability coverage.** Every capability the GPU exposes (esp. everything
   Metal surfaces) is characterized. **Gate:** a dedicated empty-context subagent finds no missing
   hardware functionality we'd expect Metal to expose.
3. **OBJ-3 — not hallucinated.** Findings pass an adversarial review against the full 54 MB corpus
   of real Metal programs (round-trip + census with zero unexplained divergence).

## Guiding empirical result (EXP-M5-01)

The M5 is a **G17P-*derived* ISA with real deltas**, not a clean-sheet ISA: the unmodified A18
DB decodes `get_sr`(position_in_grid) exactly, then desyncs at `byte0=0x18` (first memory op).
So the plan is **delta characterization** — start from the 170-descriptor A18 DB, find every op
whose leader/length/fields moved on the M5, fix it, and re-validate on M5 hardware — not a rebuild.
Method is identical to the A18 loop: own-MSL provoke → extract → decode → **splice-and-observe on
the reboot-recoverable M5** → document with provenance → commit. New experiments are `EXP-M5-*`.

---

## Phase 0 — M5 bring-up & baseline  ☑ (EXP-M5-01)
- ☑ **0.1 Device + toolchain** — M5 at `192.168.170.253`, passwordless sudo, CLT (clang 21/python3),
  auto-login (unattended reboot recovery), `macvdmtool reboot` confirmed. → `CLAUDE.md` target table.
- ☑ **0.2 Own-shader compile→extract→disassemble runs on M5** — shdump/agxparse/agx-isa built &
  working; runtime MSL compile confirmed; SIMD32, maxThreadsPerTG 1024. → `experiments/EXP-M5-01`.
- ☑ **0.3 ISA baseline delta vs G17P** — A18 DB partial-decodes then desyncs; M5 = derived-with-deltas.

## Phase 1 — Full M5 AGX (dis)assembler + ISA spec  ◐
Build a complete, **HW-validated on M5**, machine-readable M5 instruction DB (fork/extend the A18
DB). Round-trip identity across the M5 corpus; splice-validate every changed encoding on M5 HW.
- ◐ **1.1 Corpus census (own)** — quantify A18-DB coverage on M5 bytes; ranked delta list. *In flight: EXP-M5-02.*
- ◐ **1.2 Corpus census (third-party 54 MB)** — build reusable M5 hex corpus; real-program coverage. *In flight: EXP-M5-03.*
- ☐ **1.3 Per-family delta characterization** — for each diverging byte0 leader: byte-diff + splice-and-
  observe on M5, fix leader/length/fields, provenance-cite. Families: memory load/store, ALU (float/int/half),
  control flow, textures, atomics/subgroup/quad, matrix, ray-tracing, mesh, fragment/varying, SR/ABI.
- ☐ **1.4 Machine model** — GPRs/uniforms/spill, Dynamic Caching, register width — re-confirm on M5.
- ☐ **1.5 Extrapolate & test** — sweep undocumented opcode/modifier space on M5; log in `hypotheses` (M5).
- ☐ **1.6 Census to convergence** — ~0 undecoded byte0 groups on both corpora; round-trip green.

## Phase 2 — Control / command stream & state  ☐
- ☐ VDM/CDM/tiler/fragment command lists, USC binding words, state packets — re-trace on M5 (iotrace),
  diff vs A18 cmdstream. Blend programmable? PPP header? tgmem/CDM config deltas?

## Phase 3 — Resource descriptors & texture layout  ☐
- ☐ Texture/sampler/buffer/PBE descriptor bit layouts; argument-buffer model; tiling/twiddle + compression
  per format — probe on M5, diff vs A18 descriptors/tiling.

## Phase 4 — TBDR & compute specifics  ☐
- ☐ Tile size, imageblock/tile-memory budget, MSAA sample positions, memoryless, dispatch encoding,
  tiler param buffer — re-measure on M5 (8 GPU cores vs A18's 5).

## Phase 5 — Capability census + synthesis + ACCEPTANCE GATES  ◐
- ◐ **5.1 Capability baseline** — MTLDevice probe: family, RT/mesh/argbuffers/limits. *In flight: EXP-M5-04.*
- ☐ **5.2 Capability census** — every Metal-exposed + Apple-advertised feature → native/emulated/kernel/NYC
  for M5. (OBJ-2)
- ☐ **5.3 M5 porting guide** — per Mesa `src/asahi` module, M5 deltas with experiment citations.
- ☐ **5.4 OBJ-1 gate** — empty-context reviewer finds no driver-blocking holes in `docs/` (M5).
- ☐ **5.5 OBJ-2 gate** — empty-context reviewer finds no missing Metal-exposed HW functionality.
- ☐ **5.6 OBJ-3 gate** — adversarial review vs the 54 MB corpus: no hallucinated/unverified findings.

---

## Experiment log & resume point
- **EXP-M5-01** ☑ bring-up + baseline delta (byte0=0x18 desync; get_sr transfers).
- **EXP-M5-02** ◐ own-corpus ISA census (fan-out wave 1).
- **EXP-M5-03** ◐ third-party corpus build + baseline census (fan-out wave 1; OBJ-3 corpus).
- **EXP-M5-04** ◐ MTLDevice capability + hardware baseline (fan-out wave 1; OBJ-2 foundation).
- **Next:** integrate wave-1 census → prioritized delta list → fan out Phase 1.3 per-family splice waves.

## Known premises (given, not to be re-questioned)
- Clean-room above all; only our own compiled shaders / committed permissive MSL; never introspect Apple binaries.
- The A18/G17P DB and docs are prior-phase scaffolding, not M5 fact — re-probe everything on M5 HW.
- Device is reboot-recoverable via `macvdmtool reboot`; faults on Apple GPUs are typically contained.

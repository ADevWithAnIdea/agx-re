# M5 GPU Userspace — Documentation Roadmap

Status board for the clean-room documentation effort on the **Apple M5**. Read `../CLAUDE.md`
first for the rules. The A18 Pro roadmap (`ROADMAP.md`) and its `docs/`, `tools/agx-isa` DB, and
`EXP-M4-*`/`EXP-0xxx` experiments are the **prior phase** — valid for the A18 and used here as
**starting scaffolding**, never as M5 truth.

Target: **Apple M5, SoC T8142, macOS 27.0 (26A5368g), 8 GPU cores, Metal 4, MSL 4.1, SIMD width 32.**
GPU: **`MTLGPUFamilyApple10` / arch `applegpu_g17g` / IOKit `AGXAcceleratorG17G`** (EXP-M5-04) — a
**G17-family sibling of the A18 (G17P / Apple9)**, hence ~84% ISA byte-overlap. SIP **enabled** on this box.
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
- ☑ **1.1 Corpus census (own)** — EXP-M5-02: 1085 stage programs, G17P DB = **76.8% named / 84.1% byte
  coverage**; root-cause delta list (first-desync): 0x18 memory-load (#1, 204 kernels), 0x41/0xc1 store,
  0x24, 0x3f, 0xa0, 0x07, 0x78/0x58/0x50 typed, 0x3e/0xbe short-ALU, 0xef/0xff call; length-rule deltas on
  multi-word ops. **Delta, not rebuild.**
- ☑ **1.2 Corpus census (third-party 54 MB)** — EXP-M5-03: 3095-program M5 corpus (OBJ-3 set); G17P DB
  80.6% named / 86.1% byte-cov; **143/149 desync leaders corroborate** the own corpus; family `_6` #1 in real code.
- ◐ **1.3 Delta characterization** — EXP-M5-05: leader+length deltas **FIXED** (fork `tools/agx-isa-m5`),
  tokenization **96.6% own / 98.0% tp** byte-cov, round-trip green, `instr_length` recursion-hang fixed.
  **Remaining = SEMANTICS of the M5-specific ops (splice-TODO, next wave):** memory `0x18`/`0x41`, typed/sample,
  the `0xNe` family, `0xb7`, call `0xef`/`0xff`, matrix/RT/mesh field maps.
- ☐ **1.4 Machine model** — GPRs/uniforms/spill, Dynamic Caching, register width — re-confirm on M5.
- ☐ **1.5 Extrapolate & test** — sweep undocumented opcode/modifier space on M5; log in `hypotheses` (M5).
- ◐ **1.6 Tokenization converged** — ≤3.5% desync both corpora (own 3.45% / tp 2.02%), round-trip green, 0 hangs.
  Residual tail + per-op semantics remain.

## Phase 2 — Control / command stream & state  ◐ (EXP-M5-06)
- ◐ EXP-M5-06: submission model **identical to A18** (49/58 IOKit calls, `AGXAcceleratorG17G`, shared-mem+doorbell);
  **DYLD injection works under SIP**. Deltas → `docs/cmdstream/README-M5-deltas.md`: compute config bit19 dropped;
  tgmem MOVED +0x40→+0x38 (new segmented encoding); draw opcodes +0x0800; viewport +0x9d0; FF-state 0x58000
  reorganized. **Open:** FF-pool per-bit enums, USC bind grammar, attachment/PBE, indirect/mesh/tess records.

## Phase 3 — Resource descriptors & texture layout  ◐ (EXP-M5-06)
- ◐ EXP-M5-06 → `docs/descriptors/README-M5-deltas.md`: texture width/height split shifted +1 bit; **sampler +
  buffer byte-identical to A18**. **Open:** PBE/storage-image, attachment packed-format, tiling/twiddle + compression.

## Phase 4 — TBDR & compute specifics  ☐
- ☐ Tile size, imageblock/tile-memory budget, MSAA sample positions, memoryless, dispatch encoding,
  tiler param buffer — re-measure on M5 (8 GPU cores vs A18's 5).

## Phase 5 — Capability census + synthesis + ACCEPTANCE GATES  ◐
- ☑ **5.1 Capability baseline** — EXP-M5-04: Apple10/G17g/T8142; RT+mesh+tensors+funcptrs+argbuf-Tier2; SIMD32,
  32KiB tgmem. → `experiments/EXP-M5-04-capabilities/m5-capability-matrix.md`.
- ◐ **5.2 Capability census** — EXP-M5-08: **164 rows** (65 native / 72 NYC / 15 emulated / 5 kernel / 7 microarch);
  **presence 100% enumerated, no Metal-exposed capability unaccounted for** (every gap = "encoding not yet mapped").
  Backlog (72 NYC = ~46 ISA field-semantics + ~26 cmdstream/descriptor records) directs the remaining waves.
  → `docs/capability-matrix-m5.md`, `docs/capability-completeness-m5.md`. (OBJ-2)
- ☐ **5.3 M5 porting guide** — per Mesa `src/asahi` module, M5 deltas with experiment citations.
- ☐ **5.4 OBJ-1 gate** — empty-context reviewer finds no driver-blocking holes in `docs/` (M5).
- ☐ **5.5 OBJ-2 gate** — empty-context reviewer finds no missing Metal-exposed HW functionality.
- ☐ **5.6 OBJ-3 gate** — adversarial review vs the 54 MB corpus: no hallucinated/unverified findings.

---

## Experiment log & resume point
- **EXP-M5-01** ☑ bring-up + baseline delta (byte0=0x18 desync; get_sr transfers); GPU dispatch+splice validated.
- **EXP-M5-02** ☑ own-corpus ISA census — 84.2% byte coverage; **0xNe column broken**, `n3_mov` length-delta = top lever.
- **EXP-M5-03** ☑ third-party 3095-program M5 corpus + census (OBJ-3 set); delta list corroborated (143/149 leaders).
- **EXP-M5-04** ☑ MTLDevice capability baseline — **M5 = Apple10 / G17g / T8142**, RT+mesh+tensors; OBJ-2 seed.
- **EXP-M5-05** ☑ ISA DB fork `tools/agx-isa-m5` — tokenization **96.6% own / 98.0% tp**, round-trip green, hang fixed.
- **EXP-M5-06** ☑ cmdstream + descriptor deltas vs A18 (DYLD works under SIP); → `docs/*/README-M5-deltas.md`.
- **EXP-M5-08** ☑ OBJ-2 capability census — 164 rows, presence 100% enumerated; backlog = 72 NYC (encoding-unmapped).
- **EXP-M5-07** ◐ ISA semantics splice (memory/typed/`0xNe`/`0xb7`/call) — *agent running*; closes ~46 of the NYC backlog.
- **Next (resume point):** (1) **splice-and-observe semantics** for the M5-specific ISA ops (device now SIP-off,
  fault-recoverable) — memory/typed/`0xNe`/`0xb7`/call/matrix/RT/mesh; (2) render M5 DB into `docs/isa/` for OBJ-1;
  (3) close cmdstream/descriptor open items (FF-pool enums, PBE, tiling); (4) OBJ-2 capability census; then the
  three acceptance gates. Timeouts on all device probes (see global memory).

## Known premises (given, not to be re-questioned)
- Clean-room above all; only our own compiled shaders / committed permissive MSL; never introspect Apple binaries.
- The A18/G17P DB and docs are prior-phase scaffolding, not M5 fact — re-probe everything on M5 HW.
- Device is reboot-recoverable via `macvdmtool reboot`; faults on Apple GPUs are typically contained.

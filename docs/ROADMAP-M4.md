# M4 validation roadmap (repeat the A18 RE on the local Mac Mini M4)

**Goal (formal):** Validate the A18 Pro findings against the local **Apple M4** and document the
differences, to the same bar as the A18 work: (1) enough clean-room docs to implement a full M4
GPU userspace from `docs/` alone, (2) full hardware-capability coverage, (3) findings verified.
Deliverable = `docs/m4-deltas.md` (delta layer over the A18 docs) + `experiments/EXP-M4-*/`.

**Strategy:** M4 ≈ A18 (both Apple9). So this is **validate-and-delta**, not from-scratch: run
each A18 finding's experiment on the local M4, mark IDENTICAL or DELTA. Everything runs LOCALLY
(this host is the M4; compile/extract/splice/iotrace locally — no SSH).

## Phases
- **M0 setup + ISA census** — ✅ EXP-M4-01: M4 = same ISA (88.6%/91.5%, 57/57 compile). 10 cores vs 5.
- **MA ISA completeness** — 🔄 close the ~28 undecoded byte0 groups (length-cascade analysis) → ~0 on M4+A18 corpus. (subagent running)
- **MB ISA semantics + machine model** — ⏳ splice-run on M4: confirm arithmetic/CF/memory/atomic semantics + 96-GPR/SR/uniform model; byte-diff M4-vs-A18 for identical MSL (find any encoding delta).
- **MC command stream** — ⏳ iotrace on M4: CDM/VDM/USC/state/indirect/occlusion/timestamp/mesh/tessellation vs A18.
- **MD descriptors + tiling** — ⏳ probe on M4: descriptor bit layouts + tiling (cols/T/14-bit/padding) + compression vs A18.
- **ME pipeline/TBDR** — ⏳ iotrace on M4: tile size/imageblock/MSAA/sample-positions/memoryless vs A18 (watch 10-core effects).
- **MF capabilities** — ⏳ Metal feature-set + MSL probe on M4 vs A18 (tessellation/mesh/RT/matrix/atomics/Metal-4 additions).
- **MG kernel interface** — ⏳ submit/BO/VM + config (core count) the userspace must know.
- **MH docs consolidation** — ⏳ finalize `docs/m4-deltas.md`.
- **MI red-team + acceptance** — ⏳ overlapping verification of each delta + a docs-only acceptance review (implementable-from-[A18 docs + m4-deltas]).

## Delta tracker
See the running table at the bottom of `docs/m4-deltas.md`.

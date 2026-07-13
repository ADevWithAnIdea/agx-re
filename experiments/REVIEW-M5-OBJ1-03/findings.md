# REVIEW-M5-OBJ1-03 — Adversarial OBJ-1 acceptance review (M5 / Apple10 / G17g)

Empty-context reviewer, `docs/` + `tools/agx-isa-m5/db.json` (188 desc). Run 3.
**VERDICT: FAIL — 1 BLOCKER · 3 MAJOR · 6 MINOR** (was 1/8/6 in run 02). Strongly positive trajectory.

## Texture path re-assessment (the run-3 mandate)
**PARTIALLY emittable — tokenizable/identifiable, NOT emittable.** EXP-M5-16 added `m5_tex`/`m5_tex_read` leaders
(identify sample/gather/lod/read via byte+1 op + byte+2 0x12/0x1a), `m5_store_texresult`, and confirmed
`tex_write`(0xd7) image-store **fully works on M5**. But sample/read still can't be EMITTED: coordinate register,
texture-slot, sampler-slot, LOD/bias/grad operand, and per-variant length are all raw/OPEN; the A18 `tex_sample`
fallback is superseded. Internal contradiction flagged: README-M5 said "emittable" vs porting-guide §8 "blocks
textured shaders" — README overstated (fixed in EXP-M5-17 doc pass).

## BLOCKER (1)
- **B-1 — M5 texture sample/read OPERAND encoding open.** Blocks NIR→AGX for every textured/sampling shader.
  Missing: coordinate reg, texture-slot + sampler-slot selection, LOD/bias/grad operand, per-variant length —
  only the identifying leader + result-store are emittable; A18 `tex_sample` fallback superseded (non-functional).
  **Path:** agxrender coord/slot splice → typed `db.json` fields. (`tex_write` image-store already works.) → EXP-M5-17.

## MAJOR (3) — all gate-able extensions / inherited-with-documented-value, NOT core blockers (per reviewer)
- **M-1** GPR/register-file machine model not re-confirmed on M5 (ships with A18 value 96 GPRs + occupancy-tier bit; RA correctness/perf risk).
- **M-2** Out-of-line/indirect function-call ABI (`0xef`/`0xff`, VFT) open (intra-shader control flow fully specified; inlined shaders fine; gates function-pointers/dylibs/RT-IFT).
- **M-3** Coop-matrix 8×8 operand packing + RT acceleration-structure load open (both gate VK extensions).

## MINOR (6)
m-1 split-memory data-reg positional (mitigated: 0x67/0xe7 fallback retained+executes); m-2 intra-tile Morton not re-verified (A18-inherited, padding reproduces); m-3 VS→FS varying reorder not re-run; m-4 PBE W/H bit-solve inherited; m-5 mesh amplification/ICB not probed; m-6 doc hygiene: superseded-set count loose (~5 not 8; tex_write retained-not-superseded) + README/porting contradiction — **fixed in EXP-M5-17 doc pass.**

## What's solid (would pass on its own)
Submission/kernel interface; CDM/VDM; FF-state bit-identical enums (8 compares + 8 stencil-ops + cull/wind/clip
HW-validated); programmable blend; write-mask/occlusion/PPP+layer; descriptors; tiling+compression (byte-for-byte);
TBDR (tile 32×32, MSAA, sample positions, memoryless); full scalar/vector ISA — float/half/bfloat/int64 ALU, SFU,
logic, conversions, control flow, subgroup/quad reduce+scan+shuffle+ballot, split-memory load/store, uniform +
**divergent-address atomics**, `tex_write` image-store, fragment stage, native tessellation + minimal mesh.

## Top fixes to PASS
1. **Close B-1:** map M5 texture operand encoding (coord reg, tex-slot, samp-slot, LOD, per-variant length) as
   typed `db.json` fields — the ONLY remaining core-path blocker (EXP-M5-17, running).
2. Reconcile README-M5 "emittable" vs porting-guide §8; crisp do-not-emit set (done, EXP-M5-17 doc pass).
3. (Extension-gated) call ABI, coop-matrix operands, RT AS-load; re-confirm M5 GPR model.

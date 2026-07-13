# REVIEW-M5-OBJ1-04 — Adversarial OBJ-1 acceptance review (M5 / Apple10 / G17g)

Empty-context reviewer, `docs/` + `tools/agx-isa-m5/db.json` (189 desc). Run 4.
**VERDICT: PASS — 0 BLOCKER · 3 MAJOR · 6 MINOR.**

## Texture (run-03 blocker) — CLOSED and independently re-verified
An author can place coordinate + texture-slot + sampler-slot + LOD and emit a working `sample`/`read` from the
sanctioned sources. `m5_tex` (0x12 compute / 0x16 fragment) + `m5_tex_read` (0x1a) + `m5_store_texresult`: coord
reg = byte+3 (splice RED→BLUE), sampler slot = byte+5[6:0] (BLUE→RED), texture slot = byte+6 (RED→GREEN), LOD =
byte+12 (mip 0→1); lengths sample 22 / gather 14 / read 8. Upstream `iter` + downstream `frag_color_store` both
decoded + HW-exercised. **Textured fragment shader emittable end-to-end.**

## What's solid
Compute + graphics submission; `0x58000` FF-state per-bit (bit-identical enums, all compares/stencil-ops
validated); programmable blend; split-memory + subgroup + texture + divergent atomics + matrix leaders;
descriptors (tex/samp/buffer/PBE); tiling/compression byte-for-byte; TBDR 32×32/MSAA/sample-positions/occlusion;
kernel interface identical. Round-trip green over 842 own + 3095 tp, 0 hangs.

## MAJOR (3) — doc-hygiene, no hardware fact withheld (each has an in-docs fallback)
- **M-1** `encoding-tables-m5.md`: 107/188 `###` headings render match-line-only (no field table) — incl. every
  M5-new op (`m5_tex`/`m5_reduce`/`m5_alu`/`m5_atomic_*`/`m5_matrix_mac`/…). `db.json` carries full fields+semantics,
  so not a blocker; a `gen_encoding_tables.py` "Other"-section bug. **FIX: render fields for all ops.**
- **M-2** `porting-guide-m5.md` §8 STALE — still says texture "blocks textured fragment shaders" + points to an
  out-of-`docs/` fallback, contradicting README-M5 + db.json (EXP-M5-17 closed it). **FIX: state texture emittable.**
- **M-3** split-memory LOAD dest / STORE data register not fully bit-decoded (positional). **Fallback (in docs):**
  the monolithic `0x67`/`0xe7` `device_load`/`device_store` still occur on M5 and are fully decoded in the A18 base
  `encoding-tables.md` (dst byte+8/+9 → r0..r511) — a driver emits fully register-controlled loads/stores with the
  monolithic form, treating the split model as an optimization. → MAJOR, not blocker.

## MINOR (6)
m-1 descriptor-count drift (README "180" / porting "170" / roadmap "188" vs db.json 189 — reconcile); m-2 `m5_tex`
slot/LOD operands are in `semantics` prose not typed `fields` (byte+5/+6/+12 lie outside the 6-byte leader — typing
them would lengthen the descriptor + risk census regression; documented tradeoff); m-3 `m5_tex` byte+4 bank raw for
dense slot≥2; m-4 inherited ops (0x67/0xe7, iter, frag_color_store) corroborated via corpus+renders, not re-spliced;
m-5 M5 GPR machine model inherited from A18, not re-measured (allocator tuning, not encodability); m-6
documented-open extension features (Morton byte order, matrix 8×8 packing, RT AS-load, call ABI) — gate-able with fallbacks.

## Bottom line
No remaining gap blocks a core path without a working in-`docs/` fallback. The 3 MAJORs are doc-hygiene defects to
fix (done in the follow-up commit); they withhold no hardware fact. **PASS, 0 blockers.**

## Gate status: OBJ-1 PASS · OBJ-2 PASS (REVIEW-03) · OBJ-3 PASS (REVIEW-01) — ALL THREE ACCEPTANCE GATES MET.

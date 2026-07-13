# REVIEW-M5-OBJ1-02 — Adversarial OBJ-1 acceptance re-review (M5 / Apple10 / G17g)

Empty-context reviewer, `docs/` + `tools/agx-isa-m5/db.json` (180 desc). Run 2.
**VERDICT: FAIL — 1 BLOCKER · 8 MAJOR · 6 MINOR** (down from 3/6/5). Big improvement.

## Prior blockers
- **B-2 split-memory addressing — RESOLVED** (m5_addr_gen/load/store field maps HW-validated EXP-M5-07/11).
- **B-3 contradictory memory models + stale length appendix — RESOLVED** (0x18 disambiguated; 0x67/0xe7 ⇄ split coexistence documented with census counts).
- **B-1 M5-specific ops absent — PARTIAL:** memory + subgroup/quad reduce/scan (`m5_reduce`) + shuffle (`m5_shuffle`) + compute ALU (`m5_alu`/`m5_iadd`) integrated + HW-validated. **Texture/matrix-MAC/call/RT AS-load NOT integrated** → texture is core → surviving BLOCKER; rest MAJOR.

## BLOCKER
- **B-1. M5 texture sample/gather/read/compare/LOD not emittable.** Blocks NIR→AGX for every textured
  fragment/sampling-compute shader. `encoding-tables-m5.md` shows A18 `tex_sample`(0x5) but the M5 appendix
  says the M5 sample leader is byte0 `{0x0f,0x1f}` + byte+2 `0x12`(sample)/`0x1a`(read) with the **length rule
  left OPEN** (measured per-op lengths net-regressed the census, EXP-M5-09, reverted); `db.json` has **no M5
  texture descriptor**. Three conflicting answers, no shippable fallback. → integrate the M5 texture family.

## MAJOR
- **M-1** texture WRITE (`tex_write` 0xd7) unverified on M5 (imageStore).
- **M-2** divergent-address device atomics not emittable — A18 per-lane path (0x67 byte+1 0x11/0x01) "GONE on
  M5"; only *uniform-address* atomics migrated to `m5_reduce`. `atomic_fetch_add(&buf[gid],x)` has no M5 encoding.
- **M-3** `simdgroup_matrix` MAC `2f 00 05` not in db.json (blocks coop-matrix).
- **M-4** call ABI `0xef`/`0xff` open (blocks VFT/dynamic-libs/RT-IFT/recursion; intra-shader control flow is green).
- **M-5** RT AS-load / ray-data open (migrated off 0xdf; blocks BVH traversal).
- **M-6** mesh vertex-amplification / payload / full ICB not probed (minimal mesh + tessellation done).
- **M-7** `capability-matrix-m5.md` STALE — §3 memory/§4 atomics/§6 subgroup/§15 spill marked NYC but the DB
  integrated them HW-validated (EXP-M5-07/09/11). Reconcile.
- **M-8** retained A18 descriptors (`tex_sample`0x5, `tex_write`0xd7, `matrix_mac`0xcf, `call`/`call_indirect`,
  `rt_as_load`0xdf, `rt_ray_mem`0x5f, `atomic_rmw/mem`0x67) appear in the M5 table with no "superseded-on-M5" caveat.

## MINOR
m-1 m5_alu/m5_iadd operand packing byte-diff (not splice-proven); m-2 GPR machine model not re-confirmed on M5;
m-3 intra-tile Morton byte order; m-4 USC buffer slots >2 + varying-reorder; m-5 some PPP output-select bits
inherited; m-6 tex_deriv/imageblock/tile_read A18-provenance (green, not M5-splice-confirmed).

## What's solid
Submission/kernel-interface; cmdstream (FF-pool bit-identical + programmable blend + PPP/layered + USC grammar +
mesh record + native tessellation + indirect, EXP-M5-06/10/13); descriptors; tiling/compression; TBDR (tile
32×32, MSAA, sample positions, memoryless); scalar/vector ISA + this cycle's split-memory + subgroup + compute-ALU.

## Top fixes to PASS
1. **Integrate the M5 texture family** (`0x0f/0x1f`+`0x12/0x1a`, per-variant lengths, coord/operand maps) → closes the BLOCKER; validate `tex_write`.
2. Map divergent-address atomics; integrate `2f 00 05` matrix MAC, call ABI, RT AS-load.
3. Reconcile `capability-matrix-m5.md` rows vs the DB (M-7) + add "superseded-on-M5" caveats (M-8).
4. Mesh amplification/ICB; splice-confirm m5_alu operand packing; re-confirm M5 GPR model.

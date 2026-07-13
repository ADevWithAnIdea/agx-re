# REVIEW-M5-OBJ1-01 — Adversarial OBJ-1 acceptance review (M5 / Apple10 / G17g, driver-from-docs-alone)

Empty-context adversarial reviewer, `docs/`-only (+ `tools/agx-isa-m5/db.json`). Run 1 (interim gap-finder).

## VERDICT: **FAIL** — 3 BLOCKER · 6 MAJOR · 5 MINOR

Cmdstream / descriptor / tiling / TBDR are solid (A18 bases complete; M5 deltas measured on HW, EXP-M5-06/10).
The failure is concentrated in the **shader ISA**: the M5 delta docs describe *in prose* that memory / atomics /
texture / matrix / subgroup / call families changed on M5, but the emittable table (`db.json` +
`encoding-tables-m5.md`) **still contains the A18 encodings** for those ops — the EXP-M5-09 M5 forms were never
integrated. A compiler back-end cannot be built from this.

### Decisive evidence
- `db.json`: 176 descriptors, **only 7 carry M5 provenance**; 167 cite only A18 experiments.
- README-M5 says M5: matrix MAC → `2f 00 05` (simdgroup emits zero `0xcf`); atomics/subgroup → `2f 00 <scope>…`;
  shuffle → `2f 00 21`; texture → low-nibble-`0xf` + byte+2 `0x12`/`0x1a`; calls → `0xef`/`0xff`. **None exist in `db.json`.**

## BLOCKERS
1. **M5-specific ISA ops absent from the emittable table (A18 encodings mislabeled M5).** Blocks emitting atomics,
   texture sampling, cooperative-matrix/tensor MAC, SIMD reduce/scan/shuffle, function calls. → integrate the
   EXP-M5-09 deferred encodings into `db.json`/`encoding-tables-m5.md`.
2. **Split memory model under-specified for general addressing/stores.** `m5_addr_gen` documents only
   dst/`base_slot`/`idx_mode` — no arbitrary index-GPR or immediate-offset field (`a[computed]`/`a[i+k]` unemittable);
   `m5_store` data-source register is "implicit." → finish the field maps.
3. **Two contradictory memory/store models + stale length appendix.** Table keeps both `device_load`(0x67)/
   `device_store`(0xe7) and `m5_load`(0x18)/`m5_store`(0x41/0x61) with no disambiguation rule; length appendix lists
   `0x18`=`half_pack` 4B colliding with `m5_load` 10B. → reconcile + fix appendix.

## MAJOR
4. Function-call / function-pointer ABI unmapped on M5 (`0xef`/`0xff`). Blocks calls / VFT / dynamic libs / recursion / IFT.
5. RT acceleration-structure-load encoding OPEN on M5 (migrated off 0xdf into the memory family). Blocks BVH traversal.
6. Mesh grid-dispatch cmdstream record OPEN (pipeline-create aborted; vertex-amplification/ICB not probed).
7. USC *graphics* bind grammar + uniform-preamble not re-derived on M5 (only Tier-2 arg-buffer table confirmed).
8. **Stale `capability-matrix-m5.md`** — says FF fields "not located" but EXP-M5-10 (later) resolved depth/stencil/
   raster + line-fill. Reconcile. Residual genuine-open: FF `+0x194` write-mask per-channel packing; PPP output-select word.
9. CDM config constants `+0x04/+0x0c/+0x28` undecoded (borders minor).

## MINOR
10. Intra-tile Morton byte order not byte-verified on M5. 11. Length-rule appendix inconsistency (see B-3).
12. PBE width/height bit-solve + sparse/heap + `texture_buffer<T>` inherited, not re-solved on M5. 13. Depth/ZLS +
partial-render fields A18-derived, assumed to transfer. 14. `rt_intersect` "transfers unchanged" but DB descriptor is A18-provenance.

## What's solid
Submission/kernel interface; command stream (VDM/CDM/viewport/FF-pool depth-stencil-raster measured on M5, programmable
blend, occlusion, native tessellation); descriptors (complete self-contained bit tables + valid M5 delta); tiling/
compression (swept on M5); TBDR/pipeline (tile 32×32, MSAA, sample positions, memoryless); scalar ALU/control-flow ISA.

## Top fixes to reach PASS
1. Integrate the M5 ISA-semantics wave (`2f`-matrix/atomics/subgroup, `0xf`-texture, `0xef`/`0xff` call, memory-family
   RT AS-load) into `db.json` with M5 splice provenance. 2. Finish `m5_addr_gen`/`m5_load`/`m5_store` field maps +
   reconcile with retained 0x67/0xe7 + the length appendix. 3. Close mesh grid-dispatch record + USC-graphics grammar.
   4. Reconcile stale `capability-matrix-m5.md` against EXP-M5-10.

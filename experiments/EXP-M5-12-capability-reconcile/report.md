# EXP-M5-12 — M5 OBJ-2 capability-doc reconcile (close REVIEW-M5-OBJ2-01 gaps)

**Goal.** Close the OBJ-2 gaps in `REVIEW-M5-OBJ2-01/findings.md` (1 BLOCKER · 4 MAJOR · 5 MINOR) plus OBJ-1
review gap #8 (stale `capability-matrix-m5.md` rows). Mostly enumeration + reconciliation against EXP-M5-10
and the A18 base census, with own-MSL presence probes.

**Method (clean-room).** `docs/` + A18 base as model; presence via compile-only own-MSL (`newLibraryWithSource:`,
no GPU dispatch) on M5; EXP-M5-10's own-process data-trace already in `docs/*/README-M5-deltas.md`. No Apple
binary introspected.

## Presence probe (M5, own-MSL compile-only — `raw/msl_acceptance_m512.txt`)
Apple M5 / T8142 / macOS 27.0, 8 cores. **ACCEPT:** `render_target_array_index`(vs), `viewport_array_index`,
both-together, `depth(any/greater/less)`×3, `early_fragment_tests`, `sample_mask` out, `sample_mask` in
(coverage), `sample_id`+mask, barycentric. **REJECT:** `early_fragment_tests` + `depth` together — an honest
MSL mutual-exclusion rule, **not** an absence (documented as such).

## Gaps closed
- **B-1** layered rendering `[[render_target_array_index]]` — §10 native (mechanism = PPP output-select bit ∥
  `viewport_array_index`; exact M5 bit = the still-open PPP output-select word, EXP-M5-13).
- **M-1** fragment depth output + `[[early_fragment_tests]]` — §11 native (FS-epilog Z-store; depth-emit rides the `0xe7` store delta).
- **M-2** `[[sample_mask]]` output + input coverage — §11 native (output = FS-epilog write, input = `get_sr`).
- **M-3** RT custom-AABB + curve primitives — restored §8 native; + RT companion ops `rt_transform_test`/`ray_move` (NYC).
- **M-4** int8/int coopmat split — `simdgroup_matrix<int/char>` = emulated (REJECT confirmed) vs int8-via-`MTLTensor`
  neural path = NYC (same bucket as fp16/bf16 tensor).
- **MINORs** — `MTLResidencySet` (kernel), `MTLIOCommandQueue` (out-of-scope/kernel), indirect **draw** `0x6c04`/`0x6c32`
  (native, M5-measured), conservative rasterization + pipeline-statistics queries (emulated, Metal-unexposed).

## OBJ-1 gap #8 reconciliation vs EXP-M5-10 — 13 stale rows NYC→native/M5-measured
§10 depth/stencil compare+ops, depth clamp/clip, polygon line-fill, depth-bias, write-mask, alpha-cov/one; §9
tessellation (native HW VDM patch-dispatch); §12 tile size (32×32/8-core), memoryless, load/store, MSAA (1/2/4×;
**8× rejected — corrected the old "cap at 8×"**), sample positions, occlusion; §13 indirect dispatch + draw. Each
cites `cmdstream/` or `pipeline/README-M5-deltas.md`.

## Updated tallies (row-level, grep-verified)
Prev: native 65 · NYC 72 · emulated 15 · kernel 5 · microarch 7 = 164.
**New: native 84 · NYC 61 · emulated 13 · kernel 7 · microarch-NYC 5 = 170 rows** (11 new + 13 moved NYC→native).
Residual ~61 NYC now dominated by the ISA-semantics splice/integration wave (EXP-M5-11); marquee = Apple10 Neural
Accelerator / `MTLTensor` path (where int8 matmul lands).

## OBJ-2 gate impact
Reviewer FAIL (absent layered rendering + 3 unenumerated graphics caps + 1 over-strong mis-classification)
resolved; stale FF/TBDR/draw rows reconciled to measured M5 values. **No Metal-exposed capability unaccounted-for
or mis-classified.**

## Clean-room attestation
Presence facts = public runtime compiler ACCEPT/REJECT of our own MSL (compile-only, no dispatch), device flags
returned to our own program, or bytes our own process observed at the IOKit boundary (EXP-M5-10). Classifications
measured on M5 or inherited from cited A18 `docs/`. No Apple binary disassembled/decompiled/introspected.

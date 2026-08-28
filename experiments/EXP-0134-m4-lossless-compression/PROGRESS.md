# PROGRESS — EXP-0134-m4-lossless-compression

Timestamped milestone log per SUBAGENT_BRIEF.md (so a kill/wedge costs at most one
milestone; re-orient from this file + the frozen contract + `raw/` on resume, never
from memory).

## M1 — 2026-08-28 — pipeline bring-up
- Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md, APPLE9_RE_IMPLEMENTATION_GAPS.md
  §DRV-P2-01, EXP-0017-tiling/RESULTS.md, docs/tiling/README.md §4 (current model:
  aux = numTexels/32, eligibility = no-ShaderWrite ∧ W≥16∧H≥16, MSAA ratio unpinned,
  codec itself open).
- Built `tools/iotrace/iotrace.c` UNMODIFIED into `work/iotrace.dylib` (read-only
  per brief; only the build artifact lives in `work/`).
- Wrote `harness/cprobe.m` (ObjC probe binary: create texture, write a known
  pattern via the RENDER path only — compute image-store/ShaderWrite is never used
  for a compression-candidate texture, since ShaderWrite itself disables
  compression — optional CPU-visible op (replaceRegion/getBytes/blit), bind into a
  tiny read kernel so the sampled descriptor lands in a Tier-2 arg-buffer BO,
  SIGUSR1-dump). Builds clean; smoke-tested standalone (no dump) — OK.
- Wrote `harness/auxdecode.py` (host-side descriptor+aux decoder, generalizing
  EXP-0017's `twiddle.py` / EXP-M4-07's `solve3d.py` find-descriptor technique to
  8 words + secondary VA + measured aux extent). Verified against a real dump: a
  32×32 rgba8unorm ShaderRead texture decoded compression_flag=1, aux_layout=1,
  secondary_va=base+0x4000 — correct shape, but aux BYTE COUNT measurement (BO
  size − offset) was bogus (109312) — see M2.

## M2 — 2026-08-28 — shared-heap suballocation discovery (method fix)
- Root cause: **compression-eligible textures whose padded main image is below
  ~0x4000 (16KiB) bytes are suballocated from a SHARED heap BO** alongside other
  small objects, so "whole-BO-size minus aux-offset" measures into unrelated
  neighboring content. Textures whose main image is ≥0x4000 get a **dedicated BO**
  (`main_bo_gpu_va == base_va`, size == main+aux exactly) — confirmed clean at
  64×64/128×128/256×256 rgba8unorm (aux 128/512/2048, exact numTexels/32 match).
- Fix: added a `"replicate"` cprobe kind — allocate N identical small (shared-heap)
  textures in one process, bind+read each, dump once, and take **consecutive
  base_va deltas** as a direct per-object footprint measurement (works regardless
  of heap sharing). Validated: 16×16 rgba8unorm ×10 → delta 0x500 (1280B) exactly
  = round_up(main(1024)+aux(8), 256); 20×20 rgba8unorm and 16×16 r8unorm cross-
  checked the same 256-byte suballocator-granule model. This becomes the
  `aux_alloc_floor` family (finite-resource mandate) and the `aux_bpp_size` /
  `aux_msaa_ratio` families were re-sized per-bpp so their main image always
  clears the dedicated-BO threshold (`casematrix._dedicated_bo_size_pow2`).
- Also validated during this pass (informal, pre-freeze): gradient→aux 0x15
  uniform; noise→aux 0x7f uniform; all-zero clear→aux 0x03 uniform (a THIRD,
  distinct code from gradient); a single-outlier block (uniform gray + one
  perturbed texel) → 0x21 for that one block, 0x03 elsewhere (a FOURTH distinct
  code) — strong early evidence the codec has more than the two "compressed
  vs. raw" states already documented. MSAA: N=1/2/4 aux bytes at fixed W×H scaled
  exactly ×1/×2/×4 (128/256/512) — pins the previously-unresolved MSAA aux ratio
  as `numTexels·N/32`. `getBytes` on a compressed rgba8unorm gradient texture
  returned the correct DECODED texel (Metal transparently decompresses for CPU
  readback).

## M3 — 2026-08-28 — anomaly: minimum aux-allocation floor at bpp16
- `aux_bpp_size` case rgba32float 32×32 (bpp16, T=32, exactly one tile, main=16384
  — a DEDICATED BO, not shared-heap): formula predicts aux=numTexels/32=32B,
  measured **128B**. A second, non-square adversarial case (rgba32float 32×64,
  formula predicts 64B) also measured **128B** — rules out "always ×4 the
  formula" and supports a **hard ~128-byte minimum aux-allocation floor**
  independent of the shortfall amount. Added both as frozen matrix cases
  (`a_bpp_rgba32float_32`, `a_bpp_rgba32float_32x64`) rather than discarding the
  finding; `run.py`'s verdict is left strictly formula-based (these two cases are
  expected to show `FAIL` in the gated record — the mismatch IS the finding,
  documented in RESULTS.md, not a harness defect).

## M4 — 2026-08-28 — matrix frozen, gates green
- `harness/casematrix.py` frozen at 83 cases across `elig`(31)/`aux`(27)/
  `state`(16)/`cpu`(9). `harness/schema.py`, `harness/run.py`, `harness/verify.py`
  written. `fixtures/recorded_reality.json` generated from 5 REAL `run_case()`
  captures (gate (e)). `verify.py --selftest` and `--seqtest`: PASS.
- Every probe texture in the frozen matrix carries `MTLTextureUsageShaderRead`
  (PRE_REGISTRATION.md scope note): this lets every case use the one established
  bind-and-read descriptor-capture method uniformly; RT-only/write-only-without-
  ShaderRead resource classes are explicitly out of scope (a driver resource that
  is never sampled by any shader is not a realistic case, and Apple's own
  render-target-attachment path uses a structurally different descriptor per
  `docs/descriptors/README.md`, which this experiment does not attempt to reach).
- Next: `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` freeze, then the two
  official capture runs (`m4_20260828_run01`, `m4_20260828_run02`).

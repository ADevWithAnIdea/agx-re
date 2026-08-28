# EXP-0138 progress log (append-only, one entry per milestone)

## 2026-08-28 — Milestone 0: setup
- Created `experiments/EXP-0138-m4-emit-falu/`. Repo revision at pre-registration:
  `f17938ee0105c8f1fb1e1c25be3aa22fa4a77a5c` (dirty: sibling agents' untracked
  EXP-0133/0139/0140/0141 dirs only; no tracked file modified by this experiment).
- Built `work/bin/{shdump,agxrun,agxrun_persist}` from the UNMODIFIED
  `tools/shdump/shdump.m`, `tools/agxtest/agxrun.m`, `tools/agxtest/agxrun_persist.m`
  (`harness/build.sh`). Host: Apple M4 (G16G), macOS 26.6.2 (25G82).

## 2026-08-28 — Milestone 1: pilot (NON-GATED, `work/pilot/`)
Purpose: obtain a known-good, compiler-emitted ANCHOR encoding for every family
before any sweep, and prove both execution modes work. Nothing here is promoted;
every gated claim is re-derived in `raw/`.

1. **Anchor compiles** (`work/pilot/anchors{,2,3,4}.metal`, OUR OWN MSL, 42 kernels):
   byte-exact anchors obtained for `falu2`, `falu2i`, `falu2_ext`,
   `falu2_srcmod10`, `falu3`, `falu3_ext`, `falu3_srcmod12`, `falu_acc`,
   `copysign`, `half_alu`, `half_alu_ext8`, `half_alu_fma12`, `fspecial`,
   `fspecial_est`. **No compiler-emitted anchor was found for `falu_srcmod12b`,
   `falu2_ext8b` or `falu2_uni`** across 42 authored kernels (round 4 hunted them
   specifically). `falu_srcmod12b` is therefore CONSTRUCTED by family analogy;
   `falu2_ext8b` and `falu2_uni` have no carrier.
2. **MODE A works** (`work/pilot/smoke2.py`): a fully hand-built program spliced
   over the whole `_agc.main` of `kernels/carrier.metal` (region 1218 B) seeds
   r0..r12 with 13 distinct exact minifloat constants via `falu2i` and reads them
   all back exactly (5.0,1.5,3.0,0.5,7.0,9.0,11.0,13.0 at word slots 0..28).
   **Pilot bug 1 (found and fixed here):** the first attempt used the compiler's
   own `opflags=3` on the instruction under test, which sets bits 19/20 =
   release-srcA/release-srcB (EXP-0086/0099) — the later read-back stores of those
   same source registers then returned 0.0. Every instruction under test now uses
   `opflags=0` unless `opflags` is itself the swept variable.
3. **All MODE A families verified computing the predicted value** (`work/pilot/
   famsmoke.py`, 15/15): falu2 add=8.0/mul=15.0, falu2i add=8.0, falu2_ext
   saturate=0.75/1.0, falu2_srcmod10=8.0, falu_srcmod12b (opsel_mod=0) = 8.0
   (**new: EXP-0119 never read this family's own result**), falu3 fma=22.0,
   falu3_ext saturate(fma)=1.0, falu3_srcmod12 fma=22.0, falu_acc add=8.0/mul=15.0.
   **Safety disclosure:** one pilot case ran `falu_srcmod12b` with `opsel=4` (the
   EXP-0119 unrelated-register corruptor) before that guard was added; it returned
   a non-OK status with no output, the host did not wedge, the next case ran
   normally, and the case was removed from the pilot. `opsel` is NOT swept for
   that family in the gated matrix.
4. **MODE B works** (`work/pilot/modebsmoke.py`): in-place single-instruction
   splices into compiled carriers execute and change the answer —
   `half_alu` 0x1c→0x1d flips 5+3=8 to 5*3=15; `fspecial` rsqrt(4)=0.5 → rcp=0.25
   → exp2=16 → floor=4.
5. **Uniform arm works and settles `falu2.mod_lo` bit1** (`work/pilot/unismoke.py`,
   `kernels/carrier_uni.metal`): with a `constant float4&` bound at buffer(2) =
   {101,202,303,404}, `falu2` with `mod_lo=2` and `srcB_reg` swept 0..15 returned
   exactly 101/202/303/404 at indices 6/7/8/9 and 0.0 elsewhere (index 10 returned
   the carrier's own literal 1.0000001f). With `mod_lo=0` the same field reads the
   GPR file. **mod_lo bit1 = "srcB reads the UNIFORM register file".**
6. **MODE-B carrier offsets pinned** by byte search (not by tokenization, which
   desyncs on some of them): k_add@0x2a, k_addi@0x12, k_hadd@0x2a, k_hsat@0x2a,
   k_hfmaabs@0x42, k_copysign@0x30, k_rsqrtf@0x12, k_rsqrtn@0x12.

Zero GPU hangs, zero host wedges across the whole pilot (~250 dispatches).
Throughput measured at ~1.1 ms/case on the persistent runner.

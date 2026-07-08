# COVERAGE-GAPS-01 — Parameter-coverage audit of `docs/`

**Auditor role:** adversarial coverage-gap hunter. **Premise:** the A18/M4 documentation is
assumed *over-generalized* — that rules were validated at one or two points of a parameter space
and then stated for the whole space. This report hunts every such **parameter-coverage gap** so it
can be probed.

**The exemplar we are chasing everywhere:** the tiling doc said "T=64 for bpp≤4"; only bpp4 had
ever been probed at large sizes. When bpp1/bpp2/bpp8 were finally tested, bpp1 turned out to use
**T=128** (doc WRONG) and bpp2/bpp8 needed even-column padding (doc INCOMPLETE). The failure mode:
**a documented rule whose parameter space was only partially populated, hiding a surprise in the
untested arguments.** The docs are honest about many `⏳`/`untested` items; this report focuses on
the more dangerous class — rules stated *generally* ("for all", "always", "identical", "N-bit
field → range R") but *exercised narrowly*, plus rules whose one validated data-point silently
depends on a parameter (like bpp) that was held fixed.

Method: cross-read `docs/` against the `experiments/*/run.sh`, `*.m` sweep harnesses, and
`RESULTS.md` that back them, comparing **what was actually swept** vs **what the doc claims**.

---

## Gap count by subsystem

| Subsystem | Gaps | of which HIGH |
|---|---|---|
| Tiling / texture memory layout | 6 | 3 |
| Descriptors (texture / sampler / format) | 7 | 1 |
| ISA (instruction encodings) | 12 | 2 |
| cmdstream / pipeline / TBDR | 8 | 1 |
| Cross-cutting / M4 delta | 3 | 0 |
| **Total** | **36** | **7** |

## Top ~15 highest-severity gaps (one line each)

1. **[TIL-1] 3D/Array/Cube/MSAA twiddle validated at bpp4 (rgba8) ONLY** — the exact case where 2D hid a bpp surprise; per-plane tile edge T(bpp) and page-granule column rule for volumes/arrays untested at bpp1/2/8/16.
2. **[TIL-5] Compression aux-size formula self-conflicts off bpp4** — "aux = image_bytes/128" AND "1 byte per 8×4-texel block" only agree at bpp4; at bpp8/16 they diverge and neither was measured.
3. **[TIL-2] Block-compressed tiling validated on 4 of ~20 block formats** — only BC1/BC7/ASTC-4×4/8×8; the "block-tile ≈ 32 blocks / blockBytes 8-or-16" rule untested for BC2/3/5/6H, ASTC 5×5…12×12, ETC2/EAC, PVRTC.
4. **[ISA-1] High-register (r16–r95) operand-field encodings are thin** — compact `falu2` dst is 4-bit (r0–r15 only); EXP-0006's source-field sweep concluded a *wrong* mod-64 aliasing; int src widths still byte-diff-inferred. Assembler may mis-encode high regs.
5. **[CMD-1] Blend factor/op encodings are entirely unspecified in docs** — blend is "compiled into the FS microprogram" and deliberately not disassembled; a driver cannot emit any of 19 factors × 5 ops × dual-source from `docs/` alone.
6. **[DESC-1] Render-target attachment format word `@+0x22` decoded for only ~7 renderable formats** — bgra8/rgba8/r8/r32f/rgb10a2/rgba16f/rgba32f; all other RT formats (rg8, r16, rg16f, integer RTs, sRGB, rg32f…) are an *inference* ("= sampled word0"), never validated.
7. **[ISA-2] Saturate / output-clamp modifier never probed** — only abs/neg on the unary `fmov` are documented; MSL `saturate()` and fragment [0,1] clamp lowering are uncharacterized (a Vulkan/GL correctness need).
8. **[ISA-6] Array/3D/cube/MSAA texture-coordinate index operands are ⏳ byte-diff-inferred, not splice-validated** — sampling any non-2D texture from the ISA docs is guesswork.
9. **[TIL-3] MSAA memory interleave & compression tested at 4× / one format** — N=2,4 only; 8× "unsupported" not shown Metal-rejected; 2× lossless-compression engagement and compression×MSAA aux size untested.
10. **[DESC-5] Format channel-arrangement hi-nibble internal bit-split UNDECODED** — the field that disambiguates same-sizeclass formats; 8/14 ASTC block-shape nibbles, YUV, and depth32float_stencil8 stencil aspect also untested.
11. **[ISA-5] 10 of 12 atomic op-codes are byte-diff-inferred, not splice-proven** — only add→max and add→or were spliced; sub/and/xor/fadd/smin/smax/umin/umax/xchg/cmpxchg trusted from single compiles, all on int32.
12. **[CMD-2] Stencil op-codes 0–7 fully swept only on the pass-op field** — sfail/zfail tested with 2 of 8 ops; incrWrap/decrWrap (6/7) observed in one field only; shared-encoding is an assumption.
13. **[DESC-3] Sampler LOD/aniso fields sampled at a few integer points** — fractional LOD, the lodMax 14.0-saturation / 15.875-max boundary, aniso 8× and >16× untested; ×64 / ×8 scaling extrapolated.
14. **[TIL-4] Mip-chain packing (per-level padDim, 0x80 min slot) validated at bpp4 only** — untested at bpp1/2/8/16 where the tile edge T differs.
15. **[CMD-3/CMD-5] MRT tested to 4 attachments; multi-viewport/clip-mask counts spot-tested; u32 index opcode `0x61f4` "inferred, not re-run"** on both A18 and M4.

Full prioritized list with reproduction steps follows.

---

## 1. Tiling / texture memory layout (`docs/tiling/README.md`)

Backing experiments: EXP-0017, EXP-0028 (twiddle), EXP-M4-04/05/06 (bpp sweep), EXP-O2G (comp×mip).
This is the subsystem where the exemplar bug lived; it is also where the most bpp-conditioned
formulas remain single-point-validated.

### TIL-1 — 3D / 2DArray / Cube / CubeArray / MSAA twiddle validated at **bpp4 only** — HIGH
- **Doc claim:** §1.6 gives general formulas: 3D = stacked 2D-Morton planes `offset=(z·Wp·Hp+morton)·bpp`;
  array/cube = independent pow2-padded planes linear-stacked; MSAA = sample-major
  `offset=(N·morton+sample)·bps`. Stated for all formats.
- **What was actually tested:** EXP-0028 RESULTS: the type-code + twiddle captures are all "Captured
  with **rgba8unorm**" (bpp4). The 2D bpp sweep (M4-04/05/06) that found the T=128/even-column
  surprises was **2D only** and did not extend to 3D/array/cube/MSAA.
- **Why a surprise could hide:** the 2D case *proved* the tile edge is bpp-dependent (bpp1→T=128,
  bpp8→T=32) and that tile-row stride is page-granule-rounded (even columns at bpp2/8). None of that
  was re-checked per-plane for volumes/arrays. Open questions: does a 3D texture at **bpp1** use
  T=128 per plane? Is each array-layer / depth-plane stride `padDim(W,T)·padDim(H,T)·bpp` with the
  **same G granule rounding**, or is layer stride computed differently? Does MSAA sample-major
  interleave interact with T(bpp)? At bpp1 a single Morton plane is 128×128 — a small 3D texture's
  per-plane padding could balloon or round differently.
- **Experiment:** GPU-write `texel=encode(x,y,z/layer/sample)` into 3D, 2DArray, Cube, 2DMS textures
  at **bpp1/2/8/16** with non-pow2 W/H and ≥2 layers/planes; read backing bytes via `iotrace`;
  GF(2)-solve per plane. Expected: same `T(bpp)` + `G` rule per plane, planes linear-stacked at
  `padDim·padDim·bpp`. Alternative to catch: bpp1 3D uses a different plane pad; array stride uses
  nextpow2; MSAA changes T.
- **Severity:** HIGH — a wrong volume/array layout at any bpp≠4 corrupts every fetch; this is the
  literal repeat of the exemplar in a dimension nobody swept.

### TIL-2 — Block-compressed tiling validated on **4 of ~20** block formats — HIGH
- **Doc claim:** §1.5 "same tiled-Morton over BLOCK coords; blockBytes = 8 for BC1/BC4, 16 otherwise;
  block-grid tile ≈ 32 blocks, padded to a whole block-tile." Stated for all BC/ASTC/ETC.
- **What was actually tested:** EXP-0028 HW-confirmed only **BC1, BC7, ASTC-4×4, ASTC-8×8**.
- **Why a surprise could hide:** block byte-size is the *effective bpp* of the block grid. The 2D
  lesson was that effective-bpp sets the tile edge T; an 8-byte block (BC1/BC4) vs 16-byte block
  (everything else) could give a different block-tile edge, exactly as bpp1 vs bpp4 did for texels.
  ASTC 5×5/6×6/10×10/12×12 have different texel-footprints per 16-byte block — the "≈32 blocks"
  claim (only seen at 4×4/8×8) may not hold. BC4 (8-byte) block tiling is asserted but never seen.
- **Experiment:** probe BC2/BC3/BC4/BC5/BC6H, ASTC 5×5/6×6/10×10/12×12, ETC2, EAC-R/RG, PVRTC on
  non-pow2 block grids; confirm block-tile edge + padding per block byte-size. Expected: block-tile
  edge = largest pow2 with `edge²·blockBytes ≤ 16 KiB` (mirroring §1.1) — but that itself is untested.
- **Severity:** HIGH — compressed textures are common; wrong block tiling corrupts sampling.

### TIL-5 — Compression aux-SIZE formula self-conflicts away from bpp4, and was measured at bpp4 only — HIGH
- **Doc claim:** §4.3 gives **two** descriptions of the same quantity: `aux_bytes = image_bytes / 128`
  **and** "1 state byte per 8×4-texel block (32 texels = 128 bytes at rgba8)."
- **The latent contradiction:** these agree **only at bpp4**. At bpp16 (rgba32f): `image_bytes/128`
  = `texels·16/128` = 1 byte per **8** texels; "1 byte per 8×4 (=32-texel) block" = 1 byte per 32
  texels = `image_bytes/512`. The two formulas differ by 4× at bpp16 (and 2× at bpp8). Compression
  was only ever measured on **rgba8 (bpp4)** (and eligibility on r8/rgba16f), so which formula is
  right off bpp4 is unknown.
- **Why it matters:** a driver that allocates `paddedImageBytes + paddedImageBytes/128` for a
  compressed rgba16f/rgba32f target may under- or over-allocate the aux buffer → GPU writes past the
  BO or the texture unit reads garbage state bytes.
- **Experiment:** enable compression on rgba16f (bpp8) and rgba32f (bpp16) textures ≥16×16; read the
  backing-BO total size and `secondaryVA − baseVA`; determine aux ratio per bpp. Expected: resolve to
  a single rule (per-block vs per-byte). Also test whether compression even *engages* at bpp8/16.
- **Severity:** HIGH — a size-allocation bug is a memory-safety bug.

### TIL-3 — MSAA memory interleave / lossless compression tested at 4× / one format — MED
- **Doc claim:** §1.6 "N=2, N=4 (8× unsupported); 4× engages MSAA lossless compression at ≥8×8."
- **Gap:** N=2,4 validated for one format; **8× "unsupported" is not shown to be Metal-rejected** vs
  merely untested. 2× compression engagement, the 2× vs 4× aux size, and compression×MSAA aux
  placement are untested. MSAA at bpp≠4 untested (ties to TIL-1).
- **Experiment:** attempt 8× (confirm Metal reject vs HW fault); probe 2× compression aux; sweep MSAA
  interleave at bpp1/2/8/16.
- **Severity:** MED.

### TIL-4 — Mip-chain packing validated at bpp4 only — MED
- **Doc claim:** §3 per-level `padDim(W>>L,T)·padDim(H>>L,T)·bpp`, 0x80 min-slot; general.
- **What was tested:** 128×128 r32 (bpp4) and 96×96 r32. Not bpp1/2/8/16, where T differs, so the
  per-level padded sizes and the 0x80 floor at bpp16 are untested.
- **Experiment:** build mip chains at each bpp with non-pow2 dims; read per-level offsets.
- **Severity:** MED.

### TIL-6 — Compression eligibility threshold assumed bpp-independent from ~3 formats — MED
- **Doc claim:** §4.1 "W ≥ 16 ∧ H ≥ 16 texels, **bpp-independent**" (r8 16×16 yes / rgba16f 8×8 no,
  15×15 no, 17×17 yes, 16×15/32×8 no).
- **Gap:** "bpp-independent" is asserted from r8/rgba8/rgba16f near the threshold; rgba32f (bpp16,
  where 16×16 is a full 16 KiB page) and the integer formats untested. The interaction of the
  threshold with the tile edge T(bpp) is unprobed.
- **Experiment:** sweep the 15/16/17 threshold at bpp1/8/16 and for integer/packed formats.
- **Severity:** MED.

---

## 2. Descriptors — texture / sampler / format (`docs/descriptors/`)

Backing: EXP-0015 (`tvar.m`), EXP-0028, EXP-G1b, EXP-O2B, EXP-M4-04.

### DESC-1 — Render-target attachment format word `@+0x22` decoded for ~7 formats — HIGH
- **Doc claim:** `pipeline/README.md` + `cmdstream/README.md`: attachment pixel-format byte @+0x22,
  "= sampled descriptor word0 with byte0 hi-nibble 0."
- **What was tested:** EXP-G1b RESULTS explicitly lists the format sweep as **bgra8, rgba8, r8,
  r32f** (four); EXP-0021 adds rgb10a2, rgba16f, rgba32f. ~7 of ~40 renderable formats.
- **Why a surprise could hide:** the "= sampled word0" equivalence is an inference from those 7. The
  attachment path also carries store-program / MSAA / sample-count bits in the same word (+0x24); for
  integer RTs, sRGB RTs, rg8/r16/rg16f/rg32f the exact packed word is unvalidated. A wrong RT format
  word mis-renders or faults the store.
- **Experiment:** render into every renderable format; diff the LOAD/RENDER/STORE segment format
  words; confirm the "= texture-descriptor code" rule holds across all.
- **Severity:** HIGH (a driver must emit RT descriptors for far more than 7 formats).

### DESC-2 — 14-bit dims validated on 2D/rgba8; PBE split at few points — MED
- **Doc claim:** width−1/height−1 are 14-bit (max 16384); PBE (storage-image) descriptor uses a
  *different* split (word0[24:31]‖word1[0:5] / word1[6:19]).
- **What was tested:** the 14-bit range was reached only on **M4** (8192/16384) with **2D rgba8**; on
  A18 the descriptor sweep tops out at 256px (`tvar.m` dims 4…256). For 3D/cube/array the width/height
  vs depth/arrayLen field packing at large sizes is unvalidated (depth/arrayLen shares word3[14:] with
  linear stride — context-dependent, only spot-checked). The PBE alternate split was validated at a
  handful of sizes ("M4 validates the inferred width-high field word1[0:5]").
- **Experiment:** sweep width/height to 16384 for 3D/cube/array on A18; sweep PBE descriptor across
  sizes/formats with asymmetric dims to separate W/H.
- **Severity:** MED.

### DESC-3 — Sampler LOD / anisotropy fields sampled at a few integer points — MED
- **Doc claim:** lodMin ×64 (6 frac bits), lodMax ×8 (3 frac; default→14.0), maxAnisotropy 3-bit
  log2 (→128×).
- **What was tested:** `tvar.m` used lodmin 1/2, lodmax 3/5/15; aniso 2/4/16 only. The ×64 and ×8
  scaling and fractional-bit claims are extrapolated from integer LODs; the lodMax 14.0-saturation
  boundary and the field max (7-bit ×8 = 15.875) are untested; aniso 8× and the whole >16× range
  (`hypotheses` #5) untested.
- **Experiment:** sweep fractional lodMin/lodMax (0.25, 1.5, 13.9, 14.1, 16.0), aniso {8, 32, 64,
  128}; confirm scaling + saturation + whether >16× is a HW no-op or works.
- **Severity:** MED (mip/aniso quality; a mis-scaled LOD is a visible bug).

### DESC-4 — Untested address-mode / border / swizzle codes — LOW-MED
- **Doc claim (honest):** address codes 4/6/7 untested; border code 3 untested; swizzle codes 6/7
  untested; `clampToZero == clampToBorder(transparent)` (one mode).
- **Gap:** these are flagged, but a Vulkan driver mapping `VK_SAMPLER_ADDRESS_MODE_*` needs to know
  whether codes 4/6/7 fault or alias. The mirrorClampToEdge=5 vs the gap at 4 is suspicious.
- **Experiment:** splice each unused code into a sampler and observe (edge behavior / fault).
- **Severity:** LOW-MED.

### DESC-5 — Format channel-arrangement hi-nibble bit-split UNDECODED; format families untested — MED
- **Doc claim (honest):** `format-table.md` §2b: byte0 hi-nibble "disambiguates channel arrangement…
  its internal bit-split was not decoded." 8/14 ASTC block-shape nibbles untested; YUV/video
  untested; depth32float_stencil8 stencil-aspect code untested.
- **Why it matters:** the hi-nibble is *load-bearing* for format identity (it separates 1×32 vs 2×16
  vs 4×8 at the same sizeclass). A driver emitting a format whose exact byte0 was never captured must
  guess the nibble. 60 formats captured is broad, but the *rule* for the nibble is unknown, so any
  uncaptured format is unreachable.
- **Experiment:** capture the remaining format byte0 values; reverse the nibble's internal meaning
  (channel count / order / width bits) so uncaptured formats are derivable.
- **Severity:** MED.

### DESC-6 — Numtype orthogonality proven for 4 base formats, generalized to all — LOW-MED
- **Doc claim:** "numtype nibble fully orthogonal — HW-validated across all four numeric types for
  r8/r16/r32/rgba8."
- **Gap:** orthogonality (unorm/snorm/uint/sint/float independent of sizeclass) is proven for 4
  format families and asserted for the other ~26. Packed formats (rgb10a2, rg11b10, rgb9e5) and
  64/128-bit formats' numtype behavior not swept.
- **Experiment:** vary numtype on packed/wide formats; confirm the code = `numtype<<5|sizeclass` rule.
- **Severity:** LOW-MED.

### DESC-7 — Buffer descriptor "no length/format word" — bounds behavior untested — LOW
- **Doc claim:** buffer binding = bare inline 8-byte VA, no length.
- **Gap:** validated for `device T*`. No bounds word means no HW bounds checking — untested for
  out-of-bounds reads (robustBufferAccess), and texture-buffer / typed-buffer descriptors not covered.
- **Severity:** LOW.

---

## 3. ISA — instruction encodings (`docs/isa/`)

Backing: EXP-0005/0006/0007/0010/0012/0013/0016/0018/0020/0022/0023/0033/0034/0035 + RT-* passes.
The census is mature and the red-team caught real errors; the residual gaps are **operand/parameter
sub-spaces** that were validated at one or two points.

### ISA-1 — High-register (r16–r95) operand-field encodings are thin — HIGH
- **Doc claim:** register fields are `(reg<<1)|size`, "span r0–r127, covering the 96-reg file";
  compact `falu2` dst is a 4-bit nibble (r0–r15); high dst via 8-byte `falu3` (dst=byte+1, "r64
  observed").
- **What was tested:** EXP-0006's operand sweep concluded **64 GPRs with mod-64 aliasing** — later
  found **WRONG** (EXP-0020: 96 distinct, no aliasing). The compact-form dst is only 4-bit. `falu3`
  high-dst has a single observed point (r64). `encoding-tables.md` marks many integer src fields
  `raw/unmapped` ("exact widths a follow-up", EXP-0007). RT-7 re-proved the *file* is 96 distinct
  (via memory-index fault + ALU-source-reads-0), but did **not** re-sweep the per-form **operand-byte
  encoding** for r16–r95 across every instruction.
- **Why a surprise could hide:** the one sweep that touched the operand field space drew a wrong
  conclusion (mod-64). An assembler that must place any of r0–r95 in any operand slot of any form
  could mis-encode high registers (e.g., a bit that reads as size vs a high reg bit). This is the
  correctness engine of the extrapolate-and-test loop.
- **Experiment:** for each instruction form (falu2/falu3/int-add/imad/load/store/tex/atomic), splice
  each operand position across {r0, r15, r16, r31, r63, r64, r95} and observe the read/written value.
- **Severity:** HIGH (assembler correctness under register allocation).

### ISA-2 — Saturate / output-clamp modifier never probed — MED-HIGH
- **Doc claim:** only source modifiers abs(byte+5=0x02)/neg(0x0a) on the unary `fmov` are documented.
- **Gap:** no saturate/output-clamp modifier is documented anywhere. MSL `saturate()`, `clamp(x,0,1)`,
  and the classic fragment-output [0,1] clamp — how they lower (a modifier bit? a follow-up min/max?)
  is uncharacterized. Vulkan/GL rely on saturating outputs.
- **Experiment:** compile `saturate(x)` / `clamp(x,0,1)` on float and half; byte-diff; probe for a
  per-instruction saturate bit. Expected: either a modifier bit (native) or a min/max lowering
  (emulated) — either result is a first-class finding.
- **Severity:** MED-HIGH (capability + encoding gap on a ubiquitous op).

### ISA-3 — Per-operand abs/neg on 2-/3-source forms spot-validated — MED
- **Doc claim:** "no srcA-negate in the 6-byte form; abs lives in a 10-byte extended form"
  (HW-validated `a+|b|`).
- **Gap:** modifier placement validated for one case (`a+|b|`). abs/neg on srcA vs srcB vs srcC (fma),
  on integer operands, and combinations (`|a|·−b`) are untested. The compiler "commutes to reuse
  srcB-negate" — so the srcA-negate encoding may simply never have been exercised.
- **Experiment:** sweep modifier bits per operand per form (falu2/falu3/fma/int).
- **Severity:** MED.

### ISA-4 — Immediate encodings tested at few points — MED
- **Doc claim:** 8-bit minifloat (4exp/3mant, bias 11, range {0,1/32…30}); integer inline K∈{0..255}
  as `(K<<1)`; load `idx_off` immediate (byte+9 bit7 / +10 / +11).
- **Gap:** minifloat: 16 constants tested (a good sample but the exp=8 subnormal edge and the
  fallback boundary are thin). Integer immediate: the ≥256 / negative "materialize to register"
  boundary asserted, not swept. `idx_off`: only 4 points (a[41], a[42], a[56], a[552]); the field
  widths (+9bit7=+1, +10=+2/unit, +11=+512/unit) and max range are inferred from those.
- **Experiment:** sweep the minifloat over all 256 byte values (map every representable magnitude +
  the reg-fallback boundary); sweep integer immediate around 255/256 and negatives; sweep `idx_off`
  to its max to confirm field widths.
- **Severity:** MED.

### ISA-5 — 10 of 12 atomic op-codes are byte-diff-inferred (not spliced); all on int32 — MED
- **Doc claim:** atomic op at byte+12 with a 12-entry code table (add/sub/and/or/xor/fadd/smin/smax/
  umin/umax/xchg/cmpxchg).
- **What was tested:** EXP-0018 splice-proved only **add→max** and **add→or** (1024→32). The other 10
  codes come from compiling each MSL atomic (byte-diff), and all data-type validation is on **int32**
  (+ fadd on float). Signed-vs-unsigned min/max correctness on real data is inferred.
- **Experiment:** splice each of the 12 codes into a running atomic and check the arithmetic result;
  validate smin/smax/umin/umax with values straddling sign boundaries.
- **Severity:** MED.

### ISA-6 — Non-2D texture coordinate/index operands are ⏳ inferred, not splice-validated — MED-HIGH
- **Doc claim:** array/3D/cube/MSAA dims in op+2 (`0x13` cube / `0x39` 3D / `0x53` cube-array /
  `0x80` MSAA / `0x97` array bit7); "extra index (slice/face/z/sample/ref) via op+3 **⏳ byte-diff,
  not splice-validated**."
- **Gap:** the entire non-2D coordinate-operand encoding is inferred. The sample-op decode
  (op+2/op+4/op+5) was splice-validated mostly on **2D**. A driver emitting a cube/3D/array/MSAA
  sample from these docs is guessing the index operand.
- **Experiment:** for each non-2D type, splice the op+3 index operand and observe which layer/face/z/
  sample is read; validate op+2 dim codes by splice (cube↔3D↔array).
- **Severity:** MED-HIGH.

### ISA-7 — Subgroup/quad op sub-fields validated on int32/float at few lanes — MED
- **Doc claim:** shuffle modes (xor/up/down/rotate), byte+6 lane as `(value<<1)`, reduce dtype byte+7,
  ballot forms.
- **Gap:** the reduce dtype enum already needed a red-team fix (int=0x03 not 0x01, RT-5) — evidence
  this space is error-prone. dtypes beyond int32/float (i8/i16/i64/f16/bf16 reduce/scan) untested;
  ballot high-nibble forms "co-vary, decode-label only, not independently settable"; shuffle lane
  field tested at few lane values.
- **Experiment:** sweep reduce/scan over all dtypes; sweep shuffle lane/mask across the full 0–31
  range; confirm each mode by splice.
- **Severity:** MED.

### ISA-8 — Matrix `0xcf` validated on fp32; half-datapath accumulate byte UNCHARACTERIZED — MED
- **Doc claim (honest):** operand map splice-proved on the **fp32** datapath; "the half-datapath
  accumulate byte is **uncharacterized** (RT-10)"; byte+1 dtype values for bf16/mixed inferred.
- **Gap:** only fp32 fully mapped; fp16/bf16/mixed accumulate-enable and op-enable byte values are
  inferred. Only 8×8×8 (other dims Metal-reject).
- **Experiment:** splice-map the half/bf16 datapath's op-enable + accumulate bytes.
- **Severity:** MED.

### ISA-9 — RT `rt_intersect` operand sub-fields are inferred and splice-INERT — MED
- **Doc claim (honest):** every documented sub-field of `rt_intersect` (result reg, mode byte+2,
  AS-type byte+4) is **splice-inert** on the single-primitive path; the AS-type dispatch is
  **structural** (whole-kernel shape), not a settable field.
- **Gap:** a driver cannot emit ray intersection from field-level docs — it must replicate whole
  compiler-generated kernel shapes. This is an acknowledged "can't-emit-from-docs" gap, but it is a
  real coverage hole for the intersect operand space.
- **Experiment:** (hard) build multi-primitive / multi-AS kernels to try to make a sub-field
  load-bearing; otherwise document that the field space is non-orthogonal.
- **Severity:** MED (acknowledged; flag for the impl team that RT emit needs kernel-shape templates).

### ISA-10 — Control-flow offset fields validated at few distances — LOW-MED
- **Doc claim:** loop back-edge `off6` (signed LE, target=addr+4+off6) and CALL `off40` (target=
  call+4+off40).
- **Gap:** validated at ~4 distances each; the field widths (6-byte vs 40-bit) and max branch range,
  plus the reconverge/if_push **level** field range under deep nesting, are inferred from a specific
  corpus.
- **Experiment:** emit branches near the field-width limits; deep nesting to exercise level fields.
- **Severity:** LOW-MED.

### ISA-11 — Half / bfloat ALU validated for add/mul/fma only — LOW-MED
- **Doc claim:** `0x10` fp16 group (add 0x1c/mul 0x1d), `0x11` bfloat group (add/mul/fma), "half2
  packs, int16 doesn't."
- **Gap:** conversions, compares, min/max, transcendentals, and shifts in fp16/bf16 are untested; the
  bf16 datapath has only add/mul/fma. The `0x10` size-bit reaching "only the low half" was validated
  for one read.
- **Experiment:** compile the full half/bf16 op set; confirm each maps to a native op or a lowering.
- **Severity:** LOW-MED.

### ISA-12 — Transcendental / SFU function-select and range-reduce validated at few args — LOW
- **Doc claim:** SFU function codes (rcp/rsqrt/exp2/round/sqrt/log2); precise = 0x29 seed + 2 NR;
  sin/cos range-reduce via 0x2b; large-arg accuracy poor (SW range reduction needed — known gap).
- **Gap:** the function-select bytes are validated; the 0x2b range-reduction op sub-fields and the
  NR-iteration structure are inferred; accuracy measured at a few args.
- **Severity:** LOW (the actionable driver gap — large-arg trig — is already documented).

---

## 4. cmdstream / pipeline / TBDR (`docs/cmdstream/`, `docs/pipeline/`)

Backing: EXP-0011/0014/0019/0021/0024/0027/0030 + O2-A/G/H + G1a/b + RT-2a/4/6/11.

### CMD-1 — Blend factor/op encodings entirely unspecified in `docs/` — HIGH (structural)
- **Doc claim:** blend is "lowered into the fragment shader's blend microprogram" (compiled code,
  **deliberately not disassembled** per clean-room rule 5). `0x58000` keeps only write-mask +
  blend-class/constant/enable.
- **Gap:** from `docs/` alone a driver cannot realize **any** blend factor (19) × op (5) × dual-source
  — there is no spec of the microprogram, and the "blend-class" enum in the state pool was diffed
  across only a few factors (run.sh sweeps factors mainly to *prove* they rewrite the FS, not to
  decode a code). This is the single biggest "implement-from-docs" hole; it is partly a deliberate
  clean-room punt (the impl team writes its own blend-lowering compiler, as Asahi does), but the
  **which-class-for-which-factor** mapping and the constant-color/enable field layout are only
  spot-covered.
- **Experiment:** sweep all 19 factors × 5 ops (per-RGB and per-alpha) and dual-source; decode the
  `0x58000` blend-class / enable / constant-color bit layout (the *state* side is cleanly traceable
  even though the FS side is off-limits). Confirm which factor-combos change only the class field vs
  rewrite the FS.
- **Severity:** HIGH (for objective 1; note the FS microprogram itself is intentionally out of scope).

### CMD-2 — Stencil op-codes 0–7 fully swept only on the pass-op field — MED
- **Doc claim:** stencil-op 0–7 (keep/zero/replace/incrClamp/decrClamp/invert/incrWrap/decrWrap) for
  pass/zfail/sfail fields.
- **What was tested:** EXP-0019 run.sh swept all 8 ops on **spass** only; **sfail/szfail tested with
  just replace + invert** (2 of 8). incrWrap/decrWrap (codes 6/7) observed in one field.
- **Why a surprise could hide:** the three op-fields are at different bit offsets (pass[18:16],
  zfail[21:19], sfail[24:22]); the shared 0–7 encoding is an assumption. A field could have a
  different enum or a reserved code.
- **Experiment:** sweep all 8 ops on sfail and szfail independently.
- **Severity:** MED.

### CMD-3 — RT format word (see DESC-1) + MRT count coverage — MED
- **Doc claim:** attachment format @+0x22; MRT relocates to tiler heap for N≥2, arrayed 0x20-stride;
  "8× rgba32f MRT renders correctly."
- **Gap:** MRT descriptor layout diffed for **1–4** attachments only; 5/6/7/8 untested (Metal max is
  8, and the doc *claims* 8× renders but only verified it doesn't fault — the descriptor array layout
  at k=4..7 is unvalidated). Per-attachment format mixing (different formats per RT) untested.
- **Experiment:** capture 5–8-attachment MRT with mixed formats; confirm the k·0x20 array extends and
  each attachment's format word.
- **Severity:** MED.

### CMD-4 — Primitive × indexed × instanced × index-type combinations spot-tested — MED
- **Doc claim:** prim codes (point 0x00, line 0x01, tri 0x06, triStrip 0x09, lineStrip 0x03); indexed
  opcode `0x61f2`(u16)/`0x61f4`(u32); baseVertex/baseInstance offsets.
- **Gap:** `0x61f4` (u32 index) is "inferred, not re-run" on **both A18 and M4** (M4-deltas §3). Each
  primitive type was not tested under both indexed and non-indexed and instanced paths; baseVertex/
  baseInstance validated at few values; the record-shift for indexed draws proven, but per-prim.
- **Experiment:** matrix of {5 prims} × {indexed u16, indexed u32, non-indexed} × {instanced,
  base-vertex, base-instance}; confirm opcodes + record field positions.
- **Severity:** MED.

### CMD-5 — Multi-viewport / clip-mask / point-size / primitive-restart counts spot-tested — MED
- **Doc claim (O2-A):** viewport count `((count-1)<<12)|0x0C00` (max 16); clip-distance plane mask
  bits[7:0] (max 8); custom restart index (HW field exists, Metal always all-ones).
- **Gap:** the viewport count formula and the clip-mask were validated at a few counts, not swept to
  the 16/8 maxima; the **custom** restart index is asserted to exist but was **never written with a
  non-all-ones value** (Metal won't emit it) — so a Vulkan driver relying on the HW field is trusting
  an untested encoding.
- **Experiment:** sweep viewport count 1..16 and clip planes 1..8; splice a custom restart index and
  confirm it cuts.
- **Severity:** MED.

### CMD-6 — Firmware/kernel-managed submit params inferred, not captured — MED
- **Doc claim:** ZLS/depth-store, partial-render trigger, graphics shader-entry, scissor
  (`isp_scissor`), RT BVH build are "kernel-managed" (kernel-interface.md); userspace *computes* the
  value, firmware writes the register.
- **Gap:** these are explicitly out of the userspace command stream, but the **submit-struct field
  layout** a userspace driver must hand the kernel is inferred/uncaptured (no working kernel driver to
  trace against). End-to-end depth-store / partial-render behavior is unverified.
- **Experiment:** coordinate with the kernel team; where possible, trace the submit-ioctl payload for
  these params.
- **Severity:** MED (acknowledged out-of-scope, but blocks end-to-end rendering).

### CMD-7 — MSAA / occlusion / timestamp parameter breadth — LOW-MED
- **Doc claim:** MSAA 2×/4× (bit24 LSB, bit27 store); occlusion bool/count; timestamps stage-boundary
  only.
- **Gap:** 8× not shown Metal-rejected (ties TIL-3); occlusion offset `byteOffset<<14` tested at few
  offsets; timestamp period=1.0 assumed cpu==gpu at one point.
- **Severity:** LOW-MED.

### CMD-8 — Threadgroup-size rounding / occupancy-tier threshold interpolated — LOW-MED
- **Doc claim:** effective-tg @+0x1c is each axis rounded up to pow2 with product ≥32 (1..32→32,
  48/64→64, 100→128, 2-D (3,5)→(4,8)); "exact rounding is occupancy/shader-dependent." Occupancy tier
  bit23: "clear ≤11 / set ≥12 GPRs threshold is **INTERPOLATED, not measured**" (only f0=8 and f0=14
  captured).
- **Gap:** the tg-rounding rule is sampled at a handful of sizes and admitted shader-dependent; the
  register→tier threshold is an interpolation between two points (the 11↔12 flip was never observed).
- **Experiment:** sweep threadgroup sizes across many axis combos; sweep GPR footprint 8→16 by 1 to
  find the exact tier-bit flip.
- **Severity:** LOW-MED.

---

## 5. Cross-cutting / M4 delta (`docs/m4-deltas.md`, capability docs)

### X-1 — M4 machine model entirely PENDING; several M4 rows "inferred-identical, not re-run" — MED
- **Doc claim:** m4-deltas §2 machine model "⏳ PENDING (expected identical)"; §3 notes u32-index
  opcode and timestamps are "inferred-identical, not re-run"; §1 ISA delta "in progress" (census
  only, byte-diff pending).
- **Gap:** M4 completeness leans on the A18-identity assumption for the machine model (96 GPR /
  spill / SR / uniform), u32 index, and timestamps. If the M4 (g16g) differs in any of these, the
  "A18 docs + delta = M4 driver" claim breaks silently.
- **Experiment:** run the EXP-0020/0031 splice suite on M4; re-run u32 index + timestamp captures.
- **Severity:** MED (for the M4 deliverable specifically).

### X-2 — Capability matrix "identical M4" from 32 accept/reject probes — LOW-MED
- **Doc claim:** M4 §8 "zero capability deltas" from 32 MSL accept/reject probes.
- **Gap:** 32 probes is a curated subset; capability *encodings* (not just accept/reject) assumed
  identical. Fine as a first pass, but "zero deltas" is stated more strongly than 32 points support.
- **Severity:** LOW-MED.

### X-3 — "Unknown/untested" cluster carried in capability-matrix §4 — LOW (already flagged)
- GS/transform-feedback A18-native re-probe (assumed emulate, not independently probed on A18);
  anisotropy >16×; polygon-point fill; exotic gather/tex-type variants. These are honestly labeled
  ❓ in `capability-matrix.md` §4 — listed here for completeness so they aren't lost.
- **Severity:** LOW (already tracked).

---

## Notes on scope / honesty

- Many items above are **already marked `⏳`/`untested`/`inferred` in `docs/`** — I include them
  because a coverage audit must enumerate the *parameter* holes even where the doc flags the field,
  and because several "flagged" items (TIL-5's aux-size contradiction, DESC-1's format breadth,
  ISA-1's high-register operand encoding) are more dangerous than their terse `⏳` suggests.
- The **strongest new findings** (not merely restating a `⏳`) are: **TIL-1** (3D/array/MSAA only at
  bpp4 — the exact exemplar in an unswept dimension), **TIL-5** (a latent aux-size formula
  contradiction that only a non-bpp4 probe resolves), **TIL-2** (block-tiling across block byte-sizes),
  **ISA-1** (the one operand-register sweep drew a since-refuted conclusion), and **ISA-2** (saturate
  never probed at all).
- **CMD-1** (blend microprogram) is a deliberate clean-room boundary, not an oversight — but the
  *state-pool* side of blend is cleanly traceable and only spot-covered, so it belongs on the list.

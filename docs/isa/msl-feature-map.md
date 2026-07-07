# MSL → AGX Instruction-Family Provocation Map (A18 Pro / G17P / Apple9)

A practical index that answers one question for every shader instruction family we need to
characterize: **what is the minimal MSL source that forces the compiler to emit that family?**
It exists so ISA experiments can jump straight to "compile this, disassemble, diff" instead of
re-discovering how to provoke textures / atomics / subgroups / ray tracing / matrix ops each time.

**This is a planning index, not a hardware claim.** Every snippet below is **our own MSL** (safe to
write and compile — OWN-SHADER). Every `§` reference is a bare citation into the **public** Metal
Shading Language Specification (2025-10-23 revision, Metal 4), `gpu_knowledge/apple_official/msl_spec/`
(PUBLIC). Nothing here decodes an Apple binary. No row asserts an AGX encoding — that is what the
experiments produce. Apple9 hardware context (hardware ray tracing, mesh shading, Dynamic Caching)
is cited from Apple's public WWDC tech talk `wwdc2023-tech-talk-explore-gpu-advancements-m3-a17-pro.md`
(PUBLIC).

---

## RE recipe (per snippet)

1. **Compile** the snippet on the device with `tools/shdump` (runtime `newLibraryWithSource:` →
   `MTLBinaryArchive` → `agxparse.py` isolates the `_agc.main` AGX bytes). See `tools/shdump/README.md`.
2. **Tokenize / disassemble** the bytes with `tools/agx-isa` (`agxisa.py tokenize <hex>`, then
   `disasm`). Unknown groups tokenize as raw parcels — those are the new families to solve.
3. **Diff / sweep to characterize.** Compile a near-identical variant (change one op, one operand,
   one type), `bytediff.py` the two `_agc.main` hex strings, and localize the field that moved.
   Then sweep that field and, where possible, **hardware-validate** by splicing bytes and running on
   the GPU (`tools/agxtest`, the round-trip testbed) — see `docs/isa/README.md` and EXP-0003/EXP-0005.

### Working tips for clean provocation
- **Keep kernels minimal and force a side effect.** Always write the result to a `device` buffer
  (`out[tid] = ...`) so the optimizer cannot dead-code the op you are trying to elicit. Use a
  `device`-loaded input (not a constant) for the same reason.
- **Math precision matters.** `-fmetal-math-mode=fast` (the shdump default) vs `--no-fast-math`
  changes reciprocal/rsqrt/transcendental lowering and FP-contraction (fma) — compile **both** and
  diff; the fast/precise split is itself a family boundary (§1.6.3, §6.5, §8.4).
- **`half` vs `float` vs `int` are different encoding paths** (we already see int-ALU ≠ float-ALU,
  EXP-0001). Provoke each width separately.
- **Stage matters for extraction.** `shdump` today extracts **compute** (`__compute`) cleanly;
  vertex/fragment/mesh/object/tile stages need the extractor extended to their Mach-O sections
  (`__vertex`/`__fragment`/…). Rows below tagged *stage ≠ compute* are blocked on that tooling step.

### How to read each entry
Each family is a heading + a minimal compilable snippet, followed by a metadata footer in the
requested schema:

> **§** spec ref · **stage** where it must live · **Apple9** note · **provokes** the instruction family

---
---

# Part A — Baseline families (Mesa already models these for G13/G14; we re-derive G17P encodings)

## A1. Integer & float arithmetic (add/sub/mul)

```metal
#include <metal_stdlib>
using namespace metal;
kernel void arith(device float *a [[buffer(0)]], device float *b [[buffer(1)]],
                  device float *o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];        // swap to *, - to move the op-select field
}
// integer variant: change the three `float` to `int` — different encoding path (EXP-0001)
```
> **§** 3.1 (scalar/vector operators), 6.3 (integer funcs) · **stage** compute · **Apple9** float 2-src op-select already HW-validated (falu2: fadd=0b100, fmul=0b101, EXP-0005); int-ALU group `0x9f` length rule **unsolved** · **provokes** float ALU (`0x09`), integer ALU (`0x9f`)

## A2. Fused multiply-add (FMA / contraction)

```metal
kernel void fma_k(device float *a, device float *b, device float *c,
                  device float *o, uint i [[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], c[i]);       // explicit; also try a*b+c under fast vs precise math
}
```
> **§** 6.5 (`fma`), 1.6.3 (FP-contract) · **stage** compute · **Apple9** the float-ALU length bit (byte +2 bit 1) already distinguishes the 8-byte fma form from 6-byte add/mul (EXP-0005) · **provokes** float FMA form; contrast `a*b+c` fast (contracts to fma) vs `--no-fast-math` (separate mul+add)

## A3. min / max (int & float)

```metal
kernel void minmax(device float *a, device float *b, device float *o,
                   uint i [[thread_position_in_grid]]) {
    o[i] = min(a[i], b[i]) + max(a[i], b[i]);   // also min3/max3/median3 (§6.3)
}
```
> **§** 6.3 (int min/max/min3/max3/median3), 6.5 (fmin/fmax) · **stage** compute · **Apple9** float min/max is its own group (`0x12`, 6-byte, EXP-0005) · **provokes** min/max ALU; `median3`/`max3` may expose 3-source forms

## A4. Reciprocal / rsqrt / divide

```metal
kernel void recip(device float *a, device float *o, uint i [[thread_position_in_grid]]) {
    o[i] = 1.0f / a[i] + rsqrt(a[i]) + precise::divide(a[i], a[i] + 1.0f);
}
```
> **§** 6.5 (`rsqrt`, `divide`, fast vs precise), 1.6.3 (allow-reciprocal) · **stage** compute · **Apple9** fast-math turns `x/y` into `x * recip(y)`; recip/rsqrt are prime candidates for a dedicated approximation unit + Newton-Raphson refinement sequence — diff fast vs precise to separate the seed instruction from the refinement · **provokes** reciprocal/rsqrt estimate unit + refinement

## A5. Transcendentals (sin/cos/exp/log/pow/tan)

```metal
kernel void trig(device float *a, device float *o, uint i [[thread_position_in_grid]]) {
    o[i] = sin(a[i]) + cos(a[i]) + exp2(a[i]) + log2(a[i]) + sqrt(a[i]);
    // also: tan, exp, log, pow(a,b); and the fast:: / precise:: namespaces
}
```
> **§** 6.5 (math funcs), 8.4 (ULP/relative error tables) · **stage** compute · **Apple9** likely a range-reduction + core-approximation (`exp2`/`log2`) sequence rather than direct `sin`/`exp` ops; compile each of `sin/cos/exp/exp2/log/log2/sqrt/pow` separately and diff to find the shared primitive · **provokes** special-function/transcendental path

## A6. Conversions & reinterpretation (fp16 ↔ fp32 ↔ int, `as_type`)

```metal
kernel void conv(device float *fin, device int *iin,
                 device half *hout, device uint *uout,
                 uint i [[thread_position_in_grid]]) {
    hout[i] = half(fin[i]);                 // fp32 -> fp16
    float f = float(hout[i]);               // fp16 -> fp32
    int   n = int(fin[i]);                  // fp32 -> int (round toward zero, §2.22)
    uout[i] = as_type<uint>(f) ^ uint(n);   // bit-reinterpret, no conversion (§2.22)
}
```
> **§** 2.22 (`as_type`, `static_cast`), 8.6 (conversion rules) · **stage** compute · **Apple9** `as_type` should be a no-op move (same bits) → good for isolating pure fp16↔fp32 convert instructions from any packing · **provokes** int↔float convert, fp16↔fp32 convert, bit-reinterpret move

## A7. Pack / unpack (normalized <-> packed integer)

```metal
kernel void packing(device uint *pin, device uint *pout, device float4 *fout,
                    uint i [[thread_position_in_grid]]) {
    float4 c = unpack_unorm4x8_to_float(pin[i]);   // 8.8.8.8 unorm -> float4
    fout[i]  = unpack_snorm2x16_to_float(pin[i]).xyyx;
    pout[i]  = pack_float_to_unorm4x8(c) ^ pack_float_to_unorm10a2(c);
}
```
> **§** 6.14 (Table 6.23 unpack, 6.24 pack), 8.7 · **stage** compute · **Apple9** `snorm10a2` pack/unpack are **new in Metal 4** (§1.3) — verify they lower to real ops vs a shift/mask sequence; sRGB variants (`*_srgb_*`) exercise the sRGB conversion path · **provokes** pack/unpack + normalized-format convert (shared with texture read/write conversion)

## A8. Comparisons, select / ternary, boolean logic

```metal
kernel void selcmp(device float *a, device float *b, device int *m,
                   device float *o, uint i [[thread_position_in_grid]]) {
    bool p = (a[i] < b[i]) && (m[i] != 0);       // compare + boolean AND
    o[i] = select(a[i], b[i], p);                // == p ? b : a  (§6.4)
}
```
> **§** 3.1 (relational/logical operators), 6.4 (relational funcs: `select`, `all`, `any`, `isnan`) · **stage** compute · **Apple9** watch for predicate-register vs value-select lowering; `isnan`/`isinf` may need precise math to survive · **provokes** compare-set, conditional-select/csel, boolean/bitwise-on-bool

## A9. Bitfield ops (extract/insert, clz, ctz, popcount, reverse, rotate)

```metal
kernel void bits(device uint *a, device uint *b, device uint *o,
                 uint i [[thread_position_in_grid]]) {
    uint x = a[i];
    o[i] = extract_bits(x, 4, 8) | insert_bits(x, b[i], 3, 5)
         | clz(x) + ctz(x) + popcount(x) + reverse_bits(x) + rotate(x, b[i]);
}
```
> **§** 6.3 (`extract_bits`, `insert_bits`, `clz`, `ctz`, `popcount`, `reverse_bits`, `rotate`) · **stage** compute · **Apple9** these are exactly the Vulkan-relevant integer ops beyond Metal's arithmetic surface — high value; provoke each in isolation, some may be multi-instruction · **provokes** bitfield-extract/insert, count-leading/trailing-zero, popcount, bit-reverse, funnel/rotate

## A10. Control flow (if/else, loops, break/continue, return, function calls)

```metal
kernel void cflow(device int *a, device int *o, uint i [[thread_position_in_grid]]) {
    int acc = 0;
    for (int k = 0; k < a[i]; ++k) {            // data-dependent loop -> real branch
        if ((a[i] & k) != 0) { acc += k; continue; }
        if (acc > 1000) break;
        acc -= k;
    }
    if (a[i] < 0) { o[i] = -1; return; }        // early return
    o[i] = acc;
}
```
> **§** 5.11, 1.5.4 (no `goto`; recursion allowed in compute since Metal 2.4) · **stage** compute · **Apple9** exposes the branch/predication + SIMD-divergence/reconvergence encoding and the loop back-edge; the program-termination word is still **⏳ unsolved** (EXP-0003) — data-dependent CF is the way to pin it down · **provokes** conditional branch, loop back-edge, predication/execution-mask, `stop`/return

## A11. Function calls & function pointers (`[[visible]]`, tables)

```metal
[[visible]] int addone(int x) { return x + 1; }     // forces a real call, not inlined
kernel void callk(device int *a, device int *o,
                  visible_function_table<int(int)> tab [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = tab[a[i] & 1](a[i]) + addone(a[i]);       // indirect call via table
}
```
> **§** 2.15 (visible function table), 5.1.4 (visible), 5.1.5 (stitchable), 1.5.4 (function pointers since Metal 2.3) · **stage** compute · **Apple9** indirect-call ABI (link register / call/return, argument passing, stack setup) — needed for ray-tracing intersection functions too · **provokes** call/return, indirect branch, stack frame setup

## A12. Memory: device / constant / threadgroup loads & stores

```metal
kernel void mem(device float4 *g [[buffer(0)]],          // device (RW)
                constant float4 *c [[buffer(1)]],        // constant (RO, uniform)
                threadgroup float *tg [[threadgroup(0)]],
                uint i [[thread_position_in_grid]],
                uint li [[thread_position_in_threadgroup]]) {
    tg[li] = g[i].x + c[i & 15].y;                       // device+constant load, tg store
    threadgroup_barrier(mem_flags::mem_threadgroup);
    g[i] = float4(tg[li ^ 1]);                           // tg load, device store (vectorized)
}
```
> **§** 4.1–4.4 (address spaces), 4.8 (coherency, `coherent(device)`) · **stage** compute · **Apple9** contrast: `device` load/store already seen as the 14-byte `0x67/0xe7` group (EXP-0005); `constant` likely a uniform/preamble path; alignment/vectorization (float vs float4) changes access width — sweep vector width; Dynamic Caching affects threadgroup-memory backing · **provokes** device load/store, constant/uniform fetch, threadgroup load/store, barrier/fence

## A13. Stack / scratch spills

```metal
kernel void spill(device int *a, device int *o, uint i [[thread_position_in_grid]]) {
    int big[64];                                   // large private array -> forces stack/scratch
    for (int k = 0; k < 64; ++k) big[k] = a[i] * k;
    int s = 0;
    for (int k = 0; k < 64; ++k) s += big[(a[i] + k) & 63];  // dynamic index defeats reg-promotion
    o[i] = s;
}
```
> **§** 4.3 (thread address space) · **stage** compute · **Apple9** **Dynamic Caching** specifically changes how private/register overflow is backed (dynamic shader-core memory, WWDC Apple9 §1.1) — spill address computation and any occupancy metadata are A18-specific and worth close study · **provokes** stack-frame allocation, scratch load/store, spill/fill

## A14. Atomics — device & threadgroup, all ops, int & float

```metal
kernel void atomics(device atomic_int *di [[buffer(0)]],
                    device atomic_uint *du [[buffer(1)]],
                    device atomic_float *df [[buffer(2)]],
                    device atomic_ulong *dl [[buffer(3)]],
                    threadgroup atomic_int *ti [[threadgroup(0)]],
                    uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(di, 1, memory_order_relaxed);       // add (int)
    atomic_fetch_min_explicit(du, i, memory_order_relaxed);       // min/max/and/or/xor/sub: same shape
    atomic_fetch_or_explicit (du, 0xF, memory_order_relaxed);
    atomic_fetch_add_explicit(df, 1.0f, memory_order_relaxed);    // float add (device only, §6.15.4.5)
    atomic_max_explicit      (dl, ulong(i), memory_order_relaxed);// 64-bit modify (§6.15.4.6, void)
    int e = 0;
    atomic_compare_exchange_weak_explicit(ti, &e, 5,             // cmpxchg (threadgroup)
        memory_order_relaxed, memory_order_relaxed);
    atomic_exchange_explicit(ti, 7, memory_order_relaxed);        // exchange
    atomic_store_explicit(ti, 0, memory_order_relaxed);           // store; also atomic_load
}
```
> **§** 6.15 (Table 6.25 ops: add/and/max/min/or/sub/xor; 6.15.4.6 64-bit min/max; float add device-only) · **stage** compute (also valid in fragment) · **Apple9** float atomics + 64-bit atomics are the interesting deltas vs older families; device vs threadgroup scope should select different encodings; the `_explicit` memory_order argument may map to fence bits · **provokes** atomic RMW (all ops), atomic cmpxchg/exchange/load/store, 64-bit atomic, atomic fence

## A15. Textures — sample / read / write / gather / depth-compare / queries

```metal
kernel void tex(texture2d<float, access::sample>      t2  [[texture(0)]],
                texture2d<float, access::read_write>  trw [[texture(1)]],
                texture3d<float>                      t3  [[texture(2)]],
                texturecube<float>                    tc  [[texture(3)]],
                texture2d_array<float>                ta  [[texture(4)]],
                depth2d<float>                        td  [[texture(5)]],
                texture2d_ms<float>                   tms [[texture(6)]],
                sampler s [[sampler(0)]],
                device float4 *o [[buffer(0)]],
                uint2 gid [[thread_position_in_grid]]) {
    float2 uv = float2(gid) / 64.0;
    float4 c = t2.sample(s, uv);                       // plain sample
    c += t2.sample(s, uv, bias(1.0));                  // LOD bias
    c += t2.sample(s, uv, level(2.0));                 // explicit LOD
    c += t2.sample(s, uv, gradient2d(float2(1,0), float2(0,1)));  // explicit gradients
    c += t2.gather(s, uv, int2(0), component::x);      // gather (2x2)
    c += t3.sample(s, float3(uv, 0.5)) + tc.sample(s, float3(uv,1))
       + ta.sample(s, uv, 0);                          // 3D / cube / array
    float d = td.sample_compare(s, uv, 0.5);           // depth compare (PCF)
    float4 r = trw.read(gid); trw.write(r + 1, gid);   // read_write access
    float4 m = tms.read(gid, 0);                       // MSAA sample-indexed read
    uint w = t2.get_width(); uint L = t2.get_num_mip_levels();  // queries
    o[gid.x] = c + d + m + float(w + L);
}
```
> **§** 6.12 (all texture funcs; 6.12.3 2D sample/gather/read/write/queries; 6.12.10 depth `sample_compare`/`gather_compare`; 6.12.8 MSAA), 8.7 (format conversion) · **stage** compute for sample/read/write/gather; **implicit-LOD `sample` without `level`/`gradient` needs a fragment stage** (LOD from derivatives) · **Apple9** texture ops carry a sampler+format conversion; `access::read_write` + `mem_texture` fence, cube/3D/array addressing, and `get_*` queries each likely distinct; texture atomics (Metal 3.1+, cube in Metal 4) are a separate sub-family · **provokes** texture sample (bias/LOD/grad), gather, image read/write, depth-compare (PCF), MSAA read, texture-info queries

## A16. Samplers (address / filter / compare / border / anisotropy / LOD clamp)

```metal
constexpr sampler s_wrap (address::repeat,       filter::linear, mip_filter::linear);
constexpr sampler s_edge (address::clamp_to_edge, mag_filter::nearest, min_filter::linear);
constexpr sampler s_bord (address::clamp_to_border, border_color::opaque_white);
constexpr sampler s_cmp  (compare_func::less);                 // depth compare sampler
constexpr sampler s_aniso(filter::linear, max_anisotropy(16), lod_clamp(0.0, 4.0));
kernel void samplers(texture2d<float> t [[texture(0)]], depth2d<float> td [[texture(1)]],
                     device float4 *o [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    float2 uv = float2(g)/64.0;
    o[g.x] = t.sample(s_wrap, uv) + t.sample(s_edge, uv) + t.sample(s_bord, uv)
           + t.sample(s_aniso, uv) + td.sample_compare(s_cmp, uv, 0.5);
}
```
> **§** 2.10 (Table 2.7 sampler state; `max_anisotropy`, `lod_clamp`; border colors macOS 1.2+) · **stage** compute (with explicit LOD) · **Apple9** *program-source* `constexpr sampler` state is **compiled into the shader/descriptor**, not the AGX ALU stream — so this row primarily provokes **sampler-descriptor bits** (cross-reference `docs/descriptors/`); border color and anisotropy are Vulkan-relevant knobs to confirm exist · **provokes** (mostly descriptor) sampler addressing/filter/compare/border/aniso/LOD-clamp fields

## A17. Interpolation qualifiers & pull-model interpolation

```metal
struct VOut {
    float4 pos                                  [[position]];
    float4 smooth_c    [[center_perspective]];   // default perspective-correct
    float4 flat_c      [[flat]];                 // no interpolation (provoking vertex)
    float4 nop_c       [[center_no_perspective]];
    float4 centroid_c  [[centroid_perspective]];
    float4 sample_c    [[sample_perspective]];   // per-sample -> forces sample-rate shading
    interpolant<float4, interpolation::perspective> pull;   // pull-model (§2.18, §6.11)
};
fragment float4 frag(VOut in [[stage_in]]) {
    float4 a = in.smooth_c + in.flat_c + in.nop_c + in.centroid_c + in.sample_c;
    a += in.pull.interpolate_at_center()  + in.pull.interpolate_at_centroid()
       + in.pull.interpolate_at_sample(0) + in.pull.interpolate_at_offset(float2(0.25));
    return a;
}
```
> **§** 5.4 (sampling/interpolation attrs), 2.18 (`interpolant`), 6.11 (Table 6.22 pull-model) · **stage** **fragment (+ paired vertex)** — requires the fragment extractor · **Apple9** interpolation on Apple TBDR is done in the shader (no fixed-function varying unit) → these should emit real interpolation instructions reading per-vertex/coefficient data; `flat` selects provoking-vertex behavior; pull-model `interpolate_at_*` is directly Vulkan-relevant · **provokes** varying interpolation (perspective/no-persp/flat/centroid/sample), pull-model interpolate-at

## A18. Derivatives & fwidth

```metal
fragment float4 deriv(float2 uv [[stage_in]], texture2d<float> t [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    float2 dx = dfdx(uv), dy = dfdy(uv);
    float  w  = fwidth(uv).x;
    return t.sample(s, uv) + float4(dx, dy) + w;   // implicit-LOD sample also needs derivatives
}
```
> **§** 6.10.1.1 (Table 6.19 `dfdx`/`dfdy`/`fwidth`; derivatives undefined in nonuniform CF) · **stage** **fragment only** (quad-based helper lanes) · **Apple9** derivatives are quad-lane differences → tightly coupled to quad/SIMD permute hardware (see A20); implicit-LOD `sample` internally computes these · **provokes** quad-difference (dfdx/dfdy), fwidth

## A19. Barycentrics (fragment built-in)

```metal
fragment float4 bary(float3 bc [[barycentric_coord]],
                     uint prim  [[primitive_id]]) {
    return float4(bc, float(prim));
}
```
> **§** 5.2.3.4 (`barycentric_coord`, `primitive_id` fragment inputs) · **stage** **fragment** · **Apple9** exposes raw barycentric access (used to hand-interpolate); pairs with mesh/primitive-shader output (Part B) · **provokes** barycentric-coordinate built-in read

## A20. Subgroup / SIMD-group ops (broadcast, shuffle, reduce, prefix, ballot, vote)

```metal
kernel void simdops(device int *a [[buffer(0)]], device int *o [[buffer(1)]],
                    uint i    [[thread_position_in_grid]],
                    uint lane [[thread_index_in_simdgroup]]) {
    int v = a[i];
    int r = simd_broadcast(v, 0) + simd_broadcast_first(v);           // broadcast
    r += simd_shuffle(v, lane ^ 1) + simd_shuffle_xor(v, 1)           // shuffle / butterfly
       + simd_shuffle_up(v, 1) + simd_shuffle_down(v, 1)
       + simd_shuffle_rotate_up(v, 1) + simd_shuffle_rotate_down(v, 1);
    r += simd_sum(v) + simd_product(v) + simd_min(v) + simd_max(v)    // reductions
       + simd_and(v) + simd_or(v) + simd_xor(v);
    r += simd_prefix_inclusive_sum(v) + simd_prefix_exclusive_sum(v); // scans
    simd_vote ballot = simd_ballot(v > 0);                            // ballot / vote
    r += int((uint64_t)ballot) + (simd_all(v > 0) ? 1 : 0)
       + (simd_any(v > 0) ? 2 : 0) + (simd_is_first() ? 4 : 0);
    o[i] = r;
}
```
> **§** 6.9.2 (Table 6.14 permute: broadcast/shuffle/±up/down/xor/rotate + fill; Table 6.15 reduce/scan: sum/product/min/max/and/or/xor/prefix; `simd_ballot`/`simd_vote`/`simd_all`/`simd_any`/`simd_is_first`) · **stage** compute (also fragment; `simd_is_helper_thread` fragment-only) · **Apple9** the whole cross-lane permute network — directly maps Vulkan subgroup ops; the `_and_fill_up/down` + `modulo` variants and `simd_ballot` (64-bit mask, top bits UB below 64-wide) are worth confirming; SIMD width is Apple9-specific (probe `threads_per_simdgroup`) · **provokes** cross-lane shuffle/broadcast, SIMD reduce/scan, ballot/vote, elect

## A21. Quad-group ops

```metal
kernel void quadops(device int *a, device int *o,
                    uint i [[thread_position_in_grid]],
                    uint q [[thread_index_in_quadgroup]]) {
    int v = a[i];
    o[i] = quad_broadcast(v, 0) + quad_shuffle(v, q ^ 1) + quad_shuffle_xor(v, 1)
         + quad_shuffle_up(v, 1) + quad_shuffle_down(v, 1)
         + quad_sum(v) + quad_max(v) + quad_min(v) + quad_and(v) + quad_or(v);
}
```
> **§** 6.9.3 (quad-group funcs — SIMD funcs at execution width 4) · **stage** compute (and fragment; the same 2×2 quad backs derivatives, A18) · **Apple9** quad ops are the hardware substrate for `dfdx`/`dfdy` and 2×2 helper lanes on TBDR — expect them to share encoding with A20 permutes at width 4 · **provokes** quad shuffle/broadcast/reduce

---
---

# Part B — Apple9-new families (the documentation gap — Mesa has zero code for these)

> These are the highest-value, most-uncertain targets. Apple's public WWDC material confirms Apple
> family 9 adds **hardware-accelerated ray tracing** (dedicated intersector + a "reorder stage") and
> **hardware-accelerated mesh shading**; whether `simdgroup_matrix` / Metal-Performance-Primitives
> tensor ops lower to a **dedicated matrix instruction** or to a shuffle+FMA sequence is an **open
> empirical question** this effort must answer by diffing. For every row here, the key experiment is:
> does the AGX stream contain a *new opcode group* (unknown to our tokenizer), or does it lower to
> known ALU/permute ops? A new group = a new instruction family to document.

## B1. Ray tracing — intersector object API (preferred on Apple9)

```metal
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
kernel void trace(primitive_acceleration_structure accel [[buffer(0)]],
                  device float *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(0, 0, 0);
    r.direction = normalize(float3(float(i) * 0.01, 0, 1));
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;              // <-- the intersector object
    isect.assume_geometry_type(geometry_type::triangle);
    intersection_result<triangle_data> res = isect.intersect(r, accel);
    o[i] = (res.type == intersection_type::triangle)
         ? res.distance : -1.0f;                    // read barycentrics via res too
}
```
> **§** 2.17.6 (intersector), 6.18.2 (intersect funcs & Table 6.28 params), 2.17.4 (result) · **stage** compute (also fragment/vertex) · **Apple9** WWDC confirms rays go to a **hardware intersector** with a reorder stage — expect a dedicated trace/intersect instruction and acceleration-structure address handling; **most novel family here.** `intersector<>` with no tags = simplest provocation; add `instancing`, `world_space_data`, `primitive_motion`/`instance_motion` (motion blur) and `max_levels<N>` incrementally · **provokes** hardware ray-intersect, accel-structure traversal, intersector setup

## B2. Ray tracing — intersection query (`ray_query`-style, inline)

```metal
kernel void rayquery(primitive_acceleration_structure accel [[buffer(0)]],
                     device float *o [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin = 0; r.direction = float3(0,0,1); r.min_distance = 0; r.max_distance = INFINITY;
    intersection_query<triangle_data> q;
    q.reset(r, accel);
    while (q.next()) {                                       // inline traversal loop
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    }
    o[i] = (q.get_committed_intersection_type() == intersection_type::triangle)
         ? q.get_committed_distance() : -1.0f;
}
```
> **§** 2.17.8 (intersection query type), 6.18.5 (Table 6.30 query funcs: `next`/`commit_*`/`get_candidate_*`/`get_committed_*`) · **stage** compute · **Apple9** the Vulkan `rayQuery` analog — inline traversal driven by shader control flow rather than the reorder stage; WWDC advises the intersector API over this on Apple9, so contrast the two lowerings · **provokes** inline accel-traversal step (`next`), candidate/commit bookkeeping

## B3. Ray tracing — custom intersection functions & payload

```metal
struct BBoxResult {
    bool  accept          [[accept_intersection]];
    bool  continueSearch  [[continue_search]];
    float distance        [[distance]];
};
[[intersection(bounding_box)]]
BBoxResult sphereIsect(float3 origin          [[origin]],
                       float3 direction       [[direction]],
                       uint   primIndex       [[primitive_id]],
                       float  minD            [[min_distance]],
                       float  maxD            [[max_distance]],
                       ray_data float2 &payload [[payload]]) {   // ray_data address space
    float t = minD + 0.5f * (maxD - minD);
    payload += 1.0f;
    return { true, false, t };
}
```
> **§** 5.1.6 (intersection functions), 5.2.3.7 (input attrs), 4.6 (`ray_data` address space), 2.17.1 (intersection tags) · **stage** intersection function (invoked from B1/B2; own Mach-O linkage) · **Apple9** the reorder stage groups these calls across SIMD-groups — the call/return ABI + `ray_data` payload copy-in/out is A18-specific; keep payload minimal (WWDC best practice) · **provokes** intersection-function call convention, `ray_data` payload load/store, accept/reject/continue result encoding

## B4. Mesh & object shaders (the mesh pipeline)

```metal
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;
struct VOut { float4 position [[position]]; float3 color; };
struct POut { float3 normal [[flat]]; };
using tri_mesh = mesh<VOut, POut, 3, 1, topology::triangle>;

struct Payload { float scale; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_stage(object_data Payload &pl [[payload]],
               mesh_grid_properties mgp,
               uint tid [[thread_position_in_grid]]) {
    pl.scale = 1.0f + float(tid);
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));      // launch one mesh threadgroup
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_stage(tri_mesh out,
                const object_data Payload &pl [[payload]],
                uint lane [[thread_index_in_threadgroup]]) {
    out.set_primitive_count(1);
    VOut v; v.position = float4(float(lane) * pl.scale, 0, 0, 1); v.color = float3(1);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.normal = float3(0,0,1); out.set_primitive(0, p); }
}
```
> **§** 2.20 (mesh types), 5.1.7 (object funcs), 5.1.8 (mesh funcs), 4.7 (`object_data`), 2.20.1 (`mesh_grid_properties`) · **stage** **object + mesh** (needs those extractors) · **Apple9** WWDC confirms **hardware-accelerated mesh shading** — two compute-like stages with an amplifying grid launch (`set_threadgroups_per_grid`) and a payload in `object_data`; the mesh-output `set_vertex/set_primitive/set_index/set_primitive_count` writes into a HW mesh-output buffer whose layout is A18-specific · **provokes** object→mesh grid dispatch, `object_data` payload, mesh vertex/primitive/index export

## B5. `simdgroup_matrix` — cooperative matrix multiply

```metal
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
kernel void matmad(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                   device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A);                 // load 8x8 tile from device memory
    simdgroup_load(b, B);
    simdgroup_load(c, C);
    simdgroup_multiply_accumulate(r, a, b, c);   // r = a*b + c
    simdgroup_store(r, R);
    // also: simdgroup_multiply(r,a,b);  make_filled_simdgroup_matrix(1.0f);  half8x8 variant
}
```
> **§** 6.7 (Table 6.9 load/store, Table 6.10 `simdgroup_multiply(_accumulate)`) · **stage** compute (SIMD-group-cooperative) · **Apple9** **open question:** does A18 have a dedicated matrix/MAC-array instruction, or does this lower to a shuffle+FMA sequence? Diff `simdgroup_multiply_accumulate` output against a hand-written FMA loop — a new opcode group ⇒ documented matrix unit; also compare `float8x8` vs `half8x8` and the `transpose_matrix`/`elements_per_row` load variants · **provokes** cooperative matrix load/store + multiply-accumulate (candidate matrix unit)

## B6. Metal Performance Primitives — tensor ops (`matmul2d`, cooperative tensor)

```metal
#include <metal_stdlib>
#include <MetalPerformancePrimitives/MetalPerformancePrimitives.h>
using namespace metal;
using namespace mpp;
// Minimal generalized matmul C = A*B over device tensors, cooperative over the simdgroup.
kernel void mpp_matmul(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                       tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                       tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(/*M*/32, /*N*/32, /*K*/32,
                                    /*transpose_left*/false, /*transpose_right*/false,
                                    /*relaxed_precision*/false, mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}
```
> **§** 2.21 (tensor types), 2.21.3 (cooperative tensor), 7.1 (execution scopes), 7.2.1 (`matmul2d`, Table 7.3/7.4 dtype combos) · **stage** compute · **Apple9** **newest surface (Metal 4 / "new in Metal 3.2" tensors, §1.3, §9.1)** — even less certain than B5. Whether `matmul2d` maps to the same primitive as `simdgroup_matrix` or a distinct tensor path is unknown; the char/half/float/bfloat dtype matrix (Table 7.3/7.4) is a good sweep. Header/namespace spelling (`MetalPerformancePrimitives`, `mpp::`) should be verified at compile time before committing to it · **provokes** tensor matmul/convolution (candidate tensor/matrix unit) — *most uncertain to provoke; confirm it compiles on-device first*

## B7. Imageblocks & tile shaders (TBDR tile memory)

```metal
#include <metal_stdlib>
using namespace metal;
struct GBuffer {                          // an explicit imageblock layout
    half4 albedo  [[color(0)]];
    half4 normal  [[color(1)]];
    float depth   [[color(2)]];
};
// Fragment writing into the tile's imageblock:
fragment GBuffer gbuf_write(float2 uv [[stage_in]]) {
    GBuffer g; g.albedo = half4(uv, 0, 1); g.normal = half4(0,0,1,0); g.depth = uv.x;
    return g;
}
// Tile (fragment-based compute) shader reading the whole imageblock and resolving:
kernel void tile_resolve(imageblock<GBuffer, imageblock_layout_explicit> blk,
                         texture2d<half, access::write> outTex [[texture(0)]],
                         ushort2 lid [[thread_position_in_threadgroup]],
                         ushort2 gid [[thread_position_in_grid]]) {
    threadgroup_GBuffer<GBuffer>* px = blk.data(lid);   // read tile-local storage
    outTex.write(px->albedo, gid);
}
```
> **§** 2.11 (imageblocks), 5.1.9 (tile functions), 5.6 (imageblock attrs / explicit+implicit layout), 6.13 (imageblock funcs), 4.5 (`threadgroup_imageblock`) · **stage** **fragment + tile** (kernel-style tile function in a render pass) · **Apple9** tile shaders read/write **32 KB on-chip tile memory** shared between imageblock + threadgroup storage; the imageblock slice addressing and `[[color(n)]]` slot layout are core TBDR facts (cross-ref `docs/pipeline/`, `docs/tiling/`); Dynamic Caching interacts with the threadgroup/imageblock split · **provokes** imageblock slice load/store, tile-memory addressing, tile-dispatch

## B8. Programmable blending & raster order groups

```metal
// Programmable blending: read the current color attachment as a fragment INPUT, blend in-shader.
struct InColor { half4 dst [[color(0)]]; };            // <-- reads existing framebuffer value
fragment half4 prog_blend(InColor in [[stage_in]]) {
    half4 src = half4(1, 0, 0, 0.5);
    return src * src.a + in.dst * (1 - src.a);          // custom (non-fixed-function) blend
}
// Raster order group: ordered RMW on an overlapping pixel from a read_write texture.
fragment void rog(texture2d<float, access::read_write> tex
                      [[raster_order_group(0), texture(0)]],
                  float4 pos [[position]]) {
    ushort2 c = ushort2(pos.xy);
    float4 v = tex.read(c);                              // ordered w.r.t. overlapping fragments
    tex.write(v + 1.0f, c);
}
```
> **§** 5.2.3.4 (`[[color(m)]]` fragment input = read attachment), 5.2.1.2 (`[[raster_order_group]]`), 5.2.3.5 (`[[color(m)]]`/`index(i)` outputs, dual-source blend) · **stage** **fragment** · **Apple9** on TBDR, programmable blending reads the color attachment straight from **tile memory** (no fixed-function blend needed) — reading `[[color(m)]]` input is the provocation; raster-order-group adds an ordering/serialization primitive for overlapping fragments (Vulkan `FRAGMENT_SHADER_INTERLOCK` analog). `index(i)` on the output provokes **dual-source blending**. High Vulkan relevance · **provokes** color-attachment (tile) read, fragment-ordering barrier, dual-source blend output

---

## Coverage summary & open provocation risks

**Compute-extractable today** (works with current `shdump`): A1–A16 (except implicit-LOD sampling),
A20, A21, B1, B2, B3, B5, B6, B7 (the tile-*kernel* half).

**Require a non-compute stage** (blocked on extending `shdump`/`agxparse` to `__vertex`/`__fragment`/
mesh/object sections):
- **Fragment:** A17 (interpolation/pull-model), A18 (derivatives), A19 (barycentrics), B7 (fragment
  imageblock write), B8 (programmable blending, raster order groups). Also *implicit-LOD* `sample`
  (A15) needs a fragment stage to have derivatives.
- **Object + Mesh:** B4.
- **Intersection function linkage:** B3 (compiles from a compute launcher, but the intersection
  function is its own linked stage).

**Most novel / most uncertain to provoke (prioritize):**
1. **B1/B2/B3 hardware ray tracing** — WWDC-confirmed dedicated intersector; entirely new opcode
   territory, and the acceleration-structure + `ray_data` handling has no analog in Mesa's G13/G14.
2. **B6 MPP tensor ops** — newest MSL surface; **header/namespace spelling and on-device availability
   must be confirmed by a trial compile before relying on it** (flagged inline). Could fail to compile
   on the installed toolchain.
3. **B5 `simdgroup_matrix`** — genuinely unknown whether it is a matrix instruction or an FMA/shuffle
   expansion; the diff-vs-handwritten-FMA experiment is the deciding test.
4. **B4 mesh/object** — hardware-accelerated per WWDC, but the mesh-output buffer layout and grid
   amplification encoding are unknown.

**Families where a clean single-instruction MSL trigger is *not* guaranteed from the public docs
(expect multi-instruction lowerings, so diff carefully):** transcendentals (A5) and reciprocal/rsqrt
(A4) — range reduction + refinement; bitfield ops (A9) — some may expand; A16 samplers and parts of
B8 are **descriptor/state**, not ALU, so they will show up in `docs/descriptors/`/`docs/pipeline/`
rather than the AGX ALU stream. B6's exact MSL spelling is the only row not fully pinned by the spec
text (constructor/`run` surface summarized from §7.2.1) and should be treated as provisional until it
compiles on the device.

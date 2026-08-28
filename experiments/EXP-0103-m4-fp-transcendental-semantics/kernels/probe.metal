// EXP-0103 -- authored MSL probe kernels.
// One uniform record shape in and out (four uint32 slots each) so a single
// generic ObjC harness (harness/probe.m) can dispatch any named kernel
// without per-op special-casing. Every kernel here is OUR OWN source,
// compiled at runtime via newLibraryWithSource: (OWN-SHADER). fast::/
// precise:: are public MSL namespaces (Metal Shading Language Specification)
// selecting the approximate vs IEEE-conformant lowering of the same
// mathematical function; nothing here inspects Apple's implementation.
//
// Compile options are fixed by the harness: fastMathEnabled = NO,
// mathMode = MTLMathModeSafe (identical to EXP-0074), EXCEPT the single
// FP-07 case (k_rcp_precise_f32 recompiled under fastMathEnabled = YES by
// the harness's --fastmath flag) which asks whether the GLOBAL compile mode
// changes precise-namespace behavior.

using namespace metal;

struct Rec { uint r0; uint r1; uint r2; uint r3; };

inline float bf32(uint b) { return as_type<float>(b); }
inline uint fb32(float f) { return as_type<uint>(f); }
inline half bf16(uint b) { return as_type<half>(ushort(b & 0xFFFFu)); }
inline uint fb16(half h) { return uint(as_type<ushort>(h)); }
inline half2 bf16x2(uint lo, uint hi) {
    return half2(as_type<half>(ushort(lo & 0xFFFFu)), as_type<half>(ushort(hi & 0xFFFFu)));
}
inline uint pack_h2(half2 v) {
    return uint(as_type<ushort>(v.x)) | (uint(as_type<ushort>(v.y)) << 16);
}
inline half2 unpack_h2(uint x) {
    return half2(as_type<half>(ushort(x & 0xFFFFu)), as_type<half>(ushort((x >> 16) & 0xFFFFu)));
}

// ---------------------------------------------------------------- SFU f32 --

#define SFU_F32(NAME, EXPR) \
kernel void k_##NAME##_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]], \
                            uint id [[thread_position_in_grid]]) { \
    float x = bf32(in[id].r0); \
    out[id].r0 = fb32(EXPR); \
}

SFU_F32(rcp_fast,     fast::divide(1.0f, x))
SFU_F32(rcp_precise,  precise::divide(1.0f, x))
SFU_F32(rsqrt_fast,   fast::rsqrt(x))
SFU_F32(rsqrt_precise,precise::rsqrt(x))
SFU_F32(sqrt_fast,    fast::sqrt(x))
SFU_F32(sqrt_precise, precise::sqrt(x))
SFU_F32(exp2_fast,    fast::exp2(x))
SFU_F32(exp2_precise, precise::exp2(x))
SFU_F32(log2_fast,    fast::log2(x))
SFU_F32(log2_precise, precise::log2(x))
SFU_F32(sin_fast,     fast::sin(x))
SFU_F32(sin_precise,  precise::sin(x))
SFU_F32(cos_fast,     fast::cos(x))
SFU_F32(cos_precise,  precise::cos(x))

#undef SFU_F32

// ---------------------------------------------------------------- SFU f16 --

#define SFU_F16(NAME, EXPR) \
kernel void k_##NAME##_f16(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]], \
                            uint id [[thread_position_in_grid]]) { \
    half x = bf16(in[id].r0); \
    out[id].r0 = fb16(EXPR); \
}

SFU_F16(rcp_fast,     fast::divide(half(1.0h), x))
SFU_F16(rcp_precise,  precise::divide(half(1.0h), x))
SFU_F16(rsqrt_fast,   fast::rsqrt(x))
SFU_F16(rsqrt_precise,precise::rsqrt(x))
SFU_F16(sqrt_fast,    fast::sqrt(x))
SFU_F16(sqrt_precise, precise::sqrt(x))
SFU_F16(exp2_fast,    fast::exp2(x))
SFU_F16(log2_fast,    fast::log2(x))
SFU_F16(sin_fast,     fast::sin(x))
SFU_F16(cos_fast,     fast::cos(x))

#undef SFU_F16

// ------------------------------------------------------- rounding family --

kernel void k_round_family_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                                uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = fb32(floor(x));
    out[id].r1 = fb32(ceil(x));
    out[id].r2 = fb32(trunc(x));
    out[id].r3 = fb32(round(x));
}

// ------------------------------------------------------------------ fma ---

kernel void k_fma_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                       uint id [[thread_position_in_grid]]) {
    float a = bf32(in[id].r0), b = bf32(in[id].r1), c = bf32(in[id].r2);
    out[id].r0 = fb32(fma(a, b, c));
}

kernel void k_fma_f16(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                       uint id [[thread_position_in_grid]]) {
    half a = bf16(in[id].r0), b = bf16(in[id].r1), c = bf16(in[id].r2);
    out[id].r0 = fb16(fma(a, b, c));
}

kernel void k_fma_f16x2(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                         uint id [[thread_position_in_grid]]) {
    half2 a = unpack_h2(in[id].r0), b = unpack_h2(in[id].r1), c = unpack_h2(in[id].r2);
    out[id].r0 = pack_h2(fma(a, b, c));
}

// ----------------------------------------------------------- add/sub/mul/div

kernel void k_add_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                       uint id [[thread_position_in_grid]]) {
    out[id].r0 = fb32(bf32(in[id].r0) + bf32(in[id].r1));
}
kernel void k_sub_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                       uint id [[thread_position_in_grid]]) {
    out[id].r0 = fb32(bf32(in[id].r0) - bf32(in[id].r1));
}
kernel void k_mul_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                       uint id [[thread_position_in_grid]]) {
    out[id].r0 = fb32(bf32(in[id].r0) * bf32(in[id].r1));
}
kernel void k_div_precise_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                               uint id [[thread_position_in_grid]]) {
    out[id].r0 = fb32(precise::divide(bf32(in[id].r0), bf32(in[id].r1)));
}
// SFU-06: a * precise::recip(b) vs precise::divide(a,b) -- same kernel emits
// BOTH so the comparison is bit-exact from the SAME dispatch / same inputs.
kernel void k_div_vs_rcp_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                              uint id [[thread_position_in_grid]]) {
    float a = bf32(in[id].r0), b = bf32(in[id].r1);
    out[id].r0 = fb32(precise::divide(a, b));
    out[id].r1 = fb32(a * precise::divide(1.0f, b));
}
// SFU-05: precise::sqrt(x) vs x * precise::rsqrt(x).
kernel void k_sqrt_vs_rsqrt_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                                 uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = fb32(precise::sqrt(x));
    out[id].r1 = fb32(x * precise::rsqrt(x));
}

// packed/scalar fp16 add+mul (subnormal preservation, FP-08)
kernel void k_addmul_f16(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                          uint id [[thread_position_in_grid]]) {
    half a = bf16(in[id].r0), b = bf16(in[id].r1);
    out[id].r0 = fb16(a + b);
    out[id].r1 = fb16(a * b);
}
kernel void k_addmul_f16x2(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                            uint id [[thread_position_in_grid]]) {
    half2 a = unpack_h2(in[id].r0), b = unpack_h2(in[id].r1);
    out[id].r0 = pack_h2(a + b);
    out[id].r1 = pack_h2(a * b);
}

// ------------------------------------------------------------- min / max --

kernel void k_minmax_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                          uint id [[thread_position_in_grid]]) {
    float a = bf32(in[id].r0), b = bf32(in[id].r1);
    out[id].r0 = fb32(fmin(a, b));
    out[id].r1 = fb32(fmax(a, b));
}

// -------------------------------------------------------------- saturate --

kernel void k_saturate_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                            uint id [[thread_position_in_grid]]) {
    out[id].r0 = fb32(saturate(bf32(in[id].r0)));
}

// ------------------------------------------------------- f32 -> f16 round --

kernel void k_f32_to_f16(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                          uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = fb16(half(x));
}

// fquantize2f16 emulation: narrow then widen (FP-13)
kernel void k_fquantize_f16(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                             uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = fb32(float(half(x)));
}

// -------------------------------------------------------- f32 -> int trunc

kernel void k_f32_to_int(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                          uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = as_type<uint>(int(x));
    out[id].r1 = uint(x);
    out[id].r2 = as_type<uint>(int(char(x)));
    out[id].r3 = uint(uchar(x));
}

// -------------------------------------------------------------- comparisons

kernel void k_compare_nan_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                               uint id [[thread_position_in_grid]]) {
    float a = bf32(in[id].r0), b = bf32(in[id].r1);
    uint bits = 0;
    bits |= (a <  b) ? 1u : 0u;
    bits |= (a >  b) ? 2u : 0u;
    bits |= (a == b) ? 4u : 0u;
    bits |= (a != b) ? 8u : 0u;
    bits |= (a <= b) ? 16u : 0u;
    bits |= (a >= b) ? 32u : 0u;
    bits |= isnan(a) ? 64u : 0u;
    bits |= isnan(b) ? 128u : 0u;
    out[id].r0 = bits;
}

// --------------------------------------------------- sin/cos shared reduce

// Same SSA input x feeds both sin and cos (TRIG-03/04 numeric half; the
// instruction-count / shared-reduction structural question is answered by
// disassembly in analysis/structural_probe.py, not by this kernel's output).
kernel void k_sincos_shared_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                                 uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = fb32(fast::sin(x));
    out[id].r1 = fb32(fast::cos(x));
}
// Independent inputs (x for sin, y for cos) -- no sharing possible even if
// the hardware/compiler *can* share.
kernel void k_sincos_independent_f32(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                                      uint id [[thread_position_in_grid]]) {
    out[id].r0 = fb32(fast::sin(bf32(in[id].r0)));
    out[id].r1 = fb32(fast::cos(bf32(in[id].r1)));
}

// FP-12 structural probe pair: naive convert vs clamp-then-convert (disasm
// instruction count comparison lives in analysis/structural_probe.py).
kernel void k_f32_to_int8_plain(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                                 uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    out[id].r0 = as_type<uint>(int(char(x)));
}
kernel void k_f32_to_int8_sat(constant Rec* in [[buffer(0)]], device Rec* out [[buffer(1)]],
                               uint id [[thread_position_in_grid]]) {
    float x = bf32(in[id].r0);
    float c = clamp(x, -128.0f, 127.0f);
    out[id].r0 = as_type<uint>(int(char(c)));
}

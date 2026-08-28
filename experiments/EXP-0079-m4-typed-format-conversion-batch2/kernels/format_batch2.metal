#include <metal_stdlib>
using namespace metal;

// EXP-0079 authored store kernels: one per frozen case (case matrix, inputs,
// and reader kernels adopted from the EXP-0075 registration -- itself
// verified clean on real hardware for run01 before its successor gate proved
// unreachable, see ../QUARANTINE.md of EXP-0075). Each writes authored
// constants to the sole (0,0) texel of a 1x1 write-access texture. Unused
// trailing components are authored 0.0/0u; for the alpha-less packed formats
// (RG11B10Float, RGB9E5Float) the authored alpha is preregistered as ignored.
//
// MID literal 0.4999999701976776123046875 = 0.5 - 2^-25 (exact fp32
// 0x3EFFFFFF, not representable in fp16/fp11/fp10, inside the round-to-0.5
// zone of all three under round-to-nearest-even).
//
// EXP-0079 adds three cases versus EXP-0075 (see PRE_REGISTRATION.md):
//   s_r8unorm_sep_a / s_r8unorm_sep_b -- half-even vs half-up separators
//   s_r16float_pos_trunc              -- positive-direction fp16 tie probe
// All 34 EXP-0075 store-kernel bodies are otherwise byte-identical.

kernel void s_r8unorm_p100(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8unorm_zero(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8unorm_p050(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8unorm_sep_a(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.5 / 255.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8unorm_sep_b(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(2.5 / 255.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rg8unorm_p100_p050(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0, 0.5, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rg8unorm_zero_p100(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.0, 1.0, 0.0, 0.0), uint2(0, 0)); }

kernel void s_r8snorm_p100(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8snorm_zero(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8snorm_p050(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r8snorm_m100(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(-1.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rg8snorm_p100_p050(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0, 0.5, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rg8snorm_m100_zero(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(-1.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rgba8snorm_pack(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(-1.0, 0.0, 0.5, 1.0), uint2(0, 0)); }

kernel void s_r16float_exact(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r16float_mid(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.4999999701976776123046875, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r16float_third(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0 / 3.0, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r16float_pos_trunc(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.500244140625, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rg16float_exact_mid(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.4999999701976776123046875, 0.0, 0.0), uint2(0, 0)); }
kernel void s_rg16float_third_third(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0 / 3.0, 1.0 / 3.0, 0.0, 0.0), uint2(0, 0)); }

kernel void s_r32float_exact(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r32float_mid(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.4999999701976776123046875, 0.0, 0.0, 0.0), uint2(0, 0)); }
kernel void s_r32float_third(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0 / 3.0, 0.0, 0.0, 0.0), uint2(0, 0)); }

kernel void s_rg11b10float_exact(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.5, 0.5, 1.0), uint2(0, 0)); }
kernel void s_rg11b10float_mid(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.4999999701976776123046875, 0.4999999701976776123046875, 0.4999999701976776123046875, 1.0), uint2(0, 0)); }
kernel void s_rgb9e5float_exact(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.5, 0.5, 1.0), uint2(0, 0)); }
kernel void s_rgb9e5float_mid(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.4999999701976776123046875, 0.4999999701976776123046875, 0.4999999701976776123046875, 1.0), uint2(0, 0)); }

kernel void s_r16sint_1(texture2d<int, access::write> t [[texture(0)]]) { t.write(int4(1, 0, 0, 0), uint2(0, 0)); }
kernel void s_r16sint_2(texture2d<int, access::write> t [[texture(0)]]) { t.write(int4(2, 0, 0, 0), uint2(0, 0)); }
kernel void s_r16sint_3855(texture2d<int, access::write> t [[texture(0)]]) { t.write(int4(3855, 0, 0, 0), uint2(0, 0)); }
kernel void s_r16uint_1(texture2d<uint, access::write> t [[texture(0)]]) { t.write(uint4(1u, 0u, 0u, 0u), uint2(0, 0)); }
kernel void s_r16uint_2(texture2d<uint, access::write> t [[texture(0)]]) { t.write(uint4(2u, 0u, 0u, 0u), uint2(0, 0)); }
kernel void s_r16uint_3855(texture2d<uint, access::write> t [[texture(0)]]) { t.write(uint4(3855u, 0u, 0u, 0u), uint2(0, 0)); }
kernel void s_r32sint_1(texture2d<int, access::write> t [[texture(0)]]) { t.write(int4(1, 0, 0, 0), uint2(0, 0)); }
kernel void s_r32sint_2(texture2d<int, access::write> t [[texture(0)]]) { t.write(int4(2, 0, 0, 0), uint2(0, 0)); }
kernel void s_r32sint_3855(texture2d<int, access::write> t [[texture(0)]]) { t.write(int4(3855, 0, 0, 0), uint2(0, 0)); }
kernel void s_rgba16uint_pack(texture2d<uint, access::write> t [[texture(0)]]) { t.write(uint4(1u, 2u, 3855u, 0u), uint2(0, 0)); }

// Typed read kernels: in-bounds read(uint2(0, 0)) of the sole texel, emitted
// as four little-endian uint32 words in the owned result buffer.
kernel void k_read_float(texture2d<float, access::read> t [[texture(0)]], device uint4 *out [[buffer(0)]]) {
    out[0] = as_type<uint4>(t.read(uint2(0, 0)));
}
kernel void k_read_int(texture2d<int, access::read> t [[texture(0)]], device uint4 *out [[buffer(0)]]) {
    out[0] = as_type<uint4>(t.read(uint2(0, 0)));
}
kernel void k_read_uint(texture2d<uint, access::read> t [[texture(0)]], device uint4 *out [[buffer(0)]]) {
    out[0] = t.read(uint2(0, 0));
}

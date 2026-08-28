// EXP-0144 anchor kernels -- OUR OWN MSL. Each kernel provokes exactly one of
// the nine pack/convert instructions under study so that its compiler-chosen
// encoding can be tokenized by tools/agx-isa and used as the ANCHOR byte
// string for hand-built (MODE A) programs. No Apple binary is inspected; only
// the machine code produced from this file.
#include <metal_stdlib>
using namespace metal;

// pack_convert : float2 -> packed unorm2x16
kernel void k_pack_unorm(device float* a [[buffer(1)]], device uint* o [[buffer(0)]],
                         uint t [[thread_position_in_grid]]) {
    o[t] = pack_float_to_unorm2x16(float2(a[t], a[t+1]));
}
// pack_convert : float2 -> packed snorm2x16
kernel void k_pack_snorm(device float* a [[buffer(1)]], device uint* o [[buffer(0)]],
                         uint t [[thread_position_in_grid]]) {
    o[t] = pack_float_to_snorm2x16(float2(a[t], a[t+1]));
}
// pack_convert : float4 -> packed unorm4x8
kernel void k_pack_unorm4(device float* a [[buffer(1)]], device uint* o [[buffer(0)]],
                          uint t [[thread_position_in_grid]]) {
    o[t] = pack_float_to_unorm4x8(float4(a[t], a[t+1], a[t+2], a[t+3]));
}
// unpack_convert : packed unorm2x16 -> float2
kernel void k_unpack_unorm(device uint* a [[buffer(1)]], device float* o [[buffer(0)]],
                           uint t [[thread_position_in_grid]]) {
    float2 v = unpack_unorm2x16_to_float(a[t]);
    o[t] = v.x; o[t+1] = v.y;
}
// unpack_convert : packed snorm2x16 -> float2
kernel void k_unpack_snorm(device uint* a [[buffer(1)]], device float* o [[buffer(0)]],
                           uint t [[thread_position_in_grid]]) {
    float2 v = unpack_snorm2x16_to_float(a[t]);
    o[t] = v.x; o[t+1] = v.y;
}
// cvt_i2f : int -> float
kernel void k_i2f(device int* a [[buffer(1)]], device float* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    o[t] = float(a[t]);
}
// cvt_i2f (unsigned)
kernel void k_u2f(device uint* a [[buffer(1)]], device float* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    o[t] = float(a[t]);
}
// cvt_i2f_src : two converts feeding one ALU combine
kernel void k_i2f_src(device int* a [[buffer(1)]], device float* o [[buffer(0)]],
                      uint t [[thread_position_in_grid]]) {
    o[t] = float(a[t]) + float(a[t+1]);
}
// cvt_f2i : float -> int
kernel void k_f2i(device float* a [[buffer(1)]], device int* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    o[t] = int(a[t]);
}
// cvt_f2i (unsigned)
kernel void k_f2u(device float* a [[buffer(1)]], device uint* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    o[t] = uint(a[t]);
}
// cvt_f2h / cvt_f2h_dst : float -> half
kernel void k_f2h(device float* a [[buffer(1)]], device half* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    o[t] = half(a[t]);
}
// cvt_f2h_dst multi: several converts, different dst registers
kernel void k_f2h_multi(device float* a [[buffer(1)]], device half* o [[buffer(0)]],
                        uint t [[thread_position_in_grid]]) {
    o[t] = half(a[t]); o[t+1] = half(a[t+1]); o[t+2] = half(a[t+2]); o[t+3] = half(a[t+3]);
}
// cvt_bf16 : float -> bfloat
kernel void k_f2bf(device float* a [[buffer(1)]], device bfloat* o [[buffer(0)]],
                   uint t [[thread_position_in_grid]]) {
    o[t] = bfloat(a[t]);
}
// cvt_bf16 : bfloat -> half
kernel void k_bf2h(device bfloat* a [[buffer(1)]], device half* o [[buffer(0)]],
                   uint t [[thread_position_in_grid]]) {
    o[t] = half(a[t]);
}
// cvt_bf16 : half -> bfloat
kernel void k_h2bf(device half* a [[buffer(1)]], device bfloat* o [[buffer(0)]],
                   uint t [[thread_position_in_grid]]) {
    o[t] = bfloat(a[t]);
}
// packed_half2_hi : packed 2xfp16 ALU
kernel void k_packh2(device half2* a [[buffer(1)]], device half2* o [[buffer(0)]],
                     uint t [[thread_position_in_grid]]) {
    half2 x = a[t], y = a[t+1];
    o[t] = x * y + x;
}
// --- packed_half2_hi hunt: several packed-half2 shapes ---
kernel void k_ph2_add(device half2* a [[buffer(1)]], device half2* o [[buffer(0)]],
                      uint t [[thread_position_in_grid]]) { o[t] = a[t] + a[t+1]; }
kernel void k_ph2_mul(device half2* a [[buffer(1)]], device half2* o [[buffer(0)]],
                      uint t [[thread_position_in_grid]]) { o[t] = a[t] * a[t+1]; }
kernel void k_ph2_max(device half2* a [[buffer(1)]], device half2* o [[buffer(0)]],
                      uint t [[thread_position_in_grid]]) { o[t] = max(a[t], a[t+1]); }
kernel void k_ph2_chain(device half2* a [[buffer(1)]], device half2* o [[buffer(0)]],
                        uint t [[thread_position_in_grid]]) {
    half2 x = a[t], y = a[t+1], z = a[t+2], w = a[t+3];
    o[t] = x*y; o[t+1] = z+w; o[t+2] = x*w + y; o[t+3] = z*y;
}
kernel void k_ph4(device half4* a [[buffer(1)]], device half4* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) { o[t] = a[t] * a[t+1] + a[t+2]; }

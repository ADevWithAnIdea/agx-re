// EXP-0144 sweep carriers -- OUR OWN MSL.
//
// One entry point per instruction under study. Each carrier
//   (a) contains exactly one instance of the target instruction on a LIVE
//       path to the output buffer (so a field value that changes behaviour is
//       observable),
//   (b) keeps six distinct, host-known values live in distinct registers
//       ACROSS the instruction (v0..v5 are all re-used after it), so a sweep of
//       an operand field can identify WHICH register a field value selects, and
//   (c) stores several registers afterwards, so a sweep of a destination field
//       can be seen redirecting the result into one of them.
//
// Buffer 1 = inputs, buffer 0 = outputs. Indices are thread-dependent so that
// nothing is hoisted into the uniform datapath (a constant index makes the
// compiler emit the whole body as uniform_mov + store, with no convert at all).
#include <metal_stdlib>
using namespace metal;

// ---- pack_convert : float2 -> packed unorm2x16 --------------------------
kernel void c_pack(device float* a [[buffer(1)]], device uint* o [[buffer(0)]],
                   uint t [[thread_position_in_grid]]) {
    float v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = pack_float_to_unorm2x16(float2(v0, v1));
    o[t+1] = as_type<uint>(v2); o[t+2] = as_type<uint>(v3);
    o[t+3] = as_type<uint>(v4); o[t+4] = as_type<uint>(v5);
    o[t+5] = as_type<uint>(v0); o[t+6] = as_type<uint>(v1);
}
// ---- unpack_convert : packed unorm2x16 -> float2 ------------------------
kernel void c_unpack(device uint* a [[buffer(1)]], device float* o [[buffer(0)]],
                     uint t [[thread_position_in_grid]]) {
    uint v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    float2 r = unpack_unorm2x16_to_float(v0);
    o[t+0] = r.x; o[t+1] = r.y;
    o[t+2] = as_type<float>(v1); o[t+3] = as_type<float>(v2);
    o[t+4] = as_type<float>(v3); o[t+5] = as_type<float>(v4);
    o[t+6] = as_type<float>(v5); o[t+7] = as_type<float>(v0);
}
// ---- cvt_i2f : int -> float --------------------------------------------
kernel void c_i2f(device int* a [[buffer(1)]], device float* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    int v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = float(v0);
    o[t+1] = as_type<float>(v1); o[t+2] = as_type<float>(v2);
    o[t+3] = as_type<float>(v3); o[t+4] = as_type<float>(v4);
    o[t+5] = as_type<float>(v5); o[t+6] = as_type<float>(v0);
}
// ---- cvt_i2f_src : two converts feeding one ALU combine -----------------
kernel void c_i2f_src(device int* a [[buffer(1)]], device float* o [[buffer(0)]],
                      uint t [[thread_position_in_grid]]) {
    int v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = float(v0) + float(v1);
    o[t+1] = as_type<float>(v2); o[t+2] = as_type<float>(v3);
    o[t+3] = as_type<float>(v4); o[t+4] = as_type<float>(v5);
    o[t+5] = as_type<float>(v0); o[t+6] = as_type<float>(v1);
}
// ---- cvt_f2i : float -> int --------------------------------------------
kernel void c_f2i(device float* a [[buffer(1)]], device int* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    float v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = int(v0);
    o[t+1] = as_type<int>(v1); o[t+2] = as_type<int>(v2);
    o[t+3] = as_type<int>(v3); o[t+4] = as_type<int>(v4);
    o[t+5] = as_type<int>(v5); o[t+6] = as_type<int>(v0);
}
// ---- cvt_f2h (byte0==0x11, dst r1) -------------------------------------
kernel void c_f2h(device float* a [[buffer(1)]], device half* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    float v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = half(v0);
    o[t+1] = as_type<half2>(v1).x; o[t+2] = as_type<half2>(v2).x;
    o[t+3] = as_type<half2>(v3).x; o[t+4] = as_type<half2>(v4).x;
    o[t+5] = as_type<half2>(v5).x; o[t+6] = as_type<half2>(v0).x;
}
// ---- cvt_f2h_dst (generalised dst nibble) ------------------------------
kernel void c_f2h_dst(device float* a [[buffer(1)]], device half* o [[buffer(0)]],
                      uint t [[thread_position_in_grid]]) {
    float v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = half(v0); o[t+1] = half(v1); o[t+2] = half(v2);
    o[t+3] = as_type<half2>(v3).x; o[t+4] = as_type<half2>(v4).x;
    o[t+5] = as_type<half2>(v5).x; o[t+6] = as_type<half2>(v0).x;
}
// ---- cvt_bf16 : float -> bfloat ----------------------------------------
kernel void c_f2bf(device float* a [[buffer(1)]], device bfloat* o [[buffer(0)]],
                   uint t [[thread_position_in_grid]]) {
    float v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3], v4=a[t+4], v5=a[t+5];
    o[t+0] = bfloat(v0);
    o[t+1] = as_type<bfloat2>(v1).x; o[t+2] = as_type<bfloat2>(v2).x;
    o[t+3] = as_type<bfloat2>(v3).x; o[t+4] = as_type<bfloat2>(v4).x;
    o[t+5] = as_type<bfloat2>(v5).x; o[t+6] = as_type<bfloat2>(v0).x;
}
// ---- packed_half2_hi carrier : packed 2xfp16 ALU -----------------------
kernel void c_ph2(device half2* a [[buffer(1)]], device half2* o [[buffer(0)]],
                  uint t [[thread_position_in_grid]]) {
    half2 v0=a[t+0], v1=a[t+1], v2=a[t+2], v3=a[t+3];
    o[t+0] = v0 * v1;
    o[t+1] = v2; o[t+2] = v3; o[t+3] = v0; o[t+4] = v1;
}

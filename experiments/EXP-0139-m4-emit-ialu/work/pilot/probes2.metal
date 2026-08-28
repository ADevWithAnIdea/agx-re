#include <metal_stdlib>
using namespace metal;
kernel void k_sin(device const float* a [[buffer(0)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=precise::sin(a[i]); }
kernel void k_exp(device const float* a [[buffer(0)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=exp2(a[i]); }
kernel void k_log(device const float* a [[buffer(0)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=log2(a[i]); }
kernel void k_rsq(device const float* a [[buffer(0)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=rsqrt(a[i]); }
kernel void k_rcp(device const float* a [[buffer(0)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=1.0f/a[i]; }
kernel void k_not(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=~a[i]; }
kernel void k_and(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=a[i]&0x0f0f0f0fu; }
kernel void k_pop(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=popcount(a[i]); }
kernel void k_clz(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=clz(a[i]); }
kernel void k_rev(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=reverse_bits(a[i]); }
kernel void k_simdsh(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=simd_shuffle(a[i], 3u); }
kernel void k_abs(device const int* a [[buffer(0)]], device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=abs(a[i]); }
kernel void k_sat(device const uint* a [[buffer(0)]], device uchar* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=uchar(a[i]); }
kernel void k_pack(device const float4* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=pack_float_to_unorm4x8(a[i]); }
kernel void k_unpk(device const uint* a [[buffer(0)]], device float4* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=unpack_unorm4x8_to_float(a[i]); }
kernel void k_shlv(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=rotate(a[i], 7u); }
kernel void k_madlong(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=uint(mulhi(a[i], 12345u)); }

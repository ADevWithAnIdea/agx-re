#include <metal_stdlib>
using namespace metal;
// --- float-out variants (dst 32-bit -> 0x09 float ALU) ---
kernel void k_hadd(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]); o[i]=float(x+y); }
kernel void k_hmul(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]); o[i]=float(x*y); }
// --- half-out variants (dst 16-bit -> 0x10 half ALU) ---
// output packed as half2 in one 32-bit word: lane0 = result, lane1 = 0 sentinel
kernel void k_hraw_add(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]); o[i]=half2(x+y, half(0)); }
kernel void k_hraw_mul(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]); o[i]=half2(x*y, half(0)); }
kernel void k_hraw_sub(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]); o[i]=half2(x-y, half(0)); }
kernel void k_hraw_fma(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device const float* c [[buffer(3)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]),z=half(c[i]); o[i]=half2(fma(x,y,z), half(0)); }
// packed half2 both lanes live
kernel void k_h2raw_add(device const float2* a [[buffer(0)]], device const float2* b [[buffer(1)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half2 x=half2(a[i]),y=half2(b[i]); o[i]=x+y; }
kernel void k_h2raw_mul(device const float2* a [[buffer(0)]], device const float2* b [[buffer(1)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half2 x=half2(a[i]),y=half2(b[i]); o[i]=x*y; }
kernel void k_hraw_addsat(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]], device half2* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { half x=half(a[i]),y=half(b[i]); o[i]=half2(saturate(x+y), half(0)); }

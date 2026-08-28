#include <metal_stdlib>
using namespace metal;
kernel void k_popcount(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=popcount(a[i]); }
kernel void k_clz(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=clz(a[i]); }
kernel void k_ctz(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=ctz(a[i]); }
kernel void k_reverse(device const uint* a [[buffer(0)]], device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=reverse_bits(a[i]); }

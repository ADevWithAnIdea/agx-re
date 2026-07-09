#include <metal_stdlib>
using namespace metal;
kernel void k_u64add(device ulong* out [[buffer(0)]], device const ulong* a [[buffer(1)]], device const ulong* b [[buffer(2)]], uint g [[thread_position_in_grid]]) { out[g] = a[g] + b[g]; }

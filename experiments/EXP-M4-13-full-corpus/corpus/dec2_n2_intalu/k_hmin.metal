#include <metal_stdlib>
using namespace metal;
kernel void k_hmin(device half* out [[buffer(0)]], device const half* a [[buffer(1)]], device const half* b [[buffer(2)]], uint g [[thread_position_in_grid]]) { out[g] = min(a[g], b[g]); }

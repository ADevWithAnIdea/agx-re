#include <metal_stdlib>
using namespace metal;
kernel void k_imin_ba(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], device const int* b [[buffer(2)]], uint g [[thread_position_in_grid]]) { out[g] = min(b[g], a[g]); }

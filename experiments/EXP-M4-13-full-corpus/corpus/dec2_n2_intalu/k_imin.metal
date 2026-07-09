#include <metal_stdlib>
using namespace metal;
kernel void k_imin(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], device const int* b [[buffer(2)]], uint g [[thread_position_in_grid]]) { out[g] = min(a[g], b[g]); }

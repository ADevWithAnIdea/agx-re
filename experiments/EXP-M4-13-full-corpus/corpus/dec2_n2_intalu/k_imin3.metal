#include <metal_stdlib>
using namespace metal;
kernel void k_imin3(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], device const int* b [[buffer(2)]], device const int* c [[buffer(3)]], uint g [[thread_position_in_grid]]) { out[g] = min(min(a[g],b[g]),c[g]); }

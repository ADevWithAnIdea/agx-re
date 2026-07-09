#include <metal_stdlib>
using namespace metal;
kernel void k_imax_imm(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], uint g [[thread_position_in_grid]]) { out[g] = max(a[g], 100); }

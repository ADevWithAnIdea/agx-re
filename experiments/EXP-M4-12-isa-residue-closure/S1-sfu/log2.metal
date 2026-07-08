#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=log2(a[i]); }

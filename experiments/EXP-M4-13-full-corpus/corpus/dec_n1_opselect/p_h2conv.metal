#include <metal_stdlib>
using namespace metal;
kernel void p_h2conv(device half2* o[[buffer(0)]], device const float2* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=half2(a[i]); }

#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device float2* o[[buffer(0)]], device const uint* p[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=unpack_unorm2x16_to_float(p[i]); }

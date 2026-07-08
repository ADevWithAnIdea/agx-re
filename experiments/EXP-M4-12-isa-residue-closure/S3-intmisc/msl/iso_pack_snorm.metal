#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device uint* o[[buffer(0)]], device const float2* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=pack_float_to_snorm2x16(a[i]); }

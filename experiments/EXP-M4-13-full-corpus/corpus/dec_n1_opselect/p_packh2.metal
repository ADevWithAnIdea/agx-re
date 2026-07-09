#include <metal_stdlib>
using namespace metal;
kernel void p_packh2(device uint* o[[buffer(0)]], device const float2* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=as_type<uint>(half2(a[i])); }

#include <metal_stdlib>
using namespace metal;
kernel void p_h2f(device float* o[[buffer(0)]], device const half* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=float(a[i]); }

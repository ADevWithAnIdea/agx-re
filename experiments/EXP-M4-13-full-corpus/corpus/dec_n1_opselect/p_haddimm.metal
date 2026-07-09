#include <metal_stdlib>
using namespace metal;
kernel void p_haddimm(device half* o[[buffer(0)]], device const half* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+half(1.5); }

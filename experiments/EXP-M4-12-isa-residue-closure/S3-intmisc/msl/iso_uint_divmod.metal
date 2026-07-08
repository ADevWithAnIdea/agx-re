#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ uint x=a[i],y=b[i]; o[i]=(x/(y|1u))+(x%(y|1u)); }

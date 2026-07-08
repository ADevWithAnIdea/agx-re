#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device half* o[[buffer(0)]], device const half* a[[buffer(1)]], device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ half x=a[i],y=b[i]; o[i]=(x+y)*(x-y); }

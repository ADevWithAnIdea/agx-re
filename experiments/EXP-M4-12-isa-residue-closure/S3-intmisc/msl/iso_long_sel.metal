#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device long* o[[buffer(0)]], device const long* a[[buffer(1)]], device const long* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]<b[i]?a[i]:b[i]; }

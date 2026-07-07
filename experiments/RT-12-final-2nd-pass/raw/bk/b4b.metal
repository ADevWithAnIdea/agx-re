#include <metal_stdlib>
using namespace metal;
struct P { float k; };
kernel void k(device float* o [[buffer(0)]], device float* a [[buffer(1)]], constant P& p [[buffer(2)]], uint i [[thread_position_in_grid]]){ o[i]=p.k+a[i]; }

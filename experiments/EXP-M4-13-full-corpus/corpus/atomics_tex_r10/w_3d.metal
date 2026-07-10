#include <metal_stdlib>
using namespace metal;
kernel void k(texture3d<float,access::write> w[[texture(0)]], uint3 g[[thread_position_in_grid]]){ w.write(float4(1,2,3,4), g); }

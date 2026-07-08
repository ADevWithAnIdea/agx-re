#include <metal_stdlib>
using namespace metal;
kernel void k(texture3d<float, access::read> t [[texture(0)]],
              device const uint* zz [[buffer(1)]],
              device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint3(0,0,zz[i])).r;
}

#include <metal_stdlib>
using namespace metal;
kernel void k(texture2d_ms<float, access::read> t [[texture(0)]],
              device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(0,0), 2).r;   // read sample 2
}
